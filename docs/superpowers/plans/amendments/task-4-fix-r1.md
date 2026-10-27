# Task 4 fix round 1 (lead rulings on the task review of 6f48ae8)

Binding: spec §15 F11 as revised on main (b1a6d59), "Baseline bookings". Read it first.
First rebase or merge `s2/task-4` onto current `main`, which now holds Task 1 (`eia_co2`) and Task 3 (`workload.replay`). Run the full suite, commit, and push so PR #19 updates.

1. **Integer microseconds throughout.** Engine, `Capacity`, the policy protocol and bookings all use int64 µs. Remove float-second tolerances; `LATE_TOL_S` goes away or becomes 0 µs. Convert at the boundary: datetime → µs on input, µs → `datetime[us, UTC]` in the ledger.
2. **Bookings (F11).**
   - Replace or extend `u_finish_deadlines` with `u_bookings(jobs, sites, warm=None, transfer_s=...) -> pl.DataFrame`. Columns: `job_uid, site, start_us, end_us, deadline_us`, where `deadline_us = max(arrival + duration + max_delay, U end)`. These come from one U run per scenario.
   - `simulate(jobs, policy, sites, bookings, ...)`: `bookings` is required (no default). Every run pre-books all bookings.
   - At arrival of job j, the policy sees capacity with j's own booking excluded. If it returns an on-time action that fits (engine re-checks), j's booking is released and the action is reserved. Otherwise j runs on its booking.
   - Assert in the engine that every job is on time. A late job raises, because it is a bug under F11.
   - U run with its own bookings must reproduce the bookings exactly (test).
3. **Fast window-local capacity (review finding 1).**
   - Queries (`max_in`, `fits`, `earliest_start`) must cost O(log n + events in window), not O(all breakpoints). With every booking pre-reserved, the structure holds about 2× the cohort's events.
   - Design is your call, for example: a static booking step function (sorted events + prefix sum) plus a pruned dynamic delta structure for releases (negative) and moves (positive). Or a segment tree with range-add/range-max over compressed coordinates.
   - Must stay exact.
   - Target: U, G and S each ≤ 90 s on a real 1-cycle replay. Re-benchmark on `replay()` over 2024-11-01 → 2025-10-24 (about 919k instances), or a 4-week slice if the full run exceeds 10 min, and report both wall times. If the target is missed, report numbers and the bottleneck; do not stall.
4. **F3 mask in the engine (finding 5).**
   - `SimContext` carries per-site closed intervals (µs).
   - `earliest_start`/`earliest_action` skip any start whose execution [start, end) touches a closed interval.
   - `_check_action` rejects masked actions.
   - Bookings are exempt (they are at PACE; document it).
   - `simulate(..., closed: dict[str, list[tuple[int, int]]] | None = None)`; build it in the driver from `site_mask`. Tests use synthetic intervals.
5. **Ledger property test (finding 6).** Commit a sweep-line invariant test over `simulate` for U, G and S. Use fractional-second durations (sub-second µs), simultaneous arrivals, and ends equal to starts. Check:
   - no site over its slots (ends before starts at equal time);
   - remote start ≥ arrival + transfer;
   - immobile jobs only at home;
   - every job on time;
   - each job appears exactly once.
6. **S ranking required (finding 8).** No default. Tests pass it explicitly.
7. **Ledger columns (finding 9).** Add `arrival_ts`, `duration_s` (exact, from input), `moved` (bool: action ≠ booking) and `booking_site`.
8. **Read-only capacity view to policies (finding 11).** Expose only query methods.
9. **Input validation (finding 12).**
   - Reject non-finite durations and non-integral `gpus`.
   - Log a count of `mobile & ~flexible` rows.
   - Reject `bookings` that miss any job, or carry unknown uids.
10. **Warm-up boundary (finding 13).** Document the `<` rule in the docstring. The F2 ≥ 15 d check belongs to the driver (Task 7); no change here.
11. **Benchmarks** keep the synthetic case too, but the headline number is the real replay.

Out of scope: the energy fields (Task 6) and the S real ranking (Task 7).
Append a "Fix round 1" section to your report: the design of the capacity structure, test output, the benchmark table, and any F11 consequences you observed (moved share by policy, how often a policy's preferred action was blocked by bookings).
Write the report to `/tmp/claude-1001/-home-nvidia-workspace-personal-projects/d7fb1e5c-cee6-4473-88b2-02a108cc36ac/scratchpad/task-4-report.md` (`.superpowers` is not writable from your worktree). Copy your current report there first, then append.
