from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from .local_qwen_media import (
        LocalQwenMediaError,
        build_local_media_parts,
        estimate_message_tokens,
    )
    from .local_qwen_runtime import (
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
        resolve_model_path,
    )
except ImportError:
    from local_qwen_media import (
        LocalQwenMediaError,
        build_local_media_parts,
        estimate_message_tokens,
    )
    from local_qwen_runtime import (
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
        resolve_model_path,
    )


LOCAL_QWEN_API_MODE = "本地 Qwen3.8-27B（GGUF，离线）"
DEFAULT_CONTEXT_SIZE = 32768
DEFAULT_MAX_TOKENS = 4096
DEFAULT_VIDEO_SAMPLE_FPS = 2.0
MAX_VISUAL_PARTS = 16
CONTEXT_SAFETY_TOKENS = 1024


class LocalQwenProviderError(RuntimeError):
    pass


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
            raise LocalQwenProviderError("Local Qwen context size must be between 8192 and 65536 tokens.")
        if max_tokens < 256 or max_tokens > 8192:
            raise LocalQwenProviderError("Local Qwen output token limit must be between 256 and 8192.")
        if max_tokens + CONTEXT_SAFETY_TOKENS >= context_size:
            raise LocalQwenProviderError("Local Qwen output token limit leaves no usable input context.")
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
            "Local Qwen has no context budget left for connected visual media. "
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
                resolve_model_path(self.settings.mmproj_filename, label="local Qwen vision projector")
                if self.vision
                else None
            )
            self.server = LOCAL_QWEN_MANAGER.begin_run(
                model=model,
                mmproj=mmproj,
                context_size=self.settings.context_size,
                comfy_memory_policy=self.settings.comfy_memory_policy,
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
            raise LocalQwenProviderError("Local Qwen provider could not start.")
        output_tokens = int(max_tokens or self.settings.max_tokens)
        if output_tokens < 256 or output_tokens > self.settings.max_tokens:
            raise LocalQwenProviderError(
                f"Local output max_tokens must be between 256 and configured limit {self.settings.max_tokens}."
            )
        estimated_input = estimate_message_tokens(messages)
        available = self.settings.context_size - output_tokens - CONTEXT_SAFETY_TOKENS
        if estimated_input > available:
            raise LocalQwenProviderError(
                "Local Qwen context budget exceeded before inference: "
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
    "LOCAL_QWEN_API_MODE",
    "LocalQwenProvider",
    "LocalQwenProviderError",
    "LocalQwenSettings",
    "build_local_multimodal_parts",
    "local_visual_part_budget",
    "settings_from_values",
]
