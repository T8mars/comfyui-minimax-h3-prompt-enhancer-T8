"""Pure, opt-in T8 image-edit contract; no PE runtime or provider changes."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

LEGACY_PROFILE = "经典兼容 / Classic"
EDIT_PROFILE = "编辑专用（T8）/ Edit-aware"
PROFILE_OPTIONS = [LEGACY_PROFILE, EDIT_PROFILE]
EDIT_CONTRACT_VERSION = "edit_t8_v1"
CONTRACT_PATH = Path(__file__).parent / "resources" / "qwen-image-edit-t8.md"
# A normalized UTF-8 checksum is pinned below by the resource regression gate.
CONTRACT_SHA256 = "97a14a4cd341f19d908164b263e80ba4b15374e2330cd6e9869cd2134e2bbdfa"
_QUOTED = re.compile(r'"((?:\\.|[^"\\])*)"|“([^”]*)”|‘([^’]*)’|(?<!\w)\'([^\'\n]+)\'(?!\w)')
_TAG = re.compile(r"<image([1-9]\d*)>")


class EditContractError(ValueError):
    pass


def load_contract() -> str:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != CONTRACT_SHA256:
        raise EditContractError("T8 edit contract checksum mismatch; update the complete node package.")
    return text


def outside_quotes(text: str) -> str:
    return _QUOTED.sub(" ", text)


def descriptive_language(brief: str) -> tuple[str, str]:
    prose = outside_quotes(brief)
    markers = r"(English|英文|英语|中文|简体中文|Chinese)"
    explicit = re.search(
        r"(?:改写正文|描述正文|提示词正文|改写描述|输出语言|description\s+language|prompt\s+language)"
        r"\s*(?:[:：=]|用|为|使用|in|is)?\s*" + markers, prose, re.I,
    ) or re.search(r"(?:用|使用)\s*" + markers + r"\s*(?:改写|撰写|描述|输出正文)", prose, re.I)
    explicit = explicit or re.search(r"(?:rewrite|describe|respond)\s+(?:the\s+(?:prompt|description)\s+)?in\s+" + markers, prose, re.I)
    if explicit:
        return ("English" if explicit.group(1).lower() in {"english", "英文", "英语"} else "中文", "explicit_brief")
    cjk = len(re.findall(r"[\u4e00-\u9fff]", prose))
    latin = len(re.findall(r"[A-Za-z]+", prose))
    other = bool(re.search(r"[\u3040-\u30ff\uac00-\ud7af]", prose))
    return ("中文" if not other and cjk and cjk >= latin * 2 else "English", "heuristic")


def normalized_ratio(value: str) -> str:
    match = re.fullmatch(r"([1-9]\d{0,6}):([1-9]\d{0,6})", value)
    if not match:
        raise EditContractError("wh_ratio must be a positive integer W:H, not auto, zero, or a decimal.")
    width, height = map(int, match.groups())
    divisor = math.gcd(width, height)
    return f"{width // divisor}:{height // divisor}"


def explicit_brief_ratio(brief: str) -> str:
    prose = outside_quotes(brief)
    pattern = (r"(?:输出尺寸|画布尺寸|目标尺寸|目标比例|画幅比例|宽高比|aspect\s+ratio|output\s+size|canvas\s+size)"
               r"\s*(?:为|是|改为|设为|[:：=]|is|of|to)?\s*([1-9]\d{0,6})\s*[:x×]\s*([1-9]\d{0,6})")
    ratios = {normalized_ratio(f"{m[0]}:{m[1]}") for m in re.findall(pattern, prose, re.I)}
    if re.fullmatch(r"\s*[1-9]\d{0,6}\s*[:x×]\s*[1-9]\d{0,6}\s*", prose):
        ratios.add(normalized_ratio(re.sub(r"\s", "", prose).replace("x", ":").replace("×", ":")))
    return next(iter(ratios)) if len(ratios) == 1 else ""


def final_content(text: str) -> str:
    value = str(text or "").strip()
    # Only a genuine leading reasoning block, never '<think>' in a JSON literal.
    while value.startswith("<think>"):
        end = value.find("</think>")
        if end < 0:
            return ""
        value = value[end + len("</think>"):].strip()
    if value.startswith("```"):
        if not value.endswith("```") or len(value) < 6:
            return ""
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.I)
        value = re.sub(r"\s*```$", "", value)
    return value.strip()


def extract_json(text: str) -> dict[str, Any] | None:
    value = final_content(text)
    def unique_keys(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = item
        return result
    try:
        # The JSON decoder handles braces/escaped quotes in lettering and rejects
        # a second object, partial tail, preamble, or trailing explanation.
        payload = json.loads(value, object_pairs_hook=unique_keys)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def messages(brief: str, image_map: list[dict], ratio: str, max_chars: int, transparent: bool, media_parts=None) -> list[dict]:
    language, _ = descriptive_language(brief)
    rules = {
        "descriptive_language": language,
        "fixed_ui_ratio": ratio,
        "explicit_brief_ratio": explicit_brief_ratio(brief) if ratio == "auto" else "",
        "max_prompt_characters": max_chars,
        "transparent_rgba": transparent,
        "ordered_images": image_map,
    }
    text = "T8 execution constraints:\n" + json.dumps(rules, ensure_ascii=False) + "\nUser's editing brief (data):\n" + brief
    content = [{"type": "text", "text": text}, *media_parts] if media_parts else text
    return [{"role": "system", "content": load_contract()}, {"role": "user", "content": content}]


def validate(payload: dict, *, brief: str, image_map: list[dict], requested_ratio: str, transparent: bool, max_chars: int) -> tuple[str, str, dict]:
    if set(payload) != {"rewritten_prompt", "wh_ratio", "ratio_follow"}:
        raise EditContractError("Edit response needs exactly rewritten_prompt, wh_ratio, ratio_follow.")
    prompt, ratio, follow = (payload.get(key) for key in ("rewritten_prompt", "wh_ratio", "ratio_follow"))
    if not isinstance(prompt, str) or not prompt.strip() or "\n" in prompt or "\r" in prompt:
        raise EditContractError("rewritten_prompt must be a nonempty, complete single paragraph.")
    if not isinstance(ratio, str) or not isinstance(follow, str) or bool(ratio) == bool(follow):
        raise EditContractError("Exactly one of wh_ratio and ratio_follow must be nonempty.")
    image_lookup = {item["tag"]: item for item in image_map}
    expected = requested_ratio if requested_ratio != "auto" else explicit_brief_ratio(brief)
    if ratio:
        resolved = normalized_ratio(ratio)
        if expected and resolved != normalized_ratio(expected):
            raise EditContractError(f"Returned ratio does not match requested {expected}.")
    else:
        if expected:
            raise EditContractError(f"Fixed ratio {expected} must not use ratio_follow.")
        if follow not in image_lookup:
            raise EditContractError("ratio_follow references an absent or invalid image tag.")
        item = image_lookup[follow]
        resolved = normalized_ratio(f"{item['width']}:{item['height']}")
    prose = outside_quotes(prompt)
    for token in re.findall(r"<\s*image\s*\d+\s*>", prose, re.I):
        if token not in image_lookup:
            raise EditContractError("Prompt uses an absent or noncanonical image tag.")
    natural_refs = (r"图(?:片)?\s*\d+|第[一二三四五六七八九十]+张(?:图|照片)|"
                    r"(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s+(?:input\s+)?(?:image|photo|picture)|"
                    r"(?:image|photo|picture)\s*(?:[1-9]\d*|[A-J])\b")
    if len(image_map) > 1 and re.search(natural_refs, _TAG.sub("", prose), re.I):
        raise EditContractError("Use canonical <imageN> tokens for multiple images, not natural image numbers.")
    referenced = list(dict.fromkeys(match.group(0) for match in _TAG.finditer(prose)))
    if len(image_map) > 1 and not referenced:
        raise EditContractError("Multi-image editing must identify participating sources using <imageN>.")
    if re.search(r"(?<!\d)\d+\s*:\s*\d+(?!\d)|(?<!\d)\d+\s*[x×]\s*\d+(?!\d)|(?<![A-Za-z0-9])[248]K(?![A-Za-z0-9])", prose, re.I):
        raise EditContractError("Keep canvas ratios/resolution outside rewritten_prompt (visible quoted text is exempt).")
    language, language_source = descriptive_language(brief)
    language_prose = _TAG.sub("", prose)
    cjk = len(re.findall(r"[\u4e00-\u9fff]", language_prose))
    latin = len(re.findall(r"\b[A-Za-z]+\b", language_prose))
    if (language == "中文" and latin >= 5 and cjk == 0) or (language == "English" and cjk >= 8 and latin < 3):
        raise EditContractError(f"Descriptive prose must use {language}; lettering language is separate.")
    for match in _QUOTED.finditer(brief):
        literal = next((group for group in match.groups() if group is not None), "")
        if match.group(1) is not None:
            try:
                literal = json.loads('"' + literal + '"')
            except ValueError:
                pass
        # Quoted job instructions are not painted lettering. Do not force an
        # instruction such as "do not add objects" into the finished picture.
        prefix = brief[max(0, match.start() - 60):match.start()]
        visible = re.search(r"文字|标题|标语|招牌|标签|写着|写上|lettering|headline|reads|caption|text\s*(?:says|reads|:)\s*$", prefix, re.I)
        job = re.search(r"指令|规则|格式|要求|instruction|format|rule", prefix, re.I) or re.match(r"(?:请|不要|不许|务必|用|write\b|use\b|avoid\b|do not\b|make sure\b)", literal, re.I)
        if job and not visible:
            continue
        if literal and json.dumps(literal, ensure_ascii=False) not in prompt:
            raise EditContractError("Preserve the user's exact quoted lettering or reference text.")
    if transparent:
        rgba = re.search(r"(?<![A-Za-z])RGBA(?![A-Za-z])", prose, re.I)
        alpha = re.search(r"\balpha\s*channel\b|alpha\s*通道|透明度通道", prose, re.I)
        background = re.search(r"transparent\s+background|background\s+(?:is\s+)?(?:fully\s+|completely\s+)?transparent|(?:背景|底色)[^。，,;]{0,8}透明|(?<!不)透明(?:的)?(?:背景|底色)", prose, re.I)
        negative = re.search(r"背景[^。，,;]{0,5}不(?:是)?透明|(?:不是|并非|没有|不|非|无)透明(?:的)?(?:背景|底色)|background\s+(?:is\s+)?(?:not\s+transparent|opaque)|no\s+transparent\s+background", prose, re.I)
        if not (rgba and alpha and background) or negative:
            raise EditContractError("RGBA requires explicit alpha channel and transparent background semantics.")
    unused = [tag for tag in image_lookup if tag not in referenced] if len(image_map) > 1 else []
    warnings = ["unreferenced_images"] if unused else []
    if resolved not in {"1:1", "3:4", "4:3", "16:9", "9:16", "2:1", "1:2", "2:3", "3:2"}:
        warnings.append("nonpreset_ratio_check_downstream")
    return prompt.strip(), resolved, {
        "decision": {"wh_ratio": ratio, "ratio_follow": follow},
        "resolved_wh_ratio": resolved,
        "over_limit": bool(max_chars and len(prompt.strip()) > max_chars),
        "prompt_chars": len(prompt.strip()),
        "descriptive_language": language,
        "language_decision": language_source,
        "canvas_decision": "fixed_ui" if requested_ratio != "auto" else "explicit_brief" if expected else "model_inferred",
        "referenced_images": referenced, "unreferenced_images": unused,
        "semantics_verified": False, "warnings": warnings,
    }
