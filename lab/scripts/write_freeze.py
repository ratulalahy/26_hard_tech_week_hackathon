"""Stage 3 T12 step 5: write the configuration freeze record `config/freeze.json`.

    cd lab && uv run python scripts/write_freeze.py [--dry-run] [--registered-run <abs dir>]

It computes every field from the **current HEAD** and the data dir (`$GRIDPILOT_DATA_DIR`),
sets `freeze_commit` to HEAD's sha, validates the record with `gridpilot.seal` (the JSON schema,
the cross-field rules and the authorize checks that can run before the record is committed),
writes it atomically and prints the lead's commit, tag and push commands. `--dry-run` prints
the record instead of writing it.

It refuses (exit 2, with the reason) when:
- the tree is dirty, a freeze record already exists, or the `config-freeze` tag exists;
- the sealed window shows any prior opening (`seal.prior_openings`);
- the committed rebuild evidence (docs/evidence/rebuild-20261027.json) is not a match, or its
  clone's `lab/` git tree hash differs from HEAD's (`git rev-parse HEAD:lab`; trees survive a
  squash merge, commit ancestry would not);
- an input hash differs from what the rebuild or the completeness log saw;
- the registered forecast run's metrics.json differs from the one the rebuild evidence pins.

Fields (spec §5, §8; T12 step 4):
- `deployed_policy`: the §8 rule on the committed validation `results/metrics.json`: feasible,
  then the lowest aggregate attributed CO₂, then the lower mean wait, then U, G, S, K, W, L;
  every step's values are in the trace;
- `L_max_leaf_nodes`: per series, from the registered forecast run's metrics.json;
- `test_F`, `test_F_basis`: from the committed completeness log (counts and timestamps only);
- `s_ranking`: `eia_co2.s_ranking_at(2023-01-01, 2025-10-29)` on the validation carbon table
  (rows published by fit_at, 96 h envelope), ordered by (mean, BA);
- `scenario_catalog`: the primary scenario only (no extensions on test);
- `snapshot_id`: the committed data/manifests/snapshot.json;
- `input_sha256`: every `seal.TEST_INPUTS` file in the data dir;
- `validation_run`: `seal.validation_reference(repo)` at HEAD.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from gridpilot import paths, seal
from gridpilot.completeness import read_log
from gridpilot.data import eia_co2
from gridpilot.scenario import Scenario

REBUILD_EVIDENCE_REL = "docs/evidence/rebuild-20261027.json"
COMPLETENESS_LOG_REL = "docs/evidence/completeness-20261027.jsonl"
EXPECTED_SNAPSHOT = "8a1b36b24b91"  # D-060 (T11: openmeteo final)
CO2_TIE_KG = 1e-6  # two policies' aggregate CO2 within this are tied (= eval.BOUND_TOL_KG)
WAIT_TIE_S = 1e-9


class Refusal(Exception):
    """write_freeze refuses, with the reason."""


def _git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                       check=False, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if r.returncode:
        raise Refusal(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


def _sha256(p: Path) -> str:
    return seal.file_sha256(p)


def _v(rec: dict, key: str):
    return rec["metrics"][key]["value"]


# --------------------------------------------------------------------------- the §8 rule


def deploy_rule(metrics: dict) -> tuple[str, list[dict]]:
    """The spec §8 deployment rule on a validation metrics.json: the policy and its trace."""
    pols = metrics["policies"]
    missing = [p for p in seal.SELECTION_POLICIES if p not in pols]
    if missing:
        raise Refusal(f"results/metrics.json lacks the candidate policies {missing}")
    run_id = metrics.get("run_id")
    feas = {}
    for p in seal.SELECTION_POLICIES:
        r = pols[p]
        checks = {
            "status_ok": r.get("status") == "ok",
            "feasible": r.get("feasible") is True,
            "conserved": r.get("conserved") is True,
            "late_jobs": _v(r, "late_jobs"),
            "capacity_violations": _v(r, "capacity_violations"),
            "completed_eq_requested_gpu_s": _v(r, "completed_gpu_s") == _v(r, "requested_gpu_s"),
            "bound_check_ok": all(b.get("ok") is True for b in r.get("bound_check", {}).values())
            and bool(r.get("bound_check")),
        }
        checks["passes"] = (checks["status_ok"] and checks["feasible"] and checks["conserved"]
                            and checks["late_jobs"] == 0 and checks["capacity_violations"] == 0
                            and checks["completed_eq_requested_gpu_s"]
                            and checks["bound_check_ok"])
        feas[p] = checks
    ok = [p for p in seal.SELECTION_POLICIES if feas[p]["passes"]]
    trace = [{
        "rule": (f"0. candidates: U, G, S, K, W, L (spec §8) from the committed validation "
                 f"results/metrics.json, run {run_id}; H (hindsight) and the time-only W, L are "
                 f"not candidates"),
        "result": "U, G, S, K, W, L"}, {
        "rule": ("1. hard feasibility: status ok, feasible, work conserved, zero late jobs, zero "
                 "capacity violations, completed GPU-s = requested GPU-s, relaxed-bound check ok"),
        "result": (", ".join(ok) + " pass") if ok else "none passes",
        "values": feas}]
    if not ok:
        raise Refusal("no candidate policy is feasible on validation: the §8 rule selects none")
    co2 = {p: _v(pols[p], "co2_kg") for p in ok}
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in co2.values()):
        raise Refusal(f"non-finite aggregate CO2 among the feasible policies: {co2}")
    lo = min(co2.values())
    tied = [p for p in ok if co2[p] - lo <= CO2_TIE_KG]
    ranked = sorted(ok, key=lambda p: (co2[p], seal.SELECTION_POLICIES.index(p)))
    runner = next((p for p in ranked if p not in tied), None)
    gap = (f"; next {runner} +{co2[runner] - lo:,.2f} kg" if runner else "")
    trace.append({
        "rule": (f"2. lowest aggregate attributed CO2 on validation (co2_kg, kg CO2) among the "
                 f"feasible; policies within {CO2_TIE_KG:g} kg of the minimum are tied"),
        "result": (f"{tied[0]} ({lo:,.2f} kg){gap}" if len(tied) == 1
                   else f"tie: {', '.join(tied)} ({lo:,.2f} kg)"),
        "values": {"co2_kg": co2, "ranked": ranked}})
    wait = {p: _v(pols[p], "wait_mean_s") for p in ok}
    if len(tied) > 1:
        wlo = min(wait[p] for p in tied)
        tied = [p for p in tied if wait[p] - wlo <= WAIT_TIE_S]
        res3 = tied[0] if len(tied) == 1 else f"tie: {', '.join(tied)}"
    else:
        res3 = f"not needed ({tied[0]} is the unique minimum)"
    trace.append({"rule": "3. tie-break: lower mean wait (wait_mean_s, s)", "result": res3,
                  "values": {"wait_mean_s": wait}})
    winner = min(tied, key=seal.SELECTION_POLICIES.index)
    trace.append({"rule": "4. tie-break: the simpler policy, in the order U, G, S, K, W, L",
                  "result": (f"{winner} (from {', '.join(tied)})" if len(tied) > 1
                             else f"not needed ({winner})")})
    trace.append({"rule": "deployed product policy", "result": winner})
    return winner, trace


# --------------------------------------------------------------------------- the record


def l_leaves(forecast_metrics: dict) -> dict[str, int]:
    """L's frozen max_leaf_nodes per series, as JSON integers."""
    series = forecast_metrics.get("series") or {}
    out = {}
    for k in seal.SERIES:
        v = (series.get(k) or {}).get("L_max_leaf_nodes")
        if type(v) is not int or v not in seal.LEAF_NODES:
            raise Refusal(f"forecast metrics: {k} has L_max_leaf_nodes {v!r}, not one of "
                          f"{seal.LEAF_NODES}")
        out[k] = v
    return out


def completeness_basis(raw: bytes, current: dict[str, str]) -> tuple[str, dict]:
    """test_F and test_F_basis from the committed completeness log: every successful line must
    agree on D and F_test, and the last one's input hashes must equal the current files'."""
    recs = read_log(raw)
    ok = [r for r in recs if r.get("event") == "completeness" and r.get("outcome") == "ok"]
    if not ok:
        raise Refusal(f"{COMPLETENESS_LOG_REL} holds no successful completeness line")
    if len({(r["D"], r["test_F"]) for r in ok}) != 1:
        raise Refusal(f"{COMPLETENESS_LOG_REL}: the logged calls disagree on D / F_test: "
                      f"{sorted({(r['D'], r['test_F']) for r in ok})}")
    last = ok[-1]
    diff = {k: (v[:12], str(current.get(k))[:12]) for k, v in last["inputs_sha256"].items()
            if current.get(k) != v}
    if diff:
        raise Refusal(f"the completeness count saw different input files than the data dir "
                      f"holds now: {diff}")
    lines = [ln for ln in raw.decode().splitlines() if ln.strip()]  # = recs, in order
    line_sha = hashlib.sha256(
        lines[next(i for i, r in enumerate(recs) if r is last)].encode()).hexdigest()
    basis = {"D": last["D"], "rule": last["rule"],
             "last_row_ts_utc": {k: v["last_row_ts_utc"] for k, v in last["series"].items()},
             "completeness_log": {"path": COMPLETENESS_LOG_REL, "line_sha256": line_sha}}
    return last["test_F"], basis


def s_ranking(carbon_path: Path) -> dict:
    order, means = eia_co2.s_ranking_at(seal.TEST_HISTORY_START, seal.TEST_FIT_AT,
                                        sites=seal.SITES, path=carbon_path)
    if sorted(order) != sorted(seal.SITES):
        raise Refusal(f"S ranking covers {order}, not every site {seal.SITES}")
    return {"order": order,
            "window": [seal.iso(seal.TEST_HISTORY_START), seal.iso(seal.TEST_FIT_AT)],
            "fit_at": seal.iso(seal.TEST_FIT_AT),
            "mean_consumed_ci_g_kwh": {b: means[b] for b in order},
            "source": (f"eia_co2.s_ranking_at: math.fsum means of EIA's estimated consumption-"
                       f"basis hourly CO2 intensity over [2023-01-01, 2025-10-29), rows "
                       f"published by fit_at (ts_utc + 1 h + 96 h <= fit_at), from "
                       f"processed/carbon/carbon_hourly.parquet sha256 "
                       f"{_sha256(carbon_path)}")}


def build_record(root: Path, data: Path, registered_run: Path | None, *,
                 synthetic: bool = False,
                 expected_snapshot: str = EXPECTED_SNAPSHOT) -> tuple[dict, dict]:
    """(record, context) from HEAD and the data dir; raises Refusal. `synthetic` (tests only)
    requires a data dir with the seal's SYNTHETIC marker; real use refuses one."""
    status = _git(root, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise Refusal(f"the working tree is not clean: {status.splitlines()[:5]}")
    head = _git(root, "rev-parse", "HEAD")
    lab_tree = _git(root, "rev-parse", "HEAD:lab")
    if seal.committed_bytes(root, seal.FREEZE_REL) is not None or (root / seal.FREEZE_REL).exists():
        raise Refusal(f"{seal.FREEZE_REL} already exists: the configuration is already frozen")
    if subprocess.run(["git", "-C", str(root), "rev-parse", "-q", "--verify",
                       f"refs/tags/{seal.FREEZE_TAG}"], capture_output=True,
                      check=False).returncode == 0:
        raise Refusal(f"the tag {seal.FREEZE_TAG!r} already exists")
    if (data / seal.SYNTHETIC_MARKER).exists() != synthetic:
        raise Refusal(f"{data} is a synthetic data dir" if not synthetic else
                      f"synthetic=True needs a data dir with a {seal.SYNTHETIC_MARKER} marker")
    prior = seal.prior_openings(root, data, root / "results")
    if prior:
        raise Refusal(f"the sealed window shows prior openings: {prior}")

    # The independent rebuild (F12.6), at this lab/ tree.
    ev_raw = seal.committed_bytes(root, REBUILD_EVIDENCE_REL)
    if ev_raw is None:
        raise Refusal(f"{REBUILD_EVIDENCE_REL} is not committed at HEAD")
    ev = json.loads(ev_raw)
    if ev.get("match") is not True:
        raise Refusal(f"{REBUILD_EVIDENCE_REL}: the rebuild did not match: no freeze")
    if ev["clone"]["lab_tree"] != lab_tree:
        raise Refusal(f"the rebuild ran at lab/ tree {ev['clone']['lab_tree'][:12]}, but HEAD's "
                      f"lab/ tree is {lab_tree[:12]}: the frozen code was not rebuilt")

    # Validation reference and the deployed policy.
    vref = seal.validation_reference(root)
    if vref != ev["validation_reference"]:
        raise Refusal(f"validation_reference at HEAD {vref} != the rebuild evidence's "
                      f"{ev['validation_reference']}")
    metrics = json.loads(seal.committed_bytes(root, "results/metrics.json"))
    if metrics.get("run_id") != vref["run_id"]:
        raise Refusal("results/metrics.json is not the registered run's")
    policy, trace = deploy_rule(metrics)

    # L configuration, from the registered forecast run (pinned by the rebuild evidence).
    run = registered_run or root / "runs" / "slice" / vref["run_id"]
    fc = run / "forecast" / vref["run_id"]
    if not (fc / "metrics.json").exists():
        raise Refusal(f"no registered forecast run at {fc}: pass --registered-run <abs dir>")
    man = json.loads(seal.committed_bytes(root, "results/manifest.json"))
    want_fc = man["reproducibility"]["forecast_run"]["forecasts_sha256"]
    if _sha256(fc / "forecasts.parquet") != want_fc:
        raise Refusal(f"{fc}/forecasts.parquet is not the registered run's forecasts")
    fm_sha = _sha256(fc / "metrics.json")
    if fm_sha != ev["forecast"]["registered_metrics_sha256"]:
        raise Refusal(f"{fc}/metrics.json ({fm_sha[:12]}) differs from the one the rebuild "
                      f"evidence pins")
    leaves = l_leaves(json.loads((fc / "metrics.json").read_text()))
    if leaves != ev["forecast"]["L_max_leaf_nodes"]["rebuild"]:
        raise Refusal("the registered L configuration differs from the rebuild's")

    # Inputs, the S ranking and the test cutoff.
    inputs = {rel: _sha256(data / rel) for rel in seal.TEST_INPUTS}
    tables = ev["tables"]
    if inputs[seal.BALANCE_REL] != tables["balance.parquet"]["sha256"]["main"]:
        raise Refusal("balance.parquet differs from the table the rebuild compared")
    carbon = data / "processed" / "carbon" / "carbon_hourly.parquet"
    if _sha256(carbon) != tables["carbon_hourly.parquet"]["sha256"]["main"]:
        raise Refusal("carbon_hourly.parquet differs from the table the rebuild compared")
    log_raw = seal.committed_bytes(root, COMPLETENESS_LOG_REL)
    if log_raw is None:
        raise Refusal(f"{COMPLETENESS_LOG_REL} is not committed at HEAD")
    test_F, basis = completeness_basis(log_raw, inputs)

    snap = json.loads(seal.committed_bytes(root, seal.SNAPSHOT_REL))
    if snap.get("snapshot_id") != expected_snapshot:
        raise Refusal(f"committed snapshot {snap.get('snapshot_id')} != {expected_snapshot}")

    record = {
        "schema": seal.SCHEMA_ID,
        "freeze_commit": head,
        "frozen_at": seal.iso(datetime.now(UTC)),
        "deployed_policy": {"name": policy, "rule_trace": trace},
        "L_max_leaf_nodes": leaves,
        "test_F": test_F,
        "test_F_basis": basis,
        "test_fit_at": seal.iso(seal.TEST_FIT_AT),
        "test_history_start": seal.iso(seal.TEST_HISTORY_START),
        "s_ranking": s_ranking(carbon),
        "scenario_catalog": {"primary": json.loads(json.dumps(Scenario.primary().config()))},
        "snapshot_id": snap["snapshot_id"],
        "input_sha256": inputs,
        "validation_run": vref,
    }
    return record, {"head": head, "lab_tree": lab_tree}


def serialize(record: dict) -> bytes:
    return (json.dumps(record, indent=2, ensure_ascii=False) + "\n").encode()


def preflight(root: Path, data: Path, raw: bytes) -> tuple[seal.Freeze, tuple[str, ...]]:
    """The record as `load_freeze` sees it, plus every authorize check that does not need the
    record committed and tagged (B7, I5, scenario, M3, c). Returns the I5 exceptions."""
    fz = seal.parse_freeze(raw, root / seal.FREEZE_REL)
    seal._check_manifests(root, fz)
    exceptions = seal._check_manifest_inputs(root, fz)
    seal._check_scenario(fz)
    seal._check_validation_ref(root, fz)
    seal._check_inputs(fz, data)
    return fz, exceptions


def lead_commands(head: str, file_sha: str) -> str:
    msg = (f"$(cd lab && uv run python -c 'from gridpilot import seal; "
           f"print(seal.freeze_tag_message(\"{file_sha}\"))')")
    return "\n".join([
        "# In the main checkout, on main, HEAD = the freeze commit, nothing else merged:",
        f'test "$(git rev-parse HEAD)" = {head}',
        "git add config/freeze.json",
        (f'git commit -m "freeze: configuration freeze record for {head[:12]}" -- '
         f"config/freeze.json"),
        f'test "$(git rev-parse HEAD^)" = {head}',
        'test "$(git diff-tree --no-commit-id --name-only -r HEAD)" = config/freeze.json',
        f'test "$(sha256sum config/freeze.json | cut -d" " -f1)" = {file_sha}',
        f'git tag -a {seal.FREEZE_TAG} -m "{msg}"',
        f"git push origin main {seal.FREEZE_TAG}",
        (f'test "$(git ls-remote origin refs/tags/{seal.FREEZE_TAG} | cut -f1)" = '
         f'"$(git rev-parse refs/tags/{seal.FREEZE_TAG})"'),
        "# Then merge nothing else until T13 has run.",
    ])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="print the record; write nothing")
    ap.add_argument("--registered-run", default=None,
                    help="abs path of the registered run dir (default runs/slice/<run_id>)")
    a = ap.parse_args(argv)
    root, data = paths.REPO_ROOT, paths.DATA_DIR
    try:
        record, ctx = build_record(root, data,
                                   Path(a.registered_run) if a.registered_run else None)
        raw = serialize(record)
        fz, exceptions = preflight(root, data, raw)
    except (Refusal, seal.SealError) as e:
        print(f"write_freeze refused: {e}", file=sys.stderr)
        return 2
    file_sha = hashlib.sha256(raw).hexdigest()
    if a.dry_run:
        sys.stdout.write(raw.decode())
        print(f"\n# dry run: nothing written. config/freeze.json would have sha256 {file_sha}")
    else:
        out = root / seal.FREEZE_REL
        tmp = out.with_name(f".{out.name}.{os.getpid()}.tmp")
        try:
            tmp.write_bytes(raw)
            os.replace(tmp, out)
        finally:
            tmp.unlink(missing_ok=True)
        again = seal.load_freeze(out)
        if again.sha256 != file_sha:
            print("write_freeze: the written record differs from the validated bytes",
                  file=sys.stderr)
            return 2
        print(f"wrote {out} (sha256 {file_sha})")
    print(f"# deployed policy {fz.deployed_policy}; test_F {fz.raw['test_F']}; "
          f"validation run {fz.raw['validation_run']['run_id']}")
    for x in exceptions:
        print(f"# note (I5): {x}")
    print(lead_commands(ctx["head"], file_sha))
    return 0


if __name__ == "__main__":
    sys.exit(main())
