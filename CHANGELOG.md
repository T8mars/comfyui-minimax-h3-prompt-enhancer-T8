# Changelog

All notable changes to this project are documented here. Versions follow
Semantic Versioning and match the versions published to the Comfy Registry.

## [Unreleased]

## [1.13.0] - 2026-09-02

### Added

- Add an opt-in `极致（深度表演重构）` Performance Director mode for H3,
  Seedance 2.0, and Storyboard planning. Existing `AUTO / 强化 / 关闭`
  values and behavior remain unchanged for saved workflows.
- Treat already enhanced prompts as editable drafts in Extreme mode and require
  material improvements to acting causality, timing, or observable performance
  instead of adjective-only or synonym-only edits, while preserving exact
  dialogue, facts, media roles, duration, shot count, and native output format.

### Verified

- Add regression coverage for mode serialization, H3/Seedance compiler
  isolation, existing-draft rewrite rules, fixed shot counts, and exact-dialogue
  preservation.
- Complete a paid same-input A/B check against the Seedance chat route: Off and
  Extreme retained all three shots and exact dialogue, while the Extreme result
  produced a materially distinct ordered performance pass.

## [1.12.4] - 2026-09-02

### Fixed

- Stop T8 and official template detail cards from feeding ComfyUI's assigned
  inline DOM height back into their intrinsic content measurement. Previously,
  selecting a template and repeatedly restoring workflow tabs could serialize
  H3 or Seedance nodes at heights above 8,000 pixels.
- Recover already-oversized saved nodes on their next template-detail layout
  pass without changing node IDs, widget values, or workflow connections.

### Verified

- Add a real-browser regression that starts from the reported 8,267-pixel
  saved height, verifies recovery to intrinsic content height, and proves
  repeated workflow restoration remains idempotent.

## [1.12.3] - 2026-09-02

### Changed

- Make the Character Performance Bible's three required fields explicit and
  move its five acting-detail fields behind a non-serialized advanced toggle
  that starts collapsed.
- Add a locale-aware usage card explaining prompt/bible scope and the correct
  green output connection, without changing node IDs, output contracts, or
  saved values.

### Verified

- Add schema, minimal-execution, localization, and real-browser coverage for
  required/optional fields, expand/collapse behavior, help-card placement, and
  non-serialization.

## [1.12.2] - 2026-09-02

### Changed

- Add concise Chinese/English guidance and practical acting examples to every
  multiline field in the T8 Character Performance Bible node, while keeping
  all field IDs, order, empty defaults, outputs, and saved-workflow behavior
  unchanged.
- Update the Chinese and English node labels and bundled help pages to explain
  that the examples are non-persistent placeholders and never enter the output
  performance contract or JSON.

## [1.12.1] - 2026-09-02

### Changed

- Import `batch-2026-09-01-02` as seven new stable selectors and 13 evidence
  variants, while reconciling 20 earlier evidence variants present in the
  authoritative cumulative snapshot. The non-official library now contains
  435 source cases, 221 case selectors, 214 evidence variants, and two
  standalone community Skills (223 selectors total), with no duplicate
  dropdown entries.
- Advance the human-only dynamic-preview channel to `2026.09.01.1`, covering
  all 437 T8 previews in 16 hash-pinned shards while keeping the main
  repository's 377-GIF offline baseline unchanged.
- Let the maintainer preview bundler explicitly validate an oversized bundle
  for the external sharded Release channel, while retaining the hard 90 MiB
  rejection for any bundle intended for the node/Registry package.

## [1.12.0] - 2026-09-01

### Added

- Add a memory-only `Restore previous cloud result` action to the MiniMax H3,
  Seedance 2.0, and MiniMax Music 3 core nodes. A restore reads the last fully
  completed response for that node slot without submitting another paid request.
- Add a same-origin, read-only recovery status endpoint plus bounded in-memory
  checkpoints with one-hour expiry, fixed record/character limits, and no API
  key, source prompt, image, or video data in status responses.

### Changed

- Route Seedance-compatible cloud requests to the direct API endpoint first,
  stream responses into recovery checkpoints, and attach a unique idempotency
  key and client request ID to each logical call.
- Apply the requested output-language contract consistently to cloud and local
  H3, Seedance, and Music generation. A fully received response that is clearly
  in the wrong language may receive one low-temperature language-only repair;
  ambiguous network failures are never repaired or blindly resubmitted.

### Fixed

- Decode streamed SSE bytes explicitly as UTF-8 so Chinese output is not
  corrupted when an upstream `text/event-stream` response is mislabeled as
  ISO-8859-1.
- Stop retrying proxy errors, read timeouts, and mid-stream disconnects when the
  upstream may already be generating. Partial or zero-byte checkpoints are
  never exposed as successful recovered results.
- Preserve the published 31/35/38-widget contracts and existing workflows while
  assigning copied nodes independent recovery slots.

## [1.11.1] - 2026-08-31

### Changed

- Import `batch-2026-08-31-01` as one new stable selector,
  `晨间收获闭环｜人物巡园、连续采摘与动物回应`, plus 19 evidence variants attached to existing
  mechanisms. The non-official library now contains 395 source cases, 214 case
  selectors, 181 evidence variants, and two standalone community Skills (216
  selectors total); no existing selector is removed, renamed, or semantically
  changed.
- Advance the human-only dynamic-preview channel to `2026.08.31.1`, covering
  all 397 T8 previews in 16 hash-pinned shards. The main node repository keeps
  its existing 377-GIF offline baseline while future preview growth ships only
  through the separately versioned resource package.

## [1.11.0] - 2026-08-30

### Added

- Add a local-only Film Project Router for authoritative-input isolation, revision tracking,
  transitive downstream invalidation, world rules, costs/limits, knowledge gaps, and continuity anchors.
- Add a local-only Character Performance Bible, a 1–8 character Stack, and connection-only
  H3/Seedance/Storyboard inputs; each character beat is limited to one primary tactic and at most
  three observable cue channels.
- Add deterministic Storyboard causality, before/after value, scene-necessity, and setup/payoff
  coverage reporting without presenting it as an objective creative-quality score.
- Add Long-form per-segment world-rule checks, knowledge state, and stale downstream status.
- Add a resumable, credential-safe six-group paid A/B runner and a redacted evidence fixture;
  the final enhanced contract scored 100 versus a 44 baseline average on deterministic checks.
- Add reproducibility metadata/model-specific baseline hashes and an actual-render acceptance
  harness for MiniMax H3 / Seedance 2.0 video evidence plus named human scoring.

### Changed

- Extend the bundled long-form/storyboard workflow with Film Project Router and Character
  Performance Bible connections while preserving the original 31/35/38 core widget contracts.
- Enforce exact Storyboard/Long-form top-level JSON schemas, report received keys when providers
  rename the contract, preserve required literal anchors, and keep setup/payoff labels identical.
- Let Film Project Router accept the previous state by direct connection, inherit blank authoritative
  fields, selectively clear one inherited field with an explicit marker, and display invalidated
  downstream stages directly on the node.
- Display Long-form and Storyboard contract validity, item counts, and compact error codes directly
  on each node without adding an LLM request or changing existing outputs.
- Make Router, Long-form, and Storyboard status cards follow the ComfyUI locale and grow to fit
  wrapped diagnostics instead of clipping them at a fixed height.
- Add an appended, compatibility-safe contract-failure policy to Long-form and Storyboard: warning
  preserves prior behavior, while strict mode uses ComfyUI's native blocker after local validation.

### Fixed

- Preserve decimal timing facts such as `1.5秒后` instead of stripping them as numbered-list prefixes.
- Reject incomplete/extra Long-form and Storyboard contracts, wrong shot counts, broken timelines,
  cue-budget overflow, missing literal anchors, duplicate character IDs, and malformed prior revisions
  with explicit diagnostic codes instead of reporting structured success.
- Prevent blank continuation fields from becoming impossible to delete: `[清空继承]` and
  `[CLEAR_INHERITED]` now clear the selected Router field while other blank fields still inherit.
- Prevent invalid non-empty Long-form or Storyboard contracts from silently reaching downstream
  nodes when the user enables strict failure handling; UI and JSON diagnostics remain available.

## [1.10.0] - 2026-08-30

### Added

- Add `T8 Performance Director Config` with conditional `AUTO`, explicit
  `Strong`, and exact `Off` modes for H3, Seedance 2.0, and Storyboard Pack.
- Add additive per-shot performance IR covering trigger, reception, primary
  performance beat, observable cues, gaze target, speech span, transition
  strategy, and advisory risks.
- Add pinned community-research provenance plus a deterministic 200-render
  offline A/B manifest and evidence summarizer that never counts missing
  results or full-frame PSNR as facial-acting success.

### Changed

- Give H3 and Seedance separate native performance-directing compilers, with
  fixed shot counts, exact dialogue, media roles, official contracts, hard
  constraints, and LOCK anchors taking priority.
- Preserve detected body-part, product-component, color, direction, and quoted
  semantic anchors; keep continuously visible transformations visible; and
  enforce a maximum of three observable cue channels per character per beat.
- Extend Prompt Inspector with non-scoring performance advisories and a
  deterministic warning for H3 serialization leaking into Seedance prompts.
- Add an optional source-prompt socket to Prompt Inspector for deterministic
  exact-text, protected-term, and neighboring-part drift checks without
  rewriting the enhanced prompt or making another LLM request.

## [1.9.12] - 2026-08-30

### Changed

- Import the `batch-2026-08-30-01` cumulative snapshot as 40 human-only
  evidence variants attached to existing T8 selectors. Twenty records are the
  explicit current delivery and twenty close the prior cumulative gap; no
  selector is added, removed, renamed, duplicated, or semantically changed.
  The non-official library now contains 375 source cases, 213 case selectors,
  162 evidence variants, and two standalone community Skills (215 selectors
  total), with 377 T8 preview GIFs.
- Advance the external dynamic-preview asset channel to `2026.08.30.1` with 16
  deterministic, hash-pinned shards covering all 377 T8 previews. Full GitHub
  clones retain the complete GIF bundle while Registry installs fetch the
  matching human-only assets on demand.

## [1.9.11] - 2026-08-30

### Fixed

- Close only the topmost dynamic-preview asset manager when users press
  `Escape` over the T8 template browser. The manager now intercepts the key at
  the modal boundary, removes its listener on dismissal, and leaves the
  underlying template browser available until a subsequent `Escape`.

## [1.9.10] - 2026-08-30

### Fixed

- Keep the configured `presence_penalty` when the active
  `llama-cpp-python` chat-completion signature supports it, while omitting the
  optional keyword for older or patched strict signatures that reject it.
  Both the Registry in-process runtime and the GitHub standalone fallback now
  preserve local H3, Seedance, and Music 3 inference across those Wheel APIs.

## [1.9.9] - 2026-08-30

### Added

- Show a high-visibility `管理 / 更新动态预览` reminder and action inside both
  the non-official template dropdown preview and the full T8 template browser.

### Fixed

- Keep only one dynamic-preview resource manager open when users activate the
  update action repeatedly, instead of stacking modal overlays.

## [1.9.8] - 2026-08-29

### Fixed

- Remove inline `<think>...</think>` reasoning traces from shared cloud chat
  responses before they reach H3, Seedance, Music 3, or Creative Suite outputs;
  reasoning-only responses now fail as empty instead of leaking private traces.
- Discover GGUF files that are symlinked from `models/LLM` into external or
  mounted model storage while retaining safe relative workflow identifiers.
- Fall back through every discovered local runtime when a preferred
  `llama-server` cannot start, including an existing `llama-cpp-python`
  installation in the active ComfyUI environment.
- Reject AUTO model/mmproj matches when their known visual families conflict,
  while retaining family-compatible Gemma and Qwen projectors.

## [1.9.7] - 2026-08-29

### Fixed

- Restore Registry and GitHub-clone in-process `llama-cpp-python` inference by
  sending the supported `presence_penalty` argument, with a strict-signature
  regression test for both runtime implementations.
- Stop the H3 secure API-key DOM widget from scheduling a new canvas redraw
  during every draw, preventing severe canvas lag on affected ComfyUI builds.
- Include effective provider request options in Music 3 stage-cache keys so
  changes such as `top_p` or temperature policy cannot reuse stale output.
- Reject known model/mmproj parameter-scale mismatches even when only one
  projector is installed, instead of auto-selecting an incompatible projector.
- Reject IMAGE batches on first-frame and last-frame ports with an actionable
  error instead of silently discarding every image after the first.
- Keep the Seedance upload route's documented 50 MB limit while allowing local
  GGUF, T8 AI Workshop, and OpenAI-compatible inline video paths to use their
  provider-specific limits.
- Normalize string-form H3 duration and word-target values before prompt
  formatting, and preserve deep local GGUF paths in shared provider configs
  without silent 256-character truncation.

## [1.9.6] - 2026-08-29

### Changed

- Import `batch-2026-08-29-01` as 20 human-only evidence variants attached to
  19 existing T8 selectors, without creating duplicate dropdown entries. The
  non-official library now contains 335 source cases, 213 case selectors, 122
  evidence variants, and two standalone community Skills (215 selectors total),
  with 337 T8 preview GIFs.
- Advance the external preview asset channel to `2026.08.29.2` with 16
  deterministic, hash-pinned shards covering all 337 previews.

## [1.9.5] - 2026-08-29

### Fixed

- Make the selected local-GGUF output language authoritative for MiniMax H3,
  Seedance 2.0, and Music 3 Structured Captions. A final language lock now
  follows embedded Skills/examples, and an obvious dominant-language mismatch
  receives one low-temperature local correction without rejecting non-empty
  output or altering protected dialogue, lyrics, labels, and protocol tokens.
- Describe Chinese Music 3 Caption length targets as Chinese characters (or an
  automatic Chinese-appropriate length) instead of English words.

## [1.9.4] - 2026-08-29

### Changed

- Import `batch-2026-08-28-02` as 20 human-only evidence variants attached to
  19 existing T8 selectors, without creating duplicate dropdown entries. The
  non-official library now contains 315 source cases, 213 case selectors, 102
  evidence variants, and two standalone community Skills (215 selectors total),
  with 317 T8 preview GIFs.
- Advance the external preview channel to `2026.08.29.1` with 16 verified
  release shards. Re-encode all 317 T8 previews at 2 fps, 160 px, and 32 colors,
  reducing the full GitHub preview bundle to 72.28 MB while keeping every GIF.
- Make preview-profile changes explicit in the case updater and prevent encoded
  GIF reuse when the requested profile differs from the existing manifest.

## [1.9.3] - 2026-08-28

### Fixed

- Remove a Registry network-rule signature literal from the packaged release
  notes after the 1.9.2 status evidence showed that only the Markdown wording,
  not executable code, triggered the scan.
- Extend the deterministic Registry gate to inspect every packaged text file
  for that signature so documentation cannot reintroduce the false positive.

## [1.9.2] - 2026-08-28

### Fixed

- Replace the preview downloader's dedicated asynchronous HTTP client with the
  repository's existing audited Requests transport, executed off the ComfyUI
  event loop. This preserves HTTPS host allowlisting, redirect validation,
  streaming size limits, SHA-256 verification, and bounded retries while
  removing the exact Registry YARA finding that flagged versions 1.9.0 and
  1.9.1 as `python_network_operations`.

## [1.9.1] - 2026-08-28

### Changed

- Import `batch-2026-08-28-01` as 20 human-only evidence variants attached to
  existing T8 selectors, without creating duplicate dropdown entries. The
  non-official library now contains 295 source cases, 213 case selectors, 82
  evidence variants, and two standalone community Skills (215 selectors total),
  with 297 T8 preview GIFs.
- Advance the external preview asset channel to `2026.08.28.2` with 16
  deterministic, hash-pinned shards covering the complete 297-preview catalog.

## [1.9.0] - 2026-08-28

### Added

- Add a separate, versioned T8 preview asset channel with 16 deterministic
  GitHub Release shards, catalog/source identity pinning, SHA-256 verification,
  safe ZIP extraction, atomic content-addressed caching, and bounded retries.
- Add non-serialized preview management controls to the H3 and Seedance nodes:
  smart on-demand, full-auto, and manual modes plus check, install, repair, and
  clear actions. Preview state is stored only under the ComfyUI user directory.

### Changed

- Keep all 277 T8 GIFs in full GitHub clones for existing users while excluding
  them from the Registry archive. Registry installs retain the selector manifest
  and bootstrap channel, then download only the requested preview shard.
- Reduce the expected Registry archive surface to about 8.5 MiB uncompressed,
  leaving substantial room for future nodes, Skills, cases, and code updates.

### Compatibility

- Preserve all public node IDs, inputs, outputs, widget serialization order,
  selector values, workflows, and prompt behavior. Preview download failures are
  isolated from LLM execution, and preview media can never become model input.

## [1.8.2] - 2026-08-28

### Fixed

- Replace the Registry runtime shim's dynamic `importlib.import_module()` calls
  with ordinary static imports. This preserves the GitHub standalone-runtime
  preference and Registry `llama-cpp-python` fallback without triggering the
  Registry scanner's import-evasion rule.
- Extend the deterministic Registry-package gate to reject future dynamic
  import regressions before publication.

## [1.8.1] - 2026-08-28

### Fixed

- Split the Registry-safe in-process `llama-cpp-python` runtime from the full
  GitHub standalone `llama-server` launcher. Manager installs retain local
  text/vision GGUF inference when a matching Wheel is installed, while full
  GitHub clones preserve the original pinned-runtime and PATH fallback order.
- Add `.comfyignore` packaging and a deterministic scanner-tripwire gate so
  development smoke tests, download/bootstrap tools, direct connection probes,
  environment-default helpers, and external-process launchers cannot make a
  future Registry version `Flagged`.
- Preserve optional environment defaults and credential connection testing in
  full GitHub installs while keeping the Registry package's cloud prompt
  execution, credential storage, official Skills, cases, and previews intact.

## [1.8.0] - 2026-08-28

### Added

- Add a backward-compatible T8 Creative Director suite with 13 independent
  helper nodes for creative briefs, LOCK/EVOLVE/AUTO policy, directed revision,
  long-form H3/Seedance planning, reference-role mapping, multi-direction
  ideation, storyboard delivery, T8 Creative DNA mixing, workflow-local user
  presets, music ideation, version selection, and text-evidence MV beat sheets.
- Add four native example workflows with matching thumbnails, bilingual node
  documentation/localization, and a paid live quality smoke test whose reports
  contain only redacted contract metrics.
- Add a non-serialized prebuilt `llama-cpp-python` Wheel link to all three core
  nodes, plus bilingual installation guidance for users without a local
  llama.cpp runtime.

### Changed

- Add bounded creative-suite output budgets and six-attempt retry handling for
  safe Seedance gateway statuses. Candidate scores are deterministic local text
  heuristics, while storyboard keyframe and transition tables are derived
  locally from the shot contract to avoid duplicate paid generation.
- Re-encode all 285 bundled official/T8 human-preview GIFs at 2 fps, 180 px,
  and 32 colors without removing any preview, and enforce a 90 MiB raw-preview
  ceiling so the complete release remains below the Registry 100 MB ZIP limit.

### Fixed

- Hide all upstream 5xx response bodies from ComfyUI error reports while still
  reporting provider, operation, status, and retry exhaustion.
- Keep MiniMax H3 and Seedance validators open to future ComfyUI Autogrow
  group-level keyword fields in addition to the explicit `reference_images`
  and `reference_videos` compatibility fix. This prevents validation-time
  crashes before execution while leaving declared execution inputs unchanged.
- Align release gates with the actual Comfy Registry package-size scanner;
  versions 1.7.0 through 1.7.8 passed GitHub Actions but were later flagged for
  exceeding 100 MB, which caused Manager reinstalls to fall back to 1.6.0.

## [1.7.8] - 2026-08-27

### Fixed

- Apply the reviewed bundled-preview budget acknowledgement to both ComfyUI
  compatibility jobs, keeping the independent verification workflow aligned
  with the Registry release workflow.

## [1.7.7] - 2026-08-27

### Fixed

- Accept the `reference_images` and `reference_videos` Autogrow groups in the
  MiniMax H3 and Seedance 2.0 custom validators, preventing recent ComfyUI
  development builds from rejecting Ref2VA/reference-media workflows before
  node execution.

## [1.7.6] - 2026-08-27

### Fixed

- Pass the reviewed T8 GIF budget acknowledgement into the GitHub release
  verification step now that the complete 277-preview package is above the
  confirmation threshold but remains below the hard repository limit.

## [1.7.5] - 2026-08-27

### Changed

- Import `batch-2026-08-27-01` as 15 human-only evidence variants attached to
  nine existing T8 selectors, without creating duplicate dropdown entries. The
  non-official library now contains 275 source cases, 213 case selectors, 62
  evidence variants, and two standalone community Skills (215 selectors total),
  with 277 bundled preview GIFs.
- Accept evidence handoffs that bind `duplicate_of` directly to the stable
  `template_id`, while retaining strict same-template validation and backwards
  compatibility with source-case and evidence-chain bindings.

## [1.7.4] - 2026-08-26

### Fixed

- Allow saved local GGUF model and projector selections to survive ComfyUI's
  schema validation when files differ between machines, so cloud and
  OpenAI-compatible modes are no longer blocked by unused stale local values.
- Enforce the local non-thinking setting at llama-server startup when the
  runtime supports it, pass the matching template setting, and remove leaked
  `<think>` traces from returned text as a defensive fallback for third-party
  Qwen chat templates. The llama-cpp-python fallback also applies supported
  load-time template settings.

## [1.7.3] - 2026-08-26

### Changed

- Import `batch-2026-08-26-02`: add one stable dual-model T8 case selector
  with one bundled human-only GIF preview. The non-official library now
  contains 260 source cases, 213 case selectors, 47 evidence variants, and
  two standalone community Skills (215 selectors total). Official MiniMax
  Skills and model-reference media boundaries remain unchanged.

## [1.7.2] - 2026-08-26

### Changed

- Import `batch-2026-08-26-01`: add 10 stable T8 case selectors and merge 10
  same-mechanism evidence variants without duplicate dropdown entries. The
  non-official library now contains 259 source cases, 212 case selectors, 47
  evidence variants, and two standalone community Skills (214 selectors total),
  with 261 bundled human-only GIF previews. The official nine MiniMax Skills
  remain unchanged and preview/source media stays disconnected from LLM inputs.

## [1.7.1] - 2026-08-26

### Fixed

- Wrap the template-browser category controls into a responsive grid so
  Chinese labels remain inside the panel instead of overflowing or requiring
  a horizontal scrollbar.
- Refresh the non-official case library with the owner-confirmed distribution
  contract: all 239 released cases include handoff media, while source media
  remains disconnected from model reference inputs by default.

## [1.7.0] - 2026-08-26

### Changed

- Remove the 30-second prompt-duration ceiling from the MiniMax H3 and
  Seedance 2.0 enhancers. H3 now accepts any positive integer duration;
  Seedance accepts `AUTO` or a user-entered positive integer while preserving
  existing saved workflow values. Downstream video-model limits remain
  independent of this prompt-planning setting.

## [1.6.0] - 2026-08-25

### Added

- Add a pinned `heretic-9b` installer variant and verified-model recognition
  for `Qwen3.8-9B-heretic-uncensored.i1-Q6_K.gguf`, while retaining the
  existing 27B default and all saved workflow values.
- Prefer parameter-scale-compatible visual projectors during AUTO matching so
  a same-folder 27B mmproj is never silently selected for a 9B model.

## [1.5.5] - 2026-08-25

### Changed

- Import `batch-2026-08-25-04`: add 14 stable T8 case selectors and merge
  six evidence variants without creating duplicate dropdown entries; the
  non-official library now contains 239 source cases, 202 case selectors,
  37 evidence variants, and two standalone community Skills.

## [1.5.4] - 2026-08-25

### Changed

- Add one author-approved human-only GIF evidence variant to
  `t8-case-hand-bounded-local-medium-window-v1` without creating a duplicate
  selector; the non-official library now contains 219 source cases, 188 case
  selectors, 31 evidence variants, and two standalone community Skills.

## [1.5.3] - 2026-08-25

### Added

- Add a comprehensive English README with installation, provider, local GGUF,
  workflow, Skill, security, media, and troubleshooting guidance.
- Add explicit Chinese/English language switches while keeping `README.md` as
  the default Chinese GitHub landing page.

## [1.5.2] - 2026-08-25

### Added

- Add the non-official `时尚密度复位｜身份锁定、拼贴回顾与英雄主标` and
  `手势边界换媒｜局部窗口、多形态验真与回归` selectors for MiniMax H3 and
  Seedance 2.0, including bundled human-only GIF previews and editable examples.

### Changed

- Validate case-library and community-Skill inventory against each immutable
  delivery's declared counts instead of requiring a source-code count edit for
  every daily cumulative handoff.

## [1.5.1] - 2026-08-24

### Fixed

- Make the local-runtime readiness test independent of a developer machine's
  private runtime configuration so the minimum supported Linux ComfyUI release
  gate verifies the same runtime contract as Windows installations.

## [1.5.0] - 2026-08-24

### Added

- Discover text models and vision projectors recursively below
  `ComfyUI/models/LLM`, classify lightweight GGUF metadata, preserve legacy
  Qwen3.8 filenames, and auto-pair compatible mmproj files.
- Reuse an existing `llama-cpp-python` installation when the private bundled
  `llama-server` runtime is absent; also recognize `llama-server` on `PATH`.
- Show the actual model directory, discovered model/projector counts, runtime
  source/version, selected-model capability, and verification tier in all local
  status controls, with one-click directory copy and live dropdown refresh.

### Changed

- Generalize the local provider label beyond the two pinned Qwen3.8 files while
  keeping the former label as a workflow-compatible execution alias.
- New visual selections default to metadata-based mmproj AUTO matching; saved
  explicit projectors and all existing widget layouts remain valid.

## [1.4.3] - 2026-08-24

### Fixed

- Persist OpenAI-compatible Base URL and model ID across runs, API-mode
  switches, and workflow reloads for all three core nodes, including the
  unblurred DOM-input edge case; API keys remain excluded from this state.

## [1.4.2] - 2026-08-24

### Fixed

- Made a selected T8 non-official case/community template take precedence over
  all eight optional MiniMax official scene Skills, including `AUTO`, while
  keeping the always-on H3 core writing Skill active.
- Preserved the saved official scene-Skill value so existing workflows require
  no reconnection and automatically restore it after the T8 template is cleared.
- Added an explicit inactive label and hid the official preset detail card while
  a T8 template is active, avoiding conflicting UI guidance.

## [1.4.1] - 2026-08-24

### Fixed

- Corrected Seedance 2.0 widget serialization to follow ComfyUI V3's
  required-before-optional runtime order, so bundled workflows no longer send
  `randomize` to the integer `custom_length_target` input. Existing 1.4.0
  workflows are migrated by stable widget name when reopened.

## [1.4.0] - 2026-08-24

### Fixed

- Expanded legacy H3, Seedance 2.0, and Music 3 widget arrays before ComfyUI
  validates appended local-Qwen combo fields, preventing `randomize` or `null`
  from being interpreted as a GGUF model name.
- Rebuilt all four existing example workflows with the current 31/35/38 widget
  contracts.

### Added

- Added the author-authorized `指尖控制｜四向同拍全身响应` T8 selector for
  both MiniMax H3 and Seedance 2.0, with one bundled human-only lightweight GIF.
  The source video and direct-final example prompts are not bundled or sent to
  the LLM.
- Added dependency-free `T8 Prompt Text` and `T8 Show Text` STRING utility nodes,
  including a read-only result preview, copy action, localization, node
  documentation, and a dedicated example workflow.
- Added native output viewers to generated local-Qwen and multi-task workflows,
  so results can be inspected without EasyUse or Comfyroll.
- Added dedicated local Qwen3.8-27B workflows for H3, Seedance 2.0, and Music 3,
  plus a local H3-to-Prompt-Inspector workflow. Every local example includes a
  preconnected `T8 LLM Provider Config` node and a matching thumbnail.

## [1.3.0] - 2026-08-24

### Added

- Added optional shared LLM provider configuration for all three enhancer nodes,
  including explicit/automatic temperature handling, allowlisted request options,
  local Qwen settings, and workflow-safe local credential aliases.
- Added deterministic provider capability preflight, copyable redacted diagnostics,
  a local non-blocking Prompt Inspector, and local Top-3 template recommendation
  with two-to-three-template comparison.
- Added real-browser layout/performance contracts and a standard case-library
  delivery gate with immutable manifest checks, stable-ID diffs, preview staging,
  budget confirmation, rollback, tests, and machine-readable reports.

### Changed

- Preview bundles now use content-addressed GIF assets so multiple evidence
  variants may safely share identical encoded bytes. New previews have a 2 MiB
  per-file cap and the package uses 150/165/180 MiB warning/confirmation/hard gates.
- Hidden OpenAI model and Base URL values are restored and serialized by stable
  widget name across mode switches and workflow reloads.

### Compatibility

- The original three node IDs remain first in registration order, their output
  names/order remain unchanged, and their 31/35/38 serialized widget contracts
  are frozen. The shared provider socket is optional and adds no widget value.
- With no shared config connected, provider, model, temperature, retry, media,
  prompt, cache, and non-empty-output behavior follow the 1.2.0 path.

## [1.2.0] - 2026-08-24

### Added

- Expanded the bundled non-official library to 185 case selectors and two
  standalone community Skills, with 30 evidence variants and no pending cases.
- Added the approved August 21–23 case-library deliveries through stable IDs,
  Chinese labels, editable recommended inputs, mechanism anchors, dual H3 and
  Seedance 2.0 guidance, and bundled human-only GIF previews.

### Changed

- Accepted strictly traceable same-template evidence-variant chains while
  continuing to reject missing parents, cross-template bindings, and cycles.
- Re-encoded all 217 T8 previews at 3 fps, 224 px maximum width, and 40 colors,
  keeping all 225 official/T8 GIFs within the 180 MiB repository budget.
- Refined secret-pattern tests so ordinary identifiers containing
  `risk-release` are not mistaken for API keys.

### Verified

- All 177 unit and compatibility tests pass.
- The cumulative inventory closes at 215 source cases, 185 case selectors,
  30 evidence variants, two community Skills, and 187 non-official selectors.
- Preview files remain human-interface-only and are never connected or sent as
  model or LLM reference material.

## [1.1.2] - 2026-08-21

- Reused ComfyUI's initialized device-management module so Music 3 execution
  remains testable in CPU-only environments without triggering a CUDA probe.
- Made the local Music 3 provider contract test independent of GGUF files
  installed on the developer machine.

## [1.1.1] - 2026-08-21

- Added the Python 3.10 `tomli` fallback used by release verification.
- Deferred ComfyUI device-state imports until Music 3 execution so CPU-only
  metadata and CI environments can import the node package safely.

## [1.1.0] - 2026-08-21

### Added

- Release verification, semantic-version tooling, compatibility checks, and
  guarded Registry publishing.
- Native ComfyUI workflow templates, localized node documentation, and
  Chinese/English node-definition localization.
- Searchable T8 template browser with categories, favorites, recent choices,
  GIF previews, and backward-compatible selector values.
- Redacted execution progress and diagnostics shared across cloud and local
  providers.

### Changed

- Synced the pinned MiniMax H3 core prompt-writing Skill after an explicit
  upstream diff review and added deterministic source manifests. The weekly
  read-only drift check covers the H3 core, all eight official creative Skills,
  and the Music 3 caption rewriter.
- Advanced the eight creative-Skill provenance markers after reviewing the
  upstream compatibility-only change, and documented that this node adapts
  prompt-writing constraints without claiming to execute Hub-native workflows.
- Reduced bundled GIF cost while keeping every official and T8 preview in the
  installable package, and deferred menu decoding during rapid pointer travel.
- Consolidated provider request, retry, response, and diagnostic behavior
  without changing the three public node IDs or their existing outputs.

### Verified

- Existing workflow migrations and all three nodes remain compatible with the
  published 1.0.x workflows.
- Both supported Qwen3.8 GGUF variants are covered by contract and media
  compatibility checks. The optional Uncensored Q4_K_M variant additionally
  passed the complete five-case release-quality suite at 100/100, including
  deterministic seeds, Chinese Music 3 lyrics, official Skill use, and ordered
  image/video evidence for H3 and Seedance 2.0. Reports remain redacted and
  reproducible.

## [1.0.2] - 2026-08-20

- Enforced release identity and Registry versioning rules.

## [1.0.1] - 2026-08-20

- Completed Comfy Registry package metadata.

## [1.0.0] - 2026-08-20

- Initial Comfy Registry release of the MiniMax H3, Seedance 2.0, and MiniMax
  Music 3 prompt-enhancer suite.
