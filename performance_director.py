from __future__ import annotations

import re
from typing import Any, Mapping

from comfy_api.latest import io


PERFORMANCE_CONFIG_SCHEMA = "t8-performance-director-config/v1"
PERFORMANCE_AUTO = "AUTO（按人物 / 表演意图）"
PERFORMANCE_STRONG = "强化（明确表演结构）"
PERFORMANCE_EXTREME = "极致（深度表演重构）"
PERFORMANCE_OFF = "关闭（保持原编译）"
# Append the new value so the original three option indexes remain stable for
# hosts or third-party workflow tools that persisted an index instead of text.
PERFORMANCE_MODES = [PERFORMANCE_AUTO, PERFORMANCE_STRONG, PERFORMANCE_OFF, PERFORMANCE_EXTREME]
STORYBOARD_SOURCE_REPOSITORY = "https://github.com/phileiny/h3-storyboard-skill"
STORYBOARD_SOURCE_COMMIT = "ab65851f599435a1ff94ea4931949bd7bcaf069b"

T8PerformanceDirectorConfigIO = io.Custom("T8_PERFORMANCE_DIRECTOR_CONFIG")


class PerformanceDirectorConfigError(ValueError):
    pass


def build_performance_director_config(mode: Any = PERFORMANCE_AUTO) -> dict[str, Any]:
    normalized = str(mode or PERFORMANCE_AUTO).strip()
    if normalized not in PERFORMANCE_MODES:
        raise PerformanceDirectorConfigError(f"Unsupported performance director mode: {normalized}")
    return {
        "schema_version": PERFORMANCE_CONFIG_SCHEMA,
        "mode": normalized,
        "source": {
            "relationship": "community research inspiration; not an official MiniMax Skill",
            "repository": STORYBOARD_SOURCE_REPOSITORY,
            "commit": STORYBOARD_SOURCE_COMMIT,
            "evidence_level": "narrow observations pending independent paired validation",
        },
    }


def resolve_performance_mode(config: Any = None) -> str:
    if config is None:
        return PERFORMANCE_AUTO
    if not isinstance(config, Mapping) or config.get("schema_version") != PERFORMANCE_CONFIG_SCHEMA:
        raise PerformanceDirectorConfigError("Connected performance_director_config has an unsupported schema.")
    mode = str(config.get("mode") or PERFORMANCE_AUTO).strip()
    if mode not in PERFORMANCE_MODES:
        raise PerformanceDirectorConfigError(f"Unsupported performance director mode: {mode}")
    return mode


def h3_performance_instruction(
    config: Any = None,
    *,
    fixed_shot_count: int = 0,
    source_prompt: Any = "",
) -> str:
    mode = resolve_performance_mode(config)
    if mode == PERFORMANCE_OFF:
        return ""
    if mode == PERFORMANCE_EXTREME:
        strength = " ".join((
            "EXTREME PERFORMANCE REWRITE CONTRACT: this is a deep acting-direction rewrite, not merely an activation flag or a synonym-polish pass.",
            "Apply it only to requests or connected media that actually contain a person/character or explicit acting intent; never invent a character, plot event, emotion, or dialogue for a non-performance request.",
            "Treat any supplied native H3 prompt as an editable draft: preserve its facts, media identities, exact dialogue, timing/count contract, retention facts, and required H3 schema, but materially rewrite the summary and performance-bearing [Shot] passages when their acting causality is weak.",
            "Silently map each performance passage into an ordered dramatic chain: an existing concrete trigger or intention, a perceivable reception beat, one dominant physical/emotional response, and a visible residue or settled end state. Keep the chain temporally readable even when multiple beats must fit inside one shot.",
            "For dialogue, direct a brief preparation before speech, controlled gaze/breath/body behavior during the exact line, and a post-line residue after speech; never alter or extend the supplied words. For silent acting, make the change legible through ordered gaze, eyelid, breath, shoulder/neck, hand, or posture evidence rather than emotion labels.",
            "A valid extreme rewrite must improve dramatic causality, timing, or performance specificity in the performance-bearing passages; changing only adjectives, punctuation, or synonyms is insufficient. Do not rewrite unrelated visual, camera, sound, or retention content merely to appear different.",
        ))
    elif mode == PERFORMANCE_STRONG:
        strength = "When character performance is present, apply this structure explicitly."
    else:
        strength = "Apply this section only when the user's text or connected media actually contains a person/character, emotion, dialogue, reaction, or acting intent; otherwise ignore it completely."
    shot_rule = (
        f"The user fixed the shot count at {int(fixed_shot_count)}; never add or remove shots. Distribute the beats inside that exact contract."
        if int(fixed_shot_count or 0) > 0
        else
        "With AUTO shot count, split competing primary state changes when duration permits; do not use a universal numeric beat threshold."
    )
    return " ".join((
        "COMMUNITY-RESEARCH-INSPIRED PERFORMANCE DIRECTOR (not an official MiniMax Skill; soft guidance, not a proven model limit).",
        strength,
        "Build a readable acting arc as trigger -> reception -> one primary response -> settled/end state.",
        "Each shot should emphasize one primary state change. HARD CUE BUDGET: each trigger, reception, response, or settle beat may use no more than three observable cue channels per character unless the user explicitly requests dense choreography. Before returning, silently count distinct cue channels in every beat and delete the lowest-signal cues until the budget is met; do not evade the budget by listing many cues in one sentence.",
        "Translate abstract emotions into visible evidence such as gaze, eyelids, breathing, shoulders/neck, hands, or posture.",
        "Establish camera side and a concrete gaze target before prescribing head direction, eye direction, and micro-expression.",
        "For a large visible state change, prefer one motivated concealment strategy only when it does not conflict with the request. If the user explicitly requires the transformation to remain continuously visible, keep the changed attribute visible and use a blink, head move, occlusion, or cut only before or after the core change.",
        "Preserve every user-supplied dialogue line verbatim and never invent dialogue. Treat speaking as occupying time; do not schedule swallowing, finished-speaking mouth closure, or another incompatible mouth beat inside the same speaking span.",
        shot_rule,
        semantic_anchor_instruction(source_prompt),
        "User facts, fixed duration/count, exact text/dialogue, media roles, official H3 contract, hard constraints, and LOCK anchors always outrank this guidance.",
        "Return only the native H3 prompt; never print this checklist or its provenance."
    ))


def seedance_performance_instruction(
    config: Any = None,
    *,
    fixed_shot_count: int = 0,
    source_prompt: Any = "",
) -> str:
    mode = resolve_performance_mode(config)
    if mode == PERFORMANCE_OFF:
        return ""
    if mode == PERFORMANCE_EXTREME:
        strength = " ".join((
            "EXTREME PERFORMANCE REWRITE CONTRACT: perform a deep native Seedance acting-direction rewrite, not a light paraphrase or activation-only pass.",
            "Apply it only when the request or connected media contains a person/character or explicit acting intent; never invent a character, plot event, emotion, or speech for a non-performance request.",
            "Treat an already enhanced Seedance prompt as an editable draft. Preserve its facts, reference roles, exact dialogue, duration/count, continuity, stability, subtitle policy, and native natural-language organization, while materially rewriting performance-bearing timing and action passages whose causality is weak.",
            "Silently organize each performance passage as an ordered chain: an existing concrete trigger or intention, perceivable reception, one dominant response, and visible residue or settled state. The order must remain readable when several beats share one shot.",
            "For dialogue, stage preparation before speech, controlled gaze/breath/body behavior during the exact line, and post-line residue after it. For silent acting, replace generic emotion labels with ordered visible evidence from gaze, eyelids, breath, shoulders/neck, hands, or posture.",
            "A valid extreme rewrite must improve dramatic causality, timing, or performance specificity; adjective-only and synonym-only changes are insufficient. Leave unrelated visual, camera, sound, reference, and continuity content alone unless a performance beat requires coordination.",
        ))
    elif mode == PERFORMANCE_STRONG:
        strength = "When character performance is present, make the performance causality explicit."
    else:
        strength = "Apply only when the user's text or connected media actually contains a person/character, emotion, dialogue, reaction, or acting intent; otherwise skip this section."
    shot_rule = (
        f"The user fixed exactly {int(fixed_shot_count)} shots; never change that count."
        if int(fixed_shot_count or 0) > 0
        else
        "When shot count is automatic, separate competing primary state changes only when duration and task intent support it; no universal threshold is assumed."
    )
    return " ".join((
        "COMMUNITY-RESEARCH-INSPIRED PERFORMANCE DIRECTION (not an official Seedance Skill; soft guidance pending paired validation).",
        strength,
        "Keep the visible causal arc readable: trigger, reception, one primary response, then a settled/end state.",
        "HARD CUE BUDGET: each trigger, reception, response, or settle beat may use no more than three observable cue channels per character unless dense choreography is explicitly requested. Before returning, silently count distinct cue channels in every beat and delete the lowest-signal cues until the budget is met; do not evade the budget by listing many cues in one sentence.",
        "Establish camera side and a concrete gaze target before head direction and micro-expression.",
        "Hide a strong state change behind one motivated eye closure, head move, foreground/action occlusion, or cut only when appropriate. If the user explicitly asks for a continuously visible transformation, keep the changed attribute visible and place any concealment before or after the core change.",
        "Preserve supplied dialogue verbatim, never invent speech, and avoid incompatible mouth actions during the speaking span.",
        shot_rule,
        "Preserve Seedance's native media references, task intent, continuity, stability, subtitles, and output organization. Do not import another model's tags, speaker identifiers, millisecond timing, frame-grid notation, or output schema.",
        semantic_anchor_instruction(source_prompt),
        "User facts, fixed duration/count, exact text/dialogue, media roles, hard constraints, and LOCK anchors outrank this guidance. Return only the native Seedance prompt."
    ))


def storyboard_performance_instruction(
    model_target: str,
    config: Any = None,
    *,
    fixed_shot_count: int = 0,
    source_prompt: Any = "",
) -> str:
    mode = resolve_performance_mode(config)
    if mode == PERFORMANCE_OFF:
        return ""
    mode_rule = (
        "EXTREME STORYBOARD PERFORMANCE CONTRACT: for every performance-bearing shot, use the supplied story facts to fully resolve the dramatic trigger, reception beat, one dominant response, observable cues, gaze target, speech span, transition strategy, and settled residue. Treat an existing plan as an editable draft and materially improve causality or timing; adjective-only changes are insufficient. Never invent characters, plot events, emotions, or dialogue, and leave non-performance shots empty."
        if mode == PERFORMANCE_EXTREME
        else
        ""
    )
    target_rule = (
        "For Seedance targets, keep all direction in native natural language and do not import H3-only syntax or fields."
        if model_target == "Seedance 2.0"
        else
        "For a dual target, keep the performance IR model-neutral so each downstream compiler can express it natively."
        if "+" in str(model_target)
        else
        "For H3 targets, preserve the official H3 output contract while using these fields only as planning IR."
    )
    shot_rule = (
        f"The user fixed exactly {int(fixed_shot_count)} shots; do not change the count."
        if int(fixed_shot_count or 0) > 0
        else
        "AUTO may split competing primary state changes when time permits, without assuming a universal beat limit."
    )
    return " ".join(part for part in (
        mode_rule,
        "For every shot, also return dramatic_trigger, reception_beat, primary_performance_beat, observable_cues, gaze_target, speech_span, state_transition_strategy, and performance_risks.",
        "Use empty strings/lists for non-performance shots; never invent acting, speech, or emotion merely to fill fields.",
        "Observable cues must be visible gaze/eyelid/breath/shoulder/hand/posture evidence. Each trigger, reception, response, or settle beat may use no more than three cue channels per character unless dense choreography is explicit. Before returning, silently delete the lowest-signal cues from any beat that exceeds the budget. Establish camera and gaze target before facial direction.",
        "Each shot emphasizes one primary state change. A strong change may use one motivated eye/head/foreground/action occlusion or cut, but an explicitly continuous visible transformation must remain visible through its core change.",
        "Preserve exact dialogue and keep incompatible mouth actions outside its speaking span.",
        shot_rule,
        target_rule,
        semantic_anchor_instruction(source_prompt),
        "These are community-research-inspired planning fields, not an official model Skill or guaranteed quality score."
    ) if part)


_SEMANTIC_ANCHOR_GROUPS: tuple[tuple[str, ...], ...] = (
    ("瞳孔", "虹膜", "眼白", "眼睑", "睫毛"),
    ("pupil", "iris", "sclera", "eyelid", "eyelash"),
    ("嘴唇", "牙齿", "舌头", "下颌"),
    ("lips", "teeth", "tongue", "jaw"),
    ("手指", "手掌", "手腕", "手背"),
    ("finger", "palm", "wrist", "back of the hand"),
    ("表冠", "表圈", "表盘", "表壳", "表链", "指针", "秒针", "分针", "时针"),
    ("crown", "bezel", "dial", "case", "bracelet", "watch hand", "second hand", "minute hand", "hour hand"),
)
_NEIGHBOR_SUBSTITUTION_GROUPS = _SEMANTIC_ANCHOR_GROUPS[:6]
_COLOR_ANCHORS = (
    "红色", "橙色", "黄色", "金色", "绿色", "青色", "蓝色", "紫色", "粉色", "黑色", "白色", "银色", "灰色", "棕色",
    "red", "orange", "yellow", "gold", "golden", "green", "cyan", "blue", "purple", "pink", "black", "white", "silver", "gray", "grey", "brown",
)
_DIRECTION_ANCHORS = (
    "画外左侧", "画外右侧", "左侧", "右侧", "左边", "右边", "前景", "后景", "镜中", "镜外",
    "off-screen left", "off-screen right", "left side", "right side", "foreground", "background", "in the mirror", "outside the mirror",
)
_QUOTED_TEXT_RE = re.compile(r"[“\"]([^”\"\r\n]{1,200})[”\"]|[‘']([^’'\r\n]{1,200})[’']")
_TRANSFORMATION_CONTEXT_RE = re.compile(
    r"变成|变为|变化|转为|成为|染成|扩散|漫开|晕开|发亮|发光|"
    r"transform|change(?:s|d|ing)?\s+(?:into|to)|turn(?:s|ed|ing)?\s+|spread(?:s|ing)?|glow(?:s|ing)?",
    re.IGNORECASE,
)


def _ordered_matches(text: str, candidates: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    found = [candidate for candidate in candidates if candidate.lower() in lowered]
    return sorted(found, key=lambda candidate: lowered.find(candidate.lower()))


def extract_semantic_anchors(source_prompt: Any) -> dict[str, list[str]]:
    text = str(source_prompt or "").strip()
    if not text:
        return {"concrete_terms": [], "colors": [], "directions": [], "quoted_text": []}
    concrete_candidates = tuple(dict.fromkeys(term for group in _SEMANTIC_ANCHOR_GROUPS for term in group))
    quoted = [next(value for value in match if value) for match in _QUOTED_TEXT_RE.findall(text)]
    return {
        "concrete_terms": _ordered_matches(text, concrete_candidates),
        "colors": _ordered_matches(text, _COLOR_ANCHORS),
        "directions": _ordered_matches(text, _DIRECTION_ANCHORS),
        "quoted_text": list(dict.fromkeys(value.strip() for value in quoted if value.strip())),
    }


def semantic_anchor_instruction(source_prompt: Any) -> str:
    anchors = extract_semantic_anchors(source_prompt)
    listed = [
        *anchors["concrete_terms"],
        *anchors["colors"],
        *anchors["directions"],
    ]
    quoted = anchors["quoted_text"]
    details: list[str] = []
    if listed:
        details.append("Protected literal terms: " + "; ".join(dict.fromkeys(listed)) + ".")
    if quoted:
        details.append("Protected quoted text: " + "; ".join(quoted) + ".")
    return " ".join((
        "SEMANTIC ANCHOR LOCK: preserve every user-named body part, product component, color, direction, count, and quoted string literally.",
        "Never move a requested transformation or action to a neighboring anatomical part or product component. A related part may be mentioned only as context and must not become the changed attribute.",
        "Before finalizing, compare the draft with the user request for exact quoted text, changed attribute, left/right relation, color, count, and negation.",
        *details,
        "Do not print or explain this lock block in the answer.",
    ))


def semantic_anchor_warnings(source_prompt: Any, output_prompt: Any, family: str) -> list[dict[str, str]]:
    source = str(source_prompt or "").strip()
    output = str(output_prompt or "").strip()
    if not source or not output:
        return []
    anchors = extract_semantic_anchors(source)
    lowered_source = source.lower()
    lowered_output = output.lower()
    risks: list[dict[str, str]] = []

    missing_quoted = [value for value in anchors["quoted_text"] if value not in output]
    if missing_quoted:
        risks.append({
            "code": "semantic_exact_text_missing",
            "severity": "warning",
            "message": "输出未逐字保留输入中的引号文字：" + "、".join(missing_quoted),
            "family": family,
            "scope": "semantic_anchor",
            "evidence_level": "deterministic literal comparison",
        })

    missing_terms = [
        term for term in (*anchors["concrete_terms"], *anchors["colors"], *anchors["directions"])
        if term.lower() not in lowered_output
    ]
    if missing_terms:
        risks.append({
            "code": "semantic_anchor_missing",
            "severity": "warning",
            "message": "输出未保留输入中的字面语义锚点：" + "、".join(dict.fromkeys(missing_terms)),
            "family": family,
            "scope": "semantic_anchor",
            "evidence_level": "deterministic literal comparison",
        })

    substitutions: list[str] = []
    for group in _NEIGHBOR_SUBSTITUTION_GROUPS:
        source_terms = [term for term in group if term.lower() in lowered_source]
        if not source_terms:
            continue
        introduced: list[str] = []
        output_clauses = re.split(r"[。！？；;，,\n]+", output)
        for term in group:
            if term.lower() in lowered_source or term.lower() not in lowered_output:
                continue
            if any(
                term.lower() in clause.lower() and _TRANSFORMATION_CONTEXT_RE.search(clause)
                for clause in output_clauses
            ):
                introduced.append(term)
        if introduced:
            substitutions.append(f"{'/'.join(source_terms)} → {'/'.join(introduced)}")
    if substitutions:
        risks.append({
            "code": "semantic_neighbor_substitution_risk",
            "severity": "warning",
            "message": "输出引入了相邻身体部位或产品零件，请确认变化对象未被替换：" + "；".join(substitutions),
            "family": family,
            "scope": "semantic_anchor",
            "evidence_level": "deterministic protected-term comparison",
        })
    return risks


_ABSTRACT_EMOTION_RE = re.compile(
    r"(?:悲伤|伤心|愤怒|生气|恐惧|害怕|紧张|焦虑|震惊|惊讶|高兴|开心|绝望|释然|坚定|"
    r"sad|angry|afraid|fearful|nervous|anxious|shocked|surprised|happy|despair|relieved|determined)",
    re.IGNORECASE,
)
_OBSERVABLE_CUE_PATTERNS = (
    r"视线|目光|眼神|眼睑|眨眼|闭眼|睁眼|瞳孔|呼吸|吸气|吐气|肩|颈|手指|手掌|拳|姿态|低头|抬头|转头|后退|前倾",
    r"gaze|look(?:s|ing)?\s+(?:at|toward|away)|eyelid|blink|eyes?\s+(?:close|open)|pupil|breath|inhale|exhale|shoulder|neck|finger|hand|fist|posture|tilt|turns?\s+(?:the\s+)?head|leans?|steps?\s+back",
)
_CUE_CHANNEL_PATTERNS = (
    r"视线|目光|眼神|看向|凝视|gaze|look(?:s|ing)?|stare(?:s|d|ing)?",
    r"眼睑|眼皮|眨眼|闭眼|睁眼|睫毛|瞳孔|eyelid|blink|eyes?\s+(?:close|open)|eyelash|pupil",
    r"呼吸|吸气|吐气|屏息|鼻息|breath|inhale|exhale",
    r"肩|颈|脖颈|姿态|低头|抬头|转头|下巴|前倾|后退|shoulder|neck|posture|tilt|turns?\s+(?:the\s+)?head|chin|leans?|steps?\s+back",
    r"手指|指尖|手掌|拳|握紧|攥|finger|fingertip|hand|fist|clench|grip",
    r"嘴角|嘴唇|抿唇|闭唇|下颌|牙关|mouth|lips?|jaw",
    r"眉|面部|表情|微笑|笑意|eyebrow|facial|expression|smile",
)
_PERFORMANCE_BEAT_SPLIT_RE = re.compile(
    r"[。！？；;\n]+|(?=随后|然后|最后|起初|接着|紧接着|之后|话音|随后她|随后他|then\b|after\b|finally\b)",
    re.IGNORECASE,
)
_CHARACTER_TERMS = (
    "女人", "男人", "女性", "男性", "少女", "少年", "女孩", "男孩", "woman", "man", "female", "male", "girl", "boy",
)
_GAZE_RE = re.compile(r"视线|目光|眼神|看向|凝视|gaze|looks?|stares?", re.IGNORECASE)
_GAZE_TARGET_RE = re.compile(
    r"看向\S+|望向\S+|注视\S+|镜头|画外|对方|门口|窗|物体|目标|"
    r"(?:look|gaze|stare)(?:s|d|ing)?\s+(?:at|toward|to|past|off[- ]camera)|camera|off[- ]screen|target",
    re.IGNORECASE,
)
_SPEECH_RE = re.compile(r"对白|台词|说[:：]|说道|喊道|低语|旁白|dialogue|says?|speaks?|whispers?|<d>", re.IGNORECASE)
_MOUTH_CONFLICT_RE = re.compile(
    r"吞咽|咽下|说完后闭嘴|闭合嘴唇|停止说话|swallow|after finishing speaking|closes? (?:the |her |his )?(?:mouth|lips)",
    re.IGNORECASE,
)
_LIQUID_RE = re.compile(r"水|液体|雨|浪|飞溅|泼洒|water|liquid|rain|wave|splash|spill", re.IGNORECASE)
_CONTACT_RE = re.compile(r"碰撞|撞击|接触|破碎|爆裂|collision|impact|contact|shatter|breaks?", re.IGNORECASE)


def _advisory(code: str, message: str, *, family: str, scope: str, evidence_level: str) -> dict[str, str]:
    return {
        "code": code,
        "severity": "advisory",
        "message": message,
        "family": family,
        "scope": scope,
        "evidence_level": evidence_level,
    }


def performance_risk_warnings(prompt: Any, family: str) -> list[dict[str, str]]:
    text = str(prompt or "").strip()
    if not text:
        return []
    risks: list[dict[str, str]] = []
    visible_cues = sum(len(re.findall(pattern, text, re.IGNORECASE)) for pattern in _OBSERVABLE_CUE_PATTERNS)
    if _ABSTRACT_EMOTION_RE.search(text) and visible_cues == 0:
        risks.append(_advisory(
            "performance_abstract_only",
            "检测到抽象情绪，但未检测到视线、眼睑、呼吸、肩颈、手部或姿态等可见表演线索。",
            family=family,
            scope="character_performance",
            evidence_level="portable directing heuristic; not a model-quality judgment",
        ))
    shot_chunks = re.split(r"(?=\[\s*Shot\s*\d+\]|镜头\s*\d+\s*[:：])", text, flags=re.IGNORECASE)
    dense_beat = False
    for chunk in shot_chunks:
        character_count = sum(1 for term in _CHARACTER_TERMS if re.search(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", chunk, re.IGNORECASE))
        channel_limit = 5 if character_count >= 2 else 4
        for beat in _PERFORMANCE_BEAT_SPLIT_RE.split(chunk):
            channel_count = sum(bool(re.search(pattern, beat, re.IGNORECASE)) for pattern in _CUE_CHANNEL_PATTERNS)
            if channel_count >= channel_limit:
                dense_beat = True
                break
        if dense_beat:
            break
    if dense_beat:
        risks.append(_advisory(
            "performance_beat_density",
            "某个表演节拍包含较多不同线索通道；请人工确认是否超出每个角色最多三个高信号线索的预算。",
            family=family,
            scope="single_shot_density",
            evidence_level="narrow community observation pending paired validation",
        ))
    if _GAZE_RE.search(text) and not _GAZE_TARGET_RE.search(text):
        risks.append(_advisory(
            "performance_gaze_target_unclear",
            "检测到视线表演，但未检测到明确目标或镜头内外关系。",
            family=family,
            scope="camera_eyeline",
            evidence_level="portable directing heuristic",
        ))
    if _SPEECH_RE.search(text) and _MOUTH_CONFLICT_RE.search(text):
        risks.append(_advisory(
            "performance_speech_span_conflict",
            "对白与吞咽/闭嘴等口部动作可能占用同一发声跨度，请人工核对先后关系。",
            family=family,
            scope="dialogue_timing",
            evidence_level="portable directing heuristic",
        ))
    if _LIQUID_RE.search(text) and _CONTACT_RE.search(text):
        risks.append(_advisory(
            "performance_contact_causality_risk",
            "检测到液体与复杂接触/破碎因果链；这不是禁用项，建议人工确认接近、接触、反应和结果是否可见。",
            family=family,
            scope="complex_contact",
            evidence_level="unverified experiment candidate",
        ))
    if family == "Seedance 2.0" and (
        re.search(r"integrated_multimodal_description\s*:|overall_soundscape\s*:|non_diegetic_music\s*:|<d>|\(S\d+\)", text, re.IGNORECASE)
        or re.search(r"\b\d{1,6}\s*ms\b", text, re.IGNORECASE)
    ):
        risks.append({
            "code": "seedance_h3_syntax_leak",
            "severity": "warning",
            "message": "Seedance 提示词中检测到 H3 专属字段、对白标签、说话人编号或毫秒时间码。",
            "family": family,
            "scope": "output_contract",
            "evidence_level": "deterministic syntax contract",
        })
    return risks


PERFORMANCE_IR_DEFAULTS: dict[str, Any] = {
    "dramatic_trigger": "",
    "reception_beat": "",
    "primary_performance_beat": "",
    "observable_cues": [],
    "gaze_target": "",
    "speech_span": "",
    "state_transition_strategy": "",
    "performance_risks": [],
}


def normalize_storyboard_performance_fields(shots: Any) -> list[dict[str, Any]]:
    if not isinstance(shots, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in shots:
        if not isinstance(item, Mapping):
            continue
        shot = dict(item)
        for field, default in PERFORMANCE_IR_DEFAULTS.items():
            if field not in shot or shot[field] is None:
                shot[field] = list(default) if isinstance(default, list) else default
        if not isinstance(shot["observable_cues"], list):
            value = str(shot["observable_cues"] or "").strip()
            shot["observable_cues"] = [value] if value else []
        if not isinstance(shot["performance_risks"], list):
            value = str(shot["performance_risks"] or "").strip()
            shot["performance_risks"] = [value] if value else []
        normalized.append(shot)
    return normalized


class T8PerformanceDirectorConfig(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8PerformanceDirectorConfig",
            display_name="T8 Performance Director Config（表演导演）",
            category="T8/Utilities",
            description=(
                "可选的条件式人物表演结构，服务 H3、Seedance 2.0 和 T8 Storyboard Pack；不增加 LLM 请求。"
                "Optional community-research-inspired acting structure for H3, Seedance 2.0, and T8 Storyboard Pack. "
                "It is not an official MiniMax Skill; effects depend on model, media, and task."
            ),
            inputs=[
                io.Combo.Input(
                    "mode",
                    display_name="表演导演模式",
                    options=PERFORMANCE_MODES,
                    default=PERFORMANCE_AUTO,
                    tooltip="AUTO 条件启用；强化明确套用原有结构；关闭恢复原编译；极致会深度重构表演因果与节拍。",
                ),
            ],
            outputs=[T8PerformanceDirectorConfigIO.Output(display_name="performance_director_config")],
        )

    @classmethod
    def execute(cls, mode=PERFORMANCE_AUTO) -> io.NodeOutput:
        return io.NodeOutput(build_performance_director_config(mode))


__all__ = [
    "PERFORMANCE_AUTO",
    "PERFORMANCE_CONFIG_SCHEMA",
    "PERFORMANCE_EXTREME",
    "PERFORMANCE_IR_DEFAULTS",
    "PERFORMANCE_MODES",
    "PERFORMANCE_OFF",
    "PERFORMANCE_STRONG",
    "PerformanceDirectorConfigError",
    "T8PerformanceDirectorConfig",
    "T8PerformanceDirectorConfigIO",
    "build_performance_director_config",
    "h3_performance_instruction",
    "normalize_storyboard_performance_fields",
    "performance_risk_warnings",
    "resolve_performance_mode",
    "seedance_performance_instruction",
    "storyboard_performance_instruction",
]
