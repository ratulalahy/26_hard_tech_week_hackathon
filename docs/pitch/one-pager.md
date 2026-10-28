# GridPilot: compute follows cleaner power

*Torus bounty, Hard Tech Week 2026: Energy × AI infrastructure. Results from a sealed test year (358 days, Nov 1 2025 – Oct 24 2026), opened once after a tagged configuration freeze; "validation" means Nov 2024 – Oct 2025. Every number cites its source in `docs/pitch/numbers.md`.*

## Problem

An AI cluster in Utah draws power around the clock on PACE, the balancing area serving much of Utah. That grid has an evening rush: as solar fades, net load climbs to its peak around 8 PM, averaging about 6,200 MW at 8 PM over July 2026 weekdays (6,654 MW over July 2025 weekdays, validation). <!-- results/test/grid-profile.json pace_july_weekday.net_load_mw[20] 6182; results/grid-profile.json same field 6654 --> In nine of ten US regions we profiled, the rush hours are dirtier than average (validation). <!-- results/overview.json regions.*.alignment.rush_verdict --> Utah is also far more carbon-intensive than its neighbours. An operator can change two things: **when** a job runs and **where** it runs. Which matters, and by how much?

## Approach

- **A day-ahead traffic report.** Each morning, three forecasts predict tomorrow's hourly carbon intensity in Utah and at three destinations, under assumed EIA publication delays (2 h demand, 48 h wind and solar, 96 h carbon). <!-- results/overview.json forecast_issues.envelope_h {demand 2, wind 48, solar 48, ci_consumed 96}; spec §5 -->
- **A router.** It places each AI job in Utah, California, the Northwest (Bonneville) or Nevada, at a feasible start time. Every site has finite spare GPUs, and every move pays a transfer delay and transfer energy.
- **A simulated replay.** A public, measured GPU-cluster trace (Acme, Seren cluster; 888,224 jobs on the test year) is replayed against hourly EIA data. An exact gang-job simulator runs U (stay in Utah) and eight alternatives, one of them a hindsight diagnostic, on identical work. <!-- results/test/metrics.json cohort.n_jobs -->
- **A sealed test year,** opened once after a tagged configuration freeze, through a logged entry point (69 logged reads). <!-- results/test_reads.jsonl -->
- **How it was built.** AI agents helped build and review it. We froze the configuration before opening the holdout once; the routing policy remains a fixed ranking.

## Key findings

| | Test year (sealed, opened once) | Validation |
|---|---|---|
| Fixed clean-region ranking (S) vs stay in Utah | **22.3% [17.3, 27.2]** less attributed CO₂ | 22.6% [18.4, 26.8] |
| Waiting in Utah alone | under 1% (0.8%) | 0.7% |
| **Mobility caveat:** only jobs of ≤ 8 GPUs may move | **3.2% [1.9, 4.7]** (forecast policies, which can also wait: 3.9%) | 3.2% [2.1, 4.5] |
| Forecast-based search (K, W, L) vs S | no demonstrated aggregate benefit; K emits 9.9 t more [+0.8, +19.5] | the same; K +10.0 t |

<!-- results/test/metrics.json and results/metrics.json contrasts[S/U].blocks["4"].saving, .saving_ci95; contrasts[W_time/U], [L_time/U]; results/test/extras.json extensions.mobility_le_8gpus.vs_U.{S,W}["4"]; results/extensions.json sensitivities.mobility_le_8gpus.policies.S.vs_U["4"]; results/test/metrics.json framing.placement_vs_timing -->

- **Compute follows cleaner power,** mostly to Northwest hydro: 70% of the energy S ran outside Utah ran in Bonneville (69% on validation). <!-- derived: policies.S.metrics.execution_kwh_by_site BPAT / (BPAT + CISO + NEVP), 0.705 test, 0.690 validation -->
- **A few big jobs carry it.** The largest 1% of jobs use 95% of the energy (94% on validation), so whether they can move is the lever. <!-- workload.top_1pct_jobs_by_declared_gpu_h.energy_share 0.9452 / 0.9409 -->
- **It holds under other one-axis changes:** 19.9–23.3% on the test year with a 2-hour transfer, a 24-hour delay or a shifted workload; 35% with twice the spare capacity. Scenario estimates, not a confidence interval. <!-- results/test/extras.json extensions.{transfer_120min,batch_delay_24h,phase_49,phase_98,dest_slots_1024}.vs_U.*["4"] -->
- **Forecasts:** better than a seasonal average by 10–23% at the destinations, but not reliably in Utah (validation). The router doesn't need them: the fixed ranking is the baseline to pilot. <!-- results/outlook.json skill_by_horizon -->
- **Storage is a partial complement for what can't move: aim it at carbon or at the rush, not both.** An illustrative 4 MWh / 1 MW battery at the Utah site (η 0.85, assumed), on fixed schedules registered before the opening:
  - aimed at carbon, it cuts the cluster's attributed CO₂ by about 4.0% (validation 3.5%), but adds about 107 t on a flat marginal basis;
  - aimed at the rush (Utah's 14 tightest test-year hours), it cuts the cluster's average rush-hour draw from 0.88 to 0.32 MW, but CO₂ by only 1.0%;
  - neither lowers the site's yearly peak draw, which charging pushes from 1.64 to the 1.65 MW connection.
  <!-- results/test/extras.json storage.schedule_comparison.schedules.{carbon,peak}.cases.U["4"].cut_frac 0.0395 / 0.0097, .flat_marginal_cut_t −107.1, .rush_import_before_mw 0.879, .rush_import_after_mw 0.317 (peak), .peak_import_before_mw 1.639, .peak_import_after_mw 1.647; storage.rush.n_hours 14 -->
- **Cost, as a wholesale scenario (validation):** moving costs $16–22k more a year (+7–9%) at real-time wholesale prices, about $21 per attributed tonne for S. Data centers pay retail; this is not a bill. <!-- results/prices.json california_node.range.{S,W,L}.delta_vs_U_usd, .delta_vs_U_frac; policies.S.cost_per_attributed_tonne_usd_t 21.2 -->

## What's unique

- It puts the two levers side by side, place and time, on the same work. The insight is which lever matters and what it depends on, not a fancier model.
- An exact gang-job simulator with site capacity and transfer costs, and the stay-in-Utah slot kept as every job's fallback.
- A sealed test year with a logged opening, and pre-registered extras reported whatever they showed, including the ones that weakened our claims.
- Every number is labelled observed, measured, modeled, forecast, assumed or simulated, and traces to a run.
- An offline dashboard, from Utah's evening rush to one job's choice to the whole test year.

## Limits, stated plainly

- A **simulated replay**, not a live deployment, on a revised EIA snapshot; real-time data vintages are not reconstructed, and the publication delays are assumptions.
- **Attributed (EIA consumption-basis) emissions, not avoided emissions.**
- Deadlines are **met by construction (baseline bookings)**, with **exact declared runtimes; runtime uncertainty is untested.**
- **Mobility is assumed**, and it decides the result.
- The test year covers 358 days. Arrivals after Oct 15, 2026, 23:04 UTC (8,003 jobs, 3.1% of GPU-hours) are excluded so every job's deadline falls before the cutoff; the same jobs are excluded for every policy (validation: 1,203 jobs, 3.9%). <!-- results/test/metrics.json cohort.n_excluded, cohort.excluded_gpu_h, covered.arrivals[1]; results/metrics.json cohort.n_excluded -->
- Storage is an hourly illustration: missing wind or solar hours count as zero in net load, and there is no degradation, capex or fast buffering.
- The version without advance reservations, and the runtime-overrun stress test, were not run.
- The intervals are conditional on this one replay.

## Next steps

- **With an operator:** measure which real jobs can move (checkpointing, data size, residency).
- **The two missing tests:** run without advance reservations, and with runtime overruns.
- **What we'd want to test with a storage partner such as Torus:** coupling the router's residual Utah load to storage dispatch, and the seconds-scale buffering that our hourly model leaves out.

**First identify what work can move. Then size storage for the Utah load that can't, aimed at carbon or at the rush.**
