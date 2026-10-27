# Task 5 follow-up, fix round 1 (the reviewer approved; PR #29 merged as baddb55; these go in a NEW small PR off main)

Make a new branch `s2/task-5-fix` from main (baddb55). Run the full suite, commit, push, and open a PR titled "S2 Task 5 follow-up: tie tolerance, pinned climatology, bug-signal field".

1. **Tie tolerance (#1).** Use a relative tolerance `1e-9 + 1e-12·|kg|` for ties in `_best` and for the F14.7 strict-improvement test in `blocked()`.
2. **Pinned tail (#2).** `tail_climatology(run_dir=...)` loads the run's `climatology.parquet`; it does not refit. At construction, assert that the tail reproduces the run's K rows.
3. **Pinned run (#3).** `load_forecasts` and `tail_climatology` require an explicit `run_dir`. `latest_forecast_run()` may stay as a helper, but nothing calls it implicitly.
4. **Separate bug signal (#5).** Add a ledger column `fit_rejected` (bool) for the engine's F12.7 signal: a returned action that doesn't fit, so the job falls back. Keep `blocked` for F14.7 only.
   - `blocked` is False when not diagnosing. Document that.
   - Update `LEDGER_COLUMNS` and the tests.
   - Task 6's `score` reads `blocked`; check it still works, and make `score` also report `fit_rejected` counts.
5. **Duration (#8).** Price transfer with `job.duration_us / 1e6`.
6. **Docstring (#4).** Reword it to "no attribute path to the mutable Capacity".
7. **Ruling (#6).** S's "same site, earlier start" counts as an improvement under F14.7 (S's own objective is the earliest on-time start at the first ranked site that has one). Keep it, and state this in the docstring.

Append a "Fix round 1" section to /tmp/claude-1001/-home-nvidia-workspace-personal-projects/d7fb1e5c-cee6-4473-88b2-02a108cc36ac/scratchpad/task-5-report.md.
