# Astra results audit, round 1: sealed test-year run (GridPilot)

You are Astra, an independent reviewer in a fresh session. You never edit the work under review. Today is 2026-10-27; judging is Wed 2026-10-28 17:00 MT. Write your review to stdout in the format at the end.

## Scope

The sealed test year [2025-11-01, F_test 2026-10-25T00Z) was opened exactly once at 19:23 MT (run `20261028T012253Z`). Freeze record `config/freeze.json` (sha256 `5941c49de736416d8f92f8836a7b5ca05b94f8c52e8744d31a0946864e735987`, `freeze_commit` `8afed0c65b5e80142843bf74aa8e2a061452607a`, tag `config-freeze` -> `881fce65`); results commit `605e845`. Audit the checkout at origin/main (or the branch `review/results-audit`).

Read first: `AGENTS.md`, then `docs/reviews/2026-10-27-results-audit-packet.md` (the packet), `docs/superpowers/specs/2026-10-27-gridpilot-design.md`, `docs/decisions.md` (D-050 to D-074), `docs/pitch/*.md`, `results/test/metrics.json`, `results/test/extras.json`, `results/test/manifest.json`, `results/test_reads.jsonl`, `results/metrics.json`, `results/extensions.json`, `results/storage.json`, `.git/gridpilot/test_openings.jsonl` (read-only), `config/freeze.json`, and the review files in `.superpowers/sdd/2026-10-27-stage3-freeze-test/` (t12r-review.md, t20r-review.md, t22-review.md, others). The T13 console log is at `/tmp/claude-1001/-home-nvidia-workspace-personal-projects/d7fb1e5c-cee6-4473-88b2-02a108cc36ac/scratchpad/t13-console.log` if readable.

**Do not trust the packet.** It is the preparer's map and may contain errors, omissions or wrong paths. Recompute or re-read everything you rely on from the primary files.

## Hard constraints

- Read-only. Never run `make slice WINDOW=test`, `run_slice --window test`, `make outlook LIVE=1`, or anything that writes `results/`, `config/`, `lab/` or `data/`. Derived review artifacts go only in your own ignored run directory.
- Do not read raw sealed data (`data/raw`, parquet under `data/interim|processed` beyond schema/row counts). Everything needed to audit is in the committed results, logs and code. If you believe a check needs a sealed-value read, say what it would need and why, and do not do it.

## What to verify

1. **Pitch claims vs JSON.** For every number or claim in `docs/pitch/one-pager.md`, `deck-outline.md`, `narrative.md`, `qa.md` (including the `{{TEST: ...}}`, `{{STORAGE: ...}}`, `{{WATER: ...}}` placeholders and what they will be filled with): find the exact JSON field, state the validation and test values, and judge whether the wording is supported. Flag wording that is stale after the opening (for example statements that a scenario was not rerun on the test year), validation numbers presented as test numbers, rounding that changes meaning, and claims with no field behind them.
2. **Seal protocol.** One opening only; every read logged with a purpose; frozen inputs unchanged (hashes in `config/freeze.json`, witness `inputs_sha256`, `manifests_sha256`); `lab/` and `config/` unchanged between the freeze commit and the results commit; no post-hoc change of F, deployed policy S, S ranking, scenario catalog, thresholds or the extras list (D-071, D-073, D-074); the failure rule was respected; the lock is released; the witness (`.git/gridpilot/test_openings.jsonl`) agrees with `results/test_reads.jsonl` (line counts, `n_reads`, session, hashes). Weigh the disclosed incidents: the T11 blocked early attempt (D-060), the T22 metadata touch (D-072), the T20r `data/.wtest` file (D-074), and the validation run id `20261027T160656Z` vs D-056's `20261027T122317Z`. Say whether each could have influenced a test result or a registered choice.
3. **Statistics.** Check the block bootstrap (4-week temporal blocks primary, 2 and 8 exported; 2,000 replicates; 51 weeks), the definition of `saving` (ratio of totals) and of `diff_kg` sign conventions, interval construction, and that the stated intervals are described correctly ("conditional on this one replay", "scenario estimates, not a confidence interval"). Check the H2 verdict (`h2.direction`, `decided`) and the H3 wording (K emits more than S with an interval excluding zero; W and L indistinguishable): is "no demonstrated aggregate benefit from dynamic search" the right phrase, and is the multiple-comparison / selection issue handled? Check that S was selected on validation only and that the test S vs W choice was not reopened. Check the 52-week phase scenarios vs 51-week others. Spot-check internal consistency (sums of per-site energy, remote shares, CO2 totals, contrasts that should be antisymmetric, weekly totals vs policy totals).
4. **Data preprocessing.** Judge whether these rules are sound and applied identically to every policy and to validation and test: null handling; the four-tier truth fill (F14.6) and its tier shares (`kwh_share_tier_ge2`); the demand spike rule (>15% from both neighbours' mean, neighbours within 10%, values <= 0 removed; thresholds set by judgment); publication envelopes (demand +2 h, fuel mix/interchange +48 h, carbon +96 h) as assumed rules rather than receipt times; missing wind/solar as 0 in net load; time zones (UTC replay clock, America/Denver weekly blocks and storage hours, DST handling cut by D-058); revised snapshot instead of vintages; the cohort exclusion count (8,003 jobs in test vs 1,203 in validation) and the arrival cutoff A; the test cutoff F by value completeness.
5. **Overclaiming.** Check wording for: "attributed (EIA consumption-basis) emissions, not avoided emissions" (and that "avoided" appears nowhere else); "simulated replay" present where results are shown; the mobility caveat shown beside the headline (and its test counterpart); storage claims (hourly illustration, the fixed carbon schedule discharges in only part of the rush hours, flat-marginal basis negative, peak-aimed schedule cuts rush import but little CO2, "simulated contribution" not accredited capacity); forecast-skill claims (Utah not reliably better than seasonal average under block intervals; frozen interval coverage below nominal); the price lens is a wholesale scenario with an unregistered California node, not a cost saving; water claims (none made); "sealed test year" vs 358 days; "no 30x" ratio; "proves/confirms" language; the answer to "Did you peek at the test year?" given D-060 and D-072.

## Output format (mandatory)

Report **every** finding. Do not filter, rank-and-cut, or omit anything below some importance bar; triage is a separate step. Include clean results as "checked, no finding" lines so coverage is visible. Each finding:

```
### F<n> <short title>
- Severity: critical | major | minor
- Confidence: high | medium | low
- Area: pitch-claim | seal | statistics | preprocessing | overclaim | other
- Evidence: file + JSON path or line, with the values you read
- Why it matters:
- Correction: exact replacement wording or action
```

Start with a coverage table: for each of the five areas, what you checked and how. Then the findings, then a table of every pitch claim (claim, source field, validation value, test value, supported yes/no/partly). End with exactly one line:

`Verdict: ready` | `Verdict: ready_with_minor_fixes` | `Verdict: not_ready`
