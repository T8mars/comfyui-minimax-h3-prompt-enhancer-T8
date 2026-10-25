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

### 2026-10-25: display-only visual style illustrations

No schema/compiler/config/resource identity changes. The existing one browse
button still has both serialization flags disabled, with full 4/3 runtime widget
counts and 3/2 saved values. Scene/light/method/progress/play controls exist only
inside the dialog, never in widgets/properties/prompts. All 200 color comparisons
and 400 curated creator diagrams are display-only, bound to source resource
SHA256. Missing/stale preview metadata fails independently of valid style data.
Animations are opt-in and disposed on selection/search/close/configure/removal,
or stop when hidden/disconnected/owner invalid. Relative progress is not seconds.
Native browser checks must exercise these controls and assert unchanged native
serialization, actual SVG output, playback/pause, stale isolation and mobile fit.
No actual model/video benefit is implied by a diagram or a synthetic queue.

### 2026-10-25: independent color and creator styles

Append two helpers after the old 36 nodes. Color saves exactly mode/palette/scope;
creator saves mode/creator. All five fields are socketless native combos; each
helper adds one double-nonserializing browse button (actual full widget counts
4/3). Named and exact positional restoration is synchronous, including reordered
runtime controls and unknown historical labels; malformed action tails cannot
enable a style. Main H3/Seedance keep 38 saved fields and six/one outputs, appending
only two optional lazy config sockets. No MOSS or other target receives them.

Frozen old request messages are byte-identical for None/Off. A narrow AST
projection verifies every other prior H3/Seedance statement and schema prefix,
not just selected widget names. Normal execution validates the finite config and
packaged resource hash before a new checkpoint/provider request. Restore skips
new lazy producers and keeps historical finite metadata; it does not remap old
IDs to new content or bypass the host's whole-graph static validation.

Owned CPU queues exercise four arms per target at 3600 seconds, helper caches,
external typed producers, simulated catalog fingerprint changes through the
actual V3 hook, poisoned lazy restoration and invalid-config preflight retaining
the old checkpoint. This is cache-invalidation evidence, not a promise of live
resource hot reload; upgrade/restart remains the deployment policy.

Owned native Chrome checks full 4/3 widgets, old 38-field save/reload, mode-cycle
height stability, typed disconnect/reconnect, all three independent examples and
six native-exported queues, local search/preview/apply, delayed reverse responses,
workflow switching, native subgraph ownership and deleted-node replacement. The
two helpers and browser use zero model calls; loopback responses prove engineering
contracts, not actual LLM compliance or rendered-video improvement.

### 2026-10-23: opt-in MOSS authoring and visible character limit

Retain the 27 MOSS names as an immutable prefix; append only `authoring_profile`
as field 28, default Classic. New saves have `t8_moss_widgets_schema=2` plus
consistent native/private named maps. A complete valid named 28-map may restore
without its marker. Old 27-maps reset Classic; positional button tails cannot
opt in without the marker. Connected numeric nulls project safe UI placeholders
only with saved link evidence. Resolved values still validate before inference.

`max_output_chars` stays at saved index 8 and keeps its default/range/step; only
its visibility changes. Native Primitive follows that existing 100-step, unlike
a computed INT producer; do not confuse its normalization with field shifting.
The current owned Chrome check covers all 28 actual widget names, external
prompt/width/height/limit, native API export, save/reload and reconnect at
1256x1672. Node contracts separately cover linked-null, corrupt maps, old files
and reordered runtime widgets. An actual upstream GetImageSize INT=80 (not
Primitive folding) and ResolutionSelector=1256x1672 queue through the real host
without normalization or field shifting.

Append Director/Page after the old 34 nodes. Director has 17 canonical valued
widgets, synchronous named restoration, unique in-memory recovery slots and
three double-nonserializing actions. Page has three native widgets and nine
outputs; JSON paste disables dynamic prompts. Only its selected positive output
goes to MOSS. Bundle/source/report are never silently substituted for a positive.
Director's seed explicitly disables native `control_after_generate`; checking
only widgets filtered by canonical names would miss that host-added 18th field.
Connected DOM text keeps a compact labeled row on coexisting-socket hosts;
legacy converted widgets retain their native serialization hooks.
The native browser checks old five plus new eight examples, 17/3 field reload,
actual API exports, reconnect, a Comic two-page queue, cache-only queue, and
same-origin read-only failed inspection. The eight new exports also queue on an
owned CPU host using only synthetic loopback provider responses.

Real queues cover V3 image batch expansion/order, Fisher independent/fusion,
Comic source/translation shared geometry, page-2-only fixed revisions, failed
translation blocking downstream while retaining English inspection data,
restore with invalid lazy provider/brief, and zero-edit context with zero calls.
Tests also cover Local per-stage budgets/lifecycle and whole-task Strata safety.
No paid inference, real translation-quality, image rendering, RunningHub
deployment or minimum-version old-frontend visual acceptance is implied.

### 2026-10-19: Show Text output restoration and copying

`T8ShowText` keeps its existing STRING input/output and read-only DOM preview.
Live `onExecuted` and the host's snapshot `onNodeOutputsUpdated` share one updater.
Bare node IDs address the root graph only; locator UUIDs address their registered
subgraph, with encoded locators and legacy container execution paths handled
explicitly. Never resolve a bare ID against the active subgraph, or strip a
scoped ID to its last segment. Missing outputs in a restored snapshot clear old
previews. No output is placed in properties, named widget metadata or saved
`widgets_values`; the DOM widget has both serialization flags disabled.

Copy uses runtime-only raw text, not the textarea's LF-normalized value. The
fallback writes the raw string through a native copy event, restores focus and
selection, and reports failure if neither path succeeds. Pending clicks are
coalesced; subsequent copies restart one timer with a fixed reset label. Changed
outputs/removal cannot receive stale success feedback; reattached nodes remain
usable. Preserve original node callbacks and return values, and install once.

Node tests exercise same local IDs in root/sibling/nested graphs, snapshot resets,
CRLF, denial/missing APIs, failure, pending copies, removal and serialization.
The owned CPU/Chrome harness uses real execution, native workflow/change-tracker
switches and history-style output restoration, actual subgraphs and copy events.
This does not persist results into exported workflow JSON or promise restoration
when the host itself no longer retains outputs.

### 2026-10-19: independent manual spatial canvas

Append `T8H3SpatialMarkerCanvas` after the existing 33 nodes. Freeze all old
node schemas, H3's 38 fields and the config's 2 fields; do not reuse another
plugin's node ID or edit its frontend hooks. Five saved fields are explicitly
named: image, mode, markers_json, line_width, expected_source_sha256. Upload and
editor buttons cannot become saved fields. Restore synchronously by validated
named data or the exact five-value positional layout, including reordered host
widgets and null placeholders for missing linked widgets.

Linked values are None during static validation, resolved values are checked
again before CPU rendering. Editing connected fields is read-only, with no
implicit disconnect or hidden offline write. Preview and execute share the
same source loader; apply rechecks source/draft identity after asynchronous
requests. The same-origin, bounded route reads only Comfy input files, follows
no escaping symlinks and invokes no provider. RGB digest binding does not
authenticate semantic identity, downstream foreign plan classes or video quality.

Real Chromium pointer events cover create/move/eight-handle resize, undo/redo,
apply, native five-field save/reopen and a computed external STRING queue in an
owned CPU Comfy host with no audio plugin. Explicit pointer-events:auto is
required because host global modal/widget styles can otherwise swallow drags.
Two independent manual examples retain default Off and must load/reload and
queue Off/On using the actual browser export. A dynamic-prompt text source is
not an identity JSON producer: use a raw STRING producer for linked JSON tests.

### 2026-10-19: H3-only visual marker config

Append `T8H3VisualMarkerConfig` after the old 32 nodes. Two native controls,
mode (Off) and picture_selector (0), plus optional lazy marker_plan. Only H3
appends an optional lazy visual_marker_config; freeze its existing schema
prefix, six outputs, 38 saved fields and old examples against 1.34.0.
No other model node gains a socket. Linked INT None is deferred at validation;
the resolved selector and source pixels are checked before provider calls.

The helper's bilingual example button uses both `serialize:false` flags and is
idempotent. It is not a third saved value and never loads/replaces the canvas.
Its local guide downloads a reference PNG and the two bundled JSON templates;
template resolution prefers this node's python_module over backup installations.
No provider settings or credentials are read by the guide.

Owned Comfy queues exercise a real read-only producer, computed INT links,
cache/source changes, ambiguous matches, preflight preservation and restore.
Off/restore skip only new lazy dependencies, not pre-existing non-lazy IMAGE
branches or static graph checks. Native Chrome exercises two controls, all 38
H3 saved values, reconnect, stable sizes and both new examples. Five graphs
exported by the actual browser are queued on the owned CPU host, then inspected
for On/Off evidence, Picture ordinals and image counts. Tutorial download/retry,
two-value helper serialization and current-graph preservation are tested too. Native task
labels must be used when comparing runtime values: legacy Ref2VA aliases
intentionally normalize on load. Loopback replies are not model/video proof.

### 2026-10-18: independent experimental storyboard config

Append `T8StoryboardDirectorConfig` after all 31 existing nodes. One native combo
defaults to Off; no buttons, hidden fields or custom serializer. H3 and Seedance
append only an optional lazy `storyboard_director_config` after `speech_reference`.
Their 38 saved widget fields, output ports, prior schema prefixes and shipped
workflow bytes remain frozen. MOSS receives no new socket or prompt rule.

Linked dependencies resolve before normal execution but are skipped for cached
restore. Resolved malformed config fails before a new checkpoint/provider request.
The cached finite method/revision is displayed without applying today's switch.
Tests must distinguish real host queue/wiring with loopback responses from real
LLM or video-benefit acceptance; neither the method nor the UI adds a duration cap.

### 2026-10-17: independent MOSS Image authoring

Append `MOSSImagePromptEnhancerT8` after the original thirty nodes; no existing
node schema, widget order or shipped example changes. The new node stores 27
stable fields with matching native named metadata and `t8_moss_widgets_v1`.
Configure projects onto actual runtime names synchronously, before model scans.
Regressions include linked null/omitted text, optional key/control widgets,
action tails, corrupted metadata and reordered runtime widgets. API keys and
actions are never serialized by this extension. Mode/provider visibility keeps
values intact; repeated cycles do not grow the node.

Compile-only and last-good recovery skip irrelevant lazy dependencies. Resolved
text/drafts are checked again before model/transport calls. Recovery restores
the two INT outputs through a MOSS-only codec, preserving old cache behavior.
Node tests and the actual Chrome extension hooks cover these contracts. This
is not a RunningHub deployment; live queue/model evidence is recorded separately.

Cross-review: distinguish a real legacy conversion (`origType` /
`origComputeSize`) from the new host's coexisting but unconnected widget sockets.
Never resurrect a native converted widget or discard its serialization hook.
On coexisting-socket hosts, connected controls need a native compact suppressed
row, not extension-hidden/converted controls: otherwise their `y` becomes stale
and sockets overlap. DOM multiline rows need a MOSS-only bilingual draw label.
Reproduce external prompt + two INT links through real host save/reload,
disconnect/reconnect and repeated mode cycles, including actual API graph values.
MOSS additionally observes all connected shared-config fields without changing
old consumer callbacks, node schemas or output formats.

Also queue real computed INT producers, not only frontend Primitive constants:
Primitive may be folded into literals, hiding the validation boundary. Connected
MOSS canvas controls arrive as `None` during validation; defer those values only,
retain known-literal checks, then validate the resolved canvas before inference.

8-pixel compatibility follow-up: width/height now accept 8-pixel multiples in
16..16384 in both Python and named/positional widget maps. Keep all 27 field
names, defaults, sockets and output types unchanged. Test the reporter's actual
ResolutionSelector (3:4, 2 MP, multiple 8), not just 1024 defaults, and native
save/reload/reconnect of 1256x1672 without rounding. Layout compilation and typed
cache recovery use the same real dimensions; downstream latent alignment is
reported separately, never silently substituted into the prompt's canvas.

The real MOSS queue reproduced a further V3-specific failure: dynamic lazy image
fields reached `check_lazy_status` as `(value, original_graph_key)`, not plain
`None`. Failing to unwrap that tuple silently skipped connected upstream images.
Resolve unresolved dynamic tuples by their original graph keys, while retaining
older nested-None/flat forms. Every future lazy Autogrow node must test this with
two distinct images through an actual host queue, not just direct `execute()`.

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
