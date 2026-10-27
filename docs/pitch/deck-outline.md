# GridPilot: deck outline (DRAFT)

**Status:** draft, 2026-10-27 (D-063). The deck is built in a Slides artifact on Wednesday after the test run and audit.

- The live demo is the spine (`narrative.md`). The deck backs it up, or replaces it if WebGL or the laptop fails.
- Eight slides plus an appendix.
- Visuals come from the dashboard, as screenshots in `docs/design/shots-build/`, re-shot on the test-year window.
- `{{TEST: ...}}` and `{{STORAGE: ...}}` are filled after the audit. Numbers marked "validation" are from Nov 2024 – Oct 2025.

---

### 1. Title

- **Title:** GridPilot: compute follows cleaner power
- **Message:** When and where should a Utah AI job run? We measured which lever matters.
- **Visual:** the Control room at 1728 px (`control-1728.png`, re-shot on the test window), with the map, the Utah-to-Northwest arcs, and the rush strip along the bottom.
- **Speaker note:** "GridPilot is a day-ahead traffic report for the grid, plus a router for AI jobs, tested in a simulated replay on real Utah grid data and a real GPU-cluster trace."

### 2. Utah's grid has a rush hour

- **Message:** As solar fades, Utah's net load peaks in the evening; the clean hours aren't the rush hours.
- **Visual:** the Story 1 load chart (demand, net load and solar, with the carbon ribbon); the 7–10 PM rush band marked.
- **Number:** net-load peak at 8 PM, 6,654 MW (July 2025 weekdays, validation year, observed).
- **Speaker note:** "This is PACE, the balancing area serving much of Utah. Picture a hypothetical 2,300-GPU cluster here. Our objective is emissions first, with the same work done by the same deadlines."

### 3. How it works

- **Message:** Forecast tomorrow, route each job, replay the year, and count every kilowatt-hour.
- **Visual:** a five-box pipeline:
  1. EIA-930 hourly data, plus the Acme GPU trace;
  2. the 10 AM day-ahead forecast, using only published data;
  3. the router (stay, wait or move; finite GPUs; transfer cost);
  4. the exact gang-job replay;
  5. labelled results and the dashboard.

  Under the pipeline, a "sealed test year, opened once" lock icon.
- **Speaker note:** "Every number carries a label: observed, measured, modeled, forecast, assumed or simulated. The test year stayed sealed until the configuration was frozen."

### 4. One job: stay, wait or move

- **Message:** For a big training job, waiting buys almost nothing; moving changes everything.
- **Visual:** the Story 3 options table for job 5930563#c3 (72 GPUs, 104 h).
- **Number:** 2,728 kg stay vs 336 kg in the Northwest (one validation-year job; modeled and simulated).
- **Speaker note:** "Six hours of allowed delay is nothing against a 104-hour run. Moving means placing an unstarted job at another site; nothing migrates mid-run. The job was chosen by a rule fixed before its outcome was seen."

### 5. Moving beats waiting

- **Message:** About 22.5% vs under 1% on validation. On the sealed test year: {{TEST: S saving vs U, %}} vs {{TEST: best wait-only saving vs U, %}}.
- **Visual:** the Story 5 interval chart on the test window, showing S's own estimate and interval as the hero: **{{TEST: S saving vs U, % [95% interval]}}**.
- **Caption beside the hero:** *Validation: 22.6% → about 3% if only jobs of ≤8 GPUs may move.*
- **Footer:** "Simulated replay · attributed (EIA consumption-basis) emissions, not avoided emissions · deadlines met by construction (baseline bookings) · exact declared runtimes; runtime uncertainty untested."
- **Speaker note:** "Compute follows cleaner power, mostly to Northwest hydro. We found no demonstrated aggregate benefit from dynamic search in this replay; the simple fixed ranking is the one to deploy."
- No "30×" anywhere.

### 6. The condition: can the big jobs move?

- **Message:** The saving lives in a few large jobs. If they can't move, most of it goes.
- **Visual:**
  - left: the "largest jobs" table (top 1% of jobs = 94% of energy);
  - right: a horizontal bar pair for S on validation: 22.6% when all flexible jobs may move, 3.2% [2.1–4.5] when only jobs of ≤8 GPUs may.
- **Speaker note:** "Mobility is assumed, not measured, and it's the number that decides the result. With a two-hour transfer it's about 20%, with double the spare capacity 35%. These are validation scenario estimates."

### 7. Move what you can, store for what you can't

- **Message:** Once you know what can't move, you know the Utah load that storage could serve.
- **Visual:** the Story 6 storage beat:
  - the Utah day strip with the charge and discharge windows;
  - bars for the cluster's rush-hour import, before and after;
  - the break-even line (charging intensity ÷ η < displaced intensity).
- **Numbers:**
  - {{STORAGE: Utah rush-hour import, MW before → after}};
  - {{STORAGE: CO₂ change, %, fixed schedule, η 0.85}};
  - {{STORAGE: charging rebound, MW}};
  - {{STORAGE: destination load increase, MW}}.
- **Speaker note:** "This is an illustrative hourly model on validation-year data, with simulated dispatch and an assumed efficiency. Losses can erase the carbon gain, and we show that. Fast buffering on a scale of seconds is outside the model; that's the interface to build with Torus."

### 8. What an operator does tomorrow

- **Message:** First identify what work can move. Then quantify the residual Utah load storage could serve.
- **Visual:** three steps with icons:
  1. tag movable jobs;
  2. rank sites with a fixed clean-region list;
  3. size storage for the residual Utah load.

  Below, a short "Limits" line and a "Next" line.
- **Limits:** simulated replay; mobility assumed; no reservation-free or runtime-overrun test; cost not evaluated.
- **Next:**
  - measure which real jobs can move, with an operator;
  - couple the router to storage dispatch;
  - add seconds-scale buffering with Torus.
- **Speaker note:** close on the bold line, then "Thank you."

---

### Appendix (for Q&A, not presented)

- **A1. Does it hold?** The validation scenario table (phases, transfer, delay, capacity, mobility, production basis). It is labelled "scenario estimates, not a confidence interval".
- **A2. Water, illustrative.**
  - Generation-associated water, with and without hydro evaporation, plus the LBNL direct-cooling range: {{WATER: litres/MWh by region}}.
  - Caveats on the slide: consumption ≠ withdrawal; production-side weighting; PACE is not the Great Salt Lake watershed.
- **A3. The claim frame and the evidence labels.** The manifest's limitations, verbatim.
- **A4. Data sources and licences:**
  - EIA-930;
  - Acme trace (CC-BY-4.0);
  - Electricity Maps boundaries (AGPL-3.0);
  - Natural Earth.
