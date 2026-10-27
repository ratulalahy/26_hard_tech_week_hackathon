"""The ten-region overview of the traffic report (Stage 3 T18; spec §6, R2): `results/overview.json`.

**Validation only.** Profiles cover [2024-11-01T00Z, 2025-10-24T00Z) (eval_start to the selection
cutoff, as `grid_profile.WINDOW`); forecasts are the validation-selection issues of the registered
forecast run (`forecast.validation_issues()`: issued daily at 10:00 America/Denver in
[VALIDATION_START, SELECTION_END), each for the next Utah civil day). Models are fitted once at
`forecast.VAL_FIT_AT` (2024-10-29) on history from 2022-01-01, i.e. training <= 2024-10. Every grid
read goes through `drop_sealed`; nothing here reads the sealed test window.

Per region (an EIA-930 balancing authority):

* **Forecast skill.** The existing forecasters (`gridpilot.forecast`: K calendar climatology, W
  weekly seasonal, L gradient boosting with max_leaf_nodes in {15, 31} chosen by selection MAE)
  under the same publication envelopes (`forecast.ENVELOPE_H`) and issue rule, for consumed CO2
  intensity (EIA modeled) and for net load = demand - wind - solar (each forecast separately, then
  subtracted: spec §6). The baseline P is same-hour persistence: the most recent published value
  at the target's clock hour within 7 days (`l_features.same_hour_value`), else the last published
  value. Skill = 1 - MAE(model) / MAE(baseline), against P and against K. The "traffic-report"
  model is the best family by selection MAE (spec §6 tie order W, K, L); because the same window
  selects and scores it, its skill is development evidence (results.LIMIT_VALIDATION_DEV).
* **Net-load stress** is net load's percentile in the region's training-window empirical CDF
  (net-load hours in [2022-01-01, fit_at) published by fit_at), and a stress hour is one above that
  CDF's 95th percentile (spec §4, R6). Stress MAE is in percentile points; top-4 precision is the
  daily share of the forecast's four highest-net-load hours that are among the actual four.
* **Typical day** (24 America/Denver clock hours, one clock for every region as in
  `grid_profile`): mean consumed CO2 intensity, mean net load and mean stress percentile.
* **Clean hours vs rush hours (R2).** Mean intensity in stress hours and in each day's four
  highest-net-load hours (rush hours) against the all-hours mean; the share of stress hours that
  fall in the region's top intensity quartile; the Spearman correlation of hourly intensity and
  net load (equal to that with its training percentile, a monotone transform); and how many of
  each day's four cleanest hours are also its rush hours.
* **Daily swing.** Per Denver civil day with every hour published, dirtiest minus cleanest hourly
  intensity; the median over days is the room a time shift has.

The four core sites read the registered carbon table (`eia_co2.CARBON_PATH`); the other six parse
their EIA BA workbooks the same way (`eia_co2.parse_ba_workbook`), in memory, never writing the
shared data directory. `forecast.py` is left untouched (its zones cover only the core sites): the
fit below mirrors `forecast.fit` with each region's registered zone.
"""

from __future__ import annotations

import math
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingRegressor

from gridpilot import forecast as F
from gridpilot.data.eia_co2 import CARBON_PATH, CORE_BAS, WORKBOOK_DIR, parse_ba_workbook
from gridpilot.results import SCHEMA_VERSION, env, iso
from gridpilot.splits import TEST_START, drop_sealed

OVERVIEW_BAS = ("PACE", "BPAT", "CISO", "NEVP", "AZPS", "PSCO", "ERCO", "SWPP", "MISO", "PJM")
# One explicit IANA zone per region for the forecasters' calendar features (spec §6: "the overview
# zones are registered explicitly"); the core four are forecast.BA_TZ.
OVERVIEW_TZ = {**F.BA_TZ, "AZPS": "America/Phoenix", "PSCO": "America/Denver",
               "ERCO": "America/Chicago", "SWPP": "America/Chicago", "MISO": "America/Chicago",
               "PJM": "America/New_York"}
NAMES = {"PACE": "PacifiCorp East (Utah)", "BPAT": "Bonneville (Pacific Northwest)",
         "CISO": "California ISO", "NEVP": "NV Energy (Nevada)", "AZPS": "Arizona Public Service",
         "PSCO": "Public Service Co. of Colorado", "ERCO": "ERCOT (Texas)",
         "SWPP": "Southwest Power Pool", "MISO": "Midcontinent ISO", "PJM": "PJM Interconnection"}
INTERCONNECT = {"ERCO": "Texas", "SWPP": "Eastern", "MISO": "Eastern", "PJM": "Eastern"}

TZ_NAME = "America/Denver"
WINDOW = (datetime(2024, 11, 1, tzinfo=UTC), datetime(2025, 10, 24, tzinfo=UTC))
STRESS_Q = 0.95
RUSH_K = 4
MIN_COVERAGE = 0.90  # a region needs this share of window hours with intensity and net load
TARGETS = ("ci_consumed", "demand", "wind", "solar")
NET = ("demand", "wind", "solar")
PROV = "overview"
DECIMALS = 4
H = timedelta(hours=1)


def _r(v):
    if v is None:
        return None
    v = float(v)
    return round(v, DECIMALS) if math.isfinite(v) else None


# --------------------------------------------------------------------------------------------
# Inputs (validation-era rows only)
# --------------------------------------------------------------------------------------------


def load_carbon(bas: tuple[str, ...] = OVERVIEW_BAS) -> pl.DataFrame:
    """Consumed CO2 intensity (g/kWh, tier 1: EIA-published hours only, nulls kept) for `bas` over
    [VAL_HISTORY_START, TEST_START): the registered table for the core sites, the BA workbooks for
    the others."""
    lo = F.VAL_HISTORY_START
    core = [b for b in bas if b in CORE_BAS]
    frames = []
    if core:
        frames.append(drop_sealed(pl.scan_parquet(CARBON_PATH))
                      .filter(pl.col("ba").is_in(core) & (pl.col("ts_utc") >= lo))
                      .select("ba", "ts_utc", "ci_consumed_g_kwh").collect())
    for ba in bas:
        if ba in CORE_BAS:
            continue
        wb = drop_sealed(parse_ba_workbook(WORKBOOK_DIR / f"{ba}.xlsx", ba))
        frames.append(wb.filter(pl.col("ts_utc") >= lo).select("ba", "ts_utc", "ci_consumed_g_kwh"))
    out = pl.concat(frames).with_columns(pl.col("ba").cast(pl.Utf8)).sort("ba", "ts_utc")
    if out.height and out["ts_utc"].max() >= TEST_START:
        raise ValueError("overview carbon holds a sealed-window row")
    return out


def load_balance(bas: tuple[str, ...] = OVERVIEW_BAS) -> pl.DataFrame:
    """EIA-930 adjusted demand, wind and solar (MW) for `bas` over [VAL_HISTORY_START, TEST_START)."""
    cols = ["ba", "ts_utc"] + [F.BALANCE_COLS[t] for t in NET]
    out = (drop_sealed(pl.scan_parquet(F.BALANCE_PATH))
           .with_columns(pl.col("ba").cast(pl.Utf8))
           .filter(pl.col("ba").is_in(list(bas)) & (pl.col("ts_utc") >= F.VAL_HISTORY_START))
           .select(cols).collect()
           .with_columns([pl.col(F.BALANCE_COLS[t]).cast(pl.Float64) for t in NET])
           .sort("ba", "ts_utc"))
    if out.height and out["ts_utc"].max() >= TEST_START:
        raise ValueError("overview balance holds a sealed-window row")
    return out


def series(carbon: pl.DataFrame, balance: pl.DataFrame, ba: str, target: str) -> pl.DataFrame:
    """`forecast`-style series (ba, ts_utc, value) as published, nulls kept."""
    if target == "ci_consumed":
        s = carbon.filter(pl.col("ba") == ba).select(
            "ba", "ts_utc", pl.col("ci_consumed_g_kwh").alias("value"))
    else:
        s = balance.filter(pl.col("ba") == ba).select(
            "ba", "ts_utc", pl.col(F.BALANCE_COLS[target]).alias("value"))
    return s.select(pl.col("ba").cast(pl.Utf8), "ts_utc",
                    pl.col("value").cast(pl.Float64)).sort("ts_utc")


# --------------------------------------------------------------------------------------------
# Forecasts (the existing forecasters, run per region)
# --------------------------------------------------------------------------------------------


def fit_series(s: pl.DataFrame, ba: str, target: str, tz: str, *,
               fit_at: datetime = F.VAL_FIT_AT, history_start: datetime = F.VAL_HISTORY_START,
               leaf_nodes=F.MAX_LEAF_NODES) -> F.Fitted:
    """`forecast.fit` with an explicit zone (same envelopes, labels, climatology and L rows)."""
    env_h = F.ENVELOPE_H[target]
    labels = F.prepare(F.as_of(s, fit_at, env_h), target).drop_nulls("value")
    clim = F.fit_climatology(labels, tz)
    out = F.Fitted(ba=ba, target=target, tz=tz, fit_at=fit_at, history_start=history_start,
                   clim=clim, train_mean=float(labels["value"].mean()), n_labels=labels.height)
    if leaf_nodes:
        feats = F.issue_features(s, target, F.issue_times(history_start, fit_at), tz)
        rows = feats.join(labels.select(pl.col("ts_utc").alias("target_ts"), "value"),
                          on="target_ts", how="inner")
        if rows.height == 0:
            raise ValueError(f"no L training rows for {ba}/{target}")
        x, y = rows.select(F.FEATURES).to_numpy(), rows["value"].to_numpy()
        out.n_train_rows = rows.height
        for m in leaf_nodes:
            out.hgb[m] = HistGradientBoostingRegressor(max_leaf_nodes=m, **F.HGB_PARAMS).fit(x, y)
    return out


def persistence(feats: pl.DataFrame, target: str) -> pl.DataFrame:
    """Baseline P: the most recent published same-hour value (<= 7 days back), else the last
    published value, clipped at 0 for non-negative targets."""
    v = np.where(np.isfinite(feats["same_hour_value"].to_numpy()),
                 feats["same_hour_value"].to_numpy(), feats["last_value"].to_numpy())
    if target in F.NONNEGATIVE:
        v = np.where(np.isfinite(v), np.maximum(v, 0.0), v)
    return feats.select("issue_ts", "target_ts").with_columns(
        pl.Series("value", v, dtype=pl.Float64).fill_nan(None))


def forecast_target(s: pl.DataFrame, ba: str, target: str, tz: str,
                    issues: list[datetime], **fit_kw) -> tuple[dict[str, pl.DataFrame], dict]:
    """Forecast frames (issue_ts, target_ts, value) for P, K, W and L (leaf chosen by MAE over
    `issues`) and their scores against the cleaned truth."""
    fitted = fit_series(s, ba, target, tz, **fit_kw)
    feats = F.issue_features(s, target, issues, tz)
    truth = F.prepare(s, target).drop_nulls("value")
    frames = {"P": persistence(feats, target)}
    for name, (model, m) in {"K": ("K", None), "W": ("W", None),
                             **{f"L{m}": ("L", m) for m in fitted.hgb}}.items():
        f, _ = F.predict(fitted, feats, model, m)
        frames[name] = f.select("issue_ts", "target_ts", "value")
    scores = {k: _score(v, truth) for k, v in frames.items()}
    leaves = sorted(fitted.hgb)
    if leaves:
        chosen = min(leaves, key=lambda m: (_key(scores[f"L{m}"]), m))
        frames["L"], scores["L"] = frames[f"L{chosen}"], scores[f"L{chosen}"]
    else:
        chosen = None
    for m in leaves:
        frames.pop(f"L{m}")
        scores.pop(f"L{m}")
    meta = {"train_mean": fitted.train_mean, "n_labels": fitted.n_labels,
            "L_max_leaf_nodes": chosen, "scores": scores}
    return frames, meta


def _key(s: dict) -> float:
    return math.inf if not s["n"] else s["mae"]


def _score(fc: pl.DataFrame, truth: pl.DataFrame) -> dict:
    j = fc.join(truth.select(pl.col("ts_utc").alias("target_ts"), pl.col("value").alias("t")),
                on="target_ts", how="inner").drop_nulls(["value", "t"])
    if j.height == 0:
        return {"n": 0, "mae": None, "bias": None}
    e = j["value"] - j["t"]
    return {"n": j.height, "mae": float(e.abs().mean()), "bias": float(e.mean())}


def best_family(scores: dict) -> str:
    """Spec §6: lowest selection MAE among W, K, L; ties go to W, then K, then L."""
    return min(F.FAMILY_ORDER, key=lambda k: (_key(scores[k]), F.FAMILY_ORDER.index(k)))


def skill(mae: float | None, base: float | None) -> float | None:
    if mae is None or base is None or base <= 0:
        return None
    return 1.0 - mae / base


# --------------------------------------------------------------------------------------------
# Net load and stress
# --------------------------------------------------------------------------------------------


def net_load_truth(balance: pl.DataFrame, ba: str) -> pl.DataFrame:
    """ts_utc, net_load_mw: cleaned demand (spike rule) - wind - solar; null where demand is."""
    b = balance.filter(pl.col("ba") == ba)
    d = F.prepare(b.select("ba", "ts_utc", pl.col(F.BALANCE_COLS["demand"]).alias("value")),
                  "demand")
    w, s = F.BALANCE_COLS["wind"], F.BALANCE_COLS["solar"]
    return d.join(b.select("ts_utc", w, s), on="ts_utc", how="left").select(
        "ts_utc", (pl.col("value") - pl.col(w).fill_null(0) - pl.col(s).fill_null(0))
        .alias("net_load_mw")).sort("ts_utc")


@dataclass(frozen=True)
class StressCDF:
    """The training-window empirical CDF of net load (spec §4): frozen at `fit_at`."""

    sorted_mw: np.ndarray
    threshold_mw: float
    n: int

    def pct(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=float)
        out = np.searchsorted(self.sorted_mw, x, side="right") / self.n * 100.0
        return np.where(np.isfinite(x), out, np.nan)


def fit_stress(net: pl.DataFrame, fit_at: datetime = F.VAL_FIT_AT,
               history_start: datetime = F.VAL_HISTORY_START) -> StressCDF:
    """Net-load hours in [history_start, fit_at) whose every component is published by fit_at
    (the slowest envelope, wind/solar)."""
    env_h = max(F.ENVELOPE_H[t] for t in NET)
    tr = net.filter((pl.col("ts_utc") >= history_start)
                    & (pl.col("ts_utc") + pl.duration(hours=1 + env_h) <= fit_at)).drop_nulls()
    v = np.sort(tr["net_load_mw"].to_numpy().astype(float))
    if v.size == 0:
        raise ValueError("no training net-load hours")
    return StressCDF(v, float(np.quantile(v, STRESS_Q)), int(v.size))


def net_forecasts(comp: dict[str, dict[str, pl.DataFrame]], model: str) -> pl.DataFrame:
    """Net-load forecast of one model: demand - wind - solar forecasts for the same issue/hour."""
    d, w, s = (comp[t][model] for t in NET)
    return (d.rename({"value": "d"}).join(w.rename({"value": "w"}), on=["issue_ts", "target_ts"])
            .join(s.rename({"value": "s"}), on=["issue_ts", "target_ts"])
            .select("issue_ts", "target_ts", (pl.col("d") - pl.col("w") - pl.col("s"))
                    .alias("value")))


def top_k_precision(fc: pl.DataFrame, truth: pl.DataFrame, k: int = RUSH_K) -> tuple[float | None, int]:
    """Mean over target days (issues) of |forecast top-k ∩ actual top-k| / k, on days whose every
    target hour has truth."""
    j = fc.join(truth.select(pl.col("ts_utc").alias("target_ts"), pl.col("net_load_mw").alias("t")),
                on="target_ts", how="left")
    hits = []
    for _, g in j.group_by("issue_ts", maintain_order=True):
        if g["t"].null_count() or g["value"].null_count() or g.height < k:
            continue
        f = set(g.sort(["value", "target_ts"], descending=[True, False]).head(k)["target_ts"])
        a = set(g.sort(["t", "target_ts"], descending=[True, False]).head(k)["target_ts"])
        hits.append(len(f & a) / k)
    return (float(np.mean(hits)) if hits else None), len(hits)


# --------------------------------------------------------------------------------------------
# Profiles and alignment (observed / modeled, the validation window)
# --------------------------------------------------------------------------------------------


def _local(frame: pl.DataFrame) -> pl.DataFrame:
    lt = pl.col("ts_utc").dt.convert_time_zone(TZ_NAME)
    return frame.with_columns(lt.dt.hour().alias("hour"), lt.dt.date().alias("date"))


def _in_window(frame: pl.DataFrame) -> pl.DataFrame:
    s, e = WINDOW
    return frame.filter((pl.col("ts_utc") >= s) & (pl.col("ts_utc") < e))


def hourly_frame(ci: pl.DataFrame, net: pl.DataFrame, cdf: StressCDF) -> pl.DataFrame:
    """Window hours: ts_utc, hour, date, ci, net_load_mw, stress_pct (nulls kept)."""
    s, e = WINDOW
    grid = pl.select(pl.datetime_range(s, e - H, interval="1h", time_unit="us",
                                       time_zone="UTC").alias("ts_utc"))
    f = (grid.join(ci.select("ts_utc", pl.col("ci_consumed_g_kwh").alias("ci")), on="ts_utc",
                   how="left")
         .join(net, on="ts_utc", how="left"))
    pct = cdf.pct(f["net_load_mw"].cast(pl.Float64).fill_null(np.nan).to_numpy())
    return _local(f.with_columns(pl.Series("stress_pct", pct).fill_nan(None)))


def day_profile(h: pl.DataFrame, col: str) -> list[float | None]:
    agg = h.drop_nulls(col).group_by("hour").agg(pl.col(col).mean().alias("v"))
    look = {r["hour"]: _r(r["v"]) for r in agg.iter_rows(named=True)}
    return [look.get(k) for k in range(24)]


def _daily_rank(h: pl.DataFrame, col: str, k: int, descending: bool) -> pl.DataFrame:
    """Each complete day's k highest (descending) or lowest hours by `col`: (ts_utc, date)."""
    full = h.group_by("date").agg(pl.col(col).null_count().alias("nn"), pl.len().alias("n"))
    ok = full.filter((pl.col("nn") == 0) & (pl.col("n") >= 23))["date"]
    d = h.filter(pl.col("date").is_in(ok.implode()))
    return (d.sort([col, "ts_utc"], descending=[descending, False])
            .group_by("date", maintain_order=True).head(k).select("ts_utc", "date"))


def alignment(h: pl.DataFrame, cdf: StressCDF) -> dict:
    both = h.drop_nulls(["ci", "net_load_mw"])
    ci_all = h.drop_nulls("ci")
    mean_ci = float(ci_all["ci"].mean())
    q75 = float(ci_all["ci"].quantile(0.75, interpolation="linear"))
    stress = both.filter(pl.col("net_load_mw") > cdf.threshold_mw)
    rush = _daily_rank(h.drop_nulls("ci"), "net_load_mw", RUSH_K, True)
    rush_ci = h.join(rush.select("ts_utc"), on="ts_utc").drop_nulls("ci")
    clean = _daily_rank(h, "ci", RUSH_K, False)
    rush_all = _daily_rank(h, "net_load_mw", RUSH_K, True)
    days = sorted(set(clean["date"]) & set(rush_all["date"]))
    cs = {d: set(g["ts_utc"]) for (d,), g in clean.partition_by("date", as_dict=True).items()}
    rs = {d: set(g["ts_utc"]) for (d,), g in rush_all.partition_by("date", as_dict=True).items()}
    overlap = [len(cs[d] & rs[d]) / RUSH_K for d in days]
    rho = (float(both.select(pl.corr("ci", "net_load_mw", method="spearman")).item())
           if both.height > 2 else None)
    s_mean = float(stress["ci"].mean()) if stress.height else None
    r_mean = float(rush_ci["ci"].mean()) if rush_ci.height else None
    return {
        "mean_ci": mean_ci,
        "q75_ci": q75,
        "n_stress_hours": stress.height,
        "stress_mean_ci": s_mean,
        "stress_vs_mean_pct": (s_mean / mean_ci - 1) * 100 if s_mean is not None else None,
        "stress_top_quartile_share": (float((stress["ci"] > q75).mean()) * 100
                                      if stress.height else None),
        "n_rush_hours": rush_ci.height,
        "rush_mean_ci": r_mean,
        "rush_vs_mean_pct": (r_mean / mean_ci - 1) * 100 if r_mean is not None else None,
        "spearman_ci_net_load": rho,
        "clean_rush_overlap_pct": float(np.mean(overlap)) * 100 if overlap else None,
        "n_overlap_days": len(overlap),
        "n_both_hours": both.height,
    }


def daily_swing(h: pl.DataFrame) -> dict:
    """Median over complete Denver days of max - min hourly intensity (and relative to the day's
    mean)."""
    g = (h.group_by("date").agg(pl.col("ci").null_count().alias("nn"), pl.len().alias("n"),
                                pl.col("ci").max().alias("hi"), pl.col("ci").min().alias("lo"),
                                pl.col("ci").mean().alias("mu"))
         .filter((pl.col("nn") == 0) & (pl.col("n") >= 23)))
    if g.height == 0:
        return {"median_g": None, "median_pct": None, "p25_g": None, "p75_g": None, "n_days": 0}
    sw = (g["hi"] - g["lo"]).to_numpy()
    rel = ((g["hi"] - g["lo"]) / g["mu"]).to_numpy() * 100
    return {"median_g": float(np.median(sw)), "median_pct": float(np.median(rel)),
            "p25_g": float(np.quantile(sw, 0.25)), "p75_g": float(np.quantile(sw, 0.75)),
            "n_days": int(g.height)}


# --------------------------------------------------------------------------------------------
# One region
# --------------------------------------------------------------------------------------------


def coverage(carbon: pl.DataFrame, balance: pl.DataFrame, ba: str) -> tuple[float, float]:
    """Share of window hours with a published intensity, and with a net load."""
    s, e = WINDOW
    n = (e - s) // H
    c = _in_window(carbon.filter(pl.col("ba") == ba))["ci_consumed_g_kwh"].drop_nulls().len()
    nl = _in_window(net_load_truth(balance, ba))["net_load_mw"].drop_nulls().len()
    return c / n, nl / n


def region(carbon: pl.DataFrame, balance: pl.DataFrame, ba: str, *,
           issues: list[datetime] | None = None, leaf_nodes=F.MAX_LEAF_NODES) -> dict:
    """Raw (unenveloped) numbers for one region."""
    tz = OVERVIEW_TZ[ba]
    issues = issues if issues is not None else F.validation_issues()[1]
    comp: dict[str, dict[str, pl.DataFrame]] = {}
    meta: dict[str, dict] = {}
    for t in TARGETS:
        comp[t], meta[t] = forecast_target(series(carbon, balance, ba, t), ba, t, tz, issues,
                                           leaf_nodes=leaf_nodes)
    models = ("P", "K", "W") + (("L",) if leaf_nodes else ())
    # consumed intensity
    ci_scores = meta["ci_consumed"]["scores"]
    ci_best = best_family(ci_scores) if leaf_nodes else min(
        ("W", "K"), key=lambda k: (_key(ci_scores[k]), ("W", "K").index(k)))
    # net load and stress
    net = net_load_truth(balance, ba)
    cdf = fit_stress(net)
    nl_truth = net.drop_nulls()
    nl_scores, st_scores, top4 = {}, {}, {}
    for m in models:
        fc = net_forecasts(comp, m)
        nl_scores[m] = _score(fc, nl_truth.rename({"net_load_mw": "value"}))
        fp = fc.with_columns(pl.Series("value", cdf.pct(
            fc["value"].fill_null(np.nan).to_numpy())).fill_nan(None))
        tp = nl_truth.with_columns(pl.Series("value", cdf.pct(nl_truth["net_load_mw"].to_numpy())))
        st_scores[m] = _score(fp, tp.select("ts_utc", "value"))
        top4[m] = top_k_precision(fc, nl_truth)
    nl_best = (best_family(nl_scores) if leaf_nodes else
               min(("W", "K"), key=lambda k: (_key(nl_scores[k]), ("W", "K").index(k))))
    h = hourly_frame(carbon.filter(pl.col("ba") == ba), net, cdf)
    return {
        "ba": ba, "tz": tz, "n_issues": len(issues),
        "ci": {"scores": ci_scores, "best": ci_best, "train_mean": meta["ci_consumed"]["train_mean"],
               "L_max_leaf_nodes": meta["ci_consumed"]["L_max_leaf_nodes"]},
        "net": {"scores": nl_scores, "stress_scores": st_scores, "top4": top4, "best": nl_best,
                "L_max_leaf_nodes": {t: meta[t]["L_max_leaf_nodes"] for t in NET},
                "train_mean_mw": float(np.mean(cdf.sorted_mw)), "threshold_mw": cdf.threshold_mw,
                "n_train_hours": cdf.n},
        "profile": {"ci": day_profile(h, "ci"), "net_load_mw": day_profile(h, "net_load_mw"),
                    "stress_pct": day_profile(h, "stress_pct")},
        "alignment": alignment(h, cdf),
        "swing": daily_swing(h),
        "n_ci_hours": h["ci"].drop_nulls().len(),
        "n_net_hours": h["net_load_mw"].drop_nulls().len(),
    }


def _region_job(args) -> dict:
    carbon, balance, ba, leaf_nodes, issues = args
    return region(carbon, balance, ba, issues=issues, leaf_nodes=leaf_nodes)


# --------------------------------------------------------------------------------------------
# The artifact
# --------------------------------------------------------------------------------------------


def _e(v, unit, ev, pid, why="not computable in the validation window"):
    v = _r(v) if not isinstance(v, list) else [_r(x) for x in v]
    missing = v is None or (isinstance(v, list) and any(x is None for x in v))
    return env(v, unit, ev, pid, status="unavailable" if v is None else "ok",
               reason=why if missing else None)


def _count(v, unit, pid):
    return env(int(v), unit, "measured", pid)


def envelope_region(r: dict) -> dict:
    ba = r["ba"]
    p = f"{PROV}:{ba}"
    ci, net, al, sw = r["ci"], r["net"], r["alignment"], r["swing"]
    b_ci, b_nl = ci["best"], net["best"]

    def models(scores, unit, pid):
        return {m: {"mae": _e(s["mae"], unit, "measured", f"{pid}:{m}:mae"),
                    "bias": _e(s["bias"], unit, "measured", f"{pid}:{m}:bias"),
                    "n_hours": _count(s["n"], "hours", f"{pid}:{m}:n")}
                for m, s in scores.items()}

    def sk(scores, best, pid):
        return {"vs_persistence": _e(skill(scores[best]["mae"], scores["P"]["mae"]), "fraction",
                                     "measured", f"{pid}:skill_vs_P"),
                "vs_climatology": _e(skill(scores[best]["mae"], scores["K"]["mae"]), "fraction",
                                     "measured", f"{pid}:skill_vs_K")}

    return {
        "ba": ba, "name": NAMES[ba], "tz_forecast_calendar": r["tz"],
        "interconnection": INTERCONNECT.get(ba, "Western"),
        "core_site": ba in CORE_BAS,
        "forecast": {
            "ci": {
                "model": b_ci,
                "unit": "g/kWh",
                "mae": _e(ci["scores"][b_ci]["mae"], "g/kWh", "measured", f"{p}:ci:mae"),
                "nmae": _e(ci["scores"][b_ci]["mae"] / ci["train_mean"]
                           if ci["scores"][b_ci]["mae"] is not None else None, "fraction",
                           "measured", f"{p}:ci:nmae"),
                "skill": sk(ci["scores"], b_ci, f"{p}:ci"),
                "models": models(ci["scores"], "g/kWh", f"{p}:ci"),
                "L_max_leaf_nodes": _maybe_assumed(ci["L_max_leaf_nodes"], f"{p}:ci:L_leaf"),
            },
            "net_load": {
                "model": b_nl,
                "unit": "MW",
                "mae": _e(net["scores"][b_nl]["mae"], "MW", "measured", f"{p}:nl:mae"),
                "nmae": _e(net["scores"][b_nl]["mae"] / net["train_mean_mw"]
                           if net["scores"][b_nl]["mae"] is not None else None, "fraction",
                           "measured", f"{p}:nl:nmae"),
                "skill": sk(net["scores"], b_nl, f"{p}:nl"),
                "models": models(net["scores"], "MW", f"{p}:nl"),
                "L_max_leaf_nodes": {t: _maybe_assumed(v, f"{p}:nl:{t}:L_leaf")
                                     for t, v in net["L_max_leaf_nodes"].items()},
            },
            "stress": {
                "model": b_nl,
                "mae": _e(net["stress_scores"][b_nl]["mae"], "percentile points", "measured",
                          f"{p}:st:mae"),
                "skill": sk(net["stress_scores"], b_nl, f"{p}:st"),
                "models": models(net["stress_scores"], "percentile points", f"{p}:st"),
                "top4_precision": {m: {"precision": _e(v[0], "fraction", "measured",
                                                   f"{p}:st:{m}:top4"),
                                       "n_days": _count(v[1], "days", f"{p}:st:{m}:top4_n")}
                                   for m, v in net["top4"].items()},
                "threshold_mw": _e(net["threshold_mw"], "MW", "modeled", f"{p}:st:threshold"),
                "n_train_hours": _count(net["n_train_hours"], "hours", f"{p}:st:n_train"),
            },
        },
        "profile": {
            "ci": _e(r["profile"]["ci"], "g/kWh", "modeled", f"{p}:prof:ci",
                     "no published hour at this clock hour"),
            "net_load_mw": _e(r["profile"]["net_load_mw"], "MW", "observed", f"{p}:prof:nl",
                              "no net-load hour at this clock hour"),
            "stress_pct": _e(r["profile"]["stress_pct"], "percentile", "modeled", f"{p}:prof:st",
                             "no net-load hour at this clock hour"),
            "n_ci_hours": _count(r["n_ci_hours"], "hours", f"{p}:prof:n_ci"),
            "n_net_hours": _count(r["n_net_hours"], "hours", f"{p}:prof:n_nl"),
        },
        "alignment": {
            "mean_ci": _e(al["mean_ci"], "g/kWh", "modeled", f"{p}:al:mean"),
            "stress_mean_ci": _e(al["stress_mean_ci"], "g/kWh", "modeled", f"{p}:al:stress_mean",
                                 "no hour above the training 95th percentile"),
            "stress_vs_mean_pct": _e(al["stress_vs_mean_pct"], "%", "modeled", f"{p}:al:stress_pct",
                                     "no hour above the training 95th percentile"),
            "stress_top_quartile_share": _e(al["stress_top_quartile_share"], "%", "modeled",
                                            f"{p}:al:stress_q4",
                                            "no hour above the training 95th percentile"),
            "n_stress_hours": _count(al["n_stress_hours"], "hours", f"{p}:al:n_stress"),
            "rush_mean_ci": _e(al["rush_mean_ci"], "g/kWh", "modeled", f"{p}:al:rush_mean"),
            "rush_vs_mean_pct": _e(al["rush_vs_mean_pct"], "%", "modeled", f"{p}:al:rush_pct"),
            "n_rush_hours": _count(al["n_rush_hours"], "hours", f"{p}:al:n_rush"),
            "spearman_ci_net_load": _e(al["spearman_ci_net_load"], "rho", "modeled",
                                       f"{p}:al:rho"),
            "clean_rush_overlap_pct": _e(al["clean_rush_overlap_pct"], "%", "modeled",
                                         f"{p}:al:overlap"),
            "n_overlap_days": _count(al["n_overlap_days"], "days", f"{p}:al:n_days"),
        },
        "swing": {
            "median_g": _e(sw["median_g"], "g/kWh", "modeled", f"{p}:sw:median"),
            "median_pct": _e(sw["median_pct"], "%", "modeled", f"{p}:sw:median_pct"),
            "p25_g": _e(sw["p25_g"], "g/kWh", "modeled", f"{p}:sw:p25"),
            "p75_g": _e(sw["p75_g"], "g/kWh", "modeled", f"{p}:sw:p75"),
            "n_days": _count(sw["n_days"], "days", f"{p}:sw:n"),
        },
    }


def _maybe_assumed(v, pid):
    if v is None:
        return env(None, "leaves", "assumed", pid, status="not_run", reason="L not fitted")
    return env(int(v), "leaves", "assumed", pid)


def build_overview(carbon: pl.DataFrame, balance: pl.DataFrame, *,
                   bas: tuple[str, ...] = OVERVIEW_BAS, leaf_nodes=F.MAX_LEAF_NODES,
                   workers: int = 1, issues: list[datetime] | None = None) -> dict:
    """The enveloped overview artifact. Regions below MIN_COVERAGE are listed under `dropped`."""
    for name, fr in (("carbon", carbon), ("balance", balance)):
        if fr.height and fr["ts_utc"].max() >= TEST_START:
            raise ValueError(f"{name}: input holds sealed rows (ts >= {TEST_START})")
    kept, dropped = [], []
    for ba in bas:
        c, n = coverage(carbon, balance, ba)
        if c < MIN_COVERAGE or n < MIN_COVERAGE:
            dropped.append({"ba": ba, "name": NAMES.get(ba, ba),
                            "reason": f"insufficient validation data: {c:.0%} of hours with a "
                                      f"published intensity, {n:.0%} with net load (need "
                                      f"{MIN_COVERAGE:.0%})"})
        else:
            kept.append(ba)
    iss = issues if issues is not None else F.validation_issues()[1]
    if workers > 1 and len(kept) > 1:
        with ProcessPoolExecutor(max_workers=min(workers, len(kept)),
                                 mp_context=mp.get_context("spawn")) as ex:
            raw = list(ex.map(_region_job, [(carbon.filter(pl.col("ba") == b),
                                             balance.filter(pl.col("ba") == b), b, leaf_nodes, iss)
                                            for b in kept]))
    else:
        raw = [region(carbon, balance, b, issues=iss, leaf_nodes=leaf_nodes) for b in kept]
    s, e = WINDOW
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "overview",
        "window": {"start": iso(s), "end": iso(e), "name": "validation",
                   "note": "validation year to the selection cutoff; the test year is sealed"},
        "forecast_issues": {
            "rule": "daily at 10:00 America/Denver for the next Utah civil day (forecast.py)",
            "first": iso(iss[0]) if iss else None, "last": iso(iss[-1]) if iss else None,
            "n": env(len(iss), "issues", "measured", f"{PROV}:n_issues"),
            "fit_at": iso(F.VAL_FIT_AT), "history_start": iso(F.VAL_HISTORY_START),
            "envelope_h": {k: env(v, "hours", "assumed", f"{PROV}:envelope:{k}")
                           for k, v in F.ENVELOPE_H.items()},
        },
        "tz_display": TZ_NAME,
        "hour_index": "index i of every 24-value profile is the America/Denver clock hour i",
        "parameters": {
            "stress_quantile": env(STRESS_Q, "fraction", "assumed", f"{PROV}:stress_q"),
            "rush_hours_per_day": env(RUSH_K, "hours", "assumed", f"{PROV}:rush_k"),
            "min_coverage": env(MIN_COVERAGE, "fraction", "assumed", f"{PROV}:min_cov"),
        },
        "definitions": {
            "ci": "EIA consumption-basis CO2 intensity (BA workbooks), tier 1 only: hours EIA "
                  "publishes; no fills. An EIA estimate, hence modeled",
            "net_load": "EIA-930 adjusted demand (isolated spikes removed) - wind - solar; a "
                        "grid-stress proxy, not transmission congestion",
            "stress": "net load's percentile in the region's training-window CDF (2022-01-01 to "
                      "the 2024-10-29 fit, published by the fit); a stress hour is above its "
                      "95th percentile",
            "rush_hours": "each complete day's 4 highest-net-load hours (America/Denver days)",
            "models": "P same-hour persistence (baseline), K calendar climatology (baseline), "
                      "W weekly seasonal, L gradient boosting; the region's model is the best of "
                      "W, K, L by selection MAE (spec §6 tie order W, K, L)",
            "skill": "1 - MAE(model) / MAE(baseline) on the same issued hours; > 0 beats the "
                     "baseline",
            "top4_precision": "mean daily share of the forecast's 4 highest-net-load hours that "
                              "are among the actual 4",
            "swing": "per complete America/Denver day, dirtiest minus cleanest hourly intensity; "
                     "median over days",
            "clean_rush_overlap": "mean daily share of the 4 cleanest hours that are also rush "
                                  "hours; 17% is the chance level (4 of 24)",
        },
        "limitations": [
            ("Validation results are development evidence: the validation year was profiled "
             "before the design, and the same window selects each region's model and scores it."),
            F.LIMITATION,
            ("Overview regions get the forecast skill and profiles only; the router's experiment "
             "runs on the four core sites (PACE, BPAT, CISO, NEVP)."),
            ("EIA's consumption-basis intensity assigns imports from Canada and Mexico the "
             "average US emissions rate (EIA-930 convention)."),
        ],
        "order": kept,
        "regions": {r["ba"]: envelope_region(r) for r in raw},
        "dropped": dropped,
    }


def input_hashes(bas: tuple[str, ...] = OVERVIEW_BAS) -> dict[str, str]:
    """sha256 of every input file (recorded in the run's config)."""
    paths = {"carbon_hourly.parquet": CARBON_PATH, "balance.parquet": F.BALANCE_PATH}
    paths |= {f"ba_workbooks/{b}.xlsx": WORKBOOK_DIR / f"{b}.xlsx" for b in bas if b not in CORE_BAS}
    return {k: F._sha256(p) for k, p in paths.items() if p.exists()}
