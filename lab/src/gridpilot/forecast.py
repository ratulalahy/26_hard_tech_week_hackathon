"""Day-ahead forecasters K, W and L with publication envelopes (spec §5, §6, F8, F9 item 2).

Every forecast is issued daily at 10:00 America/Denver for the next Utah civil day (23, 24 or
25 UTC hours). A forecast issued at ``issue`` may only use rows that were published before it.
Publication is an **assumed** availability rule, not an archived receipt time: the row for the
hour starting at ``ts_utc`` is published at ``ts_utc + 1 h + ENVELOPE_H[target]``, and ``as_of``
keeps it only when that instant is at or before the issue.

Models (all per BA and target, in native units):

* ``K``  calendar climatology: training median by local month, local hour and
  weekday/weekend, backing off to month/hour, then hour, then the BA median. Frozen at
  ``fit_at``.
* ``W``  weekly seasonal: median of the target-hour values 168, 336, 504 and 672 h earlier
  that are published at the issue; ``K`` if none is.
* ``L``  HistGradientBoostingRegressor on issue-time features (``l_features``), fitted once at
  ``fit_at``; ``max_leaf_nodes`` is chosen in {15, 31} by validation MAE (``run_validation``).

``series`` frames have columns ``ba, ts_utc, value``: the values **as published** (hour-start
UTC). Target-specific cleaning (the demand spike rule, which looks one hour ahead) is applied
only after ``as_of``, so a feature never benefits from an hour that was not yet published.
Non-negative targets are clipped at 0 and the clip counts are logged. No night mask is applied
to solar (spec §6 allows omitting it). The BA's own demand forecast is never an input.

Limitation (spec §5): this is a publication-lagged replay of a revised historical snapshot;
historical revisions cannot be reconstructed from the bulk cache.

Run the validation forecast with ``uv run python -m gridpilot.forecast`` (writes
``runs/forecast/<UTC>/``).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import warnings
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl
import yaml
from sklearn.ensemble import HistGradientBoostingRegressor

from gridpilot.data.eia930 import add_demand_clean
from gridpilot.data.eia_co2 import CARBON_PATH, CORE_BAS, load_carbon
from gridpilot.paths import INTERIM_DIR, MANIFEST_DIR, REPO_ROOT
from gridpilot.splits import TEST_START, VALIDATION_START, drop_sealed

log = logging.getLogger(__name__)

# Publication envelopes in hours after the hour END (spec §5, assumed availability rules).
ENVELOPE_H = {"demand": 2, "wind": 48, "solar": 48, "ci_consumed": 96}
TARGETS = tuple(ENVELOPE_H)
NONNEGATIVE = frozenset(TARGETS)
UNITS = {"demand": "MW", "wind": "MW", "solar": "MW", "ci_consumed": "g/kWh"}
# One explicit IANA zone per BA (spec §6, R1), used for calendar features.
BA_TZ = {"PACE": "America/Denver", "CISO": "America/Los_Angeles",
         "BPAT": "America/Los_Angeles", "NEVP": "America/Los_Angeles"}
ISSUE_TZ = ZoneInfo("America/Denver")
ISSUE_HOUR = 10
WEEKLY_LAGS_H = (168, 336, 504, 672)
MAX_LEAF_NODES = (15, 31)
HGB_PARAMS = {"loss": "squared_error", "max_iter": 200, "learning_rate": 0.05,
              "min_samples_leaf": 48, "l2_regularization": 1.0, "early_stopping": False,
              "random_state": 42}
# Validation fit (spec §5): fitted once, history from 2022-01-01; selection on issues in
# [VALIDATION_START, SELECTION_END).
VAL_FIT_AT = datetime(2024, 10, 29, tzinfo=UTC)
VAL_HISTORY_START = datetime(2022, 1, 1, tzinfo=UTC)
SELECTION_END = datetime(2025, 10, 24, tzinfo=UTC)
# Tie-break for the best family (spec §6): seasonal, climatology, (persistence), boosting.
FAMILY_ORDER = ("W", "K", "L")
RUN_SERIES = tuple((ba, "ci_consumed") for ba in CORE_BAS) + (
    ("PACE", "demand"), ("PACE", "wind"), ("PACE", "solar"))
BALANCE_PATH = INTERIM_DIR / "eia930" / "balance.parquet"
BALANCE_COLS = {"demand": "demand_adj_mw", "wind": "gen_wind_adj_mw", "solar": "gen_solar_adj_mw"}

H = timedelta(hours=1)
TRAIL_H = 168
WINDOW_H = 1000  # history kept behind the publication cutoff (> 672 h lag + 38 h lead + 168 h)
SAME_HOUR_DAYS = 7
FORECAST_SCHEMA = {"ba": pl.Utf8, "target": pl.Utf8, "model": pl.Utf8,
                   "issue_ts": pl.Datetime("us", "UTC"), "target_ts": pl.Datetime("us", "UTC"),
                   "value": pl.Float64, "evidence": pl.Utf8}
FEATURES = (
    "lead_h", "hour", "month", "dow", "weekend", "doy",
    *(f"lag_{k}" for k in WEEKLY_LAGS_H), "lag_median", "n_lags",
    "last_value", "last_age_h", "same_hour_value", "same_hour_days",
    "trail7_mean", "trail7_range", "trail7_n", "trail24_mean",
    *(f"miss_lag_{k}" for k in WEEKLY_LAGS_H), "miss_last", "miss_same_hour",
)

Model = Literal["K", "W", "L"]


class LeakageError(ValueError):
    """A row not yet published at the issue time reached a forecaster."""


# --------------------------------------------------------------------------------------------
# Time
# --------------------------------------------------------------------------------------------


def _aware(ts: datetime, name: str) -> datetime:
    if ts.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware, got {ts!r}")
    return ts.astimezone(UTC)


def issue_times(start: datetime, end: datetime) -> list[datetime]:
    """Daily 10:00 America/Denver issue instants in [start, end), in UTC."""
    start, end = _aware(start, "start"), _aware(end, "end")
    d = start.astimezone(ISSUE_TZ).date() - timedelta(days=1)
    last = end.astimezone(ISSUE_TZ).date() + timedelta(days=1)
    out = []
    while d <= last:
        i = datetime.combine(d, time(ISSUE_HOUR), ISSUE_TZ).astimezone(UTC)
        if start <= i < end:
            out.append(i)
        d += timedelta(days=1)
    return out


def target_hours(issue: datetime) -> list[datetime]:
    """Hour starts (UTC) of the Utah civil day after the issue's local date."""
    d = _aware(issue, "issue").astimezone(ISSUE_TZ).date() + timedelta(days=1)
    s = datetime.combine(d, time(0), ISSUE_TZ).astimezone(UTC)
    e = datetime.combine(d + timedelta(days=1), time(0), ISSUE_TZ).astimezone(UTC)
    return [s + k * H for k in range((e - s) // H)]


def as_of(series: pl.DataFrame, issue: datetime, envelope_h: int) -> pl.DataFrame:
    """Rows published at or before ``issue``: ``ts_utc + 1 h + envelope_h <= issue``."""
    issue = _aware(issue, "issue")
    return series.filter(pl.col("ts_utc") + pl.duration(hours=1 + envelope_h) <= issue)


def prepare(history: pl.DataFrame, target: str | None) -> pl.DataFrame:
    """Target-specific cleaning of published rows; call it only on ``as_of`` output (or on
    truth). Demand: the EIA-930 spike rule and non-positive hours are nulled."""
    if target == "demand" and history.height:
        return add_demand_clean(history, col="value", by="ba", out="value").drop("d_spike")
    return history


def _epoch_h(ts: pl.Expr) -> pl.Expr:
    return (ts.dt.epoch("s") // 3600).cast(pl.Int64)


def _epoch_h_py(ts: datetime) -> int:
    return int(ts.timestamp() // 3600)


def _ts_frame(values: Sequence[datetime]) -> pl.DataFrame:
    return pl.DataFrame({"target_ts": list(values)},
                        schema={"target_ts": pl.Datetime("us", "UTC")})


# --------------------------------------------------------------------------------------------
# K: calendar climatology
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Climatology:
    """Frozen training medians: (month, hour, weekend) -> (month, hour) -> hour -> BA median."""

    tz: str
    cells: tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]
    ba_median: float
    n: int

    LEVELS = (("month", "hour", "weekend"), ("month", "hour"), ("hour",))


def _calendar(frame: pl.DataFrame, ts_col: str, tz: str) -> pl.DataFrame:
    local = pl.col(ts_col).dt.convert_time_zone(tz)
    return frame.with_columns(
        local.dt.month().cast(pl.Int8).alias("month"),
        local.dt.hour().cast(pl.Int8).alias("hour"),
        (local.dt.weekday() >= 6).alias("weekend"),  # polars: Monday=1 .. Sunday=7
    )


def fit_climatology(labels: pl.DataFrame, tz: str) -> Climatology:
    """Medians of the non-null ``value`` of ``labels`` (one BA) by local calendar cell."""
    lab = _calendar(labels.drop_nulls("value").filter(pl.col("value").is_not_nan()),
                    "ts_utc", tz)
    if lab.height == 0:
        raise ValueError("climatology needs at least one non-null label")
    cells = tuple(
        lab.group_by(list(keys)).agg(pl.col("value").median().alias(f"k{i}"))
        for i, keys in enumerate(Climatology.LEVELS)
    )
    return Climatology(tz=tz, cells=cells, ba_median=float(lab["value"].median()), n=lab.height)


def predict_climatology(clim: Climatology, ts: Sequence[datetime] | pl.Series) -> np.ndarray:
    """Climatology value for each UTC hour start in ``ts`` (any hour, including beyond the
    issued forecast coverage)."""
    frame = _calendar(_ts_frame(list(ts)) if not isinstance(ts, pl.Series)
                      else ts.alias("target_ts").to_frame(), "target_ts", clim.tz)
    for keys, cell in zip(Climatology.LEVELS, clim.cells, strict=True):
        frame = frame.join(cell, on=list(keys), how="left", maintain_order="left")
    out = frame.select(pl.coalesce("k0", "k1", "k2", pl.lit(clim.ba_median)).alias("v"))
    return out["v"].to_numpy().astype(float)


def climatology_table(clim: Climatology, ba: str, target: str) -> pl.DataFrame:
    """Long form of a frozen climatology, for export (level 3 is the BA median)."""
    parts = []
    for i, keys in enumerate(Climatology.LEVELS):
        c = clim.cells[i].rename({f"k{i}": "value"})
        parts.append(c.with_columns(pl.lit(i).alias("level"), *[
            pl.lit(None, dtype=pl.Int8 if k != "weekend" else pl.Boolean).alias(k)
            for k in ("month", "hour", "weekend") if k not in keys]))
    parts.append(pl.DataFrame({"value": [clim.ba_median], "level": [3]}).with_columns(
        pl.lit(None, dtype=pl.Int8).alias("month"), pl.lit(None, dtype=pl.Int8).alias("hour"),
        pl.lit(None, dtype=pl.Boolean).alias("weekend")))
    cols = ["level", "month", "hour", "weekend", "value"]
    out = pl.concat([p.select(cols).with_columns(pl.col("level").cast(pl.Int8)) for p in parts])
    return out.with_columns(pl.lit(ba).alias("ba"), pl.lit(target).alias("target"),
                            pl.lit(clim.tz).alias("tz")).sort("level", "month", "hour", "weekend")


# --------------------------------------------------------------------------------------------
# Issue-time features (shared by W and L)
# --------------------------------------------------------------------------------------------


def l_features(history: pl.DataFrame, issue: datetime, envelope_h: int, tz: str, *,
               target: str | None = None,
               targets: Sequence[datetime] | None = None) -> pl.DataFrame:
    """One feature row per target hour, built only from ``history`` as published at ``issue``.

    ``history`` must already be ``as_of(series, issue, envelope_h)``; any row published after
    the issue raises ``LeakageError``. ``target`` selects the post-as-of cleaning (``prepare``).
    Missing inputs stay NaN (HistGradientBoosting handles them natively) and get flags.
    """
    issue = _aware(issue, "issue")
    if history.height:
        late = history.filter(pl.col("ts_utc") + pl.duration(hours=1 + envelope_h) > issue)
        if late.height:
            raise LeakageError(
                f"{late.height} row(s) published after issue {issue.isoformat()} "
                f"(envelope {envelope_h} h), latest {late['ts_utc'].max()}")
    c = _epoch_h_py(issue - (1 + envelope_h) * H)  # latest admissible hour start
    base = c - WINDOW_H + 1
    hist = history.filter(_epoch_h(pl.col("ts_utc")) >= base)
    hist = prepare(hist, target)
    arr = np.full(WINDOW_H, np.nan)
    if hist.height:
        idx = hist.select(_epoch_h(pl.col("ts_utc")) - base)["ts_utc"].to_numpy()
        arr[idx] = hist["value"].cast(pl.Float64).fill_null(np.nan).to_numpy()

    targets = list(targets) if targets is not None else target_hours(issue)
    t_idx = np.array([_epoch_h_py(t) for t in targets], dtype=np.int64) - base

    def at(rel: np.ndarray) -> np.ndarray:
        ok = (rel >= 0) & (rel < WINDOW_H)
        out = np.full(rel.shape, np.nan)
        out[ok] = arr[rel[ok]]
        return out

    lags = {k: at(t_idx - k) for k in WEEKLY_LAGS_H}
    stack = np.vstack(list(lags.values()))
    n_lags = np.isfinite(stack).sum(axis=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        lag_median = np.nanmedian(stack, axis=0)

    present = np.flatnonzero(np.isfinite(arr))
    if present.size:
        last_pos = present[-1]
        last_value = np.full(len(targets), arr[last_pos])
        last_age = (t_idx - last_pos).astype(float)
    else:
        last_value = np.full(len(targets), np.nan)
        last_age = np.full(len(targets), np.nan)

    same_val = np.full(len(targets), np.nan)
    same_days = np.full(len(targets), np.nan)
    for d in range(SAME_HOUR_DAYS, 0, -1):  # smallest available day offset wins
        v = at(t_idx - 24 * d)
        ok = np.isfinite(v)
        same_val[ok], same_days[ok] = v[ok], d

    trail = arr[-TRAIL_H:]
    trail_ok = trail[np.isfinite(trail)]
    t24 = arr[-24:]
    t24 = t24[np.isfinite(t24)]
    trail_mean = float(trail_ok.mean()) if trail_ok.size else np.nan
    trail_range = float(trail_ok.max() - trail_ok.min()) if trail_ok.size else np.nan
    trail24 = float(t24.mean()) if t24.size else np.nan

    zone = ZoneInfo(tz)
    local = [t.astimezone(zone) for t in targets]
    n = len(targets)
    cols: dict[str, object] = {
        "target_ts": targets,
        "lead_h": [(t - issue) / H for t in targets],
        "hour": [x.hour for x in local],
        "month": [x.month for x in local],
        "dow": [x.weekday() for x in local],
        "weekend": [float(x.weekday() >= 5) for x in local],
        "doy": [x.timetuple().tm_yday for x in local],
        **{f"lag_{k}": v for k, v in lags.items()},
        "lag_median": lag_median,
        "n_lags": n_lags.astype(float),
        "last_value": last_value,
        "last_age_h": last_age,
        "same_hour_value": same_val,
        "same_hour_days": same_days,
        "trail7_mean": np.full(n, trail_mean),
        "trail7_range": np.full(n, trail_range),
        "trail7_n": np.full(n, float(trail_ok.size)),
        "trail24_mean": np.full(n, trail24),
        **{f"miss_lag_{k}": (~np.isfinite(v)).astype(float) for k, v in lags.items()},
        "miss_last": (~np.isfinite(last_value)).astype(float),
        "miss_same_hour": (~np.isfinite(same_val)).astype(float),
    }
    schema = {"target_ts": pl.Datetime("us", "UTC")} | {f: pl.Float64 for f in FEATURES}
    return pl.DataFrame(cols, schema=schema)


def issue_features(series: pl.DataFrame, target: str, issues: Sequence[datetime],
                   tz: str) -> pl.DataFrame:
    """``l_features`` for every issue (one BA's series), with an ``issue_ts`` column."""
    env = ENVELOPE_H[target]
    span = pl.duration(hours=WINDOW_H + env + 2)
    frames = []
    for issue in issues:
        hist = as_of(series.filter(pl.col("ts_utc") >= pl.lit(issue) - span), issue, env)
        f = l_features(hist, issue, env, tz, target=target)
        frames.append(f.with_columns(pl.lit(issue).cast(pl.Datetime("us", "UTC"))
                                     .alias("issue_ts")))
    if not frames:
        schema = {"issue_ts": pl.Datetime("us", "UTC"), "target_ts": pl.Datetime("us", "UTC")}
        return pl.DataFrame(schema=schema | {f: pl.Float64 for f in FEATURES})
    return pl.concat(frames).select("issue_ts", "target_ts", *FEATURES)


# --------------------------------------------------------------------------------------------
# Fit and predict
# --------------------------------------------------------------------------------------------


@dataclass
class Fitted:
    """Everything frozen at ``fit_at`` for one (ba, target)."""

    ba: str
    target: str
    tz: str
    fit_at: datetime
    history_start: datetime
    clim: Climatology
    train_mean: float
    n_labels: int
    hgb: dict[int, HistGradientBoostingRegressor] = field(default_factory=dict)
    n_train_rows: int = 0


def _one_ba(series: pl.DataFrame, ba: str, history_start: datetime) -> pl.DataFrame:
    s = series.filter((pl.col("ba") == ba) & (pl.col("ts_utc") >= history_start))
    return s.select(pl.col("ba").cast(pl.Utf8), "ts_utc",
                    pl.col("value").cast(pl.Float64)).sort("ts_utc")


def fit(series: pl.DataFrame, ba: str, target: str, fit_at: datetime, history_start: datetime,
        leaf_nodes: Sequence[int] = ()) -> Fitted:
    """Fit K (and L for each ``leaf_nodes`` value) on labels published by ``fit_at``, from
    ``history_start`` on. L's training rows are issues in [history_start, fit_at) whose
    features are rebuilt as of each training issue."""
    fit_at, history_start = _aware(fit_at, "fit_at"), _aware(history_start, "history_start")
    env, tz = ENVELOPE_H[target], BA_TZ[ba]
    s = _one_ba(series, ba, history_start)
    labels = prepare(as_of(s, fit_at, env), target).drop_nulls("value")
    clim = fit_climatology(labels, tz)
    out = Fitted(ba=ba, target=target, tz=tz, fit_at=fit_at, history_start=history_start,
                 clim=clim, train_mean=float(labels["value"].mean()), n_labels=labels.height)
    if leaf_nodes:
        train_issues = issue_times(history_start, fit_at)
        feats = issue_features(s, target, train_issues, tz)
        rows = feats.join(labels.select(pl.col("ts_utc").alias("target_ts"), "value"),
                          on="target_ts", how="inner")
        if rows.height == 0:
            raise ValueError(f"no L training rows for {ba}/{target} at {fit_at}")
        x, y = rows.select(FEATURES).to_numpy(), rows["value"].to_numpy()
        out.n_train_rows = rows.height
        for m in leaf_nodes:
            if m not in MAX_LEAF_NODES:
                raise ValueError(f"max_leaf_nodes must be one of {MAX_LEAF_NODES}, got {m}")
            out.hgb[m] = HistGradientBoostingRegressor(max_leaf_nodes=m, **HGB_PARAMS).fit(x, y)
    return out


def predict(fitted: Fitted, feats: pl.DataFrame, model: Model,
            max_leaf_nodes: int | None = None) -> tuple[pl.DataFrame, int]:
    """Forecast frame for the (issue_ts, target_ts) rows of ``feats`` and the clip count."""
    if feats.height and feats["issue_ts"].min() < fitted.fit_at:
        raise LeakageError("an issue precedes fit_at: the frozen model saw later labels")
    k = predict_climatology(fitted.clim, feats["target_ts"])
    if model == "K":
        v = k
    elif model == "W":
        v = np.where(feats["n_lags"].to_numpy() > 0, feats["lag_median"].to_numpy(), k)
    elif model == "L":
        if max_leaf_nodes not in fitted.hgb:
            raise ValueError(f"L with max_leaf_nodes={max_leaf_nodes} was not fitted")
        v = (fitted.hgb[max_leaf_nodes].predict(feats.select(FEATURES).to_numpy())
             if feats.height else np.array([]))
    else:
        raise ValueError(f"unknown model {model!r}")
    v = np.asarray(v, dtype=float)
    n_clip = 0
    if fitted.target in NONNEGATIVE:
        n_clip = int((v < 0).sum())
        v = np.maximum(v, 0.0)
    out = feats.select("issue_ts", "target_ts").with_columns(
        pl.lit(fitted.ba).alias("ba"), pl.lit(fitted.target).alias("target"),
        pl.lit(model).alias("model"), pl.Series("value", v, dtype=pl.Float64),
        pl.lit("forecast").alias("evidence"))
    return out.select(list(FORECAST_SCHEMA)).cast(FORECAST_SCHEMA), n_clip


def forecast(series: pl.DataFrame, ba: str, target: str, model: Model,
             issues: Sequence[datetime], fit_at: datetime, history_start: datetime, *,
             max_leaf_nodes: int | None = None) -> pl.DataFrame:
    """Forecasts of ``target`` for ``ba`` at each issue: columns ``ba, target, model, issue_ts,
    target_ts, value, evidence`` (evidence = "forecast").

    Models are frozen at ``fit_at`` with history from ``history_start``; every issue must be at
    or after ``fit_at``. ``L`` needs ``max_leaf_nodes`` (one of ``MAX_LEAF_NODES``; the
    validation choice is recorded in the run's metrics.json).
    """
    if model == "L" and max_leaf_nodes is None:
        raise ValueError("model L needs max_leaf_nodes (chosen by validation MAE)")
    issues = [_aware(i, "issue") for i in issues]
    fitted = fit(series, ba, target, fit_at, history_start,
                 leaf_nodes=(max_leaf_nodes,) if model == "L" else ())
    if model == "K":
        feats = pl.concat([_ts_frame(target_hours(i)).with_columns(
            pl.lit(i).cast(pl.Datetime("us", "UTC")).alias("issue_ts")) for i in issues]
        ) if issues else issue_features(series, target, [], fitted.tz)
    else:
        feats = issue_features(_one_ba(series, ba, fitted.history_start), target, issues,
                               fitted.tz)
    out, n_clip = predict(fitted, feats, model, max_leaf_nodes)
    if n_clip:
        log.info("%s/%s/%s: clipped %d negative forecast(s) at 0", ba, target, model, n_clip)
    return out


# --------------------------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------------------------


def score(fc: pl.DataFrame, truth: pl.DataFrame, train_mean: float) -> dict:
    """MAE, signed bias (forecast - truth) and MAE / training mean over hours with non-null
    truth. Refuses any target or truth hour at or after TEST_START."""
    if fc.height and fc["target_ts"].max() >= TEST_START:
        raise ValueError("forecast targets reach the sealed window")
    if truth.height and truth["ts_utc"].max() >= TEST_START:
        raise ValueError("truth reaches the sealed window")
    j = fc.join(truth.select("ba", pl.col("ts_utc").alias("target_ts"),
                             pl.col("value").alias("truth")),
                on=["ba", "target_ts"], how="inner").drop_nulls("truth")
    e = j["value"] - j["truth"]
    if j.height == 0:
        return {"n": 0, "mae": None, "bias": None, "nmae": None}
    mae = float(e.abs().mean())
    return {"n": j.height, "mae": mae, "bias": float(e.mean()), "nmae": mae / train_mean}


# --------------------------------------------------------------------------------------------
# Data and the validation run
# --------------------------------------------------------------------------------------------


def load_series(target: str) -> pl.DataFrame:
    """Published pre-seal series ``ba, ts_utc, value``: consumed CO2 intensity for the core BAs,
    or PACE demand / wind / solar (EIA-930 adjusted columns). Nulls are kept (dropped when
    labels or truth are formed)."""
    if target == "ci_consumed":
        frame = load_carbon().filter(pl.col("ba").is_in(list(CORE_BAS))).select(
            "ba", "ts_utc", pl.col("ci_consumed_g_kwh").alias("value"))
    else:
        col = BALANCE_COLS[target]
        frame = drop_sealed(pl.read_parquet(BALANCE_PATH, columns=["ba", "ts_utc", col]))
        frame = frame.filter(pl.col("ba").cast(pl.Utf8) == "PACE").select(
            "ba", "ts_utc", pl.col(col).alias("value"))
    frame = frame.select(pl.col("ba").cast(pl.Utf8), pl.col("ts_utc"),
                         pl.col("value").cast(pl.Float64)).sort("ba", "ts_utc")
    if frame.height and frame["ts_utc"].max() >= TEST_START:
        raise ValueError(f"{target}: loaded a sealed-window row")
    return frame


def validation_issues() -> tuple[list[datetime], list[datetime]]:
    """(all issues of the validation run, the selection issues). All issues are at or after
    the fit and their whole target day ends at or before TEST_START."""
    run = [i for i in issue_times(VAL_FIT_AT, TEST_START) if target_hours(i)[-1] + H <= TEST_START]
    sel = [i for i in run if VALIDATION_START <= i < SELECTION_END]
    return run, sel


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True,
                          check=False).stdout


def run_validation(out_root: Path | None = None) -> Path:
    """Fit at VAL_FIT_AT, forecast every validation issue with K, W and both L configs, select
    L's max_leaf_nodes per series by selection MAE, and write the run directory atomically."""
    out_root = out_root or REPO_ROOT / "runs" / "forecast"
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    issues, sel = validation_issues()
    in_sel = (pl.col("issue_ts") >= VALIDATION_START) & (pl.col("issue_ts") < SELECTION_END)
    data = {t: load_series(t) for t in {t for _, t in RUN_SERIES}}
    forecasts, climatologies, metrics = [], [], {}
    for ba, target in RUN_SERIES:
        log.info("fitting %s/%s", ba, target)
        fitted = fit(data[target], ba, target, VAL_FIT_AT, VAL_HISTORY_START,
                     leaf_nodes=MAX_LEAF_NODES)
        s = _one_ba(data[target], ba, VAL_HISTORY_START)
        feats = issue_features(s, target, issues, fitted.tz)
        truth = prepare(s, target).drop_nulls("value")
        cands = {"K": ("K", None), "W": ("W", None),
                 **{f"L{m}": ("L", m) for m in MAX_LEAF_NODES}}
        frames, clips, scores = {}, {}, {}
        for name, (model, m) in cands.items():
            f, n_clip = predict(fitted, feats, model, m)
            frames[name], clips[name] = f, n_clip
            scores[name] = {
                "selection": score(f.filter(in_sel), truth, fitted.train_mean),
                "all_issues": score(f, truth, fitted.train_mean),
            }
        # Bounded search: lower selection MAE wins; a tie keeps the smaller tree.
        chosen = min(MAX_LEAF_NODES, key=lambda m: (scores[f"L{m}"]["selection"]["mae"], m))
        clips["L"] = clips[f"L{chosen}"]
        scores["L"] = scores[f"L{chosen}"]
        best = min(FAMILY_ORDER, key=lambda k: (scores[k]["selection"]["mae"],
                                                FAMILY_ORDER.index(k)))
        forecasts += [frames["K"], frames["W"], frames[f"L{chosen}"]]
        climatologies.append(climatology_table(fitted.clim, ba, target))
        metrics[f"{ba}/{target}"] = {
            "ba": ba, "target": target, "unit": UNITS[target], "envelope_h": ENVELOPE_H[target],
            "train_mean": fitted.train_mean, "n_labels": fitted.n_labels,
            "n_train_rows_L": fitted.n_train_rows,
            "L_max_leaf_nodes": chosen,
            "best_family_by_selection_mae": best,
            "clip_counts": clips,
            "models": {k: scores[k] for k in ("K", "W", "L")},
            "L_configs": {str(m): scores[f"L{m}"] for m in MAX_LEAF_NODES},
        }
        log.info("%s/%s: L max_leaf_nodes=%d, MAE K %.2f W %.2f L %.2f", ba, target, chosen,
                 scores["K"]["selection"]["mae"], scores["W"]["selection"]["mae"],
                 scores["L"]["selection"]["mae"])
    fc = pl.concat(forecasts)
    if fc["target_ts"].max() + H > TEST_START:
        raise ValueError("a target hour reaches the sealed window")

    inputs = {"balance.parquet": BALANCE_PATH, "carbon_hourly.parquet": CARBON_PATH,
              "carbon_hourly.meta.json": CARBON_PATH.with_name("carbon_hourly.meta.json"),
              "manifests/eia930.json": MANIFEST_DIR / "eia930.json",
              "manifests/snapshot.json": MANIFEST_DIR / "snapshot.json"}
    config = {
        "run_id": run_id, "evidence": "forecast",
        "issue": {"tz": "America/Denver", "hour_local": ISSUE_HOUR,
                  "target": "next Utah civil day (America/Denver), UTC hour starts"},
        "envelope_h": ENVELOPE_H,
        "envelope_rule": "keep row iff ts_utc + 1h + envelope_h <= issue (assumed availability)",
        "fit_at": VAL_FIT_AT.isoformat(), "history_start": VAL_HISTORY_START.isoformat(),
        "issues": {"first": issues[0].isoformat(), "last": issues[-1].isoformat(),
                   "n": len(issues)},
        "selection": {"issue_start": VALIDATION_START.isoformat(),
                      "issue_end_exclusive": SELECTION_END.isoformat(), "n": len(sel)},
        "series": [f"{ba}/{t}" for ba, t in RUN_SERIES], "ba_tz": BA_TZ,
        "weekly_lags_h": list(WEEKLY_LAGS_H),
        "hgb": {**HGB_PARAMS, "max_leaf_nodes_grid": list(MAX_LEAF_NODES)},
        "features": list(FEATURES),
        "climatology_levels": [list(k) for k in Climatology.LEVELS] + [["ba_median"]],
        "nonnegative_clip": sorted(NONNEGATIVE),
        "solar_night_mask": "none (omitted, spec §6)",
        "demand_cleaning": "EIA-930 spike rule + non-positive nulled, applied after as_of",
        "inputs_sha256": {k: _sha256(p) for k, p in inputs.items() if p.exists()},
        "test_start": TEST_START.isoformat(),
    }
    out_root.mkdir(parents=True, exist_ok=True)
    tmp = out_root / f".tmp-{run_id}-{os.getpid()}"
    final = out_root / run_id
    tmp.mkdir()
    try:
        fc.write_parquet(tmp / "forecasts.parquet")
        pl.concat(climatologies).write_parquet(tmp / "climatology.parquet")
        (tmp / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
        (tmp / "git.txt").write_text(
            f"sha {_git('rev-parse', 'HEAD').strip()}\nstatus:\n{_git('status', '--porcelain')}")
        (tmp / "metrics.json").write_text(json.dumps(
            {"run_id": run_id, "evidence": "forecast",
             "window_note": ("selection = issues in [2024-11-01, 2025-10-24); all_issues = "
                             "every run issue, descriptive only. Development evidence: the "
                             "validation year was already exposed by the profiles."),
             "metric_note": "bias = mean(forecast - truth); nmae = MAE / training mean",
             "series": metrics}, indent=2) + "\n")
        os.rename(tmp, final)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return final


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    print(run_validation())
