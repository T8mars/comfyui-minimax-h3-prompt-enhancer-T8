# Changelog

All notable changes to this project are documented here. Versions follow
Semantic Versioning and match the versions published to the Comfy Registry.

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
