"""Independent MiniMax H3 Image prompt expansion through existing T8 providers."""
from __future__ import annotations

from collections.abc import Mapping
import json
import math
import re
import uuid

import requests
from comfy_api.latest import io

from . import h3_image_contract as contract
from . import h3_image_state as state
from .completion_recovery import RECOVERY_ACTION_RESTORE, recover_outputs, CompletionRecoveryError
from .execution_diagnostics import DiagnosticsRun, _provider_label
from .local_qwen_provider import (
    DEFAULT_CONTEXT_SIZE, DEFAULT_MAX_TOKENS, MAX_OUTPUT_TOKENS, LOCAL_QWEN_API_MODE,
    LOCAL_REASONING_OPTIONS, LOCAL_THINK_OFF, LOCAL_UNLOAD_AFTER_RUN, LOCAL_UNLOAD_POLICIES,
    LocalQwenProvider, settings_from_values, is_local_qwen_api_mode, build_local_multimodal_parts,
    local_visual_part_budget, local_output_token_budget,
)
from .local_qwen_runtime import (
    AUTO_MMPROJ, DEFAULT_MODEL_FILENAME, LOCAL_COMFY_MEMORY_POLICIES, LOCAL_THINK_OPTIONS,
    list_gguf_models, list_mmproj_models,
)
from .nodes import (
    API_MODES, AI_WORKSHOP_API_MODE, AI_WORKSHOP_DEFAULT_MODEL, AI_WORKSHOP_MODEL_OPTIONS,
    OPENAI_API_MODE, SEEDANCE_API_MODE, PromptEnhancerError, REQUEST_TIMEOUT,
    _provider_config, _image_count, _image_at, _inline_media_plan, _openai_media_plan, _upload_media_plan,
    _is_seedance_chat_endpoint, _seedance_request_route_kwargs,
)
from .provider_config import (
    T8ProviderConfigIO, merge_provider_config, PROVIDER_LOCAL, PROVIDER_OPENAI, PROVIDER_SEEDANCE, PROVIDER_WORKSHOP,
)
from .provider_capabilities import apply_chat_request_options, normalize_extra_parameters
from .provider_transport import request_chat_completion
from .strata_provider import strata_execution, is_strata_mode, require_strata_run, interrupted
from .strata_media import build_strata_media_parts

NODE_ID = state.NODE_ID
DEFAULT_LLM_MODEL = "qwen/qwen3.8-flash-next"
MAX_IMAGES = 16
_IMAGE_KEY = re.compile(r"(?:^|\.)reference_image_(\d+)$")
_MISSING = object()
_LOCAL_FIELDS = ("local_model", "local_mmproj", "local_context_size", "local_max_tokens", "local_think_mode",
                 "local_reasoning_effort", "local_unload_policy", "local_comfy_memory_policy")


class H3ImageError(PromptEnhancerError):
    pass


def resolve_canvas_ratio(task_type, aspect_ratio, width=0, height=0):
    """Optional pixel inputs override the legacy ratio; 0/0 preserves old graphs."""
    for value in (width, height):
        if type(value) is not int or not 0 <= value <= 9007199254740991:
            raise H3ImageError("canvas_size: Width and height must be nonnegative integers / 宽高须为非负整数。")
    if width == height == 0:
        return aspect_ratio, {"ratio_source": "adaptive" if aspect_ratio == "auto" else "explicit"}
    if not width or not height:
        raise H3ImageError("canvas_size: Connect both positive width and height / 请同时连接正数宽度和高度。")
    divisor = math.gcd(width, height)
    exact = f"{width // divisor}:{height // divisor}"
    resolved = exact
    if task_type == contract.T2I:
        def distance(ratio):
            w, h = map(int, ratio.split(":"))
            return abs(math.log((width / height) / (w / h)))
        resolved = min(contract.T2I_RATIOS, key=distance)
    return resolved, {"ratio_source": "dimensions", "canvas_dimensions": {"width": width, "height": height},
                      "exact_canvas_aspect_ratio": exact, "resolved_canvas_aspect_ratio": resolved,
                      "ratio_mapped_to_supported": resolved != exact}


def image_plan(reference_images=None, extra=None):
    """One image per socket; numeric socket order becomes continuous Picture IDs."""
    slots = {}
    if reference_images is not None and not isinstance(reference_images, Mapping):
        raise H3ImageError("image_slots: Reference images must be named sockets / 参考图输入结构无效。")
    for group in (reference_images or {}, extra or {}):
        for name, value in group.items():
            match = _IMAGE_KEY.search(str(name))
            if not match:
                if group is reference_images:
                    raise H3ImageError("image_slot: Unknown reference socket / 参考图槽无效。")
                continue
            slot = int(match.group(1))
            if slot >= MAX_IMAGES:
                raise H3ImageError("image_slot: Use slots 0–15 / 最多16张参考图。")
            if slot in slots and slots[slot] is not None and value is not None and slots[slot] is not value:
                raise H3ImageError("image_alias: Conflicting reference inputs / 同一图槽存在冲突。")
            if slot not in slots or value is not None:
                slots[slot] = value
    media, mapping = [], []
    for slot, value in sorted(slots.items()):
        if value is None:
            continue
        if _image_count(value) != 1:
            raise H3ImageError("image_batch: Split batches into separate single-image sockets / 请将批次拆成单图，每槽一张。")
        image = _image_at(value, 0)
        if len(image.shape) != 3 or min(image.shape[:2]) <= 0 or image.shape[-1] not in (3, 4):
            raise H3ImageError("image_shape: Invalid reference image / 参考图尺寸无效。")
        height, width = map(int, image.shape[:2])
        divisor = math.gcd(width, height)
        label = f"<Picture {len(media) + 1}>"
        media.append({"kind": "image", "label": label, "value": image})
        mapping.append({"label": label, "source_slot": f"reference_image_{slot}", "width": width,
                        "height": height, "aspect_ratio": f"{width // divisor}:{height // divisor}"})
    return media, mapping


def _resolved_values(values, provider_config):
    current = dict(values)
    if provider_config is not None:
        config = dict(provider_config) if isinstance(provider_config, Mapping) else provider_config
        if isinstance(config, dict) and config.get("provider") == PROVIDER_LOCAL:
            config.pop("credential_alias", None)
        current = merge_provider_config(current, config, api_mode_map={
            PROVIDER_LOCAL: LOCAL_QWEN_API_MODE, PROVIDER_OPENAI: OPENAI_API_MODE,
            PROVIDER_WORKSHOP: AI_WORKSHOP_API_MODE, PROVIDER_SEEDANCE: SEEDANCE_API_MODE,
        })
    if current["api_mode"] not in API_MODES:
        raise H3ImageError("provider: Unsupported provider / 增强渠道无效。")
    return current


def _model(current):
    mode = current["api_mode"]
    if is_strata_mode(mode):
        return require_strata_run().identity()["model"]
    if is_local_qwen_api_mode(mode):
        return str(current["local_model"]).replace("\\", "/").rsplit("/", 1)[-1]
    if mode == AI_WORKSHOP_API_MODE:
        selection = current["ai_workshop_model"]
        if selection not in AI_WORKSHOP_MODEL_OPTIONS:
            raise H3ImageError("model: Unsupported Workshop model / 工坊模型选择无效。")
        model = current.get("custom_model") if selection == "Custom（自定义）" else selection
    else:
        model = current.get("custom_model") or (DEFAULT_LLM_MODEL if mode == SEEDANCE_API_MODE else "")
    if not isinstance(model, str) or not model.strip() or len(model) > 512 or any(c.isspace() for c in model):
        raise H3ImageError("model: Enter a valid chat model ID / 请填写有效的增强语言模型ID。")
    return model


def _options(current, max_tokens, controls):
    result = dict(current.get("provider_request_options") or {})
    if is_strata_mode(current["api_mode"]) or is_local_qwen_api_mode(current["api_mode"]):
        return result
    if type(max_tokens) is not int or not 256 <= max_tokens <= 65536:
        raise H3ImageError("cloud_budget: Use 256–65536 output Tokens / 云端生成Token预算无效。")
    extra = normalize_extra_parameters(result.get("extra_parameters"))
    if "max_tokens" in extra and "max_completion_tokens" in extra:
        raise H3ImageError("cloud_budget: Specify only one token parameter / 请勿同时填写两种Token上限。")
    if "max_tokens" not in extra and "max_completion_tokens" not in extra:
        extra["max_tokens"] = max_tokens
    for name in ("max_tokens", "max_completion_tokens"):
        if name in extra and (type(extra[name]) is not int or extra[name] <= 0):
            raise H3ImageError("cloud_budget: Token budget must be a positive integer / 生成Token预算必须是正整数。")
    requested = extra.get("response_format")
    if requested is not None and requested != {"type": "json_object"}:
        supported = [contract.response_format(controls["task_type"], ratio)["json_schema"]["schema"]
                     for ratio in ("auto", controls["aspect_ratio"])]
        block = requested.get("json_schema") if isinstance(requested, dict) else None
        # A schema name is provider metadata, not part of the two-field
        # contract. Preserve the official release's differently named schema.
        if (not isinstance(requested, dict) or requested.get("type") != "json_schema"
                or not isinstance(block, dict) or block.get("schema") not in supported):
            raise H3ImageError("response_format: Shared response schema conflicts with H3 Image / 共享配置的输出格式与H3 Image冲突。")
    result["extra_parameters"] = extra
    # Validate optional provider policy before uploads, not after billing starts.
    apply_chat_request_options({}, chat_url=current.get("openai_base_url", ""), temperature=0.3, options=result)
    return result


class _CloudCompletion:
    def __init__(self, current, model, media, counters, validator):
        self.current, self.model, self.media = current, model, media
        self.counters, self.validator, self.session = counters, validator, None

    def __enter__(self):
        mode = self.current["api_mode"]
        if is_strata_mode(mode):
            self.parts = build_strata_media_parts(self.media)
            return self
        self.key, self.url, upload, self.provider = _provider_config(mode, self.current.get("api_key", ""), self.current.get("openai_base_url", ""))
        self.session = requests.Session()
        try:
            if mode == AI_WORKSHOP_API_MODE:
                self.parts = _inline_media_plan(self.media)
            elif mode == OPENAI_API_MODE:
                self.parts = _openai_media_plan(self.media, "")
            else:
                self.parts = _upload_media_plan(self.session, self.key, self.media, upload, self.provider)
        except (requests.RequestException, PromptEnhancerError) as error:
            self.session.close()
            raise H3ImageError("media_transport: Reference preparation/upload failed / 参考图准备或上传失败，请检查所选渠道。") from None
        except BaseException:
            self.session.close()
            raise
        return self

    def __exit__(self, *_):
        if self.session is not None:
            self.session.close()

    def __call__(self, messages, repair):
        self.counters["logical_generation_calls"] += 1
        if is_strata_mode(self.current["api_mode"]):
            run = require_strata_run()
            before = run.requests
            try:
                return run.complete(messages, temperature=0.1 if repair else 0.3)
            finally:
                self.counters["chat_post_attempts"] += max(0, run.requests - before)
        seedance = _is_seedance_chat_endpoint(self.url)
        payload = apply_chat_request_options({"model": self.model, "messages": messages, "stream": seedance},
            chat_url=self.url, temperature=0.1 if repair else 0.3, options=self.current["provider_request_options"])

        def attempt(number, phase):
            if phase == "start":
                self.counters["chat_post_attempts"] += 1

        def accept(text):
            try:
                self.validator(text)
                return True
            except contract.H3ImageContractError:
                return False

        def http_error(response, number):
            raise H3ImageError(f"http_{response.status_code}: Check provider/model settings / 请检查渠道、模型与接口能力。")

        result = request_chat_completion(
            session=self.session, url=self.url, api_key=self.key, payload=payload, timeout=REQUEST_TIMEOUT,
            retry_delays=(), retryable_status_codes=frozenset(),
            route_kwargs=lambda number, enabled: _seedance_request_route_kwargs(self.url, number, enabled),
            is_retryable_network_error=lambda error: False, sleep=lambda seconds: None,
            network_error=lambda error, number, delays: H3ImageError("network: Request failed; not resent / 网络异常，未自动重发。"),
            http_error=http_error,
            invalid_json_error=lambda: H3ImageError("provider_json: Invalid chat response / 渠道响应结构无效。"),
            missing_content_error=lambda: H3ImageError("no_content: No final answer / 渠道未返回正文。"),
            empty_content_error=lambda: H3ImageError("empty_content: Empty answer / 渠道返回空正文。"),
            extra_headers={"Idempotency-Key": "t8-h3-image-" + uuid.uuid4().hex} if seedance else None,
            on_attempt=attempt, require_complete=True, stream_acceptor=accept,
        )
        return result.text


def _bounded(complete, messages, validator, repairs, counters):
    raw = complete(messages, False)
    if not isinstance(raw, str) or not raw.strip():
        raise H3ImageError("empty_content: No complete answer; not resent / 没有完整正文，未自动重发。")
    try:
        return validator(raw)
    except contract.H3ImageContractError as error:
        if not repairs:
            raise
        problem = error.code
    counters["correction_calls"] += 1
    correction = messages + [{"role": "assistant", "content": raw}, {"role": "user", "content": (
        "Correct the previous complete answer once. Keep all original facts, reference roles and exact visible text. "
        "Follow the original task's two-field JSON contract, English single-paragraph caption and selected aspect ratio. "
        "Return only that complete JSON object. Fix this validation problem: " + problem
    )}]
    return validator(complete(correction, True))


@strata_execution
def _generate(current, controls, media, mapping, counters, *, api_mode, provider_request_options, seed):
    def validator(raw):
        return contract.parse_result(raw, controls["task_type"], controls["aspect_ratio"], controls["locked_text"], controls["target_words"])

    def messages(parts=None):
        return contract.build_messages(controls["prompt"], controls["task_type"], controls["aspect_ratio"],
            controls["target_words"], controls["locked_text"], mapping, parts)

    model = _model(current)
    budgets = []
    if is_local_qwen_api_mode(api_mode):
        settings = settings_from_values(**{name: current[name] for name in _LOCAL_FIELDS})
        budget = local_visual_part_budget(messages(), settings, required_visual_parts=len(media))
        parts, _ = build_local_multimodal_parts(media, settings, max_visual_parts=budget)
        initial = messages(parts)
        local_output_token_budget(initial, settings)
        with LocalQwenProvider(settings, vision=bool(media)) as provider:
            def complete(message_list, repair):
                effective = local_output_token_budget(message_list, settings)
                budgets.append({"source": "local_max_tokens", "requested": settings.max_tokens, "estimated_effective": effective})
                counters["logical_generation_calls"] += 1
                return provider.complete(message_list, temperature=0.1 if repair else 0.3, seed=seed,
                    require_complete=True, response_format=contract.response_format(controls["task_type"], controls["aspect_ratio"]))
            result = _bounded(complete, initial, validator, controls["max_corrections"], counters)
    else:
        with _CloudCompletion(current, model, media, counters, validator) as complete:
            result = _bounded(complete, messages(complete.parts), validator, controls["max_corrections"], counters)
        if is_strata_mode(api_mode):
            budgets.append({"source": "strata_settings", "requested": require_strata_run().settings.max_tokens})
        else:
            extra = current["provider_request_options"]["extra_parameters"]
            name = "max_completion_tokens" if "max_completion_tokens" in extra else "max_tokens"
            budgets.append({"source": name, "requested": extra[name]})
    interrupted()
    return result, model, budgets


def _restore(slot):
    values = recover_outputs(NODE_ID, slot, 4)
    try:
        if not all(isinstance(value, str) for value in values):
            raise ValueError
        report = json.loads(values[3])
        if (not isinstance(report, dict) or report.get("schema_version") != "t8-h3-image-report/v1"
                or report.get("adapter_revision") != contract.REVISION or report.get("source_commit") != contract.SOURCE_COMMIT
                or report.get("model_source_commit") != contract.MODEL_SOURCE_COMMIT
                or report.get("source_manifest_sha256") != contract.SOURCE_MANIFEST_SHA256):
            raise ValueError
        result = contract.parse_result(values[2], report["task_type"], target_words=report["target_words"])
        if result[:2] != tuple(values[:2]) or result[2] != values[2]:
            raise ValueError
        for field in ("caption_words", "target_words", "word_count_delta", "word_count_method", "word_target_is_soft"):
            expected = result[3][field]
            if type(report.get(field)) is not type(expected) or report[field] != expected:
                raise ValueError
        calls, corrections, posts = (report.get(name) for name in ("logical_generation_calls", "correction_calls", "chat_post_attempts"))
        if (type(calls) is not int or type(corrections) is not int or corrections not in (0, 1)
                or calls != 1 + corrections or type(posts) is not int):
            raise ValueError
        mode = report.get("provider_mode")
        if mode not in API_MODES or posts != (0 if is_local_qwen_api_mode(mode) else calls):
            raise ValueError
        mapping = contract._checked_image_map(report.get("image_map"))
        if (report["task_type"] == contract.T2I and mapping) or (report["task_type"] == contract.EDIT and not mapping):
            raise ValueError
        slots = [row["source_slot"] for row in mapping]
        if any(not isinstance(name, str) or not re.fullmatch(r"reference_image_(?:[0-9]|1[0-5])", name) for name in slots):
            raise ValueError
        numbers = [int(name.rsplit("_", 1)[1]) for name in slots]
        if numbers != sorted(set(numbers)):
            raise ValueError
        locked = report.get("locked_line_count")
        if (type(locked) is not int or locked < 0 or type(report.get("exact_text_order_verified")) is not bool
                or report["exact_text_order_verified"] != bool(locked)
                or report.get("semantics_verified") is not False or report.get("descriptive_language_verified") is not False
                or report.get("image_generation_performed") is not False):
            raise ValueError
        report["origin"] = "cache"
        return io.NodeOutput(*values[:3], json.dumps(report, ensure_ascii=False))
    except (TypeError, ValueError, KeyError, RecursionError, contract.H3ImageContractError):
        raise H3ImageError("recovery_invalid: Cached result is invalid / 缓存结果无效，请重新生成。") from None


class MiniMaxH3ImagePromptEnhancer(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id=NODE_ID, display_name="MiniMax H3 Image Prompt Enhancer T8", category="T8/H3 Image",
            description="Official H3 Image T2I/Edit prompt expansion. English description preserves original visible text. Connect expanded_prompt to H3; edit references must also reach H3 in the same order.",
            inputs=[
                io.String.Input("prompt", display_name="创作/编辑需求 / Brief", multiline=True, default="", dynamic_prompts=False, lazy=True),
                io.Combo.Input("task_type", display_name="任务 / Task", options=contract.TASKS, default=contract.T2I),
                io.String.Input("aspect_ratio", display_name="画幅比例 / Ratio (auto)", default="auto", dynamic_prompts=False,
                    tooltip="Optional width + height inputs take priority and compute the ratio. T2I maps to the closest official ratio; Edit preserves exact reduced W:H. With no dimensions: auto or a supported ratio. Does not resize downstream images."),
                io.Int.Input("target_words", display_name="目标英文词数（0=官方自动）", default=0, min=0, max=9007199254740991, step=1,
                    tooltip="Approximate caption word target, not Tokens. No 1000 ceiling; never truncates or omits fixed facts to meet a length."),
                io.Combo.Input("api_mode", display_name="增强渠道 / Provider", options=list(API_MODES), default=SEEDANCE_API_MODE),
                io.Autogrow.Input("reference_images", optional=True, template=io.Autogrow.TemplatePrefix(
                    input=io.Image.Input("reference_image", lazy=True, tooltip="Edit only. One image per slot; slot order defines <Picture N>."), prefix="reference_image_", min=0, max=MAX_IMAGES)),
                io.String.Input("api_key", display_name="LLM API Key（本地无需）", optional=True, default="", force_input=True, lazy=True),
                T8ProviderConfigIO.Input("provider_config", display_name="共享 LLM 渠道配置（可选）", optional=True, lazy=True),
                io.String.Input("locked_text", display_name="逐字锁定画面文案 / Exact visible text", optional=True, default="", multiline=True, dynamic_prompts=False, advanced=True),
                io.Int.Input("max_corrections", display_name="最多追加纠正 / Extra corrections", optional=True, default=1, min=0, max=1, advanced=True),
                io.Int.Input("llm_max_tokens", display_name="云端生成Token（含思考）", optional=True, default=16384, min=256, max=65536, step=1024, advanced=True),
                io.Combo.Input("ai_workshop_model", display_name="AI 工坊模型", options=AI_WORKSHOP_MODEL_OPTIONS, default=AI_WORKSHOP_DEFAULT_MODEL, optional=True, advanced=True),
                io.String.Input("custom_model", display_name="增强语言模型 ID / Chat model", optional=True, default=DEFAULT_LLM_MODEL, advanced=True),
                io.String.Input("openai_base_url", display_name="OpenAI Base URL", optional=True, default="", advanced=True),
                io.Int.Input("seed", display_name="本地种子 / Local seed", optional=True, default=0, min=0, max=0xffffffff, control_after_generate=False, advanced=True),
                io.Combo.Input("local_model", display_name="本地 GGUF 模型", options=list_gguf_models(), default=DEFAULT_MODEL_FILENAME, optional=True),
                io.Combo.Input("local_mmproj", display_name="视觉投影器（编辑时）", options=list_mmproj_models(), default=AUTO_MMPROJ, optional=True),
                io.Int.Input("local_context_size", display_name="本地上下文Token", default=DEFAULT_CONTEXT_SIZE, min=8192, max=65536, step=4096, optional=True, advanced=True),
                io.Int.Input("local_max_tokens", display_name="本地生成Token（含思考）", default=DEFAULT_MAX_TOKENS, min=256, max=MAX_OUTPUT_TOKENS, step=1024, optional=True, advanced=True),
                io.Combo.Input("local_think_mode", display_name="本地思考模式", options=LOCAL_THINK_OPTIONS, default=LOCAL_THINK_OFF, optional=True, advanced=True),
                io.Combo.Input("local_reasoning_effort", display_name="本地推理强度", options=LOCAL_REASONING_OPTIONS, default="medium", optional=True, advanced=True),
                io.Combo.Input("local_unload_policy", display_name="本地卸载策略", options=LOCAL_UNLOAD_POLICIES, default=LOCAL_UNLOAD_AFTER_RUN, optional=True, advanced=True),
                io.Combo.Input("local_comfy_memory_policy", display_name="本地显存策略", options=LOCAL_COMFY_MEMORY_POLICIES, default=LOCAL_COMFY_MEMORY_POLICIES[0], optional=True, advanced=True),
                io.String.Input("recovery_slot", optional=True, default="", advanced=True, socketless=True),
                io.String.Input("recovery_action", optional=True, default="normal", advanced=True, socketless=True),
                io.Int.Input("width", display_name="画幅宽度 / width", optional=True, default=0, min=0, max=9007199254740991, force_input=True, lazy=True,
                    tooltip="Connect with height to compute aspect ratio. 0/0 keeps the existing ratio setting."),
                io.Int.Input("height", display_name="画幅高度 / height", optional=True, default=0, min=0, max=9007199254740991, force_input=True, lazy=True,
                    tooltip="Connect with width to compute aspect ratio; neither input changes downstream pixel dimensions."),
            ], outputs=[io.String.Output(display_name="扩写正文 / expanded_prompt"), io.String.Output(display_name="画幅比例 / aspect_ratio"),
                        io.String.Output(display_name="官方结构 / official_json"), io.String.Output(display_name="诊断报告 / report_json")])

    @classmethod
    def validate_inputs(cls, prompt="", task_type=contract.T2I, aspect_ratio="auto", target_words=0,
                        locked_text="", max_corrections=1, recovery_action="normal", width=0, height=0, **kwargs):
        if recovery_action == RECOVERY_ACTION_RESTORE:
            return True
        try:
            actual_task = task_type if task_type is not None else contract.EDIT
            ratio = "auto" if aspect_ratio is None else aspect_ratio
            if width is not None and height is not None:
                ratio, _ = resolve_canvas_ratio(actual_task, ratio, width, height)
            else:
                ratio = "auto"  # linked dimensions are unresolved during graph validation
            contract.validate_controls(task_type if task_type is not None else contract.EDIT,
                ratio, 0 if target_words is None else target_words,
                "" if locked_text is None else locked_text, 1 if max_corrections is None else max_corrections)
            if prompt is not None and (not isinstance(prompt, str) or not prompt.strip()):
                return "brief: Enter a creative/editing brief / 请填写创作或编辑需求。"
            return True
        except (contract.H3ImageContractError, H3ImageError) as error:
            return str(error)

    @classmethod
    def check_lazy_status(cls, prompt=None, reference_images=_MISSING, api_key=_MISSING, provider_config=_MISSING,
                          recovery_action="normal", api_mode=SEEDANCE_API_MODE, width=_MISSING, height=_MISSING, **kwargs):
        if recovery_action == RECOVERY_ACTION_RESTORE:
            return []
        if provider_config is None:
            return ["provider_config"]
        provider = provider_config.get("provider") if isinstance(provider_config, Mapping) else None
        mode = {PROVIDER_LOCAL: LOCAL_QWEN_API_MODE, "Strata": API_MODES[-1], PROVIDER_OPENAI: OPENAI_API_MODE,
                PROVIDER_WORKSHOP: AI_WORKSHOP_API_MODE, PROVIDER_SEEDANCE: SEEDANCE_API_MODE}.get(provider, api_mode)
        needs = ["prompt"] if prompt is None else []
        if width is None: needs.append("width")
        if height is None: needs.append("height")
        if api_key is None and not is_local_qwen_api_mode(mode) and not is_strata_mode(mode):
            needs.append("api_key")
        if reference_images is None:
            needs.append("reference_images")
        for group, prefix in ((kwargs, ""), (reference_images if isinstance(reference_images, Mapping) else {}, "reference_images.")):
            for name, value in group.items():
                if not _IMAGE_KEY.search(name):
                    continue
                if isinstance(value, tuple) and len(value) == 2 and isinstance(value[1], str):
                    if value[0] is None:
                        needs.append(value[1])
                elif value is None:
                    needs.append(name if "." in name else prefix + name)
        return needs

    @classmethod
    def execute(cls, prompt="", task_type=contract.T2I, aspect_ratio="auto", target_words=0,
                api_mode=SEEDANCE_API_MODE, reference_images=None, api_key="", provider_config=None,
                locked_text="", max_corrections=1, llm_max_tokens=16384, ai_workshop_model=AI_WORKSHOP_DEFAULT_MODEL,
                custom_model=DEFAULT_LLM_MODEL, openai_base_url="", seed=0, local_model=DEFAULT_MODEL_FILENAME,
                local_mmproj=AUTO_MMPROJ, local_context_size=DEFAULT_CONTEXT_SIZE, local_max_tokens=DEFAULT_MAX_TOKENS,
                local_think_mode=LOCAL_THINK_OFF, local_reasoning_effort="medium", local_unload_policy=LOCAL_UNLOAD_AFTER_RUN,
                local_comfy_memory_policy=LOCAL_COMFY_MEMORY_POLICIES[0], recovery_slot="", recovery_action="normal", width=0, height=0, **kwargs):
        if recovery_action == RECOVERY_ACTION_RESTORE:
            return _restore(recovery_slot)
        if recovery_action != "normal":
            raise H3ImageError("recovery_action: Invalid action / 恢复动作无效。")
        token = state.begin(recovery_slot)
        counters = {"logical_generation_calls": 0, "chat_post_attempts": 0, "correction_calls": 0}
        diagnostics = DiagnosticsRun(NODE_ID, "generation", 3, emit_progress=False)
        try:
            aspect_ratio, canvas_metadata = resolve_canvas_ratio(task_type, aspect_ratio, width, height)
            contract.validate_controls(task_type, aspect_ratio, target_words, locked_text, max_corrections)
            if not isinstance(prompt, str) or not prompt.strip():
                raise H3ImageError("brief: Enter a creative/editing brief / 请填写创作或编辑需求。")
            media, mapping = image_plan(reference_images, kwargs)
            if task_type == contract.T2I and media:
                raise H3ImageError("t2i_references: Select Image edit when using references / 有参考图请切换到图像编辑。")
            if task_type == contract.EDIT and not media:
                raise H3ImageError("edit_references: Image edit needs at least one image / 图像编辑至少连接一张参考图。")
            controls = {"prompt": prompt, "task_type": task_type, "aspect_ratio": aspect_ratio, "target_words": target_words,
                        "locked_text": locked_text, "max_corrections": max_corrections}
            # Snapshot and input assembly validation happen before any upload or model load.
            contract.build_messages(prompt, task_type, aspect_ratio, target_words, locked_text, mapping)
            current = _resolved_values({"api_mode": api_mode, "api_key": api_key or "", "custom_model": custom_model,
                "ai_workshop_model": ai_workshop_model, "openai_base_url": openai_base_url, "local_model": local_model,
                "local_mmproj": local_mmproj, "local_context_size": local_context_size, "local_max_tokens": local_max_tokens,
                "local_think_mode": local_think_mode, "local_reasoning_effort": local_reasoning_effort,
                "local_unload_policy": local_unload_policy, "local_comfy_memory_policy": local_comfy_memory_policy}, provider_config)
            current["provider_request_options"] = _options(current, llm_max_tokens, controls)
            diagnostics.provider = current["api_mode"]
            diagnostics.advance("inputs_validated", asset_count=len(media))
            result, model, budgets = _generate(current, controls, media, mapping, counters, api_mode=current["api_mode"],
                provider_request_options=current["provider_request_options"], seed=seed)
            caption, ratio, official, details = result
            report = {"schema_version": "t8-h3-image-report/v1", "adapter_revision": contract.REVISION,
                "source_commit": contract.SOURCE_COMMIT, "task_type": task_type, "origin": "current",
                "model_source_commit": contract.MODEL_SOURCE_COMMIT, "source_manifest_sha256": contract.SOURCE_MANIFEST_SHA256,
                "provider_mode": current["api_mode"], "enhancement_model": _provider_label(model),
                "image_map": mapping, **canvas_metadata,
                "input_aspect_ratio_basis": "ComfyUI input tensor before provider resizing",
                "output_budgets": budgets, **counters, **details,
                "image_generation_performed": False, "semantics_verified": False,
                "downstream_token_check": {"limit": 4096, "measured": None, "status": "unverified"},
                "recovery_cache": "optional_process_local_1h_shared_50_slots_250000_chars", "recovery_saved": bool(recovery_slot)}
            outputs = caption, ratio, official, json.dumps(report, ensure_ascii=False)
            interrupted()
            if not state.commit(recovery_slot, token, outputs):
                report["recovery_saved"] = False
                report["recovery_unavailable_reason"] = "no_slot" if not recovery_slot else "oversize_or_superseded"
                outputs = caption, ratio, official, json.dumps(report, ensure_ascii=False)
            diagnostics.advance("validated", attempts=counters["logical_generation_calls"])
            diagnostics.complete("success")
            return io.NodeOutput(*outputs)
        except BaseException as error:
            diagnostics.complete("error", error)
            if isinstance(error, contract.H3ImageContractError):
                raise H3ImageError(f"{error.code}: {error} (calls={counters['logical_generation_calls']}, corrections={counters['correction_calls']})") from None
            raise
