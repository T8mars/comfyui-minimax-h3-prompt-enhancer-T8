"""Free, literal-safe H3 vocal formatting, independent of the quality toggle.

This is not a semantic speaker guesser. Missing IDs require an explicit source
binding, a direct named speaker, or one unnumbered vocal event with no competing
source. Ambiguous voices retain their complete draft and a diagnostic.
"""
from __future__ import annotations

import re
from collections import defaultdict

try:
    from .h3_quality import (LITERAL_RE, SHOT_RE, SPEAKER_RE, sections,
                             mask_literals, canonical_vocal_language, protected_text)
except ImportError:
    from h3_quality import (LITERAL_RE, SHOT_RE, SPEAKER_RE, sections,
                            mask_literals, canonical_vocal_language, protected_text)


FULLWIDTH_ID = re.compile(r"（\s*(S[1-9]\d*(?:\s*[,，]\s*S[1-9]\d*)*)\s*）", re.I)
ENTITY = re.compile(r"<Subject\s+[1-9]\d*>|(?<![A-Za-z-])[A-Z][A-Za-z-]{1,30}(?![A-Za-z-])")
VERB = re.compile(r"\b(?:says?|replies|whispers?|shouts?|sings?|exclaims?)\b|说(?:道|原句|台词)?(?!完)|低语|喊道|回应|唱(?:道|出)", re.I)
VOCAL = re.compile(r"<d>\s*\[(?P<language>[^\]]+)\][ \t]?(?P<words>.*?)</d>", re.I | re.S)
AUDIO_CUE = re.compile(r"<Audio\s+[1-9]\d*>\s*(?:reaches(?:\s+the\s+phrase)?|到达|唱到)\s*$", re.I)
BOUNDARY = re.compile(r"[。！？;；\n]|(?<!\d)[.!?](?!\d)")
NON_NAMES = {"she", "he", "they", "we", "you", "it", "the", "this", "that", "when", "then", "as",
             "after", "before", "at", "with", "and", "or", "but", "her", "his", "their", "both",
             "meanwhile", "woman", "man", "child", "people", "narrator"}
GROUP_VOICE = re.compile(r"两(?:人|名|个)|双人|二人|众人|齐声|[他她]们|一起(?:说|唱)|一同(?:说|唱)|\b(?:both|two|together|chorus|choir|group|they)\b", re.I)


def _id(match):
    return re.sub(r"\s+", "", match.group(1).upper()).replace("，", ",")


def _entity(value):
    return re.sub(r"\s+", " ", value).casefold()


def _direct_speaker(context):
    """Only a named clause subject, not the nearest mentioned listener.

    Alice looks at Bob then speaks / a pronoun after a cut is intentionally not
    resolved here. Exact input-line ownership can still supply that binding.
    """
    boundaries = list(BOUNDARY.finditer(context))
    start = boundaries[-1].end() if boundaries else 0
    timecode = re.match(r"\s*At\s+\d{2}:\d{2}\.\d{3},?\s*", context[start:], re.I)
    if timecode:
        start += timecode.end()
    clause = context[start:]
    names = list(ENTITY.finditer(clause))
    if len(names) != 1:
        return None
    name = names[0]
    if name.group().casefold() in NON_NAMES:
        return None
    if clause[:name.start()].strip(" \t\r,，:："):
        return None
    if not VERB.search(clause[name.end():]):
        return None
    return _entity(name.group()), start + name.end()


def _events(text):
    masked = mask_literals(text)
    previous = 0
    events = []
    for literal in LITERAL_RE.finditer(text):
        vocal = VOCAL.fullmatch(literal.group())
        if not vocal:
            continue
        shots = list(SHOT_RE.finditer(masked, previous, literal.start()))
        start = shots[-1].end() if shots else previous
        context = masked[start:literal.start()]
        ids = sorted([*SPEAKER_RE.finditer(context), *FULLWIDTH_ID.finditer(context)], key=lambda m: m.start())
        direct = _direct_speaker(context)
        # An earlier listener's annotation is not an ID for a later, explicitly
        # named speaker. Do not let the checker's broad context mask this gap.
        if direct and ids and ids[-1].end() <= direct[1]:
            ids = []
        events.append(dict(literal=literal, vocal=vocal, start=start, context=context,
                           speaker=_id(ids[-1]) if ids else "", annotation=ids[-1] if ids else None,
                           entity=direct[0] if direct else "", insert=start + direct[1] if direct else literal.start(),
                           cue=bool(AUDIO_CUE.search(context))))
        previous = literal.end()
    return events


def _source_bindings(source):
    """Bind exact supplied utterances; repeated same words with two owners conflict."""
    bindings = defaultdict(set)
    for event in _events(source):
        if not event["cue"]:
            bindings[event["vocal"].group("words")].add((event["entity"], event["speaker"]))
    masked = mask_literals(source)
    previous = 0
    for literal in LITERAL_RE.finditer(source):
        if literal.group().lower().startswith("<d"):
            previous = literal.end()
            continue
        context = masked[previous:literal.start()]
        direct = _direct_speaker(context.rsplit("，", 1)[-1])
        if direct:
            words = literal.group()[1:-1]
            if literal.group().startswith('"'):
                words = words.replace('\\"', '"').replace('\\\\', '\\')
            ids = sorted([*SPEAKER_RE.finditer(context), *FULLWIDTH_ID.finditer(context)], key=lambda m: m.start())
            bindings[words].add((direct[0], _id(ids[-1]) if ids else ""))
        previous = literal.end()
    return bindings


def normalize_h3_vocals(text: str, *, source: str = "") -> tuple[str, list[str], list[str]]:
    """Only native BODY annotations/tag names; never words, shots or metadata.

    Return finite change categories and unresolved codes. Complete malformed
    envelopes and ambiguous ownership are not salvaged by making up identities.
    Valid outputs are byte-identical and repeated normalization is idempotent.
    """
    parts = sections(text)
    bodies = [p for p in parts if p.name in {"detailed_description", "integrated_multimodal_description"}]
    if len(bodies) != 1:
        return text, [], []
    part = bodies[0]
    body = part.value
    events = _events(body)
    sources = _source_bindings(str(source or ""))
    source_vocals = [p for p in protected_text(source) if p.kind == "vocal"]
    names_to_ids = defaultdict(set)
    ids_to_names = defaultdict(set)
    reserved = set()
    for value in (text, source):
        for match in [*SPEAKER_RE.finditer(mask_literals(value)), *FULLWIDTH_ID.finditer(mask_literals(value))]:
            reserved.update(_id(match).split(","))
    # Establish ALL explicit bindings before assigning any missing ID: a later
    # occurrence may already number the speaker, and must not be renumbered.
    for event in events:
        entity = event["entity"]
        supplied = sources.get(event["vocal"].group("words"), set())
        if not entity and len(supplied) == 1:
            entity = next(iter(supplied))[0]
        event["resolved_entity"] = entity
        if entity and event["speaker"]:
            names_to_ids[entity].add(event["speaker"])
            ids_to_names[event["speaker"]].add(entity)
    for bindings in sources.values():
        for name, speaker in bindings:
            if name and speaker:
                names_to_ids[name].add(speaker)
                ids_to_names[speaker].add(name)
    edits, changes = [], set()
    unresolved = set()
    real = [e for e in events if not e["cue"]]
    for event in events:
        literal, vocal = event["literal"], event["vocal"]
        language = vocal.group("language")
        canonical = canonical_vocal_language(language)
        if canonical != language:
            edits.append((literal.start() + vocal.start("language"), literal.start() + vocal.end("language"), canonical))
            changes.add("vocal_language_alias")
        if event["cue"]:
            continue
        annotation = event["annotation"]
        if annotation:
            if annotation.re is FULLWIDTH_ID:
                edits.append((event["start"] + annotation.start(), event["start"] + annotation.end(), "(" + event["speaker"] + ")"))
                changes.add("vocal_id_punctuation")
            continue
        bindings = sources.get(vocal.group("words"), set())
        entity = event["resolved_entity"]
        if len(bindings) > 1 or (len(bindings) == 1 and entity and next(iter(bindings))[0] not in {"", entity}):
            unresolved.add("h3_missing_speaker")
            continue
        supplied_id = next(iter(bindings))[1] if len(bindings) == 1 else ""
        known = names_to_ids.get(entity, set()) if entity else set()
        if len(known) > 1:
            unresolved.add("h3_missing_speaker")
            continue
        speaker = supplied_id or (next(iter(known)) if known else "")
        if speaker and entity and ids_to_names.get(speaker, set()) - {entity}:
            unresolved.add("h3_missing_speaker")
            continue
        if not speaker:
            # Unknown distinct voices must not collapse to S1. One unnamed
            # event is safe only without existing IDs or competing input lines.
            mentioned = {_entity(m.group()) for m in ENTITY.finditer(event["context"])
                         if m.group().casefold() not in NON_NAMES}
            if not entity and (len(real) != 1 or reserved or len(source_vocals) > 1
                               or len(mentioned) > 1 or GROUP_VOICE.search(event["context"])):
                unresolved.add("h3_missing_speaker")
                continue
            index = 1
            while "S" + str(index) in reserved:
                index += 1
            speaker = "S" + str(index)
        reserved.update(speaker.split(","))
        if entity:
            names_to_ids[entity].add(speaker)
            ids_to_names[speaker].add(entity)
        position = event["insert"]
        annotation_text = " (" + speaker + ")" if position != literal.start() else "(" + speaker + ") "
        edits.append((position, position, annotation_text))
        changes.add("vocal_id_binding")
    for start, end, replacement in sorted(edits, reverse=True):
        body = body[:start] + replacement + body[end:]
    return text[:part.value_start] + body + text[part.end:], sorted(changes), sorted(unresolved)
