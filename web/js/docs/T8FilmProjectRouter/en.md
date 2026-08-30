# T8 Film Project Router

Maintains film stages, authoritative inputs, world rules, continuity anchors, and revision impact locally. It does not call an LLM, read a project directory, or regenerate downstream work.

- Authoritative inputs contain only material explicitly confirmed by the user; missing facts remain unknown.
- When an upstream stage changes, the node reports transitively affected downstream stages without deleting or rewriting them.
- Connect `film_project_state` to Long-form Planner or Storyboard Pack to pass world rules, costs and limits, knowledge gaps, and stale-stage status.
- Prefer connecting the prior purple `film_project_state` directly to Previous project state; pasting Project-state JSON remains supported. If both are supplied, they must be identical.
- On continuation, blank brief, authoritative-input, confirmed-stage, world-contract, and continuity-anchor widgets inherit their prior values instead of preserving only the revision number.
- To delete one inherited field, enter `[CLEAR_INHERITED]` in that field. Only that field is cleared; other blank fields continue to inherit. The Chinese marker `[清空继承]` is equivalent.
- After execution, a status card displays the revision, source, and invalidated downstream stages. Red means review is required; green means no invalidation was triggered. The card follows the ComfyUI locale and grows to fit longer invalidation or clear lists.

Project state must not contain an API key. API-key-like text is rejected locally.
