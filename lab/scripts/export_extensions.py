"""Stage 3 T10: `results/extensions.json`, the D-058 extensions (validation only).

    cd lab && uv run python scripts/export_extensions.py --registered-run <runs/slice/<id>>
        [--ext-root <runs/ext>] [--repro-run <runs/slice/<id>>]

1. Production-basis repricing: the registered ledgers, unchanged, priced on EIA
   production-basis CI (the F14.6 tiers with production as tier 1) next to the registered
   consumption basis; every policy against U.
2. Common support (F14.6): every policy keeps only the jobs whose charged hours touch
   tier-1 truth only under every policy; savings and intervals on that cohort.
3. Phases 49 and 98 and the one-axis sensitivities: read from each extension's latest
   complete run directory `runs/ext/<name>/<UTC>/summary.json` (made by run_slice.py
   --scenario <name>). A scenario with no complete run is exported as not_run.
4. The cut items (D-058) as not_run with their reason; `manifest.not_run` is updated.

Every number is an evidence envelope: repricing, common support and policy outcomes are
`simulated`; scenario knobs are `assumed`. Nothing here reads the sealed window.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from gridpilot.cohort import ids_hash, ledger_hash
from gridpilot.data.truth_fill import (
    TIER_SOURCE,
    TIER_SOURCE_PRODUCTION,
    fill_mask,
    fill_truth,
    missing_hours,
    tier_counts,
)
from gridpilot.eval import TruthTable
from gridpilot.extensions import common_support_cohort, reprice
from gridpilot.paths import REPO_ROOT, RESULTS_DIR
from gridpilot.results import (
    LIMIT_PHASES,
    SCHEMA_VERSION,
    canonical_hash,
    env,
    write_json_atomic,
)
from gridpilot.scenario import EXTENSIONS, Scenario, Window
from gridpilot.sim import SITES
from gridpilot.workload import replay

log = logging.getLogger("export_extensions")
SCRIPT_DIR = Path(__file__).resolve().parent
HARD_STOP_REASON = "hard stop 21:00 (F9)"
CUT_REASON = "cut by owner (D-058)"
PHASES = ("phase_49", "phase_98")
SENSITIVITIES = tuple(n for n in EXTENSIONS if n not in PHASES)
# D-058 cuts: shadow-U, missingness-blind, and the remaining §7 sensitivities.
CUT_ITEMS = {
    "shadow_U": "shadow-U (no advance booking) sensitivity (F12.7)",
    "missingness_blind": "missingness-blind scheduling sensitivity (F12.1, F13.6)",
    "batch_delay_0h": "batch delay 0 h (§7)",
    "transfer_0min": "remote transfer time 0 min (§7)",
    "transfer_energy_0pct_20pct": "remote transfer energy 0% and 20% (§7)",
    "active_power_0.40_0.80kw": "active IT power 0.40 and 0.80 kW per GPU slot (§7)",
    "remote_pue_1.10_1.56": "remote PUE 1.10 and 1.56 with home fixed (§7)",
    "idle_power_0_0.30kw": "idle IT power 0 and 0.30 kW per slot (§7)",
    "no_flexible_jobs": "no flexible jobs (§7 flexibility share)",
    "all_candidates_flexible": "all candidates flexible (§7 flexibility share)",
    "home_capacity_1.25x": "1.25x home capacity runs (§7)",
}
LIMIT_PHASES_RUN = ("Workload phase 0 is the registered result; phases 49 and 98 are "
                    "workload-alignment sensitivities (results/extensions.json), never pooled "
                    "with it (§9).")
EXT_NOTE = ("Validation results. Sensitivities are exploratory (§9): one-axis endpoints around "
            "the primary scenario, never pooled with it and never a new headline.")


def _load_run_slice():
    spec = importlib.util.spec_from_file_location("run_slice", SCRIPT_DIR / "run_slice.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rs = _load_run_slice()


def _git(*a: str) -> str:
    return subprocess.run(["git", *a], cwd=REPO_ROOT, capture_output=True, text=True,
                          check=False).stdout.strip()


def _parse(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _rel(p: Path) -> str:
    """A run path as the repo-relative `runs/...` form (worktrees share the main runs/)."""
    parts = p.resolve().parts
    return "/".join(parts[parts.index("runs"):]) if "runs" in parts else str(p)


# --------------------------------------------------------------------------- registered run


def load_registered(run: Path) -> dict:
    """The registered run's cohort, bookings and ledgers, each checked against its hashes."""
    cfg = json.loads((run / "config.json").read_text())
    coh = json.loads((run / "cohort.json").read_text())
    window = Window.named(cfg["window"])
    if cfg["phase_days"] != 0:
        raise AssertionError("the registered run is phase 0")
    A = _parse(cfg["A"])
    jobs = replay(window.init, window.F, phase_days=0)
    cj = jobs.filter((pl.col("arrival_ts") >= window.eval_start) & (pl.col("arrival_ts") < A))
    if ids_hash(cj["job_uid"].to_list()) != coh["cohort_ids_sha256"]:
        raise AssertionError("rebuilt cohort differs from the registered cohort ids")
    want = cfg["reproducibility"]["ledger_canonical_sha256"]
    ledgers = {}
    for p in cfg["policies"]:
        led = pl.read_parquet(run / f"ledger_{p}.parquet")
        if ledger_hash(led) != want[p]:
            raise AssertionError(f"ledger {p} differs from its registered canonical hash")
        ledgers[p] = led
    filled = fill_truth(window.init, window.F, list(SITES))
    stored = pl.read_parquet(run / "truth_fill.parquet")
    if not filled.equals(stored):
        raise AssertionError("the consumption truth fill differs from the registered one")
    return {"cfg": cfg, "window": window, "A": A, "cj": cj, "ledgers": ledgers,
            "filled": filled, "run_id": cfg["run_id"], "ledger_sha": want}


# --------------------------------------------------------------------------- records


def _vs_u(by_b, pid, n_weeks, window) -> dict:
    """The b = 2, 4, 8 savings vs U (b = 4 primary), as in metrics.json."""
    return rs._contrast_record("P", "U", by_b, pid, n_weeks, window)["blocks"]


def _hashes(run_id, ledger_sha, **extra) -> dict:
    return {"run_id": run_id, "ledger_canonical_sha256": ledger_sha,
            "ledger_hash_rule": "sha256 over job_uid-sorted lines 'job_uid,site,start_us,end_us'",
            **extra}


def repricing_block(reg: dict, rp: dict, prod_fill: pl.DataFrame, metrics: dict) -> dict:
    rid, window = reg["run_id"], reg["window"].name
    pid = f"{rid}:ext:reprice"
    by_policy = {}
    for p in reg["ledgers"]:
        rec = {}
        for basis, r in rp.items():
            b = {"co2_kg": env(r["totals"][p], "kg_CO2", "simulated", f"{pid}:{basis}:{p}:co2"),
                 "tier_ge2_kwh_share": env(
                     r["tier_ge2_kwh_share"][p], "fraction", "simulated",
                     f"{pid}:{basis}:{p}:tier_ge2",
                     *(("unavailable", "zero energy") if r["tier_ge2_kwh_share"][p] is None
                       else ()))}
            if p != "U":
                b["vs_U"] = _vs_u(r["contrasts"][p], f"{pid}:{basis}:{p}", r["n_weeks"], window)
            rec[basis] = b
        by_policy[p] = rec
    # The consumption basis is recomputed here; it must equal the registered metrics.
    reg_co2 = {p: metrics["policies"][p]["metrics"]["co2_kg"]["value"] for p in reg["ledgers"]}
    same = all(f"{rp['consumption']['totals'][p]:.10g}" == f"{reg_co2[p]:.10g}"
               for p in reg_co2)
    if not same:
        raise AssertionError("consumption-basis repricing does not reproduce metrics.json")
    return {
        "status": "ok",
        "definition": ("the registered ledgers, unchanged (no re-simulation), priced on EIA "
                       "production-basis CO2 intensity, next to the registered consumption "
                       "basis; saving = (U - policy) / U, ratio of totals"),
        "scenario": rs.scenario_record(Scenario.primary(), f"{pid}:scenario"),
        "canonical_hashes": _hashes(rid, reg["ledger_sha"]),
        "consumption_reproduces_metrics_json": same,
        "bases": {
            "consumption": {"tiers": {str(k): v for k, v in TIER_SOURCE.items()},
                            "evidence": "modeled"},
            "production": {
                "tiers": {str(k): v for k, v in TIER_SOURCE_PRODUCTION.items()},
                "evidence": "modeled",
                "hours_by_ba": {ba: {t: env(n, "hours", "measured", f"{pid}:prod_tier:{ba}:{t}")
                                     for t, n in row.items()}
                                for ba, row in tier_counts(prod_fill).items()},
                "missing_after_tier4": missing_hours(prod_fill)},
        },
        "note": ("Production basis is where electricity is generated, not where it is "
                 "delivered: hydro-heavy BPAT's low production intensity is not the "
                 "intensity of the power its loads consume (§10 check 6)."),
        "n_weeks": env(rp["consumption"]["n_weeks"], "weeks", "measured", f"{pid}:n_weeks"),
        "by_policy": by_policy,
    }


def common_support_block(reg: dict, cs: dict, full: dict) -> dict:
    rid, window = reg["run_id"], reg["window"].name
    pid = f"{rid}:ext:common_support"
    c = cs["contrasts"]
    by_policy = {}
    for p in reg["ledgers"]:
        rec = {"co2_kg": env(c["totals"][p], "kg_CO2", "simulated", f"{pid}:{p}:co2"),
               "energy_share_in_cohort": env(cs["energy_share"][p], "fraction", "simulated",
                                             f"{pid}:{p}:energy_share")}
        if p != "U":
            rec["vs_U"] = _vs_u(c["contrasts"][p], f"{pid}:{p}", c["n_weeks"], window)
            rec["full_cohort_vs_U"] = _vs_u(full["contrasts"][p], f"{pid}:full:{p}",
                                            full["n_weeks"], window)
        by_policy[p] = rec
    return {
        "status": "ok",
        "definition": ("F14.6 common support: every policy drops each job whose charged hours "
                       "(execution, and a remote run's arrival-hour transfer charges at both "
                       "ends) touch fill tier >= 2 under any policy; savings and intervals "
                       "are recomputed on the jobs left (consumption basis)"),
        "scenario": rs.scenario_record(Scenario.primary(), f"{pid}:scenario"),
        "canonical_hashes": _hashes(rid, reg["ledger_sha"],
                                    dropped_ids_sha256=ids_hash(cs["dropped"])),
        "cohort": {
            "n_jobs": env(cs["n_jobs"], "jobs", "simulated", f"{pid}:n"),
            "n_full_cohort": env(cs["n_cohort"], "jobs", "simulated", f"{pid}:n_full"),
            "n_dropped": env(len(cs["dropped"]), "jobs", "simulated", f"{pid}:n_dropped"),
            "share_jobs": env(cs["share_jobs"], "fraction", "simulated", f"{pid}:share_jobs"),
            "energy_share_U": env(cs["energy_share"]["U"], "fraction", "simulated",
                                  f"{pid}:energy_share_U"),
        },
        "n_weeks": env(c["n_weeks"], "weeks", "measured", f"{pid}:n_weeks"),
        "by_policy": by_policy,
    }


def latest_run(root: Path) -> Path | None:
    """The newest complete run directory (has summary.json) under `root`."""
    if not root.is_dir():
        return None
    runs = sorted(p for p in root.iterdir()
                  if p.is_dir() and not p.name.startswith((".", "failed-"))
                  and (p / "summary.json").exists())
    return runs[-1] if runs else None


def run_block(name: str, run: Path, window: str = "validation") -> dict:
    s = json.loads((run / "summary.json").read_text())
    cfg = json.loads((run / "config.json").read_text())
    if s["window"] != window:
        raise AssertionError(f"{run}: a {s['window']} run, not {window}")
    if s["scenario"]["name"] != name:
        raise AssertionError(f"{run}: summary is for {s['scenario']['name']}, not {name}")
    if canonical_hash(s) != cfg["summary_canonical_sha256"]:
        raise AssertionError(f"{run}: summary.json does not match its canonical hash")
    vs_u = {c["candidate"]: c["blocks"] for c in s["contrasts"] if c["reference"] == "U"}
    pols = {}
    for p, rec in s["policies"].items():
        m = rec["metrics"]
        out = {"co2_kg": m["co2_kg"], "late_jobs": m["late_jobs"], "feasible": rec["feasible"],
               "bound_ok": all(b["ok"] for b in rec["bound_check"].values()),
               "moved_share_jobs": m["moved_share_jobs"],
               "moved_share_energy": m["moved_share_energy"],
               "remote_energy_share": m["remote_energy_share"],
               "wait_p95_s": m["wait_p95_s"]}
        if p in vs_u:
            out["vs_U"] = vs_u[p]
        pols[p] = out
    late = sum(r["late_jobs"]["value"] for r in pols.values())
    return {
        "status": "ok",
        "scenario": s["scenario"],
        "run_id": s["run_id"],
        "run_dir": _rel(run),
        "git_sha": s["git_sha"],
        "git_clean": s["git_clean"],
        "canonical_hashes": {
            "ledger_canonical_sha256": s["reproducibility"]["ledger_canonical_sha256"],
            "summary_canonical_sha256": cfg["summary_canonical_sha256"]},
        "covered": s["covered"],
        "cohort": s["cohort"],
        "all_on_time": late == 0,
        "all_feasible": all(r["feasible"] for r in pols.values()),
        "policies": pols,
    }


def not_run_block(item: str, reason: str, scenario: Scenario | None = None) -> dict:
    out = {"item": item, "status": "not_run", "reason": reason}
    if scenario is not None:
        out["scenario"] = rs.scenario_record(scenario, f"not_run:{scenario.name}")
    return out


def reproduction_block(repro: Path, reg: dict, metrics: dict) -> dict:
    cfg = json.loads((repro / "config.json").read_text())
    new = json.loads((repro / "results" / "metrics.json").read_text())
    got = cfg["reproducibility"]["ledger_canonical_sha256"]
    return {"run_id": cfg["run_id"], "run_dir": _rel(repro), "git_sha": cfg["git_sha"],
            "git_clean": cfg["git_clean"],
            "ledgers_equal": {p: got.get(p) == h for p, h in reg["ledger_sha"].items()},
            "metrics_canonical_sha256": {"registered": canonical_hash(metrics),
                                         "reproduction": canonical_hash(new)},
            "metrics_canonical_equal": canonical_hash(metrics) == canonical_hash(new),
            "rule": "canonical_hash: floats to 10 significant digits, provenance/run ids "
                    "dropped, keys sorted (T10)"}


# --------------------------------------------------------------------------- build


def build(reg_run: Path, ext_root: Path, repro: Path | None, missing_reason: str) -> dict:
    reg = load_registered(reg_run)
    metrics = json.loads((RESULTS_DIR / "metrics.json").read_text())
    if metrics["run_id"] != reg["run_id"]:
        raise AssertionError(f"results/metrics.json is run {metrics['run_id']}, not the "
                             f"registered run {reg['run_id']}")
    w, A, cj, leds = reg["window"], reg["A"], reg["cj"], reg["ledgers"]
    window = (w.eval_start, A)
    prod_fill = fill_truth(w.init, w.F, list(SITES), basis="production")
    tt_c = TruthTable(reg["filled"], fill_mask(reg["filled"]))
    tt_p = TruthTable(prod_fill, fill_mask(prod_fill))
    log.info("repricing %d ledgers on two bases", len(leds))
    rp = reprice(leds, cj, {"consumption": tt_c, "production": tt_p}, window)
    log.info("common support")
    cs = common_support_cohort(leds, cj, tt_c, window)
    want = metrics["common_support"]["n_dropped_jobs"]["value"]
    if len(cs["dropped"]) != want:
        raise AssertionError(f"common support drops {len(cs['dropped'])} jobs, the registered "
                             f"run {want}")
    blocks, missing = {}, []
    for name in EXTENSIONS:
        run = latest_run(ext_root / name)
        if run is None:
            blocks[name] = not_run_block(EXTENSIONS[name].note, missing_reason, EXTENSIONS[name])
            missing.append(name)
        else:
            blocks[name] = run_block(name, run, w.name)
    out = {
        "schema_version": SCHEMA_VERSION,
        "kind": "validation extensions (D-058): robustness and sensitivity evidence",
        "evidence_scope": "validation (selection) results; the sealed test window "
                          "[2025-11-01, 2026-11-01) is never read",
        "note": EXT_NOTE,
        "registered_run_id": reg["run_id"],
        "export_git_sha": _git("rev-parse", "HEAD"),
        "wallclock_generated_at": datetime.now(UTC).isoformat(),
        "reproduce": ("cd lab && uv run python scripts/run_slice.py --scenario <name> "
                      "--forecast-run <registered forecast run>; then "
                      "uv run python scripts/export_extensions.py --registered-run <run>"),
        "repricing": repricing_block(reg, rp, prod_fill, metrics),
        "common_support": common_support_block(reg, cs, rp["consumption"]),
        "phases": {n: blocks[n] for n in PHASES},
        "sensitivities": {n: blocks[n] for n in SENSITIVITIES},
        "not_run": {k: not_run_block(v, CUT_REASON) for k, v in CUT_ITEMS.items()},
        "missing_runs": missing,
    }
    if repro is not None:
        out["primary_reproduction"] = reproduction_block(repro, reg, metrics)
    return out


def manifest_not_run(missing: list[str]) -> list[dict]:
    return rs.NOT_RUN + [{"item": f"{n} ({EXTENSIONS[n].note})", "reason": HARD_STOP_REASON}
                         for n in missing]


def patch_manifest(path: Path, ext: dict, text: str) -> None:
    """`manifest.not_run` and the phase limitation follow the extensions actually run; the
    manifest records extensions.json's hashes. No other field changes."""
    import hashlib

    man = json.loads(path.read_text())
    man["not_run"] = manifest_not_run(ext["missing_runs"])
    phases_ok = all(ext["phases"][p]["status"] == "ok" for p in PHASES)
    lim = [x for x in man["limitations"] if x not in (LIMIT_PHASES, LIMIT_PHASES_RUN)]
    lim.append(LIMIT_PHASES_RUN if phases_ok else LIMIT_PHASES)
    man["limitations"] = lim
    man["extensions"] = {"artifact": "extensions.json",
                         "sha256": hashlib.sha256(text.encode()).hexdigest(),
                         "canonical_sha256": canonical_hash(ext),
                         "missing_runs": ext["missing_runs"]}
    write_json_atomic(path, man)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--registered-run", required=True, type=Path)
    p.add_argument("--ext-root", type=Path, default=REPO_ROOT / "runs" / "ext")
    p.add_argument("--repro-run", type=Path, default=None)
    p.add_argument("--missing-reason", default=HARD_STOP_REASON)
    p.add_argument("--out", type=Path, default=RESULTS_DIR / "extensions.json")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    ext = build(args.registered_run, args.ext_root, args.repro_run, args.missing_reason)
    text = write_json_atomic(args.out, ext)
    patch_manifest(args.out.parent / "manifest.json", ext, text)
    print(f"wrote {args.out}; missing runs: {ext['missing_runs'] or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
