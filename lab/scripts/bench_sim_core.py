"""Benchmark the simulator core on a synthetic two-week, Seren-like slice (spec §15 F10).

The slice is synthetic (simulated): Poisson arrivals at Seren's mean submission rate,
with (GPU count, duration, job type) drawn jointly, with replacement, from the Seren
GPU attempts. Flexibility follows the global sha256 rule on the synthetic IDs.

    cd lab && GRIDPILOT_DATA_DIR=... uv run python scripts/bench_sim_core.py \
        [--days 14] [--source synthetic|busiest] [--rate-scale 1.0]

`--source busiest` instead replays the real Seren submissions of the busiest window.
"""

from __future__ import annotations

import argparse
import hashlib
import time
from datetime import UTC, datetime

import numpy as np
import polars as pl

from gridpilot.data.traces import load_acme
from gridpilot.sim import SITES, G, S, U, simulate, u_finish_deadlines

DELAY_H = {"Pretrain": 6.0, "SFT": 6.0, "MLLM": 6.0, "Eval": 1.0}
START = datetime(2024, 11, 1, tzinfo=UTC)


def synthetic_slice(days: float, rate_scale: float = 1.0, seed: int = 20261027) -> pl.DataFrame:
    seren = load_acme("seren").filter((pl.col("gpu_count") > 0) & (pl.col("run_s") > 0))
    span_s = (seren["submit_ts"].max() - seren["submit_ts"].min()).total_seconds()
    rate = rate_scale * seren.height / span_s  # jobs per second
    rng = np.random.default_rng(seed)
    horizon = days * 86400.0
    n = rng.poisson(rate * horizon)
    arrival = np.sort(rng.uniform(0.0, horizon, n)).round()  # whole seconds, like Seren
    pick = rng.integers(0, seren.height, n)
    src = seren[pick]
    uid = [f"syn{i:07d}#c0" for i in range(n)]
    jt = src["job_type"].to_list()
    flex = [t in DELAY_H and int(hashlib.sha256(f"{u}:42".encode()).hexdigest(), 16) % 2 == 0
            for u, t in zip(uid, jt, strict=True)]
    return pl.DataFrame({
        "job_uid": uid,
        "arrival_ts": pl.Series(START.timestamp() * 1e6 + arrival * 1e6)
        .cast(pl.Int64).cast(pl.Datetime("us")).dt.replace_time_zone("UTC"),
        "duration_s": src["run_s"].cast(pl.Float64),
        "gpus": src["gpu_count"].cast(pl.Int64),
        "job_type": jt,
        "flexible": flex,
        "max_delay_s": [DELAY_H.get(t, 0.0) * 3600.0 if f else 0.0
                        for t, f in zip(jt, flex, strict=True)],
        "mobile": flex,
    })


def busiest_real_slice(days: float) -> pl.DataFrame:
    """The real Seren submissions in the `days`-long window with the most GPU-hours,
    re-anchored to START (bursty, unlike the Poisson slice)."""
    seren = load_acme("seren").filter((pl.col("gpu_count") > 0) & (pl.col("run_s") > 0))
    daily = (seren.group_by(pl.col("submit_ts").dt.truncate("1d").alias("day"))
             .agg((pl.col("gpu_count") * pl.col("run_s")).sum().alias("w")).sort("day")
             .upsample("day", every="1d").fill_null(0))
    roll = daily["w"].rolling_sum(int(days))
    first = daily["day"][int(roll.arg_max()) - int(days) + 1]
    win = seren.filter((pl.col("submit_ts") >= first)
                       & (pl.col("submit_ts") < first + pl.duration(days=int(days))))
    offset = START - first
    uid = [f"{j}#c0" for j in win["job_id"].to_list()]
    jt = win["job_type"].to_list()
    flex = [t in DELAY_H and int(hashlib.sha256(f"{j}:42".encode()).hexdigest(), 16) % 2 == 0
            for j, t in zip(win["job_id"].to_list(), jt, strict=True)]
    print(f"real window starts {first:%Y-%m-%d} (source time)")
    return pl.DataFrame({
        "job_uid": uid,
        "arrival_ts": win["submit_ts"] + offset,
        "duration_s": win["run_s"].cast(pl.Float64),
        "gpus": win["gpu_count"].cast(pl.Int64),
        "job_type": jt,
        "flexible": flex,
        "max_delay_s": [DELAY_H.get(t, 0.0) * 3600.0 if f else 0.0
                        for t, f in zip(jt, flex, strict=True)],
        "mobile": flex,
    })


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=float, default=14.0)
    ap.add_argument("--source", choices=["synthetic", "busiest"], default="synthetic")
    ap.add_argument("--rate-scale", type=float, default=1.0,
                    help="synthetic arrival-rate multiplier (stress only; >1.7 overloads PACE)")
    args = ap.parse_args()

    jobs = synthetic_slice(args.days, args.rate_scale) if args.source == "synthetic" else (
        busiest_real_slice(args.days))
    gpu_h = (jobs["gpus"] * jobs["duration_s"]).sum() / 3600
    print(f"slice: {jobs.height} jobs over {args.days:g} days, {gpu_h:,.0f} GPU-h "
          f"(mean demand {gpu_h / (args.days * 24):,.0f} GPUs vs {SITES['PACE']} PACE slots), "
          f"{jobs['flexible'].mean():.1%} flexible")

    t = time.perf_counter()
    deadlines = u_finish_deadlines(jobs)
    t_f1 = time.perf_counter() - t
    print(f"u_finish_deadlines (one U run): {t_f1:.2f} s")

    for policy in (U(), G(), S()):
        t = time.perf_counter()
        ledger = simulate(jobs, policy, deadlines=deadlines)
        dt = time.perf_counter() - t
        wait = (ledger.join(jobs.select("job_uid", "arrival_ts"), on="job_uid")
                .select((pl.col("start_ts") - pl.col("arrival_ts")).dt.total_seconds()))
        print(f"{policy.name}: {dt:6.2f} s  ({dt / jobs.height * 1e6:5.1f} us/job)  "
              f"late={ledger['late'].sum()}  remote={ledger['transfer'].sum()}  "
              f"wait p95={wait.to_series().quantile(0.95):,.0f} s")
    per_job = t_f1 / jobs.height
    print(f"extrapolated U at 1,000,000 jobs: {per_job * 1e6:.0f} s at this load")


if __name__ == "__main__":
    main()
