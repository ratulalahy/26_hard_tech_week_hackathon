# Task 2 fix round 1 (small; the reviewer approved; these are cheap hardening items)

Do them on s2/task-2, run the full suite, commit, and push so PR #22 updates.

1. **Seal before load.** Use `pl.scan_parquet(BALANCE_PATH).filter(pl.col("ts_utc") < TEST_START).select(...).collect()` (or `drop_sealed` on the LazyFrame) so sealed rows never enter memory. Do the same for any other loader in forecast.py.
2. **Fit-time leak test.**
   - Corrupt to −1e6 every row with `ts + 1h + env > fit_at`.
   - Assert that `fit()` gives identical K and L predictions on the same clean features, and identical `n_labels`, `n_train_rows` and `train_mean`.
   - Parametrize over PACE demand (2 h) and a carbon series (96 h).
   - Keep it fast: use a short synthetic or real-sliced history.
3. **Limitation beside the results.** Add a `limitation` key to `metrics.json` and `config.yaml`. Text: "Publication-lagged replay of a revised historical snapshot (EIA regenerates files daily); real-time vintages are not reconstructed. Envelopes are assumed availability rules (spec §5); the adjusted-demand 2 h envelope is unverified against EIA's imputation timing."
4. **`score` guard.** Assert that the input has a single (model, target) and a unique (ba, target_ts).
5. **Empty-score guard.** The selection key uses `math.inf` when n = 0.
6. **Spike-rule density.** `prepare` asserts that the series is dense hourly per ba (no gaps in ts_utc) before applying `demand_spike`.
7. **Evidence labels.** Add `evidence="modeled"` to the climatology table. In `metrics.json`, label the error statistics `"measured"`.

Not in scope: provenance (#7) and the truncated last target day (#8); both are deferred to Task 7. Re-running the validation run is optional; do it only if the code path changed outputs. If the outputs are byte-identical, say so.
Append a "Fix round 1" section to the report at /tmp/claude-1001/-home-nvidia-workspace-personal-projects/d7fb1e5c-cee6-4473-88b2-02a108cc36ac/scratchpad/task-2-report.md.
