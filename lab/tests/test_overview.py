"""The ten-region overview (Stage 3 T18): forecast skill, stress, profiles, clean vs rush hours and
the daily swing, on synthetic frames. Validation only; the seal is refused."""

from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl
import pytest

from gridpilot import forecast as F
from gridpilot import overview as ov
from gridpilot.results import sealed_timestamps, unenveloped_numbers, validate_artifact

H = timedelta(hours=1)
START = datetime(2024, 7, 1, tzinfo=UTC)
END = datetime(2025, 10, 31, tzinfo=UTC)


def _hours(start=START, end=END):
    n = (end - start) // H
    return [start + i * H for i in range(n)]


def _frames(ba="PSCO", ci_null=False):
    """Net load peaks at 18:00 Denver-ish (01:00Z), CI rises with net load; solar at midday."""
    ts = _hours()
    hz = np.array([t.hour for t in ts], dtype=float)
    rng = np.random.default_rng(0)
    peak = np.cos((hz - 1) / 24 * 2 * np.pi)          # max at 01:00Z
    solar = np.clip(np.cos((hz - 19) / 24 * 2 * np.pi), 0, None) * 800  # max at 19:00Z
    demand = 5000 + 1000 * peak + rng.normal(0, 50, len(ts))
    wind = np.full(len(ts), 300.0)
    net = demand - wind - solar
    ci = 200 + 0.08 * (net - net.mean()) + rng.normal(0, 5, len(ts))
    carbon = pl.DataFrame({"ba": [ba] * len(ts), "ts_utc": ts,
                           "ci_consumed_g_kwh": [None] * len(ts) if ci_null else ci},
                          schema={"ba": pl.Utf8, "ts_utc": pl.Datetime("us", "UTC"),
                                  "ci_consumed_g_kwh": pl.Float64})
    balance = pl.DataFrame({"ba": [ba] * len(ts), "ts_utc": ts, "demand_adj_mw": demand,
                            "gen_wind_adj_mw": wind, "gen_solar_adj_mw": solar},
                           schema={"ba": pl.Utf8, "ts_utc": pl.Datetime("us", "UTC"),
                                   "demand_adj_mw": pl.Float64, "gen_wind_adj_mw": pl.Float64,
                                   "gen_solar_adj_mw": pl.Float64})
    return carbon, balance


def _fit_kw():
    return {"history_start": START}


# --------------------------------------------------------------------------- registry and seal


def test_ten_regions_with_registered_zones():
    assert len(ov.OVERVIEW_BAS) == 10 and ov.OVERVIEW_BAS[0] == "PACE"
    assert set(ov.OVERVIEW_BAS) <= set(ov.OVERVIEW_TZ)
    for ba, tz in F.BA_TZ.items():  # the core sites keep forecast.py's zones
        assert ov.OVERVIEW_TZ[ba] == tz


def test_window_is_the_validation_year_to_the_selection_cutoff():
    assert ov.WINDOW == (datetime(2024, 11, 1, tzinfo=UTC), F.SELECTION_END)
    assert ov.WINDOW[1] < F.TEST_START


def test_build_refuses_sealed_rows():
    carbon, balance = _frames()
    extra = carbon.tail(1).with_columns(pl.lit(F.TEST_START).alias("ts_utc"))
    with pytest.raises(ValueError, match="sealed"):
        ov.build_overview(pl.concat([carbon, extra]), balance, bas=("PSCO",), leaf_nodes=())


# --------------------------------------------------------------------------- stress


def test_stress_cdf_uses_only_training_rows_published_by_the_fit():
    ts = [F.VAL_FIT_AT - k * H for k in range(1, 200)]
    vals = [1000.0] * len(ts)
    vals[0] = 1e9  # published after fit_at under the 48 h envelope: must not enter the CDF
    net = pl.DataFrame({"ts_utc": ts, "net_load_mw": vals},
                       schema={"ts_utc": pl.Datetime("us", "UTC"), "net_load_mw": pl.Float64})
    cdf = ov.fit_stress(net, history_start=START)
    assert cdf.sorted_mw.max() == 1000.0
    assert cdf.n == len(ts) - 48  # the last 48 hour starts are not yet published


def test_stress_percentile_is_monotone_and_threshold_is_q95():
    net = pl.DataFrame({"ts_utc": [START + k * H for k in range(100)],
                        "net_load_mw": [float(k) for k in range(100)]},
                       schema={"ts_utc": pl.Datetime("us", "UTC"), "net_load_mw": pl.Float64})
    cdf = ov.fit_stress(net, fit_at=START + 200 * H, history_start=START)
    p = cdf.pct(np.array([-1.0, 10.0, 50.0, 99.0, 1e6, np.nan]))
    assert p[0] == 0 and p[3] == 100 and p[4] == 100 and np.isnan(p[5])
    assert np.all(np.diff(p[:5]) >= 0)
    assert cdf.threshold_mw == pytest.approx(np.quantile(np.arange(100.0), 0.95))


# --------------------------------------------------------------------------- forecasts


def test_persistence_prefers_the_same_hour_value_then_the_last_value():
    feats = pl.DataFrame({"issue_ts": [START] * 3, "target_ts": [START + k * H for k in range(3)],
                          "same_hour_value": [5.0, np.nan, np.nan],
                          "last_value": [9.0, 7.0, -3.0]})
    p = ov.persistence(feats, "demand")
    assert p["value"].to_list() == [5.0, 7.0, 0.0]  # clipped at 0


def test_best_family_tie_order_and_skill():
    s = {"W": {"n": 1, "mae": 2.0}, "K": {"n": 1, "mae": 2.0}, "L": {"n": 1, "mae": 3.0}}
    assert ov.best_family(s) == "W"
    s["L"]["mae"] = 1.0
    assert ov.best_family(s) == "L"
    assert ov.skill(5.0, 10.0) == pytest.approx(0.5)
    assert ov.skill(12.0, 10.0) == pytest.approx(-0.2)
    assert ov.skill(None, 10.0) is None and ov.skill(1.0, 0.0) is None


def test_forecasts_respect_the_publication_envelope():
    carbon, balance = _frames()
    s = ov.series(carbon, balance, "PSCO", "ci_consumed")
    issues = F.validation_issues()[1][:3]
    feats = F.issue_features(s, "ci_consumed", issues, "America/Denver")
    # the newest usable hour is 97 h before the issue (96 h envelope after the hour end)
    age = (feats["last_age_h"] - feats["lead_h"]).to_numpy()
    assert np.all(age >= 1 + F.ENVELOPE_H["ci_consumed"])


def test_top_k_precision_is_one_for_a_perfect_forecast():
    issue = START
    ts = [START + k * H for k in range(24)]
    vals = [float((k * 7) % 24) for k in range(24)]
    fc = pl.DataFrame({"issue_ts": [issue] * 24, "target_ts": ts, "value": vals},
                      schema={"issue_ts": pl.Datetime("us", "UTC"),
                              "target_ts": pl.Datetime("us", "UTC"), "value": pl.Float64})
    truth = pl.DataFrame({"ts_utc": ts, "net_load_mw": vals},
                         schema={"ts_utc": pl.Datetime("us", "UTC"), "net_load_mw": pl.Float64})
    assert ov.top_k_precision(fc, truth) == (1.0, 1)
    flipped = fc.with_columns((-pl.col("value")).alias("value"))
    assert ov.top_k_precision(flipped, truth) == (0.0, 1)


# --------------------------------------------------------------------------- profiles


def test_daily_swing_is_dirtiest_minus_cleanest_on_complete_days():
    ts = _hours(datetime(2025, 1, 2, 7, tzinfo=UTC), datetime(2025, 1, 4, 7, tzinfo=UTC))
    ci = [100.0 + (i % 24) for i in range(len(ts))]
    ci[30] = None  # the second Denver day is incomplete: skipped
    h = ov._local(pl.DataFrame({"ts_utc": ts, "ci": ci},
                               schema={"ts_utc": pl.Datetime("us", "UTC"), "ci": pl.Float64}))
    sw = ov.daily_swing(h)
    assert sw["n_days"] == 1 and sw["median_g"] == pytest.approx(23.0)


def test_region_alignment_on_a_grid_where_rush_hours_are_dirty():
    carbon, balance = _frames()
    issues = F.validation_issues()[1][:5]
    r = ov.region(carbon, balance, "PSCO", issues=issues, leaf_nodes=())
    al = r["alignment"]
    assert al["spearman_ci_net_load"] > 0.8
    assert al["rush_vs_mean_pct"] > 0 and al["stress_vs_mean_pct"] > 0
    assert al["clean_rush_overlap_pct"] < 100 / 6  # cleanest hours are midday, rush is evening
    assert al["stress_top_quartile_share"] > 50
    assert len(r["profile"]["ci"]) == 24 and None not in r["profile"]["ci"]
    assert r["ci"]["scores"]["P"]["n"] > 0 and r["n_issues"] == 5


def test_artifact_is_enveloped_unsealed_and_drops_regions_without_data():
    c1, b1 = _frames("PSCO")
    c2, b2 = _frames("AZPS", ci_null=True)
    art = ov.build_overview(pl.concat([c1, c2]), pl.concat([b1, b2]), bas=("PSCO", "AZPS"),
                            leaf_nodes=(), issues=F.validation_issues()[1][:4])
    assert art["order"] == ["PSCO"] and list(art["regions"]) == ["PSCO"]
    assert art["dropped"][0]["ba"] == "AZPS" and "insufficient" in art["dropped"][0]["reason"]
    assert validate_artifact(art) == []
    assert unenveloped_numbers(art) == [] and sealed_timestamps(art) == []
    r = art["regions"]["PSCO"]
    assert r["profile"]["ci"]["evidence"] == "modeled"
    assert r["profile"]["net_load_mw"]["evidence"] == "observed"
    assert r["forecast"]["ci"]["skill"]["vs_persistence"]["evidence"] == "measured"
    assert r["forecast"]["stress"]["threshold_mw"]["evidence"] == "modeled"
    assert art["parameters"]["stress_quantile"]["evidence"] == "assumed"
    assert r["forecast"]["ci"]["model"] in ("W", "K")
