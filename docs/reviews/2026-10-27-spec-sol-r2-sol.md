# Spec re-check r2: Sol (gpt-6.1-sol, xhigh)

- **Run:** 20261027T083718Z-5005e9
- **Reviewed:** main @ 5f5b320
- **Prompt:** `docs/reviews/prompts/2026-10-27-spec-sol-r2.md`
- **Budget:** run 2 of 3 (owner choice, D-050)

## Review (verbatim)

The accepted advance-reservation claim frame is defensible. Important ambiguities remain in baseline construction, cohort construction, and the relaxed bound. These can change the jobs evaluated or invalidate a bound check.

Reviewed `5f5b32009e16490e93a70a2b9fe633a78c972bad` read-only. No files changed or sealed values inspected. Counterexamples below are synthetic arithmetic, not workload measurements.

Locations refer to the [reconciled spec](/home/nvidia/workspace/personal/projects/htw-review/spec-sol-r2/docs/superpowers/specs/2026-10-27-gridpilot-design.md), with §15 binding.

My assessment of all 22 Astra dispositions is:

| ID | Assessment | Reason |
|---|---|---|
| A1 | **Adequate** | Advance knowledge of closures is explicitly assumed and disclosed. The deferred sensitivity needs clearer wording; see R11. |
| A2 | **Adequate** | Execution and both transfer endpoints require truth support, equally for policies, H, and the bound. |
| A3 | **Adequate** | Deferral is retained; F12.9 adds validation independence and republished-source auditing. |
| B1 | **Adequate** | Queueing, additional slack, deadlines, and place-only timing are distinguished. |
| B2 | **Adequate** | Capacity cases are complete scenarios, with their changed U waiting, deadlines, and emissions reported. |
| B3 | **Adequate** | S now has executable destination-priority semantics, including capacity-induced waiting. |
| C1 | **Partial** | The deadline condition addresses insufficient drain, but the cutoff and resulting replay population remain ambiguous. See R2. |
| C2 | **Partial** | Removing the cap and checking bookings fixes those defects. Sharing an action set “under capacity” with the relaxed bound creates another ambiguity. See R1. |
| C3 | **Adequate** | The finite, empty-initialized replay is an explicit estimand; steady-state convergence is no longer implied. |
| D1 | **Adequate** | The intervals are conditional diagnostics with stated dependence assumptions, without an unqualified confirmation claim. |
| D2 | **Partial** | Source-block overlap, replacement, RNG, and percentile conventions remain unspecified. See R4. |
| D3 | **Partial** | Each interval must exclude zero, but matching direction across block lengths is not explicitly required. See R5. |
| D4 | **Adequate** | All repetitions of selected source attempts are removed from paired fixed schedules. Tie handling remains a minor reproducibility detail; see R9. |
| E1 | **Adequate** | Baseline-relative deadlines, exact runtimes, and untested runtime uncertainty accompany every headline. |
| E2 | **Inadequate** | F12.5 omits “R2 coefficient intervals,” whereas Astra identified §10’s marginal-regression intervals. See R7. |
| E3 | **Adequate** | The international-import convention is explicitly disclosed. |
| G1 | **Partial** | The benchmark requirement improves realism, but the fallback window is not executable as written. See R6. |
| G2 | **Adequate** | An independent clean rebuild before freeze restores the required reproducibility gate. |
| H1 | **Adequate** | Whole-run advance knowledge and synthesis from the complete replay are explicitly disclosed. This matches the accepted frame. |
| H2 | **Adequate** | The unsupported “conservative” claim is removed. The requested blocking diagnostic needs a definition; see R9. |
| H3 | **Adequate** | Every carbon search includes the exact booking explicitly. |
| I1 | **Partial** | Labels and synthetic provenance are clarified, but the exact counts still lack reproducible, immutable evidence. See R8. |

The remaining findings are:

1. **R1 — Important; high confidence. The shared legal-action definition can invalidate the relaxed bound.**  
   **Location:** F12.3, line 663; F5, line 541; §8, lines 267–269.

   **Failure scenario:** F12.3 says policies, validator, and `C_relaxed` share an action set “under capacity.” Applying other jobs’ original bookings during independent minimization can produce a purported lower bound above a feasible policy.

   For example, one home slot has U bookings A=[0,2) and B=[2,3); B arrives at 0.1 and runs for one hour. Home intensity is zero during [0,1) and 100 during [1,3). A can move remotely at zero attributed carbon. A policy then runs B during [0.1,1.1), costing 10 units. A bound retaining A’s original booking forces B into [2,3), costing 100 units. The alleged lower bound exceeds the feasible result.

   **Correction:** Define three distinct sets:
   - A continuous per-job envelope enforcing release time, deadline, mobility, transfer, truth support, and gang size no greater than site capacity.
   - Operational candidates from F10 plus the exact booking, filtered against the evolving reservation ledger. H uses these same candidates and reservations, changing only its scoring signal.
   - The relaxed bound minimizes over the continuous envelope while dropping other jobs’ occupancy and bookings. Explicitly state whether immutable warm-up occupancy is also relaxed.

2. **R2 — Important; high confidence. Cohort selection does not uniquely determine the arrival stream, bookings, or drain.**  
   **Location:** F12.3, lines 661–665; §9, lines 277–281; F11, lines 630–631.

   **Failure scenario:** “Largest arrival at which all permitted completions are ≤ F” can mean either a safe prefix or the latest individually safe arrival. A long request can have a deadline after F while a later short request finishes before F. The latter reading admits the short request and excludes the long one; the prefix reading excludes both. The half-open `[eval_start,A)` also excludes a job if A is literally its arrival timestamp.

   It is additionally unclear whether excluded requests retain bookings or remain background traffic. Preloading every U booking and then cloning warm-up reservations can also double-count warm-up occupancy unless their union is defined.

   **Correction:** Freeze a precise prefix rule. For example, compute workload-only U schedules through the candidate horizon, then set A to the first arrival timestamp at which any request’s deadline exceeds F, taking the minimum across registered scenarios requiring a common cohort. Exclude that entire simultaneous-arrival group and every later arrival. If none fails, use the declared horizon endpoint.

   Stop the actual arrival stream at A; install no suffix bookings. Retain warm-up running and queued work exactly once, report it separately, and check support through its actual completion. Record initialization time, A, cohort IDs, booking hash, and drain coverage before grid scoring.

3. **R3 — Important; high confidence. U’s simultaneous-arrival order is circular.**  
   **Location:** §8, lines 236 and 253; F1, line 510; F12.2, line 653.

   **Failure scenario:** U orders simultaneous arrivals by deadline, but final deadlines depend on U’s finish times. With one slot, simultaneous A of duration two and B of duration one, both orders satisfy the rules:
   - A then B produces deadlines A=2, B=3.
   - B then A produces deadlines B=1, A=3.

   Both orders sort correctly by their resulting deadlines. They produce different bookings and downstream results.

   **Correction:** Give the initial U pass an independent tie break, such as `(arrival, stable mapped attempt ID)`. Compute final deadlines afterward. Other policies may then use those frozen deadlines for simultaneous-arrival ordering.

4. **R4 — Minor; high confidence. F12.4 is not a fully frozen bootstrap algorithm.**  
   **Location:** F12.4, lines 670–673.

   **Failure scenario:** “Non-overlapping draw positions sampled uniformly from all n start indices” permits incompatible readings about source-block overlap and replacement. The same seed also yields different results under different random generators or percentile conventions. Omitting empty arrival weeks changes temporal adjacency.

   **Correction:** Specify, for example:
   - Construct every Monday-based America/Denver week intersecting the arrival interval, including zero-job weeks; retain partial edges unchanged.
   - For each block length `b`, reset NumPy `Generator(PCG64(20261027))`.
   - Independently draw `ceil(n/b)` starts **with replacement** from integers `[0,n)` for each replicate.
   - Expand each start into `(start+j) % n`, concatenate, and retain the first n indices. Source blocks may overlap.
   - Apply identical indices to all policies; calculate differences and ratios from resampled totals.
   - Use 2,000 replicates and quantiles 0.025/0.975 with `method="linear"`.
   - Define empty-input and zero-denominator behavior explicitly.

   With these additions, two implementations can be checked against one reference index sequence and interval fixture. The method remains a conditional resampling diagnostic, without guaranteed population coverage.

5. **R5 — Minor; high confidence. The H2 robustness rule omits consistent direction.**  
   **Location:** F12.4, line 674; F4, line 532.

   **Failure scenario:** “Wholly on one side of zero at block lengths 2, 4 and 8” does not explicitly forbid different sides at different lengths.

   **Correction:** A favorable H2 claim requires all three lower endpoints for `W−L` to exceed zero. An adverse directional result requires all three upper endpoints below zero. Otherwise report the directional evidence as inconclusive or unstable.

6. **R6 — Important; medium confidence. The fallback delivery window remains ambiguous.**  
   **Location:** F12.6, lines 683–684; F2, line 517.

   **Failure scenario:** F_val is Friday 2025-10-24T00Z, so “13 full weeks ending at F_val” does not identify 13 complete Monday-based weeks. It also does not say whether those are arrival weeks or a truth/execution window. Treating them as arrivals through F_val leaves jobs requiring truth afterward.

   A benchmark of U alone would also underestimate K/W/L candidate-search costs, even with all bookings loaded.

   **Correction:** Freeze explicit fallback bounds. One valid choice is a **91-day truth window** `[2025-07-25T00Z, 2025-10-24T00Z)`, with a separately recorded initialization timestamp and workload-derived A under the corrected cohort rule. Report its actual shorter arrival window.

   Require the benchmark to time forecast construction, carbon-search replay, and export with representative long jobs and full-run booking density. State that the checkpoint fallback does not silently replace the registered full validation selection before configuration freeze.

7. **R7 — Minor; high confidence. E2’s correction targets the wrong analysis.**  
   **Location:** F12.5, line 679; §10, line 330; R2, lines 481–484.

   **Failure scenario:** An implementer can omit intervals from R2 while still publishing ordinary coefficient intervals for §10’s serially dependent marginal regressions.

   **Correction:** Replace the sentence with: “Coefficient confidence intervals for §10’s first-difference marginal regressions are omitted unless a dependence-aware estimator and its settings are frozen before evaluation.” R2’s descriptive correlations are separate.

8. **R8 — Minor; high confidence. F11’s exact motivating counts remain unreproducible from the cited evidence.**  
   **Location:** F11, line 627; F12 introduction, line 644; Astra disposition I1.

   **Failure scenario:** The pinned checkout does not contain `lab/scripts/bench_sim_core.py`. Naming that script and PR #19 supplies no immutable benchmark configuration, seed, ledger, or metric reference reproducing the four counts.

   **Correction:** Remove the exact counts, or supply an immutable code reference, complete synthetic configuration, reproduction command, and ledger/metric hashes. The corrected `simulated` label should remain.

9. **R9 — Minor; high confidence. Two required diagnostics still lack deterministic definitions.**  
   **Location:** F12.4, line 675; F12.7, line 689.

   **Failure scenario:** Equal-GPU-hour source attempts can produce different top-k exclusions. “Reservation-blocked preferred actions, by count and energy” can mean rejected candidates, affected jobs, or repeated full-job energy for every rejected start.

   **Correction:** Break source-ranking ties by stable source ID. Define the blocking diagnostic’s counterfactual ledger, preference rule, counting unit, and energy attribution. A workable definition counts each affected job once and sums its modeled execution energy once, comparing its preferred action with and without pending other-job U bookings while retaining earlier committed moves.

10. **R10 — Important; high confidence. The executable implementation plan still directs materially different behavior.**  
    **Location:** [Stage 2 plan](/home/nvidia/workspace/personal/projects/htw-review/spec-sol-r2/docs/superpowers/plans/2026-10-27-stage2-core.md:17), especially lines 23, 161, 191, 203, and 263.

    **Failure scenario:** Following the task-local instructions implements the old fixed drain cutoff, searches only `[arrival, arrival+max_delay]`, and tests that inflexible jobs start at arrival. These conflict with baseline-relative windows and F12’s permission for carbon-driven timing within every job’s baseline queue window. The plan also lacks the new booking and transfer-support contracts.

    **Correction:** Reconcile the plan with F11–F12 before executing its remaining tasks: baseline tie breaking, booking lifecycle, cohort/drain, legal windows, all charged truth support, bootstrap, benchmark, and rebuild requirements. Replace obsolete tests with tests of the reconciled behavior.

11. **R11 — Minor; high confidence. The deferred missingness sensitivity is described inconsistently.**  
    **Location:** F12.1, line 649; Astra A1 disposition, line 178; D-049.

    **Failure scenario:** The spec says scheduling ignores missingness; the disposition describes “carbon-blind scheduling.” Those are different experiments. Calling the former a “causal sensitivity” can also suggest an online information boundary even while whole-run bookings remain available.

    **Correction:** Call it a **missingness-blind scheduling sensitivity**, retain the intended carbon signals, and state which advance-information assumptions remain. Reserve an arrival-causal interpretation for a replay that also removes whole-run booking knowledge. This does not establish causal avoided emissions.

12. **R12 — Minor; high confidence. The disposition summary miscounts severities.**  
    **Location:** [D-049](/home/nvidia/workspace/personal/projects/htw-review/spec-sol-r2/docs/decisions.md:375), line 377.

    **Failure scenario:** The record says 10 important and 12 minor findings; Astra actually lists 11 of each. It also describes all nondeferred findings as fixed despite the gaps above.

    **Correction:** Correct the counts and record the re-check dispositions against their eventual fixing commits.

On the requested interactions: **there is no legitimate truth-support exemption for bookings**. F12.1 and F12.3 apply support rules to the exact booking too. If its precheck fails, the result is an accounting-support failure; silently executing an unscoreable fallback is prohibited. With supported, legal U bookings, the replacement invariant remains sound.

Several differences from earlier prose are intentional overrides: whole-run booking visibility, advance-known closures, timing within baseline queues, Denver arrival weeks, and the restored rebuild requirement. They need not be treated as unresolved contradictions.

The judge-facing frame is sufficient when the qualifications appear together beside the result: simulated advance reservations over the whole run, advance-known closures, baseline-relative deadlines, exact runtimes, EIA-attributed emissions, and untested runtime uncertainty. Zero misses is an invariant under those assumptions, rather than independent reliability evidence. Conditional resampling intervals must likewise stay qualified. No historical online-router or physically avoided-emissions claim follows.

Validation-only implementation can proceed on loaders, forecasts, interval capacity, accounting primitives, and the offline page. R1–R3 and R10 should be resolved before integrating the final comparison; R4–R6 before exporting uncertainty or selecting from the fallback. The accepted frame does not require implementing shadow U or runtime overruns for F9.

Verdict: not_ready
## Dispositions (lead, 2026-10-27 ~03:10 MT)

Sol's corrections are adopted as written in spec §15 F13, unless noted below.

| ID | Sev | Disposition | Where |
|---|---|---|---|
| R1 | important | **Fixed (41b2e30).** Three sets (envelope, operational, bound). The bound drops other jobs' occupancy, bookings **and** warm-up occupancy. | F13.1 |
| R2 | important | **Fixed (41b2e30).** A prefix cutoff rule, with no suffix bookings, warm-up counted once, and the record written before scoring. U is causal (job k's slot depends only on earlier jobs), so the prefix's bookings are unchanged by truncation. | F13.2 |
| R3 | important | **Fixed (41b2e30).** U's initial pass breaks ties by `(arrival, declared deadline, job_uid)`, which does not depend on U. The engine already does this (Task 4). | F13.3 |
| R4 | minor | **Fixed (41b2e30).** The bootstrap is fully specified as Sol suggested. | F13.4 |
| R5 | minor | **Fixed (41b2e30).** H2 direction must be consistent across b = 2, 4 and 8. | F13.4 |
| R6 | important | **Fixed (41b2e30).** The fallback is a 91-day truth window [2025-07-25T00Z, 2025-10-24T00Z). The benchmark times forecast construction, carbon search and export. The fallback never replaces the registered selection. | F13.5 |
| R7 | minor | **Fixed (41b2e30).** The wording now targets §10's marginal regressions. | F13.6 |
| R8 | minor | **Fixed (41b2e30).** The exact counts are removed from F11. | F11 |
| R9 | minor | **Fixed (41b2e30).** Ties go to the stable source ID. The blocked diagnostic is defined per job, counted once, with execution energy counted once. | F13.4, F13.7 |
| R10 | important | **Fixed (41b2e30).** A plan amendment section points every remaining task at F11–F13, through the lead's per-task amendment files. | plan §"Amendments" |
| R11 | minor | **Fixed (41b2e30).** Renamed to "missingness-blind scheduling sensitivity". | F13.6 |
| R12 | minor | **Fixed (41b2e30).** D-049's counts are corrected to 11 important and 11 minor. | D-049 |
| — | (interaction) | **Fixed (41b2e30).** Bookings are **not** exempt from truth support: every U booking is pre-checked (F12.3), and a failure is an accounting-support failure. The engine skips the runtime mask check for bookings only because the pre-check already passed. | F13.3 |

**Gate status.** Sol r2 is not_ready. The remaining items are precision corrections adopted verbatim. The owner's 3-run budget leaves one run, the Wed results audit. So the F13 re-check is done by a fresh-context Claude reviewer, recorded as a substitution per `.claude/skills/codex-gates`. Sol states that validation-only implementation can proceed now.
