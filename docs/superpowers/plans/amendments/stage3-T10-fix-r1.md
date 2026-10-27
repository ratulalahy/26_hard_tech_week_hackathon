# Stage 3 · T10 fix round 1 (on the T10 review; spec ✅; fix everything)

Work on `s3/t10`. Then re-export `results/extensions.json` at the final, clean commit with `--repro-run` and record `export_git_clean`. Run the tests, axe and the offline test. Push.

- **I-1.**
  - `make extensions` takes `EXT_ROOT` from `RUN_DIR`, or makes it required.
  - The export **fails** when a scenario's run is missing unless `--allow-missing` is given.
  - Add a `REPRO_RUN` variable so `primary_reproduction` is never dropped.
  - Add a test that a missing run fails without `--allow-missing`.
- **I-2.**
  - Story 6's robustness span uses **consumption-basis checks only**; it should come out at 20.2–23.2%.
  - State the production basis separately, verbatim: "On production-basis carbon the cut is {lo}–{hi}%; production basis flatters hydro-heavy destinations."
- **M-1.** Leave `wallclock_generated_at` and `export_git_sha` out of the canonical hash.
- **M-2.** The canonical rule zeroes |x| < 1e-9, then rounds to 10 significant digits. Update the test.
- **M-3.** Record `export_git_clean`, and re-export at the final commit.
- **M-4.** Use fsum in `s_ranking` means and `excluded_gpu_h`.
- **M-5.** Use `math.isclose(rel_tol=1e-9)` in the consumption check.
- **M-6.** Add §7's civil-time (DST) alignment and the +25% runtime-overrun stress to `not_run`, with the reason "cut by owner (D-058): remaining §7 sensitivities".
  - **Lead ruling:** listing batch delay 0 h and transfer 0 min as cut under D-058 is correct; they are among "the remaining §7 sensitivities".
- **M-7.** `patch_manifest` updates the shadow-U limitation to say cut (D-058).
- **M-8.** Put a manifest note `common_support_rerun: see extensions.json#common_support`, and make `metrics.json`'s `status_rerun` point there. Regenerating `metrics.json` is **not** required; the manifest note is enough.
- **M-9.**
  - `make ext-runs` checks each PID's exit status.
  - Correct AGENTS.md: peak memory is about 3 GB per process.
- **M-10.** `Scenario.transform` reuses `cohort._batch_delay`.
- **M-11.** Name the production-basis fill order in the drawer sentence.
- **M-12.** `run_block` asserts `forecasts_sha256`, `snapshot_id` and `git_clean` against the registered run.
- **M-13.** Anchor the last tick to the end, so "30%" isn't clipped.
- **M-14 (lead ruling: do it; honesty over polish).** Add a 12 px line under the Control-room hero: "The cut depends on moving large multi-node jobs: if only jobs of 8 GPUs or fewer could move, it would be about 4%." Read the figure from `extensions.json` (the S–L range, rounded).

Append a "Fix round 1" section to `/tmp/claude-1001/-home-nvidia-workspace-personal-projects/d7fb1e5c-cee6-4473-88b2-02a108cc36ac/scratchpad/s3-t10-report.md`.
