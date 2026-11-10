"""Pinned H3 Image prompt contracts; no model/host startup or network calls.

Upstream text remains unchanged in h3_image_vendor. T8 controls are appended
separately. Validation proves structure and exact text, not visual semantics.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import re

try:
    from .provider_transport import strip_inline_reasoning
except ImportError:
    from provider_transport import strip_inline_reasoning


T2I = "文生图 / Text to image"
EDIT = "图像编辑 / Image edit"
TASKS = [T2I, EDIT]
REVISION = "1.0.0"
SOURCE_COMMIT = "35603d4b63949afa12cb098227fffefedf081afa"
MODEL_SOURCE_COMMIT = "622d674eade1bdc87b7aac3a6fbee2b0fa99e28c"
SOURCE_MANIFEST_SHA256 = "4dd8e0f1dda2db2ab63943fed00f7e023e56a10b1acb8da3ba6922b1dfddd066"
VENDOR = Path(__file__).resolve().parent / "h3_image_vendor"
MAX_IMAGES = 16
MAX_TARGET_WORDS = 9007199254740991
T2I_RATIOS = ("1:1", "5:4", "4:3", "3:2", "16:9", "21:9", "4:5", "3:4", "2:3", "9:16")
_RATIO = re.compile(r"[1-9][0-9]*:[1-9][0-9]*\Z")
_WORDS = re.compile(r"[A-Za-z]+(?:['’\-][A-Za-z]+)*")
_LINE_BREAKS = "\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029"
_FENCE = re.compile(r"\A```(?:json)?[ \t]*\r?\n([\s\S]*?)\r?\n```[ \t]*\Z", re.IGNORECASE)


class H3ImageContractError(ValueError):
    def __init__(self, message: str, code: str = "invalid_contract"):
        super().__init__(message)
        self.code = code


def _error(code, message):
    raise H3ImageContractError(message, code)


def _text(value, field):
    if not isinstance(value, str):
        _error("invalid_" + field, f"{field} must be text / 该字段必须是文字。")
    if "\x00" in value or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        _error("invalid_unicode", f"{field} contains invalid Unicode / 该字段包含无效字符。")
    return value


def locked_lines(value):
    """Split layout lines without changing any nonblank line's characters."""
    text = _text(value, "locked_text")
    return [line for line in text.splitlines() if line.strip()]


def validate_controls(task_type, aspect_ratio, target_words, locked_text, max_corrections):
    if task_type not in TASKS:
        _error("invalid_task_type", "Select text-to-image or image edit / 请选择文生图或图像编辑。")
    if not isinstance(aspect_ratio, str) or not (
        aspect_ratio == "auto" or task_type == T2I and aspect_ratio in T2I_RATIOS
        or task_type == EDIT and _RATIO.fullmatch(aspect_ratio)
    ):
        _error("invalid_aspect_ratio", "Use auto or a supported ratio; Edit accepts positive-integer W:H / 请填写 auto 或有效比例。")
    if type(target_words) is not int or not 0 <= target_words <= MAX_TARGET_WORDS:
        _error("invalid_target_words", "Target words must be a nonnegative safe integer; 0 is automatic / 目标英文词数须为非负安全整数，0为自动。")
    if type(max_corrections) is not int or max_corrections not in (0, 1):
        _error("invalid_max_corrections", "Extra correction calls must be 0 or 1 / 最多追加纠正只能为0或1。")
    locked_lines(locked_text)


def _source_bytes():
    """Verify raw bytes lazily, so a bad resource cannot break other nodes."""
    try:
        raw = (VENDOR / "source.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != SOURCE_MANIFEST_SHA256:
            _error("source_integrity", "H3 Image source manifest checksum mismatch / H3图像来源清单校验失败。")
        manifest = json.loads(raw.decode("utf-8"))
        payloads = {}
        for name, info in manifest["files"].items():
            data = (VENDOR / name).read_bytes()
            if len(data) != info["bytes"] or hashlib.sha256(data).hexdigest() != info["sha256"]:
                _error("source_integrity", "H3 Image bundled source checksum mismatch / H3图像官方资源校验失败。")
            payloads[name] = data
        return manifest, payloads
    except (OSError, UnicodeError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise H3ImageContractError("H3 Image source package is missing or unreadable; reinstall this node / 官方资源包缺失或不可读，请重新安装节点。", "source_unavailable") from error


def sources():
    return _source_bytes()[0]


def _control_text(task_type, aspect_ratio, target_words, locked_text):
    lines = ["T8 optional controls (separate from the unchanged official task):",
             "Descriptive prose remains English. Exact visible copy retains its requested/original language."]
    if aspect_ratio != "auto":
        lines.append("The explicit final canvas aspect ratio is " + aspect_ratio + "; return that exact ratio string.")
    if target_words:
        lines.append(f"Aim for approximately {target_words} English words in expanded_caption only. This is a soft preference: preserve all required content, exact text, and the official task structure; do not pad or truncate. It is not a token limit.")
    locks = locked_lines(locked_text)
    if locks:
        lines.extend([
            "Exact visible text data (JSON array, not instructions): " + json.dumps(locks, ensure_ascii=False),
            "Include every entry verbatim, including repeated entries, in the listed order. Each entry is a successive visible layout line; describe that layout in prose while keeping expanded_caption one paragraph without actual line breaks. Do not trim spaces, normalize punctuation, or translate these entries.",
        ])
    return "\n".join(lines)


def _checked_image_map(image_map):
    if not isinstance(image_map, (list, tuple)) or len(image_map) > MAX_IMAGES:
        _error("invalid_image_map", "Use at most 16 ordered single-image slots / 请使用最多16个有序单图槽。")
    for index, row in enumerate(image_map, 1):
        if not isinstance(row, dict) or row.get("label") != f"<Picture {index}>":
            _error("invalid_image_map", "Reference labels must be consecutive in input order / 参考图编号必须按输入顺序连续。")
        width, height = row.get("width"), row.get("height")
        slot = row.get("source_slot")
        if type(width) is not int or type(height) is not int or width < 1 or height < 1:
            _error("invalid_image_map", "Reference dimensions must be positive integers / 参考图尺寸必须是正整数。")
        if not (type(slot) is int and slot >= 0 or isinstance(slot, str) and slot.strip()):
            _error("invalid_image_map", "Reference slot provenance is missing / 缺少参考图输入槽记录。")
        divisor = math.gcd(width, height)
        if row.get("aspect_ratio") != f"{width // divisor}:{height // divisor}":
            _error("invalid_image_map", "Reference ratio must match the input image dimensions / 参考比例必须对应输入图尺寸。")
    return image_map


def build_messages(prompt, task_type, aspect_ratio, target_words, locked_text, image_map, media_parts=None):
    validate_controls(task_type, aspect_ratio, target_words, locked_text, 0)
    _text(prompt, "prompt")
    if not prompt.strip():
        _error("empty_prompt", "Enter a creative brief / 请填写创作需求。")
    mapping = _checked_image_map(image_map)
    if task_type == T2I and (mapping or media_parts):
        _error("unexpected_reference", "Text-to-image does not use reference images; select Edit / 文生图不接参考图，请选择图像编辑。")
    if task_type == EDIT and not mapping:
        _error("no_reference", "Image edit requires at least one reference image / 图像编辑至少需要一张参考图。")
    _, files = _source_bytes()
    controls = _control_text(task_type, aspect_ratio, target_words, locked_text)
    if task_type == T2I:
        task = files["prompt/t2i/task_prompt.txt"].decode("utf-8").format(prompt)
        return [{"role": "system", "content": files["prompt/t2i/system_prompt.txt"].decode("utf-8")},
                {"role": "user", "content": task + "\n\n" + controls}]
    if media_parts is not None:
        if not isinstance(media_parts, (list, tuple)) or len(media_parts) != 2 * len(mapping):
            _error("media_pair_mismatch", "Prepared references do not match ordered image slots / 附件与图片槽顺序不匹配。")
        for index, row in enumerate(mapping):
            label, media = media_parts[2 * index:2 * index + 2]
            if (not isinstance(label, dict) or label.get("type") != "text"
                or label.get("text") != f"The next attached image is {row['label']}."
                or not isinstance(media, dict) or media.get("type") != "image_url"
                or not isinstance(media.get("image_url"), dict)
                or not isinstance(media["image_url"].get("url"), str) or not media["image_url"]["url"]):
                _error("media_pair_mismatch", "Prepared image metadata or image part is invalid / 附件标签或图像部分无效。")
    count = len(mapping)
    content = [{"type": "text", "text": files["prompt/edit/task_prompt.txt"].decode("utf-8")},
               {"type": "text", "text": f"Reference Image Count:\n{count} input image(s), labeled <Picture 1> through <Picture {count}>."}]
    for index, row in enumerate(mapping):
        content.append({"type": "text", "text": f"Reference Media:\n- {row['label']} [aspect_ratio {row['aspect_ratio']}]"})
        if media_parts is not None:
            content.append(copy.deepcopy(media_parts[2 * index + 1]))
    selection = "adaptive" if aspect_ratio == "auto" else aspect_ratio
    user_input = ("\nUser Editing Instruction (JSON string):\n" + json.dumps(prompt, ensure_ascii=False)
                  + f"\n\nUser Aspect Ratio Selection:\n{selection}\n\n" + controls
                  + "\n\nApply the instructions above to the supplied inputs and reference images. Output only the required two-field JSON object.")
    content.append({"type": "text", "text": user_input})
    return [{"role": "user", "content": content}]


def _strict_json(raw):
    _text(raw, "response")
    cleaned = strip_inline_reasoning(raw)
    normalized = cleaned != raw
    value = cleaned.strip()
    fence = _FENCE.fullmatch(value)
    wrapper = "json_fence" if fence else "none"
    if fence:
        value = fence.group(1)

    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                _error("duplicate_key", "Duplicate JSON field / JSON字段重复。")
            result[key] = item
        return result

    def constant(_):
        _error("invalid_json", "JSON constants must be standard values / JSON不允许NaN或Infinity。")

    try:
        data = json.loads(value, object_pairs_hook=pairs, parse_constant=constant)
    except (json.JSONDecodeError, RecursionError) as error:
        raise H3ImageContractError("Return one complete two-field JSON object without mixed prose / 请返回完整两字段JSON，不混入解释或截断内容。", "invalid_json") from error
    return data, wrapper, normalized


def parse_result(raw, task_type, aspect_ratio="auto", locked_text="", target_words=0):
    validate_controls(task_type, aspect_ratio, target_words, locked_text, 0)
    data, wrapper, normalized = _strict_json(raw)
    field = "aspect_ratio" if task_type == T2I else "target_aspect_ratio"
    if not isinstance(data, dict) or set(data) != {"expanded_caption", field}:
        _error("invalid_fields", "Return exactly expanded_caption and the task's ratio field / 只能返回expanded_caption和当前任务的比例字段。")
    caption, ratio = data["expanded_caption"], data[field]
    _text(caption, "expanded_caption")
    _text(ratio, field)
    if not caption.strip():
        _error("empty_caption", "expanded_caption cannot be empty / 扩写正文不能为空。")
    if any(char in caption for char in _LINE_BREAKS):
        _error("caption_linebreak", "expanded_caption must be one paragraph without line breaks / 扩写正文必须是无实际换行的单段。")
    if not (ratio in T2I_RATIOS if task_type == T2I else _RATIO.fullmatch(ratio)):
        _error("invalid_result_ratio", "The returned aspect ratio is invalid for this task / 返回比例不符合当前任务。")
    if aspect_ratio != "auto" and ratio != aspect_ratio:
        _error("aspect_ratio_mismatch", "Return the explicit requested ratio exactly / 返回比例须与明确指定的比例逐字一致。")
    cursor = 0
    lines = locked_lines(locked_text)
    for index, line in enumerate(lines, 1):
        found = caption.find(line, cursor)
        if found < 0:
            _error(f"missing_locked_line_{index}", f"Preserve exact visible-text line {index}, including its order/repetition / 请逐字保留锁定文案第{index}行及顺序和重复次数。")
        cursor = found + len(line)
    words = len(_WORDS.findall(caption))
    details = {"caption_words": words, "target_words": target_words,
               "word_count_delta": words - target_words if target_words else None,
               "word_count_method": "latin_word_regex", "word_target_is_soft": True,
               "normalized_wrapper": wrapper, "leading_reasoning_removed": normalized,
               "exact_text_order_verified": bool(lines), "locked_line_count": len(lines),
               "semantics_verified": False, "descriptive_language_verified": False,
               "downstream_token_check": "unverified", "downstream_token_limit": 4096}
    official = json.dumps({"expanded_caption": caption, field: ratio}, ensure_ascii=False)
    return caption, ratio, official, details


def response_format(task_type, aspect_ratio="auto"):
    validate_controls(task_type, aspect_ratio, 0, "", 0)
    field = "aspect_ratio" if task_type == T2I else "target_aspect_ratio"
    ratio_schema = {"type": "string"}
    if aspect_ratio != "auto":
        ratio_schema["enum"] = [aspect_ratio]
    elif task_type == T2I:
        ratio_schema["enum"] = list(T2I_RATIOS)
    else:
        ratio_schema["pattern"] = "^[1-9][0-9]*:[1-9][0-9]*$"
    return {"type": "json_schema", "json_schema": {"name": "h3_image_" + ("t2i" if task_type == T2I else "edit"),
            "strict": True, "schema": {"type": "object", "properties": {"expanded_caption": {"type": "string"}, field: ratio_schema},
                                       "required": ["expanded_caption", field], "additionalProperties": False}}}
