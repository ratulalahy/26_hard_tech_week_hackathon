# Task 1 fix round 1 (lead rulings on the task review of bc49eaa)

Fix all of these in your worktree on the same branch, run the full suite, commit, push (PR #18 updates).

1. **Seal on disk (Important).** The default `build_carbon()` must write `carbon_hourly.parquet` truncated at TEST_START (`drop_sealed` before the atomic write). Rebuild the real file so it has no row with ts_utc >= TEST_START. Sealed-window truth is NOT produced in this task. Later, the logged evaluation entry point will build it into a separate path. Update the module docstring and add a test that the built parquet (read directly with polars, not via `load_carbon`) has max ts_utc < TEST_START. When the file is absent the test may skip, but the synthetic build test must assert truncation.
2. **Production-basis reasons (spec §4: record all rejection reasons).** Ruling: add a `null_reason_generated` column next to the existing one. Rename nothing; keep `null_reason` for the consumed basis. Test it with a negative in the generated column.
3. **Mask defaults closed.** `site_mask` must return a value for every (ba, hour) in a requested window: add the parameters `start`, `end` and `bas`, and build over a complete ba × hour grid. Any key with no carbon row gives `truth_ok=False`. Add a test where an hour outside a BA's stored range comes back False, and one for a BA with no rows at all. Keep the existing call working if Task 5 might call it without a window (the defaults can come from the data range).
4. **Real atomicity test.** Pre-create a parquet at the target path, monkeypatch so the write or `os.replace` raises, then assert the old file is byte-identical and no temp file remains.
5. **Coverage.** Add tests for: zero kept as 0.0 with `truth_ok` True; "nan" and "inf" giving `non_numeric`; a duplicate hour raising ValueError; a two-BA build sorted by (ba, ts_utc).
6. **Null timestamps.** Raise instead of dropping rows with null or unparseable time.
7. **Lineage.** Write a sidecar `carbon_hourly.meta.json` atomically next to the parquet, holding: the sha256 of each source workbook, unit "lb/kWh", factor 453.592 (with a comment that the exact factor is 453.59237 and the spec pins 453.592), the shift "UTC end → hour-start −1h", the cutoff TEST_START, the build time, the output sha256, and evidence "observed".
8. Add `openpyxl` to the lab dev dependency group if the tests import it.

Not in scope: the float-precision probe (#8) and fsync.
Append a "Fix round 1" section to your report file (task-1-report.md).
