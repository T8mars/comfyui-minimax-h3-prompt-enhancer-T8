from __future__ import annotations

import json
import re
from typing import Any

from comfy_api.latest import io


FAMILY_AUTO = "AUTO（本地识别）"
FAMILY_H3 = "MiniMax H3"
FAMILY_SEEDANCE = "Seedance 2.0"
FAMILY_MUSIC = "MiniMax Music 3"
FAMILY_OPTIONS = [FAMILY_AUTO, FAMILY_H3, FAMILY_SEEDANCE, FAMILY_MUSIC]
SHOT_OPTIONS = ["AUTO", *[str(value) for value in range(1, 21)]]
LANGUAGE_OPTIONS = ["AUTO", "中文", "English"]
INSTRUMENTAL_OPTIONS = ["AUTO", "是", "否"]
H3_FIELDS = ("integrated_multimodal_description", "overall_soundscape", "non_diegetic_music")


def _family(prompt: str, selected: str) -> str:
    if selected != FAMILY_AUTO:
        return selected
    lowered = prompt.lower()
    if "### global metadata" in lowered or "### vocal details" in lowered or "### arrangement" in lowered:
        return FAMILY_MUSIC
    if any(field in lowered for field in H3_FIELDS) or re.search(r"\[shot\s+\d+\]", prompt, re.I):
        return FAMILY_H3
    return FAMILY_SEEDANCE


def _warning(code: str, message: str, severity: str = "warning") -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


def _shot_numbers(prompt: str) -> list[int]:
    values = re.findall(r"(?:\[\s*Shot\s*|镜头\s*)(\d+)(?:\s*\]|\s*[:：])", prompt, re.I)
    return [int(value) for value in values]


def inspect_prompt(
    prompt: Any,
    prompt_family: str = FAMILY_AUTO,
    expected_shot_count: str = "AUTO",
    expected_language: str = "AUTO",
    instrumental: str = "AUTO",
    task_intent: str = "",
    duration_seconds: int = 0,
) -> tuple[str, str, str]:
    original = str(prompt or "")
    text = original.strip()
    family = _family(text, prompt_family)
    warnings: list[dict[str, str]] = []
    if not text:
        warnings.append(_warning("empty_prompt", "提示词为空。", "error"))
    shots = _shot_numbers(text)
    if shots:
        expected_sequence = list(range(1, len(shots) + 1))
        if shots != expected_sequence:
            warnings.append(_warning("shot_sequence", "镜头编号不是从 1 开始且连续递增。"))
    if expected_shot_count != "AUTO" and len(shots) != int(expected_shot_count):
        warnings.append(_warning(
            "shot_count_mismatch",
            f"检测到 {len(shots)} 个镜头标记，期望 {expected_shot_count} 个。",
        ))
    all_timecodes = [float(a) * 60 + float(b) for a, b in re.findall(r"\b(\d{1,2}):(\d{2}(?:\.\d{1,3})?)\b", text)]
    if duration_seconds and all_timecodes and max(all_timecodes) > float(duration_seconds):
        warnings.append(_warning("duration_budget", "检测到超出目标时长的时间码。"))

    if family == FAMILY_H3:
        missing = [field for field in H3_FIELDS if not re.search(rf"(?mi)^\s*{field}\s*:", text)]
        if missing:
            warnings.append(_warning("h3_missing_core_fields", "缺少 H3 核心字段：" + ", ".join(missing)))
        if all_timecodes and all_timecodes != sorted(all_timecodes):
            warnings.append(_warning("non_monotonic_timecodes", "时间码未按先后顺序排列。"))
        if re.search(r"<Picture\s+\d+>|<Video\s+\d+>", text, re.I) and "reference" not in text.lower() and "参考" not in text:
            warnings.append(_warning("material_role_unclear", "检测到素材标签，但未说明素材角色或保留边界。"))
        if re.search(r"[“\"]|对白|台词|says?|dialogue", text, re.I) and not re.search(r"说话人|角色名|speaker|旁白|narrator", text, re.I):
            warnings.append(_warning("speaker_contract", "存在对白/台词，但未检测到明确说话人。"))
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

    penalty = sum(15 if item["severity"] == "error" else 8 if item["severity"] == "warning" else 3 for item in warnings)
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
            description="Local deterministic structure checks only. It returns the original prompt unchanged and never calls an LLM.",
            inputs=[
                io.String.Input("prompt", display_name="待检查提示词", multiline=True, default="", force_input=True),
                io.Combo.Input("prompt_family", display_name="提示词家族", options=FAMILY_OPTIONS, default=FAMILY_AUTO),
                io.Combo.Input("expected_shot_count", display_name="期望镜头数", options=SHOT_OPTIONS, default="AUTO"),
                io.Combo.Input("expected_language", display_name="期望语言", options=LANGUAGE_OPTIONS, default="AUTO"),
                io.Combo.Input("instrumental", display_name="纯器乐", options=INSTRUMENTAL_OPTIONS, default="AUTO"),
                io.String.Input("task_intent", display_name="任务意图（可选）", optional=True, default="", socketless=True),
                io.Int.Input("duration_seconds", display_name="目标时长（0=AUTO）", default=0, min=0, max=900, step=1),
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
    ) -> io.NodeOutput:
        return io.NodeOutput(*inspect_prompt(
            prompt,
            prompt_family,
            expected_shot_count,
            expected_language,
            instrumental,
            task_intent,
            duration_seconds,
        ))


__all__ = ["T8PromptInspector", "inspect_prompt"]
