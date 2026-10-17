"""Private MOSS transaction/draft state. Successful typed results use the shared cache."""
from __future__ import annotations

from collections import OrderedDict
import re
import threading
import time
import uuid

try:
    from .completion_recovery import complete_recovery_record, recovery_status
except ImportError:
    from completion_recovery import complete_recovery_record, recovery_status

NODE_ID = "MOSSImagePromptEnhancerT8"
TTL_SECONDS = 3600
MAX_SLOTS = 50
MAX_FAILED_BYTES = 128 * 1024
_SLOT = re.compile(r"^[A-Za-z0-9._:-]{8,160}$")
_LOCK = threading.RLock()
_RUNS: OrderedDict[str, dict] = OrderedDict()


def valid_slot(slot):
    return isinstance(slot, str) and bool(_SLOT.fullmatch(slot))


def _prune():
    now = time.monotonic()
    for slot in list(_RUNS):
        if now - _RUNS[slot]["updated"] > TTL_SECONDS:
            _RUNS.pop(slot, None)
    while len(_RUNS) > MAX_SLOTS:
        _RUNS.popitem(last=False)


def begin(slot):
    if slot and not valid_slot(slot):
        raise ValueError("Invalid MOSS recovery slot / 恢复槽无效。")
    token = uuid.uuid4().hex
    pending_slot = "t8-moss-run-" + token
    if slot:
        with _LOCK:
            _prune()
            _RUNS[slot] = {"token": token, "updated": time.monotonic(), "phase": "running", "draft": "", "code": ""}
            _RUNS.move_to_end(slot)
            _prune()
    return token, pending_slot


def commit(slot, token, outputs):
    if not slot:
        return False
    with _LOCK:
        _prune()
        record = _RUNS.get(slot)
        if record is None or record["token"] != token:
            return False
        # Do not call begin_recovery_record on this last-good slot. A failed
        # subsequent run must not erase the last complete result.
        result = complete_recovery_record(NODE_ID, slot, outputs)
        record.update(phase="completed", updated=time.monotonic(), draft="", code="")
        return result


def failed(slot, token, raw, code):
    if not slot:
        return
    with _LOCK:
        _prune()
        record = _RUNS.get(slot)
        if record is None or record["token"] != token:
            return
        payload = str(raw).encode("utf-8", errors="replace")
        record.update(phase="failed", updated=time.monotonic(), code=str(code)[:80],
                      draft=payload[:MAX_FAILED_BYTES].decode("utf-8", errors="ignore"),
                      truncated=len(payload) > MAX_FAILED_BYTES)


def status(slot):
    if not valid_slot(slot):
        return {"recoverable": False, "failed_draft_available": False, "phase": "unconfigured"}
    with _LOCK:
        _prune()
        record = _RUNS.get(slot, {})
        prior = recovery_status(NODE_ID, slot)
        return {"recoverable": bool(prior.get("recoverable")), "failed_draft_available": bool(record.get("draft")),
                "phase": record.get("phase", prior.get("state", "missing")), "code": record.get("code", ""),
                "failed_draft_truncated": bool(record.get("truncated", False))}


def draft(slot):
    if not valid_slot(slot):
        return None
    with _LOCK:
        _prune()
        record = _RUNS.get(slot)
        if not record or not record.get("draft"):
            return None
        return {"schema_version": "t8-moss-failed-draft/v1", "verified": False, "code": record["code"],
                "draft": record["draft"], "truncated": bool(record.get("truncated", False))}


def clear():
    with _LOCK:
        _RUNS.clear()
