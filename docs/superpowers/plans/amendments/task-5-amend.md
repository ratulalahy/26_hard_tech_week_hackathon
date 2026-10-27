# Task 5 amendments (lead rulings; binding over the brief where they differ; spec §15 F11, F12 on main)

1. **Candidate window (F12.3).**
   - Starts lie in `[arrival, deadline − duration]` at each legal site. Use the job's F1 deadline from the bookings; do not use `arrival + max_delay`.
   - Candidates are hourly boundaries, plus the earliest feasible start per site, **plus the exact booking (F12.7)**.
2. **Legality is the engine's.** Use Task 4's final helpers (the capacity view, `closed` intervals, transfer, mobility). Do not re-implement them. A remote move also needs truth support at the arrival hour at both home and destination (F12.1); the engine enforces this, and the search must not propose actions the engine would reject.
3. **Forecast as-of (leakage).**
   - At a job's arrival t, each target hour uses the value from the **latest issue with issue_ts ≤ t** that covers that hour.
   - Hours not covered by any such issue use the climatology tail (K from Task 2's fitted climatology), labelled modeled.
   - Never use an issue after t. Add `test_no_future_issue`: a forecast issued at t + 1 s with absurd values must not change the choice.
4. **Choice and fallback.**
   - Rank candidates by predicted kg (exact-overlap integral, plus attributed transfer).
   - Return the best one that fits the current capacity view, with ties broken as in the brief.
   - If the best-ranked candidate does not fit, it is "blocked" (F12.7). Report it through the mechanism Task 4 built.
   - If nothing fits, return the booking.
5. **Inflexible jobs (F12.2).** `test_inflexible_stays` becomes: a non-flexible job lands at PACE within its baseline queue window `[arrival, U start]`. If U start == arrival, it starts at arrival.
6. **Efficiency.** Use prefix sums per site and per issue. Fit L once and predict many times; never call `forecast()` per job. Benchmark K, W, L and H on the same real replay slice Task 4 used, and report the wall times.
7. **Signals.** K, W and L use Task 2's validation forecasts (`gridpilot.forecast`; regenerate them with `uv run python -m gridpilot.forecast` if the run is absent). H uses realized truth (consumption basis) and is a diagnostic only.
8. **Validation hours 2025-10-31T06–23Z** have no issued forecast, so they use the climatology tail.

## F13 additions (Sol r2, main 41b2e30)
9. **F13.1.** H uses exactly the same operational candidates and reservation ledger as K, W and L; only its scoring signal (realized truth) differs.
10. **F13.7 blocked diagnostic.** Per job, compute the preferred action twice, under the real capacity view and under a view without other jobs' pending (not-yet-arrived) U bookings. Earlier committed moves are kept in both. The job is blocked if the two differ. Count it once and sum its modeled execution energy once. Use Task 4's mechanism for the second view if it built one (see its report on "preferred without later bookings"); otherwise add a read-only view in the engine.

## Engine hardening (Task 4 re-review minors; do these in sim/engine.py as part of this task)
11. **M1.** Assert in `_merge`/`simulate` that every closed interval is hour-aligned, and check F12.1 as `[floor_hour(arrival), +1h)`.
12. **M3.** Booking validation also checks `deadline_us == max(arrival + duration + delay, end_us)`, and that the booking site is legal for the job.
13. **M5.** `u_bookings(..., closed=...)` passes the same `closed` to U that `simulate` uses, so U reproduces its bookings under a mask.
14. **M2.** `CapacityView` must not expose the mutable `Capacity`; use a closure or name-mangling plus a test that `reserve` is unreachable.
