# Spec soundness gate r1: Astra (gpt-6-astra, high)

- **Run:** 20261027T081838Z-73c3a7
- **Reviewed:** main @ b1a6d59
- **Prompt:** `docs/reviews/prompts/2026-10-27-spec-astra-r1.md`
- **Pre-approved budget:** run 1 of 3

## Review (verbatim)

The spec is not ready to freeze. Its central comparison is defensible, and F11 can guarantee schedule feasibility, but several rules still undermine the claimed information boundary, time-only/place-only interpretation, and complete-work accounting.

Reviewed commit `b1a6d59e61cf182237569ecc4eb4f5d14433ccc4`, read-only. No files changed, notebooks executed, or sealed values inspected. I checked the supplied evidence and used small in-memory arithmetic counterexamples; those examples are not Seren measurements.

Locations below refer to the [reconciled spec](/home/nvidia/workspace/personal/projects/htw-review/spec-astra/docs/superpowers/specs/2026-10-27-gridpilot-design.md), with §15 taking precedence.

**1. Information leakage and availability**

The publication envelopes are reasonable conservative assumptions against EIA’s typical publication schedule. The revised-snapshot caveat, historical issue-time reconstruction, fitting dates, and seal-opening requirements are sound as written. EIA distinguishes next-day generation publication from slower bilateral-flow and imported/exported-carbon publication. [EIA methodology](https://www.eia.gov/electricity/930-content/about.html)

- **A1 — important; high confidence. Location: F3, lines 522–529; §8, line 234; F11, line 635.**  
  **Failure:** F3 gives every policy advance knowledge of future missing carbon observations. A job arriving Monday avoids a destination because Thursday’s eventual historical record is missing. Equal access makes comparisons paired, but does not make this information historically available. Missingness can also correlate with unusual grid conditions. F11 therefore is not the only advance-information assumption.  
  **Correction:** Explicitly describe F3 as an assumed, advance-known closure calendar and qualify the experiment accordingly. For an operational replay, keep future truth availability out of scheduling; report unscoreable outcomes or use the pre-registered common-support analysis from the earlier §9. Completeness permission does not itself authorize operational use of future missingness.

- **A2 — important; high confidence. Location: §7, line 219; F3, line 524; F11, line 640.**  
  **Failure:** The mask checks execution, but transfer energy is charged at arrival at both endpoints. A job arriving at 00:45 can execute remotely at 01:15 with complete execution truth while the destination’s 00:00 carbon value is missing. Its total cannot be computed.  
  **Correction:** Require valid truth for every charged energy component, including both arrival-time transfer charges. Apply the identical rule to policies, H, and the relaxed bound.

- **A3 — minor; high confidence. Location: F8, line 568; R4a.**  
  **Failure:** A foundation-model checkpoint trained through October 2025 satisfies the stated test cutoff while potentially having memorized almost the entire validation year used to admit it. Excluding EIA-930 by name also does not exclude republished copies.  
  **Correction:** Keep this extension deferred. If revived, require independence from the validation period used for selection, or explicitly disqualify that validation comparison from admission evidence. Audit derived and republished target sources as well.

**2. Comparator fairness and H1–H4**

W versus L isolates the **system-level effect of changing the forecast signal**, conditional on the same booking rules, assumptions, and cohort. Their reservation states need not remain identical: downstream state differences are part of that system effect. The common-state regret diagnostic supplies the narrower forecast-skill comparison. Long-job climatology tails dilute H2 rather than invalidate it.

- **B1 — important; high confidence. Location: §7, line 214; §8, line 261; F1, lines 510–511; F5; F11, line 638.**  
  **Failure:** Setting allowed delay to zero does not remove temporal choice after F1. For a two-hour job whose U start is eight hours after arrival, F1 permits starts anywhere from arrival through hour eight, even with zero allowed delay. W/L can choose a cleaner time inside that window. Calling this “place-only” would be false. F1’s claim of “extra slack beyond” U is also inaccurate: with six hours allowed delay and eight hours of U queueing, extra slack after U is zero.  
  **Correction:** Define distinct quantities for baseline queueing, discretionary waiting, and latest completion. For place-only, permit only the earliest feasible start at each candidate site, with no carbon-driven choice among start times. State precisely whether flexibility means `max(U_finish, arrival + duration + delay)` or `U_finish + delay`; retain the chosen definition consistently.

- **B2 — minor; high confidence. Location: §7 capacity sensitivity; F1; F11, line 630.**  
  **Failure:** Changing home capacity recomputes U, deadlines, bookings, and the U denominator. An H4 capacity curve therefore changes more than available hardware. Larger capacity can tighten deadlines and reduce apparent routing opportunity.  
  **Correction:** Report each scenario’s baseline waiting, deadline distribution, and U emissions. Describe this as a complete capacity scenario. If claiming the isolated effect of capacity, add a comparison holding deadlines fixed.

- **B3 — minor; medium confidence. Location: policy S, line 255; F5, lines 538–539.**  
  **Failure:** “Rank destinations, then take their earliest feasible completion” can intentionally wait for BPAT while another site is immediately available. F5’s “static placement and no delay” can be read as forbidding that wait, producing a materially different S implementation.  
  **Correction:** Give executable pseudocode: either choose the first ranked destination with an on-time earliest slot, or choose the earliest slot across destinations and use rank only for ties. Describe any capacity-induced waiting explicitly. S-wait should add carbon-driven timing beyond that clearly defined S.

H3 is correctly narrowed by F5: it compares dynamic placement **and waiting** against a static rule. It does not independently establish forecast value.

**3. Work accounting and feasibility**

F11 removes the earlier generic greedy-scheduling infeasibility. With legal U bookings, sufficiently large home capacity per gang, exact declared durations, and complete accounting support, no remaining rule necessarily makes the primary validation cohort trivially infeasible. However, “on time” and “fully scoreable before F” are not equivalent.

- **C1 — important; high confidence. Location: §9, lines 277–281; F1; F2.**  
  **Failure:** The drain allowance remains `R_max + W_max`, but F1 introduces potentially longer U queueing. A synthetic 336-hour job queued for 30 hours finishes after 366 hours, on its F1 deadline; a 336 + 24-hour drain provides only 360 hours. Thus U can be deadline-feasible yet require unavailable carbon after F. This counterexample does not establish that Seren actually exhibits that wait.  
  **Correction:** Derive a common arrival cutoff from workload-only U bookings and the final deadline rules, checking that **every permitted completion** lies before F in every registered scenario. Freeze this before inspecting grid outcomes. Do not merely assert that 15 days suffices.

- **C2 — important; high confidence. Location: F11, lines 633–640; §8 relaxed bound.**  
  **Failure:** “Starts … capped by R_max” is undefined and can exclude a fallback booking if U queueing exceeds that cap. Different interpretations can make the search, feasibility validator, and relaxed bound use different legal windows. The guarantee also assumes PACE truth is present throughout every fallback booking; validation completeness does not establish test completeness.  
  **Correction:** Define the cap algebraically and specify whether the fallback is an explicit exception. Give policies and the bound one shared definition of legal actions. Check U bookings against F and PACE truth support before running comparisons. Classify insufficient truth as an accounting-support failure, not automatically a scheduler bug.

- **C3 — minor; medium confidence. Location: §9 warm-up; F2, line 518.**  
  **Failure:** Maximum runtime bounds how long a started job survives, not how long queue effects survive. Fifteen days of warm-up need not remove effects of starting U empty. Different warm-up starts can produce different bookings for energy-heavy campaigns.  
  **Correction:** Either define the estimand explicitly as a finite replay initialized empty at a fixed timestamp, or verify workload-only U state stability with a longer warm-up. Preserve the same resulting initial state across policies.

The overrun experiment is explicitly deferred by F9, so its earlier immutable-reservation wording does not block the core. It must consequently remain an untested limitation, not claimed evidence.

**4. Statistics**

- **D1 — important; high confidence. Location: §9, lines 296–298; F4; F6.**  
  **Failure:** Resampling blocks of already-realized arrival-week totals does not generate new workload/grid alignments or rerun their capacity interactions. Moreover, the same campaigns recur every 23 weeks, beyond all proposed block lengths, while the grid is seasonal. The proposed intervals therefore do not establish nominal 95% coverage for a population of alignments. Warning that clusters are not independent does not fix that interpretation.  
  **Correction:** Call these **conditional temporal block-resampling intervals**, state their dependence assumptions, and avoid treating exclusion of zero as unqualified statistical confirmation. Report the actual phase replays and concentration diagnostics separately. If alignment uncertainty is the target, it requires pre-registered alternative alignments and complete replays.

- **D2 — minor; high confidence. Location: §9, line 296.**  
  **Failure:** “Paired contiguous blocks” does not specify overlapping versus nonoverlapping blocks, circular wrapping, handling of partial first/last weeks, or trimming to the original sample length. Implementations can return different intervals using the same seed.  
  **Correction:** Freeze one exact resampling algorithm, use identical sampled indices for every policy in a replicate, and document edge-week treatment.

- **D3 — minor; high confidence. Location: F4, line 532.**  
  **Failure:** “Same sign at block lengths 2 and 8” is ambiguous. The original point estimate has the same sign regardless of bootstrap block length, making that reading vacuous.  
  **Correction:** Specify whether the requirement concerns the interval endpoints, bootstrap median, or another statistic. If robustness of the favorable claim is intended, require the relevant intervals to remain wholly favorable.

- **D4 — minor; high confidence. Location: F6, lines 544–546.**  
  **Failure:** Leaving out one mapped job instance can leave other copies of the same dominant source attempt in the result. Selecting “top” separately by policy also breaks pairing.  
  **Correction:** Rank unique source attempts by policy-independent declared GPU-hours; remove all repeated instances of each selected source ID from both accounting totals. Label this an influence diagnostic on fixed schedules, unless schedules are actually rerun.

**5. Carbon accounting and claim wording**

Consumption basis, same-schedule production repricing, the separation from causal avoided emissions, and the marginal proxy’s restricted role are appropriate.

- **E1 — important; high confidence. Location: headline, line 27; F1; judge answer, line 452; F9, line 613; F11.**  
  **Failure:** “Within declared deadlines” can sound like an independently supplied service requirement. Here deadlines are derived partly from U, and F11 guarantees them under exact known runtimes. The judge answer additionally says runtime uncertainty is exposed with a stress test that F9 defers.  
  **Correction:** Put “baseline-relative deadlines” and “exact declared runtimes” beside the result. State that runtime uncertainty is untested if the stress case is absent. Do not present zero misses as demonstrated production reliability.

- **E2 — minor; high confidence. Location: §10, line 330.**  
  **Failure:** Ordinary regression coefficient intervals can be too narrow for serially dependent first-differenced hourly residuals. Calling the coefficient associational does not resolve its uncertainty calculation.  
  **Correction:** Specify a dependence-aware interval method, such as an explicitly configured HAC estimator or temporal block bootstrap. Otherwise omit coefficient confidence intervals and retain descriptive diagnostics.

- **E3 — minor; high confidence. Location: primary consumption signal, lines 90–96; skeptic view and F7.**  
  **Failure:** A generic “includes imports” explanation can imply that imported electricity receives its actual source-specific carbon factor. EIA assigns Canadian and Mexican imports an average U.S. emissions rate, a material modeling convention for a hydro-region story. [EIA methodology](https://www.eia.gov/electricity/930-content/about.html)  
  **Correction:** Include that convention in the consumption-basis evidence drawer. Continue calling the result EIA-attributed emissions, not a definitive ranking of physical marginal impacts.

**6. Amendments R1–R6**

**Nothing further found in their binding reconciliation.**

R1 consistently adds NEVP. R2 remains descriptive and its quartile is now training-fitted. R3 respects the noncausal marginal-proxy limit. F9 explicitly defers R4. R5 remains subordinate to the evidence contract. R6 clearly replaces the competing workload, model, and accounting choices.

A3 applies if R4a is revived. The storage illustration should remain deferred; an assumed label alone would not establish physically feasible storage or headroom.

**7. Buildability by Tuesday 18:00**

F9 is a substantial improvement, but it still lacks a measured execution budget and a sufficiently explicit fallback scope.

- **G1 — important; medium confidence. Location: runtime discipline; F9–F11.**  
  **Failure:** A two-week benchmark can underrepresent a full run that preloads all U bookings, carries long jobs, and evaluates many candidate starts. Discovering this late can leave seven unfinished policy runs and no inspectable dashboard result. At the reviewed commit, the core forecast/simulator/evaluation implementation is not yet present in the tracked source tree.  
  **Correction:** Require an early measured benchmark using representative long-job and booking density, with forecast-build, replay, and export timings. Define a fixed, timestamp-selected validation slice as the 18:00 fallback deliverable, clearly labeled with its actual coverage; complete the full validation evaluation before configuration freeze.

- **G2 — important; high confidence. Location: §12 clean rebuild requirement; F9, line 617.**  
  **Failure:** Deferring the canonical-hash rebuild past the freeze leaves a reproducibility command without demonstrated reproducibility. A rerun can change cohort construction, bookings, or exported metrics unnoticed.  
  **Correction:** Retain one independent rebuild of the selected core run before freeze, comparing canonical metrics and ledger invariants within stated tolerances. The elaborate full-field registry can remain deferred because exported evidence envelopes already provide a smaller contract.

Explicitly defer these from the **18:00 deliverable**:

- Full-year H replay and full-year relaxed-bound computation, if they threaten delivery; retain tiny exhaustive bound and legality checks.
- Place-only until its F1 interaction is corrected.
- Additional phases, broad one-axis sweeps, S-wait, and full overview forecasting.
- Marginal regression, R2 cross-BA statistics, prediction intervals, utility-forecast comparison, break-even UI, and elaborate story animation.
- Weather, prices, foundation models, storage, PAI, MILP certification, and runtime-overrun simulation, as F9 already directs.

Keep the four sites, U/G/S/K/W/L, PACE traffic report, regional movement, exact capacity/work/energy accounting, actual covered dates, signed comparisons, evidence labels, and offline page. Production-basis repricing should remain first after the checkpoint. No H2 decision claim should appear before the specified uncertainty checks are complete.

**8. F11: baseline bookings as fallback**

The reservation invariant is sound **conditionally**. Start with a legal complete U schedule. Replacing one booking with an action that respects all other bookings and previous replacements preserves capacity feasibility. Requiring completion by that job’s deadline preserves deadline feasibility. This is an induction over replacements.

The advance-calendar assumption is acceptable for a clearly labeled **advance-reservation scheduling scenario**. It is insufficiently described for a historical online-router claim.

- **H1 — important; high confidence. Location: F11, lines 630–635.**  
  **Failure:** Initializing every booking for the whole run reveals substantially more than a day-ahead calendar. A long job’s action can be rejected because of a reservation belonging to a request that will arrive many days later. Calling this merely “day-ahead reservations” understates the information advantage.  
  **Correction:** State the actual advance-knowledge horizon and disclose that the calendar is synthesized from the complete replay. Alternatively, implement a bounded reveal horizon and revisit the guarantee, or use the causal alternative below.

- **H2 — important; high confidence. Location: F11, line 636.**  
  **Failure:** “Savings are therefore conservative” does not follow for the implemented heuristics. Reservations restrict some actions, but also prevent bad greedy backfilling and disclose future contention. They can improve a heuristic’s outcome. A feasible-set restriction bounds a matched optimum; it does not order realized savings from different heuristics or information sets.  
  **Correction:** Replace this with: “Bookings restrict rescheduling opportunity; their effect on realized policy savings is not signed.” Report reservation-blocked actions or energy to show how restrictive the assumption is.

- **H3 — minor; high confidence. Location: F10; F11, lines 632–633.**  
  **Failure:** The U booking is only a fallback when no action is returned. A non-hour-aligned booking may be omitted from the carbon search even when it has lower predicted emissions than every enumerated alternative.  
  **Correction:** Include the exact original booking as an explicit candidate for every carbon-search policy, subject to the common legality rules. This is cheap and makes the fallback behavior reviewable.

F11 does **not automatically favor L over W**: both receive the same calendar and search rules. Thus H2 remains a paired conditional comparison. H1 and H3 measure opportunity under advance bookings; they cannot be generalized to an unannounced-arrival service. H4 additionally needs the scenario interpretation in B2.

Nor does F11 force savings to be tiny. Remote capacity begins unoccupied by U bookings, so eligible jobs can still move substantial work. Time-shifting at PACE is more restricted. The existing immovable mass and long-job tails limit opportunity, but the resulting saving requires measurement.

A better causal alternative is an **online shadow U schedule**:

1. When a request arrives, insert it into a carbon-blind, immutable U reservation ledger using only requests already received. Derive its baseline-relative deadline then.
2. Keep those shadow bookings even when the real policy routes jobs elsewhere.
3. Require the real PACE reservation profile to remain pointwise no greater than the shadow-U profile of arrived jobs. Enforce ordinary capacity at destinations.
4. Permit home retiming within capacity released by already-arrived jobs; otherwise retain the request’s U booking.

A later U insertion remains feasible because real home occupancy never exceeds shadow occupancy. This protects future U service without knowing future requests. It is more restrictive than F11 and still assumes exact runtimes, but supports a causal arrival-time implementation. Test the invariant explicitly before adopting it.

**9. Other judge-facing risks**

- **I1 — minor; high confidence. Location: F11, line 627; §15 introduction, line 506; D-048.**  
  **Failure:** Synthetic simulator outcomes are labeled “Observed,” contrary to the evidence vocabulary, and their exact counts have no run/config/ledger reference in the spec. The blanket statement that the gate fixes preceded validation results also needs to distinguish later F11 implementation evidence.  
  **Correction:** Label the deadline counts **simulated**, link their reproducible benchmark provenance or remove the unsupported exact counts, and date F11 separately from F1–F10. State whether its motivating slice was synthetic or used validation grid/workload outcomes.

The most defensible judge-facing result is a conditional scheduling experiment with equal attempted GPU-work, baseline-relative deadlines, explicit reservation knowledge, and EIA-attributed emissions. The remaining fixes are needed to make that description match the executable rules.

Verdict: not_ready
## Dispositions (lead, 2026-10-27 ~02:45 MT)

Each finding was checked against the spec text before ruling. The fixes are in spec §15 F12.

| ID | Sev | Disposition | Where |
|---|---|---|---|
| A1 | important | **Fixed (relabelled).** F3 is now an *assumed advance-known closure calendar*, alongside F11. Added a deferred causal sensitivity: carbon-blind scheduling, scored on common support. | F12.1 |
| A2 | important | **Fixed.** Truth must exist for every charged component, including both arrival-hour transfer charges, for policies, H and the bound. | F12.1; Task 4/5 engine |
| A3 | minor | **Deferred.** R4a stays deferred; the condition is recorded if it is revived. | F12.9 |
| B1 | important | **Fixed.** Defined baseline queue window, discretionary slack and latest completion. Flexibility is `max(U_finish, arrival+duration+delay)`. Place-only means earliest feasible start per site; it is deferred from 18:00. | F12.2 |
| B2 | minor | **Fixed (wording and reporting).** A capacity scenario is a complete scenario, and per-scenario U waiting, deadlines and emissions are reported. | F12.2 |
| B3 | minor | **Fixed.** S pseudocode: the first ranked destination with an on-time earliest slot, else the booking. | F12.2 |
| C1 | important | **Fixed.** The cohort is derived from workload-only U bookings: arrivals in the window whose every permitted completion (deadline) is ≤ F. This is frozen before grid outcomes are seen. | F12.3 |
| C2 | important | **Fixed.** The R_max cap is removed. One legal-action definition is shared by policies, the validator and the bound. U bookings are checked against F and PACE truth support first, and a support failure is classified as an accounting-support failure. | F12.3 |
| C3 | minor | **Fixed (estimand stated).** A finite replay initialised empty at a fixed timestamp, with a 15 d U warm-up and one cloned state. | F12.3 |
| D1 | important | **Fixed.** Renamed "conditional temporal block-resampling intervals", with their assumptions stated and no unqualified "confirmation". | F12.4 |
| D2 | minor | **Fixed.** The algorithm is frozen (see F12.4). | F12.4; Task 6 |
| D3 | minor | **Fixed.** The H2 rule requires the CI to lie wholly on one side of zero at block lengths 2, 4 and 8. | F12.4 |
| D4 | minor | **Fixed.** Influence diagnostic: rank unique source attempts by declared GPU-hours, and remove all their instances from both totals. | F12.4 |
| E1 | important | **Fixed.** The headline carries "baseline-relative deadlines, exact declared runtimes; runtime uncertainty untested". | F12.5 |
| E2 | minor | **Fixed.** R2 coefficient CIs are omitted (deferred). | F12.5 |
| E3 | minor | **Fixed.** The evidence drawer states EIA's convention that Canadian and Mexican imports carry the average US rate. | F12.5 |
| G1 | important | **Fixed.** A real-replay benchmark with all bookings is required (Task 4 fix round). There is a rule-based fallback slice for 18:00. | F12.6 |
| G2 | important | **Fixed.** One independent rebuild of the selected core run happens before freeze. | F12.6 |
| H1 | important | **Fixed (disclosed).** This is an advance-reservation scheduling scenario whose calendar is synthesized from the complete replay, with a horizon of the whole run. Astra's shadow-U alternative is recorded as a deferred causal sensitivity (see note). | F12.7 |
| H2 | important | **Fixed.** "Conservative" is replaced with "effect on realized savings is not signed". Reservation-blocked actions and energy are reported. | F12.7 |
| H3 | minor | **Fixed.** The exact booking is an explicit candidate in every carbon search. | F12.7; Task 5 |
| I1 | minor | **Fixed.** F11's counts are labelled *simulated*, with the synthetic slice named and provenance linked. F11 and F12 are dated separately. | F11, F12 |

**Note on the shadow-U alternative (H1).**
- Real PACE occupancy at or below the shadow-U occupancy of arrived jobs keeps future U slots feasible causally.
- It also forbids any PACE retiming unless another job has vacated PACE. If no job moves away, real occupancy equals shadow occupancy and time-only savings are exactly zero by construction.
- It would therefore answer a different question: what a router can do without advance reservations. That is worth reporting as a sensitivity after 18:00, not as the primary design.

**Gate status:** not passed at r1. A re-check is needed. A second Astra run is outside the pre-approved budget and needs the owner's yes; otherwise a fresh-context Claude re-check runs and the substitution is recorded.
