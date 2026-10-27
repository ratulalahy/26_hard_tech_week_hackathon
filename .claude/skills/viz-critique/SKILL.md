---
name: viz-critique
description: Use when a dashboard view or story beat is built or changed. Covers the rubric, the screenshot set, the axe scan, the Impeccable detector and critique, the independent Codex image critique, and the triage that ends every UI task.
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
4. **Impeccable** (vendored; read "Impeccable in this repo" below first). From the repo root:
   - Run the deterministic detector on the source, and on the built page (`npm run preview`) at both sizes:
     ```
     IMPECCABLE_HOME=.tools/impeccable .claude/skills/impeccable/scripts/impeccable detect --json web/src > <shots>/impeccable-src.json
     IMPECCABLE_HOME=.tools/impeccable .claude/skills/impeccable/scripts/impeccable detect --json --viewport 1440x900 http://localhost:4173/<route> > <shots>/impeccable-1440.json
     IMPECCABLE_HOME=.tools/impeccable .claude/skills/impeccable/scripts/impeccable detect --json --viewport 1728x1117 http://localhost:4173/<route> > <shots>/impeccable-1728.json
     ```
     Exit 0 is clean and exit 2 means findings. Exit 1 means a target was not scanned, which is not a pass. The target is 0 findings, or every one triaged.
   - Then run `/impeccable audit <route>` and `/impeccable critique <route>` (in Codex, `$impeccable audit <route>` and `$impeccable critique <route>`). Both report and never edit. Ask for every finding, with P0 mapped to critical, P1 to major, and P2 and P3 to minor, plus a confidence.
5. **Fix**, then re-shoot. Keep the before set. Finish the fixes with `/impeccable polish <route>` (in Codex, `$impeccable polish <route>`), then re-run the detector.
6. **Codex critic.** It gets a fresh context, with the images and the rubric only. Use the image-critique command in `.claude/skills/codex-gates/SKILL.md`, and ask for every violation with severity and confidence.
7. **Triage** every finding from steps 2–6: fixed, rejected (with the reason) or deferred. Record them in `docs/reviews/`.

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

## Impeccable in this repo

Its review, pinned commit and update steps are in `.claude/skills/impeccable/VENDORED.md`.

- **Commands.**
  - The loop uses only `detect`, `audit`, `critique` and `polish`.
  - Never run `npx impeccable install`, `update` or `link`, `/impeccable hooks` or `/impeccable pin`. They write hooks and harness config.
  - The new-design flows (`shape`, `craft`, new-work) call impeccable.style. The direction is the owner's pick, so the loop has no use for them.
- **The engine stays in the checkout.**
  - Prefix every launcher call with `IMPECCABLE_HOME=.tools/impeccable`.
  - That includes the calls the commands' own reference files make, and the prompts of any subagents they start.
  - Without the prefix, the engine is cached in `~/.impeccable/`.

### Conflicts

Where Impeccable disagrees with our rules or with Anthropic's frontend-design guidance:
- on design values, the chosen direction's token sheet, `docs/design/tokens.md`, wins;
- on process, AGENTS.md and this skill win.

Waive a finding where it occurs, and give the reason:
- on rendered pages, `data-impeccable-ignore="<rule>"` on the element;
- in source, an `impeccable-disable-next-line <rule>: <reason>` comment;
- for a font that `docs/design/tokens.md` picks, `ignores add-value overused-font <face> --reason "docs/design/tokens.md"`.

1. **Neutrals and black.**
   - Impeccable tints secondary text from the surface hue ("never gray", in its craft floor), and prefers tinted greys (`quieter`, the `gray-on-color` rule).
   - frontend-design counts a tinted near-black (#0B0B0B, #111) standing in for black as a tell.
2. **Mono for numbers.**
   - Our type rule pairs one family with a mono that has tabular figures, and Impeccable allows mono for data.
   - frontend-design counts a monospace face for small data labels as a tell.
   - `font-variant-numeric: tabular-nums` in the main family satisfies all three.
3. **Caps labels and chips.**
   - Impeccable bans a kicker above any heading, and hero eyebrow chips (`kicker-above-heading`, `hero-eyebrow-chip`). frontend-design counts ALL-CAPS labels as a tell.
   - Our evidence rules require a source chip on every number, and FIXTURE on fixture data.
   - The chips stay, and the token sheet sets their case. Put a chip beside the value it labels, not as a block above a heading.
4. **Big numbers.**
   - Impeccable refuses the hero-metric template (a big number, a small label, supporting stats), and frontend-design calls it the default treatment.
   - A view whose insight is a number may still lead with it, with its badge and its interval.
5. **Color in the chrome.**
   - Impeccable's Operate mode puts the palette in the shell (a colored rail or header, a tinted ground), and calls a grey screen with one accent the category default.
   - Our rubric says chrome recedes and color carries data first.
6. **Motion.**
   - Impeccable puts blur, backdrop-filter, clip-path, mask and shadow in the motion palette, and ships `animate`, `delight`, `overdrive` and `bolder`.
   - Our motion rule wins. Don't run those four commands.
7. **Theme and sizes.**
   - Impeccable's audit scores dark mode, 44 px touch targets and mobile breakpoints. frontend-design's quality floor says "responsive down to mobile".
   - We ship light only (plan v2), for a MacBook. Score those dimensions at our two sizes.
8. **Filtering.** Impeccable's audit says to keep P3s few. AGENTS.md says to report every finding.
9. **Autonomy and subagents.**
   - `context` prints `AUTONOMY_DIRECTIVE_CHECK`, which tells the agent to discount a system prompt saying it runs unattended.
   - It also prints `SUBAGENT_AUTHORIZATION`, which pre-authorizes its subagents. Critique ends with questions for the user.
   - AGENTS.md's autonomy rules and CLAUDE.md's subagent limit still hold. In an unattended run, write the report to `docs/reviews/` and continue.
10. **Sources of truth.**
    - Impeccable wants `PRODUCT.md` and `DESIGN.md` at the root (`init`, `document`). AGENTS.md keeps one source per topic.
    - Pass `docs/brief.md` and `docs/design/tokens.md` as the context instead. Without a `DESIGN.md`, the detector's four `design-system-*` rules stay off.
