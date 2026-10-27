# Stage 3 · T9: pre-freeze copy, label and export fixes

Branch `s3/t9` from main. Use TDD where there is logic. Run `make test`, `make web`, the offline test and axe. Then re-run `make slice` from a clean tree (about 20 min), so the regenerated `results/*.json` carry the fixed strings and labels, and re-run `make profile` and copy-data against the **new** run directory.

The new run directory is created in your worktree. Record its path in your report; the lead preserves it.

## Exports (lab)
- **A7.** Drop the `observed` alias keys from `forecast-replay` (`$.observed` and `$.history_to_first_cutoff.observed`). The UI reads `truth`.
- **A8.** `eia_co2`: make the sidecar `evidence` "modeled" and fix the docstring ("EIA's estimated consumption- and production-basis hourly CO₂ intensity: modeled"). Rebuild the sidecar with `build_carbon()`. The parquet must come out frame-identical; assert it.
- **A9.** One `top_share()` helper using ceil, shared by `run_slice` and `workload_profile`, so both say 9,180.
- **A11.** `headline_wording` says "(EIA consumption basis, modeled)".
- **A13 (partial).** Rename the manifest key `not_before_18` to `not_run`, with a reason for each item, and remove `task5_status`. T10 will fill in what actually runs. Until then, list the D-058 cut items with the reason "cut by owner (D-058)".
- **C4.** Framing uses "K − S = +10.0 t" (no double negative).
- **C5.** `accounting.EVIDENCE` and `influence()` label CO₂ outputs `simulated`.
- **A6 (new limitation, required by `check_claim_frame`).** "Validation results are development evidence: the validation year was profiled before the design, and the same period selected the learned model's settings. The sealed test year is the confirmatory evaluation."

## Dashboard (web)
- **A4.** Deadline text, in the drawer and wherever else it appears: "A job's deadline is the later of (a) its run-now finish plus its allowed delay and (b) its finish in the stay-in-Utah baseline (baseline-relative)."
- **A5. Headlines carry the simulated frame and the F12.5 qualifiers.**
  - Control room H1: "In a simulated replay, moving Utah's AI jobs cut their CO₂ by a fifth. Waiting barely helps."
  - Under the hero, one 12 px line: "Replay of a measured GPU-cluster trace mapped onto Utah · deadlines relative to the baseline, met by construction · exact declared runtimes; runtime uncertainty untested."
  - Replace "every deadline met" and "deadlines met" everywhere with "deadlines met by construction (baseline bookings)".
  - In the cockpit and Story 5, use the same qualifier line.
- **A6.** One plain-language line in the drawer and in Story 6: "These are validation-year results, which shaped the design; the sealed test year is the real test."
- **A10.**
  - The planner prices transfer energy half at Utah's intensity and half at the destination's, at the arrival hour.
  - Fix the copy that says "5% extra energy in Utah".
  - In `filled()`, use the previous non-null value, never 0.
- **A12.** The bound text: "ignores competition between jobs for capacity (each job's own limits still apply)".
- **C6.** The Story count-median duration is read from `illustrative_job_literal`. Fix the comments that call EIA intensity "observed".
- **C7.** The ErrorState gets no evidence chip.
- **C8.** The load label uses the data's month.

## Tests and docs
- **A16.** Add a lab test asserting `web/public/data/results/*.json` is byte-identical to `results/*.json` for every file present in both.
- **A17.** AGENTS.md: document that `make profile` needs `RUN_DIR=` (with an example path), and that `make web` installs dependencies.
- **A14.** Make one module `gridpilot.sim.power` the single source for GPU_KW, PUE and TRANSFER_FRACTION, imported by carbon_search, accounting and run_slice. Add a test that the constants match the manifest's.

## Report
Write `/tmp/claude-1001/-home-nvidia-workspace-personal-projects/d7fb1e5c-cee6-4473-88b2-02a108cc36ac/scratchpad/s3-t9-report.md`. Include the new run id, a check that the canonical metrics hash is unchanged (the numbers must not move), screenshots of the changed views at 1728, and the test, axe and offline results.
