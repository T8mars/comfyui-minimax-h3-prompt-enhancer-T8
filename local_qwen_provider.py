from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

try:
    from .local_qwen_media import (
        LocalQwenMediaError,
        build_local_media_parts,
        estimate_message_tokens,
    )
    from .local_qwen_runtime import (
        AUTO_MMPROJ,
        DEFAULT_MMPROJ_FILENAME,
        DEFAULT_MODEL_FILENAME,
        LOCAL_QWEN_MANAGER,
        LOCAL_REASONING_OPTIONS,
        LOCAL_COMFY_MEMORY_POLICIES,
        LOCAL_RELEASE_COMFY_AUTO,
        LOCAL_THINK_OFF,
        LOCAL_THINK_ON,
        LOCAL_UNLOAD_AFTER_RUN,
        LOCAL_UNLOAD_POLICIES,
        LocalQwenRuntimeError,
        resolve_mmproj_path,
        resolve_model_path,
    )
except ImportError:
    from local_qwen_media import (
        LocalQwenMediaError,
        build_local_media_parts,
        estimate_message_tokens,
    )
    from local_qwen_runtime import (
        AUTO_MMPROJ,
        DEFAULT_MMPROJ_FILENAME,
        DEFAULT_MODEL_FILENAME,
        LOCAL_QWEN_MANAGER,
        LOCAL_REASONING_OPTIONS,
        LOCAL_COMFY_MEMORY_POLICIES,
        LOCAL_RELEASE_COMFY_AUTO,
        LOCAL_THINK_OFF,
        LOCAL_THINK_ON,
        LOCAL_UNLOAD_AFTER_RUN,
        LOCAL_UNLOAD_POLICIES,
        LocalQwenRuntimeError,
        resolve_mmproj_path,
        resolve_model_path,
    )


LOCAL_QWEN_API_MODE = "本地 GGUF（llama.cpp / Qwen，离线）"
LEGACY_LOCAL_QWEN_API_MODE = "本地 Qwen3.8-27B（GGUF，离线）"
DEFAULT_CONTEXT_SIZE = 32768
DEFAULT_MAX_TOKENS = 4096
DEFAULT_VIDEO_SAMPLE_FPS = 2.0
MAX_VISUAL_PARTS = 16
CONTEXT_SAFETY_TOKENS = 1024


_CJK_CHARACTER_RE = re.compile(r"[\u3400-\u9fff]")
_LATIN_WORD_RE = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")


def _language_family(value: Any) -> str | None:
    normalized = str(value or "").strip().casefold()
    if normalized in {"中文", "chinese", "simplified chinese", "zh", "zh-cn"}:
        return "zh"
    if normalized in {"english", "英文", "en"} or normalized.startswith("english（"):
        return "en"
    return None


def needs_local_language_repair(text: str, target_language: Any) -> bool:
    """Return True only for an obvious descriptive-language miss.

    H3 field names, Music 3 headings, labels, timestamps, and protected source
    text legitimately use another language, so this deliberately ignores mixed
    outputs and only catches strongly one-sided results such as an all-English
    response after the user selected Chinese. The check is provider-independent:
    local GGUF and cloud models can both overweight long embedded Skills.
    """

    family = _language_family(target_language)
    if family is None:
        return False
    value = str(text or "")
    cjk_characters = len(_CJK_CHARACTER_RE.findall(value))
    latin_words = len(_LATIN_WORD_RE.findall(value))
    if family == "zh":
        return latin_words >= 24 and cjk_characters <= max(6, latin_words // 5)
    return cjk_characters >= 24 and latin_words <= max(6, cjk_characters // 5)


def local_language_lock(target_language: Any) -> str:
    family = _language_family(target_language)
    if family == "zh":
        return (
            "FINAL LOCAL OUTPUT LANGUAGE LOCK / 本地输出语言最终锁定：说明正文必须使用简体中文。"
            "返回前静默检查，所有描述性句子和字段值都必须写成自然、准确的简体中文。"
            "仅协议要求的字段名、段落标题、镜头/时间码语法、参考标签、技术标记，以及用户原始对白、"
            "歌词、品牌/UI 文案或画面可见文字按协议或原文保留。前面内嵌的英文 Skill 和示例只定义"
            "结构，绝不能把说明正文切换回英文。"
        )
    if family == "en":
        return (
            "FINAL LOCAL OUTPUT LANGUAGE LOCK: The selected descriptive language is English. Before returning, "
            "silently verify that every descriptive sentence and field value is written in natural English. Keep "
            "only required protocol tokens and exact user-provided dialogue, lyrics, brand copy, UI copy, or visible "
            "text in their required/original form. Embedded examples define structure only."
        )
    return ""


def local_language_repair_messages(text: str, target_language: Any) -> list[dict[str, str]]:
    family = _language_family(target_language)
    target = "简体中文" if family == "zh" else "English"
    if family == "zh":
        system = (
            "你是严格的语言纠正编辑器。只返回修正后的最终成品。保持全部事实、顺序、结构、协议要求的"
            "字段/段落名、镜头标签、时间码、参考标签、技术标记，以及用户原始对白、歌词、品牌/UI 文案"
            "和画面可见文字不变。只把描述性正文和字段值改为自然、准确的简体中文；不要解释、删减、"
            "扩写或重新设计内容。"
        )
    else:
        system = (
            "You are a strict language-correction editor. Return only the corrected final artifact. Preserve all "
            "facts, ordering, structure, required field/section names, shot labels, timestamps, reference labels, "
            "technical tokens, and exact quoted dialogue, lyrics, brand/UI copy, and visible text. Translate only "
            "descriptive prose and field values into English. Do not explain, shorten, expand, or redesign it."
        )
    return [
        {
            "role": "system",
            "content": system,
        },
        {
            "role": "user",
            "content": json.dumps(
                {"target_descriptive_language": target, "draft_to_correct": str(text or "")},
                ensure_ascii=False,
            ),
        },
    ]


def apply_local_language_lock(
    messages: list[dict[str, Any]], target_language: Any
) -> list[dict[str, Any]]:
    """Append the selected language as the final instruction in both roles.

    Models can overweight long embedded English Skills/examples. Keeping this
    instruction last in both the system and user text makes the serialized UI
    value unambiguous without removing any official source. The historical
    function name is retained for compatibility with existing imports.
    """

    lock = local_language_lock(target_language)
    if not lock:
        return messages
    prepared: list[dict[str, Any]] = []
    for message in messages:
        updated = dict(message)
        content = updated.get("content")
        if isinstance(content, str):
            updated["content"] = content.rstrip() + "\n\n" + lock
        elif isinstance(content, list):
            parts: list[dict[str, Any]] = []
            appended = False
            for part in content:
                item = dict(part)
                if not appended and item.get("type") == "text":
                    item["text"] = str(item.get("text") or "").rstrip() + "\n\n" + lock
                    appended = True
                parts.append(item)
            if not appended:
                parts.insert(0, {"type": "text", "text": lock})
            updated["content"] = parts
        prepared.append(updated)
    return prepared


class LocalQwenProviderError(RuntimeError):
    pass


def is_local_qwen_api_mode(value: Any) -> bool:
    return str(value or "").strip() in {LOCAL_QWEN_API_MODE, LEGACY_LOCAL_QWEN_API_MODE}


@dataclass(frozen=True)
class LocalQwenSettings:
    model_filename: str = DEFAULT_MODEL_FILENAME
    mmproj_filename: str = DEFAULT_MMPROJ_FILENAME
    context_size: int = DEFAULT_CONTEXT_SIZE
    max_tokens: int = DEFAULT_MAX_TOKENS
    think_mode: str = LOCAL_THINK_OFF
    reasoning_effort: str = "medium"
    video_sample_fps: float = DEFAULT_VIDEO_SAMPLE_FPS
    unload_policy: str = LOCAL_UNLOAD_AFTER_RUN
    comfy_memory_policy: str = LOCAL_RELEASE_COMFY_AUTO

    def normalized(self) -> "LocalQwenSettings":
        context_size = int(self.context_size)
        max_tokens = int(self.max_tokens)
        sample_fps = float(self.video_sample_fps)
        if context_size < 8192 or context_size > 65536:
            raise LocalQwenProviderError("Local GGUF context size must be between 8192 and 65536 tokens.")
        if max_tokens < 256 or max_tokens > 8192:
            raise LocalQwenProviderError("Local GGUF output token limit must be between 256 and 8192.")
        if max_tokens + CONTEXT_SAFETY_TOKENS >= context_size:
            raise LocalQwenProviderError("Local GGUF output token limit leaves no usable input context.")
        if sample_fps < 0.25 or sample_fps > 8.0:
            raise LocalQwenProviderError("Local video sample rate must be between 0.25 and 8 fps.")
        if self.think_mode not in (LOCAL_THINK_OFF, LOCAL_THINK_ON):
            raise LocalQwenProviderError(f"Unsupported local think mode: {self.think_mode}")
        if self.reasoning_effort not in LOCAL_REASONING_OPTIONS:
            raise LocalQwenProviderError(f"Unsupported local reasoning effort: {self.reasoning_effort}")
        if self.unload_policy not in LOCAL_UNLOAD_POLICIES:
            raise LocalQwenProviderError(f"Unsupported local unload policy: {self.unload_policy}")
        if self.comfy_memory_policy not in LOCAL_COMFY_MEMORY_POLICIES:
            raise LocalQwenProviderError(
                f"Unsupported local ComfyUI memory policy: {self.comfy_memory_policy}"
            )
        return LocalQwenSettings(
            model_filename=str(self.model_filename or DEFAULT_MODEL_FILENAME).strip(),
            mmproj_filename=str(self.mmproj_filename or DEFAULT_MMPROJ_FILENAME).strip(),
            context_size=context_size,
            max_tokens=max_tokens,
            think_mode=self.think_mode,
            reasoning_effort=self.reasoning_effort,
            video_sample_fps=sample_fps,
            unload_policy=self.unload_policy,
            comfy_memory_policy=self.comfy_memory_policy,
        )


def settings_from_values(
    *,
    local_model: str = DEFAULT_MODEL_FILENAME,
    local_mmproj: str = DEFAULT_MMPROJ_FILENAME,
    local_context_size: int = DEFAULT_CONTEXT_SIZE,
    local_max_tokens: int = DEFAULT_MAX_TOKENS,
    local_think_mode: str = LOCAL_THINK_OFF,
    local_reasoning_effort: str = "medium",
    local_video_sample_fps: float = DEFAULT_VIDEO_SAMPLE_FPS,
    local_unload_policy: str = LOCAL_UNLOAD_AFTER_RUN,
    local_comfy_memory_policy: str = LOCAL_RELEASE_COMFY_AUTO,
) -> LocalQwenSettings:
    return LocalQwenSettings(
        model_filename=local_model,
        mmproj_filename=local_mmproj,
        context_size=local_context_size,
        max_tokens=local_max_tokens,
        think_mode=local_think_mode,
        reasoning_effort=local_reasoning_effort,
        video_sample_fps=local_video_sample_fps,
        unload_policy=local_unload_policy,
        comfy_memory_policy=local_comfy_memory_policy,
    ).normalized()


def build_local_multimodal_parts(
    media_plan: list[dict[str, Any]],
    settings: LocalQwenSettings,
    *,
    max_visual_parts: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    visual_limit = (
        MAX_VISUAL_PARTS
        if max_visual_parts is None
        else min(MAX_VISUAL_PARTS, max(0, int(max_visual_parts)))
    )
    if media_plan and visual_limit <= 0:
        raise LocalQwenProviderError(
            "Local GGUF has no context budget left for connected visual media. "
            "Reduce prompt/template text, lower max output tokens, or increase local_context_size."
        )
    try:
        return build_local_media_parts(
            media_plan,
            video_sample_fps=settings.video_sample_fps,
            max_visual_parts=visual_limit,
        )
    except LocalQwenMediaError as error:
        raise LocalQwenProviderError(str(error)) from error


def local_visual_part_budget(
    text_only_messages: list[dict[str, Any]], settings: LocalQwenSettings
) -> int:
    estimated_text = estimate_message_tokens(text_only_messages)
    available = (
        settings.context_size
        - settings.max_tokens
        - CONTEXT_SAFETY_TOKENS
        - estimated_text
    )
    return max(0, min(MAX_VISUAL_PARTS, available // 1024))


class LocalQwenProvider:
    def __init__(self, settings: LocalQwenSettings, *, vision: bool):
        self.settings = settings.normalized()
        self.vision = bool(vision)
        self.server = None
        self.closed = False
        self._owns_run = False

    def __enter__(self) -> "LocalQwenProvider":
        if self.server is not None:
            return self
        try:
            model = resolve_model_path(self.settings.model_filename, label="local Qwen model")
            mmproj = (
                resolve_mmproj_path(
                    self.settings.mmproj_filename,
                    model_filename=self.settings.model_filename,
                )
                if self.vision
                else None
            )
            self.server = LOCAL_QWEN_MANAGER.begin_run(
                model=model,
                mmproj=mmproj,
                context_size=self.settings.context_size,
                comfy_memory_policy=self.settings.comfy_memory_policy,
                think_mode=self.settings.think_mode == LOCAL_THINK_ON,
            )
            self._owns_run = True
        except LocalQwenRuntimeError as error:
            raise LocalQwenProviderError(str(error)) from error
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close(force=exc_type is not None)

    def close(self, *, force: bool = False) -> None:
        if self.closed:
            return
        self.closed = True
        if self.server is None or not self._owns_run:
            return
        self._owns_run = False
        try:
            LOCAL_QWEN_MANAGER.end_run(self.settings.unload_policy, force=force)
        except LocalQwenRuntimeError as error:
            raise LocalQwenProviderError(str(error)) from error

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
        seed: int,
        max_tokens: int | None = None,
    ) -> str:
        if self.server is None:
            self.__enter__()
        if self.server is None:
            raise LocalQwenProviderError("Local GGUF provider could not start.")
        output_tokens = int(max_tokens or self.settings.max_tokens)
        if output_tokens < 256 or output_tokens > self.settings.max_tokens:
            raise LocalQwenProviderError(
                f"Local output max_tokens must be between 256 and configured limit {self.settings.max_tokens}."
            )
        estimated_input = estimate_message_tokens(messages)
        available = self.settings.context_size - output_tokens - CONTEXT_SAFETY_TOKENS
        if estimated_input > available:
            raise LocalQwenProviderError(
                "Local GGUF context budget exceeded before inference: "
                f"estimated input {estimated_input} tokens, available {available}. "
                "Reduce reference media/template text, lower video sample rate, or increase local_context_size."
            )
        try:
            content, _usage = LOCAL_QWEN_MANAGER.complete(
                self.server,
                messages=messages,
                seed=int(seed),
                max_tokens=output_tokens,
                temperature=float(temperature),
                think_mode=self.settings.think_mode == LOCAL_THINK_ON,
                reasoning_effort=self.settings.reasoning_effort,
            )
        except LocalQwenRuntimeError as error:
            raise LocalQwenProviderError(str(error)) from error
        return content


__all__ = [
    "DEFAULT_CONTEXT_SIZE",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_VIDEO_SAMPLE_FPS",
    "AUTO_MMPROJ",
    "LOCAL_QWEN_API_MODE",
    "LEGACY_LOCAL_QWEN_API_MODE",
    "LocalQwenProvider",
    "LocalQwenProviderError",
    "LocalQwenSettings",
    "build_local_multimodal_parts",
    "apply_local_language_lock",
    "local_visual_part_budget",
    "local_language_lock",
    "local_language_repair_messages",
    "is_local_qwen_api_mode",
    "needs_local_language_repair",
    "settings_from_values",
]
