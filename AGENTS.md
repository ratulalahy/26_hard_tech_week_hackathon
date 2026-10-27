# AGENTS.md

Rules for every agent on this repo, Claude Code and Codex. They are written once, here; `CLAUDE.md` imports this file.

## What this is

A 48-hour hackathon entry for the Torus bounty at Hard Tech Week. Judging is Wed 2026-10-28 at 5 PM MT, on creativity, clarity of insight and execution.

The entry has two parts:
- a day-ahead traffic report for the US grid;
- a simulated router that keeps AI jobs out of the grid's rush hour.

Key documents:
- the brief: `docs/brief.md`;
- the approved plan: `docs/plan/2026-10-26-hackathon-plan.md`;
- the spec, once written: under `docs/superpowers/specs/`.

## Layout

- `lab/`: Python 3.12 uv project (package `gridpilot`) for data, forecasting, simulation and evaluation. Tests are in `lab/tests/`.
- `results/`: small committed artifacts the dashboard reads (JSON or Parquet).
- `web/`: the dashboard (Vite, React, TypeScript).
- `data/`:
  - `raw/`, `interim/` and `processed/` are gitignored;
  - `data/manifests/<source>.json` is committed and records each download's URL, retrieval time and sha256.
- `docs/`: brief, plan, data profile, spec, implementation plans, and Codex reviews (`docs/reviews/`).
- `scripts/review.sh`: Codex reviews (see `.claude/skills/codex-gates/SKILL.md`).

## Commands

- `cd lab && uv run pytest` runs the tests.

Every command listed here must work. Add a command when its target lands.

## Data rules

- **Sealed test window: 2025-11-01T00:00Z to 2026-11-01T00:00Z.** Use the boundaries in `gridpilot.splits`.
  - Until the spec is approved and a model or policy is final, nothing reads values from this window except completeness checks (row counts, missing hours).
  - After that, it is read only through the test-evaluation entry point, which logs every read.
- **No lookahead.** A forecast issued at time t uses only data published before t. Weather features come from archived forecasts, never from observed weather.
- **Provenance labels.** Every input and output field is `measured`, `derived`, `assumed` or `simulated`. The label travels into `results/` and the UI.
- **Raw data is immutable.**
  - Downloads go to `data/raw/<source>/` and are recorded in that source's manifest.
  - Cleaning writes to `data/interim/` or `data/processed/`.
  - Code finds the data directory through `gridpilot.paths`. The `GRIDPILOT_DATA_DIR` environment variable overrides it; worktrees point it at the main checkout's `data/`.
- **Free and open data only.**
  - No keys in git: `.env` is ignored, and `.env.example` lists the variable names.
  - Every source's license is recorded in its manifest.

## Experiments

Follow `.claude/skills/experiment-protocol/SKILL.md`:
- one run directory per run, holding the config, git SHA and metrics;
- fixed seeds;
- anything that reaches `results/` can be rebuilt from the raw cache.

## Reviews

- A reviewer reports **every** finding. Each one has a severity (critical, major or minor), a confidence (high, medium or low), the evidence, and a correction.
- The review ends with one verdict line: `Verdict: ready`, `Verdict: ready_with_minor_fixes` or `Verdict: not_ready`.
- Never filter to "important" findings. Triage is a separate step.
- Reviewers never edit the work they review.
- Every finding gets a disposition, recorded in `docs/reviews/`: fixed (with the commit), rejected (with the reason) or deferred.

## Git

- `main` is always runnable.
- Each task gets its own branch, in its own worktree when work runs in parallel, and ends in a PR.
- The lead (Claude) merges after the review the task requires.
- Never force-push `main`. Commit messages say what changed and why.

## Autonomy

Agents proceed on reversible work without asking, overnight included.

They stop and ask the owner before:
- changing the direction;
- cutting a Must item;
- making anything public (repo visibility, hosting, tunnels, uploads);
- spending money.

Status reports cite evidence: test output, metric files, commit SHAs.

## Skills

Task skills live in `.claude/skills/<name>/SKILL.md`. Claude loads them; Codex reads them by path when a task names them.
