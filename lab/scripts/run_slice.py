"""Task 7: the registered validation run (phase 0) and the results export.

    cd lab && uv run python scripts/run_slice.py [--window validation|fallback]
                                                 [--forecast-run runs/forecast/<id>]

Pipeline (Task 7 amendment; spec §15 F11–F14):
1. jobs: `replay(init, F)` at phase 0;
2. bookings: U under the primary scenario plus the F14.1 U-changing scenarios;
3. common A (F13.2, F14.1), the cohort record written before any grid value is read;
4. the F14.6 scoring truth fill over [init, F), its mask and closure calendar;
5. the support pre-check (hard gate);
6. policies U, G, S, K, W, L, H and time-only W, L on the primary scenario;
7. accounting: score, relaxed bound and the bound check, weekly totals, the paired block
   bootstrap vs U, S and W, H2, influence, common support;
8. export: `runs/slice/<UTC>/` (atomic), then the artifacts are copied into `results/`.
9. timing, and the policy table on stdout.

All numbers are **validation** results. The sealed window is never read.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import logging
import math
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl

from gridpilot import forecast as fcmod
from gridpilot.cohort import SCENARIO_NOTES, SCENARIOS, prefix_cohort
from gridpilot.data.eia_co2 import CARBON_PATH, load_carbon
from gridpilot.data.truth_fill import (
    TIER_EVIDENCE,
    TIER_SOURCE,
    fill_mask,
    fill_truth,
    missing_hours,
    tier_counts,
)
from gridpilot.eval import (
    BOOTSTRAP_LABEL,
    BOUND_TOL_KG,
    KW_PER_GPU,
    PUE,
    TRANSFER_FRACTION,
    TruthTable,
    common_support,
    h2_decision,
    influence,
    job_accounting,
    paired_block_bootstrap,
    relaxed_bound_jobs,
    score,
    support_check,
    weekly,
)
from gridpilot.paths import MANIFEST_DIR, REPO_ROOT, RESULTS_DIR
from gridpilot.results import (
    CLAIM_FRAME,
    IMPORT_CONVENTION,
    SCHEMA_VERSION,
    check_claim_frame,
    env,
    iso,
    not_run,
    write_json_atomic,
)
from gridpilot.sim import HOME, SITES, TRANSFER_S, G, S, U, closed_intervals, simulate
from gridpilot.splits import TEST_START
from gridpilot.workload import CYCLE_DAYS, cycle_stats, replay

try:  # Task 5 (K/W/L/H); absent until it is merged
    from gridpilot.sim import CarbonSearch, tail_climatology  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - depends on the merge state
    CarbonSearch = None
    tail_climatology = None

log = logging.getLogger("run_slice")

# F14.7 blocked diagnostic (Task 5 engine flag). `blocked` is read only from diagnosed runs.
DIAGNOSE = "diagnose_blocked" in inspect.signature(simulate).parameters
DIAGNOSED_POLICIES = ("G", "S", "K", "W", "L", "H")
BLOCKED_REASON = ("F14.7 blocked diagnostic not run: needs the Task 5 engine flag "
                  "(diagnose_blocked)")

H1 = timedelta(hours=1)
WINDOWS = {
    "validation": (datetime(2024, 10, 17, tzinfo=UTC), datetime(2024, 11, 1, tzinfo=UTC),
                   datetime(2025, 10, 24, tzinfo=UTC)),
    "fallback": (datetime(2025, 7, 10, tzinfo=UTC), datetime(2025, 7, 25, tzinfo=UTC),
                 datetime(2025, 10, 24, tzinfo=UTC)),
}
RANK_TRAIN = (datetime(2022, 1, 1, tzinfo=UTC), datetime(2024, 10, 29, tzinfo=UTC))
PHASE_DAYS = 0
WARMUP_MIN = timedelta(days=15)
CARBON_POLICIES = ("K", "W", "L", "H")
POLICY_ORDER = ("U", "G", "S", "K", "W", "L", "H", "W_time", "L_time")
REFERENCES = ("U", "S", "W")
BLOCKS = (2, 4, 8)
TASK5_REASON = "Task 5 pending merge"
SNAPSHOT_ID = "05efabe781cc"
TIME_ONLY_SITES = {s: (n if s == HOME else 0) for s, n in SITES.items()}
POLICY_NOTES = {
    "U": "earliest feasible execution at PACE (FIFO); local operational reference",
    "G": "earliest finish across core sites; no carbon input",
    "S": "fixed clean-region priority by training mean consumed CI",
    "K": "carbon reservation search on frozen calendar climatology",
    "W": "carbon reservation search on weekly seasonal forecasts",
    "L": "carbon reservation search on the learned forecasts (H2 candidate)",
    "H": "same search on realized (filled) truth; hindsight diagnostic, never a contender",
    "W_time": "W restricted to PACE (destination capacity 0): time-only",
    "L_time": "L restricted to PACE (destination capacity 0): time-only",
}


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True,
                          check=False).stdout.strip()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Timer:
    def __init__(self):
        self.t: dict[str, float] = {}

    def __call__(self, name):
        timer = self

        class _T:
            def __enter__(self):
                self.t0 = time.perf_counter()

            def __exit__(self, *exc):
                timer.t[name] = timer.t.get(name, 0.0) + time.perf_counter() - self.t0
                log.info("%s: %.1f s", name, timer.t[name])
        return _T()


class RemoteProbe:
    """Wraps a policy; at each flexible job's arrival, records the earliest on-time feasible
    start at every legal site in the capacity the policy sees (bookings held, its own
    released). Used on the U replay for the §11 illustrative-job rule."""

    def __init__(self, inner):
        self.inner, self.name = inner, inner.name
        self.actions: dict[str, dict[str, int]] = {}

    def choose(self, job, now, capacities, ctx):
        if job.flexible:
            acts = {}
            for site in ctx.legal_sites(job):
                s = ctx.earliest_start(job, site, capacities, latest=job.latest_start_us)
                if s is not None:
                    acts[site] = s
            if any(site != ctx.home for site in acts):
                self.actions[job.job_uid] = acts
        return self.inner.choose(job, now, capacities, ctx)


def _us_dt(us: int) -> datetime:
    return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(microseconds=int(us))


def _dt_us(t: datetime) -> int:
    return (t - datetime(1970, 1, 1, tzinfo=UTC)) // timedelta(microseconds=1)


# --------------------------------------------------------------------------- pipeline


def s_ranking() -> tuple[list[str], dict[str, float]]:
    """S's ranking: mean consumed CI over the training rows, ascending (PACE included)."""
    c = load_carbon().filter((pl.col("ts_utc") >= RANK_TRAIN[0]) & (pl.col("ts_utc") < RANK_TRAIN[1])
                             & pl.col("ba").is_in(list(SITES)))
    r = c.group_by("ba").agg(pl.col("ci_consumed_g_kwh").mean().alias("m"),
                             pl.col("ci_consumed_g_kwh").count().alias("n")).sort("m", "ba")
    return r["ba"].to_list(), {b: float(m) for b, m in zip(r["ba"], r["m"], strict=True)}


def bound_gap(acc: pl.DataFrame, per: pl.DataFrame) -> dict:
    """Cohort gap as math.fsum of per-job (policy − bound) differences (T6 #12)."""
    j = acc.select("job_uid", "co2_kg").join(per.select("job_uid", pl.col("co2_kg").alias("b")),
                                             on="job_uid", how="inner")
    if j.height != acc.height:
        raise AssertionError("bound and ledger cover different jobs")
    d = (j["co2_kg"] - j["b"]).to_numpy()
    gap = math.fsum(d.tolist())
    return {"gap_kg": gap, "min_job_gap_kg": float(d.min()) if d.size else 0.0,
            "n_job_gap_lt0": int((d < 0).sum()), "ok": gap >= -BOUND_TOL_KG}


def build_policies(ranking, forecasts, filled, mask):
    pols = {"U": (U(), SITES), "G": (G(), SITES), "S": (S(ranking), SITES)}
    if CarbonSearch is None:
        return pols, {}
    tail = tail_climatology(list(SITES))
    out = dict(pols)
    for sig in ("K", "W", "L"):
        out[sig] = (CarbonSearch(sig, forecasts, None, mask, tail=tail), SITES)
    out["H"] = (CarbonSearch("H", None, filled, mask, truth_col="ci_g_kwh"), SITES)
    for sig in ("W", "L"):
        p = CarbonSearch(sig, forecasts, None, mask, tail=tail)
        p.name = f"{sig}_time"
        out[f"{sig}_time"] = (p, TIME_ONLY_SITES)
    return out, {}


def run(args) -> int:
    timer = Timer()
    init, eval_start, F = WINDOWS[args.window]
    if eval_start - init < WARMUP_MIN:
        raise AssertionError("warm-up shorter than 15 days (F2)")
    if F > TEST_START:
        raise AssertionError("F reaches the seal")
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    root = Path(args.out) if args.out else REPO_ROOT / "runs" / "slice"
    root.mkdir(parents=True, exist_ok=True)
    tmp = root / f".tmp-{run_id}-{os.getpid()}"
    final = root / run_id
    tmp.mkdir()
    sha = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain")
    (tmp / "git.txt").write_text(f"sha {sha}\nstatus:\n{status}\n")
    try:
        rc = _pipeline(args, timer, tmp, run_id, sha, status, init, eval_start, F)
        os.rename(tmp, final)
    except BaseException:
        failed = root / f"failed-{run_id}"
        os.rename(tmp, failed)
        log.error("run failed; partial outputs in %s", failed)
        raise
    print(f"run directory: {final}")
    if rc == 0 and not args.no_export:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        for p in sorted((final / "results").glob("*.json")):
            shutil.copyfile(p, RESULTS_DIR / f".{p.name}.tmp")
            os.replace(RESULTS_DIR / f".{p.name}.tmp", RESULTS_DIR / p.name)
        print(f"exported {len(list((final / 'results').glob('*.json')))} artifacts to {RESULTS_DIR}")
    return rc


def _pipeline(args, timer, tmp, run_id, sha, status, init, eval_start, F) -> int:
    # 0. Forecasts (Task 2): constructed fresh unless a run is given.
    with timer("forecast_construction"):
        if args.forecast_run:
            fc_dir = Path(args.forecast_run)
        else:
            fc_dir = fcmod.run_validation(out_root=tmp / "forecast")
        forecasts = pl.read_parquet(fc_dir / "forecasts.parquet")
        fc_metrics = json.loads((fc_dir / "metrics.json").read_text())
    for c in ("issue_ts", "target_ts"):
        if forecasts[c].max() >= TEST_START:
            raise AssertionError("forecasts reach the seal")

    # 1. Jobs.
    with timer("replay"):
        jobs = replay(init, F, phase_days=PHASE_DAYS)
        warm_jobs = jobs.filter(pl.col("arrival_ts") < eval_start)
        stream = jobs.filter(pl.col("arrival_ts") >= eval_start)

    # 2–3. Bookings and the common A.
    with timer("bookings"):
        coh = prefix_cohort(warm_jobs, stream, F, scenarios=SCENARIOS, sites=SITES)
    cj, bookings, warm = coh.jobs, coh.bookings, coh.warm
    wl = warm.ledger
    cohort_record = {
        "window": args.window, "phase_days": PHASE_DAYS,
        "init": iso(init), "eval_start": iso(eval_start), "F": iso(F), "A": iso(coh.A),
        "first_failure": {k: iso(v) for k, v in coh.first_failure.items()},
        "n_stream": coh.n_stream, "n_cohort": cj.height, "n_excluded": coh.n_excluded,
        "excluded_gpu_h": coh.excluded_gpu_h,
        "cohort_ids_sha256": coh.ids_hash, "booking_sha256": coh.booking_hash,
        "prefix_bookings_unchanged": coh.prefix_unchanged,
        "drain": {"max_booking_end": iso(coh.max_booking_end),
                  "max_deadline": iso(coh.max_deadline), "drain_window": [iso(coh.A), iso(F)]},
        "warmup": {"n_jobs": wl.height,
                   "gpu_h": float((wl["gpus"] * wl["duration_s"]).sum() / 3600),
                   "last_arrival": iso(_us_dt(warm.last_arrival_us)),
                   "last_completion": iso(wl["end_ts"].max())},
        "recorded_before_grid_scoring": True,
    }
    (tmp / "cohort.json").write_text(json.dumps(cohort_record, indent=1) + "\n")
    bookings.write_parquet(tmp / "bookings.parquet")
    log.info("A = %s, cohort %d jobs, %d excluded", coh.A, cj.height, coh.n_excluded)

    # 4. Scoring truth fill (F14.6).
    with timer("truth_fill"):
        filled = fill_truth(init, F, list(SITES))
        mask = fill_mask(filled)
        closed = closed_intervals(mask)
        tt = TruthTable(filled, mask)
    if any(closed.values()):
        # Bookings were built before the fill with no closures (F13.3 pre-check uses filled
        # truth); a non-empty calendar would require u_bookings(closed=...) first.
        raise AssertionError(f"closure calendar not empty after tier 4: {missing_hours(filled)}")
    tiers = tier_counts(filled)
    still_missing = missing_hours(filled)
    filled.write_parquet(tmp / "truth_fill.parquet")

    # 5. Support pre-check (hard gate).
    sc_b = support_check(bookings, tt, F)
    sc_w = support_check(wl, tt, F)
    support = {"bookings": {k: v for k, v in sc_b.items() if k != "failures"},
               "warmup_ledger": {k: v for k, v in sc_w.items() if k != "failures"}}
    if not (sc_b["ok"] and sc_w["ok"]):
        (tmp / "support_failure.json").write_text(json.dumps(
            {"bookings": sc_b, "warmup_ledger": sc_w}, indent=1, default=str))
        log.error("accounting-support failure: %s", support)
        return 2

    # 6. Policies.
    ranking, rank_means = s_ranking()
    policies, _ = build_policies(ranking, forecasts, filled, mask)
    ledgers: dict[str, pl.DataFrame] = {}
    probe = None
    for name in POLICY_ORDER:
        if name not in policies:
            continue
        pol, sites = policies[name]
        if name == "U":
            pol = probe = RemoteProbe(pol)
        kw = {"diagnose_blocked": True} if DIAGNOSE and name in DIAGNOSED_POLICIES else {}
        with timer(f"policy_{name}"):
            led = simulate(cj, pol, sites, bookings=bookings, warm=warm, closed=closed, **kw)
        ledgers[name] = led
        led.write_parquet(tmp / f"ledger_{name}.parquet")

    # 7. Accounting.
    with timer("accounting"):
        acct = accounting(ledgers, policies, cj, bookings, warm, tt, eval_start, coh.A)
    # 8. Export.
    with timer("export"):
        art = build_artifacts(
            args=args, run_id=run_id, sha=sha, status=status, init=init,
            eval_start=eval_start, F=F, coh=coh, cohort_record=cohort_record, tiers=tiers,
            still_missing=still_missing, support=support, ranking=ranking,
            rank_means=rank_means, ledgers=ledgers, acct=acct, cj=cj, bookings=bookings,
            tt=tt, filled=filled, forecasts=forecasts, fc_metrics=fc_metrics, fc_dir=fc_dir,
            probe=probe, timer=timer)
        out = tmp / "results"
        hashes = {}
        for name in ("metrics.json", "forecast-replay.json", "job-replay.json"):
            text = write_json_atomic(out / name, art[name])
            hashes[name] = hashlib.sha256(text.encode()).hexdigest()
        man = art["manifest.json"]
        man["artifact_sha256"] = hashes
        man["timing_s"] = {k: env(v, "s", "measured", f"{run_id}:timing:{k}")
                           for k, v in timer.t.items()}
        check_claim_frame(man)
        write_json_atomic(out / "manifest.json", man)
    print_table(acct, timer)
    if not acct["bound_all_ok"]:
        log.error("feasible >= bound FAILED")
        return 3
    return 0


# --------------------------------------------------------------------------- accounting


def accounting(ledgers, policies, cj, bookings, warm, tt, eval_start, A) -> dict:
    per = relaxed_bound_jobs(cj, tt, bookings=bookings, sites=SITES, transfer_s=TRANSFER_S)
    if per["co2_kg"].null_count():
        raise AssertionError("a cohort job has no legal action in the relaxed envelope")
    per_t = relaxed_bound_jobs(cj, tt, bookings=bookings, sites=TIME_ONLY_SITES,
                               transfer_s=TRANSFER_S)
    bounds = {"primary": math.fsum(per["co2_kg"].to_list()),
              "time_only": math.fsum(per_t["co2_kg"].to_list())}
    scores, gaps, weeks = {}, {}, {}
    for name, led in ledgers.items():
        sites = policies[name][1]
        m = score(led, cj, tt, sites=sites, warm=warm)
        acc = job_accounting(led, cj, tt)
        gaps[name] = {"primary": bound_gap(acc, per)}
        if sites is TIME_ONLY_SITES:
            gaps[name]["time_only"] = bound_gap(acc, per_t)
        if m["feasible"] and not all(g["ok"] for g in gaps[name].values()):
            log.error("%s: feasible but below the bound: %s", name, gaps[name])
        scores[name] = m
        weeks[name] = weekly(led, cj, tt, window=(eval_start, A))
    bound_all_ok = all(g["ok"] for n in gaps for g in gaps[n].values() if scores[n]["feasible"])
    contrasts = {}
    for ref in REFERENCES:
        if ref not in weeks:
            continue
        for name, wk in weeks.items():
            if name == ref:
                continue
            contrasts[f"{name}_vs_{ref}"] = {
                b: paired_block_bootstrap(weeks[ref], wk, block=b) for b in BLOCKS}
    h2 = h2_decision(weeks["W"], weeks["L"]) if "W" in weeks and "L" in weeks else None
    inf = influence({k: v for k, v in ledgers.items()}, cj, tt, k_list=(1, 5, 10))
    cs = common_support(ledgers, tt)
    n_weeks = weeks["U"].height
    return {"scores": scores, "gaps": gaps, "bounds": bounds, "bound_all_ok": bound_all_ok,
            "weeks": weeks, "contrasts": contrasts, "h2": h2, "influence": inf,
            "common_support": cs, "n_weeks": n_weeks, "bound_per_job": per}


# --------------------------------------------------------------------------- export


EVIDENCE_POLICY = "simulated"
METRIC_UNITS = {
    "n_jobs": "jobs", "requested_gpu_s": "GPU_s", "completed_gpu_s": "GPU_s",
    "late_jobs": "jobs", "late_gpu_h": "GPU_h", "capacity_violations": "sites",
    "wait_p50_s": "s", "wait_p95_s": "s", "wait_max_s": "s", "wait_mean_s": "s",
    "execution_kwh": "kWh", "transfer_kwh": "kWh", "transfer_it_kwh": "kWh",
    "energy_kwh": "kWh", "kwh_share_tier_ge2": "fraction", "execution_co2_kg": "kg_CO2",
    "transfer_co2_kg": "kg_CO2", "co2_kg": "kg_CO2", "co2_kg_per_1000_gpu_h": "kg_CO2/1000_GPU_h",
    "moved_jobs": "jobs", "moved_share_jobs": "fraction", "moved_share_energy": "fraction",
    "remote_jobs": "jobs", "remote_energy_share": "fraction", "blocked_jobs": "jobs",
    "blocked_kwh": "kWh",
}


def _policy_record(name, m, gaps, run_id, n_weeks) -> dict:
    pid = f"{run_id}:{name}"
    diagnosed = DIAGNOSE and name in DIAGNOSED_POLICIES
    rec = {"policy": name, "status": "ok", "reason": None, "note": POLICY_NOTES[name],
           "contender": name != "H", "feasible": bool(m["feasible"]),
           "conserved": bool(m["conserved"]),
           "metrics": {}}
    for k, unit in METRIC_UNITS.items():
        v = m.get(k)
        if k in ("blocked_jobs", "blocked_kwh") and not diagnosed:
            rec["metrics"][k] = not_run(unit, EVIDENCE_POLICY, f"{pid}:{k}",
                                        BLOCKED_REASON if name in DIAGNOSED_POLICIES
                                        else "F14.7 is reported for G, S, K, W, L and H only")
        elif v is None:
            rec["metrics"][k] = env(None, unit, EVIDENCE_POLICY, f"{pid}:{k}",
                                    status="unavailable", reason="undefined (zero denominator)")
        else:
            rec["metrics"][k] = env(v, unit, EVIDENCE_POLICY, f"{pid}:{k}")
    rec["metrics"]["peak_gpus"] = {s: env(v, "GPUs", EVIDENCE_POLICY, f"{pid}:peak_gpus:{s}")
                                   for s, v in m["peak_gpus"].items()}
    rec["bound_check"] = {
        basis: {"ok": g["ok"],
                "gap_kg": env(g["gap_kg"], "kg_CO2", "modeled", f"{pid}:bound_gap:{basis}"),
                "min_job_gap_kg": env(g["min_job_gap_kg"], "kg_CO2", "modeled",
                                      f"{pid}:min_job_gap:{basis}"),
                "n_job_gap_lt0": env(g["n_job_gap_lt0"], "jobs", "modeled",
                                     f"{pid}:n_job_gap_lt0:{basis}"),
                "tolerance_kg": env(BOUND_TOL_KG, "kg_CO2", "assumed", "F14.5:tolerance")}
        for basis, g in gaps.items()}
    return rec


def _not_run_record(name, run_id) -> dict:
    pid = f"{run_id}:{name}"
    return {"policy": name, "status": "not_run", "reason": TASK5_REASON,
            "note": POLICY_NOTES[name], "contender": name != "H", "feasible": None,
            "conserved": None,
            "metrics": {k: not_run(u, EVIDENCE_POLICY, f"{pid}:{k}", TASK5_REASON)
                        for k, u in METRIC_UNITS.items()},
            "bound_check": None}


def _interval(ci, unit, evidence, pid, null_reason="undefined") -> dict:
    if ci is None:
        return env(None, unit, evidence, pid, status="unavailable", reason=null_reason)
    return env(list(ci), unit, evidence, pid)


def _contrast_record(name, ref, by_b, run_id, n_weeks) -> dict:
    pid = f"{run_id}:{name}_vs_{ref}"
    out = {"candidate": name, "reference": ref, "method": BOOTSTRAP_LABEL,
           "definition": "reference − candidate (positive = candidate emits less); "
                         "saving = ratio of totals", "blocks": {}}
    for b, r in by_b.items():
        label = []
        if r["degenerate"]:
            label.append("degenerate (n_weeks <= block: interval collapses to the point)")
        if b == 8 and n_weeks <= 8:
            label.append("low-n")
        out["blocks"][str(b)] = {
            "primary": b == 4,
            "labels": label,
            "n_weeks": env(r["n_weeks"], "weeks", "simulated", f"{pid}:b{b}:n_weeks"),
            "reps": env(r["reps"], "replicates", "assumed", "F12.4:reps"),
            "diff_kg": env(r["diff_kg"], "kg_CO2", "simulated", f"{pid}:b{b}:diff_kg",
                           *(("unavailable", "empty input") if r["diff_kg"] is None else ())),
            "diff_kg_ci95": _interval(r["diff_kg_ci"], "kg_CO2", "simulated",
                                      f"{pid}:b{b}:diff_kg_ci", "empty input"),
            "saving": env(r["saving"], "fraction", "simulated", f"{pid}:b{b}:saving",
                          *(("unavailable", "zero reference total") if r["saving"] is None
                            else ())),
            "saving_ci95": _interval(r["saving_ci"], "fraction", "simulated",
                                     f"{pid}:b{b}:saving_ci",
                                     r["saving_ci_null_reason"] or "undefined"),
        }
    return out


def _h2_record(h2, run_id) -> dict:
    if h2 is None:
        return {"status": "not_run", "reason": TASK5_REASON, "population": "full phase-0 cohort",
                "statistic": "W − L kg CO₂ (positive = L emits less)", "direction": None,
                "decided": None,
                "intervals": {str(b): not_run("kg_CO2", "simulated", f"{run_id}:h2:b{b}",
                                              TASK5_REASON) for b in BLOCKS}}
    return {"status": "ok", "reason": h2["reason"], "population": "full phase-0 cohort (F14.3)",
            "statistic": h2["statistic"], "direction": h2["direction"], "decided": h2["decided"],
            "n_weeks": env(h2["n_weeks"], "weeks", "simulated", f"{run_id}:h2:n_weeks"),
            "intervals": {str(b): {
                "diff_kg": env(r["diff_kg"], "kg_CO2", "simulated", f"{run_id}:h2:b{b}:diff"),
                "diff_kg_ci95": _interval(r["diff_kg_ci"], "kg_CO2", "simulated",
                                          f"{run_id}:h2:b{b}:ci")}
                for b, r in h2["intervals"].items()}}


def _weekly_record(weeks, run_id) -> dict:
    any_w = next(iter(weeks.values()))
    return {"week_start_local": [w.isoformat() for w in any_w["week"].to_list()],
            "tz": "America/Denver (Monday 00:00)",
            "co2_kg": {p: env(w["co2_kg"].to_numpy(), "kg_CO2", "simulated",
                              f"{run_id}:{p}:weekly_co2") for p, w in weeks.items()},
            "n_jobs": env(any_w["n_jobs"].to_numpy(), "jobs", "simulated",
                          f"{run_id}:weekly_n_jobs")}


def _flex_shares(cj, run_id) -> dict:
    gh = cj["gpus"] * cj["duration_s"] / 3600
    tot = float(gh.sum())
    out = {}
    for flag in ("flexible", "mobile"):
        m = cj[flag]
        out[flag] = {"by_jobs": env(float(m.mean()), "fraction", "assumed",
                                    f"{run_id}:share_{flag}_jobs"),
                     "by_gpu_h": env(float(gh.filter(m).sum()) / tot, "fraction", "assumed",
                                     f"{run_id}:share_{flag}_gpu_h")}
    out["max_delay_s"] = {str(int(k)): env(int(v), "jobs", "assumed", f"{run_id}:delay_{k}")
                          for k, v in cj.group_by("max_delay_s").len().sort("max_delay_s")
                          .iter_rows()}
    return out


def build_artifacts(**k) -> dict:
    run_id, coh, acct = k["run_id"], k["coh"], k["acct"]
    scores, gaps = acct["scores"], acct["gaps"]
    cj = k["cj"]
    n_weeks = acct["n_weeks"]

    # metrics.json
    policies = {}
    for name in POLICY_ORDER:
        if name in scores:
            policies[name] = _policy_record(name, scores[name], gaps[name], run_id, n_weeks)
        else:
            policies[name] = _not_run_record(name, run_id)
    contrasts = []
    for ref in REFERENCES:
        for name in POLICY_ORDER:
            if name == ref:
                continue
            key = f"{name}_vs_{ref}"
            if key in acct["contrasts"]:
                contrasts.append(_contrast_record(name, ref, acct["contrasts"][key], run_id,
                                                  n_weeks))
            else:
                contrasts.append({"candidate": name, "reference": ref, "status": "not_run",
                                  "reason": TASK5_REASON,
                                  "diff_kg": not_run("kg_CO2", "simulated",
                                                     f"{run_id}:{key}", TASK5_REASON)})
    inf = acct["influence"]
    influence_rec = {
        "reference": inf["reference"], "rank_by": "declared GPU-hours per unique source attempt",
        "by_k": {str(kk): {
            "removed_sources": d["removed_sources"],
            "removed_jobs": env(d["removed_jobs"], "jobs", "simulated", f"{run_id}:inf:{kk}:n"),
            "saving_vs_U": {p: env(v["saving"], "fraction", "simulated",
                                   f"{run_id}:inf:{kk}:{p}",
                                   *(("unavailable", "zero reference") if v["saving"] is None
                                     else ()))
                            for p, v in d["vs_reference"].items()}}
            for kk, d in inf["by_k"].items()}}
    metrics = {
        "schema_version": SCHEMA_VERSION, "run_id": run_id, "window": k["args"].window,
        "evidence_note": "validation results; policy outcomes simulated; bound modeled",
        "covered": {"arrivals": [iso(k["eval_start"]), iso(coh.A)],
                    "drain": [iso(coh.A), iso(k["F"])]},
        "cohort": {
            "n_jobs": env(cj.height, "jobs", "simulated", f"{run_id}:cohort:n"),
            "declared_gpu_h": env(float((cj["gpus"] * cj["duration_s"]).sum() / 3600), "GPU_h",
                                  "measured", f"{run_id}:cohort:gpu_h"),
            "n_excluded": env(coh.n_excluded, "jobs", "simulated", f"{run_id}:cohort:excluded"),
            "excluded_gpu_h": env(coh.excluded_gpu_h, "GPU_h", "measured",
                                  f"{run_id}:cohort:excluded_gpu_h"),
            "n_weeks": env(n_weeks, "weeks", "simulated", f"{run_id}:n_weeks"),
            "flex_shares": _flex_shares(cj, run_id),
        },
        "policies": policies,
        "relaxed_bound": {
            "primary": env(acct["bounds"]["primary"], "kg_CO2", "modeled", f"{run_id}:bound"),
            "time_only": env(acct["bounds"]["time_only"], "kg_CO2", "modeled",
                             f"{run_id}:bound_time_only"),
            "note": "C_relaxed: a lower bound (never a ceiling); its possible reduction belongs "
                    "in the evidence drawer only (F7)",
            "all_feasible_policies_ok": acct["bound_all_ok"],
        },
        "contrasts": contrasts,
        "h2": _h2_record(acct["h2"], run_id),
        "influence": influence_rec,
        "common_support": {
            "n_dropped_jobs": env(len(acct["common_support"]), "jobs", "simulated",
                                  f"{run_id}:common_support"),
            "status_rerun": "not_run",
            "reason": "the common-support sensitivity rerun is scheduled after 18:00 (Task 7 "
                      "amendment step 7)"},
        "weekly": _weekly_record(acct["weeks"], run_id),
    }

    # forecast-replay.json and job-replay.json
    frep = forecast_replay(k)
    jrep = job_replay(k)

    # manifest.json
    m_inputs = {p.name: _sha256(p) for p in sorted(MANIFEST_DIR.glob("*.json"))}
    tiers = k["tiers"]
    manifest = {
        "schema_version": SCHEMA_VERSION, "run_id": run_id, "git_sha": k["sha"],
        "git_clean": k["status"] == "", "snapshot_id": SNAPSHOT_ID,
        "wallclock_generated_at": datetime.now(UTC).isoformat(),
        "reproduce": f"make slice  # cd lab && uv run python scripts/run_slice.py --window "
                     f"{k['args'].window}",
        "evidence_scope": "validation (selection) results; the sealed test window "
                          "[2025-11-01, 2026-11-01) is never read",
        "claim_frame": CLAIM_FRAME,
        "limitations": [
            fcmod.LIMITATION, IMPORT_CONVENTION,
            "EIA's 2025-26 emission factors may be a provisional vintage (F7).",
            ("Baseline bookings are an assumed advance-reservation calendar synthesized from "
             "the whole U replay (F11, F12.7); the result is not a historical online-router "
             "claim."),
            ("Missing truth hours are filled by the pre-registered F14.6 tiers; the closure "
             "calendar is an assumed advance-known calendar (F12.1)."),
        ],
        "inputs": {"data_manifests_sha256": m_inputs,
                   "carbon_hourly_sha256": _sha256(CARBON_PATH),
                   "forecast_run": str(k["fc_dir"].name),
                   "forecast_metrics_run_id": k["fc_metrics"].get("run_id")},
        "split": {"window": k["args"].window, "init": iso(k["init"]),
                  "eval_start": iso(k["eval_start"]), "A": iso(coh.A), "F": iso(k["F"]),
                  "sealed_window": "test window [TEST_START = 2025-11-01T00:00Z, "
                                   "2026-11-01T00:00Z): never read by this run",
                  "phase_days": env(PHASE_DAYS, "days", "assumed", "spec§7:phase"),
                  "s_ranking_training_rows": [iso(RANK_TRAIN[0]), iso(RANK_TRAIN[1])],
                  "forecast_fit_at": iso(fcmod.VAL_FIT_AT)},
        "cohort_record": _cohort_record_env(k["cohort_record"], run_id),
        "scenarios_for_A": {n: {"note": SCENARIO_NOTES[n],
                                "first_failure": iso(coh.first_failure[n]),
                                "policies_run": n == "primary"} for n in SCENARIOS},
        "truth_fill": {
            "rule": "F14.6: first available of tiers 1-4; forecasts never used as fill",
            "tiers": {str(t): {"source": TIER_SOURCE[t], "evidence": TIER_EVIDENCE[t]}
                      for t in TIER_SOURCE},
            "hours_by_ba": {ba: {t: env(n, "hours", TIER_EVIDENCE[int(t)] if t != "missing"
                                        else "modeled", f"{run_id}:tier:{ba}:{t}")
                                 for t, n in row.items()} for ba, row in tiers.items()},
            "window": [iso(k["init"]), iso(k["F"])],
            "missing_after_tier4": k["still_missing"],
        },
        "support_check": _support_env(k["support"], run_id),
        "s_ranking": {"order": k["ranking"],
                      "mean_consumed_ci": {b: env(v, "g/kWh", "observed",
                                                  f"{run_id}:rank:{b}")
                                           for b, v in k["rank_means"].items()},
                      "note": "unweighted hourly mean over training rows; never shown as an "
                              "attributed factor (F7)"},
        "assumptions": {
            "home_slots": env(SITES[HOME], "GPU_slots", "assumed", "spec§7:home_slots"),
            "destination_slots": {s: env(n, "GPU_slots", "assumed", f"spec§7:slots:{s}")
                                  for s, n in SITES.items() if s != HOME},
            "kw_per_gpu": env(KW_PER_GPU, "kW", "assumed", "F7:kw_per_gpu"),
            "pue": env(PUE, "ratio", "assumed", "F7:pue"),
            "transfer_energy_fraction": env(TRANSFER_FRACTION, "fraction", "assumed",
                                            "F7:transfer_fraction"),
            "transfer_time_s": env(TRANSFER_S, "s", "assumed", "spec§7:transfer_time"),
            "allowed_delay_s": {t: env(v, "s", "assumed", f"spec§7:delay:{t}")
                                for t, v in {"Pretrain": 21600, "SFT": 21600, "MLLM": 21600,
                                             "Eval": 3600, "other": 0}.items()},
            "flexibility_rule": "candidate type and int(sha256(f'{source_job_id}:42'), 16) % 2 "
                                "== 0; mobile iff flexible (assumed)",
            "deadline_rule": "max(arrival + duration + allowed delay, finish under U) (F1)",
            "bookings": "every job holds its U booking as a fallback (F11; assumed)",
            "replay": f"Seren {CYCLE_DAYS}-day cycle at phase 0 (simulated arrivals; measured "
                      f"durations and GPU counts)",
            "bootstrap": {"method": BOOTSTRAP_LABEL,
                          "blocks": env(list(BLOCKS), "weeks", "assumed", "F12.4:blocks"),
                          "primary_block": env(4, "weeks", "assumed", "F12.4:primary_block"),
                          "reps": env(2000, "replicates", "assumed", "F12.4:reps"),
                          "seed": "20261027"},
        },
        "workload": _workload_env(run_id),
        "not_before_18": ["F14.7 blocked diagnostic", "phases 49 and 98",
                          "sensitivity-scenario policy runs", "production-basis repricing",
                          "shadow-U and missingness-blind sensitivities", "F12.6 rebuild"],
        "task5_status": ("merged" if CarbonSearch is not None
                         else f"K/W/L/H not run: {TASK5_REASON}"),
        "artifacts": ["manifest.json", "metrics.json", "forecast-replay.json",
                      "job-replay.json"],
    }
    return {"manifest.json": manifest, "metrics.json": metrics,
            "forecast-replay.json": frep, "job-replay.json": jrep}


def _cohort_record_env(r, run_id) -> dict:
    out = dict(r)
    out["phase_days"] = env(r["phase_days"], "days", "assumed", "spec§7:phase")
    out["n_stream"] = env(r["n_stream"], "jobs", "simulated", f"{run_id}:n_stream")
    out["n_cohort"] = env(r["n_cohort"], "jobs", "simulated", f"{run_id}:n_cohort")
    out["n_excluded"] = env(r["n_excluded"], "jobs", "simulated", f"{run_id}:n_excluded")
    out["excluded_gpu_h"] = env(r["excluded_gpu_h"], "GPU_h", "measured",
                                f"{run_id}:excluded_gpu_h")
    w = dict(r["warmup"])
    w["n_jobs"] = env(w["n_jobs"], "jobs", "simulated", f"{run_id}:warmup:n")
    w["gpu_h"] = env(w["gpu_h"], "GPU_h", "measured", f"{run_id}:warmup:gpu_h")
    out["warmup"] = w
    return out


def _support_env(s, run_id) -> dict:
    out = {}
    for part, d in s.items():
        out[part] = {"ok": d["ok"], "F": d["F"]}
        for key in ("n_checked", "n_after_f", "n_missing_truth", "n_filled_truth"):
            out[part][key] = env(d[key], "jobs", "simulated", f"{run_id}:support:{part}:{key}")
    return out


def _workload_env(run_id) -> dict:
    st = cycle_stats()
    units = {"unique_attempts": "attempts", "instances": "jobs", "gpu_hours": "GPU_h"}
    return {k: env(v, units.get(k, "fraction"), "measured", f"{run_id}:cycle:{k}")
            for k, v in st.items()}


# --------------------------------------------------------------------------- replays


def _replay_week(eval_start: datetime) -> tuple[datetime, datetime]:
    """The first complete Monday-00:00 America/Denver week starting at or after eval_start."""
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("America/Denver")
    d = eval_start.astimezone(tz).date()
    while True:
        start = datetime(d.year, d.month, d.day, tzinfo=tz)
        if d.weekday() == 0 and start >= eval_start:
            break
        d += timedelta(days=1)
    end = start + timedelta(days=7)
    end = datetime(end.year, end.month, end.day, tzinfo=tz)  # wall-clock Monday 00:00
    return start.astimezone(UTC), end.astimezone(UTC)


def forecast_replay(k) -> dict:
    run_id = k["run_id"]
    w0, w1 = _replay_week(k["eval_start"])
    fc = k["forecasts"].filter((pl.col("ba") == HOME) & (pl.col("target") == "ci_consumed")
                               & (pl.col("target_ts") >= w0) & (pl.col("target_ts") < w1))
    hours = pl.datetime_range(w0, w1 - H1, "1h", time_unit="us", time_zone="UTC", eager=True)
    hrs = pl.DataFrame({"target_ts": hours})
    filled = k["filled"].filter(pl.col("ba") == HOME)
    obs = hrs.join(filled.select(pl.col("ts_utc").alias("target_ts"), "ci_g_kwh", "tier"),
                   on="target_ts", how="left")
    observed = [v if t == 1 else None for v, t in zip(obs["ci_g_kwh"], obs["tier"],
                                                      strict=True)]
    series, issue_of = {}, None
    for model in ("K", "W", "L"):
        f = hrs.join(fc.filter(pl.col("model") == model).select("target_ts", "issue_ts", "value"),
                     on="target_ts", how="left")
        series[model] = f["value"].to_list()
        issue_of = f["issue_ts"]
    issues = sorted({t for t in issue_of.to_list() if t is not None})
    env_h = fcmod.ENVELOPE_H["ci_consumed"]
    issue_rows = [{"issue_ts": iso(i),
                   "target_day": [iso(fcmod.target_hours(i)[0]),
                                  iso(fcmod.target_hours(i)[-1] + H1)],
                   "data_cutoff_hour_start": iso(i - (1 + env_h) * H1)} for i in issues]
    # Observed history ending at the first issue's publication cutoff (story beat 1).
    first = issues[0]
    cut = first - (1 + env_h) * H1
    hist_hours = pl.datetime_range(cut - 167 * H1, cut, "1h", time_unit="us", time_zone="UTC",
                                   eager=True)
    hist = pl.DataFrame({"ts_utc": hist_hours}).join(
        filled.select("ts_utc", "ci_g_kwh", "tier"), on="ts_utc", how="left")
    errors = {}
    obs_arr = np.array([np.nan if v is None else v for v in observed])
    for model, vals in series.items():
        v = np.array([np.nan if x is None else x for x in vals])
        ok = np.isfinite(v) & np.isfinite(obs_arr)
        e = v[ok] - obs_arr[ok]
        errors[model] = {"mae": env(float(np.abs(e).mean()) if e.size else None, "g/kWh",
                                    "measured", f"{run_id}:fr:{model}:mae",
                                    *(() if e.size else ("unavailable", "no hours"))),
                         "bias": env(float(e.mean()) if e.size else None, "g/kWh", "measured",
                                     f"{run_id}:fr:{model}:bias",
                                     *(() if e.size else ("unavailable", "no hours"))),
                         "n_hours": env(int(ok.sum()), "hours", "measured",
                                        f"{run_id}:fr:{model}:n")}
    sel = k["fc_metrics"]["series"].get(f"{HOME}/ci_consumed", {})
    sel_mae = {m: env(sel["models"][m]["selection"]["mae"], "g/kWh", "measured",
                      f"{k['fc_metrics']['run_id']}:{HOME}/ci_consumed:{m}:selection_mae")
               for m in ("K", "W", "L")} if sel else {}

    def nulls_reason(xs):
        return "null = hour without a tier-1 (observed) value" if any(x is None for x in xs) \
            else None

    return {
        "schema_version": SCHEMA_VERSION, "run_id": run_id, "ba": HOME,
        "target": "ci_consumed (EIA consumption-basis CO2 intensity)",
        "week": {"start": iso(w0), "end": iso(w1), "tz_display": "America/Denver",
                 "rule": "first complete Monday 00:00 America/Denver week at or after "
                         "eval_start (completeness only)"},
        "issue_rule": "daily at 10:00 America/Denver for the next Utah civil day; a row is "
                      f"usable iff ts_utc + 1 h + {env_h} h <= issue (assumed envelope)",
        "issues": issue_rows,
        "hours": [iso(h) for h in hours.to_list()],
        "observed": env(observed, "g/kWh", "observed", f"{run_id}:fr:observed",
                        reason=nulls_reason(observed)),
        "forecasts": {m: env(v, "g/kWh", "forecast", f"{k['fc_metrics']['run_id']}:{m}",
                             reason=nulls_reason(v) and "null = no issued forecast")
                      for m, v in series.items()},
        "history_to_first_cutoff": {
            "hours": [iso(h) for h in hist_hours.to_list()],
            "observed": env([v if t == 1 else None for v, t in
                             zip(hist["ci_g_kwh"], hist["tier"], strict=True)], "g/kWh",
                            "observed", f"{run_id}:fr:history",
                            reason="null = hour without a tier-1 (observed) value"
                            if any(t != 1 for t in hist["tier"].to_list()) else None),
            "cutoff_hour_start": iso(cut)},
        "week_errors": errors,
        "selection_mae": sel_mae,
        "limitation": fcmod.LIMITATION,
        "forecast_note": "K/W/L forecasts are issued values; forecast values beyond issued "
                         "coverage are never shown here",
    }


def _action_co2(tt, gpus, duration_s, site, start_us, arrival_us) -> tuple[float, float]:
    d_us = round(duration_s * 1e6)
    val, miss = tt.integral(site, np.array([start_us]), np.array([start_us + d_us]))
    if miss[0]:
        raise AssertionError("illustrative action touches missing truth")
    ex = gpus * KW_PER_GPU * PUE * val[0] / 1000
    tr = 0.0
    if site != HOME:
        t_fac = TRANSFER_FRACTION * gpus * KW_PER_GPU * d_us / 3.6e9 * PUE
        ch, _ = tt.point(HOME, np.array([arrival_us]))
        cd, _ = tt.point(site, np.array([arrival_us]))
        tr = 0.5 * t_fac * (ch[0] + cd[0]) / 1000
    return float(ex), float(tr)


def job_replay(k) -> dict:
    run_id, cj, tt, ledgers, probe = k["run_id"], k["cj"], k["tt"], k["ledgers"], k["probe"]
    bookings = k["bookings"]
    # §11 illustrative job: flexible jobs with a feasible remote action in the primary (U,
    # bookings-held) replay; nearest the median GPU-hours; ties by stable ID.
    cand = cj.filter(pl.col("job_uid").is_in(list(probe.actions))).with_columns(
        (pl.col("gpus") * pl.col("duration_s") / 3600).alias("gpu_h"))
    med = float(cand["gpu_h"].median())
    pick = cand.with_columns((pl.col("gpu_h") - med).abs().alias("dist")).sort(
        "dist", "job_uid").row(0, named=True)
    uid = pick["job_uid"]
    b = bookings.filter(pl.col("job_uid") == uid).row(0, named=True)
    arr_us = _dt_us(pick["arrival_ts"])
    pid = f"{run_id}:job:{uid}"
    actions = []
    acts = dict(probe.actions[uid])
    for site, s in sorted(acts.items(), key=lambda kv: (kv[0] != HOME, kv[0])):
        ex, tr = _action_co2(tt, pick["gpus"], pick["duration_s"], site, s, arr_us)
        d_us = round(pick["duration_s"] * 1e6)
        actions.append({
            "site": site, "kind": "stay" if site == HOME else "travel",
            "start": iso(_us_dt(s)), "end": iso(_us_dt(s + d_us)),
            "wait_s": env((s - arr_us) / 1e6, "s", "simulated", f"{pid}:{site}:wait"),
            "slack_s": env((b["deadline_us"] - s - d_us) / 1e6, "s", "simulated",
                           f"{pid}:{site}:slack"),
            "execution_co2_kg": env(ex, "kg_CO2", "modeled", f"{pid}:{site}:exec_co2"),
            "transfer_co2_kg": env(tr, "kg_CO2", "modeled", f"{pid}:{site}:transfer_co2"),
            "co2_kg": env(ex + tr, "kg_CO2", "modeled", f"{pid}:{site}:co2")})
    placements = {}
    for name, led in ledgers.items():
        r = led.filter(pl.col("job_uid") == uid).row(0, named=True)
        a = job_accounting(led.filter(pl.col("job_uid") == uid),
                           cj.filter(pl.col("job_uid") == uid), tt).row(0, named=True)
        placements[name] = {"site": r["site"], "start": iso(r["start_ts"]),
                            "end": iso(r["end_ts"]), "moved": r["moved"],
                            "co2_kg": env(a["co2_kg"], "kg_CO2", "simulated",
                                          f"{run_id}:{name}:job:{uid}:co2")}
    for name in POLICY_ORDER:
        placements.setdefault(name, {"status": "not_run", "reason": TASK5_REASON})
    best = min(actions, key=lambda a: a["co2_kg"]["value"])
    stay = next((a for a in actions if a["site"] == HOME), None)
    expl = (f"Staying at {HOME} from its earliest feasible start would emit "
            f"{stay['co2_kg']['value']:.3g} kg CO2 (modeled); the lowest-CO2 earliest action "
            f"is {best['site']} at {best['co2_kg']['value']:.3g} kg including transfer."
            if stay else f"The lowest-CO2 earliest action is {best['site']}.")
    illustrative = {
        "rule": "§11: among validation flexible jobs with a feasible remote action in the "
                "primary (U, bookings-held) replay, the job nearest the median GPU-hours of "
                "that set; ties by stable ID",
        "set_size": env(cand.height, "jobs", "simulated", f"{run_id}:illustrative:set"),
        "set_median_gpu_h": env(med, "GPU_h", "measured", f"{run_id}:illustrative:median"),
        "job_uid": uid, "source_id": pick["source_id"], "job_type": pick["job_type"],
        "arrival": iso(pick["arrival_ts"]),
        "gpus": env(pick["gpus"], "GPUs", "measured", f"{pid}:gpus"),
        "declared_duration_s": env(pick["duration_s"], "s", "measured", f"{pid}:duration"),
        "realized_duration_s": env(pick["duration_s"], "s", "assumed", f"{pid}:realized",
                                   ) | {"reason": "exact declared runtimes: realized = "
                                                  "declared (runtime uncertainty untested)"},
        "declared_gpu_h": env(pick["gpu_h"], "GPU_h", "measured", f"{pid}:gpu_h"),
        "flexible": pick["flexible"], "mobile": pick["mobile"],
        "flags_evidence": "assumed",
        "max_delay_s": env(pick["max_delay_s"], "s", "assumed", f"{pid}:max_delay"),
        "deadline": iso(_us_dt(b["deadline_us"])),
        "booking": {"site": b["site"], "start": iso(_us_dt(b["start_us"])),
                    "end": iso(_us_dt(b["end_us"])), "evidence": "simulated"},
        "available_actions": actions,
        "actions_note": "earliest on-time feasible start at each legal site, in the capacity "
                        "left by every other booking (the U replay state); CO2 priced on the "
                        "filled scoring truth",
        "placements": placements,
        "explanation": expl,
    }
    # One week of placements, with arcs (the forecast-replay week).
    w0, w1 = _replay_week(k["eval_start"])
    wk = {}
    hours = pl.datetime_range(w0, w1 - H1, "1h", time_unit="us", time_zone="UTC", eager=True)
    h_us = hours.dt.epoch("us").to_numpy()
    for name, led in ledgers.items():
        lw = led.filter((pl.col("arrival_ts") >= w0) & (pl.col("arrival_ts") < w1))
        arcs = []
        for site in sorted(s for s in SITES if s != HOME):
            r = lw.filter(pl.col("site") == site)
            arcs.append({"from": HOME, "to": site,
                         "jobs": env(r.height, "jobs", "simulated", f"{run_id}:{name}:arc:{site}"),
                         "gpu_h": env(float((r["gpus"] * r["duration_s"]).sum() / 3600),
                                      "GPU_h", "simulated", f"{run_id}:{name}:arcgh:{site}")})
        busy = {}
        s_us = led["start_ts"].dt.epoch("us").to_numpy()
        e_us = led["end_ts"].dt.epoch("us").to_numpy()
        g = led["gpus"].to_numpy()
        sites_arr = led["site"].to_numpy()
        for site in SITES:
            m = sites_arr == site
            ss, ee, gg = s_us[m], e_us[m], g[m]
            occ = []
            for h in h_us:
                ov = np.clip(np.minimum(ee, h + 3_600_000_000) - np.maximum(ss, h), 0, None)
                occ.append(float((ov * gg).sum() / 3_600_000_000))
            busy[site] = env(occ, "GPU_h_per_h", "simulated", f"{run_id}:{name}:busy:{site}")
        wk[name] = {"n_arrivals": env(lw.height, "jobs", "simulated", f"{run_id}:{name}:wk_n"),
                    "arcs": arcs, "mean_busy_gpus_by_hour": busy}
    return {
        "schema_version": SCHEMA_VERSION, "run_id": run_id,
        "illustrative_job": illustrative,
        "week": {"start": iso(w0), "end": iso(w1), "hours": [iso(h) for h in hours.to_list()],
                 "note": "cohort jobs only (warm-up occupancy excluded from the busy series)",
                 "policies": wk,
                 "not_run": {n: TASK5_REASON for n in POLICY_ORDER if n not in ledgers}},
    }


# --------------------------------------------------------------------------- table


def print_table(acct, timer) -> None:
    s = acct["scores"]
    print("\nValidation results (phase 0; simulated outcomes; bound modeled). "
          "Not test results.")
    hdr = (f"{'policy':8s} {'status':8s} {'feas':5s} {'late':>4s} {'tCO2':>10s} {'vs U %':>7s} "
           f"{'U-P b4 CI kg':>24s} {'moved%':>7s} {'remote%E':>8s} {'tier>=2%':>8s} "
           f"{'bound':>5s} {'sim s':>7s}")
    print(hdr)
    u = s["U"]["co2_kg"]
    for name in POLICY_ORDER:
        if name not in s:
            print(f"{name:8s} {'not_run':8s}  ({TASK5_REASON})")
            continue
        m = s[name]
        c = acct["contrasts"].get(f"{name}_vs_U", {}).get(4)
        ci = f"[{c['diff_kg_ci'][0]:,.0f}, {c['diff_kg_ci'][1]:,.0f}]" if c else "-"
        ok = all(g["ok"] for g in acct["gaps"][name].values())
        print(f"{name:8s} {'ok':8s} {m['feasible']!s:5s} {m['late_jobs']:4d} "
              f"{m['co2_kg'] / 1000:10.1f} {100 * (u - m['co2_kg']) / u:7.2f} {ci:>24s} "
              f"{100 * (m['moved_share_jobs'] or 0):7.2f} "
              f"{100 * (m['remote_energy_share'] or 0):8.2f} "
              f"{100 * (m['kwh_share_tier_ge2'] or 0):8.3f} {ok!s:>5s} "
              f"{timer.t.get(f'policy_{name}', 0):7.1f}")
    print(f"relaxed bound (modeled): primary {acct['bounds']['primary'] / 1000:.1f} t, "
          f"time-only {acct['bounds']['time_only'] / 1000:.1f} t")
    for name, g in acct["gaps"].items():
        for basis, x in g.items():
            print(f"  bound check {name:7s} {basis:9s} gap {x['gap_kg']:.6f} kg "
                  f"min job gap {x['min_job_gap_kg']:.3e} kg ok={x['ok']}")
    print("timing (s): " + ", ".join(f"{k} {v:.1f}" for k, v in timer.t.items()))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--window", choices=sorted(WINDOWS), default="validation")
    p.add_argument("--forecast-run", default=None,
                   help="reuse a Task 2 run directory instead of building forecasts")
    p.add_argument("--out", default=None, help="run root (default: runs/slice)")
    p.add_argument("--no-export", action="store_true", help="do not copy into results/")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
