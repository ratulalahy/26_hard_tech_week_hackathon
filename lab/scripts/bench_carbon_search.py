"""Benchmark the carbon search K/W/L/H on the real validation replay (spec §15 F10,
F12.6, F13.5, F14.7).

Same slice as `bench_sim_core.py`: `gridpilot.workload.replay` over 2024-11-01 ->
2025-10-24 (~919k instances), every U booking pre-reserved, the F3 closure calendar from
`site_mask` on the pre-seal carbon table. Times: forecast inputs (the issued frame and
the K tail), `u_bookings`, policy construction, the replay, and the ledger export.
`--diagnose` adds a second run per policy with the F14.7 blocked diagnostic.

H is driven by the unfilled consumption truth here; the F14.6 filled scoring truth is
built later by the Task 7 driver. The S ranking is a placeholder (Task 7 supplies the
training-mean order).

    cd lab && GRIDPILOT_DATA_DIR=... uv run python scripts/bench_carbon_search.py \\
        [--weeks N] [--policies K,W,L,H] [--diagnose] [--forecast-run DIR] [--json PATH]
"""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from gridpilot.data.eia_co2 import CORE_BAS, load_carbon, site_mask
from gridpilot.sim import (
    CarbonSearch,
    G,
    S,
    U,
    closed_intervals,
    job_energy_kwh,
    load_forecasts,
    simulate,
    tail_climatology,
    u_bookings,
)
from gridpilot.sim.carbon_search import GRID_END, GRID_START, latest_forecast_run
from gridpilot.workload import replay

VAL_START = datetime(2024, 11, 1, tzinfo=UTC)
VAL_END = datetime(2025, 10, 24, tzinfo=UTC)
RANKING = ["BPAT", "CISO", "NEVP"]  # placeholder; Task 7 computes the real one


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", type=float, default=None)
    ap.add_argument("--policies", default="K,W,L,H")
    ap.add_argument("--diagnose", action="store_true")
    ap.add_argument("--forecast-run", type=Path, default=None)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()
    out: dict = {"evidence": "simulated", "policies": {}}

    t = time.perf_counter()
    run_dir = args.forecast_run or latest_forecast_run()
    fc = load_forecasts(run_dir)
    tail = tail_climatology(CORE_BAS)
    t_fc = time.perf_counter() - t
    carbon = load_carbon()
    mask = site_mask(carbon, GRID_START, GRID_END, CORE_BAS)
    closed = closed_intervals(mask)
    end = VAL_END if args.weeks is None else VAL_START + timedelta(weeks=args.weeks)
    t = time.perf_counter()
    jobs = replay(VAL_START, end)
    t_load = time.perf_counter() - t
    t = time.perf_counter()
    bookings = u_bookings(jobs, closed=closed)
    t_b = time.perf_counter() - t
    n = jobs.height
    print(f"replay {VAL_START:%Y-%m-%d} -> {end:%Y-%m-%d}: {n:,} jobs "
          f"({jobs['mobile'].sum():,} mobile); load {t_load:.1f} s; forecast inputs "
          f"({run_dir.name}: frame + K tail) {t_fc:.1f} s; u_bookings {t_b:.1f} s")
    print("closed hours: " + ", ".join(
        f"{s} {sum((b - a) // 3_600_000_000 for a, b in iv)}" for s, iv in closed.items()))
    out.update(slice=f"{VAL_START:%Y-%m-%d}/{end:%Y-%m-%d}", jobs=n, forecast_run=str(run_dir),
               t_forecast_inputs_s=t_fc, t_u_bookings_s=t_b,
               closed_hours={s: sum((b - a) // 3_600_000_000 for a, b in iv)
                             for s, iv in closed.items()})
    mobile = jobs.select("job_uid", "mobile", "duration_s")

    def make(name: str):
        if name == "U":
            return U()
        if name == "G":
            return G()
        if name == "S":
            return S(ranking=RANKING)
        if name == "H":
            return CarbonSearch("H", None, carbon, mask)
        return CarbonSearch(name, fc, None, mask, tail=tail)

    with tempfile.TemporaryDirectory() as tmp:
        for name in args.policies.split(","):
            t = time.perf_counter()
            policy = make(name)
            t_build = time.perf_counter() - t
            t = time.perf_counter()
            led = simulate(jobs, policy, bookings=bookings, closed=closed)
            t_run = time.perf_counter() - t
            t = time.perf_counter()
            led.write_parquet(Path(tmp) / f"{name}.parquet")
            t_exp = time.perf_counter() - t
            j = led.join(mobile, on="job_uid")
            moved = int(led["moved"].sum())
            retimed = int((led["moved"] & ~led["transfer"]).sum())
            res = {
                "t_build_s": t_build, "t_replay_s": t_run, "t_export_s": t_exp,
                "us_per_job": t_run / n * 1e6, "moved": moved, "moved_share": moved / n,
                "moved_share_of_mobile": float(j.filter("mobile")["moved"].mean()),
                "remote": int(led["transfer"].sum()), "retimed_at_home": retimed,
                "late": int(led["late"].sum()), "engine_blocked": int(led["blocked"].sum()),
            }
            print(f"{name}: build {t_build:5.1f} s, replay {t_run:6.1f} s "
                  f"({res['us_per_job']:5.1f} us/job), export {t_exp:4.1f} s; "
                  f"moved {res['moved_share']:.2%} (of mobile "
                  f"{res['moved_share_of_mobile']:.2%}), remote {res['remote']:,}, "
                  f"retimed at home {retimed:,}, late {res['late']}, "
                  f"engine-blocked {res['engine_blocked']}")
            if args.diagnose:
                t = time.perf_counter()
                d = simulate(jobs, make(name), bookings=bookings, closed=closed,
                             diagnose_blocked=True)
                t_d = time.perf_counter() - t
                same = d.drop("blocked").equals(led.drop("blocked"))
                b = d.filter("blocked")
                kwh = float(sum(job_energy_kwh(g, s) for g, s in
                                zip(b["gpus"].to_list(), b["duration_s"].to_list(),
                                    strict=True)))
                res.update(t_diagnose_s=t_d, blocked=b.height, blocked_share=b.height / n,
                           blocked_kwh=kwh, blocked_evidence="modeled",
                           diagnose_placements_identical=same)
                print(f"   F14.7 blocked: {b.height:,} jobs ({b.height / n:.3%}), "
                      f"{kwh:,.0f} kWh modeled execution energy; placements identical "
                      f"{same}; {t_d:.1f} s")
            out["policies"][name] = res
    if args.json:
        args.json.write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
