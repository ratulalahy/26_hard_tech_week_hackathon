"""Stage 3 T10b (D-061): the storage illustration. Hand-checked toy days for both strategies,
the training-only schedule, the exact-overlap load profile and the seal."""

from __future__ import annotations

import ast
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from gridpilot import storage as st
from gridpilot.forecast import VAL_FIT_AT, VAL_HISTORY_START
from gridpilot.sim.power import GPU_KW, PUE
from gridpilot.splits import TEST_START

H = 3600 * 1_000_000
T0 = datetime(2025, 3, 3, 7, tzinfo=UTC)  # 00:00 America/Denver (MST)


def _us(t: datetime) -> int:
    return int((t - datetime(1970, 1, 1, tzinfo=UTC)) / timedelta(microseconds=1))


# --------------------------------------------------------------------------- load profile


def _ledger(rows):
    return pl.DataFrame(
        {"site": [r[0] for r in rows], "start_ts": [r[1] for r in rows],
         "end_ts": [r[2] for r in rows], "gpus": [r[3] for r in rows]},
        schema={"site": pl.Utf8, "start_ts": pl.Datetime("us", "UTC"),
                "end_ts": pl.Datetime("us", "UTC"), "gpus": pl.Int64})


def test_hourly_load_is_exact_overlap_at_the_site():
    rate = GPU_KW * PUE
    led = _ledger([
        ("PACE", T0 + timedelta(minutes=30), T0 + timedelta(hours=2), 2),  # 0.5 h, then 1 h
        ("PACE", T0 + timedelta(hours=1, minutes=15), T0 + timedelta(hours=1, minutes=45), 4),
        ("BPAT", T0, T0 + timedelta(hours=3), 8),  # another site: not in PACE's load
    ])
    load = st.hourly_load_kwh(led, "PACE", _us(T0), 3)
    assert load == pytest.approx([2 * 0.5 * rate, (2 * 1 + 4 * 0.5) * rate, 0.0])


def test_hourly_load_total_matches_the_ledger_energy():
    rng = np.random.default_rng(3)
    s = rng.integers(0, 20 * H, 200)
    e = s + rng.integers(1, 5 * H, 200)
    g = rng.integers(1, 64, 200)
    led = _ledger([("PACE", T0 + timedelta(microseconds=int(a)), T0 + timedelta(microseconds=int(b)),
                    int(k)) for a, b, k in zip(s, e, g, strict=True)])
    load = st.hourly_load_kwh(led, "PACE", _us(T0), 30)
    want = math.fsum((g * (e - s) / H * GPU_KW * PUE).tolist())
    assert math.fsum(load.tolist()) == pytest.approx(want, rel=1e-12)


def test_hourly_load_refuses_the_sealed_window():
    led = _ledger([("PACE", TEST_START - timedelta(hours=1), TEST_START, 1)])
    with pytest.raises(ValueError, match="seal"):
        st.hourly_load_kwh(led, "PACE", _us(TEST_START - timedelta(hours=1)), 2)


# --------------------------------------------------------------------------- training schedule


def _train(values_by_hour, start=VAL_HISTORY_START, days=3):
    """An hourly series whose value depends on the America/Denver hour of day only."""
    ts = pl.datetime_range(start, start + timedelta(days=days), "1h", time_unit="us",
                           time_zone="UTC", eager=True, closed="left")
    hr = ts.dt.convert_time_zone("America/Denver").dt.hour().to_numpy()
    return pl.DataFrame({"ts_utc": ts, "value": [float(values_by_hour[h]) for h in hr]})


def test_schedule_hours_come_from_training_means():
    v = [500.0] * 24
    for h, x in {11: 300, 12: 290, 13: 280, 14: 285, 15: 310, 10: 320, 9: 330}.items():
        v[h] = x
    for h, x in {19: 700, 20: 720, 21: 710, 18: 690, 22: 680, 7: 670, 6: 600}.items():
        v[h] = x
    sch = st.training_schedule(_train(v))
    assert sch["charge_hours"] == [10, 11, 12, 13, 14, 15]
    assert sch["discharge_hours"] == [7, 18, 19, 20, 21, 22]
    assert sch["profile"][13] == pytest.approx(280)
    assert sch["n_hours"][0] == 3


def test_schedule_refuses_validation_rows():
    """The schedule is chosen on training data only, [2022-01-01, 2024-10-29): no peeking."""
    ok = _train([400.0] * 24, start=VAL_FIT_AT - timedelta(days=3))
    st.training_schedule(ok)  # ends exactly at the training end: allowed
    late = _train([400.0] * 24, start=VAL_FIT_AT - timedelta(days=2))
    with pytest.raises(ValueError, match="training"):
        st.training_schedule(late)
    early = _train([400.0] * 24, start=VAL_HISTORY_START - timedelta(days=1))
    with pytest.raises(ValueError, match="training"):
        st.training_schedule(early)
    assert st.TRAIN_START == VAL_HISTORY_START and st.TRAIN_END == VAL_FIT_AT


def test_schedule_ignores_nulls():
    df = _train([400.0] * 24).with_columns(
        pl.when(pl.col("ts_utc").dt.convert_time_zone("America/Denver").dt.hour() == 3)
        .then(None).otherwise(pl.col("value")).alias("value"))
    sch = st.training_schedule(df)
    assert sch["n_hours"][3] == 0 and sch["profile"][3] is None
    assert 3 not in sch["charge_hours"] + sch["discharge_hours"]


# --------------------------------------------------------------------------- strategy A


def test_fixed_schedule_toy_day_by_hand():
    # hours 0..5 of one local day; charge at 1, 2; discharge at 4, 5; E=1, P=0.6, eta=0.8
    hour = np.arange(6)
    load = np.array([5.0, 5.0, 5.0, 5.0, 0.3, 5.0])
    c, d, soc = st.fixed_schedule(load, hour, [1, 2], [4, 5], e_kwh=1.0, p_kw=0.6, eta=0.8)
    # hour 1: draws P = 0.6 -> stores 0.48; hour 2: headroom 0.52 / 0.8 = 0.65 > P -> 0.6, stores 0.48
    assert c == pytest.approx([0, 0.6, 0.6, 0, 0, 0])
    # hour 4: load caps the discharge at 0.3; hour 5: P caps it at 0.6 (0.66 left)
    assert d == pytest.approx([0, 0, 0, 0, 0.3, 0.6])
    assert soc == pytest.approx([0, 0.48, 0.96, 0.96, 0.66, 0.06])


def test_fixed_schedule_energy_limit_and_carryover():
    hour = np.array([0, 1, 2, 0, 1, 2])  # two days: charge at 0, discharge at 2
    load = np.full(6, 10.0)
    c, d, soc = st.fixed_schedule(load, hour, [0], [2], e_kwh=0.5, p_kw=2.0, eta=0.5)
    assert c == pytest.approx([1.0, 0, 0, 1.0, 0, 0])  # (E − soc)/eta = 1 grid kWh < P
    assert d == pytest.approx([0, 0, 0.5, 0, 0, 0.5])
    assert soc.max() <= 0.5 + 1e-12


@pytest.mark.parametrize("eta", [0.75, 0.85, 0.9])
def test_fixed_schedule_conserves_energy_and_respects_limits(eta):
    rng = np.random.default_rng(7)
    n = 24 * 20
    hour = np.arange(n) % 24
    load = rng.uniform(0, 3, n)
    c, d, soc = st.fixed_schedule(load, hour, [10, 11, 12, 13, 14, 15], [18, 19, 20, 21, 22, 23],
                                  e_kwh=4.0, p_kw=1.0, eta=eta)
    assert math.fsum(d) == pytest.approx(eta * math.fsum(c) - soc[-1], abs=1e-9)
    assert (c <= 1.0 + 1e-12).all() and (c >= 0).all()
    assert (d <= np.minimum(1.0, load) + 1e-12).all() and (d >= 0).all()
    assert (soc <= 4.0 + 1e-9).all() and (soc >= -1e-12).all()
    assert not (c[np.isin(hour, [18, 19, 20, 21, 22, 23])] > 0).any()
    assert not (d[np.isin(hour, [10, 11, 12, 13, 14, 15])] > 0).any()


# --------------------------------------------------------------------------- connection cap


def test_charging_is_capped_by_the_site_connection():
    """Charge ≤ min(P, connection − load); the connection is the cluster's full-load power."""
    assert st.CONNECTION_KW == pytest.approx(2288 * 0.60 * 1.20)
    hour = np.array([0, 1, 2])
    load = np.array([9.5, 10.0, 4.0])  # headroom 0.5, 0 (full load): no charging at hour 1
    c, d, soc = st.fixed_schedule(load, hour, [0, 1], [2], e_kwh=5.0, p_kw=2.0, eta=0.8,
                                  conn_kw=10.0)
    assert c == pytest.approx([0.5, 0.0, 0.0])
    assert d == pytest.approx([0, 0, 0.4])
    c, d, soc = st.hindsight_heuristic(load, np.array([100.0, 100.0, 900.0]), np.zeros(3, int),
                                       e_kwh=5.0, p_kw=2.0, eta=0.8, conn_kw=10.0)
    assert c == pytest.approx([0.5, 0.0, 0.0], abs=1e-9)
    assert d == pytest.approx([0, 0, 0.4], abs=1e-9)


# --------------------------------------------------------------------------- strategy B


def test_hindsight_heuristic_toy_day_by_hand():
    ci = np.array([100.0, 500.0, 200.0, 600.0])
    load = np.full(4, 10.0)
    day = np.zeros(4, dtype=int)
    # E = 1: charge 1 kWh at hours 0 and 2 (0.5 stored each), deliver 1 at hour 3:
    # benefit 1 × 600 − (1 × 100 + 1 × 200) = 300
    c, d, soc = st.hindsight_heuristic(load, ci, day, e_kwh=1.0, p_kw=1.0, eta=0.5)
    assert math.fsum(ci * (d - c)) == pytest.approx(300.0)
    # E = 0.5: 0 -> 1 then 2 -> 3 (150 + 100 = 250) beats pairing the best pair first
    # (0 -> 3 alone, 200)
    c, d, soc = st.hindsight_heuristic(load, ci, day, e_kwh=0.5, p_kw=1.0, eta=0.5)
    assert math.fsum(ci * (d - c)) == pytest.approx(250.0)
    assert soc.max() <= 0.5 + 1e-9


def test_hindsight_heuristic_is_chronological():
    """Energy is discharged only after it was charged; the state of charge runs over the whole
    window from empty, and each day ends empty because leftovers are worth nothing."""
    # day 0: dirty then clean (nothing to do: no stored energy at the dirty hour);
    # day 1: clean then dirty, with the discharge capped by the load
    ci = np.array([600.0, 100.0, 100.0, 600.0])
    load = np.array([10.0, 10.0, 10.0, 0.2])
    day = np.array([0, 0, 1, 1])
    c, d, soc = st.hindsight_heuristic(load, ci, day, e_kwh=5.0, p_kw=1.0, eta=0.9)
    assert d == pytest.approx([0, 0, 0, 0.2], abs=1e-9)
    assert c == pytest.approx([0, 0, 0.2 / 0.9, 0], abs=1e-9)
    assert soc == pytest.approx(np.cumsum(0.9 * c - d), abs=1e-9)
    assert soc[1] == pytest.approx(0, abs=1e-9) and soc[-1] == pytest.approx(0, abs=1e-9)


@pytest.mark.parametrize("eta", [0.75, 0.85, 0.9])
def test_hindsight_heuristic_beats_the_fixed_schedule_each_day(eta):
    rng = np.random.default_rng(11)
    days = 10
    hour = np.tile(np.arange(24), days)
    day = np.repeat(np.arange(days), 24)
    ci = 400 - 150 * np.cos((hour - 13) / 24 * 2 * np.pi) + rng.normal(0, 40, 24 * days)
    load = rng.uniform(1, 3, 24 * days)
    kw = dict(e_kwh=3.0, p_kw=0.75, eta=eta, conn_kw=3.5)
    ca, da, sa = st.fixed_schedule(load, hour, [10, 11, 12, 13, 14, 15], [18, 19, 20, 21, 22, 23], **kw)
    cb, db, sb = st.hindsight_heuristic(load, ci, day, **kw)
    assert math.fsum(db) == pytest.approx(eta * math.fsum(cb) - sb[-1], abs=1e-6)
    assert (cb <= np.minimum(0.75, np.maximum(0, 3.5 - load)) + 1e-9).all()
    assert (db <= np.minimum(0.75, load) + 1e-9).all()
    assert (sb <= 3.0 + 1e-9).all() and (sb >= -1e-9).all()
    # fixed schedule A ends each day empty here (it discharges more than it stores), so its
    # day is a feasible plan for the heuristic's day
    assert (sa[hour == 23] <= 1e-12).all()
    for k in range(days):
        m = day == k
        assert math.fsum(ci[m] * (db[m] - cb[m])) >= math.fsum(ci[m] * (da[m] - ca[m])) - 1e-6


def test_zero_storage_changes_nothing():
    load = np.array([1.0, 2.0, 3.0])
    for c, d, soc in (st.fixed_schedule(load, np.arange(3), [0], [2], e_kwh=0, p_kw=0, eta=0.85),
                      st.hindsight_heuristic(load, np.array([1.0, 2.0, 3.0]), np.zeros(3, int),
                                             e_kwh=0, p_kw=0, eta=0.85)):
        assert not c.any() and not d.any() and not soc.any()


# --------------------------------------------------------------------------- outcomes


def test_outcome_counts_losses_in_the_charging_energy():
    load = np.array([2.0, 2.0])
    ci = np.array([100.0, 500.0])
    c, d = np.array([1.0, 0.0]), np.array([0.0, 0.85])
    o = st.outcome(load, ci, c, d, np.array([0.85, 0.0]))
    assert o["base_co2_kg"] == pytest.approx((2 * 100 + 2 * 500) / 1000)
    assert o["co2_kg"] == pytest.approx((3 * 100 + 1.15 * 500) / 1000)
    assert o["cut_kg"] == pytest.approx((0.85 * 500 - 100) / 1000)
    assert o["shifted_mwh"] == pytest.approx(0.85 / 1000)
    assert o["losses_mwh"] == pytest.approx(0.15 / 1000)
    assert o["terminal_soc_mwh"] == 0.0
    assert o["charge_ci_g_kwh"] == pytest.approx(100) and o["discharge_ci_g_kwh"] == pytest.approx(500)


def test_terminal_energy_is_valued_at_zero():
    """Energy still stored at the end: its charging CO₂ counts and nothing is credited."""
    load, ci = np.array([2.0, 2.0]), np.array([100.0, 500.0])
    c, d, soc = np.array([1.0, 0.0]), np.array([0.0, 0.0]), np.array([0.85, 0.85])
    o = st.outcome(load, ci, c, d, soc)
    assert o["cut_kg"] == pytest.approx(-0.1) and o["terminal_soc_mwh"] == pytest.approx(0.00085)
    assert o["losses_mwh"] == pytest.approx(0.00015)


def test_import_view_and_rebound():
    hour = np.array([0, 1, 0, 1])
    load = np.array([1000.0, 2000.0, 1000.0, 2000.0])
    c = np.array([500.0, 0, 500.0, 0])
    d = np.array([0, 400.0, 0, 400.0])
    rush = np.array([False, True, False, True])
    v = st.import_view(load, c, d, hour, rush, [0])
    assert v["before_by_hour_mw"][:2] == pytest.approx([1.0, 2.0])
    assert v["after_by_hour_mw"][:2] == pytest.approx([1.5, 1.6])
    assert v["rush_before_mw"] == pytest.approx(2.0) and v["rush_after_mw"] == pytest.approx(1.6)
    assert v["peak_before_mw"] == pytest.approx(2.0) and v["peak_after_mw"] == pytest.approx(1.6)
    assert v["rebound_mw"] == pytest.approx(0.5)


# --------------------------------------------------------------------------- rush, relief


def test_rush_threshold_is_training_only():
    ts = pl.datetime_range(VAL_HISTORY_START, VAL_HISTORY_START + timedelta(hours=100), "1h",
                           time_unit="us", time_zone="UTC", eager=True, closed="left")
    df = pl.DataFrame({"ts_utc": ts, "value": [float(i) for i in range(100)]})
    assert st.rush_threshold(df, 0.99) == pytest.approx(98.01)
    late = df.with_columns(pl.col("ts_utc") + (VAL_FIT_AT - VAL_HISTORY_START))
    with pytest.raises(ValueError, match="training"):
        st.rush_threshold(late)


def test_peak_relief_by_site():
    rush = np.array([True, False, True])
    loads = {"U": {"PACE": np.array([1000.0, 1000.0, 3000.0]), "BPAT": np.zeros(3)},
             "W": {"PACE": np.array([500.0, 1000.0, 1500.0]), "BPAT": np.array([500.0, 0, 1500])}}
    r = st.peak_relief(loads, rush, peak_idx=2)
    assert r["W"]["PACE"]["rush_mean_mw"] == pytest.approx(1.0)
    assert r["W"]["PACE"]["rush_change_vs_U_mw"] == pytest.approx(-1.0)
    assert r["W"]["PACE"]["at_peak_change_vs_U_mw"] == pytest.approx(-1.5)
    assert r["W"]["BPAT"]["rush_change_vs_U_mw"] == pytest.approx(1.0)
    assert r["U"]["PACE"]["rush_change_vs_U_mw"] == 0


# --------------------------------------------------------------------------- seal


def test_window_refuses_the_sealed_year():
    with pytest.raises(ValueError, match="seal"):
        st.cohort_window(datetime(2025, 10, 1, tzinfo=UTC), TEST_START + timedelta(minutes=1))


def test_window_covers_the_cohort_to_its_last_hour():
    s, e = st.cohort_window(datetime(2024, 11, 1, tzinfo=UTC),
                            datetime(2025, 10, 17, 17, 37, 20, tzinfo=UTC))
    assert s == datetime(2024, 11, 1, tzinfo=UTC) and e == datetime(2025, 10, 17, 18, tzinfo=UTC)


def test_storage_module_reads_only_through_pre_seal_loaders():
    """No direct parquet scans or unseal paths in the storage code (F8)."""
    for p in (Path(st.__file__),
              Path(__file__).resolve().parents[1] / "scripts" / "export_storage.py"):
        tree = ast.parse(p.read_text())
        names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | \
                {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        assert "scan_parquet" not in names, p.name
        assert not any("unseal" in x.lower() for x in names), p.name
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                assert "carbon_hourly" not in n.value and "balance.parquet" not in n.value, p.name
