"""Lossless comic sources, caption-only translation and collection contracts.

No providers/tools. The pinned native compiler accepts only object/character/
text: retain comic_panel in the source, project a COPY solely for compilation.
"""
from __future__ import annotations

from collections import Counter
import copy
import json
import re

try:
    from . import moss_image_contract as c
    from . import moss_authoring as a
except ImportError:
    import moss_image_contract as c
    import moss_authoring as a

SCHEMA = "t8-moss-authoring-bundle/v1"
MAX_BUNDLE_BYTES = 2 * 1024 * 1024
MAX_UNITS = 16
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}\Z")
_SIGNATURE = {"topology", "emphasis", "framing_progression", "viewpoint", "blocking", "density", "entry_exit", "information_rhythm"}


def fields(value, required, optional=(), *, code="invalid_authoring_structure"):
    if not isinstance(value, dict) or not set(required) <= set(value) or set(value) - set(required) - set(optional):
        c.fail(code, "Authoring fields are missing or unknown / 创作结构缺字段或含未知字段。")


def identifier(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        c.fail("invalid_authoring_id", "Expected a bounded stable identifier / 需要有限长度稳定ID。")
    return value


def encode(value):
    try:
        text = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (ValueError, TypeError, RecursionError):
        c.fail("invalid_authoring_json", "Authoring data is not finite JSON / 创作数据不是有限JSON。")
    c.clean_text(text, "authoring bundle", limit=MAX_BUNDLE_BYTES)
    return text


def parse(text):
    c.clean_text(text, "authoring bundle", limit=MAX_BUNDLE_BYTES)
    try:
        value = json.loads(text, object_pairs_hook=c._unique, parse_constant=c._constant)
    except (ValueError, RecursionError) as error:
        if isinstance(error, c.MossContractError): raise
        c.fail("invalid_authoring_json", "Expected one complete authoring JSON / 需要一个完整创作JSON。")
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        if depth > 20:
            c.fail("input_budget", "Authoring nesting budget exceeded / 创作数据嵌套过深。")
        if isinstance(item, str): c.clean_text(item, "authoring field")
        if isinstance(item, dict): stack.extend((v, depth + 1) for pair in item.items() for v in pair)
        if isinstance(item, list):
            if len(item) > c.MAX_ITEMS: c.fail("input_budget", "Authoring array budget exceeded / 创作数组超过预算。")
            stack.extend((v, depth + 1) for v in item)
    return value


def native_projection(source):
    # Apply the per-source native 256KiB limit, Unicode/duplicate/nonfinite guards
    # BEFORE dereferencing model-generated fields. Never reverse-infer a panel
    # from the ordinary object's tags; source label is authoritative.
    source = c.strict_json(encode(source))
    projected = copy.deepcopy(source)
    if isinstance(projected, dict) and isinstance(projected.get("items"), list):
        for item in projected["items"]:
            if isinstance(item, dict) and item.get("label") == "comic_panel":
                item["label"] = "object"
                tags = item.get("tags", [])
                if not isinstance(tags, list): c.fail("invalid_panel_tags", "Panel tags must be an array / 画框tags须为数组。")
                item["tags"] = tags if "comic_panel" in tags else [*tags, "comic_panel"]
    return projected


def compile_source(source, *, width, height, locked_text="", max_chars=0):
    return c.compile_draft(native_projection(source), width=width, height=height,
                           locked_text=locked_text, max_chars=max_chars)


def visible_blocks(source):
    return [item["text"] for item in source.get("items", []) if "text" in item]


def without_captions(source):
    result = copy.deepcopy(source)
    if "caption" in result:
        result["caption"] = ""
    else:
        result["summary"]["caption"] = ""
        for item in result["items"]: item["caption"] = ""
    return result


def same_json(left, right):
    """JSON equality with strict number/bool and container types."""
    if type(left) is not type(right): return False
    if isinstance(left, dict): return set(left) == set(right) and all(same_json(left[k], right[k]) for k in left)
    if isinstance(left, list): return len(left) == len(right) and all(same_json(x, y) for x, y in zip(left, right))
    return left == right


def validate_sidecar(source, sidecar):
    fields(sidecar, {"item_ids", "panel_order", "membership", "devices", "intensity", "layout_signature", "state"})
    items = source.get("items")
    if not isinstance(items, list): c.fail("invalid_comic_layout", "Comic collection requires Layout / 漫画整册需要Layout。")
    ids = sidecar["item_ids"]
    if not isinstance(ids, list) or len(ids) != len(items): c.fail("invalid_item_ids", "Item identities must match items / 元素ID必须逐项对应。")
    for key in ids: identifier(key)
    if len(ids) != len(set(ids)): c.fail("duplicate_item_id", "Duplicate item identity / 元素ID重复。")
    panels = [key for key, item in zip(ids, items) if item["label"] == "comic_panel"]
    order = sidecar["panel_order"]
    if (not panels or source["summary"].get("canvas") != "multi_panel" or not isinstance(order, list)
            or any(not isinstance(key, str) for key in order) or Counter(order) != Counter(panels)):
        c.fail("invalid_panel_order", "Panel reading order must cover the source panels once / 读序须恰好覆盖所有画框。")
    membership = sidecar["membership"]
    fields(membership, set(ids) - set(panels))
    for record in membership.values():
        fields(record, {"panel_ids", "global_overlay"})
        parents = record["panel_ids"]
        if (type(record["global_overlay"]) is not bool or not isinstance(parents, list)
                or any(not isinstance(key, str) or key not in panels for key in parents)
                or len(set(parents)) != len(parents)
                or (not parents and not record["global_overlay"]) or (parents and record["global_overlay"])):
            c.fail("invalid_panel_membership", "Element panel ownership is incomplete / 元素画框归属无效。")
    devices = sidecar["devices"]
    if not isinstance(devices, list) or len(devices) > 50: c.fail("invalid_comic_devices", "Invalid comic device list / 手法列表无效。")
    seen = set()
    for device in devices:
        fields(device, {"id", "reason"})
        if type(device["id"]) is not int or not 1 <= device["id"] <= 50 or device["id"] in seen:
            c.fail("invalid_comic_devices", "Device IDs must be distinct 1–50 / 手法编号须为不重复1–50。")
        seen.add(device["id"])
        c.clean_text(device["reason"], "device reason", limit=1024)
    if sidecar["intensity"] not in ("quiet", "turning", "intense"):
        c.fail("invalid_comic_intensity", "Invalid narrative intensity / 叙事强度无效。")
    signature = sidecar["layout_signature"]
    fields(signature, _SIGNATURE | {"panel_count"})
    if type(signature["panel_count"]) is not int or signature["panel_count"] != len(panels):
        c.fail("invalid_layout_signature", "Signature panel count differs / 版式摘要画框数不符。")
    for key in _SIGNATURE: c.clean_text(signature[key], "layout signature", limit=2048)
    state = sidecar["state"]
    fields(state, {"identity_anchors", "scene_anchors", "current_state"})
    for mapping in state.values():
        if not isinstance(mapping, dict) or len(mapping) > 32: c.fail("input_budget", "Continuity state budget exceeded / 连续性状态超预算。")
        for key, value in mapping.items():
            identifier(key); c.clean_text(value, "continuity state", limit=4096)
    return sidecar


def translate(source, item_ids, mapping):
    """Only captions enter the translation response: geometry cannot drift."""
    result = copy.deepcopy(source)
    if "caption" in source:
        fields(mapping, {"caption"})
        c.clean_text(mapping["caption"], "translation")
        if not mapping["caption"].strip(): c.fail("empty_translation", "Empty translation / 译文为空。")
        result["caption"] = mapping["caption"]
    else:
        fields(mapping, {"summary_caption", "item_captions"})
        if (not isinstance(item_ids, list) or any(not isinstance(key, str) or not _ID.fullmatch(key) for key in item_ids)
                or len(item_ids) != len(source["items"]) or len(set(item_ids)) != len(item_ids)):
            c.fail("invalid_item_ids", "Invalid translation item identities / 翻译元素ID无效。")
        fields(mapping["item_captions"], set(item_ids))
        values = [mapping["summary_caption"], *mapping["item_captions"].values()]
        for value in values:
            c.clean_text(value, "translation")
            if not value.strip(): c.fail("empty_translation", "Empty translation / 译文为空。")
        result["summary"]["caption"] = mapping["summary_caption"]
        for key, item in zip(item_ids, result["items"]): item["caption"] = mapping["item_captions"][key]
        # Guard only whole known visible blocks explicitly quoted in a source
        # caption. This is a limited literal check, not translation semantics.
        blocks = visible_blocks(source)
        before_captions = [source["summary"]["caption"], *[item["caption"] for item in source["items"]]]
        after_captions = [result["summary"]["caption"], *[item["caption"] for item in result["items"]]]
        for before, after in zip(before_captions, after_captions):
            quoted = re.findall(r'"([^"\n]*(?:\n[^"\n]*)*)"|“([^”]*)”|‘([^’]*)’', before)
            references = [text for group in quoted for text in group if text and text in blocks]
            if references and not c._caption_blocks_match(after, references):
                c.fail("translated_visible_literal", "Translation changed quoted visible text / 翻译改变描述中引用的可见原文。")
    if not same_json(without_captions(source), without_captions(result)):
        c.fail("translation_geometry_changed", "Translation changed fixed structure / 翻译改变固定结构。")
    return result


def validate_revision(source, baseline, sidecar, baseline_sidecar, mode):
    if mode not in ("full_layout", "panels_only"):
        c.fail("invalid_layout_mode", "Unknown fixed-layout mode / 固定布局方式无效。")
    if Counter(visible_blocks(source)) != Counter(visible_blocks(baseline)):
        c.fail("locked_text_mismatch", "Revision changed exact visible text blocks / 修订改变可见文字块。")
    if mode == "full_layout":
        if not same_json(without_captions(source), without_captions(baseline)):
            c.fail("fixed_layout_changed", "Revision changed fixed non-caption fields / 修订改变固定布局字段。")
        if sidecar["item_ids"] != baseline_sidecar["item_ids"] or sidecar["membership"] != baseline_sidecar["membership"]:
            c.fail("fixed_layout_changed", "Revision changed fixed item identities / 修订改变固定元素身份。")
    else:
        def panels(value, meta):
            return [{"id": key, "geometry": without_caption(item)} for key, item in zip(meta["item_ids"], value["items"]) if item["label"] == "comic_panel"]
        if not same_json(panels(source, sidecar), panels(baseline, baseline_sidecar)):
            c.fail("fixed_panels_changed", "Revision changed fixed panel frames / 修订改变固定画框。")
        if (source["width"], source["height"], source["bbox_coord_space"], source["bbox_format"]) != (baseline["width"], baseline["height"], baseline["bbox_coord_space"], baseline["bbox_format"]):
            c.fail("fixed_panels_changed", "Revision changed fixed canvas / 修订改变固定画布。")
    if sidecar["panel_order"] != baseline_sidecar["panel_order"]:
        c.fail("fixed_panels_changed", "Revision changed fixed reading order / 修订改变固定读序。")


def without_caption(item):
    return {key: value for key, value in item.items() if key != "caption"}


def validate_unit(unit, profile, reference_count):
    if a.validate_profile(profile) == a.CLASSIC:
        c.fail("invalid_collection_profile", "Classic is not a collection profile / 原版不使用整册接口。")
    fields(unit, {"unit_id", "index", "width", "height", "reference_indices", "available_languages", "sources", "sidecar"},
           {"reference_selection_reason", "lengths"})
    identifier(unit["unit_id"])
    if type(unit["index"]) is not int or not 1 <= unit["index"] <= MAX_UNITS:
        c.fail("invalid_unit_index", "Invalid page index / 页码无效。")
    c.canvas(unit["width"], unit["height"])
    refs = unit["reference_indices"]
    if (not isinstance(refs, list) or any(type(n) is not int or not 1 <= n <= reference_count for n in refs)
            or refs != sorted(set(refs))):
        c.fail("invalid_reference_indices", "Invalid ordered image mapping / 参考图映射无效。")
    sources = unit["sources"]
    if "reference_selection_reason" in unit:
        c.clean_text(unit["reference_selection_reason"], "reference selection reason", limit=4096)
    if not isinstance(sources, dict) or not sources or set(sources) - {"en", "zh"}:
        c.fail("invalid_languages", "Expected explicit en/zh source languages / 源语言须明确en/zh。")
    if unit["available_languages"] != [key for key in ("en", "zh") if key in sources]:
        c.fail("invalid_languages", "Available languages differ from actual sources / 声明语言与实际源不符。")
    for source in sources.values():
        compile_source(source, width=unit["width"], height=unit["height"])
        if profile == a.COMIC: validate_sidecar(source, unit["sidecar"])
        else:
            if unit["sidecar"] is not None:
                c.fail("unexpected_sidecar", "Fisher units have no comic sidecar / Fisher单元不带漫画规划。")
            # The comic source vocabulary is only valid together with its
            # identity/membership sidecar, never as a bare Fisher native draft.
            c.compile_draft(source, width=unit["width"], height=unit["height"])
    if len(sources) == 2 and not same_json(without_captions(sources["en"]), without_captions(sources["zh"])):
        c.fail("translation_geometry_changed", "Paired sources differ outside captions / 双语源除描述外不一致。")
    if "lengths" in unit:
        fields(unit["lengths"], set(sources))
        for language, source in sources.items():
            compiled = compile_source(source, width=unit["width"], height=unit["height"])
            a.validate_cached_authoring({"authoring_profile": profile, "authoring_revision": a.REVISION,
                                        "authoring_length": unit["lengths"][language]}, compiled)
    return unit
