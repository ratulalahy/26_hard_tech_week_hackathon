# Task 7 amendments (lead rulings; binding over the brief; spec §15 F11–F14 on main)

**Windows (F14.4).** No "F2 window".
- Validation: init 2024-10-17T00Z, eval_start 2024-11-01T00Z, F = 2025-10-24T00Z.
- Fallback: init 2025-07-10T00Z, eval_start 2025-07-25T00Z, F = 2025-10-24T00Z.
- `run_slice.py --window {validation,fallback}`. The default is validation. Use the fallback only if validation cannot finish (F13.5). The fallback never replaces the registered selection.

**Pipeline, in order.**
1. **Jobs.** `replay(init, F)` at phase 0.
2. **Bookings.** `u_bookings` under the primary scenario, plus the F14.1 U-changing scenarios: batch delay 0 h and 24 h; no flexible jobs; all candidates flexible; 1.25× home capacity (rounded to an 8-GPU node).
3. **Common A (F13.2, F14.1).** A = min over those scenarios of the first arrival at which any deadline > F. Drop that simultaneous group and every later arrival, then recompute the primary bookings on the truncated stream. Assert that the prefix bookings are unchanged (U is causal).
   - Record before any grid scoring: init, A, cohort IDs hash, booking hash, drain coverage.
   - Only the primary scenario's policies run before 18:00; the sensitivity scenarios contribute only to A.
4. **Scoring truth fill (F14.6).** New module `lab/src/gridpilot/data/truth_fill.py`.
   - Output: a frame `ba, ts_utc, ci_g_kwh, tier` over [init, F) for the four core sites.
   - Tier 1 is the EIA consumption basis. Tier 2 is the EIA production basis, same hour. Tier 3 is our EIA-930 fuel-mix CI, same hour; move the emission factors and the production-CI formula from `lab/scripts/recon_grid.py` into the package and reuse them, keeping recon_grid working. Tier 4 is the mean of tier-1 values at the same UTC hour over the 7 preceding days.
   - Pre-seal only (it raises at or after TEST_START).
   - Tests on synthetic gaps for each tier.
   - Report the tier counts per BA.
   - `closed_intervals` is built only from hours still missing after tier 4; expect none, and report any.
5. **Support pre-check.** Run `support_check` on the bookings and the warm-up ledger. It is a hard gate: any failure stops the run.
6. **Policies.** U, G, S, K, W, L and H on the primary scenario.
   - S's ranking is computed from training rows (2022-01-01 to 2024-10-29) of `load_carbon`: mean consumed CI ascending, with PACE included at its rank. Record it.
   - Time-only W and L use destination capacity 0.
   - H is a diagnostic, never a contender.
7. **Accounting.**
   - `score` for each policy, `relaxed_bound`, and `bound_ok` (assert it holds).
   - `weekly` totals, then `paired_block_bootstrap` for each contrast vs U, S and W.
   - `h2_decision(W, L)` on the full phase-0 cohort (F14.3).
   - `influence` for k = 1, 5 and 10.
   - `kwh_share_tier_ge2`, moved share, and `common_support` (report its size; the sensitivity rerun comes after 18:00).
8. **Export.** Write to `runs/slice/<UTC>/`, atomically; `runs/` is gitignored. Then copy the results artifacts into `results/`, committed.
   - Every numeric leaf is in the §11 envelope with an evidence class:
     - simulated: policy outcomes;
     - observed: truth tier 1;
     - modeled: fills and the bound;
     - forecast: K/W/L values;
     - assumed: flex flags, power, PUE, transfer;
     - measured: forecast errors and runtimes.
   - `manifest.json` carries the claim-frame text (F12.5, F12.7; D-050): "simulated advance-reservation scheduling scenario; baseline-relative deadlines; exact declared runtimes; runtime uncertainty untested; EIA-attributed (consumption-basis) emissions; conditional temporal block-resampling intervals".
   - `manifest.json` also carries the limitations: the forecast limitation text from Task 2, and the EIA import convention.
   - If n weeks ≤ 8, label the b = 8 interval "low-n".
   - Include realized flex shares by jobs and by GPU-hours (Task 3 parked item 10). Label `flexible`, `max_delay_s` and `mobile` as assumed.
9. **Timing (F13.5).** Record wall time for: forecast construction, bookings, each policy, accounting and export. Print the policy table.

**Tests**, in addition to the brief's two:
- a prefix-cohort test on a toy stream (F13.2);
- a truth-fill tier test;
- a check that no artifact timestamp is at or after TEST_START;
- a check that the manifest carries the claim frame.

**Not before 18:00:** the F14.7 blocked diagnostic; phases 49 and 98; the sensitivity scenarios' policy runs; production-basis repricing (it comes first after the checkpoint); the shadow-U and missingness-blind sensitivities; the F12.6 rebuild (before freeze).

**Makefile:** a `make slice` target. Add it to AGENTS.md Commands only once it works.
- **Bound check (T6 #12):** compute the cohort gap as math.fsum of per-job (policy − bound) differences, and assert it is ≥ −1e-6 kg. Report the minimum per-job gap. The mask passed to TruthTable must come from the same filled truth (it raises otherwise). Pass `warm=` to score.
