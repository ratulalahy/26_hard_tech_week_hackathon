---
name: viz-critique
description: Use when a dashboard view or story beat is built or changed. Covers the rubric, the screenshot set, the independent Codex image critique, the axe scan, and the triage that ends every UI task.
---

# Viz critique

The bar: a judge who sees one screen understands its insight in five seconds and believes the number. Craft, not decoration. The demo runs offline in Chrome on a MacBook Pro.

## The loop (it ends every UI task)

1. **Shoot** with Playwright.
   - Two sizes: 1440×900 and 1728×1117 (the MacBook Pro's default resolution).
   - Light and dark, if both exist.
   - Every state the task touched.
   - Mark fixture data on the image itself.
2. **Self-pass** through the rubric below. Write each finding as `view | rubric item | severity | evidence | fix`.
3. **axe scan** (WCAG 2.2 AA) on the built page. The target is 0 violations.
4. **Fix**, then re-shoot. Keep the before set.
5. **Codex critic.** It gets a fresh context, with the images and the rubric only. Use the image-critique command in `.claude/skills/codex-gates/SKILL.md`, and ask for every violation with severity and confidence.
6. **Triage** every finding: fixed, rejected (with the reason) or deferred. Record them in `docs/reviews/`.

## Rubric

- **Insight first.** Each view answers one question, and its title states the finding ("Utah's rush hour is 6–9 PM in July"), not a label ("Demand").
- **Honest charts.**
  - Bars start at zero; no dual axes.
  - Uncertainty is shown (bands or intervals) wherever a number is an estimate.
  - Every axis has units, and the time zone is stated.
- **Labels.** Values that are forecast, modeled, assumed or simulated carry a visible badge (see the `hackathon-evidence` skill). Fixture data says FIXTURE.
- **Color.**
  - Use the palette from the design tokens, validated with the dataviz skill.
  - Sequential scales for magnitude; diverging only around a meaningful midpoint.
  - Never rely on color alone.
  - WCAG AA contrast: 4.5:1 for text, 3:1 for marks and UI.
- **Type.** One family plus a mono with tabular figures for numbers, on a clear scale.
- **Hierarchy.** One focal element per screen. Chrome recedes. Annotations point at the insight.
- **Motion.**
  - Only to show change over time, or cause and effect.
  - At most 400 ms for UI transitions.
  - Story-mode scrubbing is tied to scroll.
  - `prefers-reduced-motion` is honored.
- **Performance.** 60 fps for the map and the replay on the laptop, and no layout shift when data loads.
- **Offline.** No network requests at runtime (check the network panel). Fonts, map layers and data are all local.
- **States.** Every data view has loading (a skeleton in the final shape), empty, error and content.

## Severity

| Severity | Meaning |
|---|---|
| critical | a misleading number, broken offline mode, an unreadable view, or anything that blocks the story |
| major | a rubric item a judge would notice |
| minor | polish |
