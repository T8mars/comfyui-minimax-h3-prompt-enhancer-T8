from __future__ import annotations

import json
import re
from typing import Any

from comfy_api.latest import io

try:
    from .performance_director import performance_risk_warnings, semantic_anchor_warnings
except ImportError:
    from performance_director import performance_risk_warnings, semantic_anchor_warnings


FAMILY_AUTO = "AUTO（本地识别）"
FAMILY_H3 = "MiniMax H3"
FAMILY_SEEDANCE = "Seedance 2.0"
FAMILY_MUSIC = "MiniMax Music 3"
FAMILY_OPTIONS = [FAMILY_AUTO, FAMILY_H3, FAMILY_SEEDANCE, FAMILY_MUSIC]
SHOT_OPTIONS = ["AUTO", *[str(value) for value in range(1, 21)]]
LANGUAGE_OPTIONS = ["AUTO", "中文", "English"]
INSTRUMENTAL_OPTIONS = ["AUTO", "是", "否"]
H3_FIELDS = ("integrated_multimodal_description", "overall_soundscape", "non_diegetic_music")
H3_REFERENCE_FIELDS = (
    "subject_definitions", "summary", "retention_analysis", "detailed_description",
    "overall_soundscape", "non_diegetic_music",
)
_H3_SECTION_RE = re.compile(
    r"^[ \t]*(" + "|".join(dict.fromkeys((*H3_FIELDS, *H3_REFERENCE_FIELDS))) + r")[ \t]*:",
    re.IGNORECASE | re.MULTILINE,
)
_H3_LITERAL_RE = re.compile(
    r'<d\b[^>]*>.*?(?:</d>|$)|"(?:\\.|[^"\\])*"|“[^”]*”|‘[^’]*’',
    re.IGNORECASE | re.DOTALL,
)
_H3_SHOT_RE = re.compile(r"\[\s*Shot\s*(\d+)\s*\]", re.IGNORECASE)
_H3_CUT_TIME_RE = re.compile(r"[ \t\r\n]*At[ \t]+(\d{2}):(\d{2})\.(\d{3})(?![\d.])", re.IGNORECASE)
_H3_SPEAKER_RE = re.compile(r"\(\s*S[1-9]\d*(?:\s*,\s*S[1-9]\d*)*\s*\)", re.IGNORECASE)
_H3_VOCAL_ACTION_RE = re.compile(
    r"说[:：]|说道|喊道|低语|\b(?:says?|speaks?|sings?|shouts?|whispers?|replies|exclaims|asks?)\b",
    re.IGNORECASE,
)


def _family(prompt: str, selected: str) -> str:
    if selected != FAMILY_AUTO:
        return selected
    lowered = prompt.lower()
    if "### global metadata" in lowered or "### vocal details" in lowered or "### arrangement" in lowered:
        return FAMILY_MUSIC
    if _H3_SECTION_RE.search(prompt) or re.search(r"\[shot\s+\d+\]", prompt, re.I):
        return FAMILY_H3
    return FAMILY_SEEDANCE


def _warning(code: str, message: str, severity: str = "warning") -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


def _shot_numbers(prompt: str) -> list[int]:
    values = re.findall(r"(?:\[\s*Shot\s*|镜头\s*)(\d+)(?:\s*\]|\s*[:：])", prompt, re.I)
    return [int(value) for value in values]


def _mask_h3_literals(text: str) -> str:
    """Keep offsets/newlines while excluding exact dialogue and visible-text literals."""
    return _H3_LITERAL_RE.sub(lambda match: re.sub(r"[^\r\n]", " ", match.group()), text)


def _h3_sections(text: str) -> tuple[dict[str, str], list[str]]:
    matches = list(_H3_SECTION_RE.finditer(_mask_h3_literals(text)))
    sections: dict[str, str] = {}
    order: list[str] = []
    for index, match in enumerate(matches):
        name = match.group(1).lower()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[name] = text[match.end():end].strip()
        order.append(name)
    return sections, order


def _h3_required_fields(sections: dict[str, str], task_intent: str) -> tuple[str, ...]:
    task = str(task_intent or "").strip()
    explicit = re.match(r"^(Ref2VA|T2VA|I2VA|FL2VA|L2VA)\b", task, re.IGNORECASE)
    if explicit:
        return H3_REFERENCE_FIELDS if explicit.group(1).lower() == "ref2va" else H3_FIELDS
    if re.match(r"^full[- ]reference\b", task, re.IGNORECASE):
        return H3_REFERENCE_FIELDS
    if any(field in sections for field in H3_REFERENCE_FIELDS[:4]):
        return H3_REFERENCE_FIELDS
    return H3_FIELDS


def _h3_timeline(text: str, sections: dict[str, str], fields: tuple[str, ...]) -> str:
    body_field = "detailed_description" if fields == H3_REFERENCE_FIELDS else H3_FIELDS[0]
    if sections:
        # A missing body must not turn retention/definitions into a target timeline.
        return sections.get(body_field, "")
    # Still diagnose unstructured drafts, without treating native alignment lines as shots.
    return re.sub(
        r"(?mi)^[ \t]*(?:For the target video,|How the reference pictures align with the target video)[^\r\n]*",
        "", text,
    )


def _h3_timeline_times(timeline: str) -> tuple[list[int], list[float], bool]:
    masked = _mask_h3_literals(timeline)
    shots: list[int] = []
    cut_times: list[float] = []
    malformed = False
    for index, shot in enumerate(_H3_SHOT_RE.finditer(masked)):
        shots.append(int(shot.group(1)))
        time = _H3_CUT_TIME_RE.match(masked, shot.end())
        if index == 0:
            malformed = malformed or bool(time)
        elif time and int(time.group(2)) < 60:
            cut_times.append(int(time.group(1)) * 60 + int(time.group(2)) + int(time.group(3)) / 1000)
        else:
            malformed = True
    return shots, cut_times, malformed


def _h3_missing_speaker(timeline: str) -> bool:
    masked = _mask_h3_literals(timeline)
    shot_starts = [match.end() for match in _H3_SHOT_RE.finditer(masked)]
    previous_end = 0
    # An on-screen literal may itself print '<d>...</d>'; it is not a vocal event.
    dialogue_blocks = [match for match in _H3_LITERAL_RE.finditer(timeline)
                       if re.match(r"<d\b", match.group(), re.IGNORECASE)]
    for block in dialogue_blocks:
        start = max([previous_end, *[position for position in shot_starts if position <= block.start()]])
        context = masked[start:block.start()]
        previous_end = block.end()
        if _H3_SPEAKER_RE.search(context):
            continue
        # Lyrics cued within a reused soundtrack have an Audio source, not a new human speaker.
        if re.search(r"<Audio\s+[1-9]\d*>", context, re.IGNORECASE) and not _H3_VOCAL_ACTION_RE.search(context):
            continue
        return True
    if dialogue_blocks:
        return False
    # Quotes on signs and negative dialogue policies are not evidence of a vocal event.
    return bool(_H3_VOCAL_ACTION_RE.search(masked) and not _H3_SPEAKER_RE.search(masked))


def inspect_prompt(
    prompt: Any,
    prompt_family: str = FAMILY_AUTO,
    expected_shot_count: str = "AUTO",
    expected_language: str = "AUTO",
    instrumental: str = "AUTO",
    task_intent: str = "",
    duration_seconds: int = 0,
    source_prompt: Any = "",
) -> tuple[str, str, str]:
    original = str(prompt or "")
    text = original.strip()
    family = _family(text, prompt_family)
    warnings: list[dict[str, str]] = []
    if not text:
        warnings.append(_warning("empty_prompt", "提示词为空。", "error"))
    sections, section_order = _h3_sections(text) if family == FAMILY_H3 else ({}, [])
    h3_fields = _h3_required_fields(sections, task_intent)
    timeline = _h3_timeline(text, sections, h3_fields) if family == FAMILY_H3 else text
    if family == FAMILY_H3:
        shots, all_timecodes, malformed_shot_time = _h3_timeline_times(timeline)
    else:
        shots = _shot_numbers(text)
        all_timecodes = [float(a) * 60 + float(b) for a, b in re.findall(r"\b(\d{1,2}):(\d{2}(?:\.\d{1,3})?)\b", text)]
    if shots:
        expected_sequence = list(range(1, len(shots) + 1))
        if shots != expected_sequence:
            warnings.append(_warning("shot_sequence", "镜头编号不是从 1 开始且连续递增。"))
    if expected_shot_count != "AUTO" and len(shots) != int(expected_shot_count):
        warnings.append(_warning(
            "shot_count_mismatch",
            f"检测到 {len(shots)} 个镜头标记，期望 {expected_shot_count} 个。",
        ))
    outside_duration = bool(all_timecodes) and (
        max(all_timecodes) >= float(duration_seconds) if family == FAMILY_H3
        else max(all_timecodes) > float(duration_seconds)
    )
    if duration_seconds and outside_duration:
        warnings.append(_warning("duration_budget", "检测到超出目标时长的时间码。"))

    if family == FAMILY_H3:
        missing = [field for field in h3_fields if not sections.get(field, "").strip()]
        if missing:
            warnings.append(_warning("h3_missing_core_fields", "缺少 H3 核心字段：" + ", ".join(missing)))
        if section_order and not missing and section_order != list(h3_fields):
            warnings.append(_warning("h3_field_order", "H3 核心字段顺序不正确或混入了其他模式字段。"))
        if malformed_shot_time:
            warnings.append(_warning("h3_shot_timecode", "H3 首镜头不得带时间码；后续镜头须使用 At MM:SS.mmm 的有效切点。"))
        if all_timecodes and any(current <= previous for previous, current in zip([0.0, *all_timecodes], all_timecodes)):
            warnings.append(_warning("non_monotonic_timecodes", "时间码未按先后顺序排列。"))
        if re.search(r"<Picture\s+\d+>|<Video\s+\d+>", text, re.I) and "reference" not in text.lower() and "参考" not in text:
            warnings.append(_warning("material_role_unclear", "检测到素材标签，但未说明素材角色或保留边界。"))
        if _h3_missing_speaker(timeline):
            warnings.append(_warning("speaker_contract", "存在对白/台词，但未检测到明确说话人。"))
        vocal_blocks = [match.group() for match in _H3_LITERAL_RE.finditer(timeline)
                        if re.match(r"<d\b", match.group(), re.I)]
        if any(not re.match(r"<d>\s*\[[A-Za-z][A-Za-z -]*\]", block, re.I) for block in vocal_blocks):
            warnings.append(_warning("vocal_language_tag", "H3 对白需使用英文语言标签，例如 <d>[Chinese] 原句</d>；不要把协议标签改为[中文]。"))
        if re.search(r"字幕|招牌|标题|屏幕文字|subtitle|title|on-screen text", text, re.I) and not re.search(r"逐字|准确|不得新增|verbatim|exact|no extra", text, re.I):
            warnings.append(_warning("visible_text_contract", "存在可见文字意图，但未检测到逐字准确或禁止新增文字约束。"))
    elif family == FAMILY_SEEDANCE:
        references = re.findall(r"@(?:图片|视频|音频|Image|Video|Audio)\s*\d+", text, re.I)
        if references and not re.search(r"参考|承担|作为|锁定|preserve|reference|role", text, re.I):
            warnings.append(_warning("seedance_reference_role", "检测到素材引用，但角色分工不够明确。"))
        intent = str(task_intent or "").strip().lower()
        if intent and any(value in intent for value in ("edit", "编辑", "extend", "延长", "补齐", "track")):
            if not re.search(r"@(?:视频|Video)\s*\d+", text, re.I):
                warnings.append(_warning("seedance_task_reference", "编辑、延长或轨道任务未检测到明确的视频引用。"))
        if references and not re.search(r"一致|稳定|保持|锁定|不变|consistent|stable|preserve|lock", text, re.I):
            warnings.append(_warning("seedance_stability", "多模态提示词未检测到主体/场景稳定性约束。", "info"))
        if len(shots) > 1 and not re.search(r"切|转场|随后|then|cut|transition", text, re.I):
            warnings.append(_warning("seedance_transition", "多镜头提示词未检测到明确的衔接或转场线索。", "info"))
        if re.search(r"字幕|标题|文字|subtitle|title|text", text, re.I) and not re.search(r"准确|逐字|不要|保留|exact|verbatim|no subtitle", text, re.I):
            warnings.append(_warning("text_contract", "存在文字/字幕意图，但未检测到准确性或禁止项约束。"))
    else:
        headings = ["### Global Metadata", "### Vocal Details", "### Arrangement"]
        missing = [heading for heading in headings if heading.lower() not in text.lower()]
        if missing:
            warnings.append(_warning("music_missing_headings", "缺少 Music 3 Caption 标题：" + ", ".join(missing)))
        is_instrumental = instrumental == "是" or bool(re.search(r"\[Instrumental\]|纯器乐|instrumental", text, re.I))
        if is_instrumental and re.search(r"lead vocal|主唱|演唱|歌词", text, re.I):
            warnings.append(_warning("instrumental_vocal_conflict", "纯器乐设置与人声/歌词描述可能冲突。"))
        if expected_language == "中文" and re.search(r"\b(?:the|and|you|love|night)\b", text, re.I) and not re.search(r"[\u4e00-\u9fff]", text):
            warnings.append(_warning("lyrics_language", "期望中文，但正文主要呈现为英文。"))
        if expected_language == "English" and re.search(r"[\u4e00-\u9fff]", text) and not re.search(r"\b(?:the|and|you|love|night)\b", text, re.I):
            warnings.append(_warning("lyrics_language", "期望 English，但正文主要呈现为中文。"))

    if family in {FAMILY_H3, FAMILY_SEEDANCE}:
        warnings.extend(performance_risk_warnings(text, family))
        warnings.extend(semantic_anchor_warnings(source_prompt, text, family))

    penalty_weights = {"error": 15, "warning": 8, "info": 3, "advisory": 0}
    penalty = sum(penalty_weights.get(item["severity"], 0) for item in warnings)
    score = max(0, 100 - penalty)
    report = {
        "schema_version": "t8-prompt-inspector/v1",
        "family": family,
        "structural_score": score,
        "score_scope": "deterministic structure only; not a creative-quality judgment",
        "detected_shots": len(shots),
        "warnings": warnings,
    }
    summary = f"{family} · 结构分 {score}/100 · {len(warnings)} 条提示（仅本地结构检查，不判断创意质量）"
    return original, json.dumps(report, ensure_ascii=False, indent=2), summary


class T8PromptInspector(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8PromptInspector",
            display_name="T8 Prompt Inspector (Local, Non-blocking)",
            category="T8/Utilities",
            description=(
                "Local deterministic structure checks plus non-scoring community-research-inspired performance advisories. "
                "It returns the original prompt unchanged and never calls an LLM."
            ),
            inputs=[
                io.String.Input("prompt", display_name="待检查提示词", multiline=True, default="", force_input=True),
                io.Combo.Input("prompt_family", display_name="提示词家族", options=FAMILY_OPTIONS, default=FAMILY_AUTO),
                io.Combo.Input("expected_shot_count", display_name="期望镜头数", options=SHOT_OPTIONS, default="AUTO"),
                io.Combo.Input("expected_language", display_name="期望语言", options=LANGUAGE_OPTIONS, default="AUTO"),
                io.Combo.Input("instrumental", display_name="纯器乐", options=INSTRUMENTAL_OPTIONS, default="AUTO"),
                io.String.Input("task_intent", display_name="任务意图（可选）", optional=True, default="", socketless=True),
                io.Int.Input("duration_seconds", display_name="目标时长（0=AUTO）", default=0, min=0, max=900, step=1),
                io.String.Input(
                    "source_prompt",
                    display_name="原始提示词（可选，用于语义漂移检查）",
                    optional=True,
                    multiline=True,
                    default="",
                    force_input=True,
                ),
            ],
            outputs=[
                io.String.Output(display_name="original_prompt"),
                io.String.Output(display_name="warnings_json"),
                io.String.Output(display_name="summary"),
            ],
        )

    @classmethod
    def execute(
        cls,
        prompt,
        prompt_family=FAMILY_AUTO,
        expected_shot_count="AUTO",
        expected_language="AUTO",
        instrumental="AUTO",
        task_intent="",
        duration_seconds=0,
        source_prompt="",
    ) -> io.NodeOutput:
        return io.NodeOutput(*inspect_prompt(
            prompt=prompt,
            prompt_family=prompt_family,
            expected_shot_count=expected_shot_count,
            expected_language=expected_language,
            instrumental=instrumental,
            task_intent=task_intent,
            duration_seconds=duration_seconds,
            source_prompt=source_prompt,
        ))


__all__ = ["T8PromptInspector", "inspect_prompt"]
