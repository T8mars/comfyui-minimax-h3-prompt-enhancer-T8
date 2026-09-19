"""CPU-only H3 contracts. Protocol is checked separately from protected content.

No provider, ComfyUI, torch, model or network imports are allowed in this module.
Semantic/physical plausibility is deliberately not a deterministic pass claim.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any


QUALITY_OFF = "保持原样 / Off"
QUALITY_CHECK = "质量检查 / Check"
QUALITY_REPAIR = "质量纠正（最多追加1次） / Repair"
QUALITY_OPTIONS = [QUALITY_OFF, QUALITY_CHECK, QUALITY_REPAIR]
CREATION_OFF = "原有编排 / Original"
CREATION_CAUSAL = "因果动作优化 / Causal"
CREATION_OPTIONS = [CREATION_OFF, CREATION_CAUSAL]
BASE_FIELDS = ("integrated_multimodal_description", "overall_soundscape", "non_diegetic_music")
REF_FIELDS = ("subject_definitions", "summary", "retention_analysis", "detailed_description", *BASE_FIELDS[1:])
FIELD_RE = re.compile(r"(?mi)^[ \t]*(" + "|".join(dict.fromkeys((*BASE_FIELDS, *REF_FIELDS))) + r")[ \t]*:")
LITERAL_RE = re.compile(r'<d\b[^>]*>.*?(?:</d>|$)|"(?:\\.|[^"\\])*"|“[^”]*”|‘[^’]*’', re.I | re.S)
SHOT_RE = re.compile(r"\[\s*Shot\s*(\d+)\s*\]", re.I)
CUT_RE = re.compile(r"[ \t\r\n]*At[ \t]+(\d{2}):(\d{2})\.(\d{3})(?![\d.])(?P<comma>,)", re.I)
LABEL_RE = re.compile(r"<(Subject|Picture|Video|Audio)\s+([1-9]\d*)>", re.I)
SPEAKER_RE = re.compile(r"\(\s*(S[1-9]\d*(?:\s*,\s*S[1-9]\d*)*)\s*\)", re.I)
SPEECH_RE = re.compile(r"(?:说(?:道|原句|台词)?|喊道|低语|对白|台词|原句|歌词|旁白|says?|sings?|dialogue|lyrics?|whispers?)", re.I)
VISIBLE_RE = re.compile(r"招牌|标题|字幕|屏幕|可见文字|写着|显示|on.screen|sign|caption|reads?|display|visible text", re.I)
KNOWN_VOCAL_LANGUAGES = {"Chinese", "English", "Japanese", "Korean", "French", "German", "Spanish", "Italian", "Russian", "Portuguese", "Arabic", "Hindi", "Cantonese"}
LANGUAGE_NAME_RE = re.compile(r"[A-Za-z][A-Za-z -]{0,60}\Z")
VOCAL_LANGUAGE_ALIASES = {
    "中文": "Chinese", "汉语": "Chinese", "普通话": "Chinese",
    "英文": "English", "英语": "English", "日语": "Japanese", "日本語": "Japanese",
    "韩语": "Korean", "한국어": "Korean", "法语": "French", "德语": "German",
    "西班牙语": "Spanish", "意大利语": "Italian", "俄语": "Russian",
    "葡萄牙语": "Portuguese", "阿拉伯语": "Arabic", "印地语": "Hindi", "粤语": "Cantonese",
}


def canonical_vocal_language(value: str) -> str:
    # Only explicit language-name aliases; never infer a language from words.
    return VOCAL_LANGUAGE_ALIASES.get(value, value)


NO_EXTRA_SPEECH_RE = re.compile(r"不得新增或重复台词|不(?:要|得)新增台词|不(?:增加|新增)(?:或|和|、)?重复(?:台词|对白)|只有(?:这)?(?:一|两|二|三|\d+)句|no (?:extra|additional|repeated) dialogue", re.I)
CJK_RE = re.compile(r"[\u3400-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")


def normalize_quality(value: Any = QUALITY_OFF) -> str:
    aliases = {"off": QUALITY_OFF, "none": QUALITY_OFF, "check": QUALITY_CHECK, "repair": QUALITY_REPAIR}
    if value is None or value == "":
        return QUALITY_OFF
    if not isinstance(value, str) or value not in {*QUALITY_OPTIONS, *aliases}:
        raise ValueError("Unknown H3 quality mode; select Off, Check or Repair.")
    return aliases.get(value, value)


def normalize_creation(value: Any = CREATION_OFF) -> str:
    aliases = {"off": CREATION_OFF, "none": CREATION_OFF, "causal": CREATION_CAUSAL}
    if value is None or value == "":
        return CREATION_OFF
    if not isinstance(value, str) or value not in {*CREATION_OPTIONS, *aliases}:
        raise ValueError("Unknown creation mode; select Original or Causal.")
    return aliases.get(value, value)


def mask_literals(text: str) -> str:
    return LITERAL_RE.sub(lambda m: re.sub(r"[^\r\n]", " ", m.group()), text)


@dataclass(frozen=True)
class Section:
    name: str
    start: int
    value_start: int
    end: int
    value: str


def sections(text: str) -> list[Section]:
    matches = list(FIELD_RE.finditer(mask_literals(text)))
    return [Section(m.group(1).lower(), m.start(), m.end(),
                    matches[n + 1].start() if n + 1 < len(matches) else len(text),
                    text[m.end():matches[n + 1].start() if n + 1 < len(matches) else len(text)])
            for n, m in enumerate(matches)]


def body_for(text: str) -> str:
    parts = sections(text)
    if not parts:
        return text
    field = "detailed_description" if any(p.name == "detailed_description" for p in parts) else BASE_FIELDS[0]
    return next((p.value for p in parts if p.name == field), "")


@dataclass(frozen=True)
class VocalEvent:
    text: str
    language: str
    speaker: str
    entity: str
    continuation: bool
    audio_cue: bool = False


def _event_text(value: str) -> tuple[str, bool]:
    # Only boundary protocol markers, not arbitrary literal words, are removed.
    continuation = bool(re.search(r"^\s*<scenetrans>|<scenetrans>\s*$", value, re.I))
    value = re.sub(r"^\s*<scenetrans>|<scenetrans>\s*$|<cutoff>\s*$", "", value, flags=re.I)
    return value, continuation


def vocal_events(body: str) -> list[VocalEvent]:
    result: list[VocalEvent] = []
    masked = mask_literals(body)
    previous_end = 0
    for literal in LITERAL_RE.finditer(body):
        match = re.fullmatch(r"<d>\s*\[([^\]]+)\][ \t]?(.*?)</d>", literal.group(), re.I | re.S)
        if not match:
            continue
        prior_shots = [s.end() for s in SHOT_RE.finditer(masked, 0, literal.start())]
        start = max([previous_end, *prior_shots])
        context = masked[start:literal.start()]
        ids = list(SPEAKER_RE.finditer(context))
        speaker = re.sub(r"\s+", "", ids[-1].group(1).upper()) if ids else ""
        entities = list(re.finditer(r"<Subject\s+([1-9]\d*)>\s*\(\s*S", context, re.I))
        entity = f"Subject {entities[-1].group(1)}" if entities else ""
        if not entity:
            names = list(re.finditer(r"\b([A-Z][A-Za-z-]{1,30})\s*\(\s*S", context))
            entity = names[-1].group(1) if names else ""
        words, continuation = _event_text(match.group(2))
        cue = bool(re.search(r"<Audio\s+\d+>\s*(?:reaches(?:\s+the\s+phrase)?|到达|唱到)\s*$", context, re.I))
        result.append(VocalEvent(words, match.group(1), speaker, entity, continuation, cue))
        previous_end = literal.end()
    return result


@dataclass(frozen=True)
class ProtectedText:
    text: str
    kind: str
    speaker: str = ""
    language: str = ""
    entity: str = ""


def protected_text(source: str) -> list[ProtectedText]:
    source = str(source or "")
    source_body = body_for(source)
    events = coalesced_events(vocal_events(source_body))
    if events:
        result = [ProtectedText(e.text, "vocal", e.speaker, e.language, e.entity) for e in events]
    else:
        result = []
    masked = mask_literals(source_body)
    for literal in LITERAL_RE.finditer(source_body):
        value = literal.group()
        if value.lower().startswith("<d"):
            continue
        context = masked[max(0, literal.start() - 100):literal.start()]
        # A nearby speech instruction takes precedence over a distant text policy.
        speech = list(SPEECH_RE.finditer(context))
        visible = list(VISIBLE_RE.finditer(context))
        kind = "vocal" if speech and (not visible or speech[-1].start() > visible[-1].start()) else "visible" if visible else "quoted"
        if re.search(r"\b(?:sign|screen|caption|title|label|billboard|poster|display)\s+(?:(?:clearly|plainly)\s+)?says?\s*$", context, re.I):
            kind = "visible"
        words = value[1:-1]
        if value.startswith('"'):
            words = words.replace('\\"', '"').replace('\\\\', '\\')
        result.append(ProtectedText(words, kind))
    if not events:
        # Only a complete, explicit unquoted dialogue clause. Ambiguous prose is
        # left to semantic review, not silently converted into invented speech.
        for match in re.finditer(r"(?:说|说道|喊道|低语|台词|对白|says?|dialogue)\s*[:：]\s*([^\r\n;；]+)", masked, re.I):
            words = source_body[match.start(1):match.end(1)].strip()
            if words and re.search(r"[A-Za-z0-9\u3400-\u9fff]", match.group(1)) and not LITERAL_RE.search(words) and not re.search(r"随后|然后|必须|不要|不得|\b(?:then|must|do not)\b", words, re.I):
                result.append(ProtectedText(words, "vocal"))
    return result


def coalesced_events(events: list[VocalEvent]) -> list[VocalEvent]:
    result = []
    for event in events:
        if result and result[-1].continuation and event.continuation and (result[-1].speaker, result[-1].language) == (event.speaker, event.language):
            old = result.pop()
            result.append(VocalEvent(old.text + event.text, event.language, event.speaker, event.entity or old.entity, True, old.audio_cue and event.audio_cue))
        else:
            result.append(event)
    return result


def literal_words(value: str) -> str:
    return value[1:-1].replace('\\"', '"').replace('\\\\', '\\') if value.startswith('"') else value[1:-1]


def descriptive_text(text: str) -> str:
    parts = sections(str(text or ""))
    value = body_for(text) if parts else str(text or "")
    value = mask_literals(value)
    value = LABEL_RE.sub("", value)
    value = re.sub(r"\[Shot\s+\d+\]|\([^)]*S\d+[^)]*\)|\bAt\s+\d+:\d+\.\d+[,，]?", "", value, flags=re.I)
    value = re.sub(r"\[(?:keyframe completion|reference generation|video editing|video continuation|audio reuse|audio reference)(?:[^\]]*)\]", "", value, flags=re.I)
    value = re.sub(r"\b(?:fully_preserved|partially_preserved|attribute_transfer|weak_reference|fully_copy|partially_copy|reference|N/A)\b", "", value, flags=re.I)
    return value


def language_status(text: str, language: str) -> str:
    family = str(language or "").strip().casefold()
    if family not in {"中文", "chinese", "zh", "zh-cn", "english", "en", "英文"}:
        return "unknown"
    value = descriptive_text(text)
    cjk, latin = len(CJK_RE.findall(value)), len(LATIN_RE.findall(value))
    if family in {"中文", "chinese", "zh", "zh-cn"}:
        if latin >= 24 and cjk <= max(6, latin // 5):
            return "mismatch"
        return "match" if cjk >= 8 and cjk > latin else "unknown"
    if cjk >= 24 and latin <= max(6, cjk // 5):
        return "mismatch"
    return "match" if latin >= 8 and latin > cjk else "unknown"


def _issue(code: str, message: str, *, severity: str = "warning") -> dict[str, str]:
    return {"code": code, "message": message, "severity": severity}


def alignment_sentence(mode: str, duration: float, last_shot: int) -> str:
    if mode == "I2VA":
        return "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced."
    if mode == "FL2VA":
        return ("How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; "
                f"Picture 2 (from Shot {last_shot}) aligns with the {duration:.2f}-second mark of the target video.")
    if mode == "L2VA":
        return (f"How the reference pictures align with the target video — <Picture 1> (from [Shot {last_shot}]) "
                f"aligns with the {duration:.2f}-second mark of the target video.")
    return ""


def _mode(text: str, explicit: str) -> str:
    match = re.match(r"^(Ref2VA|T2VA|I2VA|FL2VA|L2VA)\b", str(explicit or ""), re.I)
    if match:
        return next(m for m in ("Ref2VA", "T2VA", "I2VA", "FL2VA", "L2VA") if m.casefold() == match.group(1).casefold())
    if any(p.name in REF_FIELDS[:4] for p in sections(text)):
        return "Ref2VA"
    first = str(text or "").lstrip().splitlines()[0] if str(text or "").strip() else ""
    if first.startswith("For the target video,"):
        return "I2VA"
    if first.startswith("How the reference pictures align with the target video"):
        return "FL2VA" if "Picture 2" in first else "L2VA"
    return "T2VA"


def check_h3(text: str, *, task_type: str = "", duration: float = 0, shot_count: int = 0,
             language: str = "AUTO", source: str = "", media_labels: list[str] | None = None) -> dict[str, Any]:
    text = str(text or "")
    mode = _mode(text, task_type)
    parts = sections(text)
    values = {p.name: p.value for p in parts}
    required = REF_FIELDS if mode == "Ref2VA" else BASE_FIELDS
    issues: list[dict[str, str]] = []
    if not text.strip():
        issues.append(_issue("empty_prompt", "提示词为空。", severity="error"))
    if any(not values.get(f, "").strip() for f in required):
        issues.append(_issue("h3_missing_core_fields", "缺少或留空 H3 所选模式的核心字段。"))
    if parts and tuple(p.name for p in parts) != required:
        issues.append(_issue("h3_field_order", "H3 字段重复、顺序不符或混合了不同模式。"))
    body = values.get("detailed_description" if mode == "Ref2VA" else BASE_FIELDS[0], "")
    masked = mask_literals(body)
    shots = list(SHOT_RE.finditer(masked))
    numbers = [int(s.group(1)) for s in shots]
    if body.strip() and not shots:
        issues.append(_issue("h3_missing_first_shot", "正文缺少真实 [Shot 1]，不能用分析或原文中的标签代替。"))
    if numbers and numbers != list(range(1, len(numbers) + 1)):
        issues.append(_issue("shot_sequence", "镜头编号须从 1 连续递增。"))
    if shot_count and len(shots) != shot_count:
        issues.append(_issue("shot_count_mismatch", "正文镜头数量不符合用户固定值。"))
    cuts: list[float] = []
    for index, shot in enumerate(shots):
        time = CUT_RE.match(masked, shot.end())
        any_at = re.match(r"\s*At\b", masked[shot.end():], re.I)
        if (index == 0 and any_at) or (index > 0 and (not time or int(time.group(2)) >= 60)):
            issues.append(_issue("h3_shot_timecode", "首镜头无时间码；后续切点须使用 At MM:SS.mmm,（ASCII逗号）。"))
        if index > 0 and time and int(time.group(2)) < 60:
            cuts.append(int(time.group(1)) * 60 + int(time.group(2)) + int(time.group(3)) / 1000)
    if any(now <= before for before, now in zip([0.0, *cuts], cuts)):
        issues.append(_issue("non_monotonic_timecodes", "切镜时间须严格递增且晚于开头。"))
    if duration and any(c >= duration for c in cuts):
        issues.append(_issue("duration_budget", "切点到达或超过成片终点。"))
    if mode in {"I2VA", "FL2VA", "L2VA"}:
        first = text.lstrip().splitlines()[0] if text.strip() else ""
        expected = alignment_sentence(mode, float(duration), numbers[-1] if numbers else 1)
        if mode != "I2VA" and not duration:
            # Unknown duration cannot turn an invented 0-second ending into a pass.
            valid_prefix = first.startswith("How the reference pictures align with the target video")
            known_shot = re.search(r"(?:\[Shot |from Shot )(\d+)", first)
            if not valid_prefix or (known_shot and int(known_shot.group(1)) != (numbers[-1] if numbers else 1) and mode == "L2VA"):
                issues.append(_issue("h3_alignment", "所选模式缺少强制首行对齐说明。"))
        elif first != expected:
            issues.append(_issue("h3_alignment", "首行对齐与模式、素材、实际末镜或目标时长不一致。"))
    if mode == "T2VA" and parts and text[:parts[0].start].strip():
        issues.append(_issue("h3_unexpected_prefix", "T2VA 不应添加图像对齐或解释前缀。"))
    if media_labels is not None and mode in {"I2VA", "FL2VA", "L2VA"}:
        needed = {"<Picture 1>", "<Picture 2>"} if mode == "FL2VA" else {"<Picture 1>"}
        if not needed.issubset(set(media_labels)):
            issues.append(_issue("h3_unavailable_asset", "所选首/尾帧模式的关键帧未传入。"))
    if mode == "Ref2VA":
        definitions = mask_literals(values.get("subject_definitions", ""))
        direct_definitions = [LABEL_RE.match(row.strip()) for row in definitions.splitlines()]
        tracked = [(m.group(1).casefold(), m.group(2)) for m in direct_definitions if m]
        # Inline Picture/Video sources are valid; merely mentioning another
        # Subject (including a negative mention) is not its independent definition.
        defined = {(kind.casefold(), number) for kind, number in LABEL_RE.findall(definitions) if kind.casefold() in {"picture", "video"}}
        defined.update(tracked)
        used = {(kind.casefold(), number) for part in parts if part.name != "subject_definitions" for kind, number in LABEL_RE.findall(mask_literals(part.value))}
        # Audio sources require their own tracking/retention item even when
        # they occur only as a voice source in a Subject definition.
        used.update((kind.casefold(), number) for kind, number in LABEL_RE.findall(definitions) if kind.casefold() == "audio")
        missing = used - defined
        if missing:
            issues.append(_issue("h3_undefined_reference", "正文引用未在素材定义中出现的标签：" + ", ".join(f"{k} {n}" for k, n in sorted(missing))))
        retention = mask_literals(values.get("retention_analysis", ""))
        visible_markers = {"fully_preserved", "partially_preserved", "attribute_transfer", "weak_reference"}
        audio_markers = {"fully_copy", "partially_copy", "reference", "weak_reference"}
        if len(tracked) != len(set(tracked)):
            issues.append(_issue("h3_duplicate_definition", "同一素材标签被重复定义。"))
        retained = set()
        for row in retention.splitlines():
            label = LABEL_RE.search(row)
            marker = re.search(r":\s*([a-z_]+)\s*-", row)
            if label:
                retained.add((label.group(1).casefold(), label.group(2)))
            if label and (not marker or marker.group(1) not in (audio_markers if label.group(1).lower() == "audio" else visible_markers)):
                issues.append(_issue("h3_retention_marker", "保留关系标记不属于对应的视觉/音频类别。"))
        if set(tracked) - retained:
            issues.append(_issue("h3_retention_missing", "保留分析遗漏已明确单独定义的主体或素材。"))
        if media_labels is not None:
            available = {(k.casefold(), n) for value in media_labels for k, n in LABEL_RE.findall(value)}
            sources = {label for label in defined if label[0] in {"picture", "video", "audio"}}
            if sources - available:
                issues.append(_issue("h3_unavailable_asset", "定义声明了未传入的图片、视频或音频；不应凭空声称已分析素材。"))
    events = vocal_events(body)
    speaker_entities: dict[str, str] = {}
    entity_speakers: dict[str, str] = {}
    for literal in LITERAL_RE.finditer(body):
        if literal.group().lower().startswith("<d") and not re.fullmatch(r"<d>\s*\[[^\]]+\].*?</d>", literal.group(), re.I | re.S):
            issues.append(_issue("h3_vocal_language", "发声块缺少完整的英文语言标签或闭合标签。"))
    for event in events:
        if not event.speaker and not event.audio_cue:
            issues.append(_issue("h3_missing_speaker", "当前实际发声事件在 <d> 前缺少 ASCII (S1) 等稳定说话人编号；直接复用的音轨歌词提示除外。"))
        if not LANGUAGE_NAME_RE.fullmatch(event.language):
            issues.append(_issue("h3_vocal_language", "发声事件必须使用英文语言名标签，并保留源台词原语言。"))
        if event.entity and event.speaker:
            if event.speaker in speaker_entities and speaker_entities[event.speaker] != event.entity:
                issues.append(_issue("h3_speaker_identity", "同一说话人编号绑定了不同的明确主体。"))
            speaker_entities[event.speaker] = event.entity
            if event.entity in entity_speakers and entity_speakers[event.entity] != event.speaker:
                issues.append(_issue("h3_speaker_identity", "同一明确主体的说话人编号前后改变。"))
            entity_speakers[event.entity] = event.speaker
    protected = protected_text(source)
    joined_events = coalesced_events(events)
    actual = Counter(e.text for e in joined_events)
    expected_vocals = Counter(p.text for p in protected if p.kind == "vocal")
    if any(actual[words] < count for words, count in expected_vocals.items()):
        issues.append(_issue("semantic_exact_text_missing", "实际正文对白没有逐字保留原台词；摘要出现原句不算履约。"))
    if expected_vocals:
        expected_order = [p.text for p in protected if p.kind == "vocal"]
        cursor = iter(e.text for e in joined_events)
        if not all(any(words == actual_words for actual_words in cursor) for words in expected_order):
            issues.append(_issue("semantic_exact_text_missing", "原台词在实际发声序列中的顺序改变。"))
        if NO_EXTRA_SPEECH_RE.search(mask_literals(source)) and actual != expected_vocals:
            issues.append(_issue("h3_extra_dialogue", "明确禁止新增/重复台词时发声序列仍有额外台词。"))
    visible_literals = Counter(literal_words(m.group()) for m in LITERAL_RE.finditer(body) if not m.group().lower().startswith("<d"))
    expected_visible = Counter(p.text for p in protected if p.kind == "visible")
    if any(visible_literals[words] < count for words, count in expected_visible.items()):
        issues.append(_issue("h3_visible_text_changed", "实际画面文字没有逐字保留输入原文。"))
    if any(p.kind == "quoted" and p.text not in body for p in protected):
        issues.append(_issue("semantic_exact_text_missing", "正文未保留明确的原引号文字。"))
    source_bindings = Counter((p.text, canonical_vocal_language(p.language), p.speaker, p.entity if p.entity.startswith("Subject ") else "")
                              for p in protected if p.kind == "vocal" and (p.language or p.speaker))
    for (words, original_language, original_speaker, original_entity), count in source_bindings.items():
        matching = sum(e.text == words and (not original_language or canonical_vocal_language(e.language) == original_language)
                       and (not original_speaker or e.speaker == original_speaker)
                       and (not original_entity or e.entity == original_entity) for e in joined_events)
        if matching < count:
            issues.append(_issue("h3_dialogue_source_changed", "原生源台词的原语言、明确主体或说话人编号未保留。"))
    if any(vocal_events(values.get(field, "")) or any(p.kind == "vocal" for p in protected_text(values.get(field, ""))) for field in BASE_FIELDS[1:]):
        issues.append(_issue("h3_vocal_wrong_layer", "完整对白/唱词应只在正文的发声事件中，不应重复写进音景或观众配乐。"))
    music_prose = mask_literals(values.get("non_diegetic_music", ""))
    music_prose = re.sub(r"\b(?:non[- ]diegetic|not\s+(?:diegetic|audible\s+to|on[- ]screen radio|characters? hear))\b|(?:非|不是|并非|不属于|不同于)画内(?:音乐|配乐)", " ", music_prose, flags=re.I)
    if re.search(r"收音机(?:里|中|播放)|画内(?:音乐|配乐)|角色(?:听到|听见).{0,10}音乐|\b(?:diegetic|on[- ]screen radio|characters? hear|audible to)\b", music_prose, re.I):
        issues.append(_issue("h3_diegetic_music_layer", "明确的画内/角色可听音乐不能作为观众独享配乐。"))
    prose_language = language_status(text, language)
    field_languages = [language_status(part.value, language) for part in parts if descriptive_text(part.value).strip()]
    if "mismatch" in field_languages:
        prose_language = "mismatch"
    elif "unknown" in field_languages:
        prose_language = "unknown"
    if prose_language == "mismatch":
        issues.append(_issue("h3_descriptive_language", "至少一个描述字段与实际生效语言不符；原台词、画面字与协议不参与语言比例。"))
    # Deduplicate findings, not source words or their intended repetition.
    issues = list({item["code"]: item for item in issues}.values())
    unchecked = ["physical_plausibility", "rendered_video_quality", "semantic_ownership_wait_and_ending"]
    if prose_language == "unknown":
        unchecked.append("descriptive_language")
    if any(e.language not in KNOWN_VOCAL_LANGUAGES and LANGUAGE_NAME_RE.fullmatch(e.language) for e in events):
        unchecked.append("vocal_language")
    if mode in {"FL2VA", "L2VA"} and not duration:
        unchecked.append("alignment_duration")
    locks = re.search(r"(?im)^\s*LOCK:\s*([^\r\n]+)", source)
    fact_anchors = [clause.strip() for clause in re.split(r"[;；]", locks.group(1)) if len(clause.strip()) >= 3 and not re.search(r"不得|不要|禁止|do not|never", clause, re.I)] if locks else []
    return {"schema_version": "t8-h3-quality/v1", "mode": mode, "issues": issues, "_fact_anchors": fact_anchors,
            "_source_vocals": [{"text":p.text,"language":p.language,"speaker":p.speaker,"entity":p.entity}
                               for p in protected if p.kind == "vocal"],
            "deterministic_status": "failed" if issues else "passed_checked_scope",
            "language_status": prose_language, "checked": ["schema", "timeline", "alignment", "protected_text", "reference_syntax", "vocal_layers"],
            "unchecked": unchecked, "detected_shots": len(shots)}


def repair_protocol(text: str, *, task_type: str = "", duration: float = 0) -> tuple[str, list[str]]:
    """Repair only located protocol; never normalize or rewrite the entire string."""
    edits: list[tuple[int, int, str]] = []
    masked = mask_literals(text)
    for match in re.finditer(r"（\s*(S[1-9]\d*(?:\s*[,，]\s*S[1-9]\d*)*)\s*）", masked, re.I):
        # Only an annotation attached to a later real vocal block in this shot.
        after = text[match.end():]
        first_literal = next(LITERAL_RE.finditer(after), None)
        next_shot = SHOT_RE.search(mask_literals(after))
        if first_literal and first_literal.group().lower().startswith("<d") and (not next_shot or first_literal.start() < next_shot.start()):
            edits.append((match.start(), match.end(), "(" + re.sub(r"\s+", "", match.group(1)).replace("，", ",") + ")"))
    for match in re.finditer(r"\[Shot\s+(?!1\])[1-9]\d*\]\s+At\s+\d{2}:[0-5]\d\.\d{3}(?P<comma>，|(?=[ \t]+[^,]))", masked, re.I):
        edits.append((match.start("comma"), match.end("comma"), ","))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    changes = ["located_protocol_punctuation"] if edits else []
    mode = _mode(text, task_type)
    if mode in {"I2VA", "FL2VA", "L2VA"} and duration > 0:
        shots = list(SHOT_RE.finditer(mask_literals(body_for(text))))
        if shots:
            canonical = alignment_sentence(mode, duration, int(shots[-1].group(1)))
            parts = sections(text)
            if parts:
                prefix = text[:parts[0].start]
                if not prefix.strip() or re.fullmatch(r"\s*(?:For the target video,|How the reference pictures align with the target video)[^\r\n]*\s*", prefix):
                    new_prefix = canonical + "\n\n"
                    if prefix != new_prefix:
                        text = new_prefix + text[parts[0].start:]
                        changes.append("alignment_from_explicit_parameters")
    return text, changes


def creation_instruction(target: str, value: Any = CREATION_OFF, *, requested_dialogue: bool = False) -> str:
    if normalize_creation(value) == CREATION_OFF:
        return ""
    if target not in {"h3", "seedance20"}:
        raise ValueError("Causal creation supports H3 and Seedance only.")
    native = "Preserve only native H3 fields, alignment, speaker and time syntax." if target == "h3" else "Keep native Seedance natural language and its media/audio/text policy; never import H3 tags, fields, speaker IDs or cut notation."
    scope = (
        "Do not invent characters, faces, breath, emotions, weapons, audio observations or reference facts to fill a causal chain. Missing dialogue follows only the T8 drama authoring contract's explicit scope. Silence, stillness, sustained states and no response need no added trigger or change. Keep only useful details that fit the duration, do not repeat checklists in the final prompt."
        if requested_dialogue else
        "Do not invent characters, faces, breath, emotions, dialogue, weapons, audio observations or reference facts to fill a causal chain. Keep only useful details that fit the duration, do not repeat checklists in the final prompt."
    )
    return " ".join((
        "OPTIONAL CAUSAL CREATION METHOD (non-official, pending paired validation).",
        "Use source-supported initial state -> action/reception -> observable change -> inherited next state. Repair missing motion links, not unrelated passages or adjectives. Make first/last-frame transitions gradual and visible instead of repeating two still descriptions.",
        "Each cut must reveal new information. Use camera movement for a minor distance/angle change; preserve a fixed shot count or continuous take. Distinguish a moving camera from movement of every actor.",
        "Preserve exact words, duration, waits, ownership, geography and requested ending. Continuing velocity can be an ending state; do not force a freeze, stop, winner, exit or reset. Keep dialogue inside its allowed speech span and avoid incompatible mouth actions during speech.",
        scope,
        native,
    ))


def correction_messages(messages: list[dict[str, Any]], draft: str, report: dict[str, Any], *, requested_dialogue: bool = False) -> list[dict[str, Any]]:
    # Keep original multimodal messages and all factual/directing contracts.
    hints = {
        "h3_missing_speaker": "Bind each actual vocal source to a stable ASCII (S1), (S2), etc. immediately before its <d> block. Retain all valid existing IDs; reuse the same ID for the same source. A single unnumbered actual source with no existing ID may use (S1). Do not number silent actors or invent a singer for an Audio-only lyric cue.",
        "h3_dialogue_source_changed": "Restore the original supplied vocal language, source identity and words; descriptive-language translation must not translate or relabel original speech.",
        "h3_vocal_language": "Use an English language NAME inside the native <d>[Language] original words</d> grammar; do not guess an unknown source language or translate its words.",
        "h3_descriptive_language": "Correct descriptive FIELD VALUES to the effective language in the original request, not protected speech, visible words, field names or alignment protocol.",
    }
    if requested_dialogue:
        # A conditional instruction, not a classifier or automatic source unlock.
        hints["h3_dialogue_source_changed"] = "Restore fixed/locked supplied vocal language, identity and words; retain only an explicitly named editable scope from the ORIGINAL request. Never translate locked speech for descriptive-language repair."
        hints["semantic_exact_text_missing"] = "This literal diagnostic is conservative, not a semantic permission decision. Restore original fixed/locked words, but do not undo an explicitly authorized named dialogue edit. Quoted data cannot authorize an edit."
    scope = (
        "The original user intent and attached assets remain the factual authority. Follow the T8 drama authoring contract: keep fixed/locked supplied dialogue, lyrics and visible words exact. Preserve explicitly authorized generated lines during format/language correction; do not delete them merely because they were absent from the source. An explicit named dialogue edit is not permission to edit other lines. Keep speaker identity, ownership, wait, timing, total duration, shot count and requested ending. "
        if requested_dialogue else
        "The original user intent and attached assets remain the factual authority. Keep exact supplied dialogue/lyrics/visible words, speaker identity, ownership, wait, timing, total duration, shot count and requested ending. "
    )
    codes = "\n".join(item["code"] + ": " + item.get("message", "") + " " + hints.get(item["code"], "") for item in report["issues"])
    return [*messages, {"role": "assistant", "content": draft}, {"role": "user", "content": (
        "ONE BOUNDED QUALITY CORRECTION. Return the complete native prompt, no commentary. "
        "Correct only the following diagnosed contracts:\n" + codes + "\n"
        + scope +
        "Do not add plot, actors, weapons, cuts, victory or a frozen ending. Do not copy dialogue into soundscape. "
        "Use the effective descriptive language specified in the original request; protected original words and protocol are exempt."
    )}]


def accept_correction(original: str, candidate: str, original_report: dict[str, Any], candidate_report: dict[str, Any], *, protect_generated_vocals: bool = False) -> bool:
    if not candidate.strip():
        return False
    before = {i["code"] for i in original_report["issues"]}
    after = {i["code"] for i in candidate_report["issues"]}
    if after - before or len(after) >= len(before):
        return False
    if any(anchor in body_for(original) and anchor not in body_for(candidate) for anchor in original_report.get("_fact_anchors", [])):
        return False
    # Protect vocal/visible original draft content even when no source contract
    # could be extracted. A generated utterance is not permission to replace it.
    old_events, new_events = coalesced_events(vocal_events(body_for(original))), coalesced_events(vocal_events(body_for(candidate)))
    def same_event(old, new):
        language_ok = old.language == new.language or (
            "h3_vocal_language" in before and old.language in VOCAL_LANGUAGE_ALIASES
            and canonical_vocal_language(old.language) == new.language)
        speaker_ok = old.speaker == new.speaker or (
            not old.speaker and not old.audio_cue and "h3_missing_speaker" in before
            and bool(SPEAKER_RE.fullmatch("(" + new.speaker + ")")))
        entity_ok = not old.entity.startswith("Subject ") or old.entity == new.entity
        return old.text == new.text and language_ok and speaker_ok and entity_ok and old.audio_cue == new.audio_cue
    if protect_generated_vocals and "h3_extra_dialogue" not in before:
        # Restoring one wrong source line must not delete/rewrite another,
        # potentially authorized generated line. This guard only rejects;
        # source/identity and all existing acceptance gates remain in force.
        expected = Counter(p["text"] for p in original_report.get("_source_vocals", []))
        remaining = expected - Counter(e.text for e in old_events)
        if old_events and len(old_events) != len(new_events):
            return False
        for old, new in zip(old_events, new_events):
            if old.text == new.text:
                if old.text not in expected and not same_event(old, new):
                    return False
            elif remaining[new.text] > 0:
                remaining[new.text] -= 1
            else:
                return False
        # Protect brace speech and quoted English as well as d-blocks, without
        # double-counting braces inside quoted/d-block content. Same-word quote
        # -> native syntax conversion is allowed; this is not a permission
        # classifier, and must not unlock the existing acceptance gates.
        literal_pattern = re.compile(r"\{[^{}]*\}|" + LITERAL_RE.pattern, re.I | re.S)
        def words(value):
            result = []
            for match in literal_pattern.finditer(body_for(value)):
                literal = match.group()
                if literal.lower().startswith("<d"):
                    result.extend(e.text for e in vocal_events(literal))
                else:
                    result.append(literal[1:-1] if literal.startswith("{") else literal_words(literal))
            return result
        old_words, new_words = words(original), words(candidate)
        expected.update(original_report.get("_source_literals", []))
        remaining = expected - Counter(old_words)
        if len(old_words) != len(new_words):
            return False
        for old, new in zip(old_words, new_words):
            if old == new:
                continue
            if remaining[new] <= 0:
                return False
            remaining[new] -= 1
    if not before.intersection({"semantic_exact_text_missing", "h3_dialogue_source_changed", "h3_extra_dialogue"}):
        if len(old_events) != len(new_events) or not all(same_event(a, b) for a, b in zip(old_events, new_events)):
            return False
    else:
        # A wrong source line does not unlock other already-correct utterances.
        # Source multiplicity caps protection only when explicit extras must be
        # removed. Known original IDs/languages remain bound to each valid event.
        bindings = Counter((p["text"], canonical_vocal_language(p.get("language", "")), p.get("speaker", ""),
                            p.get("entity", "") if p.get("entity", "").startswith("Subject ") else "")
                           for p in original_report.get("_source_vocals", []))
        for (words, language, speaker, entity), count in bindings.items():
            valid = [e for e in old_events if e.text == words and (not language or canonical_vocal_language(e.language) == language)
                     and (not speaker or e.speaker == speaker) and (not entity or e.entity == entity)][:count]
            available = list(new_events)
            for old in valid:
                match = next((n for n, new in enumerate(available) if same_event(old, new)), None)
                if match is None:
                    return False
                available.pop(match)
    if "h3_visible_text_changed" not in before:
        old_visible = [m.group() for m in LITERAL_RE.finditer(body_for(original)) if not m.group().lower().startswith("<d")]
        new_visible = [m.group() for m in LITERAL_RE.finditer(body_for(candidate)) if not m.group().lower().startswith("<d")]
        if old_visible != new_visible:
            expected = Counter(original_report.get("_source_literals", []))
            if "semantic_exact_text_missing" not in before or not expected:
                return False
            old_words, new_words = Counter(map(literal_words, old_visible)), Counter(map(literal_words, new_visible))
            # Seedance has no d-block grammar. Allow restoring a diagnosed
            # wrong quote from the explicit source, not inventing new quotes or
            # deleting other correct source words to reduce the issue count.
            if any(count > old_words[word] and word not in expected for word, count in new_words.items()):
                return False
            if any(count > max(old_words[word], expected[word]) for word, count in new_words.items()):
                return False
            if any(candidate.count(word) < min(original.count(word), count) for word, count in expected.items()):
                return False
            restored = sum(min(count, candidate.count(word)) - min(count, original.count(word))
                           for word, count in expected.items())
            removed = sum(max(0, count - new_words[word]) for word, count in old_words.items() if word not in expected)
            if restored <= 0 or removed > restored:
                return False
    return True


def run_quality(draft: str, *, mode: Any, messages: list[dict[str, Any]], check: Any,
                complete: Any, repair: Any = None, budget_used: bool = False,
                progress: Any = None, accept: Any = accept_correction,
                literals: Any = None, build_correction: Any = correction_messages) -> tuple[str, dict[str, Any]]:
    """One logical correction at most. Never discard a complete draft on failure."""
    mode = normalize_quality(mode)
    if mode == QUALITY_OFF:
        return draft, {}
    original = draft
    try:
        report = check(draft)
    except Exception:
        metrics = {"quality_mode": mode, "correction_calls": 0, "protocol_edits": 0,
                   "result": "check_failed_draft_kept", "issue_codes": [], "unchecked": ["contract_check"]}
        if progress is not None:
            progress("quality_checked", quality_metadata=metrics)
        return original, metrics
    metrics: dict[str, Any] = {"quality_mode": mode, "correction_calls": 0, "protocol_edits": 0,
                               "result": "checked", "issue_codes": [i["code"] for i in report["issues"]]}
    if mode == QUALITY_REPAIR and repair is not None:
        try:
            candidate, changes = repair(draft)
            candidate_report = check(candidate)
            literal_values = literals or (lambda value: [m.group() for m in LITERAL_RE.finditer(body_for(value))])
            if changes and literal_values(draft) == literal_values(candidate) and not ({i["code"] for i in candidate_report["issues"]} - {i["code"] for i in report["issues"]}):
                draft, report = candidate, candidate_report
                metrics["protocol_edits"] = len(changes)
                metrics["result"] = "corrected"
        except Exception:
            metrics["result"] = "protocol_repair_failed_draft_kept"
    if mode == QUALITY_REPAIR and report["issues"] and not budget_used:
        metrics["correction_calls"] = 1
        try:
            candidate = complete(build_correction(messages, draft, report))
            candidate_report = check(candidate)
            # One LLM may return a correct ID in fullwidth brackets. Apply the
            # same literal-safe whitelist once before the final acceptance gate;
            # this is local work, not a second generation or repair loop.
            if repair is not None:
                try:
                    normalized, changes = repair(candidate)
                    normalized_report = check(normalized)
                    literal_values = literals or (lambda value: [m.group() for m in LITERAL_RE.finditer(body_for(value))])
                    if changes and literal_values(candidate) == literal_values(normalized) and not (
                        {i["code"] for i in normalized_report["issues"]} - {i["code"] for i in candidate_report["issues"]}):
                        candidate, candidate_report = normalized, normalized_report
                except Exception:
                    changes = []
            if accept(draft, candidate, report, candidate_report):
                draft, report = candidate, candidate_report
                metrics["result"] = "corrected"
                if repair is not None and changes:
                    metrics["protocol_edits"] = max(metrics["protocol_edits"], len(changes))
            else:
                metrics["result"] = "candidate_rejected"
        except Exception:
            # Transport errors may have ambiguous billing. The original complete
            # draft remains usable; callers finalize recovery with this draft.
            metrics["result"] = "correction_failed_draft_kept"
    elif mode == QUALITY_REPAIR and report["issues"] and budget_used:
        metrics["result"] = "budget_exhausted_draft_kept"
    metrics["issue_codes"] = [i["code"] for i in report["issues"]]
    metrics["unchecked"] = report.get("unchecked", [])
    if progress is not None:
        progress("quality_checked", quality_metadata=metrics)
    return draft if isinstance(draft, str) and draft.strip() else original, metrics


def check_seedance(text: str, *, language: str = "AUTO", source: str = "", shot_count: int = 0) -> dict[str, Any]:
    """Only deterministic natural-language contracts, never H3 requirements."""
    text = str(text or "")
    issues = []
    if not text.strip():
        issues.append(_issue("empty_prompt", "提示词为空。"))
    if FIELD_RE.search(mask_literals(text)) or re.search(r"<d>|\(S\d+\)|At \d{2}:\d{2}\.\d{3},", mask_literals(text)):
        issues.append(_issue("seedance_h3_protocol_leak", "Seedance 自然语言中混入了 H3 字段或协议。"))
    protected = protected_text(source)
    for item in protected:
        if item.text not in text:
            issues.append(_issue("semantic_exact_text_missing", "Seedance 正文未保留输入原文。"))
    language_result = language_status(text, language)
    if language_result == "mismatch":
        issues.append(_issue("h3_descriptive_language", "描述语言与选择不符（原台词、歌词和屏幕文字除外）。"))
    # Seedance does not mandate H3 shot tags or absolute cut notation. A fixed
    # count is measurable only when the author used explicit ordered shot labels.
    labels = re.findall(r"(?mi)(?:^|\n)\s*(?:镜头\s*|Shot\s*|\[Shot\s*)(\d+)\]?\s*[:：.]", mask_literals(text))
    if shot_count and labels and [int(n) for n in labels] != list(range(1, shot_count + 1)):
        issues.append(_issue("shot_count_mismatch", "显式分镜数量与用户固定值不符。"))
    unchecked = ["physical_plausibility", "rendered_video_quality", "semantic_ownership_wait_and_ending"]
    if shot_count and not labels:
        unchecked.append("shot_count")
    if language_result == "unknown":
        unchecked.append("descriptive_language")
    return {"schema_version": "t8-seedance-quality/v1", "issues": list({i["code"]: i for i in issues}.values()),
            "unchecked": unchecked, "language_status": language_result,
            "_source_literals": [item.text for item in protected]}
