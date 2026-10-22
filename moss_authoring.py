"""Pure authoring policies shared by MOSS single-image and collection authoring.

No provider, ComfyUI, filesystem writes or model calls. Classic is deliberately
not rewritten here. Character preferences are soft and never truncate a draft.
"""
from __future__ import annotations

import json
import re

try:
    from . import moss_image_contract as c
    from .moss_authoring_rules import CLASSIC, COMIC, FISHER, PROFILES, REVISION, FISHER_RULES, comic_rules
except ImportError:
    import moss_image_contract as c
    from moss_authoring_rules import CLASSIC, COMIC, FISHER, PROFILES, REVISION, FISHER_RULES, comic_rules

_QUOTED = r'```[\s\S]*?```|`[^`\n]*`|"(?:\\.|[^"\\])*"|“[^”]*”|‘[^’]*’|(?<!\w)\x27(?:\\.|[^\x27\\])*\x27|(?m:^\s*>[^\n]*)'
_LENGTH = re.compile(
    r"短版|精简版|简短|简洁|压缩|(?:不超过|控制在|限制为|写|输出|扩写为|缩写为|篇幅|字数|长度)\s*(?:约|大约|一段|成|在|为|到|[:：])?\s*\d+\s*(?:个?字|汉字|字符|words?\b|characters?\b)"
    r"|(?:^|[，,。.!！?？;；\n])\s*\d+\s*(?:字|汉字|字符|words?\b|characters?\b)(?:以内|左右|以下|\s*(?:max|maximum))?"
    r"|\b(?:write|output|expand|limit|under|at most|about)\s+(?:to\s+)?\d+\s*(?:words?|characters?)\b"
    r"|\b(?:short|brief|concise|compact)\s+(?:version|description|prompt|answer)\b", re.IGNORECASE)
_ENGLISH = re.compile(
    r"(?:用|使用|输出|改成|写成|描述(?:为)?|提示词(?:为)?)\s*英[文语]|英文(?:描述|提示词|输出)"
    r"|\b(?:(?:output|write|respond|describe|use)\s+(?:(?:the\s+)?(?:image\s+)?(?:description|prose|prompt|output)\s+)?(?:in\s+)?English"
    r"|(?:description|prose|prompt|output)\s+in\s+English|English\s+(?:description|prose|prompt|output))\b", re.IGNORECASE)
_CHINESE = re.compile(
    r"(?:用|使用|输出|改成|写成|描述(?:为)?|提示词(?:为)?)\s*(?:中文|汉语)|中文(?:描述|提示词|输出)"
    r"|\b(?:(?:output|write|respond|describe|use)\s+(?:(?:the\s+)?(?:image\s+)?(?:description|prose|prompt|output)\s+)?(?:in\s+)?Chinese"
    r"|(?:description|prose|prompt|output)\s+in\s+Chinese|Chinese\s+(?:description|prose|prompt|output))\b", re.IGNORECASE)
_NEGATION = re.compile(r"不要|不需要|无需|不用|禁止|避免|勿|不能|\b(?:not|never|avoid|without|no)\b|don['’]t", re.IGNORECASE)
_STATUSES = {"automatic", "within_limit", "over_limit", "below_target", "above_target", "within_target"}


def validate_profile(value):
    if not isinstance(value, str) or value not in PROFILES:
        c.fail("invalid_authoring_profile", "Unsupported MOSS authoring profile / 强化模式无效。")
    return value


def instruction_text(brief):
    c.clean_text(brief, "brief", limit=64000)
    return re.sub(_QUOTED, lambda match: re.sub(r"[^\n]", " ", match.group(0)), brief)


def descriptive_language(profile, language, brief):
    validate_profile(profile)
    if language not in c.LANGUAGES:
        c.fail("invalid_language", "Unsupported descriptive language / 描述语言无效。")
    if language != c.LANG_AUTO:
        return language
    if profile == FISHER:
        text = instruction_text(brief)
        choices = [(match.start(), value) for pattern, value in ((_ENGLISH, "English"), (_CHINESE, "中文"))
                   for match in positive_matches(pattern, text)]
        return max(choices)[1] if choices else "中文"
    return "English"


def positive_matches(pattern, text):
    """Finite command recognition, not an arbitrary natural-language parser."""
    for match in pattern.finditer(text):
        before = re.split(r"[，,。.!！?？;；\n]", text[:match.start()])[-1]
        if not _NEGATION.search(before):
            yield match


def han_count(text):
    # Defined code-point ranges, not a tokenizer or a grapheme/word estimator.
    return sum(0x3400 <= ord(ch) <= 0x4DBF or 0x4E00 <= ord(ch) <= 0x9FFF
               or 0xF900 <= ord(ch) <= 0xFAFF or 0x20000 <= ord(ch) <= 0x323AF for ch in text)


def descriptions(result):
    source = c.strict_json(result[4])
    return source["caption"] if result[3] == "caption" else source["summary"]["caption"] + "".join(
        item["caption"] for item in source["items"])


def length_policy(profile, brief, language, max_chars):
    validate_profile(profile)
    if type(max_chars) is not int or not 0 <= max_chars <= c.MAX_DESCRIPTION_CHARS:
        c.fail("invalid_length", "Description limit must be 0–20000 / 描述字数须在0–20000。")
    target = profile == FISHER and not max_chars and descriptive_language(profile, language, brief) == "中文" and not any(positive_matches(_LENGTH, instruction_text(brief)))
    return {"max_output_chars": max_chars, "target_han_range": [1500, 2500] if target else None}


def length_metadata(result, policy):
    text = descriptions(result)
    count, han, maximum, target = len(text), han_count(text), policy["max_output_chars"], policy["target_han_range"]
    status = "within_limit" if maximum else "automatic"
    if maximum and count > maximum:
        status = "over_limit"
    elif target:
        status = "below_target" if han < target[0] else "above_target" if han > target[1] else "within_target"
    return {"metric": "unicode_code_points", "description_chars": count, "han_chars": han,
            "max_output_chars": maximum, "target_han_range": target, "status": status, "hard_enforced": False}


def candidate_rank(result, policy):
    info = length_metadata(result, policy)
    maximum, count, target, han = info["max_output_chars"], info["description_chars"], info["target_han_range"], info["han_chars"]
    return (max(0, count - maximum) if maximum else 0,
            max(target[0] - han, 0, han - target[1]) if target else 0)


def length_warning(result, policy):
    status = length_metadata(result, policy)["status"]
    return {"over_limit": "description_over_limit", "below_target": "fisher_length_target_unmet",
            "above_target": "fisher_length_target_unmet"}.get(status, "")


def validate_cached_authoring(report, result):
    """Old v1 caches need no new fields; new fields must be finite and consistent."""
    keys = {"authoring_profile", "authoring_revision", "authoring_length"}
    if not keys.intersection(report):
        return
    if not keys.issubset(report) or report["authoring_revision"] != REVISION or report["authoring_profile"] not in (COMIC, FISHER):
        c.fail("invalid_cache", "Stored authoring metadata is incompatible / 缓存强化模式无效。")
    info = report["authoring_length"]
    if not isinstance(info, dict) or type(info.get("max_output_chars")) is not int or not 0 <= info["max_output_chars"] <= c.MAX_DESCRIPTION_CHARS:
        c.fail("invalid_cache", "Stored character limit is invalid / 缓存字数无效。")
    target = info.get("target_han_range")
    if target is not None and (type(target) is not list or len(target) != 2 or any(type(n) is not int for n in target)
                               or target != [1500, 2500] or info["max_output_chars"] or report["authoring_profile"] != FISHER):
        c.fail("invalid_cache", "Stored length target is invalid / 缓存长度目标无效。")
    expected = length_metadata(result, {"max_output_chars": info["max_output_chars"], "target_han_range": target})
    # Type-strict: True must not compare equal to an integer count.
    if (set(info) != set(expected) or not isinstance(info.get("status"), str) or info["status"] not in _STATUSES
            or any(type(info[k]) is not type(v) or info[k] != v for k, v in expected.items())):
        c.fail("invalid_cache", "Stored length counts differ from the draft / 缓存计量与草稿不符。")


def build_messages(controls, image_labels, media_parts=None):
    profile = validate_profile(controls["authoring_profile"])
    messages = c.build_messages(controls["prompt"], output_format=controls["output_format"],
        width=controls["width"], height=controls["height"], language=controls["output_language"],
        locked_text=controls["locked_text"], max_chars=controls["max_output_chars"],
        image_labels=image_labels, media_parts=media_parts)
    if profile == CLASSIC:
        return messages
    messages[0]["content"] += "\n## Opt-in authoring adaptation\n" + (FISHER_RULES if profile == FISHER else comic_rules())
    content = messages[1]["content"]
    request = json.loads(content[0]["text"] if isinstance(content, list) else content)
    policy = length_policy(profile, controls["prompt"], controls["output_language"], controls["max_output_chars"])
    request["authoring_profile"] = profile
    if profile == FISHER:
        language = descriptive_language(profile, controls["output_language"], controls["prompt"])
        request["descriptive_language_rule"] = f"Write descriptive prose in {language}. Intended visible strings are unchanged."
        request["single_image_rule"] = "One image deliverable only. Never concatenate independent images into one caption."
        if policy["target_han_range"]:
            request["length_rule"] = "Aim for 1500–2500 Han characters of useful description, about 10–15 coherent paragraphs. Accuracy and explicit brief constraints win; never pad or invent hidden facts."
        request["format_rule"] += " In AUTO prefer Caption for natural-language expansion unless precise spatial/text placement requires Layout."
    else:
        request["single_image_rule"] = "This is ONE page in the selected descriptive language, not the full bilingual collection deliverable."
        request["format_rule"] += " In native Layout use summary.canvas=multi_panel and represent each panel as label=object with tags containing comic_panel. Keep characters, objects and text separate; do not emit the source-only comic_panel label or planning sidecars here. Explicit Caption selection still wins."
    encoded = json.dumps(request, ensure_ascii=False)
    if isinstance(content, list):
        content[0]["text"] = encoded
    else:
        messages[1]["content"] = encoded
    return messages


def bounded(complete, messages, validator, repairs, counters, policy, keep_error,
            *, response_rule="Return one complete native MOSS draft JSON."):
    """Non-Classic length selection: an undersized Fisher draft may grow."""
    first = complete(messages, False)
    best, problem = None, None
    try:
        best = validator(first)
        if candidate_rank(best, policy) == (0, 0):
            return best, "", False
    except c.MossContractError as error:
        problem = error
    if not repairs:
        if best is not None:
            return best, length_warning(best, policy), False
        raise problem
    counters["correction_calls"] += 1
    correction = messages + [{"role": "assistant", "content": first}, {"role": "user", "content": (
        "Revise the entire response once. " + response_rule + " Preserve the fixed canvas, visible text and facts. "
        "Fix schema errors and description length together. Never truncate or pad. Expand useful visible "
        "detail if below the automatic Fisher Han range; shorten only redundant detail if above the UI cap. "
        "If reference evidence is insufficient, keep accuracy rather than inventing details. Policy: "
        + json.dumps(policy) + "; problem: " + (problem.code if problem else length_warning(best, policy)))}]
    try:
        repaired = validator(complete(correction, True))
        if best is None or candidate_rank(repaired, policy) <= candidate_rank(best, policy):
            return repaired, length_warning(repaired, policy), False
    except Exception as error:
        # Explicit allowlist supplied by the transport layer; cancellation and
        # identity/security/deadline failures can never turn into a soft result.
        if best is None or not keep_error(error):
            raise
    if best is not None:
        return best, "correction_failed_draft_kept", True
    raise problem
