"""F14.6 scoring truth fill: tier order, the 7-day same-hour tier, the mask, the seal."""

from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl
import pytest

from gridpilot.carbon import EF_G_KWH, LB_TO_G, fuel_mix_ci
from gridpilot.data.truth_fill import (
    TIER_EVIDENCE,
    fill_mask,
    fill_truth,
    tier_counts,
)
from gridpilot.eval import TruthTable
from gridpilot.splits import TEST_START

H = timedelta(hours=1)
T0 = datetime(2024, 11, 10, tzinfo=UTC)


def _hours(start, n):
    return [start + k * H for k in range(n)]


def _carbon(ba, start, cons, gen):
    n = len(cons)
    return pl.DataFrame({
        "ba": [ba] * n, "ts_utc": _hours(start, n),
        "ci_consumed_g_kwh": cons, "ci_generated_g_kwh": gen,
    }, schema={"ba": pl.Utf8, "ts_utc": pl.Datetime("us", "UTC"),
               "ci_consumed_g_kwh": pl.Float64, "ci_generated_g_kwh": pl.Float64})


def _fuel(ba, start, vals):
    return pl.DataFrame({"ba": [ba] * len(vals), "ts_utc": _hours(start, len(vals)),
                         "ci_g_kwh": vals},
                        schema={"ba": pl.Utf8, "ts_utc": pl.Datetime("us", "UTC"),
                                "ci_g_kwh": pl.Float64})


def _history(ba="PACE", days=9, base=100.0):
    """`days` of hourly data ending at T0 + 2 days; tier-1 value = base + day index."""
    start = T0 - timedelta(days=days - 2)
    n = days * 24
    cons = [base + (k // 24) for k in range(n)]
    gen = [500.0] * n
    return start, cons, gen


def _at(frame, ba, ts):
    r = frame.filter((pl.col("ba") == ba) & (pl.col("ts_utc") == ts))
    assert r.height == 1
    return r.row(0, named=True)


def test_tier1_when_consumed_present():
    start, cons, gen = _history()
    out = fill_truth(T0, T0 + 24 * H, ["PACE"], carbon=_carbon("PACE", start, cons, gen),
                     fuel_ci=_fuel("PACE", start, [9.0] * len(cons)))
    assert out.columns == ["ba", "ts_utc", "ci_g_kwh", "tier"]
    assert out.height == 24
    assert out["tier"].unique().to_list() == [1]
    r = _at(out, "PACE", T0 + 3 * H)
    assert r["ci_g_kwh"] == cons[(T0 + 3 * H - start) // H]


def test_tier2_production_basis_same_hour():
    start, cons, gen = _history()
    i = (T0 + 5 * H - start) // H
    cons[i] = None
    gen[i] = 432.1
    out = fill_truth(T0, T0 + 24 * H, ["PACE"], carbon=_carbon("PACE", start, cons, gen),
                     fuel_ci=_fuel("PACE", start, [9.0] * len(cons)))
    r = _at(out, "PACE", T0 + 5 * H)
    assert (r["tier"], r["ci_g_kwh"]) == (2, 432.1)


def test_tier3_fuel_mix_same_hour():
    start, cons, gen = _history()
    i = (T0 + 6 * H - start) // H
    cons[i] = gen[i] = None
    fuel = [9.0] * len(cons)
    fuel[i] = 321.0
    out = fill_truth(T0, T0 + 24 * H, ["PACE"], carbon=_carbon("PACE", start, cons, gen),
                     fuel_ci=_fuel("PACE", start, fuel))
    r = _at(out, "PACE", T0 + 6 * H)
    assert (r["tier"], r["ci_g_kwh"]) == (3, 321.0)


def test_tier4_mean_of_tier1_same_utc_hour_previous_7_days():
    start, cons, gen = _history(days=10)
    h = T0 + 7 * H
    i = (h - start) // H
    cons[i] = gen[i] = None
    # Day h-2d is not tier 1 (only a production value): it must not enter the mean.
    j = i - 2 * 24
    cons[j] = None
    # Day h-8d is outside the 7 preceding days: a huge value there must not count.
    cons[i - 8 * 24] = 1e6
    fuel = [9.0] * len(cons)
    fuel[i] = None
    out = fill_truth(T0, T0 + 24 * H, ["PACE"], carbon=_carbon("PACE", start, cons, gen),
                     fuel_ci=_fuel("PACE", start, fuel))
    r = _at(out, "PACE", h)
    want = np.mean([cons[i - 24 * k] for k in range(1, 8) if k != 2])
    assert r["tier"] == 4
    assert r["ci_g_kwh"] == pytest.approx(want, abs=1e-12)


def test_tier4_looks_before_window_start():
    start, cons, gen = _history(days=10)
    i = (T0 - start) // H  # the first hour of the window
    cons[i] = gen[i] = None
    fuel = [9.0] * len(cons)
    fuel[i] = None
    out = fill_truth(T0, T0 + 24 * H, ["PACE"], carbon=_carbon("PACE", start, cons, gen),
                     fuel_ci=_fuel("PACE", start, fuel))
    r = _at(out, "PACE", T0)
    assert r["tier"] == 4
    assert r["ci_g_kwh"] == pytest.approx(np.mean([cons[i - 24 * k] for k in range(1, 8)]))


def test_still_missing_after_tier4_is_null_and_closed():
    # A whole week (plus the hour) with no tier-1 value and no fills: nothing to use.
    start = T0 - 8 * 24 * H
    n = 10 * 24
    cons = [None] * n
    gen = [None] * n
    out = fill_truth(T0, T0 + 2 * H, ["NEVP"], carbon=_carbon("NEVP", start, cons, gen),
                     fuel_ci=_fuel("NEVP", start, [None] * n))
    assert out.height == 2
    assert out["ci_g_kwh"].null_count() == 2
    assert out["tier"].null_count() == 2
    m = fill_mask(out)
    assert m.columns == ["ba", "ts_utc", "truth_ok"]
    assert not m["truth_ok"].any()


def test_absent_rows_and_absent_ba_give_a_full_grid():
    start, cons, gen = _history()
    c = _carbon("PACE", start, cons, gen).filter(pl.col("ts_utc") != T0 + 2 * H)
    out = fill_truth(T0, T0 + 24 * H, ["PACE", "BPAT"], carbon=c,
                     fuel_ci=_fuel("PACE", start, [None] * len(cons)))
    assert out.height == 48
    assert _at(out, "PACE", T0 + 2 * H)["tier"] == 4
    assert out.filter(pl.col("ba") == "BPAT")["tier"].null_count() == 24
    assert out.sort("ba", "ts_utc").equals(out)


def test_seal_raises():
    start, cons, gen = _history()
    c = _carbon("PACE", start, cons, gen)
    f = _fuel("PACE", start, [1.0] * len(cons))
    with pytest.raises(ValueError, match="TEST_START"):
        fill_truth(TEST_START - H, TEST_START + H, ["PACE"], carbon=c, fuel_ci=f)
    with pytest.raises(ValueError, match="TEST_START"):
        fill_truth(TEST_START, TEST_START + H, ["PACE"], carbon=c, fuel_ci=f)
    # Ending exactly at TEST_START is allowed (half-open).
    fill_truth(TEST_START - H, TEST_START, ["PACE"], carbon=c, fuel_ci=f)


def test_sealed_input_rows_raise():
    c = _carbon("PACE", TEST_START - H, [1.0, 2.0], [1.0, 2.0])
    with pytest.raises(ValueError, match="sealed"):
        fill_truth(TEST_START - 2 * H, TEST_START, ["PACE"], carbon=c,
                   fuel_ci=_fuel("PACE", TEST_START - H, [1.0]))


def test_window_must_be_aware_and_hour_aligned():
    start, cons, gen = _history()
    c, f = _carbon("PACE", start, cons, gen), _fuel("PACE", start, [1.0] * len(cons))
    with pytest.raises(ValueError):
        fill_truth(datetime(2024, 11, 10), T0 + H, ["PACE"], carbon=c, fuel_ci=f)
    with pytest.raises(ValueError):
        fill_truth(T0 + timedelta(minutes=5), T0 + H, ["PACE"], carbon=c, fuel_ci=f)
    with pytest.raises(ValueError):
        fill_truth(T0 + H, T0, ["PACE"], carbon=c, fuel_ci=f)


def test_tier_counts_and_evidence():
    start, cons, gen = _history(days=10)
    i = (T0 + 1 * H - start) // H
    cons[i] = None  # tier 2
    out = fill_truth(T0, T0 + 4 * H, ["PACE", "NEVP"], carbon=_carbon("PACE", start, cons, gen),
                     fuel_ci=_fuel("PACE", start, [None] * len(cons)))
    tc = tier_counts(out)
    assert tc["PACE"] == {"1": 3, "2": 1, "3": 0, "4": 0, "missing": 0}
    assert tc["NEVP"] == {"1": 0, "2": 0, "3": 0, "4": 0, "missing": 4}
    assert TIER_EVIDENCE == {1: "modeled", 2: "modeled", 3: "modeled", 4: "modeled"}


def test_truth_table_accepts_fill_and_its_mask():
    start, cons, gen = _history(days=10)
    i = (T0 + 1 * H - start) // H
    cons[i] = None
    out = fill_truth(T0, T0 + 4 * H, ["PACE"], carbon=_carbon("PACE", start, cons, gen),
                     fuel_ci=_fuel("PACE", start, [None] * len(cons)))
    tt = TruthTable(out, fill_mask(out))
    s = int((T0 - datetime(1970, 1, 1, tzinfo=UTC)) / timedelta(microseconds=1))
    val, miss = tt.integral("PACE", np.array([s]), np.array([s + 4 * 3600 * 10**6]))
    assert not miss[0]
    assert val[0] == pytest.approx(sum(out["ci_g_kwh"].to_list()))
    assert tt.filled_hours("PACE", np.array([s]), np.array([s + 4 * 3600 * 10**6]))[0] == 1


def test_fuel_mix_ci_formula():
    cols = {f"gen_{f}_adj_mw": [0.0] for f in (
        "coal", "gas", "oil", "nuclear", "hydro", "solar", "wind", "geothermal", "battery",
        "other_storage", "unknown_storage", "other", "unknown")}
    cols["gen_coal_adj_mw"] = [100.0]
    cols["gen_gas_adj_mw"] = [300.0]
    cols["gen_wind_adj_mw"] = [600.0]
    cols["gen_battery_adj_mw"] = [-50.0]  # charging: counted in the total, never emits
    df = pl.DataFrame(cols)
    got = df.select(fuel_mix_ci().alias("ci"))["ci"][0]
    want = (100 * 2.31 + 300 * 0.96) * LB_TO_G / 950.0
    assert got == pytest.approx(want)
    assert EF_G_KWH["coal"] == pytest.approx(2.31 * 453.592)
    none = pl.DataFrame({c: [None] for c in cols}, schema={c: pl.Float64 for c in cols})
    assert none.select(fuel_mix_ci().alias("ci"))["ci"][0] is None
