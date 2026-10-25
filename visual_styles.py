"""Independent, opt-in color and creator presentation resources.

No media uploads, generation, source-directory access or model protocol changes.
The config carries identity, not arbitrary instructions; consumers resolve the
same immutable, content-checked packaged resource as the selector nodes.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

REVISION = "1.0.0"
OFF = "关闭 / Off"
ON = "开启 / On"
MODES = [OFF, ON]
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
MARKER = "T8 OPTIONAL VISUAL PRESENTATION v" + REVISION
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
    result.update(mode="on", style_id=entry["id"], resource_revision=resource["revision"],
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
            or value.get("schema_version") != schema or value.get("mode") not in ("off", "on")):
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
    canonical = build_style_config(kind, ON, value["style_id"], scope or COLOR_ONLY)
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
    return result


def safe_style_metadata(values):
    """Historical finite identities survive missing resources; never load catalog."""
    if type(values) is not dict:
        return {}
    result = {}
    for kind in ("color", "creator"):
        block = values.get(kind + "_style")
        fields = {"style_id", "resource_revision", "resource_sha256", "adapter_revision"} | ({"scope"} if kind == "color" else set())
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
    return (REVISION, load_catalog()[1], json.dumps(config, sort_keys=True))


def consumer_fingerprint(color=MISSING, creator=MISSING, recovery_action="normal"):
    if recovery_action == "restore_last" or (color is MISSING and creator is MISSING):
        return False  # Same sentinel as a node without an IS_CHANGED override.
    return ("t8-visual-catalog", REVISION, load_catalog()[1])


def visual_style_instruction(color=None, creator=None, target="h3", *, fixed_shot_count=0):
    color, creator = resolve_color_style(color), resolve_creator_style(creator)
    if color is None and creator is None:
        return ""
    if target not in {"h3", "seedance20"}:
        raise _error()
    lines = [MARKER + " (independently adapted, experimental; not an extra planning pass).",
        "Use only the selected concrete presentation suggestions below, where compatible. Existing scene-directing Skills own scene strategy; acting/Bibles, storyboard, combat and reference contracts retain their roles. Do not pause or replace them. User facts, exact dialogue/text/speaker, identity, media roles, source action order, fixed timing/count, framing locks and ending take priority. These modifiers grant no new authorship.",
        "Retain the native output grammar and current language. Change neither target duration nor shot count; impose no duration cap, automatic segmentation, new sound, subtitle, character, object, location, era, rendering medium or freeze ending. An already suitable passage may remain unchanged. Do not infer extra traits or film plots from a creator name. Never claim semantic or rendered compliance has been verified."]
    if color:
        data, _, _ = load_resource("color", color["style_id"])
        lines.extend(["COLOR REFERENCE (relative source shares, not measured image coverage or a LUT):",
            "; ".join(f"{c['code']} {c['hex']} {c['share'] * 100:g}%" for c in data["primary"]),
            data["color_notes"]["en"],
            "Treat the six colors as an available hierarchy, not six compulsory objects or a whole-frame filter. Use only colors compatible with this scene; do not silently renormalize the source shares into promised pixel coverage. Preserve locked clothing, brand colors, natural skin, reference identity and readable text. Marker-box colors remain reference identifiers, never costume or palette evidence. The four optional accent swatches in the browser are not extra required colors or permission to invent emotion."])
        if color["scope"] == "color_and_light":
            lines.extend(["OPTIONAL LIGHTING: " + data["lighting_notes"]["en"],
                "Only suggest compatible lighting within established source/time/location; locked light sources and directions prevail. Never change daytime to night or add a lamp simply to fit the palette."])
        else:
            lines.append("COLOR ONLY: do not change lighting setup, light-source direction, contrast staging or camera/composition because of this selection.")
    if creator:
        data, _, _ = load_resource("creator", creator["style_id"])
        lines.append("CREATOR PRESENTATION ONLY (no automatic palette, lighting or medium transfer):")
        lines.extend(m["dimension"] + ": " + m["text_en"] for m in data["methods"]
                     if not (fixed_shot_count == 1 and m["requires_cuts"]))
        lines.append("Use existing space and authorized actions only. Framing may guide attention and pacing without adding story facts, props, cuts, reveals or reactions. Keep established information order and who can perceive each event; a presentation suggestion cannot leak a later secret or change its cause. Do not stop ongoing movement to force a static creator signature.")
    if fixed_shot_count == 1:
        lines.append("Exactly one shot: do not add cuts, montage or an insert; only compatible within-shot suggestions apply.")
    lines.append("H3: retain the selected three/six-field task, vocal syntax and actual Picture/Video roles. In Relay put persistent color/presentation in global, not a new event, and never add action in padding."
                 if target == "h3" else "Seedance: retain current 2.0 natural-language organization and requested sound/text notation; import no H3 fields/tags or absolute per-shot timestamps, and no 2.5 template.")
    lines.append("Return only the caller's native result. Do not print this guide, HEX tables, percentage charts, creator index or a style-verification report.")
    return "\n".join(lines)


def preserve_visual_styles_on_repair(repair_messages, original_messages, color=None, creator=None):
    if resolve_color_style(color) is None and resolve_creator_style(creator) is None:
        return repair_messages
    system = "\n\n".join(m["content"] for m in original_messages if m.get("role") == "system" and type(m.get("content")) is str)
    if MARKER not in system:
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
    return result
