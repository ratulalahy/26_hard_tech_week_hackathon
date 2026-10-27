"""Stage 3 T11 B2: one explicit window through every layer. Each layer defaults to
validation and never returns a sealed row there; with `Window.test()` (only inside the test
mode a synthetic authorization opens) it reads through `sealed_read`, and every such read is
in the log. Synthetic sealed rows in a temporary data directory only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl
import pytest
import sealkit

from gridpilot import forecast as fcmod
from gridpilot import grid_profile as gp
from gridpilot import seal
from gridpilot.data import eia_co2, truth_fill
from gridpilot.eval import TruthTable, support_check
from gridpilot.results import sealed_timestamps, validate_artifact, write_json_atomic
from gridpilot.sim import CarbonSearch
from gridpilot.splits import TEST_START
from gridpilot.window import Window

H = timedelta(hours=1)
F = sealkit.F_SYN
SEALED_G = sealkit.SEALED_LB * eia_co2.LB_TO_G
PRE_G = sealkit.PRE_LB * eia_co2.LB_TO_G


@pytest.fixture
def opened(tmp_path, monkeypatch):
    """(session, data_dir, results_dir, calls): a synthetic test-mode session; `calls`
    counts every sealed_read call the layers make."""
    repo, data, results = sealkit.setup(tmp_path)
    calls = []
    real = seal.sealed_read

    def counting(*a, **k):
        calls.append(k.get("purpose"))
        return real(*a, **k)

    monkeypatch.setattr(seal, "sealed_read", counting)
    with seal.test_mode(sealkit.authorize(repo, data)) as s:
        yield s, data, results, calls


def _reads(results):
    return [r for r in sealkit.read_log(results) if r["event"] == "read"]


def test_every_layer_reads_the_test_window_through_sealed_read(opened):
    s, data, results, calls = opened
    w = Window.test()
    # eia_co2: the test table goes to its own path, built through sealed_read
    p = eia_co2.build_carbon(window=w)
    assert p == data / eia_co2.CARBON_TEST_REL
    assert not (data / "processed" / "carbon" / "carbon_hourly.parquet").exists()
    c = eia_co2.load_carbon(window=w)
    assert c["ts_utc"].max() == F - H
    assert set(c.filter(pl.col("ts_utc") >= TEST_START)["ci_consumed_g_kwh"]) == {SEALED_G}
    eia_co2.site_mask(c, TEST_START, F, window=w)
    # truth_fill: tiers from the test table and the balance table
    filled = truth_fill.fill_truth(w.init, F, list(seal.CORE_BAS), window=w)
    sealed = filled.filter(pl.col("ts_utc") >= TEST_START)
    assert set(sealed["tier"]) == {1} and set(sealed["ci_g_kwh"]) == {SEALED_G}
    # forecast series
    for target in ("ci_consumed", "demand"):
        fr = fcmod.load_series(target, window=w)
        assert fr["ts_utc"].max() == F - H
    # grid profile inputs
    carbon, balance = gp.load_inputs(w)
    assert carbon["ts_utc"].min() >= TEST_START and balance["ts_utc"].max() == F - H
    reads = _reads(results)
    assert len(reads) == len(calls) == 4 + 1 + 2 + 2 + 2
    assert [r["purpose"] for r in reads] == calls
    assert all(r["sha256"] and r["caller"] and r["time_range"][1] <= seal.iso(F) for r in reads)
    paths = {r["path"] for r in reads}
    assert str(data / eia_co2.CARBON_TEST_REL) in paths
    assert str(data / seal.BALANCE_REL) in paths


def test_accounting_search_and_results_take_the_test_bound(opened):
    s, data, results, calls = opened
    w = Window.test()
    eia_co2.build_carbon(window=w)
    filled = truth_fill.fill_truth(w.init, F, list(seal.CORE_BAS), window=w)
    tt = TruthTable(filled, truth_fill.fill_mask(filled), window=w)
    t0 = int(TEST_START.timestamp()) * 10**6
    val, miss = tt.integral("PACE", np.array([t0]), np.array([t0 + 3600 * 10**6]))
    assert not miss[0] and val[0] == pytest.approx(SEALED_G)
    f_us = int(F.timestamp()) * 10**6
    with pytest.raises(ValueError, match="read bound"):
        tt.integral("PACE", np.array([f_us]), np.array([f_us + 3600 * 10**6]))
    book = pl.DataFrame({"job_uid": ["a"], "site": ["PACE"], "start_us": [t0],
                         "end_us": [t0 + 7200 * 10**6]})
    assert support_check(book, tt, F, window=w)["ok"]
    h = CarbonSearch("H", None, filled, truth_col="ci_g_kwh", window=w,
                     grid=(w.init, F))
    assert h.window.is_test
    assert seal.active() is s
    art = {"window": "test", "covered": {"arrivals": [seal.iso(TEST_START), seal.iso(F)]}}
    assert validate_artifact(art, window=w) == []
    late = {"window": "test", "t": seal.iso(F + H)}
    assert sealed_timestamps(late, window=w) == ["$.t"]
    assert any("declare window 'test'" in e for e in validate_artifact({"x": 1}, window=w))
    write_json_atomic(results / "t.json", art, window=w)
    with pytest.raises(ValueError):
        write_json_atomic(results / "u.json", art)  # a test artifact needs the test window


def test_validation_defaults_never_return_a_sealed_row(tmp_path):
    """Outside the context every layer drops, or refuses, rows at or after TEST_START."""
    data = sealkit.make_data_dir(tmp_path)
    frames = [eia_co2.parse_ba_workbook(data / seal.WORKBOOK_REL.format(ba=ba), ba)
              for ba in seal.CORE_BAS]
    carbon = pl.concat(frames)
    assert carbon["ts_utc"].max() >= TEST_START  # the synthetic table does hold sealed rows
    p = tmp_path / "carbon.parquet"
    carbon.write_parquet(p)
    assert eia_co2.load_carbon(p)["ts_utc"].max() < TEST_START
    with pytest.raises(ValueError, match="TEST_START"):
        eia_co2.site_mask(carbon, TEST_START - H, F)
    fuel = pl.DataFrame({"ba": ["PACE"], "ts_utc": [TEST_START], "ci_g_kwh": [1.0]})
    with pytest.raises(ValueError):
        truth_fill.fill_truth(TEST_START, F, ["PACE"], carbon=carbon, fuel_ci=fuel)
    with pytest.raises(ValueError, match="sealed"):
        truth_fill.fill_truth(TEST_START - 24 * H, TEST_START, ["PACE"], carbon=carbon,
                              fuel_ci=fuel)
    tt = TruthTable(carbon)
    assert tt.end_us == int(TEST_START.timestamp()) * 10**6
    t0 = int(TEST_START.timestamp()) * 10**6
    book = pl.DataFrame({"job_uid": ["a"], "site": ["PACE"], "start_us": [t0 - 3600 * 10**6],
                         "end_us": [t0 + 3600 * 10**6]})
    assert support_check(book, tt, F)["n_missing_truth"] == 1
    with pytest.raises(ValueError, match="seal"):
        CarbonSearch("H", None, carbon, truth_col="ci_consumed_g_kwh")
    fc = pl.DataFrame({"ba": ["PACE"], "target": ["ci_consumed"], "model": ["K"],
                       "issue_ts": [TEST_START - 30 * H], "target_ts": [TEST_START],
                       "value": [1.0], "evidence": ["forecast"]})
    truth = pl.DataFrame({"ba": ["PACE"], "ts_utc": [TEST_START - H], "value": [1.0]})
    with pytest.raises(ValueError, match="sealed"):
        fcmod.score(fc, truth, 1.0)
    assert sealed_timestamps({"t": seal.iso(TEST_START)}) == ["$.t"]
    assert any("written with the test window" in e for e in validate_artifact({"window": "test"}))
    with pytest.raises(ValueError, match="seal"):
        gp.check_window(TEST_START - H, TEST_START + H)


def test_a_test_window_kept_after_the_context_refuses_every_layer(tmp_path):
    repo, data, results = sealkit.setup(tmp_path)
    with seal.test_mode(sealkit.authorize(repo, data)):
        w = Window.test()
        eia_co2.build_carbon(window=w)
    n = len(_reads(results))
    for call in (lambda: eia_co2.load_carbon(window=w),
                 lambda: truth_fill.fill_truth(w.init, F, ["PACE"], window=w),
                 lambda: fcmod.load_series("demand", window=w),
                 lambda: gp.load_inputs(w),
                 lambda: TruthTable(pl.DataFrame({"ba": ["PACE"], "ts_utc": [TEST_START],
                                                  "ci_consumed_g_kwh": [1.0]}), window=w),
                 lambda: CarbonSearch("H", None, pl.DataFrame(), window=w)):
        with pytest.raises(seal.SealError):
            call()
    assert len(_reads(results)) == n  # nothing more was read


def test_test_window_bounds():
    with pytest.raises(seal.SealError):
        Window("test", seal.TEST_INIT, TEST_START, datetime(2026, 10, 25, tzinfo=UTC))


def test_forecast_issues_cover_the_first_test_day_and_end_by_F(opened):
    w = Window.test()
    issues = fcmod.issues_for_window(w)
    assert issues[0] == datetime(2025, 10, 29, 16, tzinfo=UTC)  # 10:00 MDT on the fit day
    assert all(fcmod.target_hours(i)[-1] + H <= F for i in issues)
    first_day = fcmod.target_hours(datetime(2025, 10, 31, 16, tzinfo=UTC))
    assert first_day[0] <= TEST_START + 7 * H  # Utah's Nov 1 is forecast by the Oct 31 issue
    with pytest.raises(ValueError):
        fcmod.issues_for_window(Window.validation())
