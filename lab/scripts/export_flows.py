"""Stage 3 T15 (D-064): write results/scenario-flows.json and results/flexibility-budget.json.

    cd lab && uv run python scripts/export_flows.py --run-dir <runs/slice/<id>> [--ext-root <runs/ext>]

`--run-dir` is the registered run, or a primary reproduction whose ledgers equal the
registered ones (extensions.json `primary_reproduction.ledgers_equal`); every ledger read is
checked against the registered canonical hashes. The scenario runs are the ones
extensions.json names (`runs/ext/<name>/<run_id>`), checked against their recorded summary
and ledger hashes. Savings and intervals are copied from metrics.json / extensions.json; the
ledgers give remote execution, retiming, the replay-week arcs and the budget. No simulation;
validation data only (the run's truth fill and the pre-seal workload replay).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import polars as pl

from gridpilot.cohort import ids_hash, ledger_hash
from gridpilot.data.truth_fill import fill_mask
from gridpilot.eval import TruthTable, job_accounting
from gridpilot.flows import (
    POLICIES,
    budget,
    budget_artifact,
    flows_artifact,
    policy_flow,
    week_arcs,
)
from gridpilot.paths import REPO_ROOT, RESULTS_DIR
from gridpilot.results import canonical_hash, validate_artifact, write_json_atomic
from gridpilot.scenario import Window
from gridpilot.splits import drop_sealed
from gridpilot.workload import replay

SCENARIOS = (
    ("registered", "All flexible jobs (registered)", None),
    ("mobility_le_8gpus", "Only jobs of 8 GPUs or fewer", "mobility_le_8gpus"),
    ("dest_slots_0", "No remote capacity (wait only)", "dest_slots_0"),
    ("dest_slots_1024", "Double remote capacity", "dest_slots_1024"),
)
BUDGET_POLICIES = ("S", "W", "L")  # S default, W per the brief, L so the UI can follow every arc policy


def _json(p: Path) -> dict:
    return json.loads(p.read_text())


def _check_ledger(led: pl.DataFrame, want: str, what: str) -> pl.DataFrame:
    if ledger_hash(led) != want:
        raise AssertionError(f"{what}: ledger differs from its recorded canonical hash")
    return led


def _registered(run: Path, ext: dict, man: dict) -> tuple[dict, dict]:
    cfg = _json(run / "config.json")
    # the registered run predates config["scenario"]; it is the primary when phase 0 and no scenario
    if cfg["window"] != "validation" or cfg.get("scenario", {"name": "primary"})["name"] != "primary" \
            or cfg["phase_days"] != 0:
        raise AssertionError(f"{run} is not a validation primary run")
    reg_hash = ext["repricing"]["canonical_hashes"]["ledger_canonical_sha256"]
    if run.name != man["run_id"]:
        rep = ext["primary_reproduction"]
        if Path(rep["run_dir"]).name != run.name or not all(rep["ledgers_equal"].values()):
            raise AssertionError(f"{run.name} is neither the registered run {man['run_id']} "
                                 f"nor its recorded equal-ledger reproduction")
    return cfg, reg_hash


def _vs_u_metrics(m: dict, p: str) -> dict:
    c = next(c for c in m["contrasts"] if c["candidate"] == p and c["reference"] == "U")
    return c["blocks"]["4"]


def _kwh(by_site: dict) -> dict[str, float]:
    return {s: e["value"] for s, e in by_site.items()}


def _moved_closes(f: dict, what: str) -> dict:
    """remote + retimed + rigid slips = the scored run's moved share (execution basis, I1)."""
    parts = (f["remote_execution_share"]["value"] + f["retimed_home_execution_share"]["value"]
             + f["rigid_slip_execution_share"]["value"])
    for got in (f["moved_execution_share"]["value"], f["moved_share_energy"]["value"]):
        if not math.isclose(parts, got, rel_tol=1e-9, abs_tol=1e-12):
            raise AssertionError(f"{what}: remote + retimed + slips {parts} != moved {got}")
    return f


def build(run: Path, ext_root: Path) -> tuple[dict, dict]:
    m = _json(RESULTS_DIR / "metrics.json")
    ext = _json(RESULTS_DIR / "extensions.json")
    man = _json(RESULTS_DIR / "manifest.json")
    jr = _json(RESULTS_DIR / "job-replay.json")
    cfg, reg_hash = _registered(run, ext, man)
    w0 = datetime.fromisoformat(jr["week"]["start"])
    w1 = datetime.fromisoformat(jr["week"]["end"])
    rid = man["run_id"]

    window = Window.named(cfg["window"])
    A = datetime.fromisoformat(cfg["A"])
    jobs = replay(window.init, window.F, phase_days=0)
    cj = jobs.filter((pl.col("arrival_ts") >= window.eval_start) & (pl.col("arrival_ts") < A))
    if ids_hash(cj["job_uid"].to_list()) != _json(run / "cohort.json")["cohort_ids_sha256"]:
        raise AssertionError("rebuilt cohort differs from the registered cohort ids")
    flex = cj.select("job_uid", "flexible")
    led = {p: _check_ledger(pl.read_parquet(run / f"ledger_{p}.parquet"), reg_hash[p],
                            f"{run.name}:{p}") for p in ("U", *POLICIES)}
    scen = []
    for sid, label, name in SCENARIOS:
        pols = {}
        if name is None:
            for p in POLICIES:
                pm = m["policies"][p]["metrics"]
                pols[p] = _moved_closes(policy_flow(f"{rid}:flows:{p}", _vs_u_metrics(m, p), led[p], w0, w1,
                                      remote_energy_share=pm["remote_energy_share"],
                                      moved_share_energy=pm["moved_share_energy"],
                                      by_site_kwh=_kwh(pm["execution_kwh_by_site"]), flags=flex,
                                      late_jobs=pm["late_jobs"]), f"registered:{p}")
                # the registered arcs must be job-replay.json's, number for number
                want = {a["to"]: (a["jobs"]["value"], a["gpu_h"]["value"])
                        for a in jr["week"]["policies"][p]["arcs"]}
                for a in week_arcs(led[p], w0, w1):
                    j, g = want[a["to"]]
                    if a["jobs"] != j or not math.isclose(a["gpu_h"], g, rel_tol=1e-12):
                        raise AssertionError(f"{p} arc {a['to']} differs from job-replay.json")
            scen.append({"id": sid, "label": label, "registered": True,
                         "label_kind": "registered result", "run_id": rid,
                         "ledger_run_dir": f"runs/slice/{run.name}",
                         "note": "registered primary scenario", "knobs": {},
                         "policies": pols})
            continue
        b = ext["sensitivities"][name]
        if b["status"] != "ok":
            raise AssertionError(f"{name} did not run ({b.get('reason')})")
        rd = ext_root / name / b["run_id"]
        summ = _json(rd / "summary.json")
        if canonical_hash(summ) != b["canonical_hashes"]["summary_canonical_sha256"]:
            raise AssertionError(f"{rd}: summary.json differs from extensions.json's record")
        hashes = b["canonical_hashes"]["ledger_canonical_sha256"]
        for p in POLICIES:
            lp = _check_ledger(pl.read_parquet(rd / f"ledger_{p}.parquet"), hashes[p],
                               f"{name}:{p}")
            bp = b["policies"][p]
            pols[p] = _moved_closes(policy_flow(f"{b['run_id']}:{name}:flows:{p}", bp["vs_U"]["4"], lp, w0, w1,
                                  remote_energy_share=bp["remote_energy_share"],
                                  moved_share_energy=bp["moved_share_energy"],
                                  by_site_kwh=_kwh(summ["policies"][p]["metrics"]
                                                   ["execution_kwh_by_site"]), flags=flex,
                                  late_jobs=bp["late_jobs"]), f"{name}:{p}")
        scen.append({"id": sid, "label": label, "registered": False,
                     "label_kind": "scenario estimate (validation)", "run_id": b["run_id"],
                     "ledger_run_dir": b["run_dir"], "note": b["scenario"]["note"],
                     "knobs": b["scenario"]["knobs"], "policies": pols})
    flows = flows_artifact(scenarios=scen, week=(w0, w1), registered_run_id=rid)

    # ---- flexibility budget (registered primary, S default, plus W)
    tf = drop_sealed(pl.read_parquet(run / "truth_fill.parquet"))  # F8: pre-seal truth only
    tt = TruthTable(tf, fill_mask(tf))
    jcols = cj.select("job_uid", "source_id", "arrival_ts", "gpus", "duration_s")
    acct_u = job_accounting(led["U"], jcols, tt)
    flags = cj.select("job_uid", "flexible", "mobile")
    dest_slots = min(v for k, v in cfg["sites"].items() if k != "PACE")
    out = {}
    for p in BUDGET_POLICIES:
        if p not in led:
            led[p] = _check_ledger(pl.read_parquet(run / f"ledger_{p}.parquet"), reg_hash[p], p)
        acct = job_accounting(led[p], jcols, tt)
        bud = budget(acct_u, acct, flags, dest_slots=dest_slots,
                     diagnosed=p in cfg["diagnosed_policies"])
        pm, um = m["policies"][p]["metrics"], m["policies"]["U"]["metrics"]
        want = um["co2_kg"]["value"] - pm["co2_kg"]["value"]
        if not math.isclose(bud["saving_kg"], want, rel_tol=1e-9):
            raise AssertionError(f"{p}: budget saving {bud['saving_kg']} != metrics {want}")
        if not math.isclose(bud["total_mwh"] * 1000, pm["execution_kwh"]["value"], rel_tol=1e-9):
            raise AssertionError(f"{p}: budget energy differs from metrics execution_kwh")
        cb = next(k for k in bud["buckets"] if k["id"] == "capacity_blocked")
        if bud["diagnosed"] and not math.isclose(
                (cb["mwh"] + bud["blocked_must_stay_mwh"]) * 1000, bud["blocked_total_mwh"] * 1000,
                rel_tol=1e-9, abs_tol=1e-6):
            raise AssertionError(f"{p}: capacity_blocked + blocked-but-must-stay != blocked")
        if bud["diagnosed"] and not math.isclose(bud["blocked_total_mwh"] * 1000,
                                                 pm["blocked_kwh"]["value"], rel_tol=1e-9,
                                                 abs_tol=1e-6):
            raise AssertionError(f"{p}: blocked energy differs from metrics blocked_kwh")
        out[p] = bud
    bud_art = budget_artifact(out, run_id=rid, registered_run_id=rid, default="S")
    bud_art["ledger_run_dir"] = f"runs/slice/{run.name}"
    for a in (flows, bud_art):
        bad = validate_artifact(a)
        if bad:
            raise AssertionError(f"{a['kind']}: {bad[:5]}")
    return flows, bud_art


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", required=True, type=Path)
    ap.add_argument("--ext-root", type=Path, default=None,
                    help="default: the runs/ext next to the run's runs/slice")
    a = ap.parse_args(argv)
    run = a.run_dir.resolve()
    if a.ext_root is not None and not a.ext_root.is_dir():
        raise SystemExit(f"--ext-root {a.ext_root} does not exist")  # fix r1 M14: never fall back
    ext_root = a.ext_root or run.parent.parent / "ext"
    if not ext_root.is_dir():
        ext_root = REPO_ROOT / "runs" / "ext"
    flows, bud = build(run, ext_root)
    write_json_atomic(RESULTS_DIR / "scenario-flows.json", flows)
    write_json_atomic(RESULTS_DIR / "flexibility-budget.json", bud)
    s = bud["policies"]["S"]
    print(f"wrote results/scenario-flows.json ({len(flows['scenarios'])} scenarios) and "
          f"results/flexibility-budget.json: S moved-remote "
          f"{s['buckets'][0]['share']['value']:.1%} of energy, must-stay "
          f"{s['must_stay_share']['value']:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
