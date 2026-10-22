"""Private, bounded Director-only last-good and inspection state.

The old MOSS main-node cache and shared string codec are intentionally unused.
Successes keep their own expiry; failed/restarted runs cannot renew old results.
"""
from __future__ import annotations

from collections import OrderedDict
import copy
import json
import re
import threading
import time
import uuid

try:
    from . import moss_authoring_bundle as bundle
    from . import moss_authoring_contract as contract
    from . import moss_authoring as authoring
    from . import moss_image_contract as native
except ImportError:
    import moss_authoring_bundle as bundle
    import moss_authoring_contract as contract
    import moss_authoring as authoring
    import moss_image_contract as native

NODE_ID = "MOSSAuthoringDirectorT8"
TTL_SECONDS = 3600
MAX_SLOTS = 50
MAX_FAILED_BYTES = contract.MAX_BUNDLE_BYTES
_SLOT = re.compile(r"[A-Za-z0-9._:-]{8,160}\Z")
_CODE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,79}\Z")
_LOCK = threading.RLock()
_RUNS: OrderedDict[str, dict] = OrderedDict()


def valid_slot(slot):
    return isinstance(slot, str) and bool(_SLOT.fullmatch(slot))


def _prune():
    now = time.monotonic()
    for slot in list(_RUNS):
        record = _RUNS[slot]
        if record.get("last_good") and now - record["last_good_at"] >= TTL_SECONDS:
            record["last_good"] = ""
            record["last_good_at"] = 0.0
        if now - record["updated"] >= TTL_SECONDS:
            _RUNS.pop(slot, None)
    while len(_RUNS) > MAX_SLOTS:
        _RUNS.popitem(last=False)


def begin(slot):
    if slot != "" and not valid_slot(slot):
        native.fail("invalid_authoring_slot", "Invalid Director recovery slot / 整册恢复槽无效。")
    token = uuid.uuid4().hex
    if slot:
        with _LOCK:
            _prune()
            record = _RUNS.setdefault(slot, {"last_good": "", "last_good_at": 0.0})
            record.update(token=token, updated=time.monotonic(), phase="running", code="", partial=None)
            _RUNS.move_to_end(slot)
            _prune()
    return token


def commit(slot, token, bundle_text):
    # Full validation precedes any write; a failed/partial artifact never enters
    # the selectable success namespace, even when its JSON is well-formed.
    if not isinstance(bundle_text, str):
        native.fail("invalid_authoring_bundle", "Expected complete bundle JSON text / 需要完整集合JSON文本。")
    checked = bundle.validate_bundle(bundle_text)
    text = contract.encode(checked)
    if not valid_slot(slot) or not isinstance(token, str):
        return False
    with _LOCK:
        _prune()
        record = _RUNS.get(slot)
        if record is None or record["token"] != token:
            return False
        now = time.monotonic()
        record.update(last_good=text, last_good_at=now, updated=now, phase="completed", code="", partial=None)
        _RUNS.move_to_end(slot)
        return True


def _clean_strings(value):
    if isinstance(value, str):
        return native.KEY_RE.sub("[REDACTED]", value.encode("utf-8", errors="replace").decode("utf-8"))
    if isinstance(value, dict):
        return {_clean_strings(key): _clean_strings(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean_strings(item) for item in value]
    return value


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _inspection(partial, code):
    safe_code = code if isinstance(code, str) and _CODE.fullmatch(code) else "authoring_failed"
    artifact = {"schema_version": "t8-moss-authoring-inspection/v1", "inspection_only": True, "complete": False,
                "code": safe_code, "units": [], "stage_records": [], "raw": "", "truncated": False}
    if not isinstance(partial, dict):
        artifact["truncated"] = True
        return artifact
    if set(partial) - {"units", "stage_records", "raw"}:
        artifact["truncated"] = True
    records = partial.get("stage_records", [])
    if not isinstance(records, list):
        records = []; artifact["truncated"] = True
    if len(records) > bundle.MAX_STAGE_RECORDS:
        artifact["truncated"] = True
    seen = set()
    for raw_record in records[:bundle.MAX_STAGE_RECORDS]:
        try:
            record = contract.parse(contract.encode(raw_record))
            contract.fields(record, {"stage_id", "kind", "unit_id", "calls", "corrections"})
            contract.identifier(record["stage_id"])
            if record["stage_id"] in seen or record["kind"] not in ("plan", "source", "translation"):
                raise ValueError
            if record["kind"] == "plan":
                if record["unit_id"] != "": raise ValueError
            else:
                contract.identifier(record["unit_id"])
            if (type(record["calls"]) is not int or record["calls"] not in (1, 2)
                    or type(record["corrections"]) is not int or record["corrections"] != record["calls"] - 1):
                raise ValueError
        except (native.MossContractError, ValueError, TypeError):
            artifact["truncated"] = True
            continue
        seen.add(record["stage_id"])
        artifact["stage_records"].append(record)
    units = partial.get("units", [])
    if not isinstance(units, list):
        units = []; artifact["truncated"] = True
    if len(units) > contract.MAX_UNITS:
        artifact["truncated"] = True
    seen_units = set()
    for raw_unit in units[:contract.MAX_UNITS]:
        try:
            unit = contract.parse(contract.encode(raw_unit))
            if not isinstance(unit, dict): raise ValueError
            profile = authoring.FISHER if unit.get("sidecar") is None else authoring.COMIC
            contract.validate_unit(unit, profile, 10)
            if unit["unit_id"] in seen_units: raise ValueError
        except (native.MossContractError, ValueError, TypeError):
            artifact["truncated"] = True
            continue
        cleaned = _clean_strings(unit)
        candidate = {**artifact, "units": [*artifact["units"], cleaned]}
        if len(_json_bytes(candidate)) > MAX_FAILED_BYTES:
            artifact["truncated"] = True
            break
        seen_units.add(unit["unit_id"])
        artifact["units"].append(cleaned)
    raw = partial.get("raw", "")
    if not isinstance(raw, str):
        raw = ""; artifact["truncated"] = True
    raw = _clean_strings(raw)
    payload = raw.encode("utf-8")
    if len(payload) > MAX_FAILED_BYTES:
        raw = payload[:MAX_FAILED_BYTES].decode("utf-8", errors="ignore")
        artifact["truncated"] = True
    # Escaped newlines/control characters can cost more than their UTF-8 input.
    # Keep the longest complete code-point prefix that fits the JSON artifact.
    low, high = 0, len(raw)
    while low < high:
        middle = (low + high + 1) // 2
        candidate = {**artifact, "raw": raw[:middle]}
        if len(_json_bytes(candidate)) <= MAX_FAILED_BYTES:
            low = middle
        else:
            high = middle - 1
    artifact["raw"] = raw[:low]
    if low < len(raw): artifact["truncated"] = True
    return artifact


def failed(slot, token, partial, code):
    if not valid_slot(slot) or not isinstance(token, str):
        return
    # Avoid processing a stale run's potentially large payload in the common
    # case, then recheck under the lock after bounded sanitization.
    with _LOCK:
        _prune()
        record = _RUNS.get(slot)
        if record is None or record["token"] != token:
            return
    artifact = _inspection(partial, code)
    with _LOCK:
        _prune()
        record = _RUNS.get(slot)
        if record is None or record["token"] != token:
            return
        record.update(updated=time.monotonic(), phase="failed", code=artifact["code"], partial=artifact)
        _RUNS.move_to_end(slot)


def recover(slot):
    if not valid_slot(slot):
        native.fail("missing_authoring_recovery", "No Director result is available / 没有可恢复的整册结果。")
    with _LOCK:
        _prune()
        text = _RUNS.get(slot, {}).get("last_good", "")
    if not text:
        native.fail("missing_authoring_recovery", "No complete Director result or it expired / 整册结果不存在或已过期。")
    return bundle.validate_bundle(text)


def status(slot):
    if not valid_slot(slot):
        return {"recoverable": False, "phase": "unconfigured", "code": "", "failed_draft_available": False, "truncated": False}
    with _LOCK:
        _prune()
        record = _RUNS.get(slot, {})
        partial = record.get("partial")
        return {"recoverable": bool(record.get("last_good")), "phase": record.get("phase", "missing"),
                "code": record.get("code", ""), "failed_draft_available": partial is not None,
                "truncated": bool(partial.get("truncated")) if partial else False}


def draft(slot):
    if not valid_slot(slot):
        return None
    with _LOCK:
        _prune()
        artifact = _RUNS.get(slot, {}).get("partial")
        return copy.deepcopy(artifact) if artifact is not None else None


def clear():
    with _LOCK:
        _RUNS.clear()
