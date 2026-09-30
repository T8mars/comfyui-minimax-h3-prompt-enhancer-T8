# Qwen T8 edit rules: acceptance evidence and boundaries

Date: 2026-10-01. Candidate: 1.28.1 (feature introduced in 1.28.0). Frozen compatibility baseline:
`637036b0bd0ef4e966691983c20e82c2435761ea` (1.27.1).

The 1.28.0 publishing gate passed its full suite and Chrome checks. The separate
minimum/latest ComfyUI matrix failed while retrieving this frozen source because
its shallow-checkout fetch list omitted the revision (run `36768085170`,
`git show` exit 128). 1.28.1 adds the same revision to that workflow and checks
both fetch lists. It changes CI metadata only, not the feature's runtime rules.

## Reproducible local gates

- `python -m unittest discover -s tests -p 'test_qwen_image21*.py'`: pure
  contract parsing/checksum, source maps/batches, language/lettering, ratio
  precedence, transparency, three cloud routing adapters and local-provider
  parameter/unload contracts. Mocked provider responses are not real inference.
- `node --test tests/frontend/qwen_widget_reload.test.mjs`: actual extension
  configure/serialize hooks, historical layouts, marked opt-in profile, native
  widget reordering, linked prompt, key and seed-control placeholders, and the
  next-frame overwrite reproduction.
- `python tools/run_frontend_browser_tests.py`: the real extension executes in
  Chrome, with a lightweight ComfyUI host harness. Save/reload, status display,
  stale connections, idempotence and no cumulative height are asserted. This is
  not RunningHub or a complete production ComfyUI frontend installation.
- `python -m unittest discover -s tests` and `python tools/verify_repository.py`:
  full suite, unchanged shipped examples, secret scan, source/package resources,
  JSON and frontend syntax. Registry runtime code includes the new module and
  checksum-pinned rule file, not tests or development tools.

Both Qwen example JSONs remain byte-compatible Classic examples. Load the edit
example, expand advanced settings, then choose Edit-aware to opt in. The four
output indices and cached recovery strings are unchanged. Normal Classic prompt
messages and validators are frozen against the old revision. The deliberate bug
fix is one total repair even when a length repair returns an invalid ratio.

## Live gates still requiring external access

No new valid API credential or RunningHub test environment was supplied during
this implementation. There is **no new live A/B score**, no dedicated-PE
comparison, and no actual rendered-image score in this report. Historical
Classic cloud tests must not be reused as evidence for the new edit rules.

For the next live A/B, keep identical source files, model, provider, budget and
supported sampling parameters within each Classic/Edit-aware pair. Record every
initial request, correction and failure; do not silently discard failed groups.
Use the following twelve cases with original dimensions recorded before upload:

| Case | What must be checked manually |
| --- | --- |
| Local wall edit, Chinese | Requested background only; no invented face/accessory inventory. |
| Local wall edit, English | Same boundary; English prose. |
| Chinese sign changed to `OPEN` | Chinese prose and exact English lettering coexist. |
| English brief with Chinese lettering | No lettering translation or bilingual duplication. |
| Person into second-image scene | Correct subject source and second-image canvas. |
| Clothes donor plus person canvas | Donor does not replace identity or framing. |
| Style donor plus content canvas | Style transfer does not follow donor dimensions. |
| Ten sources with explicit unused references | All sources sent/mapped; unused sources reported, not invented. |
| Fixed UI ratio versus contrary brief | UI ratio wins, with no ratio in prose. |
| Contextual output dimensions and quoted `1:1` | Real output size wins; printed ratio text remains exact. |
| Outpainting versus new-scene composition | Intent-specific canvas decision; no automatic nearest preset. |
| Alpha plus a short character target | RGBA/alpha/transparent semantics and bounded repair; complete draft retained. |

Separate objective structure metrics (valid JSON, tags, ratio, literal retention,
request count) from subjective edit usefulness. Human scores should explain
fidelity, edit clarity, preservation boundary, source-role/canvas correctness
and concise usefulness. Text scores do not prove that a downstream image model
preserved the face, executed the edit, or produced a real alpha channel.

RunningHub acceptance must publish/reload an exported workflow in that host and
inspect the resolved backend inputs, not merely its drawn node. Cover Classic
old layouts and new marked 23-field layouts, two linked images, linked text,
local/no-key mode, seed/control, and a nonserializable recovery/status UI tail.
