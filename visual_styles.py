"""Independent, opt-in color and creator presentation resources.

No media uploads, generation, source-directory access or model protocol changes.
The config carries identity, not arbitrary instructions; consumers resolve the
same immutable, content-checked packaged resource as the selector nodes.
"""
from __future__ import annotations

import hashlib
import colorsys
import json
import math
from pathlib import Path
import re
from typing import Any

REVISION = "1.0.0"
# Resource/config identity stays stable; compilation policy has its own cache revision.
INSTRUCTION_REVISION = "1.0.3"
OFF = "关闭 / Off"
ON = "开启 / On"
ON_EXPERIMENTAL = "开启（H3强化试验） / On (H3 experimental)"
MODES = [OFF, ON, ON_EXPERIMENTAL]
NONE = "未选择 / None"
COLOR_ONLY = "仅色彩 / Color only"
COLOR_LIGHT = "色彩 + 光影 / Color + lighting"
SCOPES = [COLOR_ONLY, COLOR_LIGHT]
SCOPE_IDS = {COLOR_ONLY: "color_only", COLOR_LIGHT: "color_and_light"}
MISSING = object()
ROOT = Path(__file__).resolve().parent / "resources" / "visual_styles"
CATALOG_SCHEMA = "t8-visual-style-catalog/v1"
COLOR_SCHEMA = "t8-color-style-config/v1"
CREATOR_SCHEMA = "t8-creator-style-config/v1"
# Keep ordinary On requests byte-identical; only the new opt-in mode uses v1.0.3.
MARKER = "T8 OPTIONAL VISUAL PRESENTATION v1.0.2"
EXPERIMENTAL_MARKER = "T8 OPTIONAL VISUAL PRESENTATION v1.0.3"
H3_STYLE_EXECUTION_MARKER = "H3 VISUAL STYLE EXECUTION CHECK"
REPAIR_STYLE_SCOPE = (
    "VISUAL STYLE LANGUAGE-REPAIR SCOPE: this is translation of the supplied draft, not a new style-generation pass. "
    "Translate its existing color and presentation descriptions faithfully; do not add a missing palette, camera method, "
    "object, cut or action to satisfy the earlier generation guide or selected-style reminder. "
    "Preserve the draft's facts, ordering, exact dialogue, native fields and technical tokens."
)
IDS = frozenset(f"{n:03d}" for n in range(1, 201))
DIMENSIONS = {"framing", "camera", "staging", "rhythm", "information", "editing"}
REVIEW_CODES = {"source_examples_excluded", "external_protocol_excluded", "color_kept_separate",
                "conflicting_avoid_excluded", "generic_avoid_excluded", "limited_method_specificity",
                "source_role_corrected"}
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_HEX = re.compile(r"#[0-9A-Fa-f]{6}\Z")


def _error():
    return ValueError("色彩/导演资源或配置无效；请重新选择或重装插件。 / Invalid visual style resource or config; select again or reinstall.")


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise _error()
        result[key] = value
    return result


def _read(path: Path, limit: int):
    try:
        with path.open("rb") as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise _error()
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(_error()))
        return data, hashlib.sha256(raw).hexdigest()
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise _error() from error


def _text(value, maximum=700):
    return type(value) is str and 0 < len(value) <= maximum and value.strip() == value and not any(
        ord(c) < 32 and c not in "\n\t" for c in value)


def _bilingual(value):
    return type(value) is dict and set(value) == {"zh", "en"} and all(_text(s) for s in value.values())


def load_catalog():
    data, digest = _read(ROOT / "catalog.json", 192 * 1024)
    if (type(data) is not dict or set(data) != {"schema_version", "revision", "entries"}
            or data["schema_version"] != CATALOG_SCHEMA or data["revision"] != REVISION
            or type(data["entries"]) is not list or len(data["entries"]) != 200):
        raise _error()
    fields = {"id", "label_zh", "label_en", "category", "creator_role", "color_revision",
              "color_sha256", "creator_revision", "creator_sha256"}
    seen = set()
    for entry in data["entries"]:
        if (type(entry) is not dict or set(entry) != fields or type(entry["id"]) is not str
                or entry["id"] not in IDS or entry["id"] in seen
                or any(not _text(entry[k], 160) for k in ("label_zh", "label_en", "category"))
                or type(entry["creator_role"]) is not str or entry["creator_role"] not in {"director", "cinematographer", "art_director", "team"}
                or any(entry[k] != REVISION for k in ("color_revision", "creator_revision"))
                or any(type(entry[k]) is not str or not _SHA.fullmatch(entry[k]) for k in ("color_sha256", "creator_sha256"))):
            raise _error()
        seen.add(entry["id"])
    return data, digest


def selection_label(entry):
    return f"{entry['id']} {entry['label_zh']} / {entry['label_en']}"


def style_options():
    return [NONE] + [selection_label(row) for row in load_catalog()[0]["entries"]]


def _entry(selection):
    if type(selection) is not str:
        raise _error()
    for row in load_catalog()[0]["entries"]:
        if selection in (row["id"], selection_label(row)):
            return row
    raise ValueError("请先选择一个有效风格编号。 / Select a valid style before enabling it.")


def load_resource(kind: str, selection):
    if type(kind) is not str or kind not in {"color", "creator"}:
        raise _error()
    entry = _entry(selection)
    data, digest = _read(ROOT / ("colors" if kind == "color" else "creators") / (entry["id"] + ".json"), 24 * 1024)
    common = {"schema_version", "id", "revision"}
    extra = {"primary", "accents", "color_notes", "lighting_notes"} if kind == "color" else {"methods", "review_notes"}
    if (type(data) is not dict or set(data) != common | extra
            or data["schema_version"] != f"t8-{kind}-style-resource/v1"
            or data["id"] != entry["id"] or data["revision"] != entry[kind + "_revision"]
            or digest != entry[kind + "_sha256"]):
        raise _error()
    if kind == "color":
        if (type(data["primary"]) is not list or len(data["primary"]) != 6
                or type(data["accents"]) is not list or len(data["accents"]) != 4
                or not _bilingual(data["color_notes"]) or not _bilingual(data["lighting_notes"])):
            raise _error()
        for group, prefix in (("primary", "C"), ("accents", "E")):
            for n, color in enumerate(data[group], 1):
                expected = {"code", "name_zh", "name_en", "hex"} | ({"share"} if group == "primary" else set())
                if (type(color) is not dict or set(color) != expected or color["code"] != f"{prefix}{n:02d}"
                        or not all(_text(color[k], 120) for k in ("name_zh", "name_en"))
                        or type(color["hex"]) is not str or not _HEX.fullmatch(color["hex"])):
                    raise _error()
                if group == "primary" and (type(color["share"]) not in (int, float)
                        or not 0 < color["share"] <= 1 or not math.isfinite(color["share"])):
                    raise _error()
        if not math.isclose(sum(c["share"] for c in data["primary"]), 1, abs_tol=1e-6):
            raise _error()
    else:
        if (type(data["methods"]) is not list or not 1 <= len(data["methods"]) <= 8
                or type(data["review_notes"]) is not list or len(data["review_notes"]) > 20
                or not all(type(s) is str and s in REVIEW_CODES for s in data["review_notes"])):
            raise _error()
        for method in data["methods"]:
            if (type(method) is not dict or set(method) != {"dimension", "text_zh", "text_en", "requires_cuts"}
                    or type(method["dimension"]) is not str or method["dimension"] not in DIMENSIONS or type(method["requires_cuts"]) is not bool
                    or not _text(method["text_zh"], 500) or not _text(method["text_en"], 500)):
                raise _error()
        if all(m["requires_cuts"] for m in data["methods"]):
            raise _error()
    return data, entry, digest


def build_style_config(kind, mode=OFF, selection=NONE, scope=COLOR_ONLY):
    if type(kind) is not str or kind not in {"color", "creator"} or type(mode) is not str or mode not in MODES:
        raise _error()
    result = {"schema_version": COLOR_SCHEMA if kind == "color" else CREATOR_SCHEMA, "mode": "off"}
    if mode == OFF:
        return result
    resource, entry, digest = load_resource(kind, selection)
    result.update(mode="on_experimental" if mode == ON_EXPERIMENTAL else "on", style_id=entry["id"], resource_revision=resource["revision"],
                  resource_sha256=digest, adapter_revision=REVISION)
    if kind == "color":
        if type(scope) is not str or scope not in SCOPE_IDS:
            raise _error()
        result["scope"] = SCOPE_IDS[scope]
    return result


def resolve_style_config(value, kind):
    if type(kind) is not str or kind not in {"color", "creator"}:
        raise _error()
    if value is None:
        return None
    schema = COLOR_SCHEMA if kind == "color" else CREATOR_SCHEMA
    if (kind not in {"color", "creator"} or type(value) is not dict
            or value.get("schema_version") != schema or value.get("mode") not in ("off", "on", "on_experimental")):
        raise _error()
    if value["mode"] == "off":
        if set(value) != {"schema_version", "mode"}:
            raise _error()
        return None
    expected = {"schema_version", "mode", "style_id", "resource_revision", "resource_sha256", "adapter_revision"}
    if kind == "color":
        expected.add("scope")
    if set(value) != expected or any(type(v) is not str for v in value.values()):
        raise _error()
    scope = next((label for label, key in SCOPE_IDS.items() if key == value.get("scope")), None)
    if kind == "color" and scope is None:
        raise _error()
    mode = ON_EXPERIMENTAL if value["mode"] == "on_experimental" else ON
    canonical = build_style_config(kind, mode, value["style_id"], scope or COLOR_ONLY)
    if value != canonical:
        raise _error()
    return canonical


def resolve_color_style(value=None):
    return resolve_style_config(value, "color")


def resolve_creator_style(value=None):
    return resolve_style_config(value, "creator")


def active_config_kwargs(color=None, creator=None):
    return {key: value for key, value in (("color_style_config", color), ("creator_style_config", creator)) if value is not None}


def style_metadata(color=None, creator=None):
    result = {}
    for kind, config in (("color", resolve_color_style(color)), ("creator", resolve_creator_style(creator))):
        if config is not None:
            result[kind + "_style"] = {k: v for k, v in config.items() if k not in {"schema_version", "mode"}}
            if config["mode"] == "on_experimental":
                result[kind + "_style"]["execution_mode"] = "h3_experimental"
    return result


def safe_style_metadata(values):
    """Historical finite identities survive missing resources; never load catalog."""
    if type(values) is not dict:
        return {}
    result = {}
    for kind in ("color", "creator"):
        block = values.get(kind + "_style")
        fields = {"style_id", "resource_revision", "resource_sha256", "adapter_revision"} | ({"scope"} if kind == "color" else set())
        if type(block) is dict and "execution_mode" in block:
            if block["execution_mode"] != "h3_experimental":
                continue
            fields.add("execution_mode")
        if (type(block) is dict and set(block) == fields and all(type(v) is str for v in block.values())
                and block["style_id"] in IDS and block["resource_revision"] == REVISION
                and block["adapter_revision"] == REVISION and _SHA.fullmatch(block["resource_sha256"])
                and (kind != "color" or block["scope"] in SCOPE_IDS.values())):
            result[kind + "_style"] = dict(block)
    return result


def helper_fingerprint(kind, mode, selection, scope=COLOR_ONLY):
    if mode == OFF:
        return "visual-style-off"
    config = build_style_config(kind, mode, selection, scope)
    return (REVISION, INSTRUCTION_REVISION, load_catalog()[1], json.dumps(config, sort_keys=True))


def consumer_fingerprint(color=MISSING, creator=MISSING, recovery_action="normal"):
    if recovery_action == "restore_last" or (color is MISSING and creator is MISSING):
        return False  # Same sentinel as a node without an IS_CHANGED override.
    base = ("t8-visual-catalog", REVISION, INSTRUCTION_REVISION, load_catalog()[1])
    # Linked inputs may still be unresolved here; validation happens before use.
    experimental = tuple(type(config) is dict and config.get("mode") == "on_experimental"
                         for config in (color, creator))
    return base + ("h3-experimental", *experimental) if any(experimental) else base


def _hue_description(hex_value):
    """Neutral color words from validated RGB, never thematic/emotional swatch names."""
    rgb = [int(hex_value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    hue, lightness, saturation = colorsys.rgb_to_hls(*rgb)
    if saturation < 0.12:
        if lightness < 0.15:
            return "黑色 / black"
        if lightness > 0.85:
            return "白色 / white"
        if lightness < 0.35:
            return "深灰色 / dark gray"
        if lightness > 0.65:
            return "浅灰色 / light gray"
        return "灰色 / gray"
    for bound, zh, en in ((15, "红色", "red"), (45, "橙色", "orange"), (70, "黄色", "yellow"),
                          (100, "黄绿色", "yellow green"), (165, "绿色", "green"),
                          (190, "青绿色", "teal"), (210, "青蓝色", "cyan blue"),
                          (255, "蓝色", "blue"), (290, "紫色", "purple"),
                          (335, "紫红色", "magenta"), (361, "红色", "red")):
        if hue * 360 < bound:
            break
    if lightness < 0.25:
        zh, en = "深" + zh, "deep " + en
    elif lightness > 0.78:
        zh, en = "浅" + zh, "pale " + en
    if saturation < 0.25:
        zh, en = "灰调" + zh, "muted " + en
    return zh + " / " + en


def _experimental_enabled(color, creator):
    return any(config is not None and config["mode"] == "on_experimental" for config in (color, creator))


def visual_style_instruction(color=None, creator=None, target="h3", *, fixed_shot_count=0):
    color, creator = resolve_color_style(color), resolve_creator_style(creator)
    if color is None and creator is None:
        return ""
    if target not in {"h3", "seedance20"}:
        raise _error()
    marker = EXPERIMENTAL_MARKER if target == "h3" and _experimental_enabled(color, creator) else MARKER
    lines = [marker + " (independently adapted, experimental; not an extra planning pass).",
        "ENABLED STYLE APPLICATION: these connected selections are explicit requests to shape the existing scene, not background metadata. Apply each enabled dimension concretely in the final visual description wherever its own compatible opportunity exists. Do not silently skip both selections because the draft already reads fluently or the acting is detailed. If an applicable method or palette relationship is already present, retain its explicit visual evidence rather than adding redundant wording.",
        "Existing scene-directing Skills own scene strategy; acting/Bibles, storyboard, combat and reference contracts retain their roles. User facts, exact dialogue/text/speaker, identity, media roles, source action order, fixed timing/count, framing locks and ending take priority. These modifiers grant no new story authorship. A generic default such as natural/vlog styling, or an unrequested choice made in a draft, is not a user lock. Distinguish reference identity from background/style retention according to the actual asset role; never treat a first/last-frame or explicitly retained attribute as freely editable.",
        "COORDINATE DIMENSIONS: an acting instruction to leave unrelated visuals alone limits changes made for acting alone; it does not cancel these separately enabled color/presentation requests. Apply color to eligible existing visual areas and creator methods to eligible presentation while retaining the acting beats. Conversely, color/creator selection must not replace performance, alter dialogue, or bypass an explicit lock.",
        "Retain the native output grammar and current language. Change neither target duration nor shot count; impose no duration cap, automatic segmentation, new sound, subtitle, character, object, location, era, rendering medium or freeze ending. Do not infer extra traits or film plots from a creator name. Never claim semantic or rendered compliance has been verified."]
    if color:
        data, _, _ = load_resource("color", color["style_id"])
        lines.extend(["COLOR REFERENCE (relative source shares, not measured image coverage or a LUT):",
            "; ".join(f"{c['code']} {c['hex']} {c['share'] * 100:g}% ({_hue_description(c['hex'])})" for c in data["primary"]),
            data["color_notes"]["en"],
            "Treat the six colors as an available hierarchy, not six compulsory objects or a whole-frame filter. Use only colors compatible with this scene; do not silently renormalize the source shares into promised pixel coverage. Preserve locked clothing, brand colors, natural skin, reference identity and readable text. Marker-box colors remain reference identifiers, never costume or palette evidence. The four optional accent swatches in the browser are not extra required colors or permission to invent emotion.",
            "COLOR REALIZATION: where an eligible visual area exists, choose a compatible dominant color and, if useful, a secondary/accent from the selected palette. Name their hues in the requested output language and attach them to existing unlocked surfaces or background regions. Write the resulting color relationship into the normal scene description, not merely 'cinematic', 'warm', 'natural', 'apply the palette' or a creator name. Do not invent a prop or recolor locked skin/clothing to demonstrate compliance. If all relevant colors are explicitly locked, preserve those locks and do not fake a color change."])
        if color["scope"] == "color_and_light":
            lines.extend(["OPTIONAL LIGHTING: " + data["lighting_notes"]["en"],
                "Only suggest compatible lighting within established source/time/location; locked light sources and directions prevail. Never change daytime to night or add a lamp simply to fit the palette."])
        else:
            lines.append("COLOR ONLY: do not change lighting setup, light-source direction, contrast staging or camera/composition because of this selection.")
    if creator:
        data, _, _ = load_resource("creator", creator["style_id"])
        lines.append("CREATOR PRESENTATION ONLY (no automatic palette, lighting or medium transfer):")
        lines.append("Each English/Chinese pair below describes the same method, not two actions. Preserve its concrete qualifiers in the selected output language.")
        lines.extend(m["dimension"] + ": " + m["text_en"] + " [" + m["text_zh"] + "]" for m in data["methods"]
                     if not (fixed_shot_count == 1 and m["requires_cuts"]))
        lines.append("Use existing space and authorized actions only. Framing may guide attention and pacing without adding story facts, props, reveals or reactions. Listed editing methods may use existing permitted cuts, never add cuts beyond the authorized shot plan. An explicit no-cut or continuous-shot request forbids cut-dependent methods even when shot count is AUTO. Keep established information order and who can perceive each event; a presentation suggestion cannot leak a later secret or change its cause. Do not stop ongoing movement to force a static creator signature.")
        lines.append("CREATOR REALIZATION: choose at least one listed method that is compatible with the actual scene and state how it is executed: the existing subject/space it uses and its framing, camera path, staging or timing. A generic label such as 'cinematic' or a creator's name is not an execution. When a method needs absent glass, a doorway, another subject or a cut, do not invent that prerequisite; use another compatible listed method. If every listed method conflicts with an explicit lock or lacks its required evidence, keep the lock and do not pretend the method was applied.")
    if fixed_shot_count == 1:
        lines.append("Exactly one shot: do not add cuts, montage or an insert; only compatible within-shot suggestions apply.")
    lines.append("H3: retain the selected three/six-field task, vocal syntax and actual Picture/Video roles. In Relay put persistent color/presentation in global, not a new event, and never add action in padding."
                 if target == "h3" else "Seedance: retain current 2.0 natural-language organization and requested sound/text notation; import no H3 fields/tags or absolute per-shot timestamps, and no 2.5 template.")
    lines.append("Before returning, silently check each enabled dimension separately against the final text: when a compatible opportunity exists, does the text specify its concrete visible realization? If missing, revise that visual passage within this same answer while preserving all locks, dialogue and native fields. Do not substitute an extra heading, palette table or a claim of style success for the actual description.")
    lines.append("Return only the caller's native result. Do not print this guide, HEX tables, percentage charts, creator index or a style-verification report.")
    return "\n".join(lines)


def h3_style_execution_reminder(color=None, creator=None):
    """Keep enabled visual requests concrete in H3's original generation call.

    This is a model instruction, not an adherence validator or a second pass.
    In particular it must not create speech from arbitrary quoted source text.
    """
    color = resolve_color_style(color)
    creator = resolve_creator_style(creator)
    if not _experimental_enabled(color, creator):
        return ""
    lines = [H3_STYLE_EXECUTION_MARKER + ":",
        "输出前落实已开启的视觉参考，同时保留原任务事实：人物姿态、位置、动作先后与完成状态、准确台词、身份、镜数、时长和首尾约束不能被视觉建议替代。只在当前任务的正常画面描述中表达兼容的改进，不输出方案、色卡表或验证成功声明。"]
    if color and color["mode"] == "on_experimental":
        lines.append("色彩：把选中色相对应到原场景实际可见、未锁色的具体表面；保留该表面的准确范围，床单的许可不等于整张床或人物的许可。与当前构图一起检查可见性，不能把画外区域的配色当作画面效果。保留原有锁定颜色、自然肤色与材质；不为配色新增物件或改换渲染媒介。没有兼容表面时保留原色。")
    if creator and creator["mode"] == "on_experimental":
        lines.append("导演：从所选条目列出的方法中，具体说明兼容方法在原主体、空间和当前镜头内怎样执行；不要只写导演名字或电影感。一镜到底只禁止切镜，不自动禁止运镜；初始视点选择与拍摄中的移动须分别遵守原约束，不能把固定机位解释成允许推拉。缺少必要空间、物件或许可时不用该方法，不补造条件，不改变原动作来适配拍法。")
    lines.extend([
        "原生发声：只对原任务已有或明确授权的台词、歌唱等发声保留稳定ASCII说话人编号，如(S1)，并在实际发声位置使用<d>[英文语言名称]准确原词</d>；普通话用Chinese。保留准确字词、标点、说话人及先后，不以普通引号替代原生格式，也不要把标题、文字标识或任意引文当成对白。保留画外音/离屏说话的原有角色；画面无人不等于没有发声。没有授权发声时，不为满足格式新增说话人或台词。",
        "声音与媒介：原任务已有或要求的声音照常保留，明确静音时保持静音。颜色、灯光、景深或构图本身不生成声音，不写灯光声、色彩声或景深声；风格选择不授权新增声源、音乐、旁白、CG/动画或其它媒介。继续只返回当前H3任务的原生字段；这些提醒不是新的场景事实。",
    ])
    return "\n".join(lines)


def preserve_visual_styles_on_repair(repair_messages, original_messages, color=None, creator=None):
    if resolve_color_style(color) is None and resolve_creator_style(creator) is None:
        return repair_messages
    system = "\n\n".join(m["content"] for m in original_messages if m.get("role") == "system" and type(m.get("content")) is str)
    if not any(marker in system for marker in (MARKER, EXPERIMENTAL_MARKER)):
        return repair_messages
    result = [dict(m) for m in repair_messages]
    if not result[0]["content"].startswith(system):
        result[0]["content"] = system + "\n\n" + result[0]["content"]
    text = []
    for message in original_messages:
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            text.append(content)
        elif isinstance(content, list):
            text.extend(p["text"] for p in content if p.get("type") == "text")
    source = "\n".join(text)
    if source and source not in result[1]["content"]:
        result[1]["content"] = source + "\n\n" + result[1]["content"]
    if REPAIR_STYLE_SCOPE not in result[0]["content"]:
        result[0]["content"] += "\n\n" + REPAIR_STYLE_SCOPE
    return result
