# Stage 3: extensions, configuration freeze and sealed test evaluation

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Each task has an amendment-style brief in `docs/superpowers/plans/amendments/stage3-T<N>.md`.

**Goal:** finish the validation evidence the owner selected, freeze a reproducible configuration, and then run the sealed test year exactly once through a logged entry point.

**Spec:** `docs/superpowers/specs/2026-10-27-gridpilot-design.md`, §15 F1–F14, which is binding.

**Inputs:**
- the Stage 2 final review (findings A1–A17, B1–B7, C1–C10; recorded in the SDD ledger and summarised in each task brief);
- D-057;
- the owner's extension choice, D-058.

## Global constraints
- The seal holds until T12 records the freeze and T13 runs.
- No path other than T11's `sealed_read()` may read rows at or after 2025-11-01T00:00Z, and it logs every read to `results/test_reads.jsonl`.
- Extensions are validation only, with a hard stop at Tue 21:00 MT (F9). Anything unfinished is marked `not_run` with a reason.
- Every exported number is enveloped and carries an evidence class (spec §11).
- Wording follows F12.5, F12.7, D-050 and D-055.

## Tasks
| # | Task | Findings | Depends on |
|---|---|---|---|
| T9 | Pre-freeze copy, label and export fixes, in the dashboard and the exports | A4–A12, A14, A16, A17 (docs), C4–C7 | — |
| T10 | Scenario and window refactor of `run_slice`, plus the owner-selected extensions on validation: production-basis repricing, common support, phases 49 and 98, and sensitivities (destination capacity 0 and 1,024; transfer 120 min; batch delay 24 h; mobility limited to jobs of 8 GPUs or fewer). Output: `results/extensions.json`. Also the dashboard's "Challenge it" step. | A13, F9 | T9 |
| T11 | Seal machinery: a Window object through every layer, `sealed_read()` with a JSONL log, the test entry point (`run_slice --window test`, refusing unless at the freeze commit, with a clean tree and matching hashes), the F8 static guard test, a `results/test/` namespace, and a UI parametrised by window | B1–B3, B6, B7 | T10's refactor (same files) |
| T12 | Freeze: `make data`, an independent clean rebuild compared by canonical hashes, the final registered validation run, the freeze record `config/freeze.json` (deployed policy by the §8 rule, L configurations, test F from completeness counts, the test S-ranking and fit windows), a D-entry, and the tag `config-freeze` | A2, A3, B4, B5 | T9, T10, T11 |
| T13 | One sealed test run through the entry point, its export and dashboard view, then the Astra results audit (pre-approved run 3) | — | T12 |

## Order
1. T9 runs now.
2. T10 follows; its compute runs in parallel on the DGX.
3. T11 starts once T10's refactor lands.
4. T12 runs ~21:00–23:00.
5. T13 runs overnight.
6. The Astra audit runs Wed 08:00–11:00; experiments freeze at 13:00.
