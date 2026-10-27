"""Stage 3 T12: the completeness cutoff (B4), the freeze writer's §8 rule and record checks, the
optional `test_F_basis` field, and `make data`'s refusal to overwrite. Synthetic data only."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest
import sealkit
from sealkit import FIXTURE, H, balance_frame, make_data_dir
from sealkit import git as sk_git

from gridpilot import completeness, seal
from gridpilot.data.eia_co2 import CONSUMED_COL, GENERATED_COL, SHEET, TIME_COL
from gridpilot.splits import TEST_END, TEST_START

LAB = Path(__file__).resolve().parents[1]
REPO = LAB.parent


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, LAB / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wf = _script("write_freeze")


def _workbook(path: Path, start: datetime, end: datetime, *, skip=(), empty=()) -> None:
    """A synthetic BA workbook: rows hour-ending; `skip` hours have no row, `empty` hours an
    empty consumed cell."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = SHEET
    ws.append([TIME_COL, GENERATED_COL, CONSUMED_COL])
    t = start
    while t < end:
        if t not in skip:
            ws.append([(t + H).replace(tzinfo=None), 0.8, None if t in empty else 0.9])
        t += H
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


# --------------------------------------------------------------------------- completeness


def test_the_cutoff_is_the_day_after_the_last_complete_day(tmp_path):
    data = make_data_dir(tmp_path)  # rows from 2025-10-01 to 2025-11-08 (exclusive)
    log = tmp_path / "c.jsonl"
    rec = completeness.test_cutoff(log, data_dir=data, repo_root=tmp_path)
    assert (rec["D"], rec["test_F"]) == ("2025-11-07", "2025-11-08T00:00:00Z")
    assert set(rec["series"]) == set(completeness.SERIES)
    for s in rec["series"].values():
        assert s["last_row_ts_utc"] == "2025-11-07T23:00:00Z"
        assert s["n_rows_in_window"] == 7 * 24 and s["n_null_in_window"] == 0
        assert s["through_F"]["n_missing_rows"] == 0
    assert set(rec["inputs_sha256"]) == set(seal.TEST_INPUTS[:5])
    lines = log.read_text().splitlines()
    assert len(lines) == 1 and json.loads(lines[0]) == rec
    # Only counts and timestamps: the sentinel sealed values never reach the log.
    for sentinel in ("0.9", "408.2", "9000", "0.8", "362.8"):
        assert sentinel not in lines[0]


START_SYN, END_SYN = datetime(2025, 10, 1, tzinfo=UTC), datetime(2025, 11, 8, tzinfo=UTC)


def _hours_between(a: datetime, b: datetime) -> set[datetime]:
    return {a + i * H for i in range(int((b - a) / H))}


def test_a_missing_row_moves_D_back(tmp_path):
    data = make_data_dir(tmp_path)
    _workbook(data / seal.WORKBOOK_REL.format(ba="CISO"), START_SYN, END_SYN,
              skip={datetime(2025, 11, 7, 5, tzinfo=UTC)})
    rec = completeness.test_cutoff(tmp_path / "c.jsonl", data_dir=data, repo_root=tmp_path)
    assert (rec["D"], rec["test_F"]) == ("2025-11-06", "2025-11-07T00:00:00Z")
    assert rec["last_complete_day_by_series"]["CISO/ci_consumed"] == "2025-11-06"
    assert rec["series"]["CISO/ci_consumed"]["n_rows_in_window"] == 7 * 24 - 1


def test_a_tail_of_null_rows_moves_D_back(tmp_path):
    """T12r finding 1 (spec §5): rows that exist without a value do not make a day complete.
    The publication-lag shape: the last 44 h have rows but empty consumed-CI cells."""
    data = make_data_dir(tmp_path)
    tail = _hours_between(END_SYN - 44 * H, END_SYN)  # 2025-11-06T04Z .. 11-07T23Z
    for ba in seal.CORE_BAS:
        _workbook(data / seal.WORKBOOK_REL.format(ba=ba), START_SYN, END_SYN, empty=tail)
    rec = completeness.test_cutoff(tmp_path / "c.jsonl", data_dir=data, repo_root=tmp_path)
    assert (rec["D"], rec["test_F"]) == ("2025-11-05", "2025-11-06T00:00:00Z")
    s = rec["series"]["PACE/ci_consumed"]
    assert s["last_row_complete_day"] == "2025-11-07"  # rows exist ...
    assert s["last_fully_valued_day"] == "2025-11-05"  # ... values do not
    assert s["last_valued_row_ts_utc"] == "2025-11-06T03:00:00Z"
    assert s["n_null_in_window"] == 44 and s["through_F"]["n_null"] == 0
    assert s["last_days_through_D"]["n_valued"] == 7 * 24  # 10-30 .. 11-05, all valued


def test_an_interior_null_day_before_a_complete_day_does_not_move_D(tmp_path):
    data = make_data_dir(tmp_path)
    interior = _hours_between(datetime(2025, 11, 3, tzinfo=UTC), datetime(2025, 11, 4, tzinfo=UTC))
    _workbook(data / seal.WORKBOOK_REL.format(ba="PACE"), START_SYN, END_SYN, empty=interior)
    rec = completeness.test_cutoff(tmp_path / "c.jsonl", data_dir=data, repo_root=tmp_path)
    assert (rec["D"], rec["test_F"]) == ("2025-11-07", "2025-11-08T00:00:00Z")
    s = rec["series"]["PACE/ci_consumed"]
    assert s["n_null_in_window"] == 24 and s["through_F"]["n_null"] == 24
    assert s["n_fully_valued_days_in_window"] == 6


def test_a_null_demand_tail_moves_D_back(tmp_path):
    data = make_data_dir(tmp_path)
    bal = balance_frame(START_SYN, END_SYN).with_columns(
        pl.when((pl.col("ba").cast(pl.Utf8) == "PACE")
                & (pl.col("ts_utc") >= datetime(2025, 11, 7, 20, tzinfo=UTC)))
        .then(None).otherwise(pl.col("demand_adj_mw")).alias("demand_adj_mw"))
    bal.write_parquet(data / seal.BALANCE_REL)
    rec = completeness.test_cutoff(tmp_path / "c.jsonl", data_dir=data, repo_root=tmp_path)
    assert rec["D"] == "2025-11-06"
    assert rec["series"]["PACE/demand"]["n_null_in_window"] == 4


def test_pace_demand_rows_count_and_other_bas_do_not(tmp_path):
    data = make_data_dir(tmp_path)
    bal = balance_frame(datetime(2025, 10, 1, tzinfo=UTC), datetime(2025, 11, 8, tzinfo=UTC))
    gap = datetime(2025, 11, 7, 12, tzinfo=UTC)
    bal = bal.filter(~((pl.col("ba").cast(pl.Utf8) == "PACE") & (pl.col("ts_utc") == gap)))
    bal.write_parquet(data / seal.BALANCE_REL)
    rec = completeness.test_cutoff(tmp_path / "c.jsonl", data_dir=data, repo_root=tmp_path)
    assert rec["D"] == "2025-11-06"
    assert rec["series"]["PACE/demand"]["through_F"]["n_missing_rows"] == 0  # F excludes 11-07


def test_the_cutoff_is_capped_at_test_end(tmp_path):
    data = tmp_path / "data"
    start, end = TEST_END - timedelta(days=3), TEST_END + timedelta(days=2)
    for ba in seal.CORE_BAS:
        _workbook(data / seal.WORKBOOK_REL.format(ba=ba), start, end)
    bal = data / seal.BALANCE_REL
    bal.parent.mkdir(parents=True)
    balance_frame(start, end).write_parquet(bal)
    rec = completeness.test_cutoff(tmp_path / "c.jsonl", data_dir=data, repo_root=tmp_path)
    assert (rec["D"], rec["test_F"]) == ("2026-10-31", seal.iso(TEST_END))


def test_a_failed_count_is_logged_too(tmp_path):
    data = make_data_dir(tmp_path)
    (data / seal.WORKBOOK_REL.format(ba="NEVP")).unlink()
    log = tmp_path / "c.jsonl"
    with pytest.raises(FileNotFoundError):
        completeness.test_cutoff(log, data_dir=data, repo_root=tmp_path)
    (rec,) = completeness.read_log(log)
    assert rec["outcome"].startswith("error: FileNotFoundError")


# --------------------------------------------------------------------------- the record


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text())


def test_test_F_basis_is_optional_and_must_agree_with_test_F():
    d = _fixture()
    assert seal.freeze_errors(d) == []
    d["test_F_basis"] = {"D": "2026-10-24", "rule": "r",
                         "last_row_ts_utc": {"PACE/demand": "2026-10-26T06:00:00Z"},
                         "completeness_log": {"path": "docs/x.jsonl", "line_sha256": "a" * 64}}
    assert seal.freeze_errors(d) == []
    bad = copy.deepcopy(d)
    bad["test_F_basis"]["D"] = "2026-10-23"
    assert any("min(D + 1 day" in e for e in seal.freeze_errors(bad))
    bad = copy.deepcopy(d)
    bad["test_F_basis"]["D"] = "2026-10-24T00:00:00Z"
    assert seal.freeze_errors(bad)
    bad = copy.deepcopy(d)
    bad["test_F_basis"]["extra"] = 1
    assert any(e.startswith("schema:") for e in seal.freeze_errors(bad))
    bad = copy.deepcopy(d)
    bad["test_F_extra"] = 1
    assert "unknown key 'test_F_extra'" in seal.freeze_errors(bad)


def test_the_deployment_rule_on_the_committed_validation_metrics_is_S():
    metrics = json.loads((REPO / "results" / "metrics.json").read_text())
    name, trace = wf.deploy_rule(metrics)
    assert name == "S"
    assert trace[1]["result"] == "U, G, S, K, W, L pass"
    assert trace[2]["result"].startswith("S (")
    assert trace[-1] == {"rule": "deployed product policy", "result": "S"}
    assert set(trace[2]["values"]["co2_kg"]) == set(seal.SELECTION_POLICIES)


def _metrics(co2: dict, wait: dict, infeasible=()) -> dict:
    pols = {}
    for p in seal.SELECTION_POLICIES:
        m = {k: {"value": v} for k, v in {
            "late_jobs": 1 if p in infeasible else 0, "capacity_violations": 0,
            "completed_gpu_s": 10.0, "requested_gpu_s": 10.0, "co2_kg": co2[p],
            "wait_mean_s": wait[p]}.items()}
        pols[p] = {"status": "ok", "feasible": p not in infeasible, "conserved": True,
                   "metrics": m, "bound_check": {"consumed": {"ok": True}}}
    return {"run_id": "R", "policies": pols}


BASE_CO2 = {"U": 10.0, "G": 9.0, "S": 5.0, "K": 6.0, "W": 5.5, "L": 5.6}
BASE_WAIT = {"U": 1.0, "G": 1.0, "S": 50.0, "K": 60.0, "W": 40.0, "L": 30.0}


def test_the_rule_excludes_infeasible_then_breaks_ties_on_wait_then_order():
    assert wf.deploy_rule(_metrics(BASE_CO2, BASE_WAIT))[0] == "S"
    assert wf.deploy_rule(_metrics(BASE_CO2, BASE_WAIT, infeasible={"S"}))[0] == "W"
    tie = BASE_CO2 | {"W": 5.0 + 5e-7}
    assert wf.deploy_rule(_metrics(tie, BASE_WAIT))[0] == "W"  # equal CO2, W waits less
    assert wf.deploy_rule(_metrics(tie, BASE_WAIT | {"W": 50.0}))[0] == "S"  # then order
    with pytest.raises(wf.Refusal):
        wf.deploy_rule(_metrics(BASE_CO2, BASE_WAIT, infeasible=set(seal.SELECTION_POLICIES)))


def test_l_leaves_must_be_json_integers_for_every_series():
    good = {"series": {k: {"L_max_leaf_nodes": 15} for k in seal.SERIES}}
    assert wf.l_leaves(good) == {k: 15 for k in seal.SERIES}
    bad = copy.deepcopy(good)
    bad["series"]["PACE/demand"]["L_max_leaf_nodes"] = 31.0
    with pytest.raises(wf.Refusal):
        wf.l_leaves(bad)
    del bad["series"]["PACE/wind"]
    with pytest.raises(wf.Refusal):
        wf.l_leaves(bad)


def test_the_completeness_basis_needs_agreement_and_the_same_inputs(tmp_path):
    data = make_data_dir(tmp_path)
    log = tmp_path / "c.jsonl"
    completeness.test_cutoff(log, data_dir=data, repo_root=tmp_path)
    completeness.test_cutoff(log, data_dir=data, repo_root=tmp_path)
    cur = {rel: seal.file_sha256(data / rel) for rel in seal.TEST_INPUTS}
    F, basis = wf.completeness_basis(log.read_bytes(), cur)
    assert F == "2025-11-08T00:00:00Z" and basis["D"] == "2025-11-07"
    line2 = log.read_text().splitlines()[1]
    assert basis["completeness_log"]["line_sha256"] == hashlib.sha256(line2.encode()).hexdigest()
    with pytest.raises(wf.Refusal, match="different input files"):
        wf.completeness_basis(log.read_bytes(), cur | {seal.BALANCE_REL: "0" * 64})
    recs = completeness.read_log(log)
    recs[0]["D"], recs[0]["test_F"] = "2025-11-06", "2025-11-07T00:00:00Z"
    raw = "".join(json.dumps(r) + "\n" for r in recs).encode()
    with pytest.raises(wf.Refusal, match="disagree"):
        wf.completeness_basis(raw, cur)
    # A line made under an earlier rule (T12r finding 1) is superseded, not a disagreement.
    recs[0]["rule"] = "an earlier rule: row present, null or not"
    raw = "".join(json.dumps(r) + "\n" for r in recs).encode()
    assert wf.completeness_basis(raw, cur)[0] == "2025-11-08T00:00:00Z"
    recs[1]["rule"] = recs[0]["rule"]
    raw = "".join(json.dumps(r) + "\n" for r in recs).encode()
    with pytest.raises(wf.Refusal, match="current rule"):
        wf.completeness_basis(raw, cur)


def test_the_lead_commands_commit_the_record_alone_and_check_the_remote_tag():
    cmds = wf.lead_commands("a" * 40, "b" * 64)
    assert "-- config/freeze.json" in cmds and "seal.freeze_tag_message" in cmds
    assert f"git tag -a {seal.FREEZE_TAG}" in cmds and "git ls-remote origin" in cmds
    assert "git push --atomic origin main config-freeze" in cmds
    assert cmds.splitlines()[3] == "set -euo pipefail"
    assert 'test "$(git rev-parse origin/main)" = ' + "a" * 40 in cmds
    r = subprocess.run(["bash", "-n"], input=cmds, text=True, capture_output=True, check=False)
    assert r.returncode == 0, r.stderr  # the printed sequence is valid bash


# --------------------------------------------------------------------------- make data


def test_make_data_refuses_to_replace_a_pinned_table(tmp_path):
    data = make_data_dir(tmp_path)
    (data / "raw" / "eia930" / "EIA930_BALANCE_2025_Jul_Dec.csv").write_text("x\n")
    before = seal.file_sha256(data / seal.BALANCE_REL)
    r = subprocess.run([sys.executable, str(LAB / "scripts" / "build_data.py")], cwd=LAB,
                       env={**os.environ, "GRIDPILOT_DATA_DIR": str(data)},
                       capture_output=True, text=True, check=False)
    assert r.returncode == 2 and "refusing to replace" in r.stderr
    assert seal.file_sha256(data / seal.BALANCE_REL) == before


def test_the_completeness_window_constants():
    assert completeness.TEST_START == TEST_START and completeness.WORKBOOK_REL == seal.WORKBOOK_REL
    assert completeness.BALANCE_REL == seal.BALANCE_REL


# --------------------------------------------------------------------------- end to end


RUN = "20261027T160656Z"
SYN_MEANS = {"BPAT": 90.0, "CISO": 200.0, "NEVP": 300.0, "PACE": 580.0}


def _e2e(tmp_path):
    """A synthetic repo as T12 leaves it: code (lab/), committed validation results, the
    rebuild evidence and the completeness log; a registered forecast run; a marked data dir
    with a validation carbon table. Returns (repo, data, snapshot id)."""
    data = make_data_dir(tmp_path)
    hours = [datetime(2025, 10, 1, tzinfo=UTC) + i * H for i in range(19 * 24)]
    carbon = data / "processed" / "carbon" / "carbon_hourly.parquet"
    carbon.parent.mkdir(parents=True)
    pl.DataFrame({"ba": [b for b in SYN_MEANS for _ in hours],
                  "ts_utc": hours * len(SYN_MEANS),
                  "ci_consumed_g_kwh": [v for v in SYN_MEANS.values() for _ in hours]}
                 ).with_columns(pl.col("ts_utc").cast(pl.Datetime("us", "UTC"))
                                ).write_parquet(carbon)
    repo = tmp_path / "repo"
    repo.mkdir()
    sk_git(repo, "init", "-q", "-b", "main")
    (repo / ".gitignore").write_text("runs/\n")
    (repo / "lab").mkdir()
    (repo / "lab" / "code.py").write_text("FROZEN = True\n")
    sid = sealkit._manifests(repo, data)
    (repo / "config").mkdir()
    shutil.copy(REPO / seal.FREEZE_SCHEMA_REL, repo / seal.FREEZE_SCHEMA_REL)
    fc = repo / "runs" / "slice" / RUN / "forecast" / RUN
    fc.mkdir(parents=True)
    pl.DataFrame({"x": [1, 2]}).write_parquet(fc / "forecasts.parquet")
    leaves = {k: (31 if k == "PACE/demand" else 15) for k in seal.SERIES}
    (fc / "metrics.json").write_text(json.dumps(
        {"series": {k: {"L_max_leaf_nodes": v} for k, v in leaves.items()}}) + "\n")
    (repo / "results").mkdir()
    (repo / "results" / "metrics.json").write_text(
        json.dumps(_metrics(BASE_CO2, BASE_WAIT) | {"run_id": RUN}) + "\n")
    (repo / "results" / "manifest.json").write_text(json.dumps(
        {"run_id": RUN, "reproducibility": {"forecast_run": {
            "forecasts_sha256": seal.file_sha256(fc / "forecasts.parquet")}}}) + "\n")
    sk_git(repo, "add", "-A")
    sk_git(repo, "commit", "-q", "-m", "code")
    completeness.test_cutoff(repo / wf.COMPLETENESS_LOG_REL, data_dir=data, repo_root=repo)
    ev = {"match": True, "clone": {"lab_tree": sk_git(repo, "rev-parse", "HEAD:lab")},
          "validation_reference": seal.validation_reference(repo),
          "forecast": {"registered_metrics_sha256": seal.file_sha256(fc / "metrics.json"),
                       "L_max_leaf_nodes": {"rebuild": leaves}},
          "tables": {"balance.parquet": {"sha256": {"main": seal.file_sha256(
                         data / seal.BALANCE_REL)}},
                     "carbon_hourly.parquet": {"sha256": {"main": seal.file_sha256(carbon)}}}}
    (repo / wf.REBUILD_EVIDENCE_REL).write_text(json.dumps(ev, indent=1) + "\n")
    sk_git(repo, "add", "-A")
    sk_git(repo, "commit", "-q", "-m", "evidence (the freeze commit)")
    return repo, data, sid


def test_a_written_record_committed_alone_and_tagged_passes_authorize(tmp_path):
    repo, data, sid = _e2e(tmp_path)
    head = sk_git(repo, "rev-parse", "HEAD")
    rec, ctx = wf.build_record(repo, data, None, synthetic=True, expected_snapshot=sid)
    assert rec["freeze_commit"] == head == ctx["head"]
    assert rec["deployed_policy"]["name"] == "S"
    assert rec["test_F"] == "2025-11-08T00:00:00Z" and rec["test_F_basis"]["D"] == "2025-11-07"
    assert rec["s_ranking"]["order"] == ["BPAT", "CISO", "NEVP", "PACE"]
    assert rec["s_ranking"]["mean_consumed_ci_g_kwh"] == SYN_MEANS
    assert set(rec["input_sha256"]) == set(seal.TEST_INPUTS)
    raw = wf.serialize(rec)
    wf.preflight(repo, data, raw)
    (repo / seal.FREEZE_REL).write_bytes(raw)
    sk_git(repo, "add", seal.FREEZE_REL)
    sk_git(repo, "commit", "-q", "-m", "freeze record", "--", seal.FREEZE_REL)
    sk_git(repo, "tag", "-a", seal.FREEZE_TAG, "-m",
           seal.freeze_tag_message(seal.file_sha256(repo / seal.FREEZE_REL)))
    auth = sealkit.authorize(repo, data)
    assert auth.freeze.raw == rec and auth.F == datetime(2025, 11, 8, tzinfo=UTC)
    # A second freeze over the first one is refused.
    with pytest.raises(wf.Refusal, match="already"):
        wf.build_record(repo, data, None, synthetic=True, expected_snapshot=sid)


def test_the_writer_refuses_unrebuilt_code_a_dirty_tree_and_a_failed_rebuild(tmp_path):
    repo, data, sid = _e2e(tmp_path)
    kw = {"synthetic": True, "expected_snapshot": sid}
    (repo / "lab" / "code.py").write_text("FROZEN = False\n")
    with pytest.raises(wf.Refusal, match="not clean"):
        wf.build_record(repo, data, None, **kw)
    sk_git(repo, "commit", "-q", "-am", "change code after the rebuild")
    with pytest.raises(wf.Refusal, match="was not rebuilt"):
        wf.build_record(repo, data, None, **kw)
    sk_git(repo, "reset", "-q", "--hard", "HEAD~1")
    ev = json.loads((repo / wf.REBUILD_EVIDENCE_REL).read_text()) | {"match": False}
    (repo / wf.REBUILD_EVIDENCE_REL).write_text(json.dumps(ev) + "\n")
    sk_git(repo, "commit", "-q", "-am", "a failed rebuild")
    with pytest.raises(wf.Refusal, match="did not match"):
        wf.build_record(repo, data, None, **kw)
    with pytest.raises(wf.Refusal, match="synthetic data dir"):
        wf.build_record(repo, data, None, expected_snapshot=sid)
