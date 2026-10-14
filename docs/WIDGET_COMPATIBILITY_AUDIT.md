# ComfyUI widget persistence and linked-input audit

Audit date: 2026-09-22. Scope: this repository's prompt-enhancement and
music-planning nodes. Evidence is the node schema, frontend configure/serialize
hooks, ComfyUI's `execution.py` linked-input validation path, Python unit tests,
and a real-browser regression harness. The RunningHub report supplied the
reproduction shape; we have **not** deployed this branch to RunningHub.

| Node | Linked text at graph validation | Saved widget order / result |
| --- | --- | --- |
| `QwenImage21PromptEnhancerT8` | Confirmed bug: linked `prompt` arrived as `None` and was rejected as blank. Now only a literal blank fails early; the resolved value is checked again before any provider call. | Confirmed bug: older 20-value examples had a `force_input` API-key placeholder and no seed control; extra UI values could shift the rest. Current examples save 22 named fields. Load migration covers the old layout, optional key/control widgets, omitted/`null` linked prompt, and trailing UI values. |
| `MiniMaxH3PromptEnhancerT8` / `Seedance20PromptEnhancerT8` | Their validators return `True` without requiring an unresolved upstream prompt. | Both already explicitly serialize named widget fields and have historical-layout migrations. No matching failure was reproduced in the audited local contracts. |
| `MiniMaxMusic3PromptEnhancerT8` | Its validator only tolerates installation-dependent local model values; it does not reject unresolved text. | Already saves a named 38-field array and restores published/runtime historical layouts by name. No matching failure was reproduced in the audited local contracts. |
| `YuE2MusicPromptEnhancerT8` | Its validator checks ABC source only, not unresolved upstream music text. | Its editable fields are additionally persisted by name under `t8_yue2_widgets_v1`; reload reapplies that state. No matching failure was reproduced in the audited local contracts. |
| `T8LyricWriter` / `T8ArrangementPlanner` | Confirmed same early-validation bug for a linked `music_idea`; fixed. A literal blank still fails early, and resolved blank text is rejected before starting a paid request. | No custom UI buttons or parallel named-widget serializer; native runtime widget order is used. No positional shift was observed in this audit. |

## Required gate for each new or changed node

### 2026-10-14: optional speech reference

H3 and Seedance append exactly one optional lazy custom-type `speech_reference`
socket after `combat_camera_config`; old schema prefixes, outputs, defaults,
38-field widget arrays and shipped example bytes remain frozen against 1.31.1.
Unconnected/Off messages remain identical. Recovery skips the new dependency's
execution, not ComfyUI's whole-graph static validation.

Second cross-review: accept helper named metadata only when all sixteen fields
have a valid layout; empty/corrupt metadata must fall back to the validated
positional array. Both Node and Chrome execute this with reordered runtime
widgets. Active-only language/quality adapters ignore locked vocal data when
checking descriptive prose, without changing schema/defaults, old 38-field
arrays or None/Off paths. See [second review evidence](SPEECH_REFERENCE_SECOND_REVIEW_2026-10-14.md).

The new helper saves its sixteen native fields explicitly by name. Configure
restores synchronously onto actual runtime names, not declaration positions;
four actions are nonserializable and idempotent. Off and provided-text sources
skip irrelevant media/config execution. Linked text None is unresolved during
validation; resolved values are checked before transport. Node/Chrome contracts
exercise reordered widgets, action tails, show/hide value retention and repeated
resize; real isolated queues exercise linked text, normal H3/Seedance and cached
recovery with a deliberately invalid runtime ASR dependency. These are local
contracts, not a RunningHub deployment.

### 2026-10-13 follow-up: Strata cross-review

No node inputs/outputs/defaults, main widget arrays, config 16/27-field names
or example bytes change. Shared configuration is resolved through bounded,
cycle-safe Reroute traversal, accepting object/Map link containers. A coalesced
graph connection observer preserves the host callback/return and refreshes
distant consumers when a reroute changes; original values and inactive sizes
remain intact. Existing buttons remain nonserializable. Node and Chrome
contracts cover reroute switching and saved-key retention, old/new named
reload and host callback preservation. This is not a RunningHub deployment.

### 2026-10-13: Strata existing-service provider

Append the provider choice; retain old main-node sockets/defaults/signatures
and serialized names. Shared config adds eleven optional advanced fields after
its original sixteen native widgets. Named configure/serialize covers old
native/declaration layouts, new 27-value saves, missing markers, reordered host
widgets and action tails. Buttons are nonserializable. Linked STRING None still
validates; resolved blank text fails before inference. Shared Strata overrides
stale cloud settings without reading their credential, URL or model.

Actual isolated ComfyUI 0.39.0 object_info confirms native config order:
required eleven, then optional five original fields plus eleven Strata fields.
Regressions compare old messages/branches and unchanged example bytes, Node
and Chrome contracts, plus real local queue execution. Inactive Strata does not
recalculate old saved/manual main-node sizes. This is not RunningHub deployment.

### 2026-10-06: additive H3 Hybrid

Append only a task combo option, with T2VA default and all five original indices
unchanged. Inputs, output ports, execute signature, 38 serialized names, historical
layout recognizers and original example bytes remain frozen. No button, DOM panel,
force-input field or native schema revision is added. New Hybrid examples keep
blank keys and the existing optional socket order; three same-name thumbnails
and a separate exact generator/checker prevent changes to old workflows.

Actual frontend hooks exercise all three new examples and reordered runtime
widgets, aliases, linked null text, synchronous named restoration, deferred
normalization, positional/native named serialization and repeat reload. Chrome
executes configure/serialize and the finite recovery notice. These are host-boundary
contracts, not a RunningHub deployment or an inference queue on the user's server.
Graph validation still permits unresolved upstream inputs; resolved Hybrid media
is checked before beginning a paid checkpoint or constructing a model/request.

2026-10-06 gates: 788 Python tests (786 passed, two opt-in skips), 54 frontend tests,
Chrome contracts, example checks, secret/package scans passed. Candidate ZIP CRC
and isolated CPU loading verify 29 nodes, Hybrid module/examples, eight official
GIFs, zero T8 GIFs and no live-repository fallback. Pure transport tests are not
real GGUF or rendered-video acceptance; real API A/B is recorded separately.

### 2026-10-05: reference video duration validation

Remove only the per-video and aggregate duration bounds in H3 and Seedance;
retain finite positive duration metadata and existing trim/source/count checks.
Update reference-video tooltips without changing socket IDs, input order,
options, defaults, outputs, execution signatures or widget serializers.
Regression coverage exercises long/short references across provider paths and
real CPU video decoding, alongside saved/runtime widget contracts. Fake provider
responses are transport tests, not paid API or real GGUF inference acceptance;
no RunningHub deployment is claimed.
The frozen AST gate permits exactly the removed duration guards and replacement
video tooltips, while continuing to compare all other validator code and native
schemas. All 769 Python tests completed (two opt-in skips), 51 frontend tests
and Chrome contracts passed; shipped example workflow bytes are unchanged.

### 2026-10-04: optional Tudou emotion strategy

Vocal-format follow-up: automatic H3 normalization occurs inside the existing
public quality/output boundary, with no schema, widgets, inputs/outputs or saved
values added. Finite existing diagnostics report local fixes/ambiguous drafts.
Only malformed native speaker/tag annotations change; valid outputs remain
byte-identical. Local/cloud transport tests check one generation and restoration
of the normalized cache. Relay execution text and Seedance remain unchanged.

Append a fifth value to `T8PerformanceDirectorConfig.mode`; retain the original
four values/indexes and AUTO default. This is the same single native combo,
custom output type and schema, with no additional input, DOM widget, action or
positional value. H3/Seedance main serializers, signatures and all bundled
workflow bytes remain frozen against release 1.28.2. Language-repair arguments
are internal helpers, not workflow fields. Recovery displays the stored finite
strategy/revision before queuing; it neither serializes a new field nor applies
the current mode to an old answer. CPU schema/message tests cover old modes and
native runtime contracts; the real-extension Node/Chrome harnesses cover saved
and reordered runtime widgets. This is not a live RunningHub deployment.

### Qwen opt-in edit rules (1.28.0)

Append `rewrite_profile` after every prior input; it is optional, socketless,
advanced and defaults to Classic. Freeze the previous 22 saved names as the
prefix; new saves have 23 fields and `t8_qwen_image21_widgets_schema=2`. A
historical button tail cannot enable Edit-aware. Consistent native named
metadata supports a host that drops the schema marker. Restore by name
synchronously even when native widget order differs, linked prompt is omitted,
key widgets exist or seed-control widgets do not. Every status action is
nonserializable and idempotent; repeated refreshes recalculate, never accumulate
height. Existing four outputs/recovery cache strings are frozen.
After synchronous restoration, the next animation frame performs UI refreshes
only; it must not replay saved values over a user's immediate new selection.

Tests cover old 20/22 layouts, new marked 23 layouts, extra key before API mode
or before seed, corrupted named metadata, linked text, seed control and button
tails. The Chrome harness executes the real extension hooks; it is not a live
RunningHub publish/reload. Both bundled Qwen examples keep their frozen Classic
22 layouts; load the edit example and select Edit-aware in advanced settings to
opt in. New marked 23 saves are tested through the actual frontend hooks.

Combat Camera addition (2026-09-30): `T8CombatCameraConfig` uses only three native
combos (`mode`, `continuity`, `impact`), no custom buttons or DOM widgets. H3 and
Seedance append one optional custom-type socket **after** all prior schema inputs;
it does not belong in either 38-name widget serializer. Frozen 1.25.0 comparisons
cover unchanged prior inputs/execute arguments and None/Off messages. All shipped
H3/Seedance JSONs pass configure/serialize through the actual frontend hooks in
the Node harness; the DOM/recovery harness also runs in Chrome. These are local
contracts, not a RunningHub production deployment or real LLM evaluation.

### 2026-10-01 follow-up: Issues #20 and #21

- H3, Seedance and Music had a confirmed timing gap: native positional loading
  can place a GGUF string in the wrong combo before named restoration in an
  animation callback. Restore schema values synchronously before returning
  from `onConfigure`; keep UI/layout work deferred. YuE2 already restores its
  own named property synchronously; Qwen already has a synchronous restore.
- #21's attached Desktop workflow has an extra empty API-key slot **after Base
  URL and before seed**, plus a corrupted `widgets_values_named` map. The
  historical key-before-API-mode migration alone did not cover this shape.
  Recognize the additional layout using numeric seed and seed-control markers,
  project onto runtime widget names and replace the stale named map for loading.
- Every custom positional serializer (H3, Seedance, Music, Qwen) now writes
  matching native named metadata. Qwen retains its canonical 22 fields without
  force-input key or action values. Native order and stored order remain distinct.
- Regression evidence: actual extension hooks with reordered runtime widgets,
  assertions **before** flushing animation callbacks, sanitized reporter JSON
  shape, and Chrome browser contracts. This is not a production deployment on
  the reporter's Desktop or RunningHub installation; ask for a fresh export if
  an updated installation still fails. No inference or paid API test is needed
  to reproduce this workflow-loading failure.

1. Enumerate schema inputs and the **actual** runtime widget names. V3 groups
   required and optional inputs; a `force_input=True` socket may have no widget.
   A linked text widget may be retained, serialized as `null`, or omitted by a
   host. Do not infer the saved array from Python declaration order.
2. If frontend actions or DOM widgets are appended, mark them non-serializable
   **and** explicitly serialize stable schema fields by name. Keep native
   `widgets_values_named` consistent with the stable positional array. Never let a button
   label or tooltip occupy a backend field. Do not persist API keys in examples.
3. On load, identify historical layouts from validated discriminators such as
   API mode and seed-control position. Project values onto runtime widget names
   before native positional configuration, then restore by name synchronously
   before returning from `onConfigure`. Model scans may run before the next frame.
   Test layouts
   both with and without a key widget, linked prompt widget, seed control,
   recovery fields, and trailing host-specific UI values.
4. In `validate_inputs`, treat `None` for a linked STRING as unresolved during
   graph validation. Keep literal empty-widget validation, and always validate
   the resolved value in `execute()` **before** a local-model or paid API call.
5. Load every shipped workflow JSON in a browser-level configure/serialize
   regression, then run workflow, Python, frontend, and secret-scan gates.
   Add a regression for the exact user-reported old workflow shape.

Do not claim a host-specific fix is production-verified until its exported
workflow and deployment have been tested on that host.
