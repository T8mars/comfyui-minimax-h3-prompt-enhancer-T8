# H3 visual marker authoring (experimental)

Click **📖 空间标记：示例与接线 / Examples** at the bottom of this node for a wiring diagram,
a downloadable reference PNG and Ref2VA / Hybrid workflow JSONs. Save your current graph,
import a JSON, upload its PNG, configure your enhancer and switch Off to On.
The tutorial does not automatically replace the canvas. The existing audio plugin supplies Prepare.

H3 only; Off by default. Existing Prepare.marker_plan → this helper → H3.visual_marker_config.
Connect the SAME Prepare.marked_image to H3's existing reference-image input.
Normal Ref2VA / Hybrid extra references only; active Relay is not implemented.

Zero selects a unique pixel match; positive values select the actual enhancer Picture ordinal,
not Bind.marker_position. Hybrid anchors count first. No insertion, reordering, duration cap or extra LLM.
Off does not skip independent image dependencies or remove drawn boxes. Restore skips new config dependencies,
not necessarily existing image branches. Cloud enhancement receives image and marker text.

For downstream reuse, enhanced_prompt → existing Prompt.base_prompt [manual_original] → recipe → Bind.
Do not append generated legend/actions again. Keep all media roles/order aligned and insert the marker once.
Source coordinates are soft annotation evidence, not hard trajectories, semantic identity or removal guarantees.
