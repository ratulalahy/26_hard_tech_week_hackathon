# Stage 3 · T11 fix round 2 (the last round; from the adversarial re-check of f0450a5)

Rebase `s3/t11` onto current `origin/main`. Fix the items below, then push. Synthetic temp repos only, **never `--window test` on real data**.

## Required
- **N1. Shared witness.** Before the first sealed read, append the invocation line to `$(git rev-parse --git-common-dir)/gridpilot/test_openings.jsonl`, append-only and fsynced. `prior_openings` reads the witness as well as the repo paths.
- **N2. Lock in the git common dir.** Move the lock to `<git-common-dir>/gridpilot/test_mode.lock`, with a pid-liveness check. Check (a) names a stale lock explicitly. Document the recovery in the module docstring and in `AGENTS.md`: delete the lock, commit only the log, rerun with `--rerun-reason`.
- **N3. Lead ruling: a bug-fix rerun is allowed.** With `--rerun-reason`, accept a different freeze record when all of these hold:
  - the decision fields are identical: `deployed_policy`, `L_max_leaf_nodes`, `s_ranking`, `test_F`, `scenario_catalog`, `input_sha256`, `snapshot_id`;
  - the new `freeze_commit` descends from the old one;
  - only `freeze_commit`, `frozen_at` and `validation_run` differ.

  Log both record shas and the diff of their fields.

## Cheap, do them too
- **N4.** `git log --all --reflog --full-history -- …`.
- **N5.**
  - In real use, origin must exist and equal `https://github.com/ratulalahy/26_hard_tech_week_hackathon.git`; log the URL.
  - Match the exact refname line.
  - Set `GIT_TERMINAL_PROMPT=0`, and retry once.
- **N6.** `Session.closed = True` in `finally`; `active()` returns None for a closed session.
- **N7.** Re-check `prior_openings` inside `test_mode`, under the lock.
- **N8.** In synthetic mode, refuse a `results_dir` under `paths.REPO_ROOT`, and refuse inputs whose realpath is under `paths.DATA_DIR`.
- **N11.** Add `s_ranking_at(start, fit_at)` for T12, and require `window == [TEST_HISTORY_START, TEST_FIT_AT]` in the loader.

## Deferred (accepted risk: we are the only operators; record it in the report)
N9 and N10 (guard and AST coverage of exotic forms), N12 (directory chmod), N13 (`.venv` / `__pycache__`), N14 (strict balance derivation).

Append "Fix round 2" to the report. Target: finish by about 17:30 MT.
