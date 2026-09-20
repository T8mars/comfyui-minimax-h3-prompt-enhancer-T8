"""Small, versioned contracts shared by the music planning nodes.

The external skills are knowledge sources.  They are not copied into runtime
prompts and their YAML formats are not exposed as a ComfyUI wire contract.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping


LYRIC_PLAN_SCHEMA = "t8-lyric-plan/v1"
ARRANGEMENT_PLAN_SCHEMA = "t8-arrangement-plan/v1"
PLAN_SOURCES = {"explicit", "inferred", "unknown"}
_API_KEY_RE = re.compile(r"sk-[A-Za-z0-9_-]{16,}")


class MusicPlanError(ValueError):
    pass


def clean_text(value: Any, *, limit: int = 12000) -> str:
    text = str(value or "").strip()
    if len(text) > limit:
        raise MusicPlanError(f"文本超过 {limit} 字符上限。")
    if _API_KEY_RE.search(text):
        raise MusicPlanError("创作文本疑似包含 API Key，请移到 API Key 输入。")
    return text


def plan_id(schema: str, payload: Mapping[str, Any]) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((schema + "\n" + body).encode("utf-8")).hexdigest()[:16]


def _source(value: Any, default: str = "unknown") -> str:
    value = str(value or default).strip().lower()
    return value if value in PLAN_SOURCES else default


def parse_plan(value: Any, schema: str) -> dict[str, Any] | None:
    """Parse a connected plan without accepting arbitrary provider instructions."""
    if value in (None, ""):
        return None
    if isinstance(value, Mapping):
        data = dict(value)
    else:
        try:
            data = json.loads(str(value))
        except (TypeError, ValueError) as exc:
            raise MusicPlanError("连接的音乐计划不是有效 JSON。") from exc
    if not isinstance(data, dict) or data.get("schema_version") != schema:
        raise MusicPlanError(f"只支持 {schema} 计划。")
    serialized = json.dumps(data, ensure_ascii=False)
    if len(serialized) > 200000:
        raise MusicPlanError("连接的音乐计划过大。")
    if _API_KEY_RE.search(serialized):
        raise MusicPlanError("连接的音乐计划疑似包含 API Key，请移除凭据后再连接。")
    return data


def lyric_plan(*, idea: str, language: str, song_type: str, to_whom: str,
               moment: str, anchor: str, lyrics: str, structure: str,
               source: str = "explicit", parent_plan_id: str = "") -> dict[str, Any]:
    payload = {
        "schema_version": LYRIC_PLAN_SCHEMA,
        "language": language,
        "intent": {
            "song_type": song_type,
            "one_thing": idea,
            "to_whom": to_whom,
            "at_what_moment": moment,
            "anchor_object": anchor,
        },
        "structure": structure,
        "lyrics": lyrics,
        "source": _source(source),
        "parent_plan_id": parent_plan_id,
        "locked": {"lyrics": bool(lyrics)},
    }
    payload["plan_id"] = plan_id(LYRIC_PLAN_SCHEMA, payload)
    return payload


def arrangement_plan(*, idea: str, genre: str, instruments: str, bpm: int,
                     meter: str, key_scale: str, duration: int, structure: str,
                     lyrics_plan_id: str = "", source: str = "explicit") -> dict[str, Any]:
    payload = {
        "schema_version": ARRANGEMENT_PLAN_SCHEMA,
        "intent": idea,
        "genre": genre,
        "instruments": instruments,
        "bpm": int(bpm or 0),
        "meter": meter,
        "key_scale": key_scale,
        "target_duration_seconds": int(duration or 0),
        "structure": structure,
        "lyric_plan_id": lyrics_plan_id,
        "source": _source(source),
        "locked": {},
    }
    payload["plan_id"] = plan_id(ARRANGEMENT_PLAN_SCHEMA, payload)
    return payload


def compact_json(data: Mapping[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


__all__ = [
    "ARRANGEMENT_PLAN_SCHEMA", "LYRIC_PLAN_SCHEMA", "MusicPlanError",
    "arrangement_plan", "clean_text", "compact_json", "lyric_plan",
    "parse_plan", "plan_id",
]
