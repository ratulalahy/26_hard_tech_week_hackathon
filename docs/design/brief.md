# Design brief (shared by all four directions)

Claude's three mockups (B, C, A) and Astra's own direction all build from this page.

- **References:** `docs/design/references.md`.
- **Rules:** `AGENTS.md` and `.claude/skills/viz-critique`.
- **Precedence:** once the spec is approved, its story beats and results contract replace the beats and views proposed here.

## Audience and job

- **Who:**
  - The Torus bounty judges. Torus builds flywheel and battery storage that buffers AI data-centre load, in Salt Lake City.
  - Assume they are grid-literate: they know a net-load curve.
  - They see a one-on-one demo of 4–5 minutes plus questions, on the owner's MacBook Pro, offline.
- **Judged on:** creativity, clarity of insight, and execution.
- **What we show:**
  - a day-ahead **traffic report** for the US grid;
  - a **simulated router** that moves AI training jobs to cleaner hours (**wait**) or to cleaner regions (**move**).
  - Utah (PACE) is the hero region.
- **The UI's job:**
  - Each screen lands **one insight a judge gets in five seconds and believes**.
  - Each screen then lets the judge poke at that insight.

## The two insights

The numbers below are validation-year figures (2024-11 to 2025-10) from `docs/data-profile/grid.md`. Use them in mockups only.

1. **Moving beats waiting.**
   - **Waiting:** a PACE job that may wait ≤ 24 h cuts its average carbon intensity by **at most 33%**, and by 15% if it may wait ≤ 6 h. Both figures assume perfect foresight.
   - **Moving:** moving the job to **BPAT, CISO or NEVP cuts 94%, 66% or 42%**. These are production-basis figures; on a consumption basis, BPAT's cut is 82%.
   - Destinations have capacity limits, so "send everything to BPAT" is not the answer.
2. **Clean hours ≠ rush hours in Utah.**
   - **The rush hour** is a narrow summer late afternoon. Demand peaks at 17:00 local and net load at 20:00.
   - **The dirtiest hours** are coal nights, at about 600–700 g/kWh.
   - **They barely overlap.** Demand and carbon correlate at −0.18, and the top-100 demand hours are only 3% dirtier than average.
   - So an emissions-first router moves Utah work **from nights into the midday solar trough, not out of the 5–8 PM peak.**

**Honesty rule.**
- These are gains in *average* intensity.
- PACE's *marginal* intensity stays at roughly 500–660 g/kWh all day, so waiting avoids far less at the margin. Skeptic mode shows this.
- Never call an average-CI saving "avoided".

## Story beats (a proposal for 4–5 minutes)

| Time | Beat | Views | What lands |
|---|---|---|---|
| 0:00–0:30 | "Utah's grid has a rush hour." Play one July day. | Grid clock | Demand peaks at 17:00, net load at 20:00. |
| 0:30–1:15 | "But the rush isn't the dirt." Put carbon on the same axis. | Clean≠rush strips, load-curve story | Insight 2 |
| 1:15–2:00 | "Wait for the sun." A job slides into midday. Drag the delay budget, then turn on skeptic mode. | Delay-budget slider, skeptic mode | ≤ 33% on average, and the marginal caveat |
| 2:00–3:00 | "Or move." Arcs go out to the Northwest, California and Nevada. Replay with capacity caps, and click a job to see its trace. | Map with arcs, move-vs-wait replay | Insight 1 |
| 3:00–3:45 | "Tomorrow's report." Show the day-ahead card, then plan a run. | Tomorrow card, Plan my run | The product |
| 3:45–4:30 | "How we know." Open the evidence chips and show the results (simulated, test window). | Evidence chips | Credibility |

- Keep about 30 s of buffer.
- Story mode is scroll-driven.
- Explore mode keeps every view reachable for questions.

## Views

- **Grid clock:** one BA's day over 24 hours: demand, net load and carbon, a "now" cursor, and an "as of" stamp. Each direction chooses whether it is a dial or a strip.
- **Load-curve story:** the sticky 24-hour chart behind the scroll story. Overlays change step by step.
- **Map with arcs:** the West on relief, with BA outlines, ≤ 10 labelled arcs for moved work, and "estimated" badges.
- **Move-vs-wait replay:** run-now vs routed, drawn on one axis. Clicking a job opens its decision trace: origin, decision, destination, start time, tCO₂ vs run-now, and deadline.
- **Delay-budget slider:** allowed wait from 0 to 24 h. The "CO₂ saved vs wait" curve is drawn on the slider's own track.
- **Skeptic mode:** average → consumption → marginal. The numbers change, and the claim's wording changes with them.
- **Clean≠rush strips:** two aligned 24-hour bands for the same day, one for carbon and one for rush hour, with the mismatch labelled.
- **Plan my run:**
  - The input is a sentence with scrubbable values: GPUs, hours, deadline, region.
  - The output is run now, wait or move, with tCO₂ and the deadline slack.
  - It is deterministic and runs in the browser.
- **Tomorrow card:** the issue time, a verdict sentence, the day's average, max and min, a bar for the typical range, and one advisory.
- **Evidence chips:** every number shows its label, source, window and a method link, and expands into an "About this data" panel.

## Constraints

- **Offline.** No network requests at runtime:
  - fonts come from `@fontsource`;
  - the map uses local GeoJSON and the relief PNG, with no tile, glyph or sprite server;
  - data comes from `results/`.
- **Light only.** No dark theme and no `prefers-color-scheme` switch.
- **Display.**
  - Chrome on a MacBook Pro at **1728×1117**; also check 1440×900.
  - The map and the replay run at 60 fps.
  - No layout shift when data loads.
- **Accessibility (WCAG 2.2 AA).**
  - Contrast: 4.5:1 for text, 3:1 for marks and UI.
  - Never rely on colour alone.
  - Every control is reachable by keyboard, with a visible focus state.
  - `prefers-reduced-motion` is honoured.
  - UI transitions take ≤ 400 ms.
- **Evidence labels on every value:** observed, measured, forecast, modeled, assumed or simulated. Fixture data says FIXTURE on the image itself.
- **Map attribution, verbatim:** "BA boundaries © Electricity Maps contributors (AGPL-3.0). BA codes: U.S. EIA Form EIA-930. Basemap: Natural Earth."

## Real pre-test data for the mockups

- Everything here predates the sealed window [2025-11-01Z, 2026-11-01Z). Filter through `gridpilot.splits.drop_sealed`.
- Worktrees read the main checkout's data through `GRIDPILOT_DATA_DIR`.

| For | Data | Where | Label |
|---|---|---|---|
| PACE grid clock | Hourly demand, net load (demand − wind − solar), fuel mix, and PACE's own day-ahead forecast (a baseline, not ours). A July 2024 week is profiled. | `data/interim/eia930/balance.parquet`; figure `docs/data-profile/figures/grid/pace_week_jul2024.png` | observed |
| Carbon by hour | EIA's hourly CO₂ per BA (production and consumption basis), our fuel-mix CI, and validation-year hourly profiles for 18 BAs | `data/raw/eia930/ba_workbooks/*.xlsx`; `grid.md` §8; figures `ci_diurnal.png`, `ci_shift_room.png`, `ci_by_ba.png` | modeled |
| Arcs | BA-to-BA interchange. PACE's mean net flows include IPCO +846 MW and NEVP +198 MW. | `data/interim/eia930/interchange.parquet` | observed |
| Map | 54 BA polygons and points; land, lakes, rivers, Interstates, states and cities; a 2048×1489 shaded relief | `data/processed/geo/`: `ba_boundaries.geojson`, `ba_points.geojson`, `basemap/*.geojson`, and `basemap/relief.png` with `relief.json` | n/a |
| Prices (optional) | WEIM real-time PACE prices and CAISO hubs | `data/raw/prices/` | observed; shown as a "wholesale scenario" |
| Workload facts | Acme Seren: 2,288 GPUs at 61% load. Pre-training is 0.9% of jobs but 69.5% of GPU-hours. | `docs/data-profile/workloads-prices.md` | measured |

- **Not available yet:** our forecasts, the router's schedules, and every test-window number.
- Mock these as FIXTURE with plausible shapes, never as results.

## "No AI look" rules

1. **One focal element per screen:** a real curve or a real map. No hero illustration, no mascot.
2. **No purple or violet gradients, no neon, no gradient text.** Colours come from the direction's token sheet, and each data colour means one thing everywhere.
3. **No cards and no admin template:**
   - no card grids of icon + big number + delta;
   - no sidebar + KPI row + chart-grid layout;
   - no bento.
4. **Sentence case everywhere.** No ALL-CAPS tracked eyebrows.
5. **No cream + serif + terracotta.**
6. **No glass, glow, heavy shadow or hover-lift.** Hairlines and whitespace give the structure.
7. **No decorative icons, sparkles or emoji.** Icons appear only where they are controls.
8. **No count-up numbers, bounce or staggered fade-ins.** Motion is only for change over time, or for cause and effect.
9. **No donut or gauge for one number, no rainbow or spectral scale, no dual axes.**
10. **Titles state the finding,** such as "Utah's dirtiest hours are its coal nights", not a label such as "Carbon intensity".
11. **Yellow is a fill, never a line or text.** Every direction's yellow is below 2.1:1 on white.
12. **Real numbers, rounded honestly, each with its label.** Fake precision is an AI tell too.

## The directions

| Direction | Type | Palette | Made by |
|---|---|---|---|
| B Live Load Curve | Archivo | cobalt `#1636D9`, solar `#FFB703`, peak red `#E63946` | Claude |
| C Basin & Range | Big Shoulders + Public Sans | salt `#F4F7F8`, lake `#0F6E8C`, sunrise `#F2A900`, ember `#C8102E` | Claude |
| A Highway Advisory | Overpass | interstate green `#00703C`, advisory yellow `#FFC72C`, express blue `#0060A9` | Claude |
| Astra's own | open | open | Astra (Codex) |

- **Each mockup** is one static screen at 1728×1117. It uses real pre-test data: the PACE grid clock and the map of the West.
- **Refinements for each direction** (type, colour, motion) are in `references.md` under "Per-direction notes".
- **Choosing:** the owner picks a direction at G2. The picked direction's tokens then go into `docs/design/tokens.md`.
