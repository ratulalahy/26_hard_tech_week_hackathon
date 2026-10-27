# GridPilot master plan: to judging (Wed 2026-10-28 17:00 MT)

This is the master plan from now to judging. **The task list is `docs/plan/tasks.csv`**, the single source of truth for status and times. The project board renders it: `scripts/render_board.py` writes `docs/status/board.html` and the private board link. All times are MT, from the system clock (D-065). "ETA" is an estimate; "done" is a commit or report time.

## 1. What we're solving
An AI cluster in Utah (PACE, the balancing area serving much of Utah) runs around the clock on a coal-heavy grid. The operator has three kinds of flexibility: **wait** for cleaner hours, **move** work to cleaner regions, or **store** energy. Which one cuts emissions, by how much, and what limits it?

**Our proposition.** A day-ahead grid "traffic report", a router that uses it, and a planning lens for operators and the utility.

**Validation findings** (simulated replay, attributed emissions):
- Moving cuts about 22.5% (S: 22.6% [18.4, 26.8]). Waiting in Utah alone saves under 1%.
- If only jobs of ≤ 8 GPUs can move: 3–4%. Moving small jobs plus 4 MWh of storage: about 7.3%.
- On a flat marginal basis, storage adds CO₂.
- Forecast choice shows no demonstrated benefit. The sealed test year confirms or corrects all of this once.

## 2. Data and periods
| Data | Period | Use |
|---|---|---|
| EIA-930 hourly balance (demand, generation by fuel, interchange) | 2022 → Oct 27 2026 (snapshot) | stress, fuel mix, forecasts |
| EIA hourly CO₂ per BA (PACE, CISO, BPAT, NEVP) | same | carbon truth (modeled, EIA estimate) |
| Acme "Seren" GPU-cluster trace (2,288 GPUs, about 818k jobs, 2023) | replayed in a cycle onto 2024–26 | workload |
| Electricity Maps BA shapes, Natural Earth | static | map |
| Open-Meteo archived weather | 2024–26 | descriptive context only (T16) |
| NREL and LBNL water references | static | water illustration (T14) |

**Splits:**
- Training: up to Oct 2024.
- **Validation:** Nov 2024 – Oct 2025. All results so far.
- **Test, sealed:** Nov 2025 – Oct 2026. Opens once, after the freeze.

## 3. Milestones
| When | Milestone | Status |
|---|---|---|
| Tue 07:16 | `checkpoint-tue` | done |
| Tue 14:18 | Spec approved; test may open once (D-059) | done |
| Tue 15:21 | Storage and peak relief merged (D-061, D-067) | done |
| Tue ~16:30 | Seal machinery re-checked and merged | in progress |
| Tue ~20:30 | Independent rebuild matches; freeze record ready | planned |
| Tue ~21:30 | `config-freeze` tagged (go/no-go) | planned |
| Tue ~22:15 | Test year run once, logged, exported | planned |
| Tue ~22:15 → Wed 00:30 | Post-test merges: toggle and budget, water, toughest days; dashboard test view | planned |
| Wed ~01:00 | Astra results audit (overnight) | planned |
| Wed 07:00–11:00 | Audit dispositions; deck, one-pager and dashboard final | planned |
| **Wed 13:00** | **Experiments freeze** | fixed |
| **Wed 14:00** | **Numbers and deck locked** | fixed |
| Wed 14:00–16:30 | Three timed rehearsals on the Mac | planned |
| **Wed 17:00** | **Judging** | fixed |

## 4. Workstreams (IDs as in tasks.csv)
- **Freeze and test (critical path):**
  - T11 seal fixes → T11r re-check;
  - T12 `make data`, independent rebuild and freeze writer → T12r review;
  - FZ freeze tag;
  - T13 one logged test run;
  - AP audit packet → AU Astra audit → AD dispositions.
- **Illustrative extras.** Validation only, labelled, merged after T13 unless noted:
  - T15: mobility/capacity toggle, flexibility budget, and Astra copy fixes (D-064);
  - T14: water footprint (D-063, D-064);
  - T16: toughest grid days, with temperature context (D-066);
  - T17: assumptions-vs-reality notebook (D-068), before the freeze if ready.
- **Pitch:**
  - P1 drafts (done);
  - O1 owner review;
  - P2 test and storage numbers, deck (Slides), one-pager with the operator playbook;
  - R1 rehearsals.
- **Dashboard:** MG merge and test view; UI final copy plus the parked cosmetic fixes.

## 5. Rules
- **The seal:** the test opens exactly once, through `make slice WINDOW=test` at the frozen commit. Every read is logged; a rerun needs a logged reason (D-059).
- **Freeze discipline:** no change anywhere between the rebuild and the test run except the freeze record. All extras wait until T13 is done.
- **Honesty:**
  - "simulated replay";
  - "attributed, not avoided";
  - "deadlines met by construction";
  - S's own estimate and interval as the headline;
  - the mobility caveat next to it;
  - illustrative pieces labelled and kept separate;
  - negative results kept (D-068).
- **Reviews:** every merge gets an independent review. Codex: the results audit only, unless the owner says otherwise.
- **Concurrency:** at most 3 agents at once. The queue order is T12 > T17 > T16.
- **Cut order if time is short:** T14 water, then T16 toughest days, then UI polish. Never cut the freeze, test, audit or rehearsal.
- **Hard stops:** experiments freeze Wed 13:00; numbers lock Wed 14:00.

## 6. Open owner items
| ID | What | By |
|---|---|---|
| O1 | Read the pitch drafts (`docs/pitch/`) | tonight |
| O2 | Mac check: `git pull && make web && cd web && npm run preview` | tonight |
| O3 | High effort for the freeze, test and audit agents? (the lead recommends yes) | before T12, about 16:30 |
| — | Optional: the live "tomorrow's traffic report" card for Thursday Oct 29 | Wed AM, if wanted |

## 7. Risks
| Risk | Mitigation |
|---|---|
| The rebuild doesn't match | Stop and fix; the slack before midnight covers it |
| The test run fails mid-way | Logged rerun with a reason |
| Test differs from validation | Report it honestly; the placeholders absorb either outcome |
| The demo fails on the Mac | Mac check tonight; screenshot and recording fallback |
| Wednesday time pressure | Pitch drafted tonight, audit overnight, cut order above |
| Clock drift | System-clock times only (D-065) |

## 8. Decisions in force
D-050 claim frame · D-053 palette · D-058 extensions · D-059 spec approved and the seal opens once · D-061 storage · D-062 S-ranking envelope · D-063 pitch tonight and water · D-064 toggle, budget and water after test · D-065 plan and clock · D-066 toughest days · D-067 storage headline · D-068 assumptions notebook. The full log is `docs/decisions.md`.
