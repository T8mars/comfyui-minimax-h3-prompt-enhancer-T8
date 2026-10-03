# 土豆-情绪演绎 / Tudou emotion direction

An opt-in fifth option on `T8PerformanceDirectorConfig`. The previous four
options, default, schema, ports and widget order remain unchanged. No additional
node, independent Skill slot, required form or model call is introduced.

## Why a separate strategy

Extreme focuses on restructuring weak performance causality and timing. Tudou
focuses on emotion quality versus intensity, preceding-state residue, supported
per-line delivery, and feasible voice/lip/body coordination. Explicitly large
acting stays large; peaceful, unchanged and silent scenes do not acquire a
compulsory arc. Good passages need not be rewritten merely to look different.

Choose the new mode for nuanced or mixed emotion, conflicting voice/body cues,
or a sequence whose expressions reset too abruptly. Combine it with an existing
character Bible or independent drama/combat Skill where useful. Selection does
not authorize new dialogue, events, props or a different ending.

## Contracts

- Shared independently written method, separate H3/Seedance/Storyboard adapters.
  H3 base modes retain three fields; Ref2VA retains six. Seedance keeps natural
  language. Storyboard keeps its existing compact IR and per-character beats.
- Preserve exact speech, role ownership, user sound whitelist, framing,
  duration/count, media references and first/last-frame locks. Visible breathing
  does not authorize audible breathing. Voice locks apply only to speakers.
- Relay events are not cuts. New actions and speech belong in delivery spans;
  end states are already achieved states, and final alignment padding cannot
  introduce another action or voice.
- Existing conditional drama authorship remains the only scope mechanism.
  Media/OCR/Bible content is data, not creative authorization.
- The strategy is included in initial requests and retained by existing bounded
  language/format/quality corrections. Failed quality correction keeps the last
  complete draft with its status; it is not claimed to have passed.
- Recovery returns the stored result without rerunning or applying the currently
  selected mode. Atomic strategy/revision metadata identifies new-mode runs.

## Source and evidence

User-provided `tudou-single-h3` and its actor-performance reference informed the
method. Source hashes and exclusions are in
[`tudou-emotion.lock.json`](../research_sources/tudou-emotion.lock.json).
No license was supplied; attribution does not assert permission to redistribute
the full text. Source prose, examples, tag glossary and LoRA triggers are not
bundled. Its universal six-field output, six-second default, one-take preference
and reference-image exclusion policy are not adopted.

CPU transport doubles verify transmission and cleanup boundaries, not local
9B compliance. `tools/emotion_acceptance.py` runs production cloud requests for
12 fixed cases, two modes and two repetitions (48 planned results). It uses
hidden key entry, stores evidence outside the repository, records actual model,
HTTP attempts, usage, logical corrections and failed slots, and forbids implicit
resubmission on resume. Swapping mode order between repetitions reduces order
bias but does not make a stochastic API deterministic.

Evaluate native contracts and factual/speech/sound violations before creativity.
Blind text labels hide arm names; an agent's review is not an independent human
panel. Means cannot offset hard failures. Text fluency and parser success are
not emotional realism or rendered video evidence.

Pre-registered text review rubric: native protocol, exact lines/speakers, factual
scope, sound permission, timing/count/framing and ending are hard checks. An
HTTP 200 is only a returned answer, not a pass. For outputs that pass those
checks, review supported emotion quality, ordered transition/residue, voice/lip
coordination and crop-feasible cues on a 0–4 descriptive scale (0=absent or
contradictory, 1=generic, 2=partly concrete, 3=clear, 4=clear and economical).
Do not reward length, adjective count, instruction repetition or similarity to
the source Skill. Correct unchanged acting is not a failure. Report ties and
unpaired failures; do not impute a missing answer or average away a violation.

Models can miss native formatting despite explicit instructions. A separate
automatic H3 output normalizer now fixes fullwidth IDs, safely bound missing IDs
and explicit language aliases, without a paid call or a quality-toggle change.
It preserves exact words and existing IDs. Ambiguous multiple voices are not
guessed: the complete draft and diagnostic remain available, with the existing
bounded Quality Repair option for further correction. This applies across H3
modes, not to Seedance's natural-language format. See
[format-fix evidence](H3_VOCAL_PROTOCOL_FIX.md).

The [2026-10-04 implementation/API report](EMOTION_API_ACCEPTANCE.md) retains
the 48-slot initial A/B, separate 8/4-result follow-ups, failures and exploratory
review. Do not combine different code fingerprints into a final-code win rate.

## Separately registered video acceptance

Use the same H3 version, checkpoint/LoRA state, references, dimensions, duration,
sampling settings and paired seeds. Test restrained tears, smiling threat,
carryover, heightened acting and a silent crop constraint, at least two paired
seeds per case. Hash original outputs; do not hide failures or replace weak
samples with cherry-picked repeats. Review exact speech, lip/audio timing,
reference identity, cue visibility, emotional transitions/residue and undesired
sounds. Record clipping artifacts and failures separately from preference.

Status is **pending, no generated video evidence** until those actual clips and
settings exist. An installed rendering environment and approved workflow are
needed; API prompt tests cannot mark this gate passed.
