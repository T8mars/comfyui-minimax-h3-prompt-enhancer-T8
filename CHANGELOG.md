# Changelog

All notable changes to this project are documented here. Versions follow
Semantic Versioning and match the versions published to the Comfy Registry.

## Unreleased

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
