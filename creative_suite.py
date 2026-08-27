from __future__ import annotations

import difflib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import requests
from comfy_api.latest import io

try:
    from . import nodes as h3
    from .case_templates import CASE_TEMPLATE_OPTIONS, NO_CASE_TEMPLATE, get_case_template
    from .local_qwen_provider import (
        DEFAULT_CONTEXT_SIZE,
        DEFAULT_MAX_TOKENS,
        DEFAULT_VIDEO_SAMPLE_FPS,
        LOCAL_QWEN_API_MODE,
        LocalQwenProvider,
        LocalQwenProviderError,
        build_local_multimodal_parts,
        is_local_qwen_api_mode,
        local_visual_part_budget,
        settings_from_values as local_qwen_settings,
    )
    from .local_qwen_runtime import (
        DEFAULT_MMPROJ_FILENAME,
        DEFAULT_MODEL_FILENAME,
        LOCAL_COMFY_MEMORY_POLICIES,
        LOCAL_THINK_OFF,
        LOCAL_UNLOAD_AFTER_RUN,
    )
    from .provider_config import (
        PROVIDER_LOCAL,
        PROVIDER_OPENAI,
        PROVIDER_SEEDANCE,
        PROVIDER_WORKSHOP,
        ProviderConfigError,
        T8ProviderConfigIO,
        merge_provider_config,
    )
except ImportError:
    import nodes as h3
    from case_templates import CASE_TEMPLATE_OPTIONS, NO_CASE_TEMPLATE, get_case_template
    from local_qwen_provider import (
        DEFAULT_CONTEXT_SIZE,
        DEFAULT_MAX_TOKENS,
        DEFAULT_VIDEO_SAMPLE_FPS,
        LOCAL_QWEN_API_MODE,
        LocalQwenProvider,
        LocalQwenProviderError,
        build_local_multimodal_parts,
        is_local_qwen_api_mode,
        local_visual_part_budget,
        settings_from_values as local_qwen_settings,
    )
    from local_qwen_runtime import (
        DEFAULT_MMPROJ_FILENAME,
        DEFAULT_MODEL_FILENAME,
        LOCAL_COMFY_MEMORY_POLICIES,
        LOCAL_THINK_OFF,
        LOCAL_UNLOAD_AFTER_RUN,
    )
    from provider_config import (
        PROVIDER_LOCAL,
        PROVIDER_OPENAI,
        PROVIDER_SEEDANCE,
        PROVIDER_WORKSHOP,
        ProviderConfigError,
        T8ProviderConfigIO,
        merge_provider_config,
    )


CREATIVE_SUITE_SCHEMA = "t8-creative-suite/v1"
BRIEF_SCHEMA = "t8-creative-brief/v1"
REFERENCE_MAP_SCHEMA = "t8-reference-role-map/v1"
DNA_MIX_SCHEMA = "t8-creative-dna-mix/v1"
PERSONAL_PRESET_SCHEMA = "t8-personal-creative-preset/v1"
BEAT_SHEET_SCHEMA = "t8-music-video-beat-sheet/v1"

T8CreativeBriefIO = io.Custom("T8_CREATIVE_BRIEF")
T8ReferenceRoleMapIO = io.Custom("T8_REFERENCE_ROLE_MAP")
T8CreativeDNAMixIO = io.Custom("T8_CREATIVE_DNA_MIX")
T8PersonalPresetIO = io.Custom("T8_PERSONAL_CREATIVE_PRESET")
T8BeatSheetIO = io.Custom("T8_MUSIC_VIDEO_BEAT_SHEET")

POLICIES = ["LOCK（锁定）", "EVOLVE（允许演化）", "AUTO（下游判断）"]
LOCK_POLICY = POLICIES[0]
EVOLVE_POLICY = POLICIES[1]
AUTO_POLICY = POLICIES[2]
OUTPUT_LANGUAGES = ["中文", "English"]
MODEL_TARGETS = ["MiniMax H3", "Seedance 2.0", "MiniMax H3 + Seedance 2.0"]
REWRITE_MODES = ["strict", "balanced", "creative"]
CREATIVE_SUITE_SEEDANCE_RETRY_DELAYS = (0.5, 1.0, 2.0, 4.0, 8.0)
CANDIDATE_COUNTS = ["2", "3", "4"]
SHOT_COUNT_OPTIONS = ["AUTO（根据时长与内容）"] + [str(value) for value in range(1, 21)]
DNA_ROLES = ("structure", "camera", "payoff")
SECRET_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", flags=re.IGNORECASE)
SECTION_TAG_RE = re.compile(r"\[[^\]\r\n]{1,80}\]")


class CreativeSuiteError(RuntimeError):
    pass


@dataclass(frozen=True)
class CompletionResult:
    text: str
    provider: str


def _clean_text(value: Any, *, limit: int = 100_000) -> str:
    text = str(value or "").strip()
    if SECRET_RE.search(text):
        raise CreativeSuiteError("Remove the API-key-like secret from creative text and use the API Key input instead.")
    return text[:limit]


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _extract_json(text: str) -> Any | None:
    candidate = FENCE_RE.sub("", str(text or "").strip())
    try:
        return json.loads(candidate)
    except (TypeError, json.JSONDecodeError):
        pass
    decoder = json.JSONDecoder()
    for index, character in enumerate(candidate):
        if character not in "[{":
            continue
        try:
            value, _end = decoder.raw_decode(candidate[index:])
            return value
        except json.JSONDecodeError:
            continue
    return None


def _coerce_mapping(value: Any, schema: str | None = None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    result = dict(value)
    if schema and result.get("schema_version") != schema:
        return {}
    return result


def _brief_context(value: Any) -> str:
    brief = _coerce_mapping(value, BRIEF_SCHEMA)
    if not brief:
        return "No shared creative brief is connected."
    return _json_text(brief)


def _provider_defaults(api_key: str) -> dict[str, Any]:
    return {
        "api_key": str(api_key or "").strip(),
        "api_mode": h3.SEEDANCE_API_MODE,
        "openai_base_url": "",
        "ai_workshop_model": h3.AI_WORKSHOP_DEFAULT_MODEL,
        "custom_model": "",
        "local_model": DEFAULT_MODEL_FILENAME,
        "local_mmproj": DEFAULT_MMPROJ_FILENAME,
        "local_context_size": DEFAULT_CONTEXT_SIZE,
        "local_max_tokens": DEFAULT_MAX_TOKENS,
        "local_think_mode": LOCAL_THINK_OFF,
        "local_reasoning_effort": "medium",
        "local_video_sample_fps": DEFAULT_VIDEO_SAMPLE_FPS,
        "local_unload_policy": LOCAL_UNLOAD_AFTER_RUN,
        "local_comfy_memory_policy": LOCAL_COMFY_MEMORY_POLICIES[0],
    }


def _resolve_provider(api_key: str, provider_config: Any) -> dict[str, Any]:
    try:
        return merge_provider_config(
            _provider_defaults(api_key),
            provider_config,
            api_mode_map={
                PROVIDER_SEEDANCE: h3.SEEDANCE_API_MODE,
                PROVIDER_WORKSHOP: h3.AI_WORKSHOP_API_MODE,
                PROVIDER_OPENAI: h3.OPENAI_API_MODE,
                PROVIDER_LOCAL: LOCAL_QWEN_API_MODE,
            },
        )
    except ProviderConfigError as error:
        raise CreativeSuiteError(str(error)) from error


def _messages(system: str, user: str, media_parts: Sequence[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    content: str | list[dict[str, Any]]
    if media_parts:
        content = [{"type": "text", "text": user}, *media_parts]
    else:
        content = user
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": content},
    ]


def _run_completion(
    *,
    system: str,
    user: str,
    api_key: str,
    provider_config: Any,
    rewrite_mode: str,
    seed: int,
    media_plan: list[dict[str, Any]] | None = None,
    session: requests.Session | None = None,
    max_output_tokens: int = 3072,
) -> CompletionResult:
    if rewrite_mode not in REWRITE_MODES:
        raise CreativeSuiteError(f"Unsupported rewrite mode: {rewrite_mode}")
    values = _resolve_provider(api_key, provider_config)
    api_mode = values["api_mode"]
    media_plan = list(media_plan or [])

    if is_local_qwen_api_mode(api_mode):
        try:
            settings = local_qwen_settings(
                local_model=values["local_model"],
                local_mmproj=values["local_mmproj"],
                local_context_size=values["local_context_size"],
                local_max_tokens=values["local_max_tokens"],
                local_think_mode=values["local_think_mode"],
                local_reasoning_effort=values["local_reasoning_effort"],
                local_video_sample_fps=values["local_video_sample_fps"],
                local_unload_policy=values["local_unload_policy"],
                local_comfy_memory_policy=values["local_comfy_memory_policy"],
            )
            text_messages = _messages(system, user)
            media_parts: list[dict[str, Any]] = []
            if media_plan:
                budget = local_visual_part_budget(text_messages, settings)
                media_parts, _report = build_local_multimodal_parts(
                    media_plan,
                    settings,
                    max_visual_parts=budget,
                )
                system += (
                    "\n\nLocal video evidence boundary: videos are ordered timestamped visual samples only. "
                    "Never claim exhaustive frame coverage, audio access, speech transcription, music recognition, or BPM detection."
                )
            with LocalQwenProvider(settings, vision=bool(media_plan)) as provider:
                text = provider.complete(
                    _messages(system, user, media_parts),
                    temperature=h3.MODE_TEMPERATURES[rewrite_mode],
                    seed=int(seed),
                )
            return CompletionResult(text=text, provider="Local llama.cpp GGUF")
        except LocalQwenProviderError as error:
            raise CreativeSuiteError(str(error)) from error

    key, chat_url, upload_url, provider_name = h3._provider_config(
        api_mode,
        values["api_key"],
        values["openai_base_url"],
    )
    model_id = h3._resolve_llm_model(api_mode, values["ai_workshop_model"], values["custom_model"])
    owns_session = session is None
    session = session or requests.Session()
    try:
        if media_plan and api_mode == h3.AI_WORKSHOP_API_MODE:
            media_parts = h3._inline_media_plan(media_plan)
        elif media_plan and api_mode == h3.OPENAI_API_MODE:
            media_parts = h3._openai_media_plan(media_plan, "")
        elif media_plan:
            media_parts = h3._upload_media_plan(session, key, media_plan, upload_url, provider_name)
        else:
            media_parts = []
        request_options = dict(values.get("provider_request_options") or {})
        extra_parameters = dict(request_options.get("extra_parameters") or {})
        # The limit is real-API-verified for Seedance NZ. Unknown compatible
        # providers retain their existing payload unless the user explicitly
        # configures max_tokens/max_completion_tokens in the shared config.
        if (
            api_mode == h3.SEEDANCE_API_MODE
            and "max_tokens" not in extra_parameters
            and "max_completion_tokens" not in extra_parameters
        ):
            extra_parameters["max_tokens"] = max(256, min(int(max_output_tokens), 8192))
        if extra_parameters:
            request_options["extra_parameters"] = extra_parameters
        text = h3._request_completion(
            session,
            key,
            _messages(system, user, media_parts),
            rewrite_mode,
            chat_url,
            provider_name,
            model_id,
            provider_request_options=request_options,
            retry_delays=(
                CREATIVE_SUITE_SEEDANCE_RETRY_DELAYS
                if api_mode == h3.SEEDANCE_API_MODE
                else None
            ),
        )
        return CompletionResult(text=text, provider=provider_name)
    except h3.PromptEnhancerError as error:
        raise CreativeSuiteError(str(error)) from error
    finally:
        if owns_session:
            session.close()


def _provider_inputs() -> list[Any]:
    return [
        io.String.Input(
            "api_key",
            display_name="LLM API Key（默认 Seedance NZ）",
            optional=True,
            default="",
            force_input=True,
            tooltip="可接 STRING。连接共享渠道配置后按共享配置选择 Seedance NZ、AI 工坊、OpenAI Compatible 或 Local Qwen。",
        ),
        T8ProviderConfigIO.Input(
            "provider_config",
            display_name="共享 LLM 渠道配置（可选）",
            optional=True,
        ),
        io.Int.Input(
            "seed",
            display_name="随机种子",
            default=0,
            min=0,
            max=0xFFFFFFFFFFFFFFFF,
            control_after_generate=True,
        ),
    ]


def build_creative_brief(**values: Any) -> tuple[dict[str, Any], str]:
    premise = _clean_text(values.get("premise"))
    if not premise:
        raise CreativeSuiteError("创作核心不能为空。")
    dimensions = []
    specs = (
        ("audience_and_use", "受众与用途", "audience_policy"),
        ("narrative_arc", "叙事与情绪曲线", "narrative_policy"),
        ("character_identity", "人物身份与连续性", "identity_policy"),
        ("world_and_space", "世界、场景与空间", "world_policy"),
        ("visual_language", "色彩、材质、灯光与镜头", "visual_policy"),
        ("motion_and_editing", "动作、运镜与剪辑语法", "motion_policy"),
        ("sound_and_music", "声音、对白与音乐", "sound_policy"),
    )
    for key, label, policy_key in specs:
        text = _clean_text(values.get(key))
        policy = str(values.get(policy_key) or AUTO_POLICY)
        if policy not in POLICIES:
            raise CreativeSuiteError(f"Unsupported policy for {label}: {policy}")
        dimensions.append({"id": key, "label": label, "policy": policy.split("（", 1)[0], "content": text})
    brief = {
        "schema_version": BRIEF_SCHEMA,
        "premise": premise,
        "dimensions": dimensions,
        "exclusions": _clean_text(values.get("exclusions")),
        "evolution_permissions": _clean_text(values.get("evolution_permissions")),
        "notes": "LOCK outranks EVOLVE and AUTO. Explicit user facts and connected media remain authoritative.",
    }
    lines = ["T8 创作总纲", f"创作核心：{premise}"]
    for dimension in dimensions:
        if dimension["content"] or dimension["policy"] == "LOCK":
            lines.append(f"[{dimension['policy']}] {dimension['label']}：{dimension['content'] or '不得由下游擅自补充'}")
    if brief["exclusions"]:
        lines.append(f"禁止项：{brief['exclusions']}")
    if brief["evolution_permissions"]:
        lines.append(f"允许演化范围：{brief['evolution_permissions']}")
    return brief, "\n".join(lines)


class T8CreativeDirector(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        policy = lambda name, label, default=AUTO_POLICY: io.Combo.Input(
            name, display_name=label, options=POLICIES, default=default, advanced=True
        )
        text = lambda name, label: io.String.Input(
            name, display_name=label, optional=True, multiline=True, default=""
        )
        return io.Schema(
            node_id="T8CreativeDirector",
            display_name="T8 Creative Director（创作总控）",
            category="T8/Creative Suite",
            description="纯本地整理统一创作总纲，不调用 LLM；供视频、音乐和其他创作辅助节点共同使用。",
            inputs=[
                io.String.Input("premise", display_name="创作核心（必填）", multiline=True, dynamic_prompts=True, default=""),
                text("audience_and_use", "受众与用途"),
                policy("audience_policy", "受众策略"),
                text("narrative_arc", "叙事与情绪曲线"),
                policy("narrative_policy", "叙事策略"),
                text("character_identity", "人物身份与连续性"),
                policy("identity_policy", "人物策略", LOCK_POLICY),
                text("world_and_space", "世界、场景与空间"),
                policy("world_policy", "世界策略"),
                text("visual_language", "色彩、材质、灯光与镜头"),
                policy("visual_policy", "视觉策略"),
                text("motion_and_editing", "动作、运镜与剪辑语法"),
                policy("motion_policy", "动作/剪辑策略"),
                text("sound_and_music", "声音、对白与音乐"),
                policy("sound_policy", "声音策略"),
                text("exclusions", "禁止项"),
                text("evolution_permissions", "允许演化范围"),
            ],
            outputs=[
                T8CreativeBriefIO.Output(display_name="creative_brief"),
                io.String.Output(display_name="creative_brief_text"),
                io.String.Output(display_name="creative_brief_json"),
            ],
        )

    @classmethod
    def execute(cls, **kwargs: Any) -> io.NodeOutput:
        brief, text = build_creative_brief(**kwargs)
        return io.NodeOutput(brief, text, _json_text(brief))


class T8CreativeContextAssembler(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8CreativeContextAssembler",
            display_name="T8 Creative Context Assembler（创作上下文组装）",
            category="T8/Creative Suite",
            description="纯本地组装创作总纲、素材角色、案例 DNA 和个人预设，输出可接现有核心节点的 STRING。",
            inputs=[
                T8CreativeBriefIO.Input("creative_brief", display_name="创作总纲（可选）", optional=True),
                T8ReferenceRoleMapIO.Input("reference_role_map", display_name="素材角色表（可选）", optional=True),
                T8CreativeDNAMixIO.Input("creative_dna_mix", display_name="Creative DNA 融合（可选）", optional=True),
                T8PersonalPresetIO.Input("personal_preset", display_name="个人预设（可选）", optional=True),
                io.String.Input("extra_constraints", display_name="补充硬性要求", optional=True, multiline=True, default=""),
            ],
            outputs=[
                io.String.Output(display_name="enhancer_context"),
                io.String.Output(display_name="assembled_context_json"),
            ],
        )

    @classmethod
    def execute(
        cls,
        creative_brief=None,
        reference_role_map=None,
        creative_dna_mix=None,
        personal_preset=None,
        extra_constraints="",
    ) -> io.NodeOutput:
        parts = []
        payload = {"schema_version": CREATIVE_SUITE_SCHEMA, "operation": "context_assembly"}
        for key, value, schema in (
            ("creative_brief", creative_brief, BRIEF_SCHEMA),
            ("reference_role_map", reference_role_map, REFERENCE_MAP_SCHEMA),
            ("creative_dna_mix", creative_dna_mix, DNA_MIX_SCHEMA),
            ("personal_preset", personal_preset, PERSONAL_PRESET_SCHEMA),
        ):
            normalized = _coerce_mapping(value, schema)
            if normalized:
                payload[key] = normalized
                parts.append(f"[{key}]\n{_json_text(normalized)}")
        extra = _clean_text(extra_constraints)
        if extra:
            payload["extra_constraints"] = extra
            parts.append(f"[extra_constraints]\n{extra}")
        if not parts:
            raise CreativeSuiteError("至少连接一项创作上下文或填写补充硬性要求。")
        parts.append(
            "Precedence: explicit current user facts and connected media > LOCK fields > hard constraints > "
            "selected T8/user creative mechanisms > EVOLVE > AUTO. Human previews are never model references."
        )
        return io.NodeOutput("\n\n".join(parts), _json_text(payload))


def _locked_anchor_warnings(anchors: str, revised: str) -> list[str]:
    warnings = []
    for line in (item.strip(" -\t") for item in anchors.splitlines()):
        if len(line) >= 4 and line not in revised:
            warnings.append(f"锁定锚点未逐字出现，请人工确认语义是否保留：{line[:80]}")
    return warnings


class T8DirectedRevision(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8DirectedRevision",
            display_name="T8 Directed Revision（定向修改）",
            category="T8/Creative Suite",
            description="只修改用户点名的范围，保留创作总纲与锁定锚点；一次 LLM 请求，差异报告在本地生成。",
            inputs=[
                io.String.Input("original_prompt", display_name="原提示词（必填）", multiline=True, dynamic_prompts=True, default=""),
                io.String.Input("revision_request", display_name="修改要求（必填）", multiline=True, dynamic_prompts=True, default=""),
                io.String.Input("locked_anchors", display_name="必须保留（每行一项）", optional=True, multiline=True, default=""),
                T8CreativeBriefIO.Input("creative_brief", display_name="创作总纲（可选）", optional=True),
                io.Combo.Input("rewrite_mode", display_name="修改幅度", options=REWRITE_MODES, default="balanced"),
                io.Combo.Input("output_language", display_name="报告语言", options=OUTPUT_LANGUAGES, default="中文"),
                *_provider_inputs(),
            ],
            outputs=[
                io.String.Output(display_name="revised_prompt"),
                io.String.Output(display_name="revision_report_json"),
                io.String.Output(display_name="unified_diff"),
            ],
        )

    @classmethod
    def execute(
        cls,
        original_prompt,
        revision_request,
        locked_anchors="",
        creative_brief=None,
        rewrite_mode="balanced",
        output_language="中文",
        api_key="",
        provider_config=None,
        seed=0,
    ) -> io.NodeOutput:
        original = _clean_text(original_prompt)
        request = _clean_text(revision_request)
        anchors = _clean_text(locked_anchors)
        if not original or not request:
            raise CreativeSuiteError("原提示词和修改要求都不能为空。")
        system = """You are a surgical creative editor. Modify only the scope explicitly requested by the user.
Preserve every locked anchor, unmentioned identity, costume, prop, dialogue, lyric, visible text, reference label, timing fact, ending state, and model-native field. The connected creative brief has higher priority than stylistic enrichment. Never restart from scratch or silently broaden the change.
Return one JSON object with revised_prompt, change_summary (array), preserved_anchors (array), and warnings (array). Do not use Markdown fences."""
        user = "\n".join([
            f"Report language: {output_language}",
            f"Rewrite mode: {rewrite_mode}",
            "Creative brief:", _brief_context(creative_brief),
            "Locked anchors:", anchors or "None beyond unchanged content.",
            "Original prompt:", original,
            "Requested delta:", request,
        ])
        result = _run_completion(
            system=system,
            user=user,
            api_key=api_key,
            provider_config=provider_config,
            rewrite_mode=rewrite_mode,
            seed=seed,
            max_output_tokens=2048,
        )
        parsed = _extract_json(result.text)
        data = parsed if isinstance(parsed, Mapping) else {}
        revised = str(data.get("revised_prompt") or result.text).strip()
        if not revised:
            raise CreativeSuiteError("LLM returned no revised prompt.")
        warnings = [str(item) for item in data.get("warnings", [])] if isinstance(data.get("warnings"), list) else []
        warnings.extend(_locked_anchor_warnings(anchors, revised))
        report = {
            "schema_version": CREATIVE_SUITE_SCHEMA,
            "operation": "directed_revision",
            "provider": result.provider,
            "structured_response": bool(data),
            "change_summary": data.get("change_summary", []),
            "preserved_anchors": data.get("preserved_anchors", []),
            "warnings": warnings,
        }
        diff = "\n".join(difflib.unified_diff(
            original.splitlines(), revised.splitlines(), fromfile="original", tofile="revised", lineterm=""
        ))
        return io.NodeOutput(revised, _json_text(report), diff)


def _segment_schedule(total_seconds: int, target_seconds: int) -> list[dict[str, Any]]:
    total = int(total_seconds)
    target = int(target_seconds)
    if total < 1 or target < 1:
        raise CreativeSuiteError("总时长和目标分段时长必须是正整数。")
    count = max(1, math.ceil(total / target))
    schedule = []
    start = 0
    for index in range(1, count + 1):
        end = min(total, start + target)
        schedule.append({
            "segment_index": index,
            "start_seconds": start,
            "end_seconds": end,
            "duration_seconds": end - start,
        })
        start = end
    return schedule


def _normalize_plan_response(
    text: str,
    schedule: list[dict[str, Any]],
    model_target: str,
    provider: str,
) -> tuple[str, str, str, str]:
    parsed = _extract_json(text)
    data = dict(parsed) if isinstance(parsed, Mapping) else {}
    raw_segments = data.get("segments") if isinstance(data.get("segments"), list) else []
    by_index = {
        int(item.get("segment_index")): item
        for item in raw_segments
        if isinstance(item, Mapping) and str(item.get("segment_index", "")).isdigit()
    }
    normalized = []
    for timing in schedule:
        source = dict(by_index.get(timing["segment_index"], {}))
        normalized.append({
            **timing,
            "start_state": str(source.get("start_state") or ""),
            "end_state": str(source.get("end_state") or ""),
            "continuity_anchors": source.get("continuity_anchors", []),
            "media_bindings": source.get("media_bindings", []),
            "h3_prompt": str(source.get("h3_prompt") or ""),
            "seedance20_prompt": str(source.get("seedance20_prompt") or ""),
        })
    report = {
        "schema_version": CREATIVE_SUITE_SCHEMA,
        "operation": "long_form_planning",
        "provider": provider,
        "structured_response": bool(data),
        "model_target": model_target,
        "schedule": schedule,
        "unparsed_response": "" if data else text,
    }
    global_brief = str(data.get("global_continuity_brief") or text).strip()
    h3_payload = {
        **report,
        "segments": [
            {key: value for key, value in item.items() if key != "seedance20_prompt"}
            for item in normalized
        ] if "MiniMax H3" in model_target else [],
    }
    seedance_payload = {
        **report,
        "segments": [
            {key: value for key, value in item.items() if key != "h3_prompt"}
            for item in normalized
        ] if "Seedance 2.0" in model_target else [],
    }
    handoffs = data.get("handoffs") if isinstance(data.get("handoffs"), list) else []
    return global_brief, _json_text(h3_payload), _json_text(seedance_payload), _json_text({
        **report,
        "handoffs": handoffs,
    })


class T8LongFormPlanner(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8LongFormPlanner",
            display_name="T8 Long-form Planner（长视频分段导演）",
            category="T8/Creative Suite",
            description="把任意正整数总时长拆成连续片段，输出模型独立提示词和段间交接；不生成或拼接视频。",
            inputs=[
                io.String.Input("concept", display_name="全片创意 / 剧本（必填）", multiline=True, dynamic_prompts=True, default=""),
                T8CreativeBriefIO.Input("creative_brief", display_name="创作总纲（可选）", optional=True),
                io.Combo.Input("model_target", display_name="目标模型", options=MODEL_TARGETS, default=MODEL_TARGETS[2]),
                io.Int.Input("total_duration_seconds", display_name="全片总时长（秒）", default=60, min=1, step=1),
                io.Int.Input("segment_duration_seconds", display_name="目标单段时长（秒）", default=15, min=1, step=1),
                io.String.Input("continuity_anchors", display_name="连续性锚点", optional=True, multiline=True, default=""),
                io.Combo.Input(
                    "transition_policy",
                    display_name="段间交接策略",
                    options=["状态连续（推荐）", "匹配剪辑", "声音桥接", "允许章节跳转"],
                    default="状态连续（推荐）",
                ),
                io.Combo.Input("rewrite_mode", display_name="创作幅度", options=REWRITE_MODES, default="balanced"),
                io.Combo.Input("output_language", display_name="输出语言", options=OUTPUT_LANGUAGES, default="中文"),
                *_provider_inputs(),
            ],
            outputs=[
                io.String.Output(display_name="global_continuity_brief"),
                io.String.Output(display_name="h3_segments_json"),
                io.String.Output(display_name="seedance20_segments_json"),
                io.String.Output(display_name="handoff_table_json"),
            ],
        )

    @classmethod
    def execute(
        cls,
        concept,
        creative_brief=None,
        model_target=MODEL_TARGETS[2],
        total_duration_seconds=60,
        segment_duration_seconds=15,
        continuity_anchors="",
        transition_policy="状态连续（推荐）",
        rewrite_mode="balanced",
        output_language="中文",
        api_key="",
        provider_config=None,
        seed=0,
    ) -> io.NodeOutput:
        concept = _clean_text(concept)
        anchors = _clean_text(continuity_anchors)
        if not concept:
            raise CreativeSuiteError("全片创意 / 剧本不能为空。")
        if model_target not in MODEL_TARGETS:
            raise CreativeSuiteError(f"Unsupported model_target: {model_target}")
        schedule = _segment_schedule(total_duration_seconds, segment_duration_seconds)
        system = """You are a long-form audiovisual continuity director. Plan multiple independently generatable video segments without claiming to render, stitch, edit, or hear media.
For every segment preserve identity, costume, props, spatial direction, lighting, action state, dialogue/visible text, and sound handoffs. MiniMax H3 and Seedance 2.0 prompts must be separate native variants; never chain one model's final prompt into the other.
H3 variants use concrete shot timing, visual action, camera, dialogue/sound, overall soundscape and non-diegetic music appropriate to the selected H3 mode. Seedance variants use natural model-ready Chinese or English, @素材N references only when supplied, explicit temporal order, controllable action and continuity without fabricated frame-accurate certainty. Keep every native segment prompt concise (at most 360 Chinese characters or 220 English words) while retaining its full executable event chain.
Return one JSON object with global_continuity_brief, segments, and handoffs. Each segment must contain segment_index, start_state, end_state, continuity_anchors, media_bindings, h3_prompt, seedance20_prompt. Do not use Markdown fences."""
        user = "\n".join([
            f"Output language: {output_language}",
            f"Model target: {model_target}",
            f"Transition policy: {transition_policy}",
            f"Total duration: {int(total_duration_seconds)} seconds",
            "Authoritative deterministic segment schedule:", _json_text(schedule),
            "Shared creative brief:", _brief_context(creative_brief),
            "Additional continuity anchors:", anchors or "None.",
            "Whole-film concept/script:", concept,
        ])
        result = _run_completion(
            system=system,
            user=user,
            api_key=api_key,
            provider_config=provider_config,
            rewrite_mode=rewrite_mode,
            seed=seed,
            max_output_tokens=4096,
        )
        return io.NodeOutput(*_normalize_plan_response(result.text, schedule, model_target, result.provider))


def _build_reference_media(
    reference_images: Mapping[str, Any] | None,
    reference_videos: Mapping[str, Any] | None,
    *,
    allow_trimmed_video: bool,
) -> list[dict[str, Any]]:
    media_plan: list[dict[str, Any]] = []
    picture_index = 0
    for image in h3._ordered_values(dict(reference_images or {})):
        count = h3._image_count(image)
        for batch_index in range(count):
            picture_index += 1
            if picture_index > 9:
                raise CreativeSuiteError("参考角色映射最多支持 9 张图片。")
            media_plan.append({
                "kind": "image",
                "label": f"<Picture {picture_index}>",
                "value": h3._image_at(image, batch_index),
            })
    for video_index, video in enumerate(h3._ordered_values(dict(reference_videos or {})), 1):
        if video_index > 3:
            raise CreativeSuiteError("参考角色映射最多支持 3 个视频。")
        try:
            h3._validate_video_source(video, allow_trim=allow_trimmed_video)
        except h3.PromptEnhancerError as error:
            raise CreativeSuiteError(str(error)) from error
        media_plan.append({"kind": "video", "label": f"<Video {video_index}>", "value": video})
    return media_plan


class T8ReferenceRoleMapper(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8ReferenceRoleMapper",
            display_name="T8 Reference Role Mapper（多素材角色导演）",
            category="T8/Creative Suite",
            description="分析用户实际连接的图片/视频并分配引用职责；不会读取或发送案例预览 GIF。",
            inputs=[
                io.String.Input("project_intent", display_name="创作意图（必填）", multiline=True, dynamic_prompts=True, default=""),
                io.String.Input("asset_notes", display_name="素材说明 / 禁止借用项", optional=True, multiline=True, default=""),
                io.Autogrow.Input(
                    "reference_images",
                    optional=True,
                    template=io.Autogrow.TemplatePrefix(
                        input=io.Image.Input("reference_image"), prefix="reference_image_", min=0, max=9
                    ),
                ),
                io.Autogrow.Input(
                    "reference_videos",
                    optional=True,
                    template=io.Autogrow.TemplatePrefix(
                        input=io.Video.Input("reference_video"), prefix="reference_video_", min=0, max=3
                    ),
                ),
                T8CreativeBriefIO.Input("creative_brief", display_name="创作总纲（可选）", optional=True),
                io.Combo.Input("rewrite_mode", display_name="分析幅度", options=REWRITE_MODES, default="balanced"),
                io.Combo.Input("output_language", display_name="输出语言", options=OUTPUT_LANGUAGES, default="中文"),
                *_provider_inputs(),
            ],
            outputs=[
                T8ReferenceRoleMapIO.Output(display_name="reference_role_map"),
                io.String.Output(display_name="reference_role_map_json"),
                io.String.Output(display_name="coverage_conflict_report"),
                io.String.Output(display_name="reference_context_for_enhancer"),
            ],
        )

    @classmethod
    def validate_inputs(cls, reference_images=None, reference_videos=None) -> bool:
        del reference_images, reference_videos
        return True

    @classmethod
    def execute(
        cls,
        project_intent,
        asset_notes="",
        reference_images=None,
        reference_videos=None,
        creative_brief=None,
        rewrite_mode="balanced",
        output_language="中文",
        api_key="",
        provider_config=None,
        seed=0,
    ) -> io.NodeOutput:
        intent = _clean_text(project_intent)
        notes = _clean_text(asset_notes)
        if not intent:
            raise CreativeSuiteError("创作意图不能为空。")
        provider_values = _resolve_provider(api_key, provider_config)
        media_plan = _build_reference_media(
            reference_images,
            reference_videos,
            allow_trimmed_video=is_local_qwen_api_mode(provider_values["api_mode"]),
        )
        if not media_plan and not notes:
            raise CreativeSuiteError("请至少连接一项参考素材，或填写素材说明。")
        labels = [asset["label"] for asset in media_plan]
        system = """You are a multimodal reference-role director. Analyze only user-connected media and explicit notes. Never infer or attach human-preview GIFs, case-source videos, or unavailable assets.
For each label assign only supported roles from: identity, body_proportion, costume, prop, environment, action, camera, composition, style, palette, lighting, timing, audio_reference, and must_not_borrow. Separate identity from style transfer. Record conflicts when two assets imply incompatible identity, costume, geometry, chronology, or visual direction. Record coverage gaps without inventing evidence.
Return one compact JSON object with assets (label, observations, roles, priority, shot_bindings, must_not_borrow), conflicts, coverage_gaps, and enhancer_reference_context. Keep observations and reports concise and evidence-bound. Do not use Markdown fences."""
        user = "\n".join([
            f"Output language: {output_language}",
            f"Connected labels: {', '.join(labels) or 'none; notes only'}",
            "Creative brief:", _brief_context(creative_brief),
            "Project intent:", intent,
            "User asset notes and prohibitions:", notes or "None.",
        ])
        result = _run_completion(
            system=system,
            user=user,
            api_key=api_key,
            provider_config=provider_config,
            rewrite_mode=rewrite_mode,
            seed=seed,
            media_plan=media_plan,
            max_output_tokens=2048,
        )
        parsed = _extract_json(result.text)
        data = dict(parsed) if isinstance(parsed, Mapping) else {
            "assets": [], "conflicts": [], "coverage_gaps": [],
            "enhancer_reference_context": result.text,
        }
        payload = {
            "schema_version": REFERENCE_MAP_SCHEMA,
            "provider": result.provider,
            "connected_labels": labels,
            "structured_response": isinstance(parsed, Mapping),
            **data,
        }
        report = {
            "conflicts": payload.get("conflicts", []),
            "coverage_gaps": payload.get("coverage_gaps", []),
            "evidence_boundary": (
                "Local videos were represented by timestamped visual samples; audio was not analyzed."
                if is_local_qwen_api_mode(provider_values["api_mode"]) and any(item["kind"] == "video" for item in media_plan)
                else "Only explicitly connected user media and notes were used."
            ),
        }
        context = str(payload.get("enhancer_reference_context") or result.text).strip()
        return io.NodeOutput(payload, _json_text(payload), _json_text(report), context)


def _local_candidate_scores(prompt: str) -> dict[str, int]:
    """Deterministic advisory heuristics; never an objective quality claim or gate."""
    text = str(prompt or "")
    lowered = text.lower()
    length = len(text)
    causal_hits = len(re.findall(r"因此|于是|随后|触发|导致|because|therefore|then|causes?", lowered))
    control_hits = len(re.findall(r"镜头|特写|跟拍|推近|拉远|秒|shot|camera|close-up|dolly|pan", lowered))
    continuity_hits = len(re.findall(r"保持|同一|连续|一致|锁定|preserve|same|consistent|continuity", lowered))
    media_hits = len(re.findall(r"@(?:图片|视频|image|video)|<picture|<video", lowered))
    risk_hits = len(re.findall(r"核爆|毁天灭地|海量|数百|复杂变形|瞬间切换|nuclear|hundreds|massive crowd", lowered))
    mechanism_hits = len(set(re.findall(
        r"匹配剪辑|空间变形|视觉证据|动作因果|节奏蒙太奇|一镜到底|子弹时间|match cut|transformation|montage|proof|one-take",
        lowered,
    )))
    return {
        "originality": min(10, 5 + mechanism_hits),
        "causality": min(10, 4 + causal_hits * 2),
        "controllability": min(10, 4 + control_hits),
        "continuity": min(10, 4 + continuity_hits * 2),
        "media_usage": min(10, 5 + media_hits * 2) if media_hits else 5,
        "temporal_feasibility": max(2, 10 - max(0, length - 900) // 180),
        "production_risk": min(10, 2 + risk_hits * 2),
    }


def _normalize_candidates(text: str, count: int, provider: str) -> tuple[dict[str, Any], list[str]]:
    parsed = _extract_json(text)
    data = dict(parsed) if isinstance(parsed, Mapping) else {}
    candidates = data.get("candidates") if isinstance(data.get("candidates"), list) else []
    normalized = []
    for index, item in enumerate(candidates[:count], 1):
        if isinstance(item, Mapping):
            prompt = str(item.get("prompt") or item.get("concept") or item.get("output") or "").strip()
            normalized.append({
                "candidate_index": index,
                "name": str(item.get("name") or f"方向 {index}"),
                "creative_axis": str(item.get("creative_axis") or ""),
                "prompt": prompt,
                "strengths": item.get("strengths", []),
                "risks": item.get("risks", []),
                "soft_scores": _local_candidate_scores(prompt),
            })
        elif str(item).strip():
            normalized.append({
                "candidate_index": index,
                "name": f"方向 {index}",
                "creative_axis": "",
                "prompt": str(item).strip(),
                "strengths": [], "risks": [], "soft_scores": _local_candidate_scores(str(item).strip()),
            })
    if not normalized:
        normalized = [{
            "candidate_index": 1,
            "name": "上游原始方案",
            "creative_axis": "unparsed",
            "prompt": text.strip(),
            "strengths": [], "risks": ["上游未返回结构化候选，已保留非空原文。"],
            "soft_scores": _local_candidate_scores(text.strip()),
        }]
    payload = {
        "schema_version": CREATIVE_SUITE_SCHEMA,
        "operation": "creative_candidates",
        "provider": provider,
        "requested_count": count,
        "structured_response": bool(data),
        "candidates": normalized,
        "comparison": data.get("comparison", []),
        "scoring_notice": (
            "Scores are deterministic local text heuristics, not model judgments or objective quality measurements; "
            "they never block a non-empty candidate."
        ),
    }
    return payload, [str(item["prompt"]) for item in normalized]


class T8CreativeCandidateLab(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8CreativeCandidateLab",
            display_name="T8 Creative Candidate Lab（多方案实验室）",
            category="T8/Creative Suite",
            description="一次付费请求生成 2–4 个结构不同的方向；软评分只辅助选择，不阻塞任何非空结果。",
            inputs=[
                io.String.Input("concept", display_name="创作需求（必填）", multiline=True, dynamic_prompts=True, default=""),
                T8CreativeBriefIO.Input("creative_brief", display_name="创作总纲（可选）", optional=True),
                io.Combo.Input("model_target", display_name="目标模型", options=MODEL_TARGETS, default=MODEL_TARGETS[2]),
                io.Combo.Input("candidate_count", display_name="候选数量（一次请求）", options=CANDIDATE_COUNTS, default="3"),
                io.Combo.Input(
                    "divergence",
                    display_name="方向差异",
                    options=["低（同策略微调）", "中（不同创作机制）", "高（明显不同导演路线）"],
                    default="中（不同创作机制）",
                ),
                io.String.Input("must_keep", display_name="必须保留", optional=True, multiline=True, default=""),
                io.Combo.Input("rewrite_mode", display_name="创作幅度", options=REWRITE_MODES, default="creative"),
                io.Combo.Input("output_language", display_name="输出语言", options=OUTPUT_LANGUAGES, default="中文"),
                *_provider_inputs(),
            ],
            outputs=[
                io.String.Output(display_name="candidates_json"),
                io.String.Output(display_name="comparison_report_json"),
                io.String.Output(display_name="candidate_1"),
                io.String.Output(display_name="candidate_2"),
                io.String.Output(display_name="candidate_3"),
                io.String.Output(display_name="candidate_4"),
            ],
        )

    @classmethod
    def execute(
        cls,
        concept,
        creative_brief=None,
        model_target=MODEL_TARGETS[2],
        candidate_count="3",
        divergence="中（不同创作机制）",
        must_keep="",
        rewrite_mode="creative",
        output_language="中文",
        api_key="",
        provider_config=None,
        seed=0,
    ) -> io.NodeOutput:
        concept = _clean_text(concept)
        keep = _clean_text(must_keep)
        if not concept:
            raise CreativeSuiteError("创作需求不能为空。")
        count = int(candidate_count)
        system = """You are a concise creative direction laboratory. Generate genuinely different creative mechanisms, not paraphrases. Fit the target model and preserve every locked fact.
Return compact JSON only: {\"candidates\":[{\"name\":\"\",\"creative_axis\":\"\",\"prompt\":\"\",\"strengths\":[\"\"],\"risks\":[\"\"]}],\"comparison\":[\"\"]}. Keep each prompt model-ready but concise; strengths and risks have at most two short items each. Do not score candidates; deterministic advisory scores are added locally. No Markdown fences."""
        user = "\n".join([
            f"Output language: {output_language}",
            f"Target model: {model_target}",
            f"Candidate count: exactly {count}",
            f"Divergence: {divergence}",
            "Shared creative brief:", _brief_context(creative_brief),
            "Must keep:", keep or "None beyond the brief and user facts.",
            "Creative request:", concept,
        ])
        result = _run_completion(
            system=system, user=user, api_key=api_key, provider_config=provider_config,
            rewrite_mode=rewrite_mode, seed=seed,
            max_output_tokens=1536,
        )
        payload, prompts = _normalize_candidates(result.text, count, result.provider)
        slots = (prompts + [""] * 4)[:4]
        comparison = {
            "comparison": payload["comparison"],
            "scoring_notice": payload["scoring_notice"],
            "provider": result.provider,
        }
        return io.NodeOutput(_json_text(payload), _json_text(comparison), *slots)


class T8CreativeCandidateSelector(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8CreativeCandidateSelector",
            display_name="T8 Candidate Selector（候选选择）",
            category="T8/Creative Suite",
            description="纯本地从候选 JSON 选择一个方向，不调用 LLM。",
            inputs=[
                io.String.Input("candidates_json", display_name="候选 JSON", multiline=True, default=""),
                io.Int.Input("candidate_index", display_name="候选序号", default=1, min=1, max=4, step=1),
            ],
            outputs=[io.String.Output(display_name="selected_candidate")],
        )

    @classmethod
    def execute(cls, candidates_json, candidate_index=1) -> io.NodeOutput:
        parsed = _extract_json(_clean_text(candidates_json))
        if not isinstance(parsed, Mapping) or not isinstance(parsed.get("candidates"), list):
            raise CreativeSuiteError("候选 JSON 无效。")
        index = int(candidate_index) - 1
        candidates = parsed["candidates"]
        if index < 0 or index >= len(candidates):
            raise CreativeSuiteError(f"候选序号超出范围；当前只有 {len(candidates)} 项。")
        item = candidates[index]
        output = str(item.get("prompt") if isinstance(item, Mapping) else item).strip()
        if not output:
            raise CreativeSuiteError("选中的候选内容为空。")
        return io.NodeOutput(output)


def _normalize_shot_count(value: Any) -> int:
    text = str(value or "").strip()
    if text.startswith("AUTO"):
        return 0
    count = int(text)
    if not 1 <= count <= 20:
        raise CreativeSuiteError("镜头数量必须是 AUTO 或 1–20。")
    return count


class T8StoryboardPack(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8StoryboardPack",
            display_name="T8 Storyboard Pack（分镜创作包）",
            category="T8/Creative Suite",
            description="一次请求输出全局提示词、逐镜 JSON、关键帧图像提示词、转场/声音和素材绑定。",
            inputs=[
                io.String.Input("concept", display_name="创意 / 已选方案（必填）", multiline=True, dynamic_prompts=True, default=""),
                T8CreativeBriefIO.Input("creative_brief", display_name="创作总纲（可选）", optional=True),
                T8ReferenceRoleMapIO.Input("reference_role_map", display_name="素材角色表（可选）", optional=True),
                io.Combo.Input("model_target", display_name="目标模型", options=MODEL_TARGETS, default=MODEL_TARGETS[2]),
                io.Int.Input("duration_seconds", display_name="目标时长（秒）", default=15, min=1, step=1),
                io.Combo.Input("shot_count", display_name="镜头数量", options=SHOT_COUNT_OPTIONS, default=SHOT_COUNT_OPTIONS[0]),
                io.Combo.Input("rewrite_mode", display_name="创作幅度", options=REWRITE_MODES, default="balanced"),
                io.Combo.Input("output_language", display_name="输出语言", options=OUTPUT_LANGUAGES, default="中文"),
                *_provider_inputs(),
            ],
            outputs=[
                io.String.Output(display_name="global_prompt"),
                io.String.Output(display_name="shot_list_json"),
                io.String.Output(display_name="keyframe_prompts_json"),
                io.String.Output(display_name="transition_sound_json"),
            ],
        )

    @classmethod
    def execute(
        cls,
        concept,
        creative_brief=None,
        reference_role_map=None,
        model_target=MODEL_TARGETS[2],
        duration_seconds=15,
        shot_count=SHOT_COUNT_OPTIONS[0],
        rewrite_mode="balanced",
        output_language="中文",
        api_key="",
        provider_config=None,
        seed=0,
    ) -> io.NodeOutput:
        concept = _clean_text(concept)
        if not concept:
            raise CreativeSuiteError("创意 / 已选方案不能为空。")
        duration = int(duration_seconds)
        if duration < 1:
            raise CreativeSuiteError("目标时长必须是正整数。")
        count = _normalize_shot_count(shot_count)
        reference_map = _coerce_mapping(reference_role_map, REFERENCE_MAP_SCHEMA)
        system = """You are a storyboard delivery director. Build an executable creative pack, not a production claim. Respect identity locks, reference roles, exact dialogue/lyrics/visible text, and the requested duration.
Each shot must have index, start_seconds, end_seconds, purpose, composition, subject_action, camera, continuity, media_bindings, dialogue_or_text, sound, keyframe_prompt, transition_in, and transition_out. Keep fields compact and do not repeat the global prompt. Keyframe prompts describe still images and must not include impossible temporal actions. Do not invent @素材 labels absent from the connected role map.
Return one JSON object with global_prompt and shots only. Do not repeat keyframe or transition tables at the top level; the node derives those outputs locally from each shot. Do not use Markdown fences."""
        user = "\n".join([
            f"Output language: {output_language}", f"Target model: {model_target}",
            f"Duration: {duration} seconds", f"Shot count: {'AUTO' if count == 0 else count}",
            "Creative brief:", _brief_context(creative_brief),
            "Reference role map:", _json_text(reference_map) if reference_map else "None.",
            "Selected creative direction:", concept,
        ])
        result = _run_completion(
            system=system, user=user, api_key=api_key, provider_config=provider_config,
            rewrite_mode=rewrite_mode, seed=seed,
            max_output_tokens=2048,
        )
        parsed = _extract_json(result.text)
        data = dict(parsed) if isinstance(parsed, Mapping) else {}
        global_prompt = str(data.get("global_prompt") or result.text).strip()
        shots = data.get("shots", []) if isinstance(data.get("shots"), list) else []
        keyframe_prompts = [
            {
                "index": item.get("index", index),
                "prompt": str(item.get("keyframe_prompt") or "").strip(),
            }
            for index, item in enumerate(shots, 1)
            if isinstance(item, Mapping) and str(item.get("keyframe_prompt") or "").strip()
        ]
        transition_sound = [
            {
                "index": item.get("index", index),
                "transition_in": str(item.get("transition_in") or "").strip(),
                "transition_out": str(item.get("transition_out") or "").strip(),
                "sound": str(item.get("sound") or "").strip(),
            }
            for index, item in enumerate(shots, 1)
            if isinstance(item, Mapping)
        ]
        # Older/OpenAI-compatible providers may still follow the former
        # top-level contract. Preserve those non-empty tables when present.
        if not keyframe_prompts and isinstance(data.get("keyframe_prompts"), list):
            keyframe_prompts = data["keyframe_prompts"]
        if not transition_sound and isinstance(data.get("transition_sound"), list):
            transition_sound = data["transition_sound"]
        meta = {"schema_version": CREATIVE_SUITE_SCHEMA, "provider": result.provider,
                "structured_response": bool(data), "duration_seconds": duration,
                "requested_shot_count": count}
        return io.NodeOutput(
            global_prompt,
            _json_text({**meta, "shots": shots, "unparsed_response": "" if data else result.text}),
            _json_text({**meta, "keyframe_prompts": keyframe_prompts}),
            _json_text({**meta, "transition_sound": transition_sound}),
        )


def _case_component(selection: str, role: str) -> dict[str, Any] | None:
    if str(selection or NO_CASE_TEMPLATE) == NO_CASE_TEMPLATE:
        return None
    template = get_case_template(selection)
    if template is None:
        raise CreativeSuiteError(f"找不到 T8 案例模板：{selection}")
    return {
        "role": role,
        "template_id": str(template["id"]),
        "label": str(template["label"]),
        "creative_dna": str(template["creative_dna"]),
        "required_anchors": list(template["required_anchors"]),
        "h3_guidance": str(template["variants"]["h3"]["guidance"]),
        "seedance20_guidance": str(template["variants"]["seedance20"]["guidance"]),
    }


class T8CreativeDNAMixer(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8CreativeDNAMixer",
            display_name="T8 Creative DNA Mixer（案例机制融合）",
            category="T8/Creative Suite",
            description="纯本地融合最多三个 T8 非官方案例的结构/镜头/收尾机制；不读取或发送案例媒体。",
            inputs=[
                io.String.Input("instance_intent", display_name="你的创作内容（必填）", multiline=True, dynamic_prompts=True, default=""),
                io.Combo.Input("structure_case", display_name="结构来源", options=CASE_TEMPLATE_OPTIONS, default=NO_CASE_TEMPLATE),
                io.Combo.Input("camera_case", display_name="镜头来源", options=CASE_TEMPLATE_OPTIONS, default=NO_CASE_TEMPLATE),
                io.Combo.Input("payoff_case", display_name="高潮 / 收尾来源", options=CASE_TEMPLATE_OPTIONS, default=NO_CASE_TEMPLATE),
                io.Combo.Input("model_target", display_name="目标模型", options=MODEL_TARGETS, default=MODEL_TARGETS[2]),
            ],
            outputs=[
                T8CreativeDNAMixIO.Output(display_name="creative_dna_mix"),
                io.String.Output(display_name="creative_dna_instruction"),
                io.String.Output(display_name="creative_dna_json"),
            ],
        )

    @classmethod
    def validate_inputs(cls, structure_case=None, camera_case=None, payoff_case=None) -> bool:
        del structure_case, camera_case, payoff_case
        return True

    @classmethod
    def execute(
        cls,
        instance_intent,
        structure_case=NO_CASE_TEMPLATE,
        camera_case=NO_CASE_TEMPLATE,
        payoff_case=NO_CASE_TEMPLATE,
        model_target=MODEL_TARGETS[2],
    ) -> io.NodeOutput:
        intent = _clean_text(instance_intent)
        if not intent:
            raise CreativeSuiteError("你的创作内容不能为空。")
        components = [
            component for component in (
                _case_component(structure_case, DNA_ROLES[0]),
                _case_component(camera_case, DNA_ROLES[1]),
                _case_component(payoff_case, DNA_ROLES[2]),
            ) if component
        ]
        if not components:
            raise CreativeSuiteError("请至少选择一个 T8 案例。")
        ids = [component["template_id"] for component in components]
        if len(ids) != len(set(ids)):
            raise CreativeSuiteError("同一个案例不能重复承担多个融合角色；请选择不同案例。")
        payload = {
            "schema_version": DNA_MIX_SCHEMA,
            "authority": "T8 non-official creative mechanisms",
            "instance_intent": intent,
            "model_target": model_target,
            "components": components,
            "anti_copy": (
                "Transfer only causal structure, camera grammar and payoff mechanics. Never copy source people, "
                "objects, setting, story, dialogue, wording, shot list, surface style, GIF, source video, or preview media."
            ),
        }
        instructions = [
            "T8 Creative DNA fusion (non-official). The user's instance intent is authoritative.",
            f"INSTANCE_INTENT: {intent}",
            payload["anti_copy"],
        ]
        for component in components:
            target_guidance = []
            if "MiniMax H3" in model_target:
                target_guidance.append(component["h3_guidance"])
            if "Seedance 2.0" in model_target:
                target_guidance.append(component["seedance20_guidance"])
            instructions.append(
                f"ROLE={component['role']}\nCREATIVE_DNA={component['creative_dna']}\n"
                f"REQUIRED_ANCHORS={_json_text(component['required_anchors'])}\n"
                f"MODEL_GUIDANCE={' '.join(target_guidance)}"
            )
        return io.NodeOutput(payload, "\n\n".join(instructions), _json_text(payload))


class T8PersonalCreativePreset(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8PersonalCreativePreset",
            display_name="T8 Personal Creative Preset（工作流内个人预设）",
            category="T8/Creative Suite",
            description="把用户自有创作方法保存为工作流内可复用预设；不写磁盘、不修改官方或 T8 内置库。",
            inputs=[
                io.String.Input("preset_name", display_name="预设名称（必填）", default=""),
                io.String.Input("purpose", display_name="用途（必填）", multiline=True, default=""),
                io.String.Input("recommended_input", display_name="推荐输入格式", multiline=True, default=""),
                io.String.Input("structure_anchors", display_name="结构锚点（每行一项）", multiline=True, default=""),
                io.String.Input("creative_rules", display_name="创作规则", multiline=True, default=""),
                io.String.Input("exclusions", display_name="禁止复制 / 禁止出现", optional=True, multiline=True, default=""),
                io.Combo.Input(
                    "rights_confirmation",
                    display_name="素材与规则权利确认",
                    options=["仅保存文字规则，不包含第三方媒体", "我有权使用所述自有素材"],
                    default="仅保存文字规则，不包含第三方媒体",
                ),
            ],
            outputs=[
                T8PersonalPresetIO.Output(display_name="personal_preset"),
                io.String.Output(display_name="preset_instruction"),
                io.String.Output(display_name="preset_json"),
            ],
        )

    @classmethod
    def execute(
        cls,
        preset_name,
        purpose,
        recommended_input="",
        structure_anchors="",
        creative_rules="",
        exclusions="",
        rights_confirmation="仅保存文字规则，不包含第三方媒体",
    ) -> io.NodeOutput:
        name = _clean_text(preset_name, limit=120)
        purpose = _clean_text(purpose)
        if not name or not purpose:
            raise CreativeSuiteError("预设名称和用途不能为空。")
        anchors = [line.strip(" -\t") for line in _clean_text(structure_anchors).splitlines() if line.strip(" -\t")]
        payload = {
            "schema_version": PERSONAL_PRESET_SCHEMA,
            "authority": "user-owned workflow-local preset",
            "name": name,
            "purpose": purpose,
            "recommended_input": _clean_text(recommended_input),
            "structure_anchors": anchors,
            "creative_rules": _clean_text(creative_rules),
            "exclusions": _clean_text(exclusions),
            "rights_confirmation": str(rights_confirmation),
            "media_included": False,
        }
        instruction = "\n".join([
            f"User-owned personal creative preset: {name}",
            f"Purpose: {purpose}",
            f"Recommended input shape: {payload['recommended_input'] or 'unspecified'}",
            f"Required anchors: {_json_text(anchors)}",
            f"Creative rules: {payload['creative_rules'] or 'none'}",
            f"Exclusions: {payload['exclusions'] or 'none'}",
            "Apply only to the current user's instance. Do not treat this as a MiniMax official Skill or a T8 built-in case.",
        ])
        return io.NodeOutput(payload, instruction, _json_text(payload))


MUSIC_LAB_MODES = [
    "歌词候选（T8非官方）",
    "Music Caption 候选（官方结构）",
    "歌词定向修改（T8非官方）",
    "歌词可唱性软 QA",
]
MUSIC_LANGUAGES = ["中文", "English", "日本語", "한국어", "Custom"]


def _lyric_tags_only(lyrics: str) -> str:
    return " ".join(SECTION_TAG_RE.findall(str(lyrics or "")))


def _local_lyric_qa(lyrics: str, language: str) -> dict[str, Any]:
    lines = [line.strip() for line in str(lyrics or "").splitlines()
             if line.strip() and not SECTION_TAG_RE.fullmatch(line.strip())]
    lengths = [len(re.sub(r"\s+", "", line)) for line in lines]
    repeated: dict[str, int] = {}
    for line in lines:
        normalized = re.sub(r"[\s，。！？,.!?;；:：'\"“”‘’]", "", line).lower()
        if normalized:
            repeated[normalized] = repeated.get(normalized, 0) + 1
    script_warning = ""
    joined = "".join(lines)
    if language == "中文" and joined and len(re.findall(r"[\u4e00-\u9fff]", joined)) < max(4, len(joined) // 5):
        script_warning = "目标为中文，但候选中的汉字比例偏低。"
    elif language == "日本語" and joined and not re.search(r"[\u3040-\u30ff]", joined):
        script_warning = "目标为日文，但未检测到假名。"
    elif language == "한국어" and joined and not re.search(r"[\uac00-\ud7af]", joined):
        script_warning = "目标为韩文，但未检测到谚文。"
    return {
        "line_count": len(lines),
        "line_length_min": min(lengths) if lengths else 0,
        "line_length_max": max(lengths) if lengths else 0,
        "line_length_average": round(sum(lengths) / len(lengths), 2) if lengths else 0,
        "repeated_lines": [key for key, count in repeated.items() if count > 1],
        "script_warning": script_warning,
        "notice": "这是结构与文字层面的软 QA，不等于真实演唱、旋律重音或音频质量判断。",
    }


def _music_lab_prompt(
    mode: str,
    music_idea: str,
    source_lyrics: str,
    source_caption: str,
    lyrics_language: str,
    custom_language: str,
    count: int,
    edit_request: str,
    locked_text: str,
) -> tuple[str, str]:
    language = custom_language if lyrics_language == "Custom" else lyrics_language
    common = """Never copy an existing artist's lyrics, melody, title, or distinctive hook. Preserve exact locked user text. Do not claim to hear audio, detect BPM, inspect stems, or verify real singability. Return JSON only without Markdown fences."""
    if mode == MUSIC_LAB_MODES[0]:
        system = common + """
You are an original lyric ideation editor. Create structurally different lyric candidates in exactly the requested lyric language. Use clear section tags, a memorable but original hook, singable line-length discipline, emotional progression, and no artist imitation. Keep each candidate to at most 16 non-empty lyric lines; prefer one compact Verse, one Pre-Chorus, one Chorus, one Bridge, and a short Outro. Return candidates; each has name, title, lyrics, creative_axis, and soft_qa. Also return comparison."""
        user = f"Requested language: {language}\nCandidate count: exactly {count}\nMusic idea:\n{music_idea}\nLocked text:\n{locked_text or 'None.'}"
    elif mode == MUSIC_LAB_MODES[1]:
        system = common + """
You follow the official MiniMax Music 3 caption contract. Create distinct structured-caption candidates, each containing exactly these headings in order: ### Global Metadata, ### Vocal Details, ### Arrangement. Do not reproduce, paraphrase, or summarize lyric content; only bracketed section/control tags may influence structure. Return candidates; each has name, title (optional T8 utility metadata), caption, creative_axis, and soft_qa. Also return comparison."""
        user = "\n".join([
            f"Candidate count: exactly {count}", "Music idea:", music_idea,
            "Existing caption (use only as user-owned direction; do not copy blindly):", source_caption or "None.",
            "Lyrics section/control tags only:", _lyric_tags_only(source_lyrics) or "None.",
            "Locked constraints:", locked_text or "None.",
        ])
    elif mode == MUSIC_LAB_MODES[2]:
        system = common + """
You are a surgical lyric editor. Modify only the requested lines or sections, keep every unselected line byte-for-byte when possible, retain section tags, and write replacements in exactly the requested language. Return candidates with one item containing name, title, lyrics, creative_axis, soft_qa, plus change_summary and warnings."""
        user = "\n".join([
            f"Requested language: {language}", "Music idea:", music_idea,
            "Source lyrics:", source_lyrics, "Edit request:", edit_request,
            "Locked text:", locked_text or "All unmentioned content.",
        ])
    else:
        system = common + """
You are a cautious lyric text reviewer. Provide soft, actionable observations about language consistency, line length, rhyme regularity, hook recurrence, section balance, diction, breath density, and possible awkward phrasing. Never call a stylistic choice an error and never claim actual singing or audio evidence. Return qa_report, suggested_edits, and warnings."""
        user = "\n".join([
            f"Requested language: {language}", "Music idea:", music_idea,
            "Lyrics to review:", source_lyrics, "User priorities:", edit_request or "None.",
        ])
    return system, user


class T8MusicCreativeLab(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8MusicCreativeLab",
            display_name="T8 Music Creative Lab（歌词/Caption候选与软QA）",
            category="T8/Creative Suite",
            description="独立音乐创作辅助节点；候选或 QA 每次只发起一次 LLM 请求，不改变原 Music 3 节点。",
            inputs=[
                io.Combo.Input("operation", display_name="操作", options=MUSIC_LAB_MODES, default=MUSIC_LAB_MODES[0]),
                io.String.Input("music_idea", display_name="音乐创意（必填）", multiline=True, dynamic_prompts=True, default=""),
                io.String.Input("source_lyrics", display_name="原歌词（按需）", optional=True, multiline=True, default=""),
                io.String.Input("source_caption", display_name="原 Music Caption（按需）", optional=True, multiline=True, default=""),
                io.Combo.Input("lyrics_language", display_name="歌词语言", options=MUSIC_LANGUAGES, default="中文"),
                io.String.Input("custom_language", display_name="自定义歌词语言", optional=True, default="", advanced=True),
                io.Combo.Input("candidate_count", display_name="候选数量", options=["2", "3"], default="3"),
                io.String.Input("edit_request", display_name="定向修改 / QA 要求", optional=True, multiline=True, default=""),
                io.String.Input("locked_text", display_name="必须逐字保留", optional=True, multiline=True, default=""),
                io.Combo.Input("rewrite_mode", display_name="创作幅度", options=REWRITE_MODES, default="balanced"),
                *_provider_inputs(),
            ],
            outputs=[
                io.String.Output(display_name="selected_result"),
                io.String.Output(display_name="candidates_json"),
                io.String.Output(display_name="song_titles_json"),
                io.String.Output(display_name="soft_qa_report_json"),
                io.String.Output(display_name="version_diff"),
            ],
        )

    @classmethod
    def execute(
        cls,
        operation=MUSIC_LAB_MODES[0],
        music_idea="",
        source_lyrics="",
        source_caption="",
        lyrics_language="中文",
        custom_language="",
        candidate_count="3",
        edit_request="",
        locked_text="",
        rewrite_mode="balanced",
        api_key="",
        provider_config=None,
        seed=0,
    ) -> io.NodeOutput:
        idea = _clean_text(music_idea)
        lyrics = _clean_text(source_lyrics)
        caption = _clean_text(source_caption)
        edit = _clean_text(edit_request)
        locked = _clean_text(locked_text)
        custom = _clean_text(custom_language, limit=120)
        if not idea:
            raise CreativeSuiteError("音乐创意不能为空。")
        if operation in {MUSIC_LAB_MODES[2], MUSIC_LAB_MODES[3]} and not lyrics:
            raise CreativeSuiteError("歌词定向修改和软 QA 需要原歌词。")
        if lyrics_language == "Custom" and not custom:
            raise CreativeSuiteError("选择 Custom 时必须填写自定义歌词语言。")
        count = int(candidate_count)
        system, user = _music_lab_prompt(
            operation, idea, lyrics, caption, lyrics_language, custom, count, edit, locked
        )
        result = _run_completion(
            system=system, user=user, api_key=api_key, provider_config=provider_config,
            rewrite_mode=rewrite_mode, seed=seed,
            max_output_tokens=(1536 if operation in MUSIC_LAB_MODES[:3] else 1024),
        )
        parsed = _extract_json(result.text)
        data = dict(parsed) if isinstance(parsed, Mapping) else {}
        raw_candidates = data.get("candidates") if isinstance(data.get("candidates"), list) else []
        candidates = []
        field = "caption" if operation == MUSIC_LAB_MODES[1] else "lyrics"
        for index, item in enumerate(raw_candidates[:count], 1):
            if not isinstance(item, Mapping):
                continue
            output = str(item.get(field) or item.get("output") or "").strip()
            if output:
                candidates.append({
                    "candidate_index": index,
                    "name": str(item.get("name") or f"候选 {index}"),
                    "title": str(item.get("title") or ""),
                    field: output,
                    "creative_axis": str(item.get("creative_axis") or ""),
                    "soft_qa": item.get("soft_qa", {}),
                })
        if operation == MUSIC_LAB_MODES[3]:
            selected = lyrics
        elif candidates:
            selected = str(candidates[0][field])
        else:
            selected = result.text.strip()
        target_language = custom if lyrics_language == "Custom" else lyrics_language
        local_qa = _local_lyric_qa(selected if field == "lyrics" else lyrics, target_language)
        qa_report = {
            "schema_version": CREATIVE_SUITE_SCHEMA,
            "operation": operation,
            "provider": result.provider,
            "structured_response": bool(data),
            "model_qa": data.get("qa_report") or data.get("warnings") or [],
            "suggested_edits": data.get("suggested_edits", []),
            "local_text_qa": local_qa,
        }
        payload = {
            "schema_version": CREATIVE_SUITE_SCHEMA,
            "operation": operation,
            "provider": result.provider,
            "structured_response": bool(data),
            "candidates": candidates,
            "comparison": data.get("comparison", []),
            "unparsed_response": "" if data else result.text,
        }
        titles = [item["title"] for item in candidates if item.get("title")]
        diff = ""
        if operation == MUSIC_LAB_MODES[2]:
            diff = "\n".join(difflib.unified_diff(
                lyrics.splitlines(), selected.splitlines(), fromfile="original_lyrics", tofile="revised_lyrics", lineterm=""
            ))
        return io.NodeOutput(selected, _json_text(payload), _json_text(titles), _json_text(qa_report), diff)


class T8CreativeVersionStack(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8CreativeVersionStack",
            display_name="T8 Creative Version Stack（版本选择/回退）",
            category="T8/Creative Suite",
            description="纯本地保存并选择提示词、歌词或 Caption 版本；版本跟随工作流，不写外部文件。",
            inputs=[
                io.String.Input("base_version", display_name="版本 1（必填）", multiline=True, dynamic_prompts=True, default=""),
                io.Autogrow.Input(
                    "versions",
                    optional=True,
                    template=io.Autogrow.TemplatePrefix(
                        input=io.String.Input("version", multiline=True, default=""),
                        prefix="version_",
                        min=0,
                        max=7,
                    ),
                ),
                io.Int.Input("selected_version", display_name="选择版本（1–8）", default=1, min=1, max=8, step=1),
                io.String.Input("version_notes", display_name="版本说明（每行对应一个版本）", optional=True, multiline=True, default=""),
            ],
            outputs=[
                io.String.Output(display_name="selected_text"),
                io.String.Output(display_name="version_history_json"),
                io.String.Output(display_name="diff_from_previous"),
            ],
        )

    @classmethod
    def validate_inputs(cls, versions=None) -> bool:
        del versions
        return True

    @classmethod
    def execute(cls, base_version, versions=None, selected_version=1, version_notes="") -> io.NodeOutput:
        base = _clean_text(base_version)
        if not base:
            raise CreativeSuiteError("版本 1 不能为空。")
        texts = [base]
        for value in h3._ordered_values(dict(versions or {})):
            text = _clean_text(value)
            if text:
                texts.append(text)
        selected_index = int(selected_version) - 1
        if selected_index < 0 or selected_index >= len(texts):
            raise CreativeSuiteError(f"选择版本超出范围；当前共有 {len(texts)} 个非空版本。")
        notes = [line.strip() for line in _clean_text(version_notes).splitlines()]
        history = {
            "schema_version": CREATIVE_SUITE_SCHEMA,
            "operation": "workflow_local_version_stack",
            "selected_version": selected_index + 1,
            "versions": [
                {"version": index, "note": notes[index - 1] if index - 1 < len(notes) else "", "text": text}
                for index, text in enumerate(texts, 1)
            ],
        }
        previous = texts[selected_index - 1] if selected_index > 0 else texts[selected_index]
        diff = "\n".join(difflib.unified_diff(
            previous.splitlines(), texts[selected_index].splitlines(),
            fromfile=f"version_{max(1, selected_index)}",
            tofile=f"version_{selected_index + 1}",
            lineterm="",
        ))
        return io.NodeOutput(texts[selected_index], _json_text(history), diff)


class T8MusicVideoBeatSheet(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8MusicVideoBeatSheet",
            display_name="T8 Music-to-Video Beat Sheet（音乐视频节拍导演）",
            category="T8/Creative Suite",
            description="把文字歌词、Music Caption 和用户已知节拍事实转为视频节拍表；没有 AUDIO 时绝不声称听歌。",
            inputs=[
                io.String.Input("video_intent", display_name="MV / 视频意图（必填）", multiline=True, dynamic_prompts=True, default=""),
                io.String.Input("lyrics", display_name="歌词（可选）", optional=True, multiline=True, default=""),
                io.String.Input("music_caption", display_name="Music Caption（可选）", optional=True, multiline=True, default=""),
                io.Int.Input("duration_seconds", display_name="视频时长（秒）", default=15, min=1, step=1),
                io.Int.Input("known_bpm", display_name="已知 BPM（0=未知）", default=0, min=0, max=400, step=1),
                io.String.Input("known_time_cues", display_name="已知时间点 / Drop / 重音", optional=True, multiline=True, default=""),
                io.Combo.Input("shot_count", display_name="镜头数量", options=SHOT_COUNT_OPTIONS, default=SHOT_COUNT_OPTIONS[0]),
                io.Combo.Input("output_language", display_name="输出语言", options=OUTPUT_LANGUAGES, default="中文"),
                io.Combo.Input("rewrite_mode", display_name="导演幅度", options=REWRITE_MODES, default="balanced"),
                *_provider_inputs(),
            ],
            outputs=[
                T8BeatSheetIO.Output(display_name="beat_sheet"),
                io.String.Output(display_name="beat_sheet_json"),
                io.String.Output(display_name="h3_direction"),
                io.String.Output(display_name="seedance20_direction"),
            ],
        )

    @classmethod
    def execute(
        cls,
        video_intent,
        lyrics="",
        music_caption="",
        duration_seconds=15,
        known_bpm=0,
        known_time_cues="",
        shot_count=SHOT_COUNT_OPTIONS[0],
        output_language="中文",
        rewrite_mode="balanced",
        api_key="",
        provider_config=None,
        seed=0,
    ) -> io.NodeOutput:
        intent = _clean_text(video_intent)
        lyrics = _clean_text(lyrics)
        caption = _clean_text(music_caption)
        cues = _clean_text(known_time_cues)
        if not intent:
            raise CreativeSuiteError("MV / 视频意图不能为空。")
        duration = int(duration_seconds)
        count = _normalize_shot_count(shot_count)
        system = """You are a music-video beat-sheet director working from text evidence only. Never claim to hear audio, detect BPM, find beats, transcribe vocals, or know timing that the user did not provide.
Use exact lyric text only when the user supplied it. Map section tags, phrasing, known BPM, known timestamps, drop cues, narrative actions, spatial typography, performance, and camera changes into a controllable visual timeline. When BPM or timestamps are unknown, use qualitative section-relative rhythm and label timing as editorial planning, not detected evidence.
Return one compact JSON object with evidence_boundary, rhythm_arc, beat_events, h3_direction, and seedance20_direction. Each beat event has start_seconds, end_seconds, lyric_or_section, energy, visual_event, camera, typography, sound_relation, and evidence_source. When a fixed shot count is supplied, return exactly that many non-overlapping beat events covering the duration. H3 and Seedance directions are concise model-specific constraint summaries (at most 180 Chinese characters or 110 English words each); do not repeat the beat-event table inside them. Do not use Markdown fences."""
        user = "\n".join([
            f"Output language: {output_language}", f"Duration: {duration} seconds",
            f"Shot count: {'AUTO' if count == 0 else count}",
            f"Known BPM: {int(known_bpm) if int(known_bpm) else 'unknown'}",
            "Known time cues:", cues or "None.",
            "Video intent:", intent,
            "User-supplied lyrics:", lyrics or "None.",
            "User-supplied Music Caption:", caption or "None.",
        ])
        result = _run_completion(
            system=system, user=user, api_key=api_key, provider_config=provider_config,
            rewrite_mode=rewrite_mode, seed=seed,
            max_output_tokens=1536,
        )
        parsed = _extract_json(result.text)
        data = dict(parsed) if isinstance(parsed, Mapping) else {}
        payload = {
            "schema_version": BEAT_SHEET_SCHEMA,
            "provider": result.provider,
            "structured_response": bool(data),
            "duration_seconds": duration,
            "known_bpm": int(known_bpm),
            "evidence_boundary": data.get("evidence_boundary") or (
                "Text-only planning; no audio was connected or analyzed."
            ),
            "rhythm_arc": data.get("rhythm_arc", ""),
            "beat_events": data.get("beat_events", []),
            "unparsed_response": "" if data else result.text,
        }
        h3_direction = str(data.get("h3_direction") or result.text).strip()
        seedance_direction = str(data.get("seedance20_direction") or result.text).strip()
        return io.NodeOutput(payload, _json_text(payload), h3_direction, seedance_direction)


CREATIVE_SUITE_NODES = [
    T8CreativeDirector,
    T8CreativeContextAssembler,
    T8DirectedRevision,
    T8LongFormPlanner,
    T8ReferenceRoleMapper,
    T8CreativeCandidateLab,
    T8CreativeCandidateSelector,
    T8StoryboardPack,
    T8CreativeDNAMixer,
    T8PersonalCreativePreset,
    T8MusicCreativeLab,
    T8CreativeVersionStack,
    T8MusicVideoBeatSheet,
]


__all__ = [
    "BEAT_SHEET_SCHEMA",
    "BRIEF_SCHEMA",
    "CREATIVE_SUITE_NODES",
    "CREATIVE_SUITE_SCHEMA",
    "CreativeSuiteError",
    "DNA_MIX_SCHEMA",
    "PERSONAL_PRESET_SCHEMA",
    "REFERENCE_MAP_SCHEMA",
    "T8BeatSheetIO",
    "T8CreativeBriefIO",
    "T8CreativeCandidateLab",
    "T8CreativeCandidateSelector",
    "T8CreativeContextAssembler",
    "T8CreativeVersionStack",
    "T8CreativeDNAMixIO",
    "T8CreativeDNAMixer",
    "T8CreativeDirector",
    "T8DirectedRevision",
    "T8LongFormPlanner",
    "T8MusicCreativeLab",
    "T8MusicVideoBeatSheet",
    "T8PersonalCreativePreset",
    "T8PersonalPresetIO",
    "T8ReferenceRoleMapIO",
    "T8ReferenceRoleMapper",
    "T8StoryboardPack",
    "build_creative_brief",
]
