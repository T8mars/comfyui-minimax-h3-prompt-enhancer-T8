from __future__ import annotations

import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

try:
    from comfy.utils import ProgressBar
except ImportError:  # Unit tests and static tooling can run outside ComfyUI.
    ProgressBar = None


_LOCK = threading.Lock()
_RECENT: deque[dict[str, Any]] = deque(maxlen=50)
_SAFE_PROVIDER = re.compile(r"[^A-Za-z0-9 ._()/\-\u4e00-\u9fff]")
_URL = re.compile(r"https?://\S+", re.IGNORECASE)
_API_KEY = re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}")


def _provider_label(value: Any) -> str:
    label = str(value or "unknown")
    label = _URL.sub("[redacted-url]", label)
    label = _API_KEY.sub("[redacted-key]", label)
    return _SAFE_PROVIDER.sub("?", label)[:80]


def _error_category(error: BaseException) -> str:
    text = str(error)
    match = re.search(r"\bcategory=([a-z_]+)", text)
    if match:
        return match.group(1)
    name = type(error).__name__
    if "Timeout" in name:
        return "timeout"
    if "Connection" in name or "SSL" in name:
        return "network"
    return "execution_error"


@dataclass
class DiagnosticsRun:
    component: str
    provider: str
    total_stages: int
    emit_progress: bool = True
    started: float = field(default_factory=time.monotonic)
    _last: float = field(default_factory=time.monotonic)
    _stages: list[dict[str, Any]] = field(default_factory=list)
    _finished: bool = False

    def __post_init__(self) -> None:
        self.component = _provider_label(self.component)
        self.provider = _provider_label(self.provider)
        self.total_stages = max(1, int(self.total_stages))
        self._progress = ProgressBar(self.total_stages) if ProgressBar is not None and self.emit_progress else None

    def advance(self, stage: str, **safe_metrics: Any) -> None:
        if self._finished:
            return
        now = time.monotonic()
        event: dict[str, Any] = {
            "stage": _provider_label(stage),
            "duration_ms": round((now - self._last) * 1000),
        }
        for key in ("attempts", "asset_count", "cache_hit"):
            if key in safe_metrics:
                event[key] = safe_metrics[key]
        self._stages.append(event)
        self._last = now
        if self._progress is not None:
            self._progress.update(1)

    def complete(self, outcome: str, error: BaseException | None = None) -> None:
        if self._finished:
            return
        self._finished = True
        if self._progress is not None:
            self._progress.update_absolute(self.total_stages, self.total_stages)
        record: dict[str, Any] = {
            "schema_version": "t8-redacted-execution-diagnostic/v1",
            "component": self.component,
            "provider": self.provider,
            "outcome": outcome,
            "duration_ms": round((time.monotonic() - self.started) * 1000),
            "stages": list(self._stages),
        }
        if error is not None:
            record["error_type"] = type(error).__name__
            record["error_category"] = _error_category(error)
        with _LOCK:
            _RECENT.appendleft(record)


def diagnostics_snapshot() -> dict[str, Any]:
    with _LOCK:
        recent = list(_RECENT)
    return {
        "schema_version": "t8-redacted-execution-diagnostics/v1",
        "privacy": "No API keys, request/response bodies, prompts, lyrics, template bodies, media, URLs, or model reasoning are stored.",
        "recent": recent,
    }
