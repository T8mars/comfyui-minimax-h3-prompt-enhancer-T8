"""Model-free H3 Relay authoring compiler; the execution node owns Relay plans.

Only strings and a frame count cross this boundary.  No ComfyUI, model, network,
token binding, attention, or downstream hash implementation is imported here.
"""

from __future__ import annotations

import json
import math
import re
from fractions import Fraction
from typing import Any


NORMAL = "普通增强 / Normal"
RELAY = "Prompt Relay 编排"
FPS = 24
MAX_EVENTS = 32
MIN_EVENT_FRAMES = 5
_BASIC_FIELDS = (
    "integrated_multimodal_description", "overall_soundscape", "non_diegetic_music",
)
_REFERENCE_FIELDS = (
    "subject_definitions", "summary", "retention_analysis", "detailed_description",
    "overall_soundscape", "non_diegetic_music",
)
_RANGE = re.compile(
    r"^\s*([0-9]+(?:\.[0-9]+)?)\s*[-:–—]\s*([0-9]+(?:\.[0-9]+)?)\s*$"
)
_LINE_BREAKS = frozenset("\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029")


def _error(message: str) -> ValueError:
    return ValueError(f"Prompt Relay: {message}")


def _nonempty(value: Any, name: str, *, single_line: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _error(f"{name} must be a non-empty string / 必须为非空文本。")
    # Check before stripping: even a trailing line break violates the contract.
    if single_line and ("|" in value or any(c in _LINE_BREAKS for c in value)):
        raise _error(
            f"{name} contains a newline or ASCII |; preserve exact user text and "
            "report the format conflict instead of deleting these characters."
        )
    return value


def _request(duration_seconds: Any, event_count: Any, task_type: str) -> tuple[float, int, int, str]:
    if isinstance(duration_seconds, bool) or not isinstance(duration_seconds, (int, float)):
        raise _error("duration_seconds must be a finite positive number.")
    try:
        duration = float(duration_seconds)
        frame_value = duration * FPS
    except (OverflowError, ValueError) as exc:
        raise _error("duration_seconds is outside the supported numeric range.") from exc
    if not math.isfinite(frame_value) or duration <= 0:
        raise _error("duration_seconds must be a finite positive number.")
    delivery = max(1, round(frame_value))  # Same Python ties-to-even as the runner.
    if delivery < MIN_EVENT_FRAMES:
        raise _error("duration_seconds must provide at least 5 delivery frames at 24 FPS.")
    if isinstance(event_count, bool) or not isinstance(event_count, int) or not 0 <= event_count <= MAX_EVENTS:
        raise _error("event_count must be an integer from 0 (automatic) to 32.")
    if event_count * MIN_EVENT_FRAMES > delivery:
        raise _error("Requested event_count cannot fit: each event needs at least 5 delivery frames.")
    tasks = {"T2VA", "I2VA", "FL2VA", "L2VA", "Ref2VA"}
    if not isinstance(task_type, str) or task_type not in tasks:
        raise _error(f"Unsupported H3 task_type {task_type!r}.")
    return duration, delivery, event_count, task_type


def _explicit_ranges(value: Any, delivery: int) -> list[tuple[int, int]]:
    if not isinstance(value, str):
        raise _error("time_ranges must be a string containing seconds ranges.")
    if not value.strip():
        return []
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if len(lines) > MAX_EVENTS:
        raise _error("time_ranges supports at most 32 ranges.")
    ranges = []
    previous_end = 0
    for index, line in enumerate(lines, 1):
        match = _RANGE.fullmatch(line)
        if match is None:
            raise _error(f"time_ranges line {index}: use decimal seconds start-end, without units or timecodes.")
        start, end = (float(number) for number in match.groups())
        if not math.isfinite(start * FPS) or not math.isfinite(end * FPS) or end < start:
            raise _error(f"time_ranges line {index} must have finite, ordered endpoints.")
        start_frame, end_frame = round(start * FPS), round(end * FPS)
        if start_frame != previous_end:
            raise _error(f"time_ranges line {index} leaves a gap, overlap, or nonzero start; cover delivery continuously.")
        if end_frame - start_frame < MIN_EVENT_FRAMES:
            raise _error(f"time_ranges line {index} resolves to fewer than 5 frames.")
        if end_frame > delivery:
            raise _error(f"time_ranges line {index} exceeds delivery frame {delivery}; do not include alignment padding.")
        ranges.append((start_frame, end_frame))
        previous_end = end_frame
    if previous_end != delivery:
        raise _error(f"time_ranges must cover all {delivery} delivery frames before alignment padding.")
    return ranges


def _seconds(frame: int) -> str:
    value = f"{frame / FPS:.6f}"
    if not math.isfinite(float(value) * FPS) or round(float(value) * FPS) != frame:
        raise _error("Frame count is too large for a six-decimal seconds round trip.")
    return value.rstrip("0").rstrip(".")


def relay_instruction(duration, event_count=0, time_ranges="", task_type="T2VA") -> str:
    """Validate user timing before an LLM request and describe its JSON envelope."""
    duration, delivery, count, task = _request(duration, event_count, task_type)
    explicit = _explicit_ranges(time_ranges, delivery)
    if explicit and count and len(explicit) != count:
        raise _error("event_count does not match the number of explicit time_ranges.")
    count = len(explicit) if explicit else count
    fields = _REFERENCE_FIELDS if task == "Ref2VA" else _BASIC_FIELDS
    count_rule = (
        f"Return exactly {count} events in the supplied order."
        if count else f"Choose 1..{min(MAX_EVENTS, delivery // MIN_EVENT_FRAMES)} events fitting the story, not a fixed three or five."
    )
    timing = (
        "The authoritative user event ranges in decimal seconds are "
        + json.dumps([f"{_seconds(a)}-{_seconds(b)}" for a, b in explicit])
        if explicit else "There are no explicit ranges. Give positive relative duration weights; code assigns integer frames."
    )
    return f"""H3 PROMPT RELAY AUTHORING OUTPUT CONTRACT
This replaces only the outer plain-text response format. All official H3 core,
language-profile, reference, factual and exact-dialogue rules remain in force.
Return one JSON object and no commentary with exactly these keys:
{{"global_prompt":"stable full-film constraints", "events":[{{"prompt":"current event", "end_state":"settled state after the event", "weight":1}}], "native_prompt":"the COMPLETE original official-format H3 prompt"}}
Task: {task}. Requested duration: {duration:g} seconds; delivery: {delivery} frames
at 24 FPS, ending at {_seconds(delivery)} seconds. {count_rule}
{timing}
- global_prompt contains only persistent identity, appearance, style, shared scene
conditions, camera principles, stable voices, ambience, music and restrictions.
Never put the full plot, future actions or verbatim dialogue in global_prompt.
- Each event has exactly prompt, end_state and weight. prompt describes current
state, action and result, camera and only this event's dialogue/sound. Preserve
all user words, punctuation, identities, relationships and constraints exactly.
Keep object ownership and speaker IDs continuous. No implicit new shot per event.
- prompt and end_state must each be one nonempty line, with no line-break
characters or ASCII |, including inside quoted dialogue. If exact source text
conflicts with that parser contract, report it rather than silently altering it.
- end_state describes an already achieved, stable visible state, not a new action,
dialogue, lyric, cut or future event. Do not include <d> speech in end_state.
- weight is a finite positive JSON number. All actions and dialogue must fit
within delivery time; at least 5 frames per event is a parser minimum, NOT a
speech-duration or quality guarantee. Allocate enough time for complete dialogue.
- The compiler extends ONLY the last event to the 17n+5 plan grid and holds its
already completed end_state in padding. Never schedule new dialogue/actions there.
- native_prompt is a STRING containing the complete ordinary {task} H3 prompt,
not another JSON object, global summary, compiled Relay prompt, or missing excerpt.
Keep the official required sections in order: {', '.join(fields)}. Preserve the
task's required keyframe alignment declarations. Native text describes the SAME
story and requested delivery duration, not the extra Relay alignment padding.
- Reference labels must correspond to actual media. Do not invent audio analysis
or reference connections. An event timeline is not the runner's window timeline.
Do not emit plan hashes, token spans, execution settings, or claims of generation.
"""


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _error(f"JSON contains duplicate key {key!r}.")
        result[key] = value
    return result


def _invalid_constant(value):
    raise _error(f"JSON contains non-finite number {value}; use finite positive weights.")


def _parse(text: Any) -> dict:
    raw = _nonempty(text, "response").strip()
    if raw.startswith("```"):
        fence = re.fullmatch(r"```(?:json)?[ \t]*\r?\n([\s\S]*?)\r?\n```", raw, re.IGNORECASE)
        if fence is None:
            raise _error("Malformed JSON code fence; return exactly one JSON object.")
        raw = fence.group(1)
    try:
        result = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_invalid_constant)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise _error("Response is not valid JSON; return global_prompt, events and native_prompt, with no surrounding prose.") from exc
    if not isinstance(result, dict) or not {"global_prompt", "events", "native_prompt"} <= set(result):
        raise _error("JSON must contain global_prompt, events and native_prompt.")
    return result


def _native(value: Any, task: str) -> str:
    native = _nonempty(value, "native_prompt")
    if native.lstrip().startswith(("{", "[", "```")):
        raise _error("native_prompt must be the original plain official H3 text, not JSON or a code fence.")
    fields = _REFERENCE_FIELDS if task == "Ref2VA" else _BASIC_FIELDS
    pattern = re.compile(r"^[ \t]*(" + "|".join(fields) + r")[ \t]*:", re.MULTILINE)
    matches = list(pattern.finditer(native))
    if [match.group(1) for match in matches] != list(fields):
        raise _error("native_prompt requires each official field once in order: " + ", ".join(fields))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(native)
        if not native[match.end():end].strip():
            raise _error(f"native_prompt field {match.group(1)} cannot be empty.")
    return native  # Do not reformat, translate or replace the ordinary output.


def _weighted_ranges(weights: list[Fraction], delivery: int) -> list[tuple[int, int]]:
    """Minimum-five allocation plus exact largest remainders; stable tie order."""
    remaining = delivery - MIN_EVENT_FRAMES * len(weights)
    if remaining < 0:
        raise _error("Too many events for duration: each needs at least 5 delivery frames.")
    total = sum(weights)
    shares = [remaining * weight / total for weight in weights]
    allocated = [int(share) for share in shares]
    order = sorted(range(len(weights)), key=lambda i: (-(shares[i] - allocated[i]), i))
    for index in order[:remaining - sum(allocated)]:
        allocated[index] += 1
    ranges, cursor = [], 0
    for frames in allocated:
        end = cursor + MIN_EVENT_FRAMES + frames
        ranges.append((cursor, end))
        cursor = end
    return ranges


def compile_relay_response(text, duration_seconds, event_count=0, time_ranges="", task_type="T2VA", output_language="English") -> dict:
    """Compile a validated authoring JSON response to the existing text inputs.

    Explicit seconds first cover the delivery frames. Only the final range is
    extended to the plan grid, keeping narrative completion before delivery ends.
    Validation errors deliberately fail closed for a bounded caller-owned repair.
    """
    duration, delivery, requested_count, task = _request(duration_seconds, event_count, task_type)
    ranges = _explicit_ranges(time_ranges, delivery)
    if ranges and requested_count and len(ranges) != requested_count:
        raise _error("event_count does not match the number of explicit time_ranges.")
    data = _parse(text)
    global_prompt = _nonempty(data["global_prompt"], "global_prompt").strip()
    native = _native(data["native_prompt"], task)
    events = data["events"]
    if not isinstance(events, list) or not 1 <= len(events) <= MAX_EVENTS:
        raise _error("events must be a list containing 1..32 event objects; automatic count is not a zero-event bypass.")
    expected_count = len(ranges) if ranges else requested_count
    if expected_count and len(events) != expected_count:
        raise _error(f"Expected {expected_count} events, received {len(events)}; do not change the user's event count.")
    weights, prompts, states = [], [], []
    authoring_warnings = []
    if set(data) - {"global_prompt", "events", "native_prompt"}:
        authoring_warnings.append("响应的额外顶层字段未用于执行；仅使用 global_prompt、events、native_prompt。")
    for index, event in enumerate(events, 1):
        if not isinstance(event, dict) or not {"prompt", "end_state", "weight"} <= set(event):
            raise _error(f"Event {index} must contain prompt, end_state and weight.")
        if set(event) - {"prompt", "end_state", "weight"}:
            authoring_warnings.append(f"事件 {index} 的额外字段未用于执行；时间由用户范围或 weight 编译，不读取模型额外时间字段。")
        prompts.append(_nonempty(event["prompt"], f"Event {index} prompt", single_line=True).strip())
        state = _nonempty(event["end_state"], f"Event {index} end_state", single_line=True).strip()
        if re.search(r"<\s*(?:d|scenetrans|cutoff)\b", state, re.IGNORECASE):
            authoring_warnings.append(f"事件 {index} 的 end_state 含语音标签；请人工检查是否重复台词或在收尾补齐区加入新语音，末态应只描述已完成状态。")
        states.append(state)
        weight = event["weight"]
        try:
            valid = not isinstance(weight, bool) and isinstance(weight, (int, float)) and math.isfinite(weight) and weight > 0
        except OverflowError:
            valid = False
        if not valid:
            raise _error(f"Event {index} weight must be a finite positive JSON number.")
        weights.append(Fraction(str(weight)))
    timing_source = "explicit_seconds" if ranges else "weighted_integer_frames"
    if not ranges:
        ranges = _weighted_ranges(weights, delivery)
    length = delivery + ((5 - delivery) % 17)
    delivered_ranges = list(ranges)
    ranges[-1] = (ranges[-1][0], length)
    local = []
    for index, (prompt, state, (_, end)) in enumerate(zip(prompts, states, delivered_ranges)):
        boundary = _seconds(end)
        if output_language == "中文":
            line = f"在全局交付时间线的 {boundary} 秒之前完成本事件的动作与对白：{prompt} 已完成的稳定末态：{state}"
        else:
            line = (
                f"Complete this event's actions and any dialogue before {boundary} seconds "
                f"on the global delivery timeline: {prompt} Settled end state: {state}"
            )
        if index == len(prompts) - 1 and length > delivery:
            if output_language == "中文":
                line += (
                    f" 从 {_seconds(delivery)} 至 {_seconds(length)} 秒只延续上述已经完成的稳定末态；"
                    "不增加新动作、对白、歌词、切镜或剧情发展，不重复已完成的动作和台词。"
                )
            else:
                line += (
                    f" From {_seconds(delivery)} to {_seconds(length)} seconds, only hold "
                    "that already completed end state; no new action, dialogue, lyric, "
                    "cut or plot development, and no repetition of completed actions or speech."
                )
        local.append(line)
    range_text = "\n".join(f"{_seconds(start)}-{_seconds(end)}" for start, end in ranges)
    report = {
        "schema": "t8-h3-relay-authoring/v1",
        "status": "static_validation_passed",
        "validation_scope": "仅静态格式与整数帧映射校验；未生成视频，未验证剧情语义、口型或音频。",
        "task_type": task,
        "output_language": output_language,
        "fps": FPS,
        "requested_duration_seconds": duration,
        "delivery_frames": delivery,
        "delivery_duration_seconds": delivery / FPS,
        "relay_length": length,
        "plan_duration_seconds": length / FPS,
        "padding_frames": length - delivery,
        "event_count": len(events),
        "timing_source": timing_source,
        "timing_mode": "seconds",
        "rounding": "Python round (ties-to-even), then six-decimal seconds round trip",
        "allow_gaps": False,
        "allow_overlaps": False,
        "events": [
            {"event": i + 1, "delivery_frames": list(delivered_ranges[i]),
             "plan_frames": list(ranges[i]), "end_state": states[i]}
            for i in range(len(events))
        ],
        "warnings": [
            "时间映射不是成片保证；Relay 是时变注意力偏置，不保证硬切、毫秒对齐、对白不重复或口型同步。",
            "补齐区只保持已完成末态；仍须人工核对事实、逐字台词、动作密度与末态语义。",
        ] + authoring_warnings,
        "wiring_requirements": [
            "Connect global_prompt/local_prompts/time_ranges to the existing Prompt Relay Plan node; set timing_mode=seconds, allow_gaps=false, allow_overlaps=false.",
            "Set Plan length to relay_length; leave prompt_relay_events disconnected because any connected typed chain overrides both text event inputs.",
            "Connect the Plan through the desired Query Route to the runner and explicitly enable apply_exp there; these text outputs alone do not activate Relay.",
            "Keep runner global_prompt empty or identical to plan global_prompt, and segment_prompts_json empty. Preserve the requested delivery duration, not plan padding duration.",
            "Do not connect enhanced_prompt as Relay global_prompt: it remains the complete native H3 prompt for ordinary conditioning.",
            "Query Route, audio mode, sampler, EAV and generation remain downstream responsibilities; multi-event joint_av_exp with lock_source is not supported.",
        ],
    }
    if len(events) == 1:
        report["warnings"].append("单事件计划不会启用多事件竞争路由；不能宣称获得精确时序控制。")
    return {
        "enhanced_prompt": native,
        "global_prompt": global_prompt,
        "local_prompts": "\n".join(local),
        "time_ranges": range_text,
        "relay_length": length,
        "relay_report": json.dumps(report, ensure_ascii=False, indent=2),
    }
