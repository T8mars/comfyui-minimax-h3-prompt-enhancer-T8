"""MOSS collection authoring and zero-inference page selection."""
from __future__ import annotations

import json

from comfy_api.latest import io

from . import moss_authoring_bundle as bundle
from . import moss_authoring_contract as contract
from . import moss_authoring as authoring
from . import moss_authoring_runtime as runtime
from . import moss_authoring_state as state
from . import moss_image as main
from .provider_config import T8ProviderConfigIO
from .execution_diagnostics import DiagnosticsRun

DIRECTOR_AUTO = "Auto / 自动（Fisher默认中文）"
LANGUAGES = [DIRECTOR_AUTO, "English", "中文"]


def _language(value):
    return contract.c.LANG_AUTO if value == DIRECTOR_AUTO else value


def _collection_output(value, origin):
    value = bundle.validate_bundle(value)
    status = {"origin": origin, "profile": value["profile"], "unit_count": len(value["units"]),
              "calls": 0 if origin == "cache" else value["report"]["logical_generation_calls"],
              "source_generation_calls": value["report"]["logical_generation_calls"],
              "bilingual_complete": value["report"]["bilingual_complete"], "semantics_verified": False}
    return io.NodeOutput(contract.encode(value), len(value["units"]), contract.encode(value["report"]), bundle.readable(value),
                         ui={"t8_moss_authoring_result": [json.dumps(status, ensure_ascii=False)]})


class MOSSAuthoringDirector(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id=state.NODE_ID, display_name="MOSS Authoring Director T8", category="T8/MOSS Image",
            description="Comic pages with English/Chinese shared geometry, or Fisher independent/fused references. Outputs a collection, NOT a positive prompt. Connect MOSS Authoring Page. No image generation.",
            inputs=[
                io.String.Input("brief", display_name="创作/修订需求 / Brief", default="", multiline=True, dynamic_prompts=False, lazy=True),
                io.Combo.Input("profile", display_name="强化模式 / Profile", options=[authoring.COMIC, authoring.FISHER], default=authoring.COMIC),
                io.Int.Input("width", display_name="宽 / Width", default=1024, min=16, max=16384, step=8),
                io.Int.Input("height", display_name="高 / Height", default=1024, min=16, max=16384, step=8),
                io.Int.Input("max_output_chars", display_name="每页每语言描述字数上限（0自动）", default=0, min=0, max=20000, step=100,
                             tooltip="Unicode description code points, not Tokens. Soft cap, never truncates. Fisher automatic Chinese uses its creative Han-length preference."),
                io.Int.Input("max_corrections", display_name="每阶段最多追加纠正 / Corrections per stage", default=1, min=0, max=1),
                io.Int.Input("page_count", display_name="漫画页数（0自动；Fisher忽略）", default=0, min=0, max=contract.MAX_UNITS, step=1),
                io.Combo.Input("reference_mode", display_name="Fisher参考方式（漫画忽略）", options=["independent", "fusion"], default="independent",
                               tooltip="independent: one complete unit per expanded image, in order; fusion: explicit single-image combination. Comic images are shared context, not one book per image."),
                io.Combo.Input("descriptive_language", display_name="Fisher描述语言（漫画固定英中双语）", options=LANGUAGES, default=DIRECTOR_AUTO),
                T8ProviderConfigIO.Input("provider_config", display_name="共享LLM配置（生成时必接）", optional=True, lazy=True,
                    tooltip="Required for generation. Use T8 LLM Provider Config; restore and zero-edit context need no provider."),
                io.Autogrow.Input("reference_images", optional=True, template=io.Autogrow.TemplatePrefix(
                    input=io.Image.Input("reference_image", lazy=True), prefix="reference_image_", min=0, max=10)),
                io.String.Input("locked_text", display_name="锁定可见文案 / Exact visible blocks", default="", optional=True, multiline=True, dynamic_prompts=False, lazy=True),
                io.String.Input("continuity_context", display_name="显式人物/连续性事实 / Human continuity", default="", optional=True, multiline=True, dynamic_prompts=False, lazy=True),
                io.String.Input("layout_context_json", display_name="既有整册修订上下文 / Typed revision context", default="", optional=True, multiline=True, dynamic_prompts=False, lazy=True,
                                tooltip="Typed context JSON with bundle, mode and edit_unit_ids. Unselected units are copied unchanged. Original reference images must be reattached for edits."),
                io.Boolean.Input("preserve_layout", display_name="保留上下文布局 / Preserve layout", default=True, optional=True),
                io.Int.Input("llm_max_tokens", display_name="云端每阶段生成Token / Cloud budget", default=16384, min=256, max=65536, step=1024, optional=True, advanced=True),
                io.Int.Input("seed", display_name="种子 / Seed", default=0, min=0, max=0xffffffffffffffff, control_after_generate=False, optional=True, advanced=True),
                io.String.Input("recovery_slot", default="", optional=True, socketless=True, advanced=True),
                io.String.Input("recovery_action", default="normal", optional=True, socketless=True, advanced=True),
            ], outputs=[io.String.Output(display_name="完整集合 / bundle_json"), io.Int.Output(display_name="单元数 / unit_count"),
                        io.String.Output(display_name="诊断报告 / report_json"), io.String.Output(display_name="逐页英中阅读稿 / paired_reading")])

    @classmethod
    def validate_inputs(cls, brief="", profile=authoring.COMIC, width=1024, height=1024, max_output_chars=0,
                        max_corrections=1, page_count=0, reference_mode="independent", descriptive_language=DIRECTOR_AUTO,
                        preserve_layout=True, layout_context_json="", continuity_context="", locked_text="", recovery_action="normal", **kwargs):
        if recovery_action == "restore_last": return True
        try:
            context = runtime.context_value(layout_context_json) if isinstance(layout_context_json, str) else None
            if context and not context["edit_unit_ids"]: return True
            # Linked values are unresolved during graph validation only. The
            # resolved branch repeats all checks before provider ownership.
            runtime.controls_valid("placeholder" if brief is None else brief,
                authoring.COMIC if profile is None else profile, 1024 if width is None else width, 1024 if height is None else height,
                0 if max_output_chars is None else max_output_chars, 1 if max_corrections is None else max_corrections,
                0 if page_count is None else page_count, "independent" if reference_mode is None else reference_mode,
                contract.c.LANG_AUTO if descriptive_language is None else _language(descriptive_language), True if preserve_layout is None else preserve_layout)
            if layout_context_json is not None: runtime.context_value(layout_context_json)
            if continuity_context is not None: contract.c.clean_text(continuity_context, "continuity context", limit=64000)
            if locked_text is not None: contract.c.locked_blocks(locked_text)
            if isinstance(layout_context_json, str) and brief is not None and not brief.strip():
                return "A brief is required for generation / 生成或修订需求不能为空。"
            return True
        except (contract.c.MossContractError, main.MossImageError) as error:
            return str(error)

    @classmethod
    def check_lazy_status(cls, brief=None, provider_config=main._MISSING, reference_images=main._MISSING,
                          layout_context_json=main._MISSING, continuity_context=main._MISSING, locked_text=main._MISSING,
                          recovery_action="normal", **kwargs):
        if recovery_action == "restore_last": return []
        if layout_context_json is None: return ["layout_context_json"]
        if isinstance(layout_context_json, str) and layout_context_json.strip():
            context = runtime.context_value(layout_context_json)
            if not context["edit_unit_ids"]: return []
        needs = [name for name, value in (("brief", brief), ("continuity_context", continuity_context), ("locked_text", locked_text)) if value is None]
        if provider_config is None: return ["provider_config", *needs]
        images = main.MOSSImagePromptEnhancer.check_lazy_status(prompt="resolved", reference_images=reference_images,
            provider_config=provider_config, **kwargs)
        return list(dict.fromkeys([*needs, *images]))

    @classmethod
    def execute(cls, brief="", profile=authoring.COMIC, width=1024, height=1024, max_output_chars=0, max_corrections=1,
                page_count=0, reference_mode="independent", descriptive_language=DIRECTOR_AUTO, provider_config=None,
                reference_images=None, locked_text="", continuity_context="", layout_context_json="", preserve_layout=True,
                llm_max_tokens=16384, seed=0, recovery_slot="", recovery_action="normal", **kwargs):
        if recovery_action == "restore_last":
            return _collection_output(state.recover(recovery_slot), "cache")
        if recovery_action != "normal": contract.c.fail("invalid_recovery_action", "Invalid recovery action / 恢复动作无效。")
        diagnostics = DiagnosticsRun(state.NODE_ID, "authoring", 3, emit_progress=False)
        token = state.begin(recovery_slot)
        counters = {"logical_generation_calls": 0, "chat_post_attempts": 0, "correction_calls": 0, "failed_raw": ""}
        progress = {"units": [], "stage_records": []}
        controls = {"brief": brief, "profile": profile, "width": width, "height": height, "max_output_chars": max_output_chars,
            "max_corrections": max_corrections, "page_count": page_count, "reference_mode": reference_mode,
            "descriptive_language": _language(descriptive_language), "preserve_layout": preserve_layout, "continuity_context": continuity_context,
            "locked_text": locked_text, "layout_context_json": layout_context_json, "seed": seed}
        try:
            prepared = runtime.prepare(controls, reference_images, kwargs)
            diagnostics.advance("inputs_validated", asset_count=len(prepared["media"]))
            def finish(result, current):
                # Construct all returned strings before the final deadline and
                # transaction check. Partial data never reaches downstream.
                output = _collection_output(result, "current")
                main.interrupted()
                if current is not None and main.is_strata_mode(current["api_mode"]):
                    main.require_strata_run().identity(); main.require_strata_run().remaining()
                state.commit(recovery_slot, token, output.result[0])
                diagnostics.advance("completed", attempts=counters["logical_generation_calls"])
                diagnostics.complete("success")
                return output
            if prepared["context"] and not prepared["context"]["edit_unit_ids"]:
                return finish(runtime.run(None, controls, prepared, counters, progress), None)
            if type(seed) is not int or not 0 <= seed <= 0xffffffffffffffff:
                contract.c.fail("invalid_seed", "Seed must be an unsigned integer / 种子须为非负整数。")
            current = runtime.provider_values(provider_config, llm_max_tokens)
            diagnostics.provider = current["api_mode"]
            return runtime.execute_run(current, controls, prepared, counters, progress,
                api_mode=current["api_mode"], provider_request_options=current["provider_request_options"], seed=seed, on_complete=finish)
        except BaseException as error:
            diagnostics.complete("error", error)
            code = error.code if isinstance(error, contract.c.MossContractError) else type(error).__name__
            state.failed(recovery_slot, token, {**progress, "raw": counters["failed_raw"]}, code)
            if isinstance(error, contract.c.MossContractError):
                raise main.MossImageError(str(error)) from error
            raise


class MOSSAuthoringPage(io.ComfyNode):
    """A zero-inference selector: one page and one language produce one prompt."""

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="MOSSAuthoringPageT8", display_name="MOSS Authoring Page T8",
            category="T8/MOSS Image", description="Select one validated collection unit/language. No LLM, automatic translation or image generation. Only positive_prompt goes to MOSS.",
            inputs=[
                io.String.Input("bundle_json", display_name="完整集合 / Complete bundle", default="", multiline=True, dynamic_prompts=False,
                                tooltip="Paste a complete bundle for CPU-only use, or connect Director's bundle output. Not a positive prompt; JSON is never dynamic-prompt expanded."),
                io.Int.Input("page_index", display_name="页码 / Page (1-based)", default=1, min=1, max=contract.MAX_UNITS, step=1),
                io.Combo.Input("language", display_name="描述语言 / Language", options=["en", "zh"], default="en"),
            ], outputs=[
                io.String.Output(display_name="正向提示词 / positive_prompt"),
                io.Int.Output(display_name="宽 / width"), io.Int.Output(display_name="高 / height"),
                io.String.Output(display_name="实际格式 / resolved_format"),
                io.String.Output(display_name="原生可编辑草稿 / native_draft_json"),
                io.String.Output(display_name="选择报告 / report_json"),
                io.String.Output(display_name="漫画源 / source_json"),
                io.String.Output(display_name="英中阅读稿 / paired_reading"),
                io.String.Output(display_name="单元ID / unit_id"),
            ])

    @classmethod
    def validate_inputs(cls, bundle_json="", page_index=1, language="en", **kwargs):
        try:
            if page_index is not None and (type(page_index) is not int or not 1 <= page_index <= contract.MAX_UNITS):
                return "Page index must be 1–16 / 页码须为1–16。"
            if language is not None and language not in ("en", "zh"):
                return "Choose en or zh / 请选择en或zh。"
            if bundle_json is not None:
                contract.c.clean_text(bundle_json, "authoring bundle", limit=contract.MAX_BUNDLE_BYTES)
                if not bundle_json.strip(): return "Connect a complete authoring bundle / 请连接完整创作集合。"
            return True
        except contract.c.MossContractError as error:
            return str(error)

    @classmethod
    def execute(cls, bundle_json, page_index=1, language="en"):
        values = bundle.select(bundle_json, page_index, language)
        status = {"unit_id": values[8], "page_index": page_index, "language": language,
                  "width": values[1], "height": values[2], "logical_generation_calls": 0}
        return io.NodeOutput(*values, ui={"t8_moss_authoring_page_result": [json.dumps(status, ensure_ascii=False)]})
