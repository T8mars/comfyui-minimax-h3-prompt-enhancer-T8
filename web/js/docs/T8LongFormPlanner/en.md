# T8 Long-form Planner

Builds a gap-free segment schedule and returns separate H3 and Seedance 2.0 plans plus continuity handoffs. It does not render, stitch, or edit video.

An optional Film Project Router connection adds `world_rule_checks`, `knowledge_state`, and `downstream_status` to every segment. Missing facts remain unknown and stale upstream/downstream work is never silently repaired.

Router continuity anchors become verbatim `required_literal_anchors`. If a provider returns JSON but renames required keys such as `segments`, the report sets `structured_response=false` and lists the received top-level keys instead of falsely reporting schema success.

After execution, a status card shows the structural-contract result. Green means the segment contract passed; red means fields, segment count/timing, or required anchors failed validation. The card follows the ComfyUI locale and grows with wrapped diagnostics so text is not clipped.

`Contract failure handling` defaults to compatibility warning, preserving existing workflow behavior. Select the recommended strict option to stop downstream execution with ComfyUI's native blocker while retaining the status card and JSON diagnostics. Neither mode makes another LLM request.
