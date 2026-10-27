# Stage 3 · T10: scenarios, windows and the owner-selected extensions (validation only)

Branch `s3/t10` from main after T9 merges. The hard stop is Tue 21:00 MT: anything unfinished is exported as `not_run` with a reason (F9, D-058). Validation only; the seal holds.

## Part A: refactor (lands first; T11 builds on it)
- **Pipeline function.** Turn `run_slice.run(args)` into a pure function `run_pipeline(window: Window, scenario: Scenario, out_dir, *, export: bool) -> RunResult`.
  - `Window` is a frozen dataclass: init, eval_start, F, name. Only `validation` and `fallback` are constructible here. Test mode is T11's job: a `Window.test(...)` that raises `NotImplementedError("T11")`.
  - `Scenario` is a frozen dataclass: name, plus the knobs below, defaulting to primary.
  - The CLI calls the function. Behaviour and outputs for the primary run must not change: the canonical metrics hash stays equal to the registered `f45821c0…`. Add a test asserting that `Scenario.primary()` reproduces the registered config fields.
- **Scenario knobs** (spec §7; F14.1 says which of them change U and therefore A):
  - `dest_slots` (default 512 per destination);
  - `transfer_s` (1,800);
  - `batch_delay_s` (21,600 for Pretrain/SFT/MLLM; Eval stays 3,600);
  - `mobility_max_gpus` (None = no limit);
  - `phase_days` (0, 49 or 98).
- **Cohort A** stays the common F14.1 A for phase 0. Phases 49 and 98 get their own A (F14.1). A sensitivity scenario never changes the registered primary results.

## Part B: extensions, validation (D-058)
Run each as its own run directory under `runs/ext/<name>/<UTC>/`, in parallel where memory allows (the DGX has 128 GB). Policies per run are U, S, K, W, L, plus W and L time-only where the scenario has destinations.

1. **Production-basis repricing.** Reprice the *same* registered ledgers on EIA production-basis CI (`ci_generated_g_kwh`, filled by the same F14.6 tiers with production as tier 1). No re-simulation. Report each policy's saving vs U on both bases side by side.
2. **Common support (F14.6).** Restrict every policy to the jobs whose charged hours touch only tier-1 hours under every policy, using `common_support`. Recompute the savings and intervals on that cohort, and report its size and its energy share.
3. **Phases 49 and 98.** Run the full primary scenario at those workload alignments and report the savings per phase. Never pool the phases (§9).
4. **Sensitivities:** destination capacity 0 and 1,024 per site; transfer time 120 min; batch delay 24 h; mobility limited to jobs of 8 GPUs or fewer. Report the S, K, W and L savings vs U with intervals, the moved share, and the late count (it must stay 0).

## Export
- `results/extensions.json`, every number enveloped:
  - repricing and common support are `simulated`;
  - the scenario knobs are `assumed`.
- Each block carries its scenario definition, the run id and the canonical hashes.
- Cut items appear as `{status: "not_run", reason: "cut by owner (D-058)"}`: shadow-U, missingness-blind, and the remaining §7 sensitivities.
- Update `manifest.not_run` accordingly.
- Extend `test_every_number_enveloped` and `test_no_sealed_dates` to cover the new file.

## Dashboard
- Story 6 "Challenge it" and the Method drawer show the extensions as a compact table: scenario, and the S/W/L saving with its interval. Also show the production-basis and common-support comparison.
- Plain language, with the evidence chips.
- Shoot screenshots at 1728 and 1440. axe must stay at 0 violations and the offline test must pass.
- **Determinism (T9 finding):** replace every non-deterministic float aggregation feeding exports (e.g. run_slice.py:525 `group_by(site).agg(sum)`) with `math.fsum` over values sorted by job_uid. Change the canonical metrics hash to round floats to 10 significant digits. Add a test that 5 repeated aggregations give identical floats.
- **UI nit from T9:** in the Control room interval chart, the wait-only dots (0.7%) overlap their row labels. Give the chart's plot area a left inset, or move the labels.
