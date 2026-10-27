# AGENTS.md

Rules for every agent on this repo, Claude Code and Codex. They are written once, here; `CLAUDE.md` imports this file.

## What this is

A 48-hour hackathon entry for the Torus bounty at Hard Tech Week. Judging is Wed 2026-10-28 at 5 PM MT, on creativity, clarity of insight and execution.

The entry has two parts:
- a day-ahead traffic report for the US grid;
- a simulated router that keeps AI jobs out of the grid's rush hour.

The headline is Option 2, Compute Follows the Sun; the traffic report is its engine. Utah's PACE is the hero region.

The owner approved emissions-first scheduling, with deadlines and identical completed work as constraints. Delivery is PACE first with roughly ten BAs in the overview; full experiment depth is not required for every overview region. The decision record is in `docs/brief.md`.

Key documents:
- the brief: `docs/brief.md`;
- the approved plan: `docs/plan/2026-10-27-plan-v2.md` (v1 kept as history);
- the independent design proposals: under `docs/superpowers/specs/`; only the owner-approved, reconciled spec authorizes implementation and test evaluation.

## Roles

- **Owner:** product decisions, gate approvals, the pitch.
- **Claude** (lead; checkout `26_hard_tech_week_hackathon`): downloads, the data pipeline, experiment code, the dashboard, and merges to `main`.
- **Codex** (planning partner; checkout `26_hard_tech_week_hackathon-codex`, branch `codex/planning`): its own version of the experiment spec, evidence review, and the presentation narrative.
- **Codex reviews** run through `scripts/review.sh` in separate fresh sessions, and never edit.
- **Between agents:** `docs/HANDOFF.md`. Each topic has one source of truth:
  - rules: here;
  - decisions: `docs/decisions.md` is the log of every decision (D-xxx, with evidence); `docs/brief.md` keeps the bounty and the owner's product decisions table;
  - the plan: `docs/plan/`;
  - the design: the approved, reconciled spec. Independent proposal files are alternatives, not parallel sources of implementation requirements.
  - do not create separate `CONTEXT.md` or `PLAN.md` copies; conversation decisions belong in the brief, execution changes in the plan, and status in the handoff.

## Layout

- `lab/`: Python 3.12 uv project (package `gridpilot`) for data, forecasting, simulation and evaluation. Tests are in `lab/tests/`.
- `results/`: small committed artifacts the dashboard reads (JSON or Parquet).
- `web/`: the dashboard (Vite, React, TypeScript).
- `data/`:
  - `raw/`, `interim/` and `processed/` are gitignored;
  - `data/manifests/<source>.json` is committed and records each download's URL, retrieval time and sha256.
- `docs/`: brief, plan, data profile, spec, implementation plans, Codex reviews (`docs/reviews/`), and the agent handoff (`docs/HANDOFF.md`).
- `scripts/review.sh`: Codex reviews (see `.claude/skills/codex-gates/SKILL.md`).

## Commands

- `cd lab && uv run pytest` runs the tests.
- `make test` does the same from the repo root.
- `make data` rebuilds the pipeline's derived tables from `data/raw` into `$GRIDPILOT_DATA_DIR`: `interim/eia930/balance.parquet` (from the EIA-930 BALANCE files), then `processed/carbon/carbon_hourly.parquet` and its lineage (from the core BA workbooks, truncated at the seal). About ten seconds. Interchange and the map layers are not rebuilt: the pipeline does not read them, and `make web` keeps the committed map layers. The freeze record pins these tables by hash, so it refuses to replace an existing table (`ARGS=--overwrite` forces it): rebuild into a fresh data dir whose `raw/` links to the shared raw cache and whose `manifests/` is copied from git, never over the shared one. `scripts/rebuild_check.sh` does exactly that for the independent rebuild (F12.6), and `scripts/rebuild_compare.py` writes its evidence, `docs/evidence/rebuild-<date>.json`.
- `make freeze` writes the configuration freeze record `config/freeze.json` from HEAD (`lab/scripts/write_freeze.py`) and prints the lead's commit, tag and push commands; `make freeze ARGS=--dry-run` prints the record instead. It refuses on a dirty tree, an existing record or tag, any prior opening of the sealed window, a `lab/` git tree that differs from the one the committed rebuild evidence rebuilt, or inputs that differ from what the rebuild and the completeness count saw. The test cutoff comes from `lab/scripts/completeness_cutoff.py --log docs/evidence/completeness-<date>.jsonl`, which counts rows and timestamps only (never sealed values) and logs every call.
- `make notebooks` re-executes the evidence notebooks in `notebooks/` in place and exports HTML copies to `docs/evidence/`. It reads the cached data through `GRIDPILOT_DATA_DIR` and takes about five minutes. Each notebook ends with the decisions it supports in `docs/decisions.md`.
- `make slice` runs the registered phase-0 validation experiment (U, G, S, K, W, L, H and time-only W, L) and exports the evidence-enveloped `results/*.json` the dashboard reads. Run directories go to `runs/slice/<UTC>/`. It reads the cached data through `GRIDPILOT_DATA_DIR` and takes about 20 minutes. `make slice WINDOW=fallback` runs the 91-day fallback window, which never replaces the registered selection.
- `make slice WINDOW=test` is the only way to open the sealed test window (`run_slice --window test`; add `ARGS='--rerun-reason "<text>"'` to rerun over a completed run). It runs once, after the freeze, and refuses with a non-zero exit and the reason unless HEAD is the freeze commit in a clean tree, `config/freeze.json` matches the annotated tag `config-freeze`, every input hash matches the freeze record (schema: `config/freeze.schema.json`) and `results/test/` holds no completed run. Every grid read goes through `gridpilot.seal.sealed_read` and is logged in `results/test_reads.jsonl`; outputs go to `runs/test/<UTC>/` and `results/test/*.json`.
  - Every invocation is also recorded in a witness that all worktrees share, `$(git rev-parse --git-common-dir)/gridpilot/test_openings.jsonl`. The session lock sits next to it, as `gridpilot/test_mode.lock`.
  - **If a session crashes**, the refusal names a stale lock. To recover: delete the lock file, commit only `results/test_reads.jsonl` without editing it, then rerun with `ARGS='--rerun-reason "<what crashed, and the fix>"'`.
  - **If the fix changes code**, write a new freeze record and tag it. The rerun accepts it only under all of these conditions:
    - every decision field is unchanged;
    - the new `freeze_commit` descends from the old one;
    - only `freeze_commit`, `frozen_at` and `validation_run` differ.

    The rerun logs both record hashes.
- `make profile` writes `results/grid-profile.json`, the dashboard's validation-year grid context (typical-day carbon by month, Utah's July weekday load, the top-100 net-load hours) and `results/workload-profile.json` (how much energy and saving sits in the largest jobs, recomputed from the registered run's ledgers). It reads the cached data through the seal and takes about a minute. **It needs `RUN_DIR=`**, the run directory whose name is the `run_id` in `results/manifest.json`. Run directories are gitignored, so a fresh worktree has none; the make recipe runs inside `lab/`, so give an absolute path, for example `make profile RUN_DIR=/home/nvidia/workspace/personal/projects/26_hard_tech_week_hackathon/runs/slice/20261027T122317Z`.
- `make ext-runs RUN_DIR=<abs path of the registered run>` runs the seven D-058 extension scenarios (phases 49 and 98; destination capacity 0 and 1,024; transfer 120 min; batch delay 24 h; mobility ≤ 8 GPUs) in parallel into `runs/ext/<name>/<UTC>/` (default: the `runs/ext` next to `RUN_DIR`), with the registered run's forecasts. About 12 minutes and a peak of about 3 GB per process; it fails if any scenario fails. Validation only.
- `make extensions RUN_DIR=<abs path of the registered run> REPRO_RUN=<abs path of a primary run made by this code>` writes `results/extensions.json` (production-basis repricing and common support from the registered ledgers, each extension's latest run, and the primary reproduction) and updates `manifest.not_run`. A missing extension run fails it; `ALLOW_MISSING=1` exports it as `not_run` (the 21:00 hard stop). Run it at a clean commit. About a minute.
- `make storage RUN_DIR=<abs path of the registered run>` writes `results/storage.json`, the illustrative storage piece ("move what you can, store for what you can't", D-061): a battery at the Utah cluster run against the registered U ledger's hourly load and the mobility ≤ 8 GPUs run's W ledger (from `EXT_ROOT`, default the `runs/ext` next to `RUN_DIR`), with a fixed training-year schedule and a daily hindsight heuristic (each day planned on its actual carbon). It adds the manifest's `storage` pointer. Validation only; not part of the registered experiment. About 7 seconds.
- `make web` copies `results/*.json` and the map layers into `web/public/data/` (committed) and builds the offline dashboard into `web/dist`. It installs the web dependencies itself (`npm ci`) when `web/node_modules` is missing, so a fresh clone needs no separate step. To serve it: `cd web && npm run preview`, then open http://127.0.0.1:4173/.

Every command listed here must work. Add a command when its target lands.

## Data rules

- **Sealed test window: 2025-11-01T00:00Z to 2026-11-01T00:00Z.** Use the boundaries in `gridpilot.splits`.
  - The window ends at the availability cutoff: the last complete day in the frozen data snapshot. Results state the days they cover.
  - It opens only after the spec is approved **and** the model and policy configurations are frozen at a recorded commit. Until then, nothing reads its values except completeness checks (row counts, missing hours).
  - Numbers shown at G2 and G3 are validation results.
  - Once open, the window is read only through the test-evaluation entry point. Each read is logged with its input, code and config hashes and its purpose.
- **No lookahead.** A forecast issued at time t uses only data published before t. Weather features come from archived forecasts, never from observed weather.
- **Evidence labels.** Every field that reaches `results/`, the UI or a slide is labeled `observed`, `measured`, `forecast`, `modeled`, `assumed` or `simulated`. The definitions are in `.claude/skills/hackathon-evidence/SKILL.md`.
- **Raw data is immutable.**
  - Downloads go to `data/raw/<source>/` and are recorded in that source's manifest.
  - Cleaning writes to `data/interim/` or `data/processed/`.
  - Experiment outputs are written atomically (temp file, then rename) and versioned by run id or content hash. Each run writes only into its own run directory.
  - Static reference assets (cleaned source tables, map layers) keep fixed paths. They are written atomically, and their sha256 is recorded in the source manifest.
  - Code finds the data directory through `gridpilot.paths`. The `GRIDPILOT_DATA_DIR` environment variable overrides it; worktrees point it at the main checkout's `data/`.
  - For Codex planning/review, that shared directory is read-only. No duplicate downloads, cleaning writes, or experiment outputs go there; use the planning checkout's own ignored run directory for any derived review artifacts.
  - A source manifest that is still changing is not a frozen snapshot. Record its hash and file inventory before analysis, and verify them again afterwards.
- **Free and open data only.**
  - No keys in git: `.env` is ignored, and `.env.example` lists the variable names.
  - Every source's license is recorded in its manifest.

## Experiments

Follow `.claude/skills/hackathon-evidence/SKILL.md`:
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

Task skills live in `.claude/skills/<name>/SKILL.md`. `.agents/skills` links to the same folder, so Claude and Codex read the same files.
