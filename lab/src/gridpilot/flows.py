"""Stage 3 T15 (D-064): where the work went in each validation scenario, and the flexibility
budget. Both re-read already-computed ledgers; nothing here simulates.

- `results/scenario-flows.json`: for the registered primary and three registered D-058
  sensitivities (mobility <= 8 GPUs; destination capacity 0 and 1,024), per policy S/W/L,
  the saving vs U and its interval **copied** from metrics.json / extensions.json; remote
  execution energy by site; the remote share of energy; and the replay-week arcs.
- `results/flexibility-budget.json`: the registered primary's cohort execution energy split
  into five buckets by what the policy did with each job.

**Remote execution vs "moved"** (Astra F08). A job *ran remotely* when its executing site is
not Utah (PACE). The ledger's `moved` is broader: the job did not run on its booking, which
also counts a start-time change at home (retiming, earlier or later). Both are reported,
under those names.

Totals are `math.fsum` over job_uid-sorted rows (order-free). Outcomes are `simulated`;
flexibility and mobility flags and scenario knobs are `assumed`. Validation only.
"""

from __future__ import annotations

import math
from datetime import datetime

import polars as pl

from gridpilot.results import SCHEMA_VERSION, env, iso
from gridpilot.sim import HOME, SITES
from gridpilot.sim.power import GPU_KW as KW_PER_GPU
from gridpilot.sim.power import PUE

DESTS = tuple(sorted(s for s in SITES if s != HOME))
POLICIES = ("S", "W", "L")
HOUR_US = 3_600_000_000

# Display order (a)-(e). Assignment precedence is different: capacity_blocked (F14.7, when
# the run was diagnosed), then must_stay, then moved_remote, retimed_home, stayed_booking.
BUCKETS = ("moved_remote", "retimed_home", "stayed_booking", "must_stay", "capacity_blocked")
BUCKET_TEXT = {
    "moved_remote": "ran at a remote site (remote execution)",
    "retimed_home": "flexible job retimed at home: ran in Utah with its start changed from "
                    "its booking",
    "stayed_booking": "flexible and mobile, but ran on its Utah booking (no better option "
                      "for the policy)",
    "must_stay": "must stay: not flexible or not mobile (assumed flags), wherever it started",
    "capacity_blocked": "capacity-blocked (F14.7): the policy would have chosen better "
                        "without other jobs' pending bookings",
}
DEFINITIONS = {
    "remote_execution": "the job executed at a site other than Utah (PACE); remote execution "
                        "energy is that job's execution energy at the destination",
    "moved": "ledger `moved`: the job did not run on its booking, so it includes remote "
             "execution and retiming at home (a start-time change, earlier or later) (F08)",
    "remote_energy_share": "remote jobs' energy (execution plus transfer) / all energy "
                           "(execution plus transfer), copied from the scored run",
    "remote_execution_share": "remote execution kWh / all execution kWh, from the ledger",
    "retimed_home_execution_share": "execution kWh of jobs that ran in Utah off their booking "
                                    "start / all execution kWh, from the ledger",
    "week_arcs": "cohort jobs arriving in the replay week that executed at each destination: "
                 "count and declared GPU-hours (gpus x declared duration)",
    "saving_vs_U": "copied verbatim from metrics.json (registered) or extensions.json "
                   "(scenarios): (U - policy) / U, ratio of totals, 4-week blocks, 95% "
                   "interval; not recomputed",
}


def _fsum(frame: pl.DataFrame, col: str) -> float:
    if frame.height == 0:
        return 0.0
    return math.fsum(frame.sort("job_uid")[col].to_list())


def _exec_kwh(led: pl.DataFrame) -> pl.Expr:
    return (pl.col("gpus") * KW_PER_GPU * PUE
            * (pl.col("end_ts").dt.epoch("us") - pl.col("start_ts").dt.epoch("us"))
            / HOUR_US).alias("exec_kwh")


# --------------------------------------------------------------------------- flows


def week_arcs(led: pl.DataFrame, w0: datetime, w1: datetime) -> list[dict]:
    """Cohort jobs arriving in [w0, w1) that executed at each destination: count and declared
    GPU-hours (math.fsum of gpus x duration_s / 3600), in DESTS order (as job-replay.json)."""
    lw = led.filter((pl.col("arrival_ts") >= w0) & (pl.col("arrival_ts") < w1))
    out = []
    for site in DESTS:
        r = lw.filter(pl.col("site") == site).sort("job_uid")
        gh = math.fsum((r["gpus"] * r["duration_s"]).to_list()) / 3600 if r.height else 0.0
        out.append({"to": site, "jobs": r.height, "gpu_h": gh})
    return out


def execution_split(led: pl.DataFrame) -> dict:
    """Execution kWh (facility) from the ledger: total, by site, remote, and retimed at home."""
    f = led.select("job_uid", "site", "moved", _exec_kwh(led))
    home = pl.col("site") == HOME
    remote = f.filter(~home)
    ret = f.filter(home & pl.col("moved"))
    return {"total_kwh": _fsum(f, "exec_kwh"), "remote_kwh": _fsum(remote, "exec_kwh"),
            "retimed_home_kwh": _fsum(ret, "exec_kwh"), "remote_jobs": remote.height,
            "retimed_home_jobs": ret.height,
            "by_site_kwh": {s: _fsum(f.filter(pl.col("site") == s), "exec_kwh") for s in SITES}}


def policy_flow(pid: str, vs_u_b4: dict, led: pl.DataFrame, w0: datetime, w1: datetime, *,
                remote_energy_share: dict, moved_share_energy: dict,
                by_site_kwh: dict[str, float], late_jobs: dict) -> dict:
    """One policy's flows. `vs_u_b4`, the shares and `late_jobs` are envelopes copied from the
    scored run; `by_site_kwh` is the scored run's execution kWh by site, which must agree with
    the ledger's own (a cross-check that the ledger is the scored one)."""
    s = execution_split(led)
    for site in SITES:
        a, b = s["by_site_kwh"][site], by_site_kwh.get(site, 0.0)
        if not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-6):
            raise AssertionError(f"{pid}: ledger execution kWh at {site} ({a}) differs from "
                                 f"the scored run's ({b})")
    tot = s["total_kwh"]
    rem = {d: env(by_site_kwh.get(d, 0.0) / 1000, "MWh", "simulated", f"{pid}:remote_mwh:{d}")
           for d in DESTS}
    share = (lambda x, k: env(x / tot, "fraction", "simulated", f"{pid}:{k}") if tot else
             env(None, "fraction", "simulated", f"{pid}:{k}", "unavailable", "no energy"))
    keep = ("saving", "saving_ci95", "diff_kg", "diff_kg_ci95", "n_weeks")
    return {
        "saving_vs_U": {k: vs_u_b4[k] for k in keep if k in vs_u_b4},
        "remote_execution_mwh": rem,
        "remote_execution_mwh_total": env(math.fsum(by_site_kwh.get(d, 0.0) for d in DESTS)
                                          / 1000, "MWh", "simulated", f"{pid}:remote_mwh"),
        "remote_execution_share": share(s["remote_kwh"], "remote_exec_share"),
        "remote_energy_share": remote_energy_share,
        "moved_share_energy": moved_share_energy,
        "retimed_home_execution_share": share(s["retimed_home_kwh"], "retimed_home_share"),
        "remote_jobs": env(s["remote_jobs"], "jobs", "simulated", f"{pid}:remote_jobs"),
        "retimed_home_jobs": env(s["retimed_home_jobs"], "jobs", "simulated",
                                 f"{pid}:retimed_home_jobs"),
        "late_jobs": late_jobs,
        "week_arcs": [{"from": HOME, "to": a["to"],
                       "jobs": env(a["jobs"], "jobs", "simulated", f"{pid}:arc:{a['to']}"),
                       "gpu_h": env(a["gpu_h"], "GPU_h", "simulated", f"{pid}:arcgh:{a['to']}")}
                      for a in week_arcs(led, w0, w1)],
    }


def flows_artifact(*, scenarios: list[dict], week: tuple[datetime, datetime],
                   registered_run_id: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "scenario-flows",
        "evidence_scope": "validation (selection) results; the sealed test window "
                          "[2025-11-01, 2026-11-01) is never read",
        "note": ("Re-read from already-computed validation runs; no new simulation. The "
                 "registered scenario is the registered result; the others are scenario "
                 "estimates (one-axis sensitivities, D-058), never pooled with it."),
        "registered_run_id": registered_run_id,
        "default_scenario": "registered",
        "default_policy": "S",
        "definitions": DEFINITIONS,
        "week": {"start": iso(week[0]), "end": iso(week[1]), "tz_display": "America/Denver"},
        "scenarios": scenarios,
    }


# --------------------------------------------------------------------------- budget


def budget(acct_u: pl.DataFrame, acct_p: pl.DataFrame, flags: pl.DataFrame, *,
           dest_slots: int, diagnosed: bool = True) -> dict:
    """Split the cohort's execution energy into the five BUCKETS for one policy.

    `acct_u`, `acct_p`: `job_accounting` rows (job_uid, site, start_ts, execution_kwh, co2_kg,
    moved, blocked, gpus) over the same jobs; `flags`: job_uid, flexible, mobile for each.
    Saving per job = U's CO2 - the policy's (execution plus transfer), so the bucket savings
    sum to the policy's saving vs U. Without the F14.7 diagnosis (`diagnosed=False`) the
    blocked bucket is not_run and blocked jobs fall where their flags and placement put them.
    """
    if acct_u.height != acct_p.height or set(acct_u["job_uid"]) != set(acct_p["job_uid"]):
        raise ValueError("U and policy accounting must cover the same jobs")
    if flags.height != acct_p.height or set(flags["job_uid"]) != set(acct_p["job_uid"]):
        raise ValueError("flags must cover the same jobs as the accounting")
    f = (acct_p.select("job_uid", "site", "moved", "blocked", "gpus",
                       pl.col("start_ts").alias("s_p"), pl.col("execution_kwh").alias("kwh"),
                       pl.col("co2_kg").alias("co2_p"))
         .join(acct_u.select("job_uid", pl.col("start_ts").alias("s_u"),
                             pl.col("co2_kg").alias("co2_u")), on="job_uid")
         .join(flags.select("job_uid", "flexible", "mobile"), on="job_uid")
         .with_columns((pl.col("co2_u") - pl.col("co2_p")).alias("sav")))
    blocked = pl.col("blocked") if diagnosed else pl.lit(False)
    must = ~(pl.col("flexible") & pl.col("mobile"))
    home = pl.col("site") == HOME
    f = f.with_columns(
        pl.when(blocked).then(pl.lit("capacity_blocked"))
        .when(must).then(pl.lit("must_stay"))
        .when(~home).then(pl.lit("moved_remote"))
        .when(pl.col("moved")).then(pl.lit("retimed_home"))
        .otherwise(pl.lit("stayed_booking")).alias("bucket"))
    total = _fsum(f, "kwh")
    saving = _fsum(f, "sav")
    out = []
    for b in BUCKETS:
        r = f.filter(pl.col("bucket") == b)
        rec = {"id": b, "text": BUCKET_TEXT[b], "status": "ok", "reason": None,
               "mwh": _fsum(r, "kwh") / 1000, "n_jobs": r.height,
               "saving_kg": _fsum(r, "sav")}
        rec["share"] = rec["mwh"] * 1000 / total if total else None
        rec["saving_share"] = rec["saving_kg"] / saving if saving else None
        if b == "retimed_home":
            rec["n_later"] = r.filter(pl.col("s_p") > pl.col("s_u")).height
            rec["n_earlier"] = r.filter(pl.col("s_p") < pl.col("s_u")).height
        if b == "stayed_booking":
            big = r.filter(pl.col("gpus") > dest_slots)
            rec["larger_than_destination_mwh"] = _fsum(big, "kwh") / 1000
            rec["larger_than_destination_jobs"] = big.height
        if b == "capacity_blocked" and not diagnosed:
            rec.update(status="not_run", mwh=None, share=None, n_jobs=None, saving_kg=None,
                       saving_share=None,
                       reason="the run was not diagnosed (no F14.7 blocked column)")
        out.append(rec)
    fm = f.filter(~must)
    return {"total_mwh": total / 1000, "saving_kg": saving, "diagnosed": diagnosed,
            "dest_slots": dest_slots,
            "flexible_mobile_share": _fsum(fm, "kwh") / total if total else None,
            "must_stay_share": _fsum(f.filter(must), "kwh") / total if total else None,
            "blocked_total_mwh": (_fsum(f.filter(pl.col("blocked")), "kwh") / 1000
                                  if diagnosed else None),
            "buckets": out}


def _e(v, unit, ev, pid, rec=None):
    if v is None:
        st = (rec or {}).get("status", "unavailable")
        return env(None, unit, ev, pid, "not_run" if st == "not_run" else "unavailable",
                   (rec or {}).get("reason") or "no saving to share")
    return env(v, unit, ev, pid)


def budget_artifact(by_policy: dict[str, dict], *, run_id: str, registered_run_id: str,
                    default: str = "S") -> dict:
    pols = {}
    for p, b in by_policy.items():
        pid = f"{run_id}:budget:{p}"
        bk = []
        for r in b["buckets"]:
            q = f"{pid}:{r['id']}"
            rec = {"id": r["id"], "text": r["text"], "status": r["status"],
                   "reason": r["reason"],
                   "mwh": _e(r["mwh"], "MWh", "simulated", f"{q}:mwh", r),
                   "share": _e(r["share"], "fraction", "simulated", f"{q}:share", r),
                   "n_jobs": _e(r["n_jobs"], "jobs", "simulated", f"{q}:n", r),
                   "saving_kg": _e(r["saving_kg"], "kg_CO2", "simulated", f"{q}:saving", r),
                   "saving_share": _e(r["saving_share"], "fraction", "simulated",
                                      f"{q}:saving_share", r)}
            for k, unit in (("n_later", "jobs"), ("n_earlier", "jobs"),
                            ("larger_than_destination_jobs", "jobs"),
                            ("larger_than_destination_mwh", "MWh")):
                if k in r:
                    rec[k] = env(r[k], unit, "simulated", f"{q}:{k}")
            bk.append(rec)
        pols[p] = {
            "total_mwh": env(b["total_mwh"], "MWh", "simulated", f"{pid}:total"),
            "saving_kg": env(b["saving_kg"], "kg_CO2", "simulated", f"{pid}:saving"),
            "flexible_mobile_share": _e(b["flexible_mobile_share"], "fraction", "simulated",
                                        f"{pid}:flex_mobile_share"),
            "must_stay_share": _e(b["must_stay_share"], "fraction", "simulated",
                                  f"{pid}:must_stay_share"),
            "blocked_total_mwh": (env(b["blocked_total_mwh"], "MWh", "simulated",
                                      f"{pid}:blocked_total")
                                  if b["diagnosed"] else
                                  env(None, "MWh", "simulated", f"{pid}:blocked_total",
                                      "not_run", "the run was not diagnosed")),
            "dest_slots": env(b["dest_slots"], "GPU_slots", "assumed", f"{pid}:dest_slots"),
            "buckets": bk,
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "flexibility-budget",
        "evidence_scope": "validation (selection) results; the sealed test window "
                          "[2025-11-01, 2026-11-01) is never read",
        "run_id": run_id,
        "registered_run_id": registered_run_id,
        "default_policy": default,
        "flags_evidence": "assumed",
        "definition": ("the registered primary's cohort execution energy (MWh, math.fsum) "
                       "split by what the policy did with each job; each bucket's share of "
                       "energy, job count, and share of the policy's CO2 saving vs U (U - "
                       "policy per job, execution plus transfer; signed). Assignment "
                       "precedence: capacity_blocked, must_stay, moved_remote, retimed_home, "
                       "stayed_booking. Flexibility and mobility flags are assumed (spec "
                       "rule); every outcome is simulated."),
        "bucket_order": list(BUCKETS),
        "policies": pols,
    }


__all__ = ["BUCKETS", "DESTS", "budget", "budget_artifact", "execution_split",
           "flows_artifact", "policy_flow", "week_arcs"]
