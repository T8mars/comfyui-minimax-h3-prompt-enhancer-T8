"""Opt-in, independently worded emotion direction; never a platform grammar.

User-provided Tudou material informed the selection method, not output fields,
reference handling, vocal tags, LoRA triggers or model-capability claims.
"""
from __future__ import annotations

from typing import Any


EMOTION_MODE = "土豆-情绪演绎（声画协同）"
EMOTION_REVISION = "1.0.0"
EMOTION_MARKER = "T8 TUDOU EMOTION STRATEGY v" + EMOTION_REVISION
SOURCE_FILES = {
    "SKILL.md": "4c2e705558c7c9e4bebe59fc26f9829c75f64dba737377ef43b24dfb66fba39b",
    "references/actor-performance.md": "d8f9df1e40c854c03fcaa7161ba9f0d07e8b6abf77fab3af7745227d27951058",
}


def emotion_source_metadata() -> dict[str, Any]:
    """Finite provenance only; never expose the user's local source path."""
    return {
        "relationship": "independently worded adaptation; not an official MiniMax Skill",
        "author": "土豆 / Tudou",
        "material": "user-provided tudou-single-h3 and actor-performance reference",
        "revision": EMOTION_REVISION,
        "files_sha256": dict(SOURCE_FILES),
        "evidence_level": "text-contract adaptation; rendered benefit unverified",
    }


def emotion_performance_instruction(
    model_target: str,
    *,
    fixed_shot_count: int = 0,
    anchor_instruction: str = "",
    requested_dialogue: bool = False,
    planning_ir: bool = False,
) -> str:
    """One shared method, expressed inside each caller's existing contract.

    Authorship comes from the caller's established drama contract, never from
    selecting this mode. This helper neither invokes a provider nor adds IR.
    """
    dialogue = (
        "Only the existing T8 drama authoring contract and the actual user's explicit scope can authorize missing or named editable lines; selecting this mode grants no authorship."
        if requested_dialogue else
        "Never invent, extend or rewrite dialogue."
    )
    protected_words = (
        "Preserve all supplied locked words, punctuation, language and speakers exactly; an explicitly named editable line follows only the existing drama authoring contract."
        if requested_dialogue else
        "Preserve supplied words, punctuation, language and speaker exactly."
    )
    shot_rule = (
        f"Keep exactly {int(fixed_shot_count)} shots and their locked timing."
        if int(fixed_shot_count or 0) > 0 else
        "Keep the selected platform's existing AUTO shot policy; this method imposes neither one take nor extra cuts."
    )
    native = (
        "Keep the existing storyboard JSON and compact field budgets. Map the arc and carryover into the existing trigger, reception, primary beat, cues, speech span and transition fields; add no keys, tables or analysis. Leave non-performance fields empty. Keep this IR model-neutral for native downstream compilers."
        if planning_ir else
        "Use only native Seedance natural-language organization, reference and sound notation; import no other model's grammar, fields, speaker numbering or timing notation."
        if model_target == "Seedance 2.0" else
        "Keep the selected H3 task's native fields and keyframe alignment. Each actual vocal event must bind its existing speaker immediately before the native <d> block using ASCII parentheses, for example (S1) says: <d>[Chinese] exact words</d>; never use fullwidth （S1） or omit the ID, and keep the actual spoken-language tag in English. Do not number silent actors. In overall_soundscape describe only permitted non-vocal sounds; if speech is the only permitted sound, state that non-vocal sound is absent rather than marking the entire clip silent. N/A for that field requires explicit complete silence, not merely no ambience or no music. Import no extra vocal tags or sections."
    )
    return " ".join(part for part in (
        EMOTION_MARKER + " (non-official, opt-in acting method; not a higher intensity tier).",
        "Apply only to existing characters or explicitly requested anthropomorphic acting. Pure products, scenery and mechanical actions gain no face, breathing, feelings or speech. A still image establishes visible appearance and starting pose, not hidden motives, diagnoses, relationships or a voice.",
        "Preserve user facts, identity, media roles/order, exact words, framing, duration, shot count, first/last-frame locks and the selected directing method. Matching character Bibles remain authoritative and separate; never guess a missing character binding or spread one person's tactic, voice or emotion to everyone. A conditional mask-break happens only at its established trigger.",
        "Separate emotional quality and intensity from body amplitude, vocal volume, pace, texture and clarity. Choose only input-supported delivery: restrained tears need not sound like crying; a smiling threat may stay smiling; quiet speech may stay clear; numbness still has natural speaking mouth motion. Explicitly heightened acting may stay large. With little evidence, add the fewest cues, not a compulsory restrained arc.",
        "Order changes around the supplied event, intention or established realization; never invent an off-screen reply, knock, prop or backstory as a trigger. Several causally linked sub-beats may share one shot. Preserve the specified emotional order and meaningful residue from the preceding state instead of swapping unrelated expressions or resetting after every line. Calmness and no reaction are valid.",
        "For each needed line, coordinate its existing addressee, preparation, delivery and aftermath. " + protected_words + " Place each line once in its native speech location, never repeat it in a sound field. Delivery and reactions stay outside the protected words. " + dialogue,
        "Use at most three useful observable cue channels per character per beat unless dense choreography is explicitly requested; this is not a limit on attacks, exchanges or emotional stages. Match cues to the actual crop and permitted body movement. Do not insert a close-up or cut to reveal an invisible detail, or add accessories/wind to decorate it. Keep tactic order, ownership, waits and continuing physical tasks.",
        "Coordinate speaking, lip motion and any permitted breath or swallow sequentially; a sustained utterance cannot share an incompatible closed-mouth or inhalation action. Voice locks apply only when that character actually speaks. Fit speech and reactions into the user's time; shorten optional embellishment first, never silently shorten a locked line, change its delivery speed or extend duration to disguise conflicting requirements.",
        "Treat explicit sound sources as a closed whitelist. No music is not complete silence, and permitted speech is not permission for extra sobs, sighs, breathing audio or another speaker. Complete silence permits no vocalization or ambient sound; visible breathing does not authorize audible breathing. Preserve the actual sound contract rather than inventing a convenient audible trigger.",
        "The endpoint retains the requested aftermath or ongoing state, not an automatic smile, neutral reset or freeze. Relay events are not cuts: stage changes and speech only in delivery time; end_state records an already achieved state and final alignment padding adds no action or voice. Do not claim a LoRA is installed, add its trigger or change the upload list.",
        shot_rule,
        native,
        anchor_instruction,
        "Improve only weak emotion/voice/visible-action coordination; a complete well-directed passage may remain unchanged. Do not rewrite unrelated passages merely to look different. Return only the caller's complete native output, never this checklist, a reasoning transcript, a score or an interactive question.",
    ) if part)
