# Task 7 fix round 1 (lead rulings on the task review of 52d5bd8)

Work on s2/task-7. Fix everything below, then **re-run `make slice` from a clean tree** and commit the regenerated `results/*.json`, with the new policy table in the commit body. Run the full suite and push so PR #31 updates. Append a "Fix round 1" section to /tmp/claude-1001/-home-nvidia-workspace-personal-projects/d7fb1e5c-cee6-4473-88b2-02a108cc36ac/scratchpad/task-7-report.md.

1. **Fallback (F14.4, #1).** When `window == "fallback"`, always add "low-n" to the b = 8 labels. Export `h2` with `status: "not_evaluated"`, `direction` and `decided` null, and the reason "F14.4: the fallback makes no H2 decision statement". Keep the intervals as estimates. Unit-test `_contrast_record` and `_h2_record` with the fallback window.
2. **Limitations (F12.5, F12.7, #2).** Add these four limitation strings to the manifest, and make `check_claim_frame` require the first two:
   - "Zero deadline misses hold by construction under baseline bookings; they are not evidence of production reliability."
   - "The bookings' effect on realized savings is not signed."
   - "The shadow-U sensitivity ('possible without advance reservations') is pending."
   - "Only workload phase 0 is run; phases 49 and 98 are pending."
3. **Reproducibility (F12.6, #3).** Record:
   - a canonical hash per policy ledger (sorted by job_uid, over site, start_us, end_us);
   - sha256 of bookings, truth_fill, forecasts, climatology, balance and the trace parquet;
   - a canonical metrics hash (floats rounded to 1e-6, provenance_id and run_id stripped);
   - `snapshot_id` read from `data/manifests/snapshot.json`, with an assertion against the constant.

   Write `config.json` into the run dir. Record the forecast run by both path and the sha256 of its `forecasts.parquet`.
4. **F14.7 (#4). Ruling:** keep the diagnostic in the run, since it is already done and cheap enough, and remove it from `not_before_18`.
   - Record diagnosed and undiagnosed timing for at least one policy.
   - Assert that the G ledger is identical with and without `diagnose_blocked` (a canonical-hash equality).
5. **Framing (#5).** Replace `framing.placement_vs_timing` with: "Validation: no dynamic carbon search improves on the static clean-region ranking S (H3 not supported); K emits more than S (interval excludes zero); W and L are not distinguishable from S. Waiting in Utah alone saves about 0.7%; the saving comes from moving work, mostly to BPAT."
   - Fill the numbers from the run.
   - No advocacy phrases.
   - Add one line: "Per-job greedy search, including hindsight H, is not a cohort optimum; holding scarce BPAT slots for cleaner hours pushes later jobs to dirtier sites."
6. **Labels (#6).**
   - (a) Transfer and policy energy are `simulated` everywhere, including the headline wording ("simulated transfer energy").
   - (b) The stratum energy share is `simulated`.
   - (c) Hour counts in truth_fill (tier counts, missing) are `measured`.
   - (d) `n_weeks` is `measured`.
7. **S ranking (#7).** Keep it `observed`. Add provenance text: "means of EIA's published consumption-basis hourly CO₂ intensity, 2022-01-01 to 2024-10-29".
8. **Persist the eligible set (#8).** Write `illustrative_candidates.parquet` (job_uid, gpu_h, per-site earliest feasible start) into the run dir and hash it.
9. **Illustrative job (#9, decision D-054).** Register "illustration criterion v2", the GPU-hour-weighted median:
   - over the same eligible set, sort by (declared GPU-h, job_uid);
   - take the first job where cumulative declared GPU-h ≥ 50% of the set's total.

   Export it as `illustrative_job`. Keep the literal-rule job as `illustrative_job_literal`. Include the reviewer's disclosure text verbatim, with the numbers filled in.
10. **Seal walkers (#10).**
    - The committed-artifact tests fail, rather than skip, when `results/` is tracked but missing.
    - Scan date substrings inside strings, with an allowlist of seal-description fields.
    - The exemption covers only the exact key `wallclock_generated_at`.
11. **Lazy scan (#11).** `s_ranking()` uses a lazy scan with the training filter. Hash `CARBON_PATH` as it is today; the file is already truncated pre-seal per Task 1.
12. **Timing (#12).**
    - Add `wallclock_written_at` to `cohort.json`, and put its sha256 into the manifest.
    - Write `timing.json` after export, including export time.
13. **Robustness (#13).**
    - `forecast_replay` takes issues per model.
    - A week with no issues raises a clear error.
    - The copy into `results/` stages all four files and then renames them.
    - `bound_gap` checks that the set of jobs per policy equals the ledger's set.
14. **Dead code (#14).** Remove the unreachable Task-5 fallback branches.
15. **Rounding (#15).** Make the 1.25× home capacity rounding explicit: round half up to an 8-GPU node, giving 2,864.
16. **Report (#16).** Note that run 095903Z's recorded SHA (67dbd53) is the pre-rebase SHA.
17. **Busy series (#17).** Include warm-up occupancy in `mean_busy_gpus_by_hour`, or label the series "cohort only" in the export. Prefer including it.
