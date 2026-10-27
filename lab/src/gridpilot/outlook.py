"""The grid outlook (Stage 3 T19): a multi-day consumed-CO2 outlook for Utah (PACE) and its move
destinations (BPAT, CISO, NEVP), with what the deployed router would recommend.

**Horizon.** An outlook is issued at a 10:00 America/Denver instant (as the day-ahead forecasts
are, `gridpilot.forecast`). Horizon day ``d`` (1..7) is the Utah civil day ``d`` days after the
issue's local date; day 1 is the existing day-ahead target. Consumed CO2 intensity is published
with an assumed 96 h envelope (``forecast.ENVELOPE_H``), so at issue the newest usable hour is
about four days old and day ``d`` sits 14 + 24 d to 38 + 24 d hours past the issue.

**Models** (per BA), all frozen at ``fit_at``:

* ``K``  the calendar climatology of ``gridpilot.forecast`` (horizon-independent);
* ``W``  the weekly seasonal median of the 168/336/504/672 h lags that are published at the
  issue (fewer lags as the horizon grows), ``K`` if none is;
* ``Lh15`` / ``Lh31``  a multi-horizon HistGradientBoosting model on the same issue-time
  features (``forecast.l_features``; ``lead_h`` carries the horizon), trained on days 1..7 of
  every training issue. It is a new model for the outlook, not the frozen day-ahead L.

**Skill by horizon** (``skill_by_horizon``) is measured on the validation issues
[VALIDATION_START, SELECTION_END) whose seven target days end before TEST_START: MAE per
(BA, day, model), the skill ``1 - MAE / MAE_K`` of the best model with a 90% issue-block
bootstrap interval, and the p10/p90 residual quantiles of the best model (the forecast bands).
The interval is a circular block bootstrap over consecutive issues (7-day blocks; 14-day
blocks reported too), because day-to-day forecast errors are correlated. A (BA, day) is shown
as a forecast only when the 7-day-block interval's lower end is above zero; otherwise the outlook
shows climatology, flagged ``climatology_only``. Model choice and bands come from the
same validation issues they are scored on (development evidence, like the validation run).

**Leakage.** ``build_outlook`` reads nothing published after the issue: it cuts its input with
``forecast.as_of`` and ``l_features`` raises ``LeakageError`` on any later row. Without
``live=True`` an issue whose horizon reaches TEST_START is refused (``OutlookSealError``).

**Live mode** (after the seal has opened, T13): the newest weeks come from a fresh EIA download
into the run directory (never ``data/raw``, so the frozen snapshot does not change), read through
``live_read``, which refuses unless live mode is on, the seal has opened (``seal_opened``) and
the path is such a download. It follows ``sealed_read``'s protocol (read the bytes once, sha256,
append one fsynced JSONL line with the purpose to ``results/outlook_reads.jsonl``, parse the same
bytes). A site whose newest row is more than 7 days old is refused (``check_fresh``). The model
fits only ever use pre-seal rows (``drop_sealed``).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingRegressor

from gridpilot import forecast as fc
from gridpilot import seal
from gridpilot.eval.bootstrap import block_indices
from gridpilot.paths import REPO_ROOT, RESULTS_DIR
from gridpilot.results import env, iso, validate_artifact
from gridpilot.splits import TEST_START, VALIDATION_START

TARGET = "ci_consumed"
ENV_H = fc.ENVELOPE_H[TARGET]
SITES = ("PACE", "BPAT", "CISO", "NEVP")
HOME = "PACE"
MAX_DAYS = 7
LH_LEAVES = (15, 31)
MODELS = ("K", "W", *(f"Lh{m}" for m in LH_LEAVES))
UNIT = "g/kWh"
BLOCK_H = 4  # the time-shift view: the cleanest contiguous 4-hour block of each day
N_BOOT = 2000
BLOCK_DAYS = 7  # primary block (issues are daily); BLOCK_DAYS_ALT is reported alongside
BLOCK_DAYS_ALT = 14
SEED = 20261027
LIVE_LOG_NAME = "outlook_reads.jsonl"
H = timedelta(hours=1)
_RUN_ID = re.compile(r"^\d{8}T\d{6}Z$")
ISSUE_TZ = fc.ISSUE_TZ
LIMITATIONS = (
    fc.LIMITATION,
    ("EIA's consumption-basis intensity assigns imports from Canada and Mexico the average US "
    "emissions rate (EIA-930 convention)."),
    ("Skill, model choice and the p10/p90 bands are measured on the validation issues "
    "(Nov 2024 to Oct 2025) and assumed to transfer to the issue shown."),
    ("Policy S ranks regions by a fixed training mean; it does not read this forecast. The "
    "forecast-cleanest region and the cleanest hours are the time-shift view, not S's choice."),
)


class OutlookSealError(PermissionError):
    """An outlook read or issue would reach the sealed window outside live mode."""


# --------------------------------------------------------------------------- horizon


def day_hours(issue: datetime, d: int) -> list[datetime]:
    """UTC hour starts of the Utah civil day ``d`` days after the issue's local date."""
    day = fc._aware(issue, "issue").astimezone(ISSUE_TZ).date() + timedelta(days=d)
    s = datetime.combine(day, time(0), ISSUE_TZ).astimezone(UTC)
    e = datetime.combine(day + timedelta(days=1), time(0), ISSUE_TZ).astimezone(UTC)
    return [s + k * H for k in range((e - s) // H)]


def horizon_hours(issue: datetime, days: int = MAX_DAYS) -> tuple[list[datetime], list[int]]:
    ts, dd = [], []
    for d in range(1, days + 1):
        h = day_hours(issue, d)
        ts += h
        dd += [d] * len(h)
    return ts, dd


def latest_issue(now: datetime) -> datetime:
    """The latest 10:00 America/Denver instant at or before ``now``."""
    local = fc._aware(now, "now").astimezone(ISSUE_TZ)
    i = datetime.combine(local.date(), time(fc.ISSUE_HOUR), ISSUE_TZ)
    if i > local:
        i = datetime.combine(local.date() - timedelta(days=1), time(fc.ISSUE_HOUR), ISSUE_TZ)
    return i.astimezone(UTC)


def horizon_features(series: pl.DataFrame, issue: datetime, tz: str,
                     days: int = MAX_DAYS) -> pl.DataFrame:
    """Issue-time features for every hour of days 1..``days`` (one BA's series as published).
    ``series`` is cut with ``as_of`` here, so nothing published after the issue is used."""
    issue = fc._aware(issue, "issue")
    span = pl.duration(hours=fc.WINDOW_H + ENV_H + 2)
    hist = fc.as_of(series.filter(pl.col("ts_utc") >= pl.lit(issue) - span), issue, ENV_H)
    ts, dd = horizon_hours(issue, days)
    f = fc.l_features(hist, issue, ENV_H, tz, target=TARGET, targets=ts)
    return f.with_columns(pl.lit(issue).cast(pl.Datetime("us", "UTC")).alias("issue_ts"),
                          pl.Series("day", dd, dtype=pl.Int8))


def features_for(series: pl.DataFrame, issues: Sequence[datetime], tz: str,
                 days: int = MAX_DAYS) -> pl.DataFrame:
    frames = [horizon_features(series, i, tz, days) for i in issues]
    return pl.concat(frames).select("issue_ts", "day", "target_ts", *fc.FEATURES)


# --------------------------------------------------------------------------- models


@dataclass
class Models:
    """K (climatology) and the multi-horizon boosters, frozen at ``fit_at`` for one BA."""

    ba: str
    tz: str
    fit_at: datetime
    history_start: datetime
    clim: fc.Climatology
    hgb: dict[int, HistGradientBoostingRegressor] = field(default_factory=dict)
    n_train_rows: int = 0

    def predict(self, feats: pl.DataFrame, model: str) -> np.ndarray:
        if feats.height and feats["issue_ts"].min() < self.fit_at:
            raise fc.LeakageError("an issue precedes fit_at: the frozen model saw later labels")
        k = fc.predict_climatology(self.clim, feats["target_ts"])
        if model == "K":
            v = k
        elif model == "W":
            v = np.where(feats["n_lags"].to_numpy() > 0, feats["lag_median"].to_numpy(), k)
        elif model.startswith("Lh"):
            m = int(model[2:])
            v = (self.hgb[m].predict(feats.select(fc.FEATURES).to_numpy()) if feats.height
                 else np.array([]))
        else:
            raise ValueError(f"unknown model {model!r}")
        return np.maximum(np.asarray(v, dtype=float), 0.0)


def fit_models(series: pl.DataFrame, ba: str, fit_at: datetime, history_start: datetime,
               leaves: Sequence[int] = LH_LEAVES) -> Models:
    """Fit K and the multi-horizon boosters on labels published by ``fit_at``. Training rows:
    days 1..7 of every issue in [history_start, fit_at) whose label is published by fit_at."""
    tz = fc.BA_TZ[ba]
    s = fc._one_ba(series, ba, history_start)
    labels = fc.as_of(s, fit_at, ENV_H).drop_nulls("value").filter(pl.col("value").is_not_nan())
    clim = fc.fit_climatology(labels, tz)
    out = Models(ba=ba, tz=tz, fit_at=fit_at, history_start=history_start, clim=clim)
    if leaves:
        train = fc.issue_times(history_start, fit_at)
        feats = features_for(s, train, tz)
        rows = feats.join(labels.select(pl.col("ts_utc").alias("target_ts"), "value"),
                          on="target_ts", how="inner")
        x, y = rows.select(fc.FEATURES).to_numpy(), rows["value"].to_numpy()
        out.n_train_rows = rows.height
        for m in leaves:
            out.hgb[m] = HistGradientBoostingRegressor(max_leaf_nodes=m, **fc.HGB_PARAMS).fit(x, y)
    return out


# --------------------------------------------------------------------------- skill


def skill_issues() -> list[datetime]:
    """Validation issues in [VALIDATION_START, SELECTION_END) whose 7 target days end before
    TEST_START."""
    out = []
    for i in fc.issue_times(VALIDATION_START, fc.SELECTION_END):
        if day_hours(i, MAX_DAYS)[-1] + H <= TEST_START:
            out.append(i)
    return out


def _boot_skill(err: pl.DataFrame, model: str, block: int) -> tuple[float, float]:
    """90% circular block bootstrap interval of 1 - MAE_model / MAE_K over consecutive issues
    (``gridpilot.eval.bootstrap.block_indices``: blocks of ``block`` issues, i.e. days, so the
    day-to-day correlation of the errors is kept; fixed seed, N_BOOT replicates)."""
    per = err.group_by("issue_ts").agg(pl.col(model).sum().alias("m"),
                                       pl.col("K").sum().alias("k")).sort("issue_ts")
    m, k = per["m"].to_numpy(), per["k"].to_numpy()
    idx = block_indices(len(m), block, N_BOOT, SEED)
    s = 1.0 - m[idx].sum(axis=1) / k[idx].sum(axis=1)
    return float(np.quantile(s, 0.05)), float(np.quantile(s, 0.95))


def skill_by_horizon(series: pl.DataFrame, models: dict[str, Models],
                     issues: Sequence[datetime] | None = None) -> dict:
    """Per (BA, day): MAE of every model, the best model, its skill over K with a 90% interval,
    the residual p10/p90 (truth - forecast) and the issue count. Validation rows only."""
    issues = list(issues if issues is not None else skill_issues())
    if not issues:
        raise ValueError("no skill issue")
    issues = sorted(issues)
    if day_hours(issues[-1], MAX_DAYS)[-1] + H > TEST_START:
        raise OutlookSealError("a skill target reaches the sealed window")
    out: dict = {}
    for ba, mod in models.items():
        s = fc._one_ba(series, ba, mod.history_start)
        if s.height and s["ts_utc"].max() >= TEST_START:
            raise OutlookSealError("skill series holds a sealed-window row")
        feats = features_for(s, issues, mod.tz)
        preds = {m: mod.predict(feats, m) for m in MODELS if m[:2] != "Lh" or int(m[2:]) in mod.hgb}
        truth = s.drop_nulls("value").filter(pl.col("value").is_not_nan()).select(
            pl.col("ts_utc").alias("target_ts"), pl.col("value").alias("truth"))
        frame = feats.select("issue_ts", "day", "target_ts").with_columns(
            *[pl.Series(m, v) for m, v in preds.items()]).join(truth, on="target_ts", how="inner")
        err = frame.with_columns(*[(pl.col(m) - pl.col("truth")).abs().alias(m) for m in preds])
        res = frame.with_columns(*[(pl.col("truth") - pl.col(m)).alias(m) for m in preds])
        out[ba] = {}
        for d in range(1, MAX_DAYS + 1):
            e, r = err.filter(pl.col("day") == d), res.filter(pl.col("day") == d)
            mae = {m: float(e[m].mean()) for m in preds}
            best = min(preds, key=lambda m: (mae[m], MODELS.index(m)))
            lo, hi = (_boot_skill(e, best, BLOCK_DAYS) if best != "K" else (0.0, 0.0))
            alt = (_boot_skill(e, best, BLOCK_DAYS_ALT) if best != "K" else (0.0, 0.0))
            out[ba][d] = {
                "mae": mae, "best": best, "skill": 1.0 - mae[best] / mae["K"],
                "skill_ci90": (lo, hi), "skill_ci90_b14": alt, "n_hours": e.height,
                "n_issues": e["issue_ts"].n_unique(),
                "status": "forecast" if best != "K" and lo > 0 else "climatology_only",
                # bands of the model the outlook shows (K when the day is climatology only)
                "q": {m: (float(r[m].quantile(0.10)), float(r[m].quantile(0.90))) for m in preds},
                "coverage_split": _split_coverage(r, best if best != "K" and lo > 0 else "K"),
            }
    return out


def _split_coverage(res: pl.DataFrame, model: str) -> float:
    """Out-of-fold p10-p90 coverage: quantiles from one half of the issues (by issue month
    parity), coverage measured on the other half, averaged over both folds."""
    odd = res["issue_ts"].dt.month() % 2 == 1
    cov = []
    for a, b in ((odd, ~odd), (~odd, odd)):
        fit, ev = res.filter(a)[model], res.filter(b)[model]
        if fit.len() == 0 or ev.len() == 0:
            continue
        lo, hi = fit.quantile(0.10), fit.quantile(0.90)
        cov.append(float(((ev >= lo) & (ev <= hi)).mean()))
    return float(np.mean(cov)) if cov else float("nan")


def _coverage_env(x: float, pid: str) -> dict:
    if np.isfinite(x):
        return env(x, "fraction", "measured", pid)
    return env(None, "fraction", "measured", pid, status="not_evaluated",
               reason="the skill issues span one month parity only: no out-of-fold split")


def days_to_show(skill: dict, site: str = HOME) -> int:
    """The longest prefix of days on which the home site has skill over climatology."""
    n = 0
    for d in range(1, MAX_DAYS + 1):
        if skill[site][d]["status"] != "forecast":
            break
        n = d
    return n


# --------------------------------------------------------------------------- outlook


def _local(t: datetime, tz: str = "America/Denver") -> str:
    return t.astimezone(ZoneInfo(tz)).isoformat()


def build_outlook(series: pl.DataFrame, models: dict[str, Models], skill: dict,
                  issue: datetime, *, days: int, ranking: Sequence[str],
                  ranking_means: dict[str, float], ranking_note: str, live: bool = False,
                  run_id: str, meta: dict | None = None,
                  extra_limitations: Sequence[str] = ()) -> dict:
    """The outlook artifact for ``issue``: per region and hour the forecast with p10/p90 bands,
    per day the router's view. ``series`` is cut at the issue (``as_of``); every input row
    published after the issue is ignored, and any that reaches a forecaster raises."""
    issue = fc._aware(issue, "issue")
    if not 1 <= days <= MAX_DAYS:
        raise ValueError(f"days must be in 1..{MAX_DAYS}")
    ts_all, _ = horizon_hours(issue, days)
    if not live and (issue >= TEST_START or ts_all[-1] + H > TEST_START):
        raise OutlookSealError(
            f"issue {iso(issue)} with {days} day(s) reaches the sealed window "
            f"(TEST_START {iso(TEST_START)}); a live outlook needs --live after the seal opens")
    series = fc.as_of(series, issue, ENV_H)  # the leakage boundary: nothing published later
    pid = f"outlook:{run_id}"
    regions, per_day = {}, {d: {} for d in range(1, days + 1)}
    for ba in SITES:
        mod = models[ba]
        s = fc._one_ba(series, ba, mod.history_start)
        feats = horizon_features(s, issue, mod.tz, days)
        k = mod.predict(feats, "K")
        p50, p10, p90 = (np.empty(feats.height) for _ in range(3))
        used: list[str] = []
        day_col = feats["day"].to_numpy()
        for d in range(1, days + 1):
            sk = skill[ba][d]
            m = sk["best"] if sk["status"] == "forecast" else "K"
            sel = day_col == d
            v = (mod.predict(feats.filter(pl.col("day") == d), m) if m != "K" else k[sel])
            lo, hi = sk["q"][m]
            p50[sel], p10[sel], p90[sel] = v, np.maximum(v + lo, 0.0), np.maximum(v + hi, 0.0)
            used.append(m)
        last_pub = s["ts_utc"].max() if s.height else None
        regions[ba] = {
            "tz": fc.BA_TZ[ba],
            "last_published_hour_utc": iso(last_pub) if last_pub else None,
            "p50": env(p50.tolist(), UNIT, "forecast", f"{pid}:{ba}:p50"),
            "p10": env(p10.tolist(), UNIT, "forecast", f"{pid}:{ba}:p10"),
            "p90": env(p90.tolist(), UNIT, "forecast", f"{pid}:{ba}:p90"),
            "climatology": env(k.tolist(), UNIT, "modeled", f"{pid}:{ba}:K"),
        }
        for d in range(1, days + 1):
            sel = day_col == d
            v = p50[sel]
            hrs = feats["target_ts"].to_list()
            hrs = [h for h, ok in zip(hrs, sel, strict=True) if ok]
            j = int(np.argmin(np.convolve(v, np.ones(BLOCK_H) / BLOCK_H, mode="valid")))
            sk = skill[ba][d]
            per_day[d][ba] = {
                "status": sk["status"], "model": used[d - 1],
                "mean": env(float(v.mean()), UNIT, "forecast", f"{pid}:{ba}:d{d}:mean"),
                "cleanest_block": {
                    "start_utc": iso(hrs[j]), "start_denver": _local(hrs[j]),
                    "hours": env(BLOCK_H, "h", "assumed", f"{pid}:block_h"),
                    "mean": env(float(v[j:j + BLOCK_H].mean()), UNIT, "forecast",
                                f"{pid}:{ba}:d{d}:block"),
                },
                # the skill of the model shown (climatology shown: 0 by definition)
                "skill_vs_climatology": env(sk["skill"] if used[d - 1] != "K" else 0.0,
                                            "fraction", "measured", f"{pid}:{ba}:d{d}:skill"),
                # the best model's point estimate, shown only with "not distinguishable" when
                # its interval includes zero
                "best_model_skill": env(sk["skill"], "fraction", "measured",
                                        f"{pid}:{ba}:d{d}:best_skill"),
                "best_model_skill_ci90": env(list(sk["skill_ci90"]), "fraction", "measured",
                                             f"{pid}:{ba}:d{d}:best_skill_ci90"),
            }
    ts_iso = [iso(t) for t in ts_all]
    day_rows = []
    for d in range(1, days + 1):
        hrs = day_hours(issue, d)
        r = per_day[d]
        clean = min(SITES, key=lambda b: (r[b]["mean"]["value"], b))
        s_pick = next(iter(ranking))
        day_rows.append({
            "day": f"D+{d}", "date_local": hrs[0].astimezone(ISSUE_TZ).date().isoformat(),
            "first_hour_utc": iso(hrs[0]),
            "status": r[HOME]["status"],
            "router_s_pick": s_pick,
            "router_s_note": "S sends a movable job to the first ranked region with an on-time "
                             "start; capacity is assumed available here",
            "forecast_cleanest_region": clean,
            "s_agrees_with_forecast": clean == s_pick,
            "home_cleanest_block": r[HOME]["cleanest_block"],
            "regions": r,
        })
    skill_rows = {ba: {str(d): {
        "best_model": skill[ba][d]["best"], "status": skill[ba][d]["status"],
        "skill": env(skill[ba][d]["skill"], "fraction", "measured", f"{pid}:{ba}:d{d}:skill"),
        "skill_ci90": env(list(skill[ba][d]["skill_ci90"]), "fraction", "measured",
                          f"{pid}:{ba}:d{d}:skill_ci90"),
        "skill_ci90_b14": env(list(skill[ba][d]["skill_ci90_b14"]), "fraction", "measured",
                              f"{pid}:{ba}:d{d}:skill_ci90_b14"),
        "mae": {m: env(v, UNIT, "measured", f"{pid}:{ba}:d{d}:mae:{m}")
                for m, v in skill[ba][d]["mae"].items()},
        "band_coverage_out_of_fold": _coverage_env(skill[ba][d]["coverage_split"],
                                                   f"{pid}:{ba}:d{d}:coverage"),
        "n_issues": env(skill[ba][d]["n_issues"], "issues", "measured", f"{pid}:{ba}:d{d}:n"),
    } for d in range(1, MAX_DAYS + 1)} for ba in SITES}
    return {
        "schema_version": "gridpilot.results.v1",
        "kind": "outlook",
        "window": "live" if live else "validation",
        "demo": not live,
        "title": "Grid outlook",
        "note": ("live outlook from a fresh EIA download" if live else
                 "validation-dated demo: the issue is a past validation date, not today; the live "
                 "run replaces this file after the seal opens"),
        "run_id": run_id,
        "issue_utc": iso(issue), "issue_denver": _local(issue),
        "envelope_h": env(ENV_H, "h", "assumed", f"{pid}:envelope"),
        "days_shown": env(days, "days", "assumed", f"{pid}:days_shown"),
        "days_with_skill_home": env(days_to_show(skill), "days", "measured",
                                    f"{pid}:days_with_skill"),
        "days_rule": ("a (region, day) is a forecast when its best validation model beats "
                      "climatology with a 90% block-bootstrap interval (7-day blocks) above zero; "
                      "otherwise it "
                      "shows climatology, flagged climatology_only. days_with_skill_home is the "
                      "longest such run from day 1 for Utah (PACE)"),
        "sites": list(SITES), "home": HOME,
        "hours_utc": ts_iso,
        "regions": regions,
        "days": day_rows,
        "router": {
            "deployed_policy": "S",
            "s_ranking": list(ranking),
            "s_ranking_mean_ci": {b: env(ranking_means[b], UNIT, "modeled", f"{pid}:rank:{b}")
                                  for b in ranking},
            "note": ranking_note,
        },
        "skill_by_horizon": skill_rows,
        "skill_interval": {"method": "circular block bootstrap over consecutive daily issues",
                           "block_days": env(BLOCK_DAYS, "days", "assumed", f"{pid}:block"),
                           "block_days_alt": env(BLOCK_DAYS_ALT, "days", "assumed",
                                                 f"{pid}:block_alt"),
                           "reps": env(N_BOOT, "replicates", "assumed", f"{pid}:reps"),
                           "level": env(0.9, "fraction", "assumed", f"{pid}:level"),
                           "seed": str(SEED)},
        "skill_issues_rule": ("validation issues from 2024-11-01 (before 2025-10-24) whose 7 "
                              "target days end before the seal"),
        "limitations": [*LIMITATIONS, *extra_limitations],
        "lineage": meta or {},
    }


# --------------------------------------------------------------------------- live reads


FRESH_DAYS = 7  # live rows older than this before the issue are refused (stale download)
LIVE_ROOT = REPO_ROOT / "runs" / "outlook"


def seal_opened(results_dir: Path = RESULTS_DIR, repo_root: Path = REPO_ROOT) -> bool:
    """True once T13 has run: a completed test run (results/test/manifest.json), a non-empty
    read log (results/test_reads.jsonl) and the annotated freeze tag ``config-freeze`` present
    in the local repository."""
    results_dir = Path(results_dir)
    if not (results_dir / "test" / seal.COMPLETED_MARKER).is_file():
        return False
    log = results_dir / Path(seal.READ_LOG_REL).name
    if not log.is_file() or not log.read_text().strip():
        return False
    tag = subprocess.run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{seal.FREEZE_TAG}"],
                         cwd=repo_root, capture_output=True, text=True, check=False)
    return tag.returncode == 0 and bool(tag.stdout.strip())


def _git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True,
                          text=True, check=False).stdout.strip()


def _caller() -> str:
    f = sys._getframe(2)
    return f"{f.f_globals.get('__name__', '?')}:{f.f_code.co_name}:{f.f_lineno}"


def _check_live_path(path: Path, live_root: Path) -> None:
    """Only a fresh download inside an outlook run directory: <live_root>/<UTC run id>/raw/<file>."""
    try:
        rel = path.resolve().relative_to(Path(live_root).resolve())
    except ValueError:
        raise OutlookSealError(f"live_read reads only fresh downloads under {live_root}; "
                               f"refused {path}") from None
    parts = rel.parts
    if len(parts) != 3 or parts[1] != "raw" or not _RUN_ID.match(parts[0]):
        raise OutlookSealError(f"live_read reads only <run id>/raw/<file> under {live_root}; "
                               f"refused {path}")


def live_read(path: Path | str, *, purpose: str, columns: Sequence[str],
              time_range: tuple[datetime, datetime], live: bool,
              reader: Callable[[io.BytesIO], pl.DataFrame],
              results_dir: Path = RESULTS_DIR, repo_root: Path = REPO_ROOT,
              live_root: Path = LIVE_ROOT, ts_col: str = "ts_utc") -> pl.DataFrame:
    """The only outlook read that may return rows at or after TEST_START.

    Refuses unless ``live`` is set, the seal has opened (``seal_opened``) and ``path`` is a fresh
    download inside an outlook run directory (never a frozen input under the data dir). It reads
    the bytes once, hashes them, appends one fsynced JSONL line (purpose, path, sha256, columns,
    time range, code commit, caller) to ``results/outlook_reads.jsonl`` and parses the same
    bytes. (``seal.sealed_read`` cannot serve this: it reads only freeze-hashed inputs inside the
    test-mode session that ``run_slice --window test`` alone enters.)"""
    if not live:
        raise OutlookSealError("live_read needs --live")
    if not purpose or not purpose.strip():
        raise OutlookSealError("live_read needs a purpose")
    if not seal_opened(results_dir, repo_root):
        raise OutlookSealError("the sealed window has not been opened (needs a completed test run "
                               "at results/test/manifest.json, a non-empty results/test_reads.jsonl "
                               "and the config-freeze tag): a live outlook waits for T13")
    path = Path(path)
    _check_live_path(path, live_root)
    start, end = (fc._aware(t, "time_range") for t in time_range)
    if not start < end:
        raise OutlookSealError(f"empty time range [{start}, {end})")
    buf = path.read_bytes()
    sha = hashlib.sha256(buf).hexdigest()
    rec = {"event": "read", "utc": iso(datetime.now(UTC)), "purpose": purpose.strip(),
           "path": str(path), "sha256": sha, "columns": list(columns), "ts_col": ts_col,
           "time_range": [iso(start), iso(end)], "code_commit": _git_head(),
           "caller": _caller(), "pid": os.getpid()}
    log = Path(results_dir) / LIVE_LOG_NAME
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
    frame = reader(io.BytesIO(buf))
    return frame.filter((pl.col(ts_col) >= start) & (pl.col(ts_col) < end)).select(list(columns))


class StaleDataError(ValueError):
    """A live series ends too long before the issue (EIA lag or a failed download)."""


def check_fresh(series: pl.DataFrame, issue: datetime, sites: Sequence[str] = SITES) -> dict:
    """Refuse a live series in which any site's latest non-null row is older than FRESH_DAYS
    before the issue. Returns {site: latest hour start}."""
    issue = fc._aware(issue, "issue")
    out = {}
    for ba in sites:
        s = series.filter((pl.col("ba") == ba) & pl.col("value").is_not_null()
                          & pl.col("value").is_not_nan())
        last = s["ts_utc"].max() if s.height else None
        if last is None or last < issue - timedelta(days=FRESH_DAYS):
            raise StaleDataError(f"{ba}: latest published row {iso(last) if last else 'none'} is "
                                 f"more than {FRESH_DAYS} days before the issue {iso(issue)}")
        out[ba] = last
    return out


# --------------------------------------------------------------------------- writing


def write_outlook(path: Path, obj: dict, *, live: bool) -> str:
    """Validate (every number enveloped; outside live mode no sealed timestamp) and write
    atomically (temp file, then rename)."""
    if live:
        if obj.get("window") != "live":
            raise ValueError("a live outlook must declare window 'live'")
        errs = [e for e in validate_artifact(obj) if not e.startswith("sealed timestamp")]
    else:
        if obj.get("window") != "validation":
            raise ValueError("a demo outlook must declare window 'validation'")
        errs = validate_artifact(obj)
    if errs:
        raise ValueError(f"{path.name}: {len(errs)} contract errors: {errs[:20]}")
    text = json.dumps(obj, indent=1, ensure_ascii=False, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    return text
