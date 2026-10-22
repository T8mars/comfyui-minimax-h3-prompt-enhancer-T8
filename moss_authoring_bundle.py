"""Validated, in-memory MOSS collections and zero-inference page selection.

Only original source drafts are retained. Native positive prompts are compiled
on selection, never trusted from a cached model-facing string. No provider,
filesystem writes, ComfyUI runtime or image generation is involved here.
"""
from __future__ import annotations

import copy
import json
import re

try:
    from . import moss_authoring_contract as contract
    from . import moss_authoring as authoring
    from . import moss_image_contract as native
except ImportError:
    import moss_authoring_contract as contract
    import moss_authoring as authoring
    import moss_image_contract as native

SCHEMA = contract.SCHEMA
MAX_STAGE_RECORDS = 1 + 2 * contract.MAX_UNITS
MAX_GENERATION_CALLS = 2 * MAX_STAGE_RECORDS
_TOP = {"schema_version", "adapter_revision", "complete", "profile", "reference_mode", "units",
        "reference_map", "edited_unit_ids", "continuity_context", "report"}
_REPORT = {"logical_generation_calls", "chat_post_attempts", "correction_calls", "stage_records",
           "semantics_verified", "translation_quality", "bilingual_complete", "image_generation_performed"}
_SLOT = re.compile(r"reference_image_([0-9])\Z")
_SHA256 = re.compile(r"[A-Fa-f0-9]{64}\Z")


def _integer(value, minimum, maximum, code):
    if type(value) is not int or not minimum <= value <= maximum:
        native.fail(code, "Authoring integer is outside its safety range / 创作整数超出安全范围。")
    return value


def _references(rows):
    if not isinstance(rows, list) or len(rows) > 10:
        native.fail("invalid_reference_map", "Expected at most ten ordered references / 最多十张有序参考图。")
    positions = []
    for expected, row in enumerate(rows, 1):
        contract.fields(row, {"index", "source_slot", "batch_index", "sha256", "role"})
        if type(row["index"]) is not int or row["index"] != expected:
            native.fail("invalid_reference_map", "Reference indices must be sequential / 参考图序号须连续。")
        slot = row["source_slot"]
        match = _SLOT.fullmatch(slot) if isinstance(slot, str) else None
        if match is None:
            native.fail("invalid_reference_map", "Reference slot must be reference_image_0–9 / 参考图槽无效。")
        batch = _integer(row["batch_index"], 0, 9, "invalid_reference_map")
        if not isinstance(row["sha256"], str) or not _SHA256.fullmatch(row["sha256"]):
            native.fail("invalid_reference_map", "Reference digest must be SHA256 hex / 参考图摘要无效。")
        native.clean_text(row["role"], "reference role", limit=4096)
        positions.append((int(match.group(1)), batch))
    if positions != sorted(set(positions)):
        native.fail("invalid_reference_map", "Reference source/batch ordering is ambiguous / 参考图来源或批次顺序含歧义。")
    return len(rows)


def _units(bundle, reference_count):
    units, profile = bundle["units"], bundle["profile"]
    if not isinstance(units, list) or not 1 <= len(units) <= contract.MAX_UNITS:
        native.fail("invalid_unit_count", "A collection needs 1–16 units / 集合须含1–16个单元。")
    identifiers = []
    all_references = list(range(1, reference_count + 1))
    for expected, unit in enumerate(units, 1):
        if not isinstance(unit, dict):
            native.fail("invalid_authoring_unit", "A collection unit must be an object / 集合单元须为对象。")
        # This source-only explanation is intentionally not projected into the
        # native MOSS draft. Older contract revisions know only the base fields.
        base = {key: value for key, value in unit.items() if key not in ("reference_selection_reason", "lengths")}
        contract.validate_unit(base, profile, reference_count)
        if "lengths" in unit:
            contract.fields(unit["lengths"], set(unit["sources"]))
            for language, info in unit["lengths"].items():
                compiled = contract.compile_source(unit["sources"][language], width=unit["width"], height=unit["height"])
                authoring.validate_cached_authoring({"authoring_profile": profile, "authoring_revision": authoring.REVISION,
                    "authoring_length": info}, compiled)
                if language != "zh" and info["target_han_range"] is not None:
                    native.fail("invalid_language_length_target", "The automatic Han target applies only to Chinese / 自动汉字目标仅适用于中文描述。")
        if unit["index"] != expected:
            native.fail("invalid_unit_index", "Collection pages must be sequential / 集合页码须按顺序连续。")
        identifiers.append(unit["unit_id"])
        if "reference_selection_reason" in unit:
            native.clean_text(unit["reference_selection_reason"], "reference selection reason", limit=4096)
        if profile == authoring.COMIC and unit["reference_indices"] != all_references:
            reason = unit.get("reference_selection_reason", "")
            if not isinstance(reason, str) or not reason.strip():
                native.fail("unexplained_reference_subset", "A comic reference subset needs a reason / 漫画选择部分参考图须说明原因。")
    if len(identifiers) != len(set(identifiers)):
        native.fail("duplicate_unit_id", "Collection unit identities must be unique / 集合单元ID须唯一。")
    mode = bundle["reference_mode"]
    if profile == authoring.COMIC:
        if mode != "context":
            native.fail("invalid_reference_mode", "Comic references use context mode / 漫画参考图使用context模式。")
    elif mode == "independent":
        if len(units) != max(1, reference_count) or any(
            unit["reference_indices"] != ([index] if reference_count else []) for index, unit in enumerate(units, 1)
        ):
            native.fail("independent_reference_mismatch", "Independent references need one ordered unit each / 独立参考图须逐张对应单元。")
    elif mode == "fusion":
        if len(units) != 1 or units[0]["reference_indices"] != all_references:
            native.fail("fusion_reference_mismatch", "Fusion needs one unit using all references / 融合须由一个单元使用全部参考图。")
    else:
        native.fail("invalid_reference_mode", "Unsupported collection reference mode / 集合参考图方式无效。")
    return identifiers


def _stages(records, profile, unit_ids, edited_ids):
    if not isinstance(records, list) or len(records) > MAX_STAGE_RECORDS:
        native.fail("invalid_stage_records", "Authoring stage budget exceeded / 创作阶段超过安全预算。")
    seen_ids, seen_pairs = set(), set()
    total_calls = total_corrections = 0
    for position, record in enumerate(records):
        contract.fields(record, {"stage_id", "kind", "unit_id", "calls", "corrections"})
        key = contract.identifier(record["stage_id"])
        if key in seen_ids:
            native.fail("duplicate_stage_id", "Stage identities must be unique / 创作阶段ID须唯一。")
        seen_ids.add(key)
        kind, unit_id = record["kind"], record["unit_id"]
        if not isinstance(kind, str) or kind not in ("plan", "source", "translation"):
            native.fail("invalid_stage_kind", "Unknown authoring stage / 创作阶段类型无效。")
        if kind == "plan":
            if profile != authoring.COMIC or unit_id != "" or position != 0 or not edited_ids:
                native.fail("invalid_plan_stage", "Only an edited comic begins with one plan / 仅漫画编辑任务在首阶段规划。")
        else:
            contract.identifier(unit_id)
            if unit_id not in unit_ids or unit_id not in edited_ids:
                native.fail("invalid_stage_unit", "Stage unit is not in the edit scope / 创作阶段不属于编辑范围。")
            if kind == "translation" and ("source", unit_id) not in seen_pairs:
                native.fail("invalid_stage_order", "Translation must follow its source stage / 翻译须在对应源稿之后。")
        pair = kind, unit_id
        if pair in seen_pairs:
            native.fail("duplicate_stage", "A unit stage cannot be counted twice / 同一单元阶段不能重复计数。")
        seen_pairs.add(pair)
        calls = _integer(record["calls"], 1, 2, "invalid_stage_counts")
        corrections = _integer(record["corrections"], 0, 1, "invalid_stage_counts")
        if corrections != calls - 1:
            native.fail("invalid_stage_counts", "Stage calls and corrections disagree / 阶段调用数与纠正数不符。")
        total_calls += calls
        total_corrections += corrections
    expected = {("source", key) for key in edited_ids}
    if profile == authoring.COMIC and edited_ids:
        expected |= {("plan", "")} | {("translation", key) for key in edited_ids}
    if not expected <= seen_pairs:
        native.fail("incomplete_stages", "Completed collection is missing required stages / 完整集合缺少必要创作阶段。")
    if profile == authoring.FISHER and any(kind == "translation" for kind, _key in seen_pairs):
        # A supplied bilingual Fisher source may be retained, but this first
        # generation contract promises one selected-language source per unit.
        native.fail("unexpected_fisher_translation", "Fisher collection generation is single-language / Fisher集合生成使用所选单语言。")
    return total_calls, total_corrections


def validate_bundle(bundle_or_json):
    """Validate the WHOLE collection before returning a detached JSON value."""
    bundle = contract.parse(bundle_or_json) if isinstance(bundle_or_json, str) else contract.parse(contract.encode(bundle_or_json))
    contract.fields(bundle, _TOP)
    if bundle["schema_version"] != SCHEMA or bundle["adapter_revision"] != authoring.REVISION or bundle["complete"] is not True:
        native.fail("incomplete_authoring_bundle", "Collection is incomplete or incompatible / 创作集合不完整或版本不兼容。")
    profile = authoring.validate_profile(bundle["profile"])
    if profile == authoring.CLASSIC:
        native.fail("invalid_collection_profile", "Classic does not use collection authoring / 原版不使用集合接口。")
    reference_count = _references(bundle["reference_map"])
    unit_ids = _units(bundle, reference_count)
    native.clean_text(bundle["continuity_context"], "continuity context", limit=64000)
    edited = bundle["edited_unit_ids"]
    if not isinstance(edited, list):
        native.fail("invalid_edit_scope", "Edit scope must list stable unit IDs / 编辑范围须列出稳定单元ID。")
    for key in edited: contract.identifier(key)
    if len(edited) != len(set(edited)) or any(key not in unit_ids for key in edited):
        native.fail("invalid_edit_scope", "Edit scope is duplicated or outside the collection / 编辑范围重复或超出集合。")
    if profile == authoring.COMIC and any(unit["available_languages"] != ["en", "zh"] for unit in bundle["units"] if unit["unit_id"] in edited):
        native.fail("incomplete_bilingual_unit", "Each edited comic page needs English and Chinese / 每个编辑漫画页须有完整英中双语。")
    report = bundle["report"]
    contract.fields(report, _REPORT)
    calls, corrections = _stages(report["stage_records"], profile, unit_ids, edited)
    _integer(report["logical_generation_calls"], 0, MAX_GENERATION_CALLS, "invalid_collection_counts")
    _integer(report["correction_calls"], 0, MAX_STAGE_RECORDS, "invalid_collection_counts")
    _integer(report["chat_post_attempts"], 0, calls, "invalid_collection_counts")
    bilingual = profile == authoring.COMIC and all(unit["available_languages"] == ["en", "zh"] for unit in bundle["units"])
    if (report["logical_generation_calls"] != calls or report["correction_calls"] != corrections
            or report["semantics_verified"] is not False or report["image_generation_performed"] is not False
            or report["translation_quality"] != "unverified" or type(report["bilingual_complete"]) is not bool
            or report["bilingual_complete"] != bilingual):
        native.fail("invalid_collection_report", "Collection report disagrees with actual sources/stages / 集合报告与实际源稿或阶段不符。")
    return bundle


validate = validate_bundle


def build_bundle(profile, reference_mode, units, reference_map, edited_unit_ids, continuity_context, stage_records, chat_post_attempts):
    """Derive report counts from finite stage records, then validate everything."""
    # Validate records before summing: booleans or malformed values must not be
    # silently promoted by Python arithmetic into trustworthy execution counts.
    profile = authoring.validate_profile(profile)
    if profile == authoring.CLASSIC:
        native.fail("invalid_collection_profile", "Classic does not use collection authoring / 原版不使用集合接口。")
    if not isinstance(units, list) or not 1 <= len(units) <= contract.MAX_UNITS:
        native.fail("invalid_unit_count", "Collection units must be an array / 集合单元须为数组。")
    if not isinstance(edited_unit_ids, list):
        native.fail("invalid_edit_scope", "Edit scope must be an array / 编辑范围须为数组。")
    unit_ids = []
    for unit in units:
        if not isinstance(unit, dict):
            native.fail("invalid_authoring_unit", "A collection unit must be an object / 集合单元须为对象。")
        unit_ids.append(contract.identifier(unit.get("unit_id")))
    for key in edited_unit_ids: contract.identifier(key)
    if len(unit_ids) != len(set(unit_ids)):
        native.fail("duplicate_unit_id", "Collection unit identities must be unique / 集合单元ID须唯一。")
    if len(edited_unit_ids) != len(set(edited_unit_ids)) or any(key not in unit_ids for key in edited_unit_ids):
        native.fail("invalid_edit_scope", "Edit scope is duplicated or outside the collection / 编辑范围重复或超出集合。")
    calls, corrections = _stages(stage_records, profile, unit_ids, edited_unit_ids)
    bilingual = profile == authoring.COMIC and all(isinstance(unit, dict) and unit.get("available_languages") == ["en", "zh"] for unit in units)
    bundle = {"schema_version": SCHEMA, "adapter_revision": authoring.REVISION, "complete": True,
        "profile": profile, "reference_mode": reference_mode, "units": copy.deepcopy(units),
        "reference_map": copy.deepcopy(reference_map), "edited_unit_ids": list(edited_unit_ids),
        "continuity_context": continuity_context, "report": {"logical_generation_calls": calls,
            "chat_post_attempts": chat_post_attempts, "correction_calls": corrections,
            "stage_records": copy.deepcopy(stage_records), "semantics_verified": False,
            "translation_quality": "unverified", "bilingual_complete": bilingual, "image_generation_performed": False}}
    return validate_bundle(bundle)


def _unit_reading(unit):
    chunks = [f"Page {unit['index']} / {unit['width']} × {unit['height']} / {unit['unit_id']}"]
    for language, heading in (("en", "English / en"), ("zh", "中文 / zh")):
        if language in unit["sources"]:
            chunks.append(heading + "\n```json\n" + json.dumps(unit["sources"][language], ensure_ascii=False, indent=2, allow_nan=False) + "\n```")
    return "\n\n".join(chunks)


def readable(bundle):
    checked = validate_bundle(bundle)
    return "\n\n".join(_unit_reading(unit) for unit in checked["units"])


def select(bundle_or_json, index, language):
    """Return one native prompt and original source; never infer or fall back."""
    bundle = validate_bundle(bundle_or_json)
    _integer(index, 1, len(bundle["units"]), "invalid_selected_unit")
    if not isinstance(language, str) or language not in ("en", "zh"):
        native.fail("invalid_selected_language", "Select en or zh / 请选择en或zh。")
    unit = bundle["units"][index - 1]
    if language not in unit["sources"]:
        native.fail("missing_selected_language", "Selected unit has no requested language / 所选单元没有此语言，不会自动翻译或回退。")
    source = unit["sources"][language]
    historical_max = unit["lengths"][language]["max_output_chars"] if "lengths" in unit else 0
    compiled = contract.compile_source(source, width=unit["width"], height=unit["height"], max_chars=historical_max)
    report = {"schema_version": "t8-moss-authoring-selection-report/v1", "adapter_revision": authoring.REVISION,
        "profile": bundle["profile"], "reference_mode": bundle["reference_mode"], "unit_id": unit["unit_id"],
        "index": index, "language": language, "available_languages": unit["available_languages"],
        "reference_indices": unit["reference_indices"], "resolved_format": compiled[3],
        "canvas": {"width": compiled[1], "height": compiled[2]}, "logical_generation_calls": 0,
        "chat_post_attempts": 0, "correction_calls": 0,
        "source_bundle_generation_calls": bundle["report"]["logical_generation_calls"],
        "semantics_verified": False, "translation_quality": "unverified", "image_generation_performed": False,
        **compiled[5]}
    if "lengths" in unit:
        report.update(authoring_profile=bundle["profile"], authoring_revision=authoring.REVISION,
                      authoring_length=copy.deepcopy(unit["lengths"][language]))
    return (*compiled[:5], contract.encode(report), contract.encode(source), _unit_reading(unit), unit["unit_id"])
