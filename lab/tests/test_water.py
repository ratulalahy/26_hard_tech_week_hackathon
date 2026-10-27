"""Stage 3 T14 (D-063): the water accounting. Hand-checked fuel-mix intensities, the missing-hour
rule and its fill, policy water on the carbon accounting's exact hourly energy (execution at the
site, transfer half at home and half at the destination), direct cooling, and the seal."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from gridpilot import water as wa
from gridpilot.data.water_factors import L_PER_GAL
from gridpilot.sim.power import GPU_KW, PUE, TRANSFER_FRACTION
from gridpilot.splits import TEST_START

T0 = datetime(2025, 3, 3, 7, tzinfo=UTC)
FUELS = wa.FUEL_COLS


def _bal(rows):
    """rows: (ba, hour offset, {fuel: MW}); a fuel not named is null."""
    data = {"ba": [], "ts_utc": [], **{f"gen_{f}_adj_mw": [] for f in FUELS}}
    for ba, h, mix in rows:
        data["ba"].append(ba)
        data["ts_utc"].append(T0 + timedelta(hours=h))
        for f in FUELS:
            data[f"gen_{f}_adj_mw"].append(mix.get(f))
    return pl.DataFrame(data, schema={"ba": pl.Utf8, "ts_utc": pl.Datetime("us", "UTC"),
                                      **{f"gen_{f}_adj_mw": pl.Float64 for f in FUELS}})


def _row(fr, ba, h):
    return fr.filter((pl.col("ba") == ba) & (pl.col("ts_utc") == T0 + timedelta(hours=h))).row(
        0, named=True)


# --------------------------------------------------------------------------- intensity


def test_intensity_is_the_generation_weighted_factor_with_hydro_separate():
    fr = wa.intensity(_bal([("PACE", 0, {"coal": 50, "gas": 25, "hydro_conv": 25, "wind": 0})]))
    r = _row(fr, "PACE", 0)
    assert r["ex_hydro"] == pytest.approx((50 * 687 + 25 * 198) / 100)
    assert r["hydro"] == pytest.approx(25 * 4491 / 100)
    assert r["gen_mw"] == pytest.approx(100)
    assert r["missing"] is False


def test_negative_generation_is_clipped_and_other_takes_the_mix_average():
    fr = wa.intensity(_bal([("CISO", 0, {"gas": 60, "solar": -10, "battery": 40, "other": -50,
                                         "nuclear": 0}),
                            ("CISO", 1, {"gas": 60, "solar": 0, "battery": 40, "other": 900,
                                         "nuclear": 0})]))
    for h in (0, 1):  # solar's -10 and other's MW (either sign) never enter the shares
        r = _row(fr, "CISO", h)
        assert r["gen_mw"] == pytest.approx(100)
        assert r["ex_hydro"] == pytest.approx(60 * 198 / 100)  # battery: in the shares, no water
        assert r["hydro"] == 0


def test_a_regularly_reported_fuel_missing_makes_the_hour_missing_a_rare_one_is_zero():
    rows = [("BPAT", h, {"gas": 10, "nuclear": 10, "hydro_conv": 80}) for h in range(20)]
    rows[5] = ("BPAT", 5, {"gas": 10, "hydro_conv": 80})  # nuclear (always reported) is null
    rows[6] = ("BPAT", 6, {"gas": 10, "nuclear": 10, "hydro_conv": 80, "battery": 100})
    rows[7] = ("BPAT", 7, {})  # nothing reported
    fr = wa.intensity(_bal(rows))
    assert _row(fr, "BPAT", 5)["missing"] is True
    assert _row(fr, "BPAT", 7)["missing"] is True
    r6 = _row(fr, "BPAT", 6)  # battery reported in 1 of 20 hours: null elsewhere means 0
    assert r6["missing"] is False and r6["gen_mw"] == pytest.approx(200)
    assert _row(fr, "BPAT", 4)["gen_mw"] == pytest.approx(100)
    assert _row(fr, "BPAT", 4)["missing"] is False


def test_fill_interpolates_missing_hours_and_marks_them_tier_2():
    rows = [("NEVP", 0, {"gas": 100}), ("NEVP", 1, {}), ("NEVP", 2, {}),
            ("NEVP", 3, {"gas": 50, "wind": 50}), ("NEVP", 4, {})]
    fr = wa.fill(wa.intensity(_bal(rows)))
    v = fr.sort("ts_utc")
    ex = v["ex_hydro"].to_list()
    assert ex[0] == pytest.approx(198) and ex[3] == pytest.approx(99)
    assert ex[1] == pytest.approx(198 - 33) and ex[2] == pytest.approx(198 - 66)
    assert ex[4] == pytest.approx(99)  # trailing gap: carried from the last valid hour
    assert v["tier"].to_list() == [1, 2, 2, 1, 2]


def test_fill_adds_absent_hours_on_the_grid():
    rows = [("NEVP", 0, {"gas": 100}), ("NEVP", 2, {"wind": 100})]  # hour 1 has no row at all
    fr = wa.fill(wa.intensity(_bal(rows)), start=T0, end=T0 + timedelta(hours=3))
    assert fr.height == 3 and fr.sort("ts_utc")["tier"].to_list() == [1, 2, 1]
    assert fr.sort("ts_utc")["ex_hydro"][1] == pytest.approx(99)


def test_intensity_refuses_a_sealed_row():
    b = _bal([("PACE", 0, {"coal": 1})]).with_columns(pl.lit(TEST_START).alias("ts_utc"))
    with pytest.raises(ValueError, match="seal"):
        wa.intensity(b)


def test_load_balance_refuses_a_window_reaching_the_seal():
    with pytest.raises(ValueError, match="seal"):
        wa.load_balance(T0, TEST_START + timedelta(hours=1))


# --------------------------------------------------------------------------- policy water


def _truth(values):
    """values: {ba: [gal/MWh per hour from T0]} -> filled frame (tier 1)."""
    rows = [(ba, T0 + timedelta(hours=h), v) for ba, vs in values.items() for h, v in enumerate(vs)]
    return pl.DataFrame({"ba": [r[0] for r in rows], "ts_utc": [r[1] for r in rows],
                         "ex_hydro": [float(r[2]) for r in rows],
                         "hydro": [0.0 for _ in rows], "tier": [1 for _ in rows]},
                        schema={"ba": pl.Utf8, "ts_utc": pl.Datetime("us", "UTC"),
                                "ex_hydro": pl.Float64, "hydro": pl.Float64, "tier": pl.Int64})


def _ledger_jobs(rows):
    """rows: (uid, site, start h, end h, gpus, arrival h, duration h)."""
    t = lambda h: T0 + timedelta(hours=h)
    led = pl.DataFrame({
        "job_uid": [r[0] for r in rows], "site": [r[1] for r in rows],
        "start_ts": [t(r[2]) for r in rows], "end_ts": [t(r[3]) for r in rows],
        "arrival_ts": [t(r[5]) for r in rows], "deadline_ts": [t(r[3] + 10) for r in rows],
        "moved": [r[1] != "PACE" for r in rows], "blocked": [False for _ in rows],
        "fit_rejected": [False for _ in rows], "gpus": [r[4] for r in rows],
    }, schema_overrides={"start_ts": pl.Datetime("us", "UTC"), "end_ts": pl.Datetime("us", "UTC"),
                         "arrival_ts": pl.Datetime("us", "UTC"),
                         "deadline_ts": pl.Datetime("us", "UTC"), "gpus": pl.Int64})
    jobs = pl.DataFrame({"job_uid": [r[0] for r in rows], "source_id": [r[0] for r in rows],
                         "arrival_ts": led["arrival_ts"], "gpus": led["gpus"],
                         "duration_s": [r[6] * 3600.0 for r in rows]})
    return led, jobs


def test_policy_water_is_exact_overlap_energy_times_the_hourly_intensity():
    rate = GPU_KW * PUE
    tts = wa.truth_tables(_truth({"PACE": [400, 800, 100], "BPAT": [50, 50, 50]}))
    led, jobs = _ledger_jobs([("a", "PACE", 0.5, 2.0, 2, 0.5, 1.5)])
    out = wa.policy_water(led, jobs, tts)
    want = 2 * rate * (0.5 * 400 + 1.0 * 800) / 1000  # kWh × gal/MWh / 1000
    assert out["ex_hydro"]["total"] == pytest.approx(want)
    assert out["ex_hydro"]["by_site"] == pytest.approx({"PACE": want, "BPAT": 0.0, "CISO": 0.0,
                                                        "NEVP": 0.0})
    assert out["energy_kwh"] == pytest.approx(2 * rate * 1.5)
    assert out["it_kwh"] == pytest.approx(2 * GPU_KW * 1.5)


def test_a_moved_job_puts_its_transfer_half_at_home_half_at_the_destination():
    rate = GPU_KW * PUE
    tts = wa.truth_tables(_truth({"PACE": [400, 800, 100, 100], "BPAT": [50, 60, 70, 80]}))
    led, jobs = _ledger_jobs([("b", "BPAT", 1.5, 3.5, 4, 1.25, 2.0)])
    out = wa.policy_water(led, jobs, tts)
    t_fac = TRANSFER_FRACTION * 4 * GPU_KW * 2.0 * PUE
    exec_gal = 4 * rate * (0.5 * 60 + 1.0 * 70 + 0.5 * 80) / 1000
    home, dest = 0.5 * t_fac * 800 / 1000, 0.5 * t_fac * 60 / 1000  # the arrival hour (h = 1)
    by = out["ex_hydro"]["by_site"]
    assert by["PACE"] == pytest.approx(home)
    assert by["BPAT"] == pytest.approx(exec_gal + dest)
    assert out["ex_hydro"]["total"] == pytest.approx(math.fsum(by.values()))
    assert out["energy_kwh"] == pytest.approx(4 * rate * 2.0 + t_fac)
    assert out["it_kwh"] == pytest.approx(out["energy_kwh"] / PUE)


def test_direct_cooling_is_it_kwh_times_wue_in_gallons():
    assert wa.direct_cooling_gal(1000.0, 0.36) == pytest.approx(1000 * 0.36 / L_PER_GAL)


def test_change_vs_u():
    assert wa.change(120.0, 100.0) == (20.0, pytest.approx(0.2))
    assert wa.change(0.0, 0.0) == (0.0, None)
