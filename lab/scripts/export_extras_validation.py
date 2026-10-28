"""Write results/extras-validation.json: the validation counterparts of the pre-registered
test-year extras (Stage 3 T20, D-071) that need a computation, fixed before the seal opens.

    cd lab && uv run python scripts/export_extras_validation.py --registered-run <abs runs/slice/<run_id>>

- item 2b (D-073): the peak-aimed storage schedule from the training years, beside the carbon
  schedule on the registered validation ledgers;
- item 5: the seasonal split of S and W vs U on the registered validation ledgers;
- item 6: forecast skill on the registered forecast run (MAE of K, W, L; L and W relative to K;
  PACE demand vs EIA's day-ahead forecast), the **frozen p10/p90 intervals** (residual
  quantiles over the validation selection issues) that the test run scores, and the L
  permutation importance on validation.

The test run (`run_slice --window test`) reads this committed file for its drift table and its
interval coverage; it never recomputes the validation side. Validation only; no sealed value.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import polars as pl

from gridpilot import forecast as fcmod
from gridpilot import test_extras as tx
from gridpilot.data.truth_fill import BALANCE_PATH
from gridpilot.eval import TruthTable
from gridpilot.paths import RESULTS_DIR
from gridpilot.results import SCHEMA_VERSION, env, write_json_atomic
from gridpilot.splits import drop_sealed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registered-run", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=RESULTS_DIR / "extras-validation.json")
    ap.add_argument("--ext-root", type=Path, default=None,
                    help="runs/ext holding the mobility ≤ 8 GPUs run (default: next to the run)")
    a = ap.parse_args()
    run = a.registered_run
    a.ext_root = a.ext_root or run.parents[1] / "ext"
    man = json.loads((RESULTS_DIR / "manifest.json").read_text())
    if run.name != man["run_id"]:
        raise SystemExit(f"{run} is not the registered run {man['run_id']}")
    cfg = json.loads((run / "config.json").read_text())
    if cfg.get("window") != "validation":
        raise SystemExit(f"{run} is not a validation run")
    eval_start = datetime.fromisoformat(cfg["eval_start"])
    A = datetime.fromisoformat(cfg["A"])
    led = {p: pl.read_parquet(run / f"ledger_{p}.parquet") for p in ("U", "S", "W")}
    jobs = led["U"].select("job_uid",
                           pl.col("job_uid").str.split("#").list.first().alias("source_id"),
                           "arrival_ts", "gpus", "duration_s")
    tt = TruthTable(drop_sealed(pl.read_parquet(run / "truth_fill.parquet")))
    seasonal = tx.seasonal_section(ledgers=led, cj=jobs, tt=tt, window=(eval_start, A),
                                   pid=f"extras-validation:{run.name}:seasonal",
                                   label=tx.LABEL_VALIDATION)
    fc_dir = run / "forecast" / run.name
    fm = json.loads((fc_dir / "metrics.json").read_text())
    leaves = {k: int(v["L_max_leaf_nodes"]) for k, v in fm["series"].items()}
    bal = drop_sealed(pl.scan_parquet(BALANCE_PATH)).filter(
        (pl.col("ba").cast(pl.Utf8) == "PACE") & (pl.col("ts_utc") >= tx.VAL_SKILL[0])
        & (pl.col("ts_utc") < tx.VAL_SKILL[1])).select("ba", "ts_utc", tx.EIA_DF_COL).collect()
    skill = tx.forecast_skill(fc_dir=fc_dir, fit_at=fcmod.VAL_FIT_AT,
                              history_start=fcmod.VAL_HISTORY_START, leaves=leaves,
                              issues=fcmod.validation_issues()[0], scored=tx.VAL_SKILL,
                              load=lambda t: fcmod.load_series(t), eia_df=tx.eia_day_ahead(bal),
                              intervals=None, pid=f"extras-validation:{run.name}:skill",
                              label=tx.LABEL_VALIDATION)
    # D-073 (item 2b): the peak-aimed schedule from the training years, and its comparison with
    # the carbon schedule on the registered validation ledgers (the test run reads the schedule)
    from gridpilot import storage as st
    from gridpilot.window import Window

    ext = json.loads((RESULTS_DIR / "extensions.json").read_text())
    mob_dir = a.ext_root / "mobility_le_8gpus" / ext["sensitivities"]["mobility_le_8gpus"]["run_id"]
    net = st.net_load()
    peak = tx.peak_schedule(net)
    storage = json.loads((RESULTS_DIR / "storage.json").read_text())
    led3 = {p: pl.read_parquet(run / f"ledger_{p}.parquet") for p in ("U", "S", "W")}
    sto = tx.storage_section(ledgers=led3, mob_w=pl.read_parquet(mob_dir / "ledger_W.parquet"),
                             filled=drop_sealed(pl.read_parquet(run / "truth_fill.parquet")),
                             eval_start=eval_start, net=net, committed=storage,
                             pid=f"extras-validation:{run.name}:storage", peak=peak,
                             window=Window.validation(), label=tx.LABEL_VALIDATION)
    storage_peak = {**sto["schedule_comparison"], "label": tx.LABEL_VALIDATION,
                    "peak_schedule": {
                        "rule": peak["rule"],
                        "charge_hours": env(peak["charge_hours"], "local_hour", "assumed",
                                            "extras-validation:peak:charge"),
                        "discharge_hours": env(peak["discharge_hours"], "local_hour", "assumed",
                                               "extras-validation:peak:discharge"),
                        "n_training_days": env(peak["n_days"], "days", "measured",
                                               "extras-validation:peak:n_days"),
                        "top4_counts": env(peak["top4_counts"], "days", "observed",
                                           "extras-validation:peak:top4"),
                        "lowest_counts": env(peak["lowest_counts"], "days", "observed",
                                             "extras-validation:peak:lowest")},
                    "rush_hours": sto["rush"]["n_hours"]}
    art = {"schema_version": SCHEMA_VERSION, "artifact": "extras-validation",
           "kind": "validation counterparts of the pre-registered test-year extras (D-071)",
           "window": "validation", "run_id": run.name, "label": tx.LABEL_VALIDATION,
           "note": ("validation results, fixed before the seal opens; the test run's drift table "
                    "and interval coverage read this file"),
           "seasonal": seasonal, "forecast_skill": skill, "storage_peak": storage_peak}
    write_json_atomic(a.out, art)
    for ba, by in skill["series"].items():
        for t, r in by.items():
            pi = r["permutation_importance"]
            print(f"{ba}/{t}: MAE K {r['models']['K']['mae']['value']:.2f} W "
                  f"{r['models']['W']['mae']['value']:.2f} L {r['models']['L']['mae']['value']:.2f}"
                  f"; L reproduces the run: {pi['reproduces_frozen_forecasts']}")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
