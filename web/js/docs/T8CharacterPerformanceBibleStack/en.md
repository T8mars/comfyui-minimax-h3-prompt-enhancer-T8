# T8 Character Performance Bible Stack

Combines 1–8 `T8 Character Performance Bible` outputs into one purple contract accepted by H3, Seedance 2.0, or Storyboard Pack. It runs locally and makes no LLM request.

- Every connected character needs a unique ID; duplicate IDs are rejected locally.
- Objectives, tactics, physical inertia, and gaze/listening rules are never merged across characters.
- Downstream compilation applies one primary tactic and at most three observable cue channels per character per beat.
- Multi-character Storyboard output requires `character_performance_beats` so each character remains independently auditable.

For one character, skip this node and connect the single bible directly.
