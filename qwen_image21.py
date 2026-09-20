from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import requests

from comfy_api.latest import io

try:
    from .nodes import (
        AI_WORKSHOP_API_MODE,
        AI_WORKSHOP_DEFAULT_MODEL,
        AI_WORKSHOP_MODEL_OPTIONS,
        API_MODES,
        LEGACY_UI_VALUES,
        OPENAI_API_MODE,
        PromptEnhancerError,
        SEEDANCE_API_MODE,
        _image_at,
        _image_count,
        _inline_media_plan,
        _openai_media_plan,
        _ordered_values,
        _provider_config,
        _request_completion,
        _upload_media_plan,
    )
    from .completion_recovery import (
        RECOVERY_ACTION_NORMAL,
        RECOVERY_ACTION_RESTORE,
        CompletionRecoveryError,
        begin_recovery_record,
        complete_recovery_record,
        mark_recovery_failed,
        recover_outputs,
    )
    from .local_qwen_provider import (
        DEFAULT_CONTEXT_SIZE,
        DEFAULT_MAX_TOKENS,
        DEFAULT_VIDEO_SAMPLE_FPS,
        LOCAL_QWEN_API_MODE,
        LOCAL_REASONING_OPTIONS,
        LOCAL_THINK_OFF,
        LOCAL_THINK_ON,
        LOCAL_UNLOAD_AFTER_RUN,
        LOCAL_UNLOAD_POLICIES,
        MAX_OUTPUT_TOKENS,
        LocalQwenProvider,
        LocalQwenProviderError,
        apply_local_language_lock,
        build_local_multimodal_parts,
        is_local_qwen_api_mode,
        local_visual_part_budget,
        settings_from_values as local_qwen_settings,
    )
    from .local_qwen_runtime import (
        AUTO_MMPROJ,
        DEFAULT_MODEL_FILENAME,
        LOCAL_COMFY_MEMORY_POLICIES,
        list_gguf_models,
        list_mmproj_models,
    )
    from .provider_config import (
        PROVIDER_LOCAL,
        PROVIDER_OPENAI,
        PROVIDER_SEEDANCE,
        PROVIDER_WORKSHOP,
        T8ProviderConfigIO,
        merge_provider_config,
    )
except ImportError:
    from nodes import (  # type: ignore
        AI_WORKSHOP_API_MODE,
        AI_WORKSHOP_DEFAULT_MODEL,
        AI_WORKSHOP_MODEL_OPTIONS,
        API_MODES,
        LEGACY_UI_VALUES,
        OPENAI_API_MODE,
        PromptEnhancerError,
        SEEDANCE_API_MODE,
        _image_at,
        _image_count,
        _inline_media_plan,
        _openai_media_plan,
        _ordered_values,
        _provider_config,
        _request_completion,
        _upload_media_plan,
    )
    from completion_recovery import (  # type: ignore
        RECOVERY_ACTION_NORMAL,
        RECOVERY_ACTION_RESTORE,
        CompletionRecoveryError,
        begin_recovery_record,
        complete_recovery_record,
        mark_recovery_failed,
        recover_outputs,
    )
    from local_qwen_provider import (  # type: ignore
        DEFAULT_CONTEXT_SIZE,
        DEFAULT_MAX_TOKENS,
        DEFAULT_VIDEO_SAMPLE_FPS,
        LOCAL_QWEN_API_MODE,
        LOCAL_REASONING_OPTIONS,
        LOCAL_THINK_OFF,
        LOCAL_THINK_ON,
        LOCAL_UNLOAD_AFTER_RUN,
        LOCAL_UNLOAD_POLICIES,
        MAX_OUTPUT_TOKENS,
        LocalQwenProvider,
        LocalQwenProviderError,
        apply_local_language_lock,
        build_local_multimodal_parts,
        is_local_qwen_api_mode,
        local_visual_part_budget,
        settings_from_values as local_qwen_settings,
    )
    from local_qwen_runtime import (  # type: ignore
        AUTO_MMPROJ,
        DEFAULT_MODEL_FILENAME,
        LOCAL_COMFY_MEMORY_POLICIES,
        list_gguf_models,
        list_mmproj_models,
    )
    from provider_config import (  # type: ignore
        PROVIDER_LOCAL,
        PROVIDER_OPENAI,
        PROVIDER_SEEDANCE,
        PROVIDER_WORKSHOP,
        T8ProviderConfigIO,
        merge_provider_config,
    )


NODE_ID = "QwenImage21PromptEnhancerT8"
DISPLAY_NAME = "Qwen Image 2.1 Prompt Enhancer"
QWEN_IMAGE_MODEL_ID = "qwen/qwen3.8-flash-next"
INPUT_MODE_TEXT = "文生图 / Text-to-image"
INPUT_MODE_EDIT = "图像编辑 / Image edit"
INPUT_MODES = [INPUT_MODE_TEXT, INPUT_MODE_EDIT]
RATIO_OPTIONS = ["auto", "1:1", "3:4", "4:3", "16:9", "9:16", "2:1", "1:2"]
OUTPUT_RATIOS = (set(RATIO_OPTIONS) - {"auto"}) | {"2:3", "3:2"}
MAX_IMAGES = 10
MAX_PROMPT_CHARS = 12000
DEFAULT_CLOUD_MAX_TOKENS = 8192
API_KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
LOCAL_THINK_OPTIONS = [LOCAL_THINK_OFF, LOCAL_THINK_ON]
SKILL_PATH = Path(__file__).parent / "official_skills" / "qwen-image-2.1" / "SKILL.md"
SKILL_SHA256 = "a77c9a06c59b120741141d9514b95682bb8761d02bec49ca61def7b2b3d9fb99"


class QwenImage21PromptEnhancerError(PromptEnhancerError):
    pass


def _load_skill() -> str:
    try:
        text = SKILL_PATH.read_text(encoding="utf-8")
    except OSError as error:
        raise QwenImage21PromptEnhancerError("Bundled Qwen Image 2.1 Skill is missing or unreadable. Update from GitHub.") from error
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if digest != SKILL_SHA256:
        raise QwenImage21PromptEnhancerError("Bundled Qwen Image 2.1 Skill hash mismatch. Update the complete node package.")
    return text


def _clean_secret(value: Any, label: str) -> str:
    text = str(value or "").strip()
    # The dedicated api_key input is intentionally allowed to contain the
    # provider credential.  Other free-text fields must never carry a key;
    # this mirrors the existing H3/Seedance input sanitisation contract.
    if label == "api_key":
        return "" if text in LEGACY_UI_VALUES else text
    if API_KEY_PATTERN.search(text):
        raise QwenImage21PromptEnhancerError(f"Remove API-key-like text from {label} before running this node.")
    return text


def _image_plan(reference_images: dict[str, Any] | None) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for value in _ordered_values(reference_images):
        for index in range(_image_count(value)):
            assets.append({
                "kind": "image",
                "label": f"<Image {len(assets) + 1}>",
                "value": _image_at(value, index),
            })
    if len(assets) > MAX_IMAGES:
        raise QwenImage21PromptEnhancerError(f"Qwen Image 2.1 accepts at most {MAX_IMAGES} reference images; received {len(assets)}.")
    return assets


_REFERENCE_IMAGE_KEY = re.compile(r"(?:^|\.)reference_image_(\d+)$")


def _coerce_reference_images(
    reference_images: Mapping[str, Any] | list[Any] | tuple[Any, ...] | None,
    extra_inputs: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Normalize V3 autogrow images across old and new ComfyUI runtimes.

    Current ComfyUI rebuilds an ``io.Autogrow`` group as a nested mapping
    before calling the node.  Older V3 builds and workflows saved during the
    autogrow migration can still deliver the live sockets as flat keyword
    arguments (``reference_image_0`` or
    ``reference_images.reference_image_0``).  Accept both forms so a visible
    connected image is never discarded merely because the runtime did not
    rebuild the group.
    """
    collected: dict[str, Any] = {}
    if isinstance(reference_images, Mapping):
        collected.update({str(key): value for key, value in reference_images.items() if value is not None})
    elif isinstance(reference_images, (list, tuple)):
        collected.update({f"reference_image_{index}": value for index, value in enumerate(reference_images) if value is not None})

    for key, value in (extra_inputs or {}).items():
        match = _REFERENCE_IMAGE_KEY.search(str(key))
        if match and value is not None:
            collected.setdefault(f"reference_image_{int(match.group(1))}", value)
    return collected or None


def _has_reference_slots(
    reference_images: Mapping[str, Any] | list[Any] | tuple[Any, ...] | None,
    extra_inputs: Mapping[str, Any] | None = None,
) -> bool:
    """Return whether the graph declares reference-image sockets.

    During ComfyUI's pre-execution validation, linked upstream IMAGE values
    are intentionally represented as ``None`` because their producer has not
    run yet.  The autogrow group is still present (with keys such as
    ``reference_image_0``), so validation must distinguish those pending
    links from a genuinely empty edit request.
    """
    if isinstance(reference_images, Mapping):
        if any(_REFERENCE_IMAGE_KEY.search(str(key)) for key in reference_images):
            return True
    elif isinstance(reference_images, (list, tuple)) and reference_images:
        return True
    return any(_REFERENCE_IMAGE_KEY.search(str(key)) for key in (extra_inputs or {}))


def _validate_mode(prompt: str, input_mode: str, media_plan: list[dict[str, Any]], ratio: str, max_chars: int, transparent: bool) -> None:
    if not str(prompt or "").strip():
        raise QwenImage21PromptEnhancerError("prompt is required. Enter the image brief or editing instruction.")
    if input_mode not in INPUT_MODES:
        raise QwenImage21PromptEnhancerError(f"Unsupported input_mode: {input_mode}")
    if input_mode == INPUT_MODE_TEXT and media_plan:
        raise QwenImage21PromptEnhancerError("Text-to-image mode must not have reference images; choose Image edit.")
    if input_mode == INPUT_MODE_EDIT and not media_plan:
        raise QwenImage21PromptEnhancerError("Image edit mode requires 1–10 reference images.")
    if ratio not in RATIO_OPTIONS:
        raise QwenImage21PromptEnhancerError(f"Unsupported wh_ratio: {ratio}")
    if not isinstance(max_chars, int) or max_chars < 0 or max_chars > MAX_PROMPT_CHARS:
        raise QwenImage21PromptEnhancerError(f"max_output_chars must be 0 or an integer from 1 to {MAX_PROMPT_CHARS}.")
    del transparent


def _build_messages(prompt: str, input_mode: str, media_plan: list[dict[str, Any]], ratio: str, max_chars: int, transparent: bool, media_parts: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    skill = _load_skill()
    ratio_rule = (
        "The user selected auto. Do not impose a user ratio; let the Skill choose its 3:2 or 2:3 default when appropriate."
        if ratio == "auto"
        else f"The user selected wh_ratio={ratio}. Preserve this value exactly in the JSON field and never write it in rewritten_prompt."
    )
    alpha_rule = (
        "Transparency is required. Describe the finished image as an RGBA image with an alpha channel and a transparent background."
        if transparent
        else "Transparency is not requested. Do not invent an alpha channel or a transparent background."
    )
    length_rule = (
        "The user set max_output_chars=0. Let the model choose a complete Skill-compliant length."
        if max_chars == 0
        else f"Keep rewritten_prompt at or below {max_chars} characters while preserving fixed facts; do not cut it mid-sentence."
    )
    media_rule = (
        f"This is {input_mode}. There are {len(media_plan)} ordered reference images. Inspect every image and keep image labels in order."
        if media_plan
        else "This is text-to-image with no reference images."
    )
    user_text = "\n".join((
        "Follow the bundled Skill as the governing contract.",
        media_rule,
        ratio_rule,
        alpha_rule,
        length_rule,
        "The user's brief follows. Fixed visible text and named objects are authoritative:",
        str(prompt).strip(),
        "Return only one JSON object on one line. Do not add Markdown, analysis, or a preamble.",
    ))
    user_content: str | list[dict[str, Any]] = user_text
    if media_parts:
        user_content = [{"type": "text", "text": user_text}, *media_parts]
    return [
        {
            "role": "system",
            "content": (
                "You are the Qwen Image 2.1 Prompt Enhancer for ComfyUI. The attached Skill is a frozen source contract. "
                "Never echo job instructions as image content. Preserve user-fixed text character-for-character.\n\n" + skill
            ),
        },
        {"role": "user", "content": user_content},
    ]


def _extract_json(text: str) -> dict[str, Any] | None:
    value = str(text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*```$", "", value)
    start, end = value.find("{"), value.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(value[start:end + 1])
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _cloud_request_options(options: Any) -> Any:
    """Keep enough completion budget for the Skill's hidden reasoning.

    The shared provider config remains authoritative when it specifies either
    ``max_tokens`` or ``max_completion_tokens``.  Otherwise this node supplies
    the 8192-token budget that was validated against the bundled Skill; this is
    especially important for Qwen models whose thinking tokens count toward
    the response limit.
    """
    if options is None:
        return {"extra_parameters": {"max_tokens": DEFAULT_CLOUD_MAX_TOKENS}}
    if not isinstance(options, dict):
        return options
    result = dict(options)
    extra = result.get("extra_parameters")
    if extra in (None, ""):
        extra = {}
    elif not isinstance(extra, dict):
        return options
    else:
        extra = dict(extra)
    if "max_tokens" not in extra and "max_completion_tokens" not in extra:
        extra["max_tokens"] = DEFAULT_CLOUD_MAX_TOKENS
    result["extra_parameters"] = extra
    return result


def _validate_output(payload: dict[str, Any], *, requested_ratio: str, transparent: bool, max_chars: int) -> tuple[str, str, dict[str, Any]]:
    if set(payload) != {"rewritten_prompt", "wh_ratio"}:
        raise QwenImage21PromptEnhancerError("Qwen Image response must contain exactly rewritten_prompt and wh_ratio.")
    description = payload.get("rewritten_prompt")
    ratio = payload.get("wh_ratio")
    if not isinstance(description, str) or not description.strip():
        raise QwenImage21PromptEnhancerError("Qwen Image response is missing a non-empty rewritten_prompt.")
    if not isinstance(ratio, str) or ratio not in OUTPUT_RATIOS:
        raise QwenImage21PromptEnhancerError("Qwen Image response contains an invalid wh_ratio.")
    description = description.strip()
    if requested_ratio != "auto" and ratio != requested_ratio:
        raise QwenImage21PromptEnhancerError(f"Qwen Image returned wh_ratio={ratio}, expected {requested_ratio}.")
    # The Skill keeps ratio metadata outside the prose, but exact visible text
    # is required to remain inside straight quotes.  Ignore quoted literals so
    # a real sign such as "1:1" is not destroyed by the ratio guard.
    unquoted_description = re.sub(r'"(?:\\.|[^"\\])*"', "", description)
    if requested_ratio != "auto" and requested_ratio in unquoted_description:
        raise QwenImage21PromptEnhancerError("Qwen Image prompt must keep the selected ratio in wh_ratio, not in rewritten_prompt.")
    if transparent:
        has_rgba = bool(re.search(r"\bRGBA\b", description, flags=re.IGNORECASE))
        has_alpha = bool(re.search(r"\balpha\s+channel\b", description, flags=re.IGNORECASE))
        has_transparent_background = bool(
            re.search(
                r"\btransparent\s+background\b|\bbackground\s+(?:is|remains|must\s+be)\s+transparent\b",
                description,
                flags=re.IGNORECASE,
            )
        )
        if not (has_rgba and has_alpha and has_transparent_background):
            raise QwenImage21PromptEnhancerError(
                "Transparent output requires explicit RGBA, alpha channel, and transparent background semantics."
            )
    over_limit = bool(max_chars and len(description) > max_chars)
    return description, ratio, {"over_limit": over_limit, "prompt_chars": len(description)}


def _accept_complete_stream(
    text: str,
    *,
    requested_ratio: str,
    transparent: bool,
    max_chars: int,
) -> bool:
    """Accept a disconnected cloud stream only when its Qwen JSON is complete.

    Seedance chat is streamed through a proxy.  A proxy can close the socket
    after the model has emitted the whole JSON object but before ``[DONE]``.
    This predicate is deliberately strict: a balanced, schema-valid object is
    safe to use; any partial/invalid response remains ambiguous and is never
    retried automatically.
    """
    try:
        payload = _extract_json(text)
        if payload is None:
            return False
        _validate_output(
            payload,
            requested_ratio=requested_ratio,
            transparent=transparent,
            max_chars=max_chars,
        )
        return True
    except (QwenImage21PromptEnhancerError, TypeError, ValueError):
        return False


def _correction_messages(messages: list[dict[str, Any]], draft: str, reason: str) -> list[dict[str, Any]]:
    return [
        *messages,
        {"role": "assistant", "content": draft},
        {"role": "user", "content": (
            "Repair the previous answer once. Return only one valid one-line JSON object with exactly "
            "rewritten_prompt and wh_ratio. Preserve every fixed user fact and visible text. " + reason
        )},
    ]


def _resolve_image_model(api_mode: str, ai_workshop_model: str, custom_model: str) -> str:
    if is_local_qwen_api_mode(api_mode):
        return "local-gguf"
    if api_mode == SEEDANCE_API_MODE:
        return QWEN_IMAGE_MODEL_ID
    if api_mode == AI_WORKSHOP_API_MODE:
        selection = str(ai_workshop_model or AI_WORKSHOP_DEFAULT_MODEL).strip()
        if selection == "Custom（自定义）":
            value = str(custom_model or "").strip()
            if not value or any(ch.isspace() for ch in value):
                raise QwenImage21PromptEnhancerError("Custom AI Workshop model is empty or contains whitespace.")
            return value
        if selection != AI_WORKSHOP_DEFAULT_MODEL:
            raise QwenImage21PromptEnhancerError(f"Unsupported AI Workshop model: {selection}")
        return selection
    if api_mode == OPENAI_API_MODE:
        value = str(custom_model or "").strip()
        if not value or any(ch.isspace() for ch in value):
            raise QwenImage21PromptEnhancerError("OpenAI-compatible mode requires a valid custom_model.")
        return value
    return "local-gguf"


def _report(*, api_mode: str, model: str, input_mode: str, image_count: int, ratio: str, transparent: bool, structured: bool, corrections: int, over_limit: bool = False, error: str = "") -> str:
    return json.dumps({
        "schema_version": "t8-qwen-image-21-report/v1",
        "provider_mode": api_mode,
        "model": model,
        "input_mode": input_mode,
        "image_count": image_count,
        "requested_ratio": ratio,
        "transparent_alpha": bool(transparent),
        "structured_response": bool(structured),
        "correction_calls": corrections,
        "over_limit": bool(over_limit),
        "error": str(error or "")[:500],
    }, ensure_ascii=False)


class QwenImage21PromptEnhancer(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id=NODE_ID,
            display_name=DISPLAY_NAME,
            category="T8/Qwen Image",
            description=(
                "Turns text and up to ten ordered reference images into the frozen Qwen Image prompt JSON contract. "
                "Cloud and local GGUF channels share the existing T8 provider configuration."
            ),
            inputs=[
                io.String.Input("prompt", display_name="图像描述 / Prompt（必填）", multiline=True, dynamic_prompts=True, default=""),
                io.Combo.Input("input_mode", display_name="输入模式 / Input mode", options=INPUT_MODES, default=INPUT_MODE_TEXT),
                io.Autogrow.Input(
                    "reference_images",
                    optional=True,
                    template=io.Autogrow.TemplatePrefix(
                        input=io.Image.Input("reference_image", tooltip="Ordered reference image for image editing."),
                        prefix="reference_image_",
                        min=0,
                        max=MAX_IMAGES,
                    ),
                ),
                io.Int.Input(
                    "max_output_chars",
                    display_name="最大提示词字数（0=AI自动）",
                    default=0,
                    min=0,
                    max=MAX_PROMPT_CHARS,
                    step=100,
                    tooltip="0 让模型自行决定完整长度；非零会执行一次有界长度纠正，超出时保留完整结果并在报告标记。",
                ),
                io.Combo.Input("wh_ratio", display_name="尺寸比例 / Aspect ratio", options=RATIO_OPTIONS, default="auto"),
                io.Boolean.Input("transparent_alpha", display_name="透明通道 / Transparent RGBA", default=False),
                io.String.Input("api_key", display_name="API Key", optional=True, default="", force_input=True),
                io.Combo.Input("api_mode", display_name="API 模式", options=API_MODES, default=SEEDANCE_API_MODE),
                io.Combo.Input("ai_workshop_model", display_name="AI 工坊模型", options=AI_WORKSHOP_MODEL_OPTIONS, default=AI_WORKSHOP_DEFAULT_MODEL, advanced=True),
                io.String.Input("custom_model", display_name="自定义模型 ID", optional=True, default="", socketless=True, advanced=True),
                io.String.Input("openai_base_url", display_name="OpenAI兼容 Base URL", optional=True, default="", socketless=True, advanced=True),
                io.Int.Input("seed", display_name="随机种子", optional=True, default=0, min=0, max=0xffffffffffffffff, control_after_generate=True, advanced=True),
                io.Combo.Input("local_model", display_name="本地 GGUF 主模型", options=list_gguf_models(), default=DEFAULT_MODEL_FILENAME, optional=True, advanced=True),
                io.Combo.Input("local_mmproj", display_name="本地视觉投影器", options=list_mmproj_models(), default=AUTO_MMPROJ, optional=True, advanced=True),
                io.Int.Input("local_context_size", display_name="本地上下文 Token", default=DEFAULT_CONTEXT_SIZE, min=8192, max=65536, step=4096, optional=True, advanced=True),
                io.Int.Input("local_max_tokens", display_name="本地单次生成 Token（含思考）", default=DEFAULT_MAX_TOKENS, min=256, max=MAX_OUTPUT_TOKENS, step=1024, optional=True, advanced=True),
                io.Combo.Input("local_think_mode", display_name="本地思考模式", options=LOCAL_THINK_OPTIONS, default=LOCAL_THINK_OFF, optional=True, advanced=True),
                io.Combo.Input("local_reasoning_effort", display_name="本地推理强度", options=LOCAL_REASONING_OPTIONS, default="medium", optional=True, advanced=True),
                io.Float.Input("local_video_sample_fps", display_name="本地视觉采样率", default=DEFAULT_VIDEO_SAMPLE_FPS, min=0.25, max=8.0, step=0.25, optional=True, advanced=True),
                io.Combo.Input("local_unload_policy", display_name="本地模型卸载策略", options=LOCAL_UNLOAD_POLICIES, default=LOCAL_UNLOAD_AFTER_RUN, optional=True, advanced=True),
                io.Combo.Input("local_comfy_memory_policy", display_name="本地显存策略", options=LOCAL_COMFY_MEMORY_POLICIES, default=LOCAL_COMFY_MEMORY_POLICIES[0], optional=True, advanced=True),
                io.String.Input("recovery_slot", display_name="恢复槽（内部）", optional=True, default="", socketless=True, advanced=True),
                io.String.Input("recovery_action", display_name="恢复动作（内部）", optional=True, default=RECOVERY_ACTION_NORMAL, socketless=True, advanced=True),
                T8ProviderConfigIO.Input("provider_config", display_name="共享 LLM 渠道配置（可选）", optional=True),
            ],
            outputs=[
                io.String.Output(display_name="rewritten_prompt"),
                io.String.Output(display_name="wh_ratio"),
                io.String.Output(display_name="qwen_image_request_json"),
                io.String.Output(display_name="enhancement_report_json"),
            ],
        )

    @classmethod
    def validate_inputs(cls, prompt="", input_mode=INPUT_MODE_TEXT, reference_images=None, wh_ratio="auto", max_output_chars=0, transparent_alpha=False, **kwargs):
        pending_reference_slots = _has_reference_slots(reference_images, kwargs)
        reference_images = _coerce_reference_images(reference_images, kwargs)
        del kwargs
        media_plan = _image_plan(reference_images)
        if pending_reference_slots and not media_plan:
            # Linked IMAGE sockets are unresolved while ComfyUI validates the
            # graph.  Keep mode/ratio/length checks, but defer the 1–10 image
            # count/type check until execute() receives real tensors.
            media_plan = [{"kind": "image", "value": None}]
        _validate_mode(str(prompt or ""), input_mode, media_plan, str(wh_ratio or "auto"), int(max_output_chars or 0), bool(transparent_alpha))
        return True

    @classmethod
    def execute(
        cls,
        prompt="",
        input_mode=INPUT_MODE_TEXT,
        reference_images=None,
        max_output_chars=0,
        wh_ratio="auto",
        transparent_alpha=False,
        api_key="",
        api_mode=SEEDANCE_API_MODE,
        ai_workshop_model=AI_WORKSHOP_DEFAULT_MODEL,
        custom_model="",
        openai_base_url="",
        seed=0,
        local_model=DEFAULT_MODEL_FILENAME,
        local_mmproj=AUTO_MMPROJ,
        local_context_size=DEFAULT_CONTEXT_SIZE,
        local_max_tokens=DEFAULT_MAX_TOKENS,
        local_think_mode=LOCAL_THINK_OFF,
        local_reasoning_effort="medium",
        local_video_sample_fps=DEFAULT_VIDEO_SAMPLE_FPS,
        local_unload_policy=LOCAL_UNLOAD_AFTER_RUN,
        local_comfy_memory_policy=LOCAL_COMFY_MEMORY_POLICIES[0],
        recovery_slot="",
        recovery_action=RECOVERY_ACTION_NORMAL,
        provider_config=None,
        **kwargs,
    ) -> io.NodeOutput:
        if str(recovery_action or RECOVERY_ACTION_NORMAL) == RECOVERY_ACTION_RESTORE:
            try:
                cached = recover_outputs(NODE_ID, recovery_slot, 4)
                return io.NodeOutput(*cached)
            except CompletionRecoveryError as error:
                raise QwenImage21PromptEnhancerError(str(error)) from error
        reference_images = _coerce_reference_images(reference_images, kwargs)
        del kwargs
        api_mode = str(api_mode or SEEDANCE_API_MODE)
        input_mode = str(input_mode or INPUT_MODE_TEXT)
        ratio = str(wh_ratio or "auto")
        max_chars = int(max_output_chars or 0)
        media_plan = _image_plan(reference_images)
        _validate_mode(str(prompt or ""), input_mode, media_plan, ratio, max_chars, bool(transparent_alpha))
        api_key = _clean_secret(api_key, "api_key")
        _clean_secret(prompt, "prompt")
        custom_model = _clean_secret(custom_model, "custom_model")
        openai_base_url = _clean_secret(openai_base_url, "openai_base_url")
        current = {
            "api_mode": api_mode,
            "openai_base_url": openai_base_url,
            "ai_workshop_model": ai_workshop_model,
            "custom_model": custom_model,
            "local_model": local_model,
            "local_mmproj": local_mmproj,
            "local_context_size": local_context_size,
            "local_max_tokens": local_max_tokens,
            "local_think_mode": local_think_mode,
            "local_reasoning_effort": local_reasoning_effort,
            "local_video_sample_fps": local_video_sample_fps,
            "local_unload_policy": local_unload_policy,
            "local_comfy_memory_policy": local_comfy_memory_policy,
            "api_key": api_key,
        }
        if provider_config is not None:
            try:
                current = merge_provider_config(
                    current,
                    provider_config,
                    api_mode_map={
                        PROVIDER_SEEDANCE: SEEDANCE_API_MODE,
                        PROVIDER_WORKSHOP: AI_WORKSHOP_API_MODE,
                        PROVIDER_OPENAI: OPENAI_API_MODE,
                        PROVIDER_LOCAL: LOCAL_QWEN_API_MODE,
                    },
                )
            except Exception as error:
                raise QwenImage21PromptEnhancerError(str(error)) from error
        # A connected provider config may carry editable text fields.  Apply
        # the same secret guard after merging so a malformed config cannot
        # move a key into the model/base-url fields; the dedicated api_key
        # remains the only allowed credential carrier.
        current["custom_model"] = _clean_secret(current.get("custom_model"), "custom_model")
        current["openai_base_url"] = _clean_secret(current.get("openai_base_url"), "openai_base_url")
        current["api_key"] = str(current.get("api_key") or "").strip()
        current["provider_request_options"] = _cloud_request_options(current.get("provider_request_options"))
        api_mode = str(current["api_mode"] or SEEDANCE_API_MODE)
        model_id = _resolve_image_model(api_mode, current["ai_workshop_model"], current["custom_model"])
        begin_recovery_record(NODE_ID, recovery_slot, api_mode)
        corrections = 0
        structured = False
        chosen_ratio = ""
        over_limit = False
        report_error = ""
        raw_response = ""
        try:
            if is_local_qwen_api_mode(api_mode):
                settings = local_qwen_settings(
                    local_model=current["local_model"], local_mmproj=current["local_mmproj"],
                    local_context_size=current["local_context_size"], local_max_tokens=current["local_max_tokens"],
                    local_think_mode=current["local_think_mode"], local_reasoning_effort=current["local_reasoning_effort"],
                    local_video_sample_fps=current["local_video_sample_fps"], local_unload_policy=current["local_unload_policy"],
                    local_comfy_memory_policy=current["local_comfy_memory_policy"],
                )
                text_messages = _build_messages(str(prompt), input_mode, media_plan, ratio, max_chars, bool(transparent_alpha))
                text_messages = apply_local_language_lock(text_messages, "English")
                visual_budget = local_visual_part_budget(text_messages, settings, required_visual_parts=len(media_plan))
                media_parts, _ = build_local_multimodal_parts(media_plan, settings, max_visual_parts=visual_budget)
                messages = apply_local_language_lock(_build_messages(str(prompt), input_mode, media_plan, ratio, max_chars, bool(transparent_alpha), media_parts), "English")
                with LocalQwenProvider(settings, vision=bool(media_plan)) as provider:
                    raw_response = provider.complete(messages, temperature=0.2, seed=int(seed), require_complete=True)
                    payload = _extract_json(raw_response)
                    try:
                        if payload is None:
                            raise QwenImage21PromptEnhancerError("response is not valid JSON")
                        rewritten, chosen_ratio, details = _validate_output(payload, requested_ratio=ratio, transparent=bool(transparent_alpha), max_chars=max_chars)
                        if details.get("over_limit"):
                            corrections = 1
                            corrected = provider.complete(
                                _correction_messages(messages, raw_response, f"Keep rewritten_prompt at or below {max_chars} characters."),
                                temperature=0.1, seed=int(seed), require_complete=True,
                            )
                            corrected_payload = _extract_json(corrected)
                            if corrected_payload is not None:
                                rewritten, chosen_ratio, details = _validate_output(
                                    corrected_payload, requested_ratio=ratio, transparent=bool(transparent_alpha), max_chars=max_chars,
                                )
                                raw_response = corrected
                    except QwenImage21PromptEnhancerError as first_error:
                        corrections = 1
                        corrected = provider.complete(_correction_messages(messages, raw_response, str(first_error)), temperature=0.1, seed=int(seed), require_complete=True)
                        payload = _extract_json(corrected)
                        if payload is None:
                            raise first_error
                        rewritten, chosen_ratio, details = _validate_output(payload, requested_ratio=ratio, transparent=bool(transparent_alpha), max_chars=max_chars)
                        raw_response = corrected
            else:
                api_key, chat_url, upload_url, provider_name = _provider_config(api_mode, current["api_key"], current["openai_base_url"])
                session = requests.Session()
                try:
                    if api_mode == AI_WORKSHOP_API_MODE:
                        media_parts = _inline_media_plan(media_plan)
                    elif api_mode == OPENAI_API_MODE:
                        media_parts = _openai_media_plan(media_plan, "", video_sample_fps=float(current["local_video_sample_fps"]))
                    else:
                        media_parts = _upload_media_plan(session, api_key, media_plan, upload_url, provider_name)
                    messages = _build_messages(str(prompt), input_mode, media_plan, ratio, max_chars, bool(transparent_alpha), media_parts)
                    raw_response = _request_completion(
                        session, api_key, messages, "balanced", chat_url, provider_name, model_id,
                        provider_request_options=current.get("provider_request_options"),
                        recovery_component=NODE_ID,
                        recovery_slot=recovery_slot,
                        stream_acceptor=lambda text: _accept_complete_stream(
                            text, requested_ratio=ratio, transparent=bool(transparent_alpha), max_chars=max_chars,
                        ),
                    )
                    payload = _extract_json(raw_response)
                    try:
                        if payload is None:
                            raise QwenImage21PromptEnhancerError("response is not valid JSON")
                        rewritten, chosen_ratio, details = _validate_output(payload, requested_ratio=ratio, transparent=bool(transparent_alpha), max_chars=max_chars)
                        if details.get("over_limit"):
                            corrections = 1
                            corrected = _request_completion(
                                session, api_key, _correction_messages(messages, raw_response, f"Keep rewritten_prompt at or below {max_chars} characters."),
                                "balanced", chat_url, provider_name, model_id,
                                provider_request_options=current.get("provider_request_options"), temperature_override=0.1,
                                recovery_component=NODE_ID,
                                recovery_slot=recovery_slot,
                                stream_acceptor=lambda text: _accept_complete_stream(
                                    text, requested_ratio=ratio, transparent=bool(transparent_alpha), max_chars=max_chars,
                                ),
                            )
                            corrected_payload = _extract_json(corrected)
                            if corrected_payload is not None:
                                rewritten, chosen_ratio, details = _validate_output(
                                    corrected_payload, requested_ratio=ratio, transparent=bool(transparent_alpha), max_chars=max_chars,
                                )
                                raw_response = corrected
                    except QwenImage21PromptEnhancerError as first_error:
                        corrections = 1
                        corrected = _request_completion(
                            session, api_key, _correction_messages(messages, raw_response, str(first_error)),
                            "balanced", chat_url, provider_name, model_id,
                            provider_request_options=current.get("provider_request_options"), temperature_override=0.1,
                            recovery_component=NODE_ID,
                            recovery_slot=recovery_slot,
                            stream_acceptor=lambda text: _accept_complete_stream(
                                text, requested_ratio=ratio, transparent=bool(transparent_alpha), max_chars=max_chars,
                            ),
                        )
                        payload = _extract_json(corrected)
                        if payload is None:
                            raise first_error
                        rewritten, chosen_ratio, details = _validate_output(payload, requested_ratio=ratio, transparent=bool(transparent_alpha), max_chars=max_chars)
                        raw_response = corrected
                finally:
                    session.close()
            structured = True
            over_limit = bool(details.get("over_limit"))
        except (QwenImage21PromptEnhancerError, LocalQwenProviderError, PromptEnhancerError) as error:
            report_error = str(error)
            rewritten = str(raw_response or "").strip()
            if not rewritten:
                mark_recovery_failed(NODE_ID, recovery_slot, error)
                raise QwenImage21PromptEnhancerError(report_error) from error
        request_json = json.dumps({
            "schema_version": "t8-qwen-image-21-request/v1",
            "model": model_id,
            "input_mode": input_mode,
            "images": [asset["label"] for asset in media_plan],
            "prompt": str(prompt),
            "wh_ratio": chosen_ratio or (ratio if ratio != "auto" else ""),
            "transparent_alpha": bool(transparent_alpha),
            "max_output_chars": max_chars,
        }, ensure_ascii=False)
        report = _report(
            api_mode=api_mode, model=model_id, input_mode=input_mode, image_count=len(media_plan), ratio=ratio,
            transparent=bool(transparent_alpha), structured=structured, corrections=corrections,
            over_limit=over_limit, error=report_error,
        )
        complete_recovery_record(NODE_ID, recovery_slot, (rewritten, chosen_ratio, request_json, report))
        return io.NodeOutput(rewritten, chosen_ratio, request_json, report)


__all__ = ["QwenImage21PromptEnhancer", "QwenImage21PromptEnhancerError", "NODE_ID", "QWEN_IMAGE_MODEL_ID"]
