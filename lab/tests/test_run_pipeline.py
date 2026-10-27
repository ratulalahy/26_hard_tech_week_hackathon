"""Stage 3 T10 Part A: `run_pipeline` guards, the common-A rule for extension cohorts (F14.1),
the extension summary contract, and the registered-run reproduction check."""

from __future__ import annotations

import importlib.util
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from gridpilot.paths import RESULTS_DIR
from gridpilot.results import canonical_hash, unenveloped_numbers
from gridpilot.scenario import EXTENSIONS, Scenario, Window

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_slice.py"
H = timedelta(hours=1)
T = datetime(2024, 11, 4, tzinfo=UTC)
F = T + 30 * H


@pytest.fixture(scope="module")
def rs():
    spec = importlib.util.spec_from_file_location("run_slice", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_run_pipeline_refuses_to_export_a_sensitivity(rs, tmp_path):
    with pytest.raises(ValueError, match="never exports"):
        rs.run_pipeline(Window.validation(), EXTENSIONS["dest_slots_0"], tmp_path, export=True)
    with pytest.raises(TypeError):
        rs.run_pipeline("validation", Scenario.primary(), tmp_path, export=False)
    assert list(tmp_path.iterdir()) == []  # refused before any run directory was made


def test_extension_runs_go_to_runs_ext(rs):
    assert rs.default_root(Scenario.primary()).parts[-2:] == ("runs", "slice")
    assert rs.default_root(EXTENSIONS["phase_49"]).parts[-3:] == ("runs", "ext", "phase_49")


def _jobs(rows):
    """rows: (uid, arrival offset h, duration h, gpus, flexible)."""
    return pl.DataFrame({
        "job_uid": [r[0] for r in rows],
        "source_id": [r[0].split("#")[0] for r in rows],
        "arrival_ts": [T + r[1] * H for r in rows],
        "duration_s": [r[2] * 3600.0 for r in rows],
        "gpus": [r[3] for r in rows],
        "job_type": ["Pretrain"] * len(rows),
        "flexible": [r[4] for r in rows],
        "max_delay_s": [21600 if r[4] else 0 for r in rows],
        "mobile": [r[4] for r in rows],
    }, schema_overrides={"arrival_ts": pl.Datetime("us", "UTC"), "gpus": pl.Int64,
                         "max_delay_s": pl.Int64})


WARM = _jobs([("w0#c0", -2, 3, 2, False)])
STREAM = _jobs([
    ("j1#c0", 0, 1, 16, True),  # 24 h delay: deadline T+25h <= F
    ("j0#c0", 5, 1, 2, False),
    ("j2#c0", 10, 1, 4, True),  # 24 h delay: deadline T+35h > F -> first failure (F14.1)
    ("j3#c0", 12, 1, 4, False),
])


def test_every_scenario_in_a_phase_shares_the_f14_1_A(rs):
    prim = rs._cohort(WARM, STREAM, F, Scenario.primary())
    assert prim.A == T + 10 * H  # set by the registered batch_delay_24h scenario
    assert prim.first_failure["batch_delay_24h"] == T + 10 * H
    for name in ("dest_slots_0", "dest_slots_1024", "transfer_120min", "mobility_le_8gpus",
                 "batch_delay_24h"):
        c = rs._cohort(WARM, STREAM, F, EXTENSIONS[name])
        assert c.A == prim.A, name
        assert c.jobs["job_uid"].to_list() == prim.jobs["job_uid"].to_list(), name


def test_extension_cohort_follows_its_own_knobs(rs):
    prim = rs._cohort(WARM, STREAM, F, Scenario.primary())
    mob = rs._cohort(WARM, STREAM, F, EXTENSIONS["mobility_le_8gpus"])
    assert dict(zip(mob.jobs["job_uid"], mob.jobs["mobile"], strict=True))["j1#c0"] is False
    assert mob.bookings.sort("job_uid").equals(prim.bookings.sort("job_uid"))  # U unchanged
    b24 = rs._cohort(WARM, STREAM, F, EXTENSIONS["batch_delay_24h"])
    dl = dict(zip(b24.bookings["job_uid"], b24.bookings["deadline_us"], strict=True))
    t_us = int(T.timestamp()) * 10**6
    assert dl["j1#c0"] == t_us + 25 * 3600 * 10**6
    assert b24.bookings.select("site", "start_us", "end_us").sort("start_us").equals(
        prim.bookings.select("site", "start_us", "end_us").sort("start_us"))


def test_scenario_record_envelopes_every_knob_as_assumed(rs):
    rec = rs.scenario_record(EXTENSIONS["mobility_le_8gpus"], "r:scenario")
    assert {k: v["evidence"] for k, v in rec["knobs"].items()} == {
        k: "assumed" for k in rs.SCENARIO_KNOB_UNITS}
    assert rec["knobs"]["mobility_max_gpus"]["value"] == 8
    none = rs.scenario_record(EXTENSIONS["phase_49"], "r:scenario")["knobs"]
    assert none["mobility_max_gpus"]["value"] is None and none["mobility_max_gpus"]["reason"]
    assert unenveloped_numbers(rec) == []


# --------------------------------------------------------------------------- reproduction

REPRO_ENV = "GRIDPILOT_PRIMARY_REPRO_RUN"


@pytest.mark.skipif(not os.environ.get(REPRO_ENV),
                    reason=f"set {REPRO_ENV}=<run dir> of a primary run made by this code")
def test_primary_run_reproduces_the_registered_ledgers_and_metrics():
    """The refactored pipeline's primary run hash-equals the registered run (20 min to make,
    so it is opt-in): every canonical ledger hash, and the canonical metrics hash under the
    10-significant-digit rule, computed on both metrics.json files."""
    run = Path(os.environ[REPRO_ENV])
    man = json.loads((RESULTS_DIR / "manifest.json").read_text())
    cfg = json.loads((run / "config.json").read_text())
    assert cfg["reproducibility"]["ledger_canonical_sha256"] == \
        man["reproducibility"]["ledger_canonical_sha256"]
    reg = json.loads((RESULTS_DIR / "metrics.json").read_text())
    new = json.loads((run / "results" / "metrics.json").read_text())
    assert canonical_hash(new) == canonical_hash(reg)
