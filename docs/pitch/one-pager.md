# GridPilot: compute follows cleaner power

*Torus bounty, Hard Tech Week 2026: Energy × AI infrastructure. DRAFT, 2026-10-27. `{{TEST: ...}}` marks a sealed test-year number that will be filled after the audit; any number marked "validation" comes from the validation year, Nov 2024 – Oct 2025.*

## Problem

An AI cluster in Utah draws power around the clock on PACE, the balancing area serving much of Utah. That grid has an evening rush: as solar fades, net load climbs to its peak around 8 PM (6,654 MW on a July 2025 weekday, validation year). It is also far more carbon-intensive than its neighbours. An operator can change two things: **when** a job runs and **where** it runs. Which of those matters, and by how much?

## Approach

- **A day-ahead traffic report.** Each morning, three forecasts predict tomorrow's hourly carbon intensity in Utah. They use only data EIA would already have published.
- **A router.** It places each AI job in Utah, in California, in the Northwest (Bonneville) or in Nevada, at a feasible start time. Every site has finite spare GPUs, and every move pays a transfer delay and transfer energy.
- **A simulated replay.** We replay a public, measured GPU-cluster trace (Acme, Seren cluster: {{TEST: cohort size, jobs}} jobs) against hourly EIA data. An exact gang-job simulator runs U (stay in Utah) and eight alternatives, one of them a hindsight diagnostic, on identical work.
- **A sealed test year,** opened once after a recorded configuration freeze.

## Key findings

| | Validation | Test year (sealed, opened once) |
|---|---|---|
| Fixed clean-region ranking (S) vs stay in Utah | about **22.5% vs under 1%** for waiting alone; S: 22.6% [18.4–26.8] | S: {{TEST: S saving vs U, % [95% interval]}} |
| Waiting in Utah alone | 0.7% | {{TEST: best wait-only saving vs U, % [95% interval]}} |
| **Mobility caveat (beside the headline)** | **22.6% → about 3%** if only jobs of ≤8 GPUs may move | not rerun on the test year |
| Dynamic search (K, W, L) vs S | no demonstrated aggregate benefit | {{TEST: K, W, L minus S, t [95% interval]}} |

- **Compute follows cleaner power,** mostly to Northwest hydro: 69% of S's remote execution energy ran there in validation; in the test year it was {{TEST: BPAT share of S's remote energy, %}}.
- **A few big jobs carry it.** The largest 1% of jobs use 94% of the energy.
- **Storage covers what can't move.** For the residual Utah load, an illustrative store of {{STORAGE: E MWh / P MW}} changes the cluster's attributed CO₂ by {{STORAGE: %, fixed schedule, η 0.85}}. It changes the cluster's Utah rush-hour import from {{STORAGE: MW before}} to {{STORAGE: MW after}}, with a charging rebound of {{STORAGE: MW}}. This is illustrative and on the validation year.

## What's unique

- It puts the two levers side by side, place and time, on the same work. The insight is which lever matters, not a fancier model.
- An exact gang-job simulator with site capacity and transfer costs, and the stay-in-Utah slot kept as every job's fallback.
- Forecasts that respect EIA's publication delays, and a sealed test year with logged reads.
- Every number is labelled observed, measured, modeled, forecast, assumed or simulated, and every one traces to a run.
- An offline dashboard, from Utah's evening rush to one job's choice to the whole year.

## Limits, stated plainly

- This is a **simulated replay**, not a live deployment.
- These are **attributed (EIA consumption-basis) emissions, not avoided emissions**.
- Deadlines are **met by construction (baseline bookings)**, with **exact declared runtimes; runtime uncertainty is untested**.
- **Mobility is assumed**, and it decides the result.
- The version without advance reservations, and the runtime-overrun stress test, were not run.
- Cost was not evaluated.
- The intervals are conditional on this one replay.

## Next steps

- **With an operator:** measure which real jobs can move (checkpointing, data size, residency).
- **The two missing tests:** run without advance reservations, and with runtime overruns.
- **With Torus:** couple the router's residual Utah load to storage dispatch, and add the seconds-scale buffering that our hourly model leaves out.

**First identify what work can move. Then quantify the residual Utah load storage could serve.**
