# Changelog

All notable changes to this project are documented here. Versions follow
Semantic Versioning and match the versions published to the Comfy Registry.

## Unreleased

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
