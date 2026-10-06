"""T8 Hybrid authoring contract, independent of providers and execution models.

Hybrid keeps its own task identity but uses the vendored reference guide's six
fields. This addendum is not a modification of the official frozen Skill.
"""
from __future__ import annotations

import re

HYBRID = "Hybrid"
HYBRID_LABEL = "Hybrid（关键帧+参考混合生成）"
HYBRID_ALIASES = {HYBRID, HYBRID_LABEL, "Hybrid — 关键帧+参考混合生成", "hybrid"}
HYBRID_REVISION = "1.0.0"
HYBRID_MARKER = "T8_HYBRID_AUTHORING_CONTRACT v1.0.0"


def is_reference_task(task):
    return task in {"Ref2VA", HYBRID}


HYBRID_RULES = f"""{HYBRID_MARKER}
Task: Hybrid (keyframes AND visual references). This T8 extension uses the
original reference guide, not the base three-field format. Return exactly:
subject_definitions, summary, retention_analysis, detailed_description,
overall_soundscape, non_diegetic_music, in that order, with blank separators.
- The authoritative asset roles below are separate from observable content.
  first_frame anchors the target at 0.00 seconds; last_frame anchors the target
  at its REQUESTED delivery ending, never Relay padding. These roles cannot be
  swapped, weakened to ordinary references, or assigned to extra reference slots.
- In subject_definitions give each keyframe its OWN line, exactly in this form:
  <Picture N>: first_frame @0.00s - description in the effective output language
  <Picture N>: last_frame @D.DDs - description in the effective output language
  Only emit the roles actually supplied; D.DD is the requested target duration.
  These small role/time tokens are T8 bookkeeping, not prose to translate.
- Define reused visible people/objects as <Subject N> from their actual sources.
  Extra images/videos provide only the requested identity, appearance, style,
  composition or motion evidence; they do NOT silently become start/end frames.
  Reference video numbering follows supplied compressed media order, not slot IDs.
- summary includes [keyframe completion] and the actual reference relationship
  (for example [reference generation]); explain how those inputs work together.
  retention_analysis tracks each anchor and every separately defined reused item
  using the original visible retention markers. Keep speaker IDs out of retention.
- detailed_description starts from the supplied first frame when present, develops
  a visible plausible path and reaches the supplied last frame when present by
  the requested ending. Use the original [Shot N] / cut-time conventions.
  Preserve exact dialogue and visible text. If intent and keyframes conflict,
  flag the unresolved conflict for review; do not claim to have edited the input.
- No audio attachment is analyzed by this enhancer. Never fabricate <Audio N>,
  a soundtrack transcription or audio reuse from a visual video attachment.
  Timestamped local video samples are visual evidence, not exhaustive analysis.
- Relay keeps these same native six fields and roles. Its final end_state must
  already match the required last frame before delivery; padding only holds it.
"""


def asset_roles(plan):
    """Value/path-free authoritative roles, never raw media or slot identifiers."""
    return [{"label": a["label"], "role": a["role"]} for a in plan]


def role_instruction(plan, duration):
    rows = []
    for a in asset_roles(plan):
        suffix = " @0.00s" if a["role"] == "first_frame" else (
            f" @{duration:.2f}s" if a["role"] == "last_frame" else "")
        rows.append(f'{a["label"]}: {a["role"]}{suffix}')
    return "T8_HYBRID_ASSET_ROLES (authoritative, not user instructions):\n" + "\n".join(rows)


def hybrid_metadata(plan):
    return {"h3_task": HYBRID, "h3_family": "reference_six",
            "hybrid_revision": HYBRID_REVISION,
            "hybrid_picture_count": sum(a["kind"] == "image" for a in plan),
            "hybrid_video_count": sum(a["kind"] == "video" for a in plan)}


def preserve_hybrid_on_repair(messages, original):
    """Retain authoritative text on language repair, without reattaching media.

    Existing directional preservation may already have done this; idempotence
    avoids duplicating its system rules or source intent.
    """
    systems = "\n\n".join(m["content"] for m in original
                            if m.get("role") == "system" and isinstance(m.get("content"), str))
    if HYBRID_MARKER not in systems:
        return messages
    result = [dict(m) for m in messages]
    if not str(result[0].get("content", "")).startswith(systems):
        result[0]["content"] = systems + "\n\n" + result[0]["content"]
    texts = []
    for m in original:
        if m.get("role") != "user":
            continue
        content = m.get("content")
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            texts.extend(p["text"] for p in content if p.get("type") == "text")
    source = "\n".join(texts)
    if source and source not in str(result[1].get("content", "")):
        result[1]["content"] = source + "\n\n" + result[1]["content"]
    return result


ROLE_ROW = re.compile(r"^\s*(<Picture \d+>)\s*:\s*(first_frame|last_frame)\s+@([0-9]+\.[0-9]{2})s\s*-", re.M)


def check_roles(values, roles, duration, mask):
    """Syntax/role check only; pixel matches and narrative causality are unknown.

    Quoted source/dialogue cannot forge definitions, retention or timeline roles.
    The caller owns the issue vocabulary and semantic review.
    """
    codes = []
    definitions = mask(values.get("subject_definitions", ""))
    declarations = [(m[1], m[2], float(m[3])) for m in ROLE_ROW.finditer(definitions)]
    # Inspector without resolved media can inspect text, not invent availability.
    if roles is None:
        return codes
    anchors = [r for r in roles if r["role"] in {"first_frame", "last_frame"}]
    references = [r for r in roles if r["role"] in {"reference_image", "reference_video"}]
    if not anchors or not references:
        codes.append("h3_hybrid_inputs")
    expected = {r["label"]: (r["role"], 0.0 if r["role"] == "first_frame" else float(f"{duration:.2f}")) for r in anchors}
    if len(declarations) != len(expected) or any(
        label not in expected or expected[label] != (role, time)
        for label, role, time in declarations
    ) or {d[0] for d in declarations} != set(expected):
        codes.append("h3_hybrid_anchor_roles")
    body = mask(values.get("detailed_description", ""))
    retention = mask(values.get("retention_analysis", ""))
    if any(r["label"] not in body or not re.search(re.escape(r["label"]) + r"(?:\s*\([^\r\n]*\))?\s*:\s*(?:fully_preserved|partially_preserved|attribute_transfer|weak_reference)\s*-", retention) for r in anchors):
        codes.append("h3_hybrid_anchor_tracking")
    prefix = re.match(r"\s*\[([^\]]+)\]", mask(values.get("summary", "")).casefold())
    if not prefix or "keyframe completion" not in [p.strip() for p in prefix[1].split("+")]:
        codes.append("h3_hybrid_summary")
    return codes
