"""Stage 3 T16 (D-066): "Utah's toughest grid days". The pre-registered day rule (top 3
validation days by PACE daily maximum net load; ties to the earlier date) and the day-sliced
accounting, on hand-checked toy data."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta

import numpy as np
import polars as pl
import pytest

from gridpilot import case_days as cd
from gridpilot.sim.power import GPU_KW, PUE, TRANSFER_FRACTION
from gridpilot.splits import TEST_START

RATE = GPU_KW * PUE


def _net(rows: list[tuple[datetime, float | None]]) -> pl.DataFrame:
    return pl.DataFrame({"ts_utc": [r[0] for r in rows], "value": [r[1] for r in rows]},
                        schema={"ts_utc": pl.Datetime("us", "UTC"), "value": pl.Float64})


def _day_hours(d: date) -> list[datetime]:
    t0, n = cd.local_day_utc(d)
    return [t0 + timedelta(hours=k) for k in range(n)]


def _flat_day(d: date, base: float, peak: float | None = None, at: int = 20):
    """A local day of `base` MW with `peak` at local hour index `at` (America/Denver)."""
    hs = _day_hours(d)
    return [(t, peak if (peak is not None and i == at) else base) for i, t in enumerate(hs)]


# --------------------------------------------------------------------------- calendar


def test_local_day_is_the_denver_calendar_day_with_dst():
    t0, n = cd.local_day_utc(date(2025, 7, 8))
    assert t0 == datetime(2025, 7, 8, 6, tzinfo=UTC) and n == 24  # MDT
    t0, n = cd.local_day_utc(date(2025, 1, 15))
    assert t0 == datetime(2025, 1, 15, 7, tzinfo=UTC) and n == 24  # MST
    assert cd.local_day_utc(date(2025, 3, 9))[1] == 23  # spring forward
    assert cd.local_day_utc(date(2024, 11, 3))[1] == 25  # fall back


def test_local_day_refuses_days_outside_the_validation_window():
    with pytest.raises(ValueError, match="validation"):
        cd.local_day_utc(date(2024, 10, 31))
    with pytest.raises(ValueError, match="validation"):
        cd.local_day_utc(date(2025, 10, 24))
    with pytest.raises(ValueError, match="validation"):
        cd.local_day_utc(date(2025, 11, 2))


# --------------------------------------------------------------------------- the day rule


def test_daily_max_groups_by_denver_date_and_keeps_the_window():
    rows = (_flat_day(date(2024, 11, 1), 100.0, 900.0, at=3)
            + _flat_day(date(2025, 10, 23), 100.0, 800.0)
            # outside the validation days (local dates): never counted
            + [(datetime(2024, 11, 1, 5, tzinfo=UTC), 5000.0),  # Oct 31, 23:00 MDT
               (datetime(2025, 10, 24, 6, tzinfo=UTC), 6000.0)])  # Oct 24, 00:00 MDT
    daily = cd.daily_max(_net(rows))
    assert daily["date"].to_list() == [date(2024, 11, 1), date(2025, 10, 23)]
    assert daily["max_mw"].to_list() == [900.0, 800.0]
    assert daily["peak_hour_local"].to_list() == [3, 20]
    assert daily["n_hours"].to_list() == [24, 24]  # the out-of-window hours are not counted


def test_daily_max_counts_dst_hours_and_ignores_nulls():
    rows = _flat_day(date(2024, 11, 3), 100.0, 700.0, at=1)  # 25 hours; index 1 = 01:00 MDT
    rows[5] = (rows[5][0], None)
    daily = cd.daily_max(_net(rows))
    r = daily.row(0, named=True)
    assert r["n_hours"] == 25 and r["n_null"] == 1 and r["max_mw"] == 700.0
    assert r["peak_hour_local"] == 1


def test_daily_max_peak_hour_tie_goes_to_the_earlier_hour():
    rows = _flat_day(date(2025, 7, 8), 100.0)
    rows[19] = (rows[19][0], 500.0)
    rows[21] = (rows[21][0], 500.0)
    r = cd.daily_max(_net(rows)).row(0, named=True)
    assert r["peak_hour_local"] == 19
    assert r["peak_ts_utc"] == rows[19][0]


def test_select_top3_by_daily_max_ties_go_to_the_earlier_date():
    days = {date(2025, 7, 8): 8000.0, date(2025, 7, 16): 7600.0, date(2025, 9, 2): 7600.0,
            date(2025, 6, 1): 7600.0, date(2025, 1, 5): 3000.0}
    rows = [x for d, v in days.items() for x in _flat_day(d, 1000.0, v)]
    top = cd.select_days(cd.daily_max(_net(rows)))
    assert top["date"].to_list() == [date(2025, 7, 8), date(2025, 6, 1), date(2025, 7, 16)]
    assert top["rank"].to_list() == [1, 2, 3]


def test_the_rule_is_deterministic_under_row_order():
    rng = np.random.default_rng(66)
    days = [date(2024, 11, 1) + timedelta(days=int(k)) for k in range(0, 350, 7)]
    vals = rng.choice([5000.0, 6000.0, 7000.0], len(days))  # many ties
    rows = [x for d, v in zip(days, vals, strict=True) for x in _flat_day(d, 100.0, float(v))]
    want = cd.select_days(cd.daily_max(_net(rows)))
    for seed in range(5):
        perm = np.random.default_rng(seed).permutation(len(rows))
        got = cd.select_days(cd.daily_max(_net([rows[i] for i in perm])))
        assert got.equals(want)
    # the earliest of the 7000 MW days wins every rank in order
    tops = sorted(d for d, v in zip(days, vals, strict=True) if v == 7000.0)[:3]
    assert want["date"].to_list() == tops


def test_the_rule_refuses_sealed_rows():
    rows = _flat_day(date(2025, 7, 8), 100.0) + [(TEST_START, 1.0)]
    with pytest.raises(ValueError, match="seal"):
        cd.daily_max(_net(rows))


def test_the_rule_constants_are_the_pre_registered_ones():
    assert cd.K == 3
    assert (cd.DAY_START, cd.DAY_END) == (date(2024, 11, 1), date(2025, 10, 24))
    assert "earlier date" in cd.RULE and "D-066" in cd.RULE


# --------------------------------------------------------------------------- day accounting


def _ledger(rows):
    """rows: (job_uid, site, start, end, gpus, arrival, duration_s)."""
    return pl.DataFrame(
        {"job_uid": [r[0] for r in rows], "site": [r[1] for r in rows],
         "start_ts": [r[2] for r in rows], "end_ts": [r[3] for r in rows],
         "gpus": [r[4] for r in rows], "arrival_ts": [r[5] for r in rows],
         "duration_s": [r[6] for r in rows]},
        schema={"job_uid": pl.Utf8, "site": pl.Utf8, "start_ts": pl.Datetime("us", "UTC"),
                "end_ts": pl.Datetime("us", "UTC"), "gpus": pl.Int64,
                "arrival_ts": pl.Datetime("us", "UTC"), "duration_s": pl.Float64})


D = date(2025, 7, 8)
T0 = datetime(2025, 7, 8, 6, tzinfo=UTC)  # local midnight (MDT)


def test_day_load_slices_a_job_that_spans_local_midnight():
    led = _ledger([("a", "PACE", T0 - timedelta(hours=1), T0 + timedelta(hours=2), 10,
                    T0 - timedelta(hours=1), 3 * 3600.0)])
    load = cd.day_load_kwh(led, "PACE", D)
    assert load.shape == (24,)
    assert load[:3] == pytest.approx([10 * RATE, 10 * RATE, 0.0])
    assert load.sum() == pytest.approx(20 * RATE)  # the hour before midnight is another day


def test_day_co2_counts_execution_by_hour_and_transfer_at_arrival():
    ci = {s: np.full(24, 100.0) for s in ("PACE", "BPAT", "CISO", "NEVP")}
    ci["BPAT"][:] = 20.0
    ci["PACE"][2] = 500.0
    led = _ledger([
        # local: 01:00-03:00 in Utah; the 02:00 hour is dirty
        ("u", "PACE", T0 + timedelta(hours=1), T0 + timedelta(hours=3), 4,
         T0 + timedelta(hours=1), 7200.0),
        # moved to BPAT, arrives 05:30 local, runs 06:00-07:00
        ("m", "BPAT", T0 + timedelta(hours=6), T0 + timedelta(hours=7), 8,
         T0 + timedelta(hours=5, minutes=30), 3600.0),
        # moved, arrived the day before: its transfer belongs to that day
        ("p", "BPAT", T0, T0 + timedelta(hours=1), 2, T0 - timedelta(hours=2), 3600.0),
    ])
    got = cd.day_co2(led, D, ci)
    exec_kg = (4 * RATE * (100.0 + 500.0) + 8 * RATE * 20.0 + 2 * RATE * 20.0) / 1000
    tr_kwh = TRANSFER_FRACTION * 8 * GPU_KW * 1.0 * PUE
    tr_kg = 0.5 * tr_kwh * (ci["PACE"][5] + ci["BPAT"][5]) / 1000
    assert got["execution_kg"] == pytest.approx(exec_kg, rel=1e-12)
    assert got["transfer_kg"] == pytest.approx(tr_kg, rel=1e-12)
    assert got["total_kg"] == pytest.approx(exec_kg + tr_kg, rel=1e-12)
    assert got["energy_mwh_by_site"]["BPAT"] == pytest.approx((8 + 2) * RATE / 1000)
    assert got["energy_mwh_by_site"]["PACE"] == pytest.approx(2 * 4 * RATE / 1000)
    assert got["energy_mwh_by_site"]["CISO"] == 0.0


def test_peak_hour_change_reads_the_cluster_load_at_that_hour():
    u = _ledger([("a", "PACE", T0 + timedelta(hours=20), T0 + timedelta(hours=21), 100,
                  T0 + timedelta(hours=20), 3600.0)])
    s = _ledger([("a", "BPAT", T0 + timedelta(hours=20), T0 + timedelta(hours=21), 100,
                  T0 + timedelta(hours=19, minutes=30), 3600.0)])
    lu, ls = cd.day_load_kwh(u, "PACE", D), cd.day_load_kwh(s, "PACE", D)
    assert lu[20] / 1000 == pytest.approx(100 * RATE / 1000)
    assert ls[20] == 0.0


# --------------------------------------------------------------------------- weather (descriptive)


def test_degree_days_and_fahrenheit():
    assert cd.c_to_f(100.0) == pytest.approx(212.0)
    assert cd.c_to_f(-40.0) == pytest.approx(-40.0)
    # mean of max and min, base 65 °F
    assert cd.degree_days(100.0, 70.0) == (pytest.approx(20.0), 0.0)
    assert cd.degree_days(40.0, 20.0) == (0.0, pytest.approx(35.0))
    assert cd.degree_days(70.0, 60.0) == (0.0, 0.0)


def test_day_weather_uses_the_valid_instants_of_the_local_day():
    t0 = T0  # 00:00 MDT
    vt = [t0 + timedelta(hours=k) for k in range(-2, 26)]
    temp = [50.0 if (t < t0 or t >= t0 + timedelta(hours=24)) else 20.0 + (k % 24) * 0.5
            for k, t in enumerate(vt)]
    frame = pl.DataFrame({"valid_time_utc": vt, "temperature_2m": temp},
                         schema={"valid_time_utc": pl.Datetime("us", "UTC"),
                                 "temperature_2m": pl.Float32})
    w = cd.day_weather(frame, D)
    assert w["n"] == 24
    inside = [x for t, x in zip(vt, temp, strict=True) if t0 <= t < t0 + timedelta(hours=24)]
    assert w["tmax_f"] == pytest.approx(cd.c_to_f(max(inside)), abs=1e-4)
    assert w["tmin_f"] == pytest.approx(cd.c_to_f(min(inside)), abs=1e-4)
    assert not math.isnan(w["cdd"]) and not math.isnan(w["hdd"])
