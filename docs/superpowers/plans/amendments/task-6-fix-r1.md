# Task 6 fix round 1. The reviewer approved; fix these before Task 7 consumes the API.

Fix all of these on s2/task-6, run the full suite, commit, and push so PR #28 updates.

1. **Null tier (#1).** Raise if `tier` is null or outside 1–4 wherever `ci_g_kwh` is finite.
2. **Timezones (#2).** Require tz-aware datetimes (raise on naive) in `support_check`, `denver_weeks` and the `weekly` window. Compute µs as `(F - epoch) // timedelta(microseconds=1)`.
3. **Degenerate bootstrap (#3).** Add `degenerate: n <= block` to the bootstrap output. `h2_decision` returns `"inconclusive"` with `reason="degenerate"` if n ≤ max(blocks).
4. **`weekly` window (#4).** Make `window` required: it is [eval_start, A).
5. **Capacity (#5).** Accept an optional warm-up ledger and include it in `_peak`, so `capacity_violations` covers warm-up plus cohort. Keep the name.
6. **Mask hazard (#6).** In `TruthTable`, raise if the mask closes an hour that has a finite filled value. The mask must come from filled truth. Document this in the docstring and in the report's notes for Task 7.
7. **Independent integral test (#7).** Commit a small test that checks `TruthTable.integral` against a pure-Python hour-walk on random jobs with µs-level times.
8. **Tests (#8).** Add:
   - an H2 case where two block lengths decide and the third does not;
   - the n ≤ b degenerate case;
   - `end == F` passing `support_check`;
   - a spring-forward DST week.
9. **Mixed inputs (#9).** Require both inputs to be frames or both to be arrays.
10. **Influence (#10).** Assert that all instances of a source share one duration.
11. **Null `truth_ok` (#11).** `fill_null(False)` before filtering, so a null means closed.

Not in scope: #12, the tolerance error budget. Just note the measured error in the report.
Append a "Fix round 1" section to /tmp/claude-1001/-home-nvidia-workspace-personal-projects/d7fb1e5c-cee6-4473-88b2-02a108cc36ac/scratchpad/task-6-report.md.
