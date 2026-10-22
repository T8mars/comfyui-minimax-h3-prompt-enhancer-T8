# MOSS page selection and native compilation

Director output 0 `bundle_json` → this node's matching input, or paste a **complete
bundle** for offline CPU-only use. No provider, model or references are needed.
JSON is not dynamically expanded. Failed inspection artifacts are not bundles.

`page_index` starts at 1; choose an existing `en` or `zh` language. Newly generated
Comic pages have both; Fisher normally has one. Missing languages fail explicitly,
without translation or fallback. Use multiple Page nodes for several pages/languages.

| Output index | Meaning |
| --- | --- |
| 0 | `positive_prompt`: **the only output to wire to MOSS positive encoding** |
| 1 / 2 | `width` / `height`: INT canvas dimensions |
| 3 | `resolved_format`: caption or layout |
| 4 | `native_draft_json`: editable native draft, not positive |
| 5 | `report_json`: selection/structure diagnostics, not positive |
| 6 | `source_json`: selected source retaining comic labels, not positive |
| 7 / 8 | Current page's paired reading copy / stable `unit_id` for review or revision |

The whole collection is validated before compiling the selected source. Zero
model calls; no other unit changes. Length diagnostics retain historical source
settings. Eight-pixel-multiple canvas dimensions stay exact; downstream latent
nodes may align them independently, so check the real final canvas.

Successful compilation proves structure, not translation semantics, aesthetics,
typography or compliance with the unmeasured target 4096-token limit. Never use
bundles, source JSON, reports or reading copies as positive prompts, or feed
compiled centered coordinates back as an original draft.
