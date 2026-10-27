# Stage 3 · T11: seal machinery, the test entry point and the read log (final review B1–B3, B6, B7)

Branch `s3/t11` from T10's Part A commit (or main once T10 merges). **Nothing in this task reads sealed values.** Tests use synthetic sealed rows in temp dirs; the real test run is T13, after the freeze.

## B2: one explicit window switch through every layer
- A `Window` object, introduced by T10, carries `name` ∈ {validation, fallback, test} and its upper bound. Every layer takes it explicitly and defaults to validation:
  - eia_co2;
  - truth_fill;
  - forecast;
  - carbon_search (the grid bounds);
  - accounting (TruthTable, support_check);
  - results (the sealed-timestamp checks);
  - grid_profile;
  - run_slice.
- Test-mode upper bound: F_test (from the freeze record), never past TEST_END.
- **Test truth goes to a separate path:** `data/processed/carbon/carbon_hourly_test.parquet`, built only by the entry point through `sealed_read`. The validation parquet stays truncated at TEST_START.
- **Forecast test path:** fit at TEST_FIT_AT = 2025-10-29T00:00Z, with history from TEST_HISTORY_START = 2023-01-01 (spec §5). Use the **frozen** L configurations (`max_leaf_nodes` per series, read from the freeze record), with no reselection. Issues run from 2025-11-01, and every target day ends by F_test.
- **S ranking for test:** read from the freeze record (T12 decides the window). Never recomputed inside the test run.

## B1: entry point and log
- **`run_slice --window test`** is the only way to construct `Window.test`. It refuses (non-zero exit, with the reason) unless:
  - (a) HEAD equals `config/freeze.json` `freeze_commit` and the tree is clean;
  - (b) the sha256 of `config/freeze.json` matches the annotated tag `config-freeze`;
  - (c) every input file hash matches the freeze record;
  - (d) `results/test/` does not already hold a completed run, unless `--rerun-reason "<text>"` is given, and that reason is logged.
- **`gridpilot.seal.sealed_read(path, *, purpose, columns, time_range)`** is the only function allowed to return rows at or after TEST_START.
  - Before returning anything, it appends one JSONL line to `results/test_reads.jsonl`: UTC time, purpose, path, the file's sha256, columns, time range, code commit, config hash and the caller.
  - The log is append-only (opened with `"a"`), with an fsync after each write.
  - It refuses outside an active test-mode context, which is a context manager entered only by the entry point.
- **Outputs:** the run directory `runs/test/<UTC>/` and the exports `results/test/*.json`, with the same schema plus `window: "test"`.

## B3: the F8 guard test
A static test (AST or grep-based) fails on any grid read in `lab/src` or `lab/scripts`: `read_parquet`, `scan_parquet`, `read_excel` or `read_csv` on grid paths. Each must be wrapped by `drop_sealed` / a window filter, or by `sealed_read`. A small allowlist, with reasons, for files read for counts only.

## B6: namespace and UI
- copy-data copies `results/*.json` and `results/test/*.json` separately.
- The UI shows a window switch, "Validation year" or "Test year (sealed until <freeze>)". The test option is enabled only when `results/test/manifest.json` exists.
- The copy is parametrised by window. No validation wording appears on test numbers.
- The offline test covers both states. Use a synthetic `results/test` fixture under `web/tests/fixtures` that is never committed under `public/`.

## B7: provenance enforcement
- In test mode, assert a clean tree and committed manifests: the hashes are read from git (`git show HEAD:data/manifests/...`), not from the data dir.
- Refresh `data/manifests/snapshot.json`: the openmeteo hash is now final, or openmeteo is excluded from the snapshot with a reason.

## Tests
- Synthetic end-to-end: a tiny fake sealed table in a temp `GRIDPILOT_DATA_DIR`; enter test mode through the entry-point function with a fake freeze record; assert that:
  - a read log line is written for every sealed read;
  - nothing reads sealed rows outside the context;
  - each refusal case (a)–(d) fires.

## Report
Write `/tmp/claude-1001/-home-nvidia-workspace-personal-projects/d7fb1e5c-cee6-4473-88b2-02a108cc36ac/scratchpad/s3-t11-report.md`.
