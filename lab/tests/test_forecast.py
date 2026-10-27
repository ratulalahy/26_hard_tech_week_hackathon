"""Forecasters K/W/L and the as-of guard (spec sections 5 and 6, F8, F9 item 2)."""

from datetime import UTC, datetime, timedelta
from itertools import pairwise
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl
import pytest

from gridpilot.forecast import (
    ENVELOPE_H,
    WEEKLY_LAGS_H,
    LeakageError,
    as_of,
    fit_climatology,
    forecast,
    issue_times,
    l_features,
    predict_climatology,
    score,
    target_hours,
)
from gridpilot.splits import TEST_START

DENVER = ZoneInfo("America/Denver")
H = timedelta(hours=1)


def _series(start: datetime, hours: int, ba: str = "PACE", fn=None) -> pl.DataFrame:
    ts = [start + i * H for i in range(hours)]
    fn = fn or (lambda i, t: 100.0 + 10.0 * np.sin(2 * np.pi * t.hour / 24) + 0.01 * i)
    return pl.DataFrame(
        {"ba": [ba] * hours, "ts_utc": ts, "value": [float(fn(i, t)) for i, t in enumerate(ts)]},
        schema={"ba": pl.Utf8, "ts_utc": pl.Datetime("us", "UTC"), "value": pl.Float64},
    )


def test_envelopes_are_the_pinned_values():
    assert ENVELOPE_H == {"demand": 2, "wind": 48, "solar": 48, "ci_consumed": 96}
    assert WEEKLY_LAGS_H == (168, 336, 504, 672)


def test_issue_times_denver_dst():
    issues = issue_times(datetime(2025, 3, 8, tzinfo=UTC), datetime(2025, 3, 11, tzinfo=UTC))
    assert all(i.tzinfo == UTC for i in issues)
    assert [i.astimezone(DENVER).hour for i in issues] == [10, 10, 10]
    assert issues[0] == datetime(2025, 3, 8, 17, tzinfo=UTC)  # MST
    assert issues[1] == datetime(2025, 3, 9, 16, tzinfo=UTC)  # MDT, DST began 02:00 local

    autumn = issue_times(datetime(2025, 11, 1, tzinfo=UTC), datetime(2025, 11, 3, tzinfo=UTC))
    assert autumn == [datetime(2025, 11, 1, 16, tzinfo=UTC), datetime(2025, 11, 2, 17, tzinfo=UTC)]
    assert all(i.astimezone(DENVER).hour == 10 for i in autumn)


def test_issue_times_half_open():
    start = datetime(2025, 1, 10, 17, tzinfo=UTC)  # exactly an issue instant
    issues = issue_times(start, start + timedelta(days=2))
    assert issues == [start, start + timedelta(days=1)]


def test_target_day_lengths():
    def day(local_date):
        issue = datetime(*local_date, 10, tzinfo=DENVER).astimezone(UTC)
        return target_hours(issue)

    spring, normal, autumn = day((2025, 3, 8)), day((2025, 6, 1)), day((2025, 11, 1))
    assert (len(spring), len(normal), len(autumn)) == (23, 24, 25)
    for hours, local_day in ((spring, 9), (normal, 2), (autumn, 2)):
        assert hours[0].astimezone(DENVER).hour == 0
        assert hours[0].astimezone(DENVER).day == local_day
        assert all(b - a == H for a, b in pairwise(hours))
        assert (hours[-1] + H).astimezone(DENVER).hour == 0
    assert all(t.tzinfo == UTC for t in normal)


def test_as_of_drops_future():
    issue = datetime(2025, 1, 10, 17, tzinfo=UTC)
    s = _series(issue - 10 * H, 10)  # last row is issue - 1 h
    kept = as_of(s, issue, 2)
    assert (issue - H) not in kept["ts_utc"].to_list()  # the sentinel
    assert kept["ts_utc"].max() == issue - 3 * H  # hour end + 2 h == issue: just in
    assert as_of(s, issue, 96).height == 0


def test_weekly_median():
    start = datetime(2024, 1, 1, tzinfo=UTC)
    s = _series(start, 24 * 60, fn=lambda i, t: float(i))  # value = hours since start
    issue = issue_times(start + timedelta(days=40), start + timedelta(days=41))[0]
    targets = target_hours(issue)
    out = forecast(s, "PACE", "demand", "W", [issue], fit_at=issue, history_start=start)
    for t, v in zip(targets, out.sort("target_ts")["value"].to_list(), strict=True):
        idx = (t - start) // H
        assert v == pytest.approx(np.median([idx - k for k in WEEKLY_LAGS_H]))

    # Drop the 336 h and 672 h lags of the first target: the median uses the two left.
    t0 = targets[0]
    holed = s.filter(~pl.col("ts_utc").is_in([t0 - 336 * H, t0 - 672 * H]))
    out = forecast(holed, "PACE", "demand", "W", [issue], fit_at=issue, history_start=start)
    i0 = (t0 - start) // H
    first = out.filter(pl.col("target_ts") == t0)["value"].item()
    assert first == pytest.approx(np.median([i0 - 168, i0 - 504]))

    # No lag at all: fall back to climatology.
    none = s.filter(~pl.col("ts_utc").is_in([t0 - k * H for k in WEEKLY_LAGS_H]))
    out = forecast(none, "PACE", "demand", "W", [issue], fit_at=issue, history_start=start)
    first = out.filter(pl.col("target_ts") == t0)["value"].item()
    clim_none = fit_climatology(as_of(none, issue, ENVELOPE_H["demand"]), "America/Denver")
    assert first == pytest.approx(predict_climatology(clim_none, [t0])[0])


def test_weekly_median_respects_the_envelope():
    # ci_consumed (96 h) for a target 168 h ahead of a just-published hour: still available,
    # but a lag that is not yet published must not be used.
    start = datetime(2024, 1, 1, tzinfo=UTC)
    s = _series(start, 24 * 60, fn=lambda i, t: float(i))
    issue = issue_times(start + timedelta(days=40), start + timedelta(days=41))[0]
    feats = l_features(as_of(s, issue, 96), issue, 96, "America/Denver")
    cutoff = issue - H - 96 * H
    for row in feats.iter_rows(named=True):
        for k in WEEKLY_LAGS_H:
            lag_ts = row["target_ts"] - k * H
            if lag_ts > cutoff:
                assert row[f"lag_{k}"] is None or np.isnan(row[f"lag_{k}"])


def test_climatology_backoff():
    tz = "America/Denver"
    # Only January weekday data at local hours 0..22 plus one July weekday row at hour 5.
    jan = [datetime(2024, 1, d, h, tzinfo=ZoneInfo(tz)) for d in (2, 3, 4) for h in range(23)]
    jul = [datetime(2024, 7, 2, 5, tzinfo=ZoneInfo(tz))]
    ts = [t.astimezone(UTC) for t in jan + jul]
    vals = [float(t.astimezone(ZoneInfo(tz)).hour) for t in jan] + [1000.0]
    s = pl.DataFrame({"ba": "PACE", "ts_utc": ts, "value": vals},
                     schema={"ba": pl.Utf8, "ts_utc": pl.Datetime("us", "UTC"),
                             "value": pl.Float64})
    clim = fit_climatology(s, tz)

    def at(y, m, d, h):
        return datetime(y, m, d, h, tzinfo=ZoneInfo(tz)).astimezone(UTC)

    # Full cell: January weekday hour 7.
    assert predict_climatology(clim, [at(2024, 1, 9, 7)])[0] == 7.0
    # January Saturday hour 7: no weekend cell, back off to month/hour.
    assert predict_climatology(clim, [at(2024, 1, 6, 7)])[0] == 7.0
    # March weekday hour 7: no March cells, back off to hour (Jan median 7).
    assert predict_climatology(clim, [at(2024, 3, 5, 7)])[0] == 7.0
    # March hour 5: hour 5 pools Jan (5) and Jul (1000) -> median of [5,5,5,1000].
    assert predict_climatology(clim, [at(2024, 3, 5, 5)])[0] == 5.0
    # Hour 23 never observed: back off to the BA median.
    expected = float(np.median(vals))
    assert predict_climatology(clim, [at(2024, 3, 5, 23)])[0] == expected


def test_no_future_in_L_features():
    start = datetime(2024, 1, 1, tzinfo=UTC)
    issue = issue_times(start + timedelta(days=40), start + timedelta(days=41))[0]
    s = _series(start, 24 * 60)
    ok = as_of(s, issue, 2)
    feats = l_features(ok, issue, 2, "America/Denver")
    assert feats.height == len(target_hours(issue))
    leaked = pl.concat([ok, _series(issue - 2 * H, 1)])  # hour end + 2 h > issue
    with pytest.raises(LeakageError):
        l_features(leaked, issue, 2, "America/Denver")


@pytest.mark.parametrize("model", ["K", "W", "L"])
def test_forecast_ignores_data_published_after_the_issue(model):
    start = datetime(2024, 1, 1, tzinfo=UTC)
    s = _series(start, 24 * 90)
    fit_at = start + timedelta(days=60)
    issues = issue_times(fit_at, fit_at + timedelta(days=5))
    kw = {"max_leaf_nodes": 15} if model == "L" else {}
    base = forecast(s, "PACE", "wind", model, issues, fit_at=fit_at, history_start=start, **kw)
    # Corrupt everything not yet published at the first issue: its forecast must not change.
    first = issues[0]
    cut = first - H - ENVELOPE_H["wind"] * H
    bad = s.with_columns(pl.when(pl.col("ts_utc") > cut).then(-1e6).otherwise(pl.col("value"))
                         .alias("value"))
    got = forecast(bad, "PACE", "wind", model, [first], fit_at=fit_at, history_start=start, **kw)
    exp = base.filter(pl.col("issue_ts") == first).sort("target_ts")
    assert got.sort("target_ts")["value"].to_list() == pytest.approx(exp["value"].to_list())


def test_forecast_schema_and_clipping():
    start = datetime(2024, 1, 1, tzinfo=UTC)
    # Night-zero solar-like series with small negatives, as in EIA data.
    s = _series(start, 24 * 90, fn=lambda i, t: max(-2.0, 50 * np.sin(np.pi * (t.hour - 13) / 12)))
    fit_at = start + timedelta(days=60)
    issues = issue_times(fit_at, fit_at + timedelta(days=3))
    out = forecast(s, "PACE", "solar", "L", issues, fit_at=fit_at, history_start=start,
                   max_leaf_nodes=15)
    assert out.columns == ["ba", "target", "model", "issue_ts", "target_ts", "value", "evidence"]
    assert out["evidence"].unique().to_list() == ["forecast"]
    assert out["value"].min() >= 0.0
    assert out.height == sum(len(target_hours(i)) for i in issues)
    assert out["target"].unique().to_list() == ["solar"]
    assert out["model"].unique().to_list() == ["L"]


def test_L_requires_a_config():
    start = datetime(2024, 1, 1, tzinfo=UTC)
    s = _series(start, 24 * 30)
    with pytest.raises(ValueError):
        forecast(s, "PACE", "demand", "L", [], fit_at=start + timedelta(days=20),
                 history_start=start)


def test_history_start_is_respected():
    # Data before history_start must not enter the climatology.
    start = datetime(2024, 1, 1, tzinfo=UTC)
    s = _series(start, 24 * 60, fn=lambda i, t: 1e6 if i < 24 * 30 else 1.0)
    hs = start + timedelta(days=30)
    fit_at = start + timedelta(days=55)
    out = forecast(s, "PACE", "demand", "K", issue_times(fit_at, fit_at + timedelta(days=1)),
                   fit_at=fit_at, history_start=hs)
    assert out["value"].max() == 1.0


def test_demand_spike_rule_is_applied_after_as_of():
    # The spike flag at hour t uses hour t+1. At an issue the latest published hour has no
    # published successor, so its value is used as published (not cleaned with future data).
    start = datetime(2024, 1, 1, tzinfo=UTC)
    issue = issue_times(start + timedelta(days=40), start + timedelta(days=41))[0]
    last = issue - 3 * H
    s = _series(start, 24 * 60, fn=lambda i, t: 1000.0)
    s = s.with_columns(pl.when(pl.col("ts_utc") == last).then(5000.0).otherwise(pl.col("value"))
                       .alias("value"))
    feats = l_features(as_of(s, issue, 2), issue, 2, "America/Denver", target="demand")
    assert feats["last_value"].unique().to_list() == [5000.0]
    # With the successor published, the spike is cleaned (nulled) and the last value is 1000.
    later = issue + H
    feats = l_features(as_of(s, later, 2), later, 2, "America/Denver", target="demand")
    assert feats["last_value"].unique().to_list() == [1000.0]


def test_score_refuses_sealed_truth():
    fc = pl.DataFrame({"ba": ["PACE"], "target": ["demand"], "model": ["K"],
                       "issue_ts": [TEST_START - 20 * H], "target_ts": [TEST_START],
                       "value": [1.0], "evidence": ["forecast"]},
                      schema_overrides={"issue_ts": pl.Datetime("us", "UTC"),
                                        "target_ts": pl.Datetime("us", "UTC")})
    truth = pl.DataFrame({"ba": ["PACE"], "ts_utc": [TEST_START - H], "value": [1.0]},
                         schema_overrides={"ts_utc": pl.Datetime("us", "UTC")})
    with pytest.raises(ValueError):
        score(fc, truth, train_mean=1.0)


def test_score_metrics():
    t0 = datetime(2024, 5, 1, tzinfo=UTC)
    fc = pl.DataFrame({"ba": "PACE", "target": "demand", "model": "K", "issue_ts": t0 - 20 * H,
                       "target_ts": [t0, t0 + H, t0 + 2 * H], "value": [10.0, 12.0, 9.0],
                       "evidence": "forecast"},
                      schema_overrides={"issue_ts": pl.Datetime("us", "UTC"),
                                        "target_ts": pl.Datetime("us", "UTC")})
    truth = pl.DataFrame({"ba": "PACE", "ts_utc": [t0, t0 + H, t0 + 2 * H],
                          "value": [11.0, 12.0, None]},
                         schema_overrides={"ts_utc": pl.Datetime("us", "UTC")})
    m = score(fc, truth, train_mean=4.0)
    assert m == {"n": 2, "mae": 0.5, "bias": -0.5, "nmae": 0.125}
