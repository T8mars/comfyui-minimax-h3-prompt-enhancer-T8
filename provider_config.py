from __future__ import annotations

from typing import Any, Mapping

from comfy_api.latest import io

try:
    from .credential_store import CredentialStoreError, get_credential
    from .local_qwen_provider import (
        DEFAULT_CONTEXT_SIZE,
        DEFAULT_MAX_TOKENS,
        DEFAULT_VIDEO_SAMPLE_FPS,
        MAX_OUTPUT_TOKENS,
    )
    from .local_qwen_runtime import (
        AUTO_MMPROJ,
        DEFAULT_MMPROJ_FILENAME,
        DEFAULT_MODEL_FILENAME,
        LOCAL_COMFY_MEMORY_POLICIES,
        LOCAL_REASONING_OPTIONS,
        LOCAL_THINK_OFF,
        LOCAL_THINK_OPTIONS,
        LOCAL_UNLOAD_AFTER_RUN,
        LOCAL_UNLOAD_POLICIES,
        list_gguf_models,
        list_mmproj_models,
    )
    from .provider_capabilities import (
        ProviderCapabilityError,
        TEMPERATURE_AUTO,
        TEMPERATURE_OMIT,
        TEMPERATURE_SEND,
        normalize_extra_parameters,
    )
except ImportError:
    from credential_store import CredentialStoreError, get_credential
    from local_qwen_provider import (
        DEFAULT_CONTEXT_SIZE,
        DEFAULT_MAX_TOKENS,
        DEFAULT_VIDEO_SAMPLE_FPS,
        MAX_OUTPUT_TOKENS,
    )
    from local_qwen_runtime import (
        AUTO_MMPROJ,
        DEFAULT_MMPROJ_FILENAME,
        DEFAULT_MODEL_FILENAME,
        LOCAL_COMFY_MEMORY_POLICIES,
        LOCAL_REASONING_OPTIONS,
        LOCAL_THINK_OFF,
        LOCAL_THINK_OPTIONS,
        LOCAL_UNLOAD_AFTER_RUN,
        LOCAL_UNLOAD_POLICIES,
        list_gguf_models,
        list_mmproj_models,
    )
    from provider_capabilities import (
        ProviderCapabilityError,
        TEMPERATURE_AUTO,
        TEMPERATURE_OMIT,
        TEMPERATURE_SEND,
        normalize_extra_parameters,
    )


PROVIDER_CONFIG_SCHEMA = "t8-llm-provider-config/v1"
PROVIDER_SEEDANCE = "Seedance NZ"
PROVIDER_WORKSHOP = "T8 AI Workshop"
PROVIDER_OPENAI = "OpenAI Compatible"
PROVIDER_LOCAL = "Local Qwen"
PROVIDER_OPTIONS = [PROVIDER_SEEDANCE, PROVIDER_WORKSHOP, PROVIDER_OPENAI, PROVIDER_LOCAL]
TEMPERATURE_LABELS = {
    "AUTO（兼容策略）": TEMPERATURE_AUTO,
    "发送 temperature": TEMPERATURE_SEND,
    "省略 temperature": TEMPERATURE_OMIT,
}
T8ProviderConfigIO = io.Custom("T8_LLM_PROVIDER_CONFIG")


class ProviderConfigError(RuntimeError):
    pass


def _clean_text(value: Any, *, limit: int = 4096) -> str:
    return str(value or "").strip()[:limit]


def _clean_local_identifier(value: Any, *, label: str) -> str:
    text = str(value or "").strip()
    if len(text) > 4096:
        raise ProviderConfigError(f"{label} exceeds the 4096-character safety limit.")
    return text


def build_provider_config(**values: Any) -> dict[str, Any]:
    provider = _clean_text(values.get("provider"), limit=64)
    if provider not in PROVIDER_OPTIONS:
        raise ProviderConfigError(f"Unsupported shared provider: {provider}")
    policy_label = _clean_text(values.get("temperature_policy") or next(iter(TEMPERATURE_LABELS)), limit=64)
    if policy_label not in TEMPERATURE_LABELS:
        raise ProviderConfigError(f"Unsupported temperature policy: {policy_label}")
    try:
        extra = normalize_extra_parameters(values.get("extra_parameters_json"))
    except ProviderCapabilityError as exc:
        raise ProviderConfigError(str(exc)) from exc
    alias = _clean_text(values.get("credential_alias"), limit=64)
    return {
        "schema_version": PROVIDER_CONFIG_SCHEMA,
        "provider": provider,
        "openai_base_url": _clean_text(values.get("openai_base_url")),
        "ai_workshop_model": _clean_text(values.get("ai_workshop_model"), limit=256) or "gemini-3.5-flash",
        "custom_model": _clean_text(values.get("custom_model"), limit=512),
        "credential_alias": alias,
        "provider_request_options": {
            "temperature_policy": TEMPERATURE_LABELS[policy_label],
            "extra_parameters": extra,
        },
        "local_model": _clean_local_identifier(values.get("local_model"), label="local_model")
        or DEFAULT_MODEL_FILENAME,
        "local_mmproj": _clean_local_identifier(values.get("local_mmproj"), label="local_mmproj")
        or DEFAULT_MMPROJ_FILENAME,
        "local_context_size": int(values.get("local_context_size") or DEFAULT_CONTEXT_SIZE),
        "local_max_tokens": int(values.get("local_max_tokens") or DEFAULT_MAX_TOKENS),
        "local_think_mode": _clean_text(values.get("local_think_mode"), limit=64) or LOCAL_THINK_OFF,
        "local_reasoning_effort": _clean_text(values.get("local_reasoning_effort"), limit=32) or "medium",
        "local_video_sample_fps": float(values.get("local_video_sample_fps") or DEFAULT_VIDEO_SAMPLE_FPS),
        "local_unload_policy": _clean_text(values.get("local_unload_policy"), limit=64) or LOCAL_UNLOAD_AFTER_RUN,
        "local_comfy_memory_policy": _clean_text(values.get("local_comfy_memory_policy"), limit=64)
        or LOCAL_COMFY_MEMORY_POLICIES[0],
    }


def merge_provider_config(
    current: Mapping[str, Any],
    provider_config: Any,
    *,
    api_mode_map: Mapping[str, str],
) -> dict[str, Any]:
    result = dict(current)
    if provider_config is None:
        result["provider_request_options"] = None
        return result
    if not isinstance(provider_config, Mapping) or provider_config.get("schema_version") != PROVIDER_CONFIG_SCHEMA:
        raise ProviderConfigError("Connected provider_config has an unsupported schema.")
    provider = str(provider_config.get("provider", ""))
    if provider not in api_mode_map:
        raise ProviderConfigError(f"Connected provider is unsupported by this node: {provider}")
    result["api_mode"] = api_mode_map[provider]
    for key in (
        "openai_base_url", "ai_workshop_model", "custom_model", "local_model", "local_mmproj",
        "local_context_size", "local_max_tokens", "local_think_mode", "local_reasoning_effort",
        "local_video_sample_fps", "local_unload_policy", "local_comfy_memory_policy",
    ):
        if key in provider_config:
            result[key] = provider_config[key]
    result["provider_request_options"] = provider_config.get("provider_request_options")
    # Existing connected/saved api_key remains authoritative.  The alias is
    # only resolved at execution time and is never copied into a workflow.
    if not str(result.get("api_key") or "").strip():
        alias = str(provider_config.get("credential_alias") or "").strip()
        if alias:
            try:
                result["api_key"] = get_credential(alias)
            except CredentialStoreError as exc:
                raise ProviderConfigError(str(exc)) from exc
    return result


class T8LLMProviderConfig(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8LLMProviderConfig",
            display_name="T8 LLM Provider Config",
            category="T8/Utilities",
            description=(
                "Optional shared cloud/local provider configuration for the three T8 enhancer nodes. "
                "Disconnecting it restores every original node widget immediately."
            ),
            inputs=[
                io.Combo.Input("provider", display_name="共享渠道", options=PROVIDER_OPTIONS, default=PROVIDER_SEEDANCE),
                io.String.Input("credential_alias", display_name="本地凭据别名（可选）", optional=True, default="", socketless=True),
                io.String.Input("openai_base_url", display_name="OpenAI Base URL", optional=True, default="", socketless=True),
                io.String.Input("custom_model", display_name="自定义模型 ID", optional=True, default="", socketless=True),
                io.String.Input("ai_workshop_model", display_name="AI 工坊模型", optional=True, default="gemini-3.5-flash", socketless=True),
                io.Combo.Input(
                    "temperature_policy",
                    display_name="temperature 策略",
                    options=list(TEMPERATURE_LABELS),
                    default="AUTO（兼容策略）",
                ),
                io.String.Input(
                    "extra_parameters_json",
                    display_name="附加请求参数 JSON（allowlist）",
                    optional=True,
                    multiline=True,
                    default="",
                    advanced=True,
                    socketless=True,
                ),
                io.Combo.Input("local_model", display_name="本地 GGUF 主模型", options=list_gguf_models(), default=DEFAULT_MODEL_FILENAME, advanced=True),
                io.Combo.Input("local_mmproj", display_name="本地视觉投影器", options=list_mmproj_models(), default=AUTO_MMPROJ, advanced=True),
                io.Int.Input(
                    "local_context_size",
                    display_name="本地上下文 Token",
                    default=DEFAULT_CONTEXT_SIZE,
                    min=8192,
                    max=65536,
                    step=4096,
                    advanced=True,
                    tooltip="输入、视觉部件、思考和最终正文共享此上下文；数值越大，占用的内存/显存越多。",
                ),
                io.Int.Input(
                    "local_max_tokens",
                    display_name="本地单次生成 Token（含思考）",
                    default=DEFAULT_MAX_TOKENS,
                    min=256,
                    max=MAX_OUTPUT_TOKENS,
                    step=1024,
                    advanced=True,
                    tooltip=(
                        "这是思考过程与最终正文的生成上限。输入文字及已连接的图/视频会优先保留，"
                        "必要时自动下调本次实际生成上限；如需同时保留多媒体和较长输出，请提高本地上下文 Token。"
                    ),
                ),
                io.Combo.Input("local_think_mode", display_name="本地思考模式", options=LOCAL_THINK_OPTIONS, default=LOCAL_THINK_OFF, advanced=True),
                io.Combo.Input("local_reasoning_effort", display_name="本地推理强度", options=LOCAL_REASONING_OPTIONS, default="medium", advanced=True),
                io.Float.Input("local_video_sample_fps", display_name="本地视频采样率", default=DEFAULT_VIDEO_SAMPLE_FPS, min=0.25, max=8.0, step=0.25, advanced=True),
                io.Combo.Input("local_unload_policy", display_name="本地卸载策略", options=LOCAL_UNLOAD_POLICIES, default=LOCAL_UNLOAD_AFTER_RUN, advanced=True),
                io.Combo.Input("local_comfy_memory_policy", display_name="本地显存策略", options=LOCAL_COMFY_MEMORY_POLICIES, default=LOCAL_COMFY_MEMORY_POLICIES[0], advanced=True),
            ],
            outputs=[T8ProviderConfigIO.Output(display_name="provider_config")],
        )

    @classmethod
    def validate_inputs(cls, local_model=None, local_mmproj=None) -> bool:
        # Shared configs must remain loadable on machines with a different
        # local GGUF catalog; actual local paths are checked only when used.
        del local_model, local_mmproj
        return True

    @classmethod
    def execute(cls, **kwargs: Any) -> io.NodeOutput:
        return io.NodeOutput(build_provider_config(**kwargs))


__all__ = [
    "PROVIDER_CONFIG_SCHEMA",
    "PROVIDER_LOCAL",
    "PROVIDER_OPENAI",
    "PROVIDER_SEEDANCE",
    "PROVIDER_WORKSHOP",
    "ProviderConfigError",
    "T8LLMProviderConfig",
    "T8ProviderConfigIO",
    "build_provider_config",
    "merge_provider_config",
]
