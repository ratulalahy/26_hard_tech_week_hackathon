"""Grid-profile export for the dashboard (Task 8 amendment): typical-day carbon, Utah's July
weekday load, the month x hour heatmap and the top-100 net-load hours. Validation year only."""

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from gridpilot import grid_profile as gp
from gridpilot.data.eia930 import PARTITION_FUELS
from gridpilot.results import sealed_timestamps, unenveloped_numbers

H = timedelta(hours=1)


def _carbon(rows):
    return pl.DataFrame(rows, schema={"ba": pl.Utf8, "ts_utc": pl.Datetime("us", "UTC"),
                                      "ci_consumed_g_kwh": pl.Float64}, orient="row")


def _balance(start, hours, ba="PACE", demand=5000.0, solar=0.0, wind=0.0, coal=1000.0):
    ts = [start + i * H for i in range(hours)]
    n = len(ts)
    cols = {"ba": [ba] * n, "ts_utc": ts,
            "demand_adj_mw": [demand(t) if callable(demand) else demand for t in ts],
            "gen_solar_adj_mw": [solar(t) if callable(solar) else solar for t in ts],
            "gen_wind_adj_mw": [wind] * n}
    for f in PARTITION_FUELS:
        name = f"gen_{f}_adj_mw"
        if name not in cols:
            cols[name] = [coal if f == "coal" else 0.0] * n
    df = pl.DataFrame(cols).with_columns(
        pl.col("ts_utc").dt.replace_time_zone("UTC").dt.cast_time_unit("us"))
    return df.with_columns([pl.col(c).cast(pl.Float32) for c in df.columns
                            if c.endswith("_mw")])


# --------------------------------------------------------------------------- window and months


def test_window_is_the_validation_year_before_F():
    s, e = gp.WINDOW
    assert s == datetime(2024, 11, 1, tzinfo=UTC)
    assert e == datetime(2025, 10, 24, tzinfo=UTC)
    assert gp.MONTHS[0] == "2024-11" and gp.MONTHS[-1] == "2025-10" and len(gp.MONTHS) == 12


# --------------------------------------------------------------------------- typical days


def test_typical_day_by_month_uses_denver_hours_and_skips_nulls():
    # 2025-01-15 19:00Z is 12:00 MST; 2025-07-15 18:00Z is 12:00 MDT.
    c = _carbon([
        ("PACE", datetime(2025, 1, 15, 19, tzinfo=UTC), 400.0),
        ("PACE", datetime(2025, 1, 16, 19, tzinfo=UTC), 600.0),
        ("PACE", datetime(2025, 1, 17, 19, tzinfo=UTC), None),   # not tier 1: skipped
        ("PACE", datetime(2025, 7, 15, 18, tzinfo=UTC), 300.0),
        ("BPAT", datetime(2025, 1, 15, 19, tzinfo=UTC), 50.0),
    ])
    vals, counts = gp.typical_day_by_month(c, "PACE")
    jan, jul = gp.MONTHS.index("2025-01"), gp.MONTHS.index("2025-07")
    assert vals[jan][12] == pytest.approx(500.0)
    assert counts[jan][12] == 2
    assert vals[jul][12] == pytest.approx(300.0)
    assert vals[jan][13] is None and counts[jan][13] == 0
    assert len(vals) == 12 and all(len(r) == 24 for r in vals)


def test_day_profile_is_the_hourly_mean_over_all_days():
    c = _carbon([("PACE", datetime(2025, 1, 15, 19, tzinfo=UTC), 400.0),
                 ("PACE", datetime(2025, 7, 15, 18, tzinfo=UTC), 200.0)])
    day, n = gp.day_profile(c, "PACE")
    assert day[12] == pytest.approx(300.0) and n[12] == 2
    assert day[0] is None


# --------------------------------------------------------------------------- Utah load


def test_july_weekday_profile_excludes_weekends_and_nets_out_solar_and_wind():
    # July 2025 local; 2025-07-05/06 are Sat/Sun. Weekend demand is huge so a leak shows.
    start = datetime(2025, 7, 1, 6, tzinfo=UTC)  # 00:00 MDT on Tue 1 July

    def demand(t):
        return 99999.0 if t.astimezone(gp.TZ).weekday() >= 5 else 5000.0

    b = _balance(start, 24 * 31, demand=demand, solar=1000.0, wind=500.0)
    p = gp.july_weekday_profile(b)
    assert p["n_days"] == 23
    assert p["demand_mw"][12] == pytest.approx(5000.0)
    assert p["net_load_mw"][12] == pytest.approx(3500.0)
    assert p["solar_mw"][12] == pytest.approx(1000.0)


def test_top_k_net_load_counts_sum_to_k_and_land_in_the_right_cells():
    start = datetime(2025, 1, 1, 7, tzinfo=UTC)  # 00:00 MST

    def demand(t):  # a smooth evening hump peaking at 20:00 in January, flat otherwise
        lt = t.astimezone(gp.TZ)  # (an isolated one-hour spike would be cleaned away)
        hump = 300.0 * max(0, 3 - abs(lt.hour - 20)) if lt.month == 1 else 0.0
        return 4000.0 + lt.day * 0.1 + hump

    b = _balance(start, 24 * 59, demand=demand)
    counts = gp.top_k_net_load_counts(b, k=10)
    assert sum(map(sum, counts)) == 10
    assert counts[gp.MONTHS.index("2025-01")][20] == 10


# --------------------------------------------------------------------------- the artifact


def _inputs():
    s, _ = gp.WINDOW
    hours = 24 * 357  # to F (2025-10-24)
    rows = []
    for ba, base in (("PACE", 600.0), ("BPAT", 80.0), ("CISO", 200.0), ("NEVP", 320.0)):
        for i in range(0, hours, 5):
            rows.append((ba, s + i * H, base + (i % 24)))
    carbon = _carbon(rows)
    bal = pl.concat([_balance(s, hours, ba="PACE", demand=lambda t: 4000.0 + t.hour * 10,
                              solar=lambda t: max(0.0, 800.0 - abs(t.hour - 19) * 120)),
                     _balance(s, hours, ba="AZPS", coal=800.0)])
    return carbon, bal


def test_build_profile_is_fully_enveloped_and_pre_seal():
    carbon, bal = _inputs()
    prof = gp.build_profile(carbon, bal)
    assert unenveloped_numbers(prof) == []
    assert sealed_timestamps(prof) == []
    assert set(prof["ci"]["by_ba"]) == {"PACE", "BPAT", "CISO", "NEVP"}
    pace = prof["ci"]["by_ba"]["PACE"]
    assert pace["month_hour"]["evidence"] == "observed"
    assert len(pace["month_hour"]["value"]) == 12
    assert prof["pace_july_weekday"]["net_load_mw"]["evidence"] == "observed"
    assert sum(map(sum, prof["pace_top100_net_load"]["counts_month_hour"]["value"])) == 100
    ctx = prof["context_year_mean_ci"]["by_ba"]
    assert "AZPS" in ctx and ctx["AZPS"]["evidence"] == "modeled"
    assert "PACE" not in ctx  # core BAs use the observed consumption basis only


def test_build_profile_drops_rows_outside_the_window():
    carbon, bal = _inputs()
    late = _carbon([("PACE", datetime(2025, 10, 30, 12, tzinfo=UTC), 99999.0)])
    prof = gp.build_profile(pl.concat([carbon, late]), bal)
    flat = [v for row in prof["ci"]["by_ba"]["PACE"]["month_hour"]["value"] for v in row
            if v is not None]
    assert max(flat) < 99999.0


def test_build_profile_refuses_sealed_rows():
    carbon, bal = _inputs()
    sealed = _carbon([("PACE", datetime(2025, 11, 1, 0, tzinfo=UTC), 500.0)])
    with pytest.raises(ValueError, match="sealed"):
        gp.build_profile(pl.concat([carbon, sealed]), bal)


def test_window_cannot_reach_the_seal():
    with pytest.raises(ValueError, match="seal"):
        gp.check_window(datetime(2024, 11, 1, tzinfo=UTC), datetime(2025, 11, 2, tzinfo=UTC))
