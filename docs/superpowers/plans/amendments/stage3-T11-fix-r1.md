# Stage 3 · T11 fix round 1 (from the adversarial review; D-059 "exactly once, any rerun logged")

Work on `s3/t11`. Fix everything below. Use synthetic temp repos only; **never run `--window test` on real data**. Push, and append "Fix round 1" to the report.

## Important (all required)
- **I1. Prior openings are detected from history, not just the working tree.** Check (d) treats any of these as a prior opening, which then requires `--rerun-reason`:
  - any `invocation` or `read` event in the working-tree log or in `git show HEAD:results/test_reads.jsonl`;
  - any commit in `git log --all -- results/test/manifest.json results/test_reads.jsonl`;
  - the existence of the test carbon table or any `runs/test/*` directory.

  Check (a) also requires that the log at HEAD is an append-only extension of the log at every commit since `freeze_commit`, and refuses deletions under `results/test/`. Add tests for S2b, S3 and S4b/c.
- **I2.** Use `git diff --no-renames --name-status`. Only `A` or `M` statuses are allowed, and only on the allowed paths. Add a test for the rename case.
- **I3. Tag binding.** The tag target must equal `git log -1 --format=%H -- config/freeze.json`, and that commit's parent must equal `freeze_commit`.
  - If `origin` exists, `git ls-remote origin refs/tags/config-freeze` must equal the local tag object. If the remote is unreachable, refuse with a clear reason, and allow an override flag that is logged.
  - Refuse if the log holds an earlier invocation with a different `config_sha256`.
- **I4.** In real use, `authorize` and `run_test` refuse unless:
  - `repo_root == paths.REPO_ROOT`;
  - `run_slice.py` lives under it;
  - `results_dir == REPO_ROOT/results`;
  - `data_dir == paths.DATA_DIR`.

  Overrides are allowed only with an explicit `synthetic=True`, which also refuses when the data dir is the real one, or lacks a `SYNTHETIC` marker file. Remove `pipeline=` or gate it the same way.
- **I5.** For every `TEST_INPUTS` entry listed in a committed manifest (read via `git show HEAD:`), require `freeze.input_sha256[rel] == manifest sha256`. For `balance.parquet`, add a committed derivation record: the hashes of the raw files it is built from, plus the build-code tree hash. T12's rebuild will write it. Until then, document the exception explicitly.
- **I6. Sealed values never persist in shared, unguarded places.**
  - Write the test carbon table into the test run directory, not the shared `data/processed/carbon/`.
  - `load_carbon`, `TruthTable` and `truth_fill` refuse frames past TEST_START outside test mode.
  - Extend the F8 guard to `runs/test/**` reads and to `notebooks/` (via nbformat).
  - Make `runs/test/<id>/` files read-only (chmod 0444) at context exit.

## Minor (fix all; they are cheap)
- **M1.** The close line logs `rc` and `exported`; the outcome is not "ok" when rc ≠ 0.
- **M2.** Load the freeze record via `git show HEAD:config/freeze.json`. Refuse if any file has skip-worktree or assume-unchanged flags. Include ignored files under `lab/` in the clean check.
- **M3.** Validate the freeze record with `jsonschema` in `load_freeze`. L leaves must be `type(v) is int`. The S means are required, for exactly 4 sites, finite and consistent with `order`. Cross-check `validation_run` against `results/manifest.json` at HEAD.
- **M4.** The F8 guard resolves import aliases and assignments, and adds pyarrow, duckdb, openpyxl, `read_ipc`, and `open()` on data extensions. The reader call must be the direct first argument of `drop_sealed`. Narrow the `recon_grid` allowlist entry to the specific call.
- **M5.** AST check of `test_mode`, `authorize`, `_ACTIVE` and `run_test` usage. An authorization is single-use: it is consumed on first `test_mode` entry, and `dataclasses.replace` copies are rejected.
- **M6.** Keep the session in `contextvars`, and refuse other threads or processes.
- **M7.** Read the bytes once, then hash and parse from the buffer. fsync the directory when the log is created.
- **M8.** The export line logs the sha256 of every artifact. Make `copy-data`, plus a lab test, verify `results/test/*.json` against the last export line.
- **M9.** Archive earlier test results to `results/test/history/<run_id>/` before a rerun export.
- **M10.** Hold an `O_EXCL` lock file for the session.
- **M11.** Wrap every authorize failure as `SealError`, so it exits with REFUSED_RC and a reason.
- **M12.** Reject `--out` together with `--window test`.
- **M13.** The test grid profile reads only the 4 core sites (lead ruling).
- **M14.** Test-window copy says "over the covered period (N weeks)", never "all year" or "over the year".
- **M15.**
  - Compute the canonical metrics hash on the **serialized artifact**: load the written JSON and hash that, everywhere.
  - Rerun the validation reproduction at your final commit, and report its ledger hashes and its serialized-artifact canonical hash.
  - State in the report exactly which hash T12 must record in `validation_run`.
- **M16.** Exempt `wallclock_frozen_at` only for the test window.
