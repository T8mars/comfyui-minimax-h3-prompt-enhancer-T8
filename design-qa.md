# Dynamic Preview Update CTA Design QA

## Comparison Target

- Source visual truth: `C:\Users\ADMINI~1\AppData\Local\Temp\codex-clipboard-52c32f3a-2be6-4b8e-bb81-e5a8cb7e3f16.png`
- Browser-rendered implementation: `G:\CodexHome\.codex\visualizations\2026\08\03\019fc835-cafe-7b73-991b-95aaf54e10a2\t8-preview-manager-cta-qa.png`
- Source pixels: 1144 × 869.
- Implementation pixels / CSS viewport: 1280 × 900 at the browser's default 1× capture density.
- State: the source shows the existing dark ComfyUI node and the two entry points; the implementation shows the opened T8 template browser with the new persistent preview-update reminder and action. The states intentionally differ because the requested controls did not exist in the source open states.
- Density normalization: none required for layout judgment; both captures were reviewed at native size, with the focused CTA region inspected separately.

## Full-View Comparison Evidence

- The implementation retains the existing ComfyUI dark palette, compact border treatment, typography hierarchy, modal radius, and dense control rhythm visible in the source.
- The new amber reminder occupies one bounded row above browser content. It does not cover search, filters, template details, GIF content, or selection controls at 1280 × 900.
- The management action has substantially stronger contrast than ordinary buttons while staying inside the existing dark UI vocabulary.

## Focused Region Evidence

- The browser CTA reads `管理 / 更新动态预览` and is paired with the visible reminder `首次使用或 GIF 未显示？请先检查并更新动态预览。`.
- The dropdown-side preview uses the same label, amber semantic color, and reminder copy before its GIF area.
- Real-browser contracts clicked both entry points, confirmed that the resource manager opened, and confirmed that reopening replaces the prior modal rather than stacking overlays.

## Required Fidelity Surfaces

- Fonts and typography: inherited ComfyUI/system fonts remain unchanged; reminder copy uses a compact 12 px hierarchy and a 700-weight action label without truncation.
- Spacing and layout rhythm: 8–10 px CTA spacing matches surrounding controls; flex wrapping protects compact layouts; no persistent control is hidden.
- Colors and visual tokens: existing CSS variables remain the base; amber is limited to the update callout and meets the requested conspicuous state.
- Image quality and asset fidelity: no new image assets, placeholders, or generated graphics were introduced; GIF rendering and lifecycle behavior are unchanged.
- Copy and content: both requested open states explicitly tell users when and where to manage or update previews.

## Findings

- No actionable P0, P1, or P2 visual mismatch remains.
- P3: the exact amber hue may vary slightly with custom ComfyUI themes because surrounding surfaces use theme variables; the CTA contrast remains explicit by design.

## Comparison History

1. Initial implementation added both CTA locations and passed the real-browser click contract. Audit then found that repeated programmatic opens could stack resource-manager overlays.
2. The resource manager was changed to keep a single active modal. The post-fix browser run passed the dropdown action, browser action, manager-open, single-overlay, responsive-layout, and performance checks.

## Primary Interactions and Console Gate

- Dropdown preview action: present and clickable.
- T8 template browser action: present and clickable.
- Resource manager: opens from the browser CTA.
- Reopen behavior: exactly one resource-manager overlay remains.
- Browser stderr / fatal console gate: clean on the final passing Edge run.
- Frontend performance: three-node layout 4.9 ms; 1,200 drag frames 3.1 ms; 300 preview switches 1.2 ms.

## Final Result

final result: passed
