# Task 6 amendments (lead rulings; binding over the brief where they differ; spec §15 F11, F12 on main)

1. **Energy and CO₂.**
   - Execution energy is `gpus × 0.60 kW × hours × 1.20`, charged at the execution site's hourly consumption-basis intensity, as an exact-overlap integral.
   - Transfer energy, for remote moves only, is `0.05 × gpus × 0.60 × duration_h`. Half is charged at home and half at the destination, at the **arrival hour**, with PUE 1.20 on each half.
2. **Weekly totals (F12.4).** Use the arrival week starting Monday 00:00 America/Denver. Each job's full totals go to its arrival week. Partial edge weeks are kept as they are.
3. **Bootstrap (F12.4, superseded in detail by F13.4; follow F13.4 exactly where they differ).**
   - Circular block bootstrap.
   - Each replicate draws ⌈n/b⌉ block start indices uniformly from 0..n−1, takes b consecutive weeks from each start with wrap-around, concatenates them and trims to n.
   - The **same indices are used for every policy** in a replicate.
   - reps = 2000, seed = 20261027 (`numpy.random.default_rng`), percentile 95%.
   - Return the ratio-of-totals saving and the paired absolute kg difference.
   - Also provide `h2_decision(w_weeks, l_weeks) -> dict`. It returns the intervals at b = 2, 4 and 8, and `decided` is True only if all three intervals for W − L kg lie wholly on one side of zero.
   - Call these "conditional temporal block-resampling intervals" in docstrings and outputs.
4. **Relaxed bound (F5, F12.3; F13.1 overrides).** Minimise over the continuous per-job envelope (release, deadline, mobility, transfer, truth support, gang ≤ site capacity), dropping all other jobs' occupancy, bookings **and warm-up occupancy**. The original text follows for reference.
   - Take the per-job minimum over the shared legal-action set: [arrival, deadline − duration] at legal sites, plus the booking, under mobility, transfer and the F12.1 truth support.
   - Ignore only competition between jobs.
   - The minimum of an exact-overlap integral is attained where the start or the end aligns with an hour boundary, or at a window endpoint, so enumerate those.
   - The test `bound ≤ every feasible policy` stays.
5. **Influence diagnostic (F12.4 D4).** `influence(ledgers: dict[str, Ledger], jobs, truth, k_list=(1, 5, 10))`.
   - Rank unique `source_job_id` by declared GPU-hours, independent of policy.
   - Remove every instance of the top k from all policies' totals.
   - Report the savings vs U for each k.
6. **Accounting-support check (F12.3).** `support_check(bookings, truth, F) -> dict`. It reports every U booking that ends after F or touches missing PACE truth. A nonzero result is an accounting-support failure, which the driver must report.
7. **Feasibility.** Under F11 every policy is on time by construction. `score` still computes `late_jobs` and `late_gpu_h`, and sets `feasible = late_jobs == 0`.
   - Also report `moved_share` (by jobs and by energy) and `blocked` (count and energy), from Task 4's ledger columns.
8. **Ledger interface.** Use Task 4's final ledger columns (`job_uid, site, start_ts, end_ts, arrival_ts, duration_s, moved, booking_site, blocked`, plus whatever Task 4 reports). Check the merged code on main and do not assume more.

## F13 additions (Sol r2, main 41b2e30)
9. **Bootstrap, exactly per F13.4.**
   - Weeks are every Monday-based Denver week that intersects the arrival interval, including zero-job weeks.
   - For each b ∈ {2, 4, 8}, reset `Generator(PCG64(20261027))`. Each of 2,000 replicates draws `ceil(n/b)` starts with replacement from `[0, n)`, expanded `(s+j) % n`, concatenated, and the first n kept.
   - Shared indices across policies. Quantiles 0.025 and 0.975 with `method="linear"`.
   - Empty input gives null intervals; a zero reference gives a null ratio.
   - Add a fixture test: a 6-week toy, b = 2 and reps = 3, asserting the exact index sequence, so a reimplementation can be checked.
10. **H2 direction (F13.4).** `h2_decision` returns `"favourable"` only if all three lower endpoints of W − L are > 0, `"adverse"` only if all three upper endpoints are < 0, and `"inconclusive"` otherwise.
11. **Influence ties** go to the stable `source_job_id`.
