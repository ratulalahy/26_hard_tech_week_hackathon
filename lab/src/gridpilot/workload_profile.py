"""How concentrated the workload is (Task 8 fix R9): `results/workload-profile.json`.

From a registered slice run's per-job accounting (`job_accounting` over the run's ledgers and
its truth fill), jobs are ranked by declared GPU-hours (ties by job_uid). For the top 0.1%,
1% and 10% of jobs it reports their share of declared GPU-hours (`measured`), of U's energy
(`simulated`) and of a policy's saving vs U (`simulated`). Validation data only: the run is
the registered validation slice.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from gridpilot.results import SCHEMA_VERSION, env

QS = (0.001, 0.01, 0.1)


def concentration(acct_u: pl.DataFrame, acct_p: pl.DataFrame, qs=QS) -> dict:
    """Shares held by the largest jobs. Both frames: job_uid, requested_gpu_s, energy_kwh,
    co2_kg, one row per job, over the same jobs."""
    if set(acct_u["job_uid"]) != set(acct_p["job_uid"]) or acct_u.height != acct_p.height:
        raise ValueError("U and policy accounting must cover the same jobs")
    f = acct_u.select("job_uid", (pl.col("requested_gpu_s") / 3600).alias("gpu_h"),
                      pl.col("energy_kwh").alias("kwh"), pl.col("co2_kg").alias("co2_u")).join(
        acct_p.select("job_uid", pl.col("co2_kg").alias("co2_p")), on="job_uid")
    f = f.with_columns((pl.col("co2_u") - pl.col("co2_p")).alias("sav")).sort(
        ["gpu_h", "job_uid"], descending=[True, False])
    tot = {k: f[k].sum() for k in ("gpu_h", "kwh", "sav")}
    top = []
    for q in qs:
        k = max(1, round(f.height * q))
        t = f.head(k)
        top.append({"fraction": q, "n_jobs": k, "gpu_h_share": t["gpu_h"].sum() / tot["gpu_h"],
                    "energy_share": t["kwh"].sum() / tot["kwh"],
                    "saving_share": t["sav"].sum() / tot["sav"] if tot["sav"] else None})
    return {"n_jobs": f.height, "top": top, "median_gpu_h": float(f["gpu_h"].median()),
            "share_jobs_under_1_gpu_h": float((f["gpu_h"] < 1).mean()),
            "saving_kg": tot["sav"]}


def build_artifact(acct_u: pl.DataFrame, acct_p: pl.DataFrame, *, policy: str, run_id: str) -> dict:
    c = concentration(acct_u, acct_p)
    pid = f"{run_id}:workload"
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "workload-profile",
        "run_id": run_id,
        "policy": policy,
        "definition": "jobs ranked by declared GPU-hours (ties by job_uid); shares of the "
                      f"cohort's declared GPU-hours, of U's energy, and of {policy}'s saving vs U",
        "n_jobs": env(c["n_jobs"], "jobs", "simulated", f"{pid}:n_jobs"),
        "median_gpu_h": env(c["median_gpu_h"], "GPU_h", "measured", f"{pid}:median_gpu_h"),
        "share_jobs_under_1_gpu_h": env(c["share_jobs_under_1_gpu_h"], "fraction", "measured",
                                        f"{pid}:under_1_gpu_h"),
        "saving_kg": env(c["saving_kg"], "kg_CO2", "simulated", f"{pid}:saving_kg"),
        "top": [{
            "fraction": env(t["fraction"], "fraction", "assumed", f"{pid}:q{t['fraction']}"),
            "n_jobs": env(t["n_jobs"], "jobs", "simulated", f"{pid}:q{t['fraction']}:n"),
            "gpu_h_share": env(t["gpu_h_share"], "fraction", "measured",
                               f"{pid}:q{t['fraction']}:gpu_h"),
            "energy_share": env(t["energy_share"], "fraction", "simulated",
                                f"{pid}:q{t['fraction']}:energy"),
            "saving_share": env(t["saving_share"], "fraction", "simulated",
                                f"{pid}:q{t['fraction']}:saving",
                                status="ok" if t["saving_share"] is not None else "unavailable",
                                reason=None if t["saving_share"] is not None else "no saving"),
        } for t in c["top"]],
    }


def from_run(run_dir: Path, policy: str = "W") -> dict:
    """Per-job accounting for U and `policy` from a slice run directory's ledgers and truth."""
    from gridpilot.eval.accounting import TruthTable, job_accounting

    u = pl.read_parquet(run_dir / "ledger_U.parquet")
    p = pl.read_parquet(run_dir / f"ledger_{policy}.parquet")
    jobs = u.select("job_uid", pl.col("job_uid").str.split("#").list.first().alias("source_id"),
                    "arrival_ts", "gpus", "duration_s")
    tt = TruthTable(pl.read_parquet(run_dir / "truth_fill.parquet"))
    return build_artifact(job_accounting(u, jobs, tt), job_accounting(p, jobs, tt),
                          policy=policy, run_id=run_dir.name)
