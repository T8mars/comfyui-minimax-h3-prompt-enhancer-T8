"""Run ownership for H3 Image's optional, process-local last-success cache."""
from __future__ import annotations

from collections import OrderedDict
import re
import threading
import time
import uuid

from .completion_recovery import complete_recovery_record

NODE_ID = "MiniMaxH3ImagePromptEnhancerT8"
_LOCK = threading.RLock()
_RUNS = OrderedDict()
_SLOT = re.compile(r"[A-Za-z0-9._:-]{8,160}")


def _prune():
    now = time.monotonic()
    for slot, (_, timestamp) in list(_RUNS.items()):
        if now - timestamp > 3600:
            del _RUNS[slot]
    while len(_RUNS) > 50:
        _RUNS.popitem(last=False)


def begin(slot):
    if not isinstance(slot, str) or (slot and not _SLOT.fullmatch(slot)):
        raise ValueError("Invalid H3 Image recovery slot / 恢复槽无效。")
    token = uuid.uuid4().hex
    if slot:
        with _LOCK:
            _prune()
            _RUNS[slot] = (token, time.monotonic())
            _RUNS.move_to_end(slot)
            _prune()
    return token


def commit(slot, token, outputs):
    if not slot:
        return False
    with _LOCK:
        _prune()
        if _RUNS.get(slot, (None,))[0] != token:
            return False
        # Checking ownership and replacing the shared last-good record must
        # be atomic with begin(). A late old run cannot supersede new intent.
        saved = complete_recovery_record(NODE_ID, slot, outputs)
        _RUNS[slot] = (token, time.monotonic())
        return saved
