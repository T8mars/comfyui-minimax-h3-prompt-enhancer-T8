from __future__ import annotations

import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any


RECOVERY_ACTION_NORMAL = "normal"
RECOVERY_ACTION_RESTORE = "restore_last"
RECOVERY_TTL_SECONDS = 60 * 60
MAX_RECOVERY_RECORDS = 50
MAX_RECOVERY_TEXT_CHARS = 250_000
_SLOT_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,160}$")
_LOCK = threading.RLock()


class CompletionRecoveryError(RuntimeError):
    pass


@dataclass
class RecoveryRecord:
    component: str
    slot: str
    provider: str
    state: str = "started"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    partial_text: str = ""
    outputs: tuple[str, ...] = ()
    response_id: str = ""
    error_type: str = ""


_RECORDS: OrderedDict[tuple[str, str], RecoveryRecord] = OrderedDict()


def _safe_component(value: Any) -> str:
    component = str(value or "").strip()
    if not component or len(component) > 100 or not re.fullmatch(r"[A-Za-z0-9._-]+", component):
        raise CompletionRecoveryError("Recovery component is invalid.")
    return component


def _safe_slot(value: Any) -> str:
    slot = str(value or "").strip()
    if not slot:
        return ""
    if not _SLOT_PATTERN.fullmatch(slot):
        raise CompletionRecoveryError("Recovery slot is invalid.")
    return slot


def _safe_provider(value: Any) -> str:
    # Provider labels are diagnostic metadata only. Never store URLs or secrets.
    label = str(value or "unknown")
    label = re.sub(r"https?://\S+", "[redacted-url]", label, flags=re.IGNORECASE)
    label = re.sub(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}", "[redacted-key]", label)
    return re.sub(r"[^A-Za-z0-9 ._()/\-\u4e00-\u9fff]", "?", label)[:80]


def _prune_locked(now: float | None = None) -> None:
    current = time.time() if now is None else float(now)
    expired = [key for key, record in _RECORDS.items() if current - record.updated_at > RECOVERY_TTL_SECONDS]
    for key in expired:
        _RECORDS.pop(key, None)
    while len(_RECORDS) > MAX_RECOVERY_RECORDS:
        _RECORDS.popitem(last=False)


def begin_recovery_record(component: Any, slot: Any, provider: Any) -> bool:
    component_name = _safe_component(component)
    slot_name = _safe_slot(slot)
    if not slot_name:
        return False
    record = RecoveryRecord(component=component_name, slot=slot_name, provider=_safe_provider(provider))
    with _LOCK:
        _prune_locked()
        key = (component_name, slot_name)
        _RECORDS[key] = record
        _RECORDS.move_to_end(key)
        _prune_locked()
    return True


def checkpoint_recovery_text(
    component: Any,
    slot: Any,
    text: Any,
    *,
    complete: bool = False,
    response_id: Any = "",
) -> None:
    component_name = _safe_component(component)
    slot_name = _safe_slot(slot)
    if not slot_name:
        return
    value = str(text or "")
    if len(value) > MAX_RECOVERY_TEXT_CHARS:
        value = value[-MAX_RECOVERY_TEXT_CHARS:]
    with _LOCK:
        record = _RECORDS.get((component_name, slot_name))
        if record is None:
            return
        record.partial_text = value
        record.response_id = str(response_id or "")[:160]
        record.state = "stream_complete" if complete else "streaming"
        record.updated_at = time.time()


def complete_recovery_record(component: Any, slot: Any, outputs: Any) -> bool:
    component_name = _safe_component(component)
    slot_name = _safe_slot(slot)
    if not slot_name:
        return False
    values = tuple(str(value) for value in outputs)
    if not values:
        return False
    with _LOCK:
        record = _RECORDS.get((component_name, slot_name))
        if record is None:
            record = RecoveryRecord(component=component_name, slot=slot_name, provider="unknown")
            _RECORDS[(component_name, slot_name)] = record
        if sum(len(value) for value in values) > MAX_RECOVERY_TEXT_CHARS:
            # Recovery is optional and must never turn a successfully generated
            # provider result into a node failure merely because it is unusually
            # large. Keep only redacted status metadata in this case.
            record.outputs = ()
            record.partial_text = ""
            record.state = "unavailable_oversize"
            record.error_type = ""
            record.updated_at = time.time()
            _RECORDS.move_to_end((component_name, slot_name))
            _prune_locked()
            return False
        record.outputs = values
        record.partial_text = ""
        record.state = "completed"
        record.error_type = ""
        record.updated_at = time.time()
        _RECORDS.move_to_end((component_name, slot_name))
        _prune_locked()
    return True


def mark_recovery_ambiguous(component: Any, slot: Any, error: BaseException) -> None:
    component_name = _safe_component(component)
    slot_name = _safe_slot(slot)
    if not slot_name:
        return
    with _LOCK:
        record = _RECORDS.get((component_name, slot_name))
        if record is None:
            return
        record.state = "ambiguous_partial" if record.partial_text else "ambiguous_no_checkpoint"
        record.error_type = type(error).__name__[:80]
        record.updated_at = time.time()


def mark_recovery_failed(component: Any, slot: Any, error: BaseException) -> None:
    component_name = _safe_component(component)
    slot_name = _safe_slot(slot)
    if not slot_name:
        return
    with _LOCK:
        record = _RECORDS.get((component_name, slot_name))
        if record is None or record.state.startswith("ambiguous"):
            return
        record.state = "failed"
        record.error_type = type(error).__name__[:80]
        record.updated_at = time.time()


def recover_outputs(component: Any, slot: Any, expected_count: int) -> tuple[str, ...]:
    component_name = _safe_component(component)
    slot_name = _safe_slot(slot)
    if not slot_name:
        raise CompletionRecoveryError("No recovery slot is configured for this node.")
    with _LOCK:
        _prune_locked()
        record = _RECORDS.get((component_name, slot_name))
        if record is None:
            raise CompletionRecoveryError("No in-memory result exists for this node. Run it once before using recovery.")
        if record.state != "completed" or len(record.outputs) != int(expected_count):
            if record.state == "ambiguous_partial":
                raise CompletionRecoveryError(
                    "Only an incomplete stream checkpoint is available. It was not returned as a final result to avoid silently using truncated output."
                )
            if record.state == "ambiguous_no_checkpoint":
                raise CompletionRecoveryError(
                    "The upstream result is unknown and no response bytes reached ComfyUI. Recovery cannot resubmit because the provider has no idempotent lookup API."
                )
            raise CompletionRecoveryError("The most recent run has no complete recoverable result.")
        return tuple(record.outputs)


def recovery_status(component: Any, slot: Any) -> dict[str, Any]:
    component_name = _safe_component(component)
    slot_name = _safe_slot(slot)
    if not slot_name:
        return {"state": "unconfigured", "recoverable": False, "partial_chars": 0}
    with _LOCK:
        _prune_locked()
        record = _RECORDS.get((component_name, slot_name))
        if record is None:
            return {"state": "missing", "recoverable": False, "partial_chars": 0}
        return {
            "state": record.state,
            "recoverable": record.state == "completed" and bool(record.outputs),
            "partial_chars": len(record.partial_text),
            "response_id_present": bool(record.response_id),
            "age_seconds": max(0, round(time.time() - record.updated_at)),
            "memory_only": True,
            "error_type": record.error_type,
        }


def clear_recovery_records() -> None:
    with _LOCK:
        _RECORDS.clear()


__all__ = [
    "CompletionRecoveryError",
    "RECOVERY_ACTION_NORMAL",
    "RECOVERY_ACTION_RESTORE",
    "begin_recovery_record",
    "checkpoint_recovery_text",
    "clear_recovery_records",
    "complete_recovery_record",
    "mark_recovery_ambiguous",
    "mark_recovery_failed",
    "recover_outputs",
    "recovery_status",
]
