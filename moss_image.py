"""Independent MOSS prompt authoring node using existing T8 provider infrastructure."""
from __future__ import annotations

from collections.abc import Mapping
import json
import re
import uuid

import requests
from comfy_api.latest import io

from . import moss_image_contract as contract
from . import moss_image_state as state
from . import moss_authoring as authoring
from .completion_recovery import RECOVERY_ACTION_RESTORE, recover_outputs, CompletionRecoveryError
from .execution_diagnostics import DiagnosticsRun
from .local_qwen_provider import (
    DEFAULT_CONTEXT_SIZE, DEFAULT_MAX_TOKENS, MAX_OUTPUT_TOKENS, LOCAL_QWEN_API_MODE,
    LOCAL_REASONING_OPTIONS, LOCAL_THINK_OFF, LOCAL_UNLOAD_AFTER_RUN,
    LOCAL_UNLOAD_POLICIES, LocalQwenProvider, LocalQwenProviderError,
    settings_from_values, is_local_qwen_api_mode, build_local_multimodal_parts, local_visual_part_budget, local_output_token_budget,
)
from .local_qwen_runtime import (
    AUTO_MMPROJ, DEFAULT_MODEL_FILENAME, LOCAL_COMFY_MEMORY_POLICIES, LOCAL_THINK_OPTIONS, list_gguf_models, list_mmproj_models,
)
from .nodes import (
    API_MODES, AI_WORKSHOP_API_MODE, AI_WORKSHOP_DEFAULT_MODEL, AI_WORKSHOP_MODEL_OPTIONS,
    OPENAI_API_MODE, SEEDANCE_API_MODE, PromptEnhancerError, REQUEST_TIMEOUT,
    _provider_config, _image_count, _image_at, _inline_media_plan, _openai_media_plan, _upload_media_plan,
    _is_seedance_chat_endpoint, _seedance_request_route_kwargs, _raise_http_error,
)
from .provider_config import (
    T8ProviderConfigIO, merge_provider_config, PROVIDER_LOCAL, PROVIDER_OPENAI, PROVIDER_SEEDANCE, PROVIDER_WORKSHOP,
)
from .provider_capabilities import apply_chat_request_options
from .provider_transport import request_chat_completion, ChatCompletionTruncatedError
from .strata_provider import strata_execution, is_strata_mode, require_strata_run, interrupted, StrataProviderError
from .strata_media import build_strata_media_parts

NODE_ID = state.NODE_ID
DEFAULT_LLM_MODEL = "qwen/qwen3.8-flash-next"
MAX_IMAGES = 10
_IMAGE_KEY = re.compile(r"(?:^|\.)reference_image_(\d+)$")
_MISSING = object()


class MossImageError(PromptEnhancerError):
    pass


def reference_inputs(reference_images=None, extra=None):
    """Accept current V3 nested Autogrow and historical flat sockets, in numeric order."""
    slots = {}
    groups = []
    if isinstance(reference_images, Mapping):
        groups.append(reference_images)
    elif isinstance(reference_images, (list, tuple)):
        groups.append({f"reference_image_{i}": value for i, value in enumerate(reference_images)})
    elif reference_images is not None:
        raise MossImageError("Reference images must be an Autogrow mapping / 参考图输入结构无效。")
    groups.append(extra or {})
    for group in groups:
        for name, value in group.items():
            match = _IMAGE_KEY.search(str(name))
            if match is None:
                if group is reference_images:
                    raise MossImageError("Unknown reference image slot / 参考图槽名称无效。")
                continue
            slot = int(match.group(1))
            if slot >= MAX_IMAGES:
                raise MossImageError("T8 accepts image slots 0–9 / 参考图槽须为 0–9。")
            if slot in slots and slots[slot] is not None and value is not None and slots[slot] is not value:
                raise MossImageError("Conflicting aliases for one image slot / 同一参考图槽存在冲突。")
            if slot not in slots or value is not None:
                slots[slot] = value
    return slots


def image_plan(slots):
    assets, image_map = [], []
    for slot, value in sorted(slots.items()):
        if value is None:
            continue
        for batch in range(_image_count(value)):
            image = _image_at(value, batch)
            if len(image.shape) != 3 or min(image.shape[:2]) <= 0 or image.shape[-1] not in (3, 4):
                raise MossImageError("Invalid reference image dimensions / 参考图尺寸无效。")
            label = f"Reference {len(assets) + 1}"
            assets.append({"kind": "image", "label": label, "value": image})
            image_map.append({"label": label, "source_slot": f"reference_image_{slot}", "batch_index": batch})
            if len(assets) > MAX_IMAGES:
                raise MossImageError("T8 allows at most ten images after batch expansion / 批次展开后最多十张参考图，不会丢图。")
    return assets, image_map


def validate_controls(operation, output_format, width, height, language, max_chars, repairs):
    if operation not in (contract.GENERATE, contract.COMPILE):
        raise MossImageError("Unsupported MOSS operation / 处理方式无效。")
    if operation == contract.COMPILE:
        return
    contract.normalize_format(output_format)
    # Compile Layout deliberately ignores disabled UI dimensions; its own
    # declared canvas is validated by compile_draft instead.
    if operation == contract.GENERATE:
        contract.canvas(width, height)
    if language not in contract.LANGUAGES:
        raise MossImageError("Unsupported descriptive language / 描述语言无效。")
    if type(max_chars) is not int or not 0 <= max_chars <= contract.MAX_DESCRIPTION_CHARS:
        raise MossImageError("Description limit must be 0–20000 / 描述字数须在 0–20000。")
    if type(repairs) is not int or repairs not in (0, 1):
        raise MossImageError("MOSS allows zero or one correction / 纠正次数只能为 0 或 1。")


def _canvas_conflict(prompt, width, height):
    # Conservative explicit-canvas syntax only. Product/screen dimensions or
    # arbitrary quoted numbers are NOT inferred as an authoritative canvas.
    pattern = r"(?:最终画布|出图尺寸|画布尺寸|canvas(?:\s+(?:size|dimensions))?|output\s+(?:size|resolution))\s*[:：=]?\s*(\d{2,5})\s*[xX×*]\s*(\d{2,5})"
    # Quoted copy, fenced examples, reference annotations and negated sizes are
    # task data, not final-canvas instructions. This remains a conservative
    # explicit-syntax guard, not natural-language intent recognition.
    quoted = r'```[\s\S]*?```|`[^`\n]*`|"(?:\\.|[^"\\])*"|“[^”]*”|‘[^’]*’|(?<!\w)\x27(?:\\.|[^\x27\\])*\x27|(?m:^\s*>[^\n]*)'
    masked = re.sub(quoted, lambda m: re.sub(r"[^\n]", " ", m.group(0)), prompt)
    for match in re.finditer(pattern, masked, re.IGNORECASE):
        before = re.split(r"[，,。.!！?？;；\n]", masked[:match.start()])[-1]
        after = re.split(r"[，,。.!！?？;；\n]", masked[match.end():], maxsplit=1)[0]
        if re.search(r"不要|不使用|不采用|避免|无需|禁止|勿|不能|并非|不是|\b(?:not|never|avoid|without)\b|don['’]t", before, re.IGNORECASE):
            continue
        if re.search(r"参考图|参考图片|水印|\b(?:reference|watermark)\b", before + after, re.IGNORECASE):
            continue
        if tuple(map(int, match.groups())) != (width, height):
            raise MossImageError("Explicit brief canvas conflicts with UI width/height / 需求中的明确画布与节点宽高冲突，请先统一尺寸。")


def _resolved_values(values, provider_config):
    current = dict(values)
    if provider_config is not None:
        config = dict(provider_config) if isinstance(provider_config, Mapping) else provider_config
        if isinstance(config, dict) and config.get("provider") == PROVIDER_LOCAL:
            # An inactive cloud alias must not make an offline generation fail.
            config.pop("credential_alias", None)
        current = merge_provider_config(current, config, api_mode_map={
            PROVIDER_LOCAL: LOCAL_QWEN_API_MODE, PROVIDER_OPENAI: OPENAI_API_MODE,
            PROVIDER_WORKSHOP: AI_WORKSHOP_API_MODE, PROVIDER_SEEDANCE: SEEDANCE_API_MODE,
        })
    mode = current["api_mode"]
    if mode not in API_MODES:
        raise MossImageError("Unsupported provider mode / 渠道无效。")
    if not is_local_qwen_api_mode(mode) and not is_strata_mode(mode):
        for name in ("custom_model", "openai_base_url"):
            current[name] = contract.clean_text(current.get(name) or "", name, limit=4096).strip()
    return current


def _model(current):
    mode = current["api_mode"]
    if is_strata_mode(mode):
        return require_strata_run().identity()["model"]
    if is_local_qwen_api_mode(mode):
        return "local-gguf"
    if mode == AI_WORKSHOP_API_MODE:
        selection = current["ai_workshop_model"]
        if selection == "Custom（自定义）":
            model = current.get("custom_model", "")
        elif selection == AI_WORKSHOP_DEFAULT_MODEL:
            model = selection
        else:
            raise MossImageError("Unsupported AI Workshop model / 工坊模型无效。")
    else:
        model = current.get("custom_model") or (DEFAULT_LLM_MODEL if mode == SEEDANCE_API_MODE else "")
    if not isinstance(model, str) or not model.strip() or any(x.isspace() for x in model):
        raise MossImageError("A valid chat model ID is required / 请填写有效的增强语言模型 ID。")
    return model


def _options(current, llm_max_tokens):
    source = current.get("provider_request_options") or {}
    result = dict(source)
    extra = dict(result.get("extra_parameters") or {})
    if "max_tokens" in extra and "max_completion_tokens" in extra:
        raise MossImageError("Specify one chat token parameter, not both / 请勿同时填写两种生成 Token 上限。")
    if "max_tokens" not in extra and "max_completion_tokens" not in extra:
        extra["max_tokens"] = llm_max_tokens
    result["extra_parameters"] = extra
    return result


class _CloudCompletion:
    def __init__(self, current, model, media, counters, validator):
        self.current, self.model, self.media = current, model, media
        self.counters, self.validator = counters, validator
        self.session = None
        self.raw = ""

    def __enter__(self):
        mode = self.current["api_mode"]
        self.key, self.url, upload, self.provider = _provider_config(mode, self.current.get("api_key", ""), self.current.get("openai_base_url", ""))
        if is_strata_mode(mode):
            self.parts = build_strata_media_parts(self.media)
        else:
            self.session = requests.Session()
            try:
                if mode == AI_WORKSHOP_API_MODE:
                    self.parts = _inline_media_plan(self.media)
                elif mode == OPENAI_API_MODE:
                    self.parts = _openai_media_plan(self.media, "")
                else:
                    self.parts = _upload_media_plan(self.session, self.key, self.media, upload, self.provider)
            except BaseException:
                self.session.close()
                raise
        return self

    def __exit__(self, *_args):
        if self.session is not None:
            self.session.close()

    def __call__(self, messages, repair):
        self.counters["logical_generation_calls"] += 1
        if is_strata_mode(self.current["api_mode"]):
            run = require_strata_run()
            before = run.requests
            try:
                self.raw = run.complete(messages, temperature=0.1 if repair else 0.3)
                return self.raw
            finally:
                self.counters["chat_post_attempts"] += max(0, run.requests - before)
        seedance = _is_seedance_chat_endpoint(self.url)
        payload = apply_chat_request_options({"model": self.model, "messages": messages, "stream": seedance},
                                             chat_url=self.url, temperature=0.1 if repair else 0.3,
                                             options=self.current["provider_request_options"])

        def checkpoint(text, complete, response_id):
            self.raw = text

        def attempt(number, phase):
            if phase == "start":
                self.counters["chat_post_attempts"] += 1

        def network(error, number, delays):
            return MossImageError(f"Chat network error: {type(error).__name__}. Not resent to avoid duplicate billing / 网络异常，未自动重发。")

        def accept(text):
            try:
                self.validator(text)
                return True
            except contract.MossContractError:
                return False

        result = request_chat_completion(
            session=self.session, url=self.url, api_key=self.key, payload=payload, timeout=REQUEST_TIMEOUT,
            retry_delays=(), retryable_status_codes=frozenset(),
            route_kwargs=lambda number, enabled: _seedance_request_route_kwargs(self.url, number, enabled),
            is_retryable_network_error=lambda error: False, sleep=lambda seconds: None,
            network_error=network, http_error=lambda response, number: _raise_http_error(response, self.key, "chat", self.provider, attempts=number),
            invalid_json_error=lambda: MossImageError("Chat returned invalid JSON / 渠道返回无效 JSON。"),
            missing_content_error=lambda: MossImageError("Chat response has no final content / 渠道未返回正文。"),
            empty_content_error=lambda: MossImageError("Chat returned an empty final answer / 渠道返回空正文。"),
            extra_headers={"Idempotency-Key": "t8-moss-" + uuid.uuid4().hex} if seedance else None,
            on_attempt=attempt, on_checkpoint=checkpoint, require_complete=True, stream_acceptor=accept,
        )
        self.raw = result.text
        return result.text


def _bounded(complete, messages, validator, repairs, counters):
    """One initial call, one shared correction budget, no unvalidated fallback."""
    first = complete(messages, False)
    best, last_error = None, None
    try:
        best = validator(first)
        if not best[-1]["over_limit"]:
            return best, "", False
    except contract.MossContractError as error:
        last_error = error
    if not repairs:
        if best is not None:
            return best, "description_over_limit", False
        raise last_error
    counters["correction_calls"] += 1
    correction = messages + [{"role": "assistant", "content": first}, {"role": "user", "content": (
        "Correct the previous complete draft once. Preserve every fixed fact, visible text block and canvas. "
        "Return ONLY one native MOSS draft JSON, no centered coordinates. Fix all schema, canvas, literal-text "
        "and description-limit constraints together. Problem: " + (last_error.code if last_error else "description_over_limit")
    )}]
    try:
        repaired = validator(complete(correction, True))
        if best is None or repaired[-1]["description_chars"] <= best[-1]["description_chars"]:
            return repaired, "description_over_limit" if repaired[-1]["over_limit"] else "", False
    except StrataProviderError as error:
        # A soft length repair may keep the complete first draft after a
        # bounded transport/output failure, never after a broken identity,
        # security, protocol, configuration or whole-run deadline invariant.
        if best is None or error.category not in {
            "connection", "service_error", "service_busy", "truncated", "empty_content", "structured_output",
        }:
            raise
    except (contract.MossContractError, PromptEnhancerError, LocalQwenProviderError,
            requests.RequestException, ChatCompletionTruncatedError):
        # Do not swallow cancellation/KeyboardInterrupt. A failed *optional*
        # correction cannot destroy a complete, hard-valid first result.
        if best is None:
            raise
    if best is not None:
        return best, "correction_failed_draft_kept", True
    raise last_error


def _authoring_soft_error(error):
    if isinstance(error, StrataProviderError):
        return error.category in {"connection", "service_error", "service_busy", "truncated", "empty_content", "structured_output"}
    return isinstance(error, (contract.MossContractError, PromptEnhancerError, LocalQwenProviderError,
                              requests.RequestException, ChatCompletionTruncatedError))


@strata_execution
def _generate(current, controls, media, image_map, counters, *, api_mode, provider_request_options, seed):
    def validator(text):
        return contract.compile_draft(contract.strict_json(text), output_format=controls["output_format"],
                                      width=controls["width"], height=controls["height"],
                                      locked_text=controls["locked_text"], max_chars=controls["max_output_chars"])

    def messages(parts=None):
        if controls.get("authoring_profile", authoring.CLASSIC) != authoring.CLASSIC:
            return authoring.build_messages(controls, [m["label"] for m in media], parts)
        return contract.build_messages(controls["prompt"], output_format=controls["output_format"], width=controls["width"],
                                       height=controls["height"], language=controls["output_language"],
                                       locked_text=controls["locked_text"], max_chars=controls["max_output_chars"],
                                       image_labels=[m["label"] for m in media], media_parts=parts)

    def bounded(complete, message_list):
        if controls.get("authoring_profile", authoring.CLASSIC) == authoring.CLASSIC:
            return _bounded(complete, message_list, validator, controls["max_corrections"], counters)
        policy = authoring.length_policy(controls["authoring_profile"], controls["prompt"], controls["output_language"], controls["max_output_chars"])
        return authoring.bounded(complete, message_list, validator, controls["max_corrections"], counters, policy, _authoring_soft_error)

    model = _model(current)
    if is_local_qwen_api_mode(api_mode):
        settings = settings_from_values(**{name: current[name] for name in (
            "local_model", "local_mmproj", "local_context_size", "local_max_tokens", "local_think_mode",
            "local_reasoning_effort", "local_unload_policy", "local_comfy_memory_policy")})
        budget = local_visual_part_budget(messages(), settings, required_visual_parts=len(media))
        parts, _ = build_local_multimodal_parts(media, settings, max_visual_parts=budget)
        initial_messages = messages(parts)
        local_output_token_budget(initial_messages, settings)  # reject before taking model/VRAM ownership
        with LocalQwenProvider(settings, vision=bool(media)) as provider:
            def complete(message_list, repair):
                if controls.get("authoring_profile", authoring.CLASSIC) != authoring.CLASSIC:
                    local_output_token_budget(message_list, settings)
                counters["logical_generation_calls"] += 1
                text = provider.complete(message_list, temperature=0.1 if repair else 0.3, seed=seed, require_complete=True)
                counters["failed_raw"] = text
                return text
            result, warning, repair_failed = bounded(complete, initial_messages)
    else:
        with _CloudCompletion(current, model, media, counters, validator) as complete:
            try:
                result, warning, repair_failed = bounded(complete, messages(complete.parts))
            except BaseException:
                counters["failed_raw"] = complete.raw
                raise
    interrupted()
    return result, model, warning, repair_failed


def _output(values, origin):
    report = json.loads(values[5])
    status = {"origin": origin, "operation": report["operation"], "format": values[3], "width": values[1], "height": values[2],
              "calls": report["logical_generation_calls"], "corrections": report["correction_calls"],
              "warnings": report["warnings"], "token_check": "unverified", "draft": values[4]}
    if "authoring_profile" in report:
        status.update(authoring_profile=report["authoring_profile"], authoring_length=report["authoring_length"])
    return io.NodeOutput(*values, ui={"t8_moss_image_result": [json.dumps(status, ensure_ascii=False)]})


class MOSSImagePromptEnhancer(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id=NODE_ID, display_name="MOSS Image Prompt Enhancer T8", category="T8/MOSS Image",
            description="MOSS-native Caption/Layout authoring. References inform the LLM, not native image editing. Compile-only needs no API or model. 4096-token target budget is not measured.",
            inputs=[
                io.String.Input("prompt", display_name="创作需求 / Brief（生成时必填）", multiline=True, default="", dynamic_prompts=False, lazy=True),
                io.Combo.Input("operation", display_name="处理方式 / Operation", options=[contract.GENERATE, contract.COMPILE], default=contract.GENERATE),
                io.Combo.Input("output_format", display_name="输出格式 / Format", options=contract.FORMATS, default=contract.AUTO),
                io.Int.Input("width", display_name="最终宽度 / Width", default=1024, min=16, max=contract.MAX_SIDE, step=8,
                             tooltip="8-pixel multiples are accepted without rounding; confirm downstream latent/image dimensions."),
                io.Int.Input("height", display_name="最终高度 / Height", default=1024, min=16, max=contract.MAX_SIDE, step=8,
                             tooltip="8-pixel multiples are accepted without rounding; confirm downstream latent/image dimensions."),
                io.Combo.Input("output_language", display_name="描述语言 / Language", options=contract.LANGUAGES, default=contract.LANG_AUTO),
                io.Combo.Input("api_mode", display_name="增强渠道 / Provider", options=list(API_MODES), default=SEEDANCE_API_MODE),
                io.Autogrow.Input("reference_images", optional=True, template=io.Autogrow.TemplatePrefix(
                    input=io.Image.Input("reference_image", lazy=True, tooltip="Only the enhancement LLM sees references. Not MOSS native image editing."), prefix="reference_image_", min=0, max=MAX_IMAGES)),
                io.String.Input("api_key", display_name="LLM API Key（本地无需）", optional=True, default="", force_input=True, lazy=True),
                T8ProviderConfigIO.Input("provider_config", display_name="共享 LLM 渠道配置（可选）", optional=True, lazy=True),
                io.String.Input("locked_text", display_name="锁定画面文案 / Exact visible text", optional=True, default="", multiline=True, dynamic_prompts=False, advanced=True),
                io.Int.Input("max_output_chars", display_name="最大描述字数（0=自动）/ Description limit", optional=True, default=0, min=0, max=contract.MAX_DESCRIPTION_CHARS, step=100,
                             tooltip="Unicode description characters, including punctuation/whitespace; excludes Layout visible text and JSON. Soft maximum, not Tokens; never truncates. 0 = automatic."),
                io.Int.Input("max_corrections", display_name="最多追加纠正 / Extra correction calls", optional=True, default=1, min=0, max=1, advanced=True),
                io.Int.Input("llm_max_tokens", display_name="云端生成 Token（含思考，不是MOSS 4096）", optional=True, default=16384, min=256, max=65536, step=1024, advanced=True),
                io.String.Input("draft_json", display_name="原始草稿 / Draft JSON（仅编译）", optional=True, default="", multiline=True, dynamic_prompts=False, advanced=True, lazy=True),
                io.Combo.Input("ai_workshop_model", display_name="AI 工坊模型", options=AI_WORKSHOP_MODEL_OPTIONS, default=AI_WORKSHOP_DEFAULT_MODEL, optional=True, advanced=True),
                io.String.Input("custom_model", display_name="增强语言模型 ID / Chat model", optional=True, default=DEFAULT_LLM_MODEL, advanced=True),
                io.String.Input("openai_base_url", display_name="OpenAI Base URL", optional=True, default="", advanced=True),
                io.Int.Input("seed", display_name="创作种子 / Seed", optional=True, default=0, min=0, max=0xffffffffffffffff, control_after_generate=True, advanced=True),
                io.Combo.Input("local_model", display_name="本地 GGUF 模型", options=list_gguf_models(), default=DEFAULT_MODEL_FILENAME, optional=True, advanced=True),
                io.Combo.Input("local_mmproj", display_name="视觉投影器（有图时）", options=list_mmproj_models(), default=AUTO_MMPROJ, optional=True, advanced=True),
                io.Int.Input("local_context_size", display_name="本地上下文 Token", default=DEFAULT_CONTEXT_SIZE, min=8192, max=65536, step=4096, optional=True, advanced=True),
                io.Int.Input("local_max_tokens", display_name="本地生成 Token（含思考）", default=DEFAULT_MAX_TOKENS, min=256, max=MAX_OUTPUT_TOKENS, step=1024, optional=True, advanced=True),
                io.Combo.Input("local_think_mode", display_name="本地思考模式", options=LOCAL_THINK_OPTIONS, default=LOCAL_THINK_OFF, optional=True, advanced=True),
                io.Combo.Input("local_reasoning_effort", display_name="本地推理强度", options=LOCAL_REASONING_OPTIONS, default="medium", optional=True, advanced=True),
                io.Combo.Input("local_unload_policy", display_name="本地卸载策略", options=LOCAL_UNLOAD_POLICIES, default=LOCAL_UNLOAD_AFTER_RUN, optional=True, advanced=True),
                io.Combo.Input("local_comfy_memory_policy", display_name="本地显存策略", options=LOCAL_COMFY_MEMORY_POLICIES, default=LOCAL_COMFY_MEMORY_POLICIES[0], optional=True, advanced=True),
                io.String.Input("recovery_slot", optional=True, default="", advanced=True, socketless=True),
                io.String.Input("recovery_action", optional=True, default="normal", advanced=True, socketless=True),
                io.Combo.Input("authoring_profile", display_name="强化模式 / Authoring profile", options=list(authoring.PROFILES), default=authoring.CLASSIC, optional=True, socketless=True),
            ], outputs=[io.String.Output(display_name="正向提示词 / positive_prompt"), io.Int.Output(display_name="宽 / width"),
                        io.Int.Output(display_name="高 / height"), io.String.Output(display_name="实际格式 / resolved_format"),
                        io.String.Output(display_name="可编辑草稿 / draft_json"), io.String.Output(display_name="诊断报告 / report_json")])

    @classmethod
    def validate_inputs(cls, prompt="", operation=contract.GENERATE, output_format=contract.AUTO, width=1024, height=1024,
                        output_language=contract.LANG_AUTO, max_output_chars=0, max_corrections=1,
                        draft_json="", recovery_action="normal", authoring_profile=authoring.CLASSIC, **kwargs):
        if recovery_action == RECOVERY_ACTION_RESTORE:
            return True
        if operation is None:
            return True  # upstream mode is unresolved; execute validates the resolved branch
        try:
            if operation == contract.GENERATE and authoring_profile is not None:
                authoring.validate_profile(authoring_profile)
            # Graph validation cannot resolve upstream INT/STRING widgets yet.
            # execute checks every resolved value before any provider/model.
            validate_controls(operation, contract.AUTO if output_format is None else output_format,
                              1024 if width is None else width, 1024 if height is None else height,
                              contract.LANG_AUTO if output_language is None else output_language,
                              0 if max_output_chars is None else max_output_chars,
                              1 if max_corrections is None else max_corrections)
            if operation == contract.GENERATE and prompt is not None and (not isinstance(prompt, str) or not prompt.strip()):
                return "Brief is required for generation / 生成时请填写创作需求。"
            if operation == contract.COMPILE and draft_json is not None and (not isinstance(draft_json, str) or not draft_json.strip()):
                return "Draft JSON is required for compile-only / 仅编译时请填写原始草稿。"
            return True
        except (contract.MossContractError, MossImageError) as error:
            return str(error)

    @classmethod
    def check_lazy_status(cls, prompt=None, operation=contract.GENERATE, reference_images=_MISSING, api_key=_MISSING, provider_config=_MISSING,
                          draft_json=None, recovery_action="normal", api_mode=SEEDANCE_API_MODE, **kwargs):
        if recovery_action == RECOVERY_ACTION_RESTORE:
            return []
        if operation == contract.COMPILE:
            return ["draft_json"] if draft_json is None else []
        needs = ["prompt"] if prompt is None else []
        if provider_config is None:
            # Resolve the selected route first. Shared local/Strata must not
            # execute an irrelevant linked cloud-Key dependency.
            return ["provider_config"]
        provider = provider_config.get("provider") if isinstance(provider_config, Mapping) else None
        mode = {PROVIDER_LOCAL: LOCAL_QWEN_API_MODE, "Strata": "Strata 本地服务（桥接）",
                PROVIDER_OPENAI: OPENAI_API_MODE, PROVIDER_WORKSHOP: AI_WORKSHOP_API_MODE,
                PROVIDER_SEEDANCE: SEEDANCE_API_MODE}.get(provider, api_mode)
        # ComfyUI ignores requests for unconnected optional sockets. Flat
        # legacy lazy names must be requested by their actual graph names.
        if api_key is None and not is_local_qwen_api_mode(mode) and not is_strata_mode(mode):
            needs.append("api_key")
        if reference_images is None:
            needs.append("reference_images")
        def unresolved_image(value, fallback):
            # Recent V3 hosts pass dynamic lazy fields as (value, original_key)
            # to check_lazy_status only. Treating that tuple as an evaluated
            # image silently skips the upstream image node.
            if isinstance(value, tuple) and len(value) == 2 and isinstance(value[1], str):
                return value[1] if value[0] is None else None
            return fallback if value is None else None
        for name, value in kwargs.items():
            if _IMAGE_KEY.search(name):
                missing = unresolved_image(value, name)
                if missing: needs.append(missing)
        if isinstance(reference_images, Mapping):
            for name, value in reference_images.items():
                missing = unresolved_image(value, f"reference_images.{name}" if "." not in name else name)
                if missing: needs.append(missing)
        return needs

    @classmethod
    def execute(cls, prompt="", operation=contract.GENERATE, output_format=contract.AUTO, width=1024, height=1024,
                output_language=contract.LANG_AUTO, api_mode=SEEDANCE_API_MODE, reference_images=None, api_key="", provider_config=None,
                locked_text="", max_output_chars=0, max_corrections=1, llm_max_tokens=16384, draft_json="",
                ai_workshop_model=AI_WORKSHOP_DEFAULT_MODEL, custom_model=DEFAULT_LLM_MODEL, openai_base_url="", seed=0,
                local_model=DEFAULT_MODEL_FILENAME, local_mmproj=AUTO_MMPROJ, local_context_size=DEFAULT_CONTEXT_SIZE,
                local_max_tokens=DEFAULT_MAX_TOKENS, local_think_mode=LOCAL_THINK_OFF, local_reasoning_effort="medium",
                local_unload_policy=LOCAL_UNLOAD_AFTER_RUN, local_comfy_memory_policy=LOCAL_COMFY_MEMORY_POLICIES[0],
                recovery_slot="", recovery_action="normal", authoring_profile=authoring.CLASSIC, **kwargs):
        if recovery_action == RECOVERY_ACTION_RESTORE:
            diagnostics = DiagnosticsRun(NODE_ID, "cache", 1, emit_progress=False)
            try:
                cached = contract.decode_cached(recover_outputs(NODE_ID, recovery_slot, 6))
                diagnostics.advance("restored", cache_hit=True)
                diagnostics.complete("success")
                return _output(cached, "cache")
            except (CompletionRecoveryError, contract.MossContractError) as error:
                diagnostics.complete("error", error)
                raise MossImageError(str(error)) from error
        if recovery_action not in ("", "normal", None):
            raise MossImageError("Invalid recovery action / 恢复动作无效。")
        counters = {"logical_generation_calls": 0, "chat_post_attempts": 0, "correction_calls": 0}
        diagnostics = DiagnosticsRun(NODE_ID, "none" if operation == contract.COMPILE else "generation", 3, emit_progress=False)
        token, pending_slot = state.begin(recovery_slot)
        raw = draft_json if operation == contract.COMPILE else ""
        try:
            validate_controls(operation, output_format, width, height, output_language, max_output_chars, max_corrections)
            if operation == contract.COMPILE:
                data = contract.strict_json(draft_json)
                # UI format/language/limits/locks/providers are inactive: only
                # the editable draft determines compilation and Layout canvas.
                if isinstance(data, dict) and "caption" not in data:
                    width, height = data.get("width"), data.get("height")
                result = contract.compile_draft(data, width=width, height=height, fixed_canvas=False)
                model, warning, repair_failed, mapping = "none", "", False, []
                provider_mode = "none"
            else:
                authoring.validate_profile(authoring_profile)
                contract.clean_text(prompt, "brief", limit=64000)
                if not prompt.strip():
                    raise MossImageError("Brief is required / 请填写创作需求。")
                contract.locked_blocks(locked_text)
                _canvas_conflict(prompt, width, height)
                media, mapping = image_plan(reference_inputs(reference_images, kwargs))
                if authoring_profile == authoring.FISHER and len(media) > 1:
                    raise MossImageError("Fisher single-image mode cannot merge independent references / Fisher多图默认须逐张处理，请分别连接单图；完整集合入口单独处理独立/融合模式。")
                current = _resolved_values({"api_mode": api_mode, "api_key": api_key or "", "custom_model": custom_model,
                    "ai_workshop_model": ai_workshop_model, "openai_base_url": openai_base_url,
                    "local_model": local_model, "local_mmproj": local_mmproj, "local_context_size": local_context_size,
                    "local_max_tokens": local_max_tokens, "local_think_mode": local_think_mode,
                    "local_reasoning_effort": local_reasoning_effort, "local_unload_policy": local_unload_policy,
                    "local_comfy_memory_policy": local_comfy_memory_policy}, provider_config)
                if is_local_qwen_api_mode(current["api_mode"]) or is_strata_mode(current["api_mode"]):
                    current["provider_request_options"] = dict(current.get("provider_request_options") or {})
                else:
                    if type(llm_max_tokens) is not int or not 256 <= llm_max_tokens <= 65536:
                        raise MossImageError("Cloud token budget must be 256–65536 / 云端生成预算无效。")
                    current["provider_request_options"] = _options(current, llm_max_tokens)
                diagnostics.provider = current["api_mode"]
                diagnostics.advance("inputs_validated", asset_count=len(media))
                controls = {"prompt": prompt, "output_format": output_format, "width": width, "height": height,
                            "output_language": output_language, "locked_text": locked_text, "max_output_chars": max_output_chars,
                            "max_corrections": max_corrections}
                if authoring_profile != authoring.CLASSIC:
                    controls["authoring_profile"] = authoring_profile
                result, model, warning, repair_failed = _generate(current, controls, media, mapping, counters,
                    api_mode=current["api_mode"], provider_request_options=current["provider_request_options"], seed=seed)
                provider_mode = current["api_mode"]
            positive, out_width, out_height, actual, editable, details = result
            warnings = ["moss_4096_token_budget_unverified"]
            if out_width % 16 or out_height % 16:
                warnings.append("eight_pixel_canvas_downstream_unverified")
            if warning:
                warnings.append(warning)
            if details["over_limit"] and "description_over_limit" not in warnings:
                warnings.append("description_over_limit")
            report = {"schema_version": "t8-moss-image-report/v1", "adapter_revision": contract.REVISION,
                "source_commit": contract.SOURCE_COMMIT, "operation": operation, "provider_mode": provider_mode,
                "enhancement_model": model, "requested_format": output_format if operation == contract.GENERATE else "draft",
                "resolved_format": actual, "canvas": {"width": out_width, "height": out_height},
                "canvas_source": "draft" if operation == contract.COMPILE and actual == "layout" else "ui",
                "image_map": mapping, "references_are_native_editing": False,
                **{k: v for k, v in counters.items() if k != "failed_raw"}, **details,
                "repair_failed": repair_failed, "warnings": warnings, "image_generation_performed": False,
                "default_model_quality": "requires_live_acceptance"}
            if operation == contract.GENERATE and authoring_profile != authoring.CLASSIC:
                policy = authoring.length_policy(authoring_profile, prompt, output_language, max_output_chars)
                report.update(authoring_profile=authoring_profile, authoring_revision=authoring.REVISION,
                              authoring_length=authoring.length_metadata(result, policy))
            outputs = positive, out_width, out_height, actual, editable, json.dumps(report, ensure_ascii=False)
            interrupted()
            state.commit(recovery_slot, token, outputs)
            diagnostics.advance("compiled", attempts=counters["logical_generation_calls"])
            diagnostics.complete("success")
            return _output(outputs, "current")
        except BaseException as error:
            diagnostics.complete("error", error)
            code = error.code if isinstance(error, contract.MossContractError) else type(error).__name__
            failed_raw = counters.get("failed_raw", raw)
            failed_raw = contract.KEY_RE.sub("[REDACTED]", failed_raw) if isinstance(failed_raw, str) else ""
            state.failed(recovery_slot, token, failed_raw, code)
            if isinstance(error, (contract.MossContractError, CompletionRecoveryError)):
                note = " Failed draft is retained for explicit inspection / 可查看保留的失败草稿。" if state.status(recovery_slot).get("failed_draft_available") else ""
                raise MossImageError(f"{error}{note}") from error
            raise
