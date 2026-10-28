# GridPilot: deck outline

**Status:** post-test rewrite, Tue 2026-10-27 night. Every number is from committed JSON and is on the numbers card, `docs/pitch/numbers.md`; each cites its JSON path in a comment here.

- The live demo is the spine (`narrative.md`). The deck backs it up, or replaces it if WebGL or the laptop fails; it follows the same six beats.
- Eight slides plus an appendix, in the narrative's beat order: slide 2 is Beat 1, 3 Beat 2, 4–5 Beat 3, 6 Beat 4, 7 Beat 5, 8 Beat 6. Built as `docs/pitch/deck/index.html` (`make deck`).
- Visuals: dashboard screenshots in `docs/design/shots-build/`, **all in the test-year window**. Test shots exist for the Control room, `#story-3`, `#story-4`, `#story-5`, the ribbon and two drawer sections (`test-*.png`). `#story-1` and `#story-2` still need test-window shots; the existing `story-1`/`story-2` shots are validation (July 2025, job #c3) and must not be used with test numbers (audit F3).

---

### 1. Title

- **Title:** GridPilot: compute follows cleaner power
- **Message:** When and where should a Utah AI job run? We measured which lever matters.
- **Visual:** the Control room in the test window (`test-control-1728.png`): the map, the Utah-to-Northwest arc and the rush strip.
- **Speaker note:** "GridPilot is a day-ahead traffic report for the grid, plus a router for AI jobs, tested in a simulated replay on real Utah grid data and a real GPU-cluster trace."

### 2. Utah's grid has a rush hour

- **Message:** As solar fades, Utah's net load peaks in the evening; the clean hours aren't the rush hours.
- **Visual:** the Story 1 load chart in the test window (to shoot), the evening rush band marked: 7–11 PM on the test year (the hours holding at least 10 of the year's 100 highest net-load hours, as the dashboard draws it); the validation year's band was 7–10 PM.
- **Number:** net-load peak at 8 PM, **6,182 MW** (mean of July 2026 weekdays, test year, observed). <!-- results/test/grid-profile.json pace_july_weekday.net_load_mw[20] -->
- **Small print:** "In nine of ten US regions the rush hours are dirtier than average; Bonneville's are cleaner (validation year)." <!-- results/overview.json regions.*.alignment.rush_verdict, regions.BPAT.alignment.rush_vs_mean_pct −8.0 -->
- **Speaker note:** "This is PACE, the balancing area serving much of Utah. Picture a hypothetical 2,300-GPU cluster here. Our goal is emissions first, with the same work done by the same deadlines."

### 3. One job: stay, wait or move

- **Message:** For a big training job, waiting buys almost nothing; moving changes everything.
- **Visual:** the Story 2 options table in the test window (to shoot): job 5930563#c5 (72 GPUs, 104 h).
- **Number:** **2,098 kg** if it stays vs **362 kg** in the Northwest (one test-year job; option CO₂ modeled, placements simulated). <!-- results/test/job-replay.json illustrative_job.available_actions[*].co2_kg -->
- **Speaker note:** "Six hours of allowed delay is nothing against a 104-hour run. Moving means placing a job before it starts at another site; nothing migrates mid-run. The job was chosen by a rule fixed before its outcome was seen."

### 4. How it works

- **Spoken with:** the opening of Beat 3 (1:14), right after the one job, so the slide order follows the spoken order (deck fix r1, M2). Narrative timings are unchanged.
- **Message:** Forecast tomorrow, route each job, replay the year, count every kilowatt-hour.
- **Visual:** a five-box pipeline:
  1. EIA-930 hourly data, plus the Acme GPU trace;
  2. the 10 AM day-ahead forecast, using only data published under assumed EIA delays (2 h demand, 48 h wind and solar, 96 h carbon);
  3. the router (stay, wait or move; finite GPUs; transfer cost);
  4. the exact gang-job replay;
  5. labelled results and the dashboard.

  Under the pipeline, a lock icon: "sealed test year: 358 days, opened once after a tagged freeze; 69 logged reads". <!-- results/test/manifest.json split.eval_start, split.F (358 days, D-074); results/test_reads.jsonl -->
- **Method line on the slide (verbatim):** "AI agents helped build and review it. We froze the configuration before opening the holdout once; the routing policy remains a fixed ranking."
- **Speaker note:** "Every number carries a label: observed, measured, modeled, forecast, assumed or simulated. The test year stayed sealed until the configuration was frozen; only completeness counts were taken before." (audit F1)

### 5. Moving beats waiting

- **Message:** On the sealed test year, the fixed ranking cut attributed CO₂ by 22.3%; waiting in Utah alone, under 1%.
- **Visual:** the Story 3 interval chart (`test-story-3-1728.png`), S's own estimate and interval as the hero: **22.3% [17.3, 27.2]**, with "validation 22.6%" beside it. <!-- results/test/metrics.json contrasts[S/U].blocks["4"].saving, .saving_ci95; results/metrics.json contrasts[S/U].blocks["4"].saving -->
- **Caption beside the hero (visible with it):** *If only jobs of ≤ 8 GPUs may move: 3.2% [1.9, 4.7] (test; validation 3.2%).* <!-- results/test/extras.json extensions.mobility_le_8gpus.vs_U.S["4"]; results/extensions.json sensitivities.mobility_le_8gpus.policies.S.vs_U["4"] -->
- **Footer:** "Simulated replay · 358 days · attributed (EIA consumption-basis) emissions, not avoided · deadlines met by construction (baseline bookings) · exact declared runtimes; runtime uncertainty untested."
- **Speaker note:** "Compute follows cleaner power: 70% of the work that left Utah ran in the Northwest. Forecast-based search showed no demonstrated aggregate routing benefit over the fixed ranking in this replay, so the fixed ranking is the baseline to pilot." <!-- derived: results/test/metrics.json policies.S.metrics.execution_kwh_by_site BPAT share 0.705; framing.placement_vs_timing -->
- No "30×", no "deploy", no "simple rules beat AI".

### 6. The condition: can the big jobs move?

- **Message:** The saving lives in a few large jobs. If they can't move, most of it goes.
- **Visual:**
  - left: "the largest 1% of jobs use 95% of the energy" (test; 94% on validation); <!-- workload.top_1pct_jobs_by_declared_gpu_h.energy_share -->
  - right: a horizontal bar pair for S on the test year: 22.3% when all flexible jobs may move, **3.2% [1.9, 4.7]** when only jobs of ≤ 8 GPUs may (W 3.9%); validation bars in grey beside them (22.6%, 3.2%).
- **Speaker note:** "Mobility is assumed, not measured, and it decides the result. Other changes move it much less: a two-hour transfer gives about 20%, double the spare capacity 35%, on both years. These are scenario estimates." <!-- results/test/extras.json extensions.transfer_120min.vs_U.S["4"] 0.1995, extensions.dest_slots_1024.vs_U.S["4"] 0.3487 -->

### 7. Move what you can, store for what you can't

- **Message:** Aim the battery at carbon or at the rush, not both.
- **Visual:** the Story 5 two-schedule table (`test-story-5-1728.png`).
- **Numbers (test year; 4 MWh / 1 MW, η 0.85 assumed; both schedules registered before the opening):** <!-- results/test/extras.json storage.schedule_comparison.schedules.{carbon,peak}.cases.U["4"]; storage.rush.n_hours -->
  - carbon schedule: CO₂ **−4.0%**, but **+107 t** on a flat marginal basis; rush draw 0.88 → 0.55 MW (6 of 14 rush hours);
  - peak-aimed schedule: rush draw **0.88 → 0.32 MW** (10 of 14), but CO₂ only **−1.0%**;
  - both: the site's yearly peak draw goes 1.64 → **1.65 MW** (charging fills the connection);
  - moving the router's work also adds 0.20 MW in Bonneville and 0.04 MW in California during Utah's rush. <!-- storage.peak_relief.S.{BPAT,CISO}.rush_change_vs_U_mw -->
- **Speaker note:** "An illustrative hourly model with simulated dispatch and an assumed efficiency. On validation the carbon schedule cut 3.5% and barely touched the rush. Fast buffering on a scale of seconds is outside the model; that's the interface we'd want to test with a storage partner." <!-- results/extras-validation.json storage_peak.schedules.carbon.cases.U["4"] -->

### 8. What an operator does tomorrow

- **Message:** First identify what work can move. Then size storage for the Utah load that can't, aimed at carbon or at the rush.
- **Visual:** three steps with icons:
  1. tag movable jobs;
  2. pilot the fixed clean-region ranking as the baseline;
  3. size storage for the residual Utah load (0.83 MW in the rush if only ≤ 8-GPU jobs move). <!-- results/test/extras.json storage.schedule_comparison.schedules.carbon.cases.mobility_le_8gpus_W["4"].rush_import_before_mw -->

  Below, a short "Limits" line and a "Next" line.
- **Limits:** simulated replay; mobility assumed; no reservation-free or runtime-overrun test; cost only as a wholesale scenario (validation: +7–9%, about $21 per attributed tonne). <!-- results/prices.json california_node.range.*.delta_vs_U_frac; policies.S.cost_per_attributed_tonne_usd_t -->
- **Next:**
  - measure which real jobs can move, with an operator;
  - couple the router's residual Utah load to storage dispatch;
  - what we'd want to test with a storage partner: seconds-scale buffering on measured cluster power.
- **Speaker note:** close on the bold line, then "Thank you."

---

### Appendix (for Q&A, not presented)

- **A1. Does it hold?** The validation → test drift table for the scenarios (`test-method-drift-1728.png` or a table): phases 49/98, 2 h transfer, 24 h delay, capacity 0 and 1,024, mobility ≤ 8 GPUs, each test beside validation. Production-basis repricing (25.5%) and observed-hours-only scoring (22.5%) are validation-only rows. Labelled "scenario estimates, not a confidence interval".
- **A2. Water, illustrative.** S vs U, generation-associated water: −18.6% without hydro evaporation, +174% with it (test); −20.5% / +145% (validation). No water-saving claim. Caveats: consumption ≠ withdrawal; production-side weighting; PACE is not the Great Salt Lake watershed. <!-- results/test/extras.json water.policies.S.change_vs_U.ex_hydro_frac, .with_hydro_frac; results/water.json policies.S.change_vs_U -->
- **A3. The claim frame and the limitations.** Show the manifest's claim frame verbatim and the limitations as the dashboard restates them, not the raw test-manifest list: two of its lines were written before the extras ran (audit F16). Replace "The shadow-U sensitivity … is pending" with "shadow-U: cut (D-058)" and "phases 49 and 98 are pending" with "phases 49 and 98: run as pre-registered secondary scenarios (`results/test/extras.json`)", with a footnote that the results file is frozen and these two lines are errata.
- **A4. The seal.** One opening at 19:22 MT on Oct 27 (2026-10-28T01:22:53Z), tag `config-freeze`, 69 logged reads; the disclosures: counts-only completeness checks (D-052, D-074), a blocked early attempt (D-060), the column names and node list of one post-seal price file printed with no values (D-072), and an empty `data/.wtest` file created and deleted by a reviewer, changing only the directory's mtime (D-074). The excluded tail: 8,003 jobs (3.1% of GPU-hours), the same for every policy (validation: 1,203, 3.9%).
- **A5. Data sources and licences:**
  - EIA-930 and EIA hourly CO₂ estimates;
  - Acme trace (CC-BY-4.0);
  - Open-Meteo archived forecasts (toughest-days case study);
  - NREL and LBNL water factors;
  - CAISO/WEIM real-time LMPs (wholesale scenario);
  - Electricity Maps boundaries (AGPL-3.0);
  - Natural Earth.
