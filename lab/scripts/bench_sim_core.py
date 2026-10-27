"""Benchmark the simulator core (spec §15 F10, F11) on a real replay or a synthetic slice.

Sources:
- `replay` (headline): `gridpilot.workload.replay` over [--start, --end), default the
  validation arrivals 2024-11-01 -> 2025-10-24 (~919k instances); `--weeks N` cuts it.
- `synthetic`: Poisson arrivals at Seren's mean rate (x `--rate-scale`), with
  (GPU count, duration, job type) drawn jointly from the Seren attempts.

Each run: one `u_bookings` (the F1/F11 U run), then U, G and S with bookings.
`--diagnose` adds a counterfactual per policy: the action it would pick if future
bookings were not held (only earlier placements), counted as "blocked" when it differs
from what it got. That pass roughly doubles the cost.

    cd lab && GRIDPILOT_DATA_DIR=... uv run python scripts/bench_sim_core.py \\
        [--source replay|synthetic] [--weeks N] [--rate-scale 1.0] [--diagnose]
"""

from __future__ import annotations

import argparse
import hashlib
import time
from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl

from gridpilot.data.traces import load_acme
from gridpilot.sim import SITES, Capacity, G, S, U, simulate, u_bookings

DELAY_H = {"Pretrain": 6.0, "SFT": 6.0, "MLLM": 6.0, "Eval": 1.0}
VAL_START = datetime(2024, 11, 1, tzinfo=UTC)
VAL_END = datetime(2025, 10, 24, tzinfo=UTC)
RANKING = ["BPAT", "CISO", "NEVP"]  # placeholder; Task 7 computes the real one


def synthetic_slice(days: float, rate_scale: float = 1.0, seed: int = 20261027) -> pl.DataFrame:
    seren = load_acme("seren").filter((pl.col("gpu_count") > 0) & (pl.col("run_s") > 0))
    span_s = (seren["submit_ts"].max() - seren["submit_ts"].min()).total_seconds()
    rate = rate_scale * seren.height / span_s  # jobs per second
    rng = np.random.default_rng(seed)
    horizon = days * 86400.0
    n = rng.poisson(rate * horizon)
    arrival = np.sort(rng.uniform(0.0, horizon, n)).round()  # whole seconds, like Seren
    src = seren[rng.integers(0, seren.height, n)]
    uid = [f"syn{i:07d}#c0" for i in range(n)]
    jt = src["job_type"].to_list()
    flex = [t in DELAY_H and int(hashlib.sha256(f"{u}:42".encode()).hexdigest(), 16) % 2 == 0
            for u, t in zip(uid, jt, strict=True)]
    return pl.DataFrame({
        "job_uid": uid,
        "arrival_ts": pl.Series(VAL_START.timestamp() * 1e6 + arrival * 1e6)
        .cast(pl.Int64).cast(pl.Datetime("us")).dt.replace_time_zone("UTC"),
        "duration_s": src["run_s"].cast(pl.Float64),
        "gpus": src["gpu_count"].cast(pl.Int64),
        "job_type": jt,
        "flexible": flex,
        "max_delay_s": [DELAY_H.get(t, 0.0) * 3600.0 if f else 0.0
                        for t, f in zip(jt, flex, strict=True)],
        "mobile": flex,
    })


class _Counterfactual:
    """Wraps a policy; also asks it what it would do without future bookings."""

    def __init__(self, inner, sites):
        self.inner = inner
        self.name = inner.name
        self.free = {s: Capacity(n) for s, n in sites.items()}  # earlier placements only
        self.views = {s: c.view() for s, c in self.free.items()}
        self.blocked = 0
        self.blocked_gpu_h = 0.0
        self.decisions = 0

    def choose(self, job, now, capacities, ctx):
        for c in self.free.values():
            c.advance(now)
        got = self.inner.choose(job, now, capacities, ctx)
        want = self.inner.choose(job, now, self.views, ctx)
        self.decisions += 1
        if want is not None and want != got and ctx.on_time(job, want.start_us):
            self.blocked += 1
            self.blocked_gpu_h += job.gpus * job.duration_s / 3600
        return got

    def on_commit(self, job, action):
        self.free[action.site].reserve(action.start_us, action.start_us + job.duration_us,
                                       job.gpus)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["replay", "synthetic"], default="replay")
    ap.add_argument("--weeks", type=float, default=None, help="cut the source to N weeks")
    ap.add_argument("--rate-scale", type=float, default=1.0)
    ap.add_argument("--diagnose", action="store_true")
    args = ap.parse_args()

    t = time.perf_counter()
    if args.source == "replay":
        from gridpilot.workload import replay
        end = VAL_END if args.weeks is None else VAL_START + timedelta(weeks=args.weeks)
        jobs = replay(VAL_START, end)
        label = f"replay {VAL_START:%Y-%m-%d} -> {end:%Y-%m-%d}"
    else:
        days = 14.0 if args.weeks is None else 7 * args.weeks
        jobs = synthetic_slice(days, args.rate_scale)
        label = f"synthetic {days:g} d x{args.rate_scale:g}"
    t_load = time.perf_counter() - t
    span_h = (jobs["arrival_ts"].max() - jobs["arrival_ts"].min()).total_seconds() / 3600
    gpu_h = (jobs["gpus"] * jobs["duration_s"]).sum() / 3600
    print(f"{label}: {jobs.height:,} jobs, {gpu_h:,.0f} GPU-h (mean demand "
          f"{gpu_h / span_h:,.0f} GPUs vs {SITES['PACE']} PACE), "
          f"{jobs['flexible'].mean():.1%} flexible; load {t_load:.1f} s")

    t = time.perf_counter()
    bookings = u_bookings(jobs)
    t_b = time.perf_counter() - t
    wait_s = (bookings.join(jobs.select("job_uid", pl.col("arrival_ts").dt.epoch("us")
                                        .alias("a")), on="job_uid")
              .select((pl.col("start_us") - pl.col("a")) / 1e6).to_series())
    print(f"u_bookings (one U run): {t_b:6.1f} s ({t_b / jobs.height * 1e6:5.1f} us/job); "
          f"U wait p95 {wait_s.quantile(0.95):,.0f} s, max {wait_s.max():,.0f} s")

    for policy in (U(), G(), S(ranking=RANKING)):
        t = time.perf_counter()
        ledger = simulate(jobs, policy, bookings=bookings)
        dt = time.perf_counter() - t
        mob = ledger.join(jobs.select("job_uid", "mobile"), on="job_uid")
        print(f"{policy.name}: {dt:6.1f} s ({dt / jobs.height * 1e6:5.1f} us/job)  "
              f"late={ledger['late'].sum()}  moved={ledger['moved'].mean():.2%} "
              f"(of mobile {mob.filter(pl.col('mobile'))['moved'].mean():.2%})  "
              f"remote={ledger['transfer'].sum():,}  blocked={ledger['blocked'].sum():,} "
              f"({ledger.filter('blocked').select(pl.col('gpus') * pl.col('duration_s'))
                 .sum().item() / 3600:,.0f} GPU-h)")
        if args.diagnose:
            cf = _Counterfactual(policy, SITES)
            t = time.perf_counter()
            simulate(jobs, cf, bookings=bookings, on_commit=cf.on_commit)
            print(f"   counterfactual: preferred action blocked by bookings in "
                  f"{cf.blocked:,} of {cf.decisions:,} decisions "
                  f"({cf.blocked / cf.decisions:.2%}, {cf.blocked_gpu_h:,.0f} GPU-h); "
                  f"{time.perf_counter() - t:.1f} s")


if __name__ == "__main__":
    main()
