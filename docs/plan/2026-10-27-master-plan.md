# GridPilot master plan: to judging (Wed 2026-10-28 17:00 MT)

This is the plan that runs from now to judging. Supersedes the timeline parts of `2026-10-27-plan-v2.md` and the Stage 3 plan. The task list is `docs/plan/tasks.csv`, the single source of truth for status and times. The project board renders it.

All times are MT, from the system clock (D-065 records the earlier clock drift). "ETA" is an estimate; "done" is a commit or report time.

## Goal
Win the Torus bounty with an honest, rigorous and clear story.

> In a simulated replay, moving Utah's AI work to cleaner grids cuts attributed CO₂ by about 22.5%, while waiting in Utah alone saves under 1%. That holds only if the large jobs can move. Storage at the Utah site is how to treat the work that can't.

The sealed test year confirms or corrects the result once, and every number is labelled.

## Milestones
| When | Milestone | Status |
|---|---|---|
| Tue 07:16 | `checkpoint-tue`: checkable build on validation data | done |
| Tue 14:18 | Spec approved; test year may open once after the freeze (D-059) | done |
| Tue ~18:30 | Seal machinery and storage piece reviewed and merged | in progress |
| Tue ~21:30 | Freeze: independent rebuild matches, `config-freeze` tagged | planned |
| Tue ~22:15 | Test year run once, logged, exported | planned |
| Wed ~01:00 | Astra results audit finished (overnight) | planned |
| Wed ~11:00 | Deck and one-pager with test numbers; dashboard final | planned |
| Wed 13:00 | **Experiments freeze**: no new numbers | fixed |
| Wed 14:00 | **Numbers and deck locked** | fixed |
| Wed 14:00–16:30 | Three timed rehearsals offline on the Mac | planned |
| Wed 17:00 | Judging at Aernata | fixed |

## Critical path
T11 seal fixes → re-check → T10b storage → review → T12 rebuild and freeze writer → review → freeze tag → T13 test run → audit → dispositions → deck numbers → lock → rehearse.

Anything not on this path, such as T14 water and T15 toggle/budget, is built in parallel and merged only after T13. That way it can never block the freeze or the test run.

## Rules that govern the plan
- **The seal:** the test year opens exactly once, through `make slice WINDOW=test`, at the frozen commit. Every read is logged. A rerun needs a logged reason (D-059).
- **Freeze discipline:** no `lab/` change between the independent rebuild and the test run. Web and docs changes after the freeze would also block the entry point's clean-HEAD check, so they wait until T13 is done.
- **Honesty:**
  - "simulated replay";
  - "attributed, not avoided";
  - "deadlines met by construction";
  - S's own estimate and interval as the headline;
  - the mobility caveat next to the headline;
  - illustrative pieces (storage, peak relief, water) are labelled and kept apart from the registered result.
- **Reviews:** every merge gets an independent review. The results audit is the last Codex run planned.
- **Concurrency:** at most 3 agents at once.
- **Hard stops:** experiments freeze Wed 13:00; numbers lock Wed 14:00. Anything unfinished is cut, and listed as not run.

## Owner actions
| When | What |
|---|---|
| Tonight | Mac check: `git pull && make web && cd web && npm run preview`, then Chrome at http://127.0.0.1:4173. Look at map smoothness and fonts. |
| Tonight | Read the pitch drafts in `docs/pitch/` once they land, about 16:00, and comment. |
| Wed morning | Review the audit dispositions and the deck. |
| Wed 14:00–16:30 | Rehearse three times. |

## Risks and mitigations
| Risk | Mitigation |
|---|---|
| The rebuild doesn't match | The freeze stops; fix and rebuild. The 21:30 target leaves room before midnight. |
| The test run fails mid-way | The logged rerun path, with a reason (D-059). Results come no later than early Wed. |
| The test numbers differ from validation | Report them honestly. Validation is development evidence; test is confirmatory. The pitch placeholders absorb either outcome. |
| The demo fails on the Mac | Mac check tonight. Fallback: screenshots plus a short screen recording made Wed. |
| Time pressure Wednesday | Pitch drafted tonight; the audit runs overnight. Cut order: water, then the toggle, then extra polish. |
| Agent clock drift | Plans use system-clock times only (D-065). |

## Decisions in force
D-050 (claim frame), D-053 (Utah palette), D-058 (extensions), D-059 (spec approved; seal opens once), D-061 (storage), D-062 (S-ranking envelope), D-063 (pitch tonight; water), D-064 (toggle, budget, water after test). See `docs/decisions.md`.
