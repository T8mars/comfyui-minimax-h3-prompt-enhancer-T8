# T8 Storyboard Pack

Returns a global prompt, shot JSON, still-keyframe prompts, and transition/sound data. The model generates one shot contract; the two delivery tables are derived locally to avoid duplicated paid output. It respects connected brief and reference-role inputs.

Optional film-project state and character-performance connections add causal links, before/after dramatic values, scene necessity, setup/payoff tracking, and bounded observable performance cues. The local `narrative_audit` reports structural coverage and unmatched setup/payoff names only; it is not an objective creative-quality score.

Continuity anchors must be copied verbatim, and the same compact label must be reused for a setup and its payoff. The top level accepts only `global_prompt` and `shots`; aliases such as `storyboard` or `shot_list` are reported as `structured_response=false` with safe schema diagnostics.

After execution, a status card shows whether shot count, timing, required fields, cue budgets, and literal anchors passed. Green is valid; red means at least one contract failure. The card follows the ComfyUI locale and grows with its diagnostics.

`Contract failure handling` defaults to compatibility warning so existing workflows keep their behavior. Select the recommended strict option to stop downstream execution with ComfyUI's native blocker while retaining the status card and `shot_list_json.validation_errors`. Neither the card nor the local blocker creates another paid request.
