# Stage 3 · T12: independent rebuild, configuration freeze record and tag (final review A2, A3, B4, B5)

Branch `s3/t12` from main **after T11 merges**, because it uses T11's `config/freeze.schema.json` and `seal.load_freeze` / `seal.freeze_tag_message`. **Nothing in T12 reads sealed values**, except the completeness counts in step 3 (counts only, as AGENTS.md allows), and those are logged.

## 1. `make data` (A2)
Add a Makefile target that rebuilds, from `data/raw` into `$(GRIDPILOT_DATA_DIR)`:
- `build_balance`, then `build_interchange` if the pipeline needs it;
- `build_carbon`;
- the geo layers only if the web export needs them.

Document it in AGENTS.md.

## 2. Independent clean rebuild (F12.6)
1. Make a fresh clone of the freeze-candidate commit (main at T12 start) into `/tmp/claude-1001/-home-nvidia-workspace-personal-projects/d7fb1e5c-cee6-4473-88b2-02a108cc36ac/scratchpad/rebuild/repo`.
2. Make a fresh data dir in `.../scratchpad/rebuild/data`. `raw/` is a read-only symlink to the main `data/raw`; `manifests/` is copied from git. `interim/` and `processed/` start empty, and `make data` rebuilds them.
3. In the clone, run `run_slice --no-export --out .../rebuild/runs` for the validation window.
4. Compare against the registered run (the main checkout's `runs/slice/20261027T160656Z`, or `173750Z`, which is its exact reproduction under T10 code):
   - the canonical metrics hash, under the current rule;
   - all 9 ledger hashes;
   - the bookings and cohort hashes;
   - `balance.parquet` and `carbon_hourly.parquet`, by frame equality (`assert_frame_equal`), not bytes.
5. Write the result to `docs/evidence/rebuild-20261027.json`, with every hash on both sides, the clone commit and its `lab/` git tree hash, the commands and wall time.

**A mismatch is a stop.** Report it and do not freeze.

## 3. Test cutoff F from completeness counts (B4; counts only)
- **Data:** the raw EIA CO₂ workbooks for PACE, CISO, BPAT and NEVP, and the EIA-930 balance for PACE demand.
- **Cutoff day:** find the last UTC day D on or before TEST_END − 1 day on which every hour of D exists as a published row for all four BAs' CO₂ and for PACE demand. A row counts as present whether its value is null or not; nulls are handled by the F14.6 fill.
- **F_test** = (D + 1 day) 00:00Z, capped at 2026-11-01T00:00Z.
- **Record:** the per-BA last-row timestamps and D in the freeze record and in a D-entry.
- **Seal discipline:** do the counting through a function that returns **only counts and timestamps, never values**, and make it log one line to `docs/evidence/completeness-20261027.jsonl`.

## 4. Freeze record `config/freeze.json`, valid against T11's schema
- **Deployed policy by the spec §8 rule:**
  1. feasible;
  2. then lowest validation CO₂;
  3. then lower mean wait;
  4. then the order U, G, S, K, W, L.

  Include the rule trace with each policy's values. It should come out as S.
- **L configurations:** `max_leaf_nodes` per series, from the registered forecast run's `metrics.json`.
- **Test fit:** `test_fit_at` 2025-10-29T00:00Z, `test_history_start` 2023-01-01.
- **Test S ranking (B5, with F05):** the mean consumed-basis CI (fsum) over rows from 2023-01-01 **published by fit_at**, i.e. `ts_utc + 1h + 96h <= 2025-10-29T00Z`, from `load_carbon()`, using T11's enveloped `s_ranking`. Record each BA's mean and the window. (Validation used [2022-01-01, 2024-10-29), which is the same rule shifted.)
- **Scenario catalog for test:**
  - primary scenario only;
  - policies U, G, S, K, W, L and H, plus W and L time-only;
  - phase 0;
  - no extensions on test.
- **Snapshot:** `8a1b36b24b91`.
- **Input file hashes** for every input the test path reads.
- **Validation reference:** the registered run id, its canonical hash, and the rebuild result reference.
- `freeze_commit`.

## 5. Freeze writer, not a committed record (the PRs are squash-merged)
- **Build `lab/scripts/write_freeze.py`.**
  - It computes everything in step 4 from the **current HEAD**, sets `freeze_commit` to HEAD's sha, and validates against the schema.
  - It writes `config/freeze.json` and prints the exact git commands for the lead:
    1. commit `config/freeze.json` alone on main;
    2. `git tag -a config-freeze -m "$(seal.freeze_tag_message(<sha>))"`;
    3. push.
  - It refuses on a dirty tree, or when the `lab/` git tree hash recorded in the rebuild evidence (`git rev-parse <commit>:lab`) differs from HEAD's `lab/` tree hash. Comparing trees survives squash merges; comparing commit ancestry would not.
- **On your branch:** run it once in dry-run mode (`--dry-run`, which prints the JSON). Put that output in your report. **Do not commit `config/freeze.json`.**
- **After the lead merges your PR,** the lead runs `write_freeze.py` on main, commits the record, then tags and pushes.
- **Steps 2 (rebuild) and 3 (completeness)** run on your branch. Their evidence files (`docs/evidence/rebuild-20261027.json`, `completeness-20261027.jsonl`) are committed in your PR.

## 6. Decision entry
Add a draft decision entry (next free ID, D-063 or later) to your report (the lead commits it), covering:
- the rebuild result;
- F_test;
- the deployed policy;
- the test S ranking;
- the L configurations.

## Report
Write `/tmp/claude-1001/-home-nvidia-workspace-personal-projects/d7fb1e5c-cee6-4473-88b2-02a108cc36ac/scratchpad/s3-t12-report.md`.

## Addendum: T11's enforced requirements (from the T11 re-checks; binding)
- **Base.** Start T12 from main **after T11 (PR #44) merges**; it brings snapshot `8a1b36b24b91`.
- **S ranking.** Use `eia_co2.s_ranking_at(2023-01-01, 2025-10-29T00Z)`, which applies the 96 h envelope, for the test S ranking. Order by (mean, BA).
- **validation_run.** Use `seal.validation_reference(repo)` at the freeze commit. It must equal `{run_id: 20261027T160656Z, metrics_canonical_sha256: e6ad2635…}`.
- **Balance derivation.** Optionally commit `data/manifests/derived/balance.json` from `seal.balance_derivation` in the freeze-candidate code. Otherwise the documented exception is logged on every run.
- **`write_freeze.py` must produce a record that passes `seal.load_freeze`:**
  - integer L leaves;
  - `test_F` at UTC midnight;
  - `frozen_at` real UTC, never in the future;
  - `scenario_catalog.primary == Scenario.primary().config()`, round-tripped through JSON;
  - all 6 `TEST_INPUTS` in `input_sha256`.
- **Commit and tag sequence, done by the lead on main, with no squash:**
  1. main HEAD is the freeze commit;
  2. commit `config/freeze.json` **alone**, so its only parent is the freeze commit;
  3. `git tag -a config-freeze -m "$(seal.freeze_tag_message(sha))"` on that commit;
  4. `git push origin main config-freeze`;
  5. check that `git ls-remote origin refs/tags/config-freeze` equals the local tag;
  6. **merge nothing else** until T13 has run.
- **T13 runs in the main checkout:** `cd lab && uv run python scripts/run_slice.py --window test`, with a clean tree and no other flags. Afterwards, `git add results/test results/test_reads.jsonl` only (never `-A`, never the lock), then commit and push.
- **Effort:** high for T12 and T12r (D-069).
