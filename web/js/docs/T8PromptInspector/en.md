# T8 Prompt Inspector

A deterministic, local, non-blocking structure checker for MiniMax H3, Seedance 2.0, and MiniMax Music 3 prompts.

- `original_prompt` returns the input byte-for-byte without rewriting it.
- `warnings_json` reports structural concerns such as missing core fields, shot numbering, duration budgets, media roles, task references, stability, transitions, speaker/text constraints, Music 3 headings, or language conflicts.
- The summary score covers mechanically detectable structure only. It is not a creative-quality score and never calls an LLM.
- Warnings are advisory and never block downstream execution.
