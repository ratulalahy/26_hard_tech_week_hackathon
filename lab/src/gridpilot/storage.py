"""Storage illustration (Stage 3 T10b, owner D-061, with the Astra review's F12–F15, F29):
"move what you can, store for what you can't".

**Illustrative.** Not part of the registered experiment, never in the test scenario catalog, and
storage is not simulated in the scheduler: a battery behind the meter at the Utah cluster (PACE)
is dispatched against the cluster's hourly energy from registered validation ledgers. Validation
data only; every read goes through the pre-seal loaders.

**Window.** The registered results' cohort window: UTC hours from eval_start to the last hour any
cohort job (U, or W under mobility ≤ 8 GPUs) still runs, so the cluster CO₂ with no storage is
exactly U's (Utah-only) attributed CO₂.

**Load.** Hourly facility energy at a site: busy GPUs × 0.60 kW × PUE 1.20 (`gridpilot.sim.power`),
the exact overlap of each ledger interval with each UTC hour. Cohort jobs only (the warm-up
ledger is not stored in the run directory), like the registered attributed CO₂.

**Battery.** Energy E (kWh) and power P (kW; P = E/4). Round-trip efficiency η is charged on the
charging side: drawing c kWh stores η·c; discharge delivers stored energy 1:1 into the cluster
and never more than that hour's load (no export). Charging is limited by P and by the site
connection: the cluster's full-load site power, 2,288 GPUs × 0.60 kW × 1.20 = 1,647.36 kW, less
that hour's load. State of charge is chronological over the whole window, starting empty; energy
left at the end is reported (`terminal_soc_mwh`) and valued at zero (its charging CO₂ counts,
nothing is credited). Degradation, self-discharge and auxiliary loads are ignored.

**Strategy A, fixed daily schedule (implementable, no forecasts).** Charge in the 6 local
(America/Denver) hours with the lowest mean CI on the training years [2022-01-01, 2024-10-29),
discharge in the 6 highest of the remaining hours, every day, as much as the limits allow
(charging starts as soon as the window opens). Chosen on training data only.

**Strategy B, hindsight heuristic.** Day by day, the dispatch that minimizes that day's CO₂ on
that day's *actual* hourly CI (a small LP per day, chronological: energy is discharged only after
it was charged that day). Energy left at midnight is worth nothing to the day's plan, so it
always ends the day empty (checked), which is why the day-by-day plan carries no charge across
days. It sees the future within each day and is not an optimum over the year or a bound: it is
a heuristic for what perfect day-ahead knowledge of carbon could do.

**Break-even.** Shifting 1 kWh helps only if the charging intensity / η is below the displaced
intensity. On a marginal basis we have no defensible hourly assignment (the spec §10
training-only proxy was not built; grid.md §8's 6-hour block slopes are a validation-year
regression with R² 0.47), so the skeptic view is a labelled threshold scenario, not an annual
avoided total.

**Rush hours.** Validation hours whose PACE net load (adjusted demand with spikes removed, minus
wind and solar; EIA-930, observed) is at or above the 99th percentile of the training years'
hourly net load: a training-derived threshold.

**Peak relief (router).** From the registered ledgers: each site's cluster load during the
rush hours and at PACE's annual net-load peak hour under U, S and W (`simulated`).

**Evidence (F29).** Dispatch outcomes (energy, CO₂, import, peak relief) are `simulated`; CI
inputs are `modeled`; η, P/E, the sizes and the schedule hours are `assumed`. Float totals use
`math.fsum`.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
from scipy import sparse
from scipy.optimize import linprog

from gridpilot.forecast import VAL_FIT_AT, VAL_HISTORY_START
from gridpilot.results import SCHEMA_VERSION, env, iso
from gridpilot.sim import HOME, SITES
from gridpilot.sim.power import GPU_KW, PUE
from gridpilot.splits import TEST_START

TZ_NAME = "America/Denver"
SITE = HOME  # PACE
TRAIN_START = VAL_HISTORY_START  # 2022-01-01T00Z
TRAIN_END = VAL_FIT_AT  # 2024-10-29T00Z: the forecasters' validation fit time
N_SCHEDULE_HOURS = 6
ETA_DEFAULT = 0.85
ETAS = (0.75, 0.85, 0.90)
SIZES_MWH = (0, 1, 2, 4, 8, 12, 16, 24)
P_OVER_E = 0.25  # per hour: P = E/4
RATE_KW = GPU_KW * PUE  # facility kW per busy GPU
CONNECTION_KW = SITES[SITE] * RATE_KW  # the cluster's full-load site power, 1,647.36 kW
RUSH_QUANTILE = 0.99
# grid.md §8, PACE: ΔCO2/Δnet-load slopes by local 6-hour block, validation year (R² 0.47).
MARGINAL_BLOCKS_G_KWH = (497.0, 658.0, 498.0, 550.0)
MARGINAL_FLAT_G_KWH = 618.0
MARGINAL_SOURCE = ("docs/data-profile/grid.md §8: PACE ΔCO₂/Δnet-load OLS slopes, all hours 618 "
                   "g/kWh and by local 6-hour block (00–06, 06–12, 12–18, 18–24 h), validation "
                   "year, R² 0.47. An associational reference, not a causal marginal factor, and "
                   "not the spec §10 training-only proxy (not built), so it gives no defensible "
                   "hourly assignment.")
HEADLINE_RULE = ("the smallest size whose fixed-schedule (A) cut, U load, η 0.85, is at least 90% "
                 "of A's largest cut over the size grid")
NOTE = ("not part of the registered experiment; validation-year profiles; storage not simulated "
        "in the scheduler")
PQ_LINE = ("Fast power-quality buffering (seconds to minutes) is a future interface, outside the "
           "hourly model.")
H_US = 3600 * 1_000_000
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
TEST_START_US = (TEST_START - _EPOCH) // timedelta(microseconds=1)
DESTS = tuple(s for s in SITES if s != SITE)


def _us(t: datetime) -> int:
    return (t - _EPOCH) // timedelta(microseconds=1)


def _dt(us: int) -> datetime:
    return _EPOCH + timedelta(microseconds=int(us))


def _mean(x) -> float | None:
    x = list(x)
    return math.fsum(x) / len(x) if x else None


# --------------------------------------------------------------------------- load


def hourly_load_kwh(ledger: pl.DataFrame, site: str, t0_us: int, n_hours: int) -> np.ndarray:
    """Facility kWh in each UTC hour [t0 + k h, t0 + (k+1) h), k < n_hours, at `site`: the exact
    overlap of every ledger interval × gpus × 0.60 kW × PUE 1.20. Integer GPU-µs internally."""
    if t0_us % H_US:
        raise ValueError("t0 must be a UTC hour start")
    t1_us = t0_us + n_hours * H_US
    if t1_us > TEST_START_US:
        raise ValueError(f"load window reaches the seal at {TEST_START.isoformat()} (F8)")
    f = ledger.filter(pl.col("site") == site)
    s = f["start_ts"].dt.epoch("us").to_numpy().astype(np.int64)
    e = f["end_ts"].dt.epoch("us").to_numpy().astype(np.int64)
    g = f["gpus"].to_numpy().astype(np.int64)
    s, e = np.maximum(s, t0_us) - t0_us, np.minimum(e, t1_us) - t0_us
    k = e > s
    s, e, g = s[k], e[k], g[k]
    hs, he = s // H_US, e // H_US  # he == n_hours only when e is the window end
    gus = np.zeros(n_hours + 1, dtype=np.int64)
    same = hs == he
    np.add.at(gus, hs[same], g[same] * (e[same] - s[same]))
    m = ~same
    np.add.at(gus, hs[m], g[m] * ((hs[m] + 1) * H_US - s[m]))
    np.add.at(gus, he[m], g[m] * (e[m] - he[m] * H_US))
    diff = np.zeros(n_hours + 2, dtype=np.int64)
    np.add.at(diff, hs[m] + 1, g[m] * H_US)
    np.add.at(diff, he[m], -g[m] * H_US)
    gus += np.cumsum(diff)[: n_hours + 1]
    return gus[:n_hours] / H_US * RATE_KW


# --------------------------------------------------------------------------- calendar


def cohort_window(start: datetime, last_end: datetime) -> tuple[datetime, datetime]:
    """UTC hours [start, ceil_hour(last_end)): the cohort's whole execution."""
    s_us = _us(start)
    if s_us % H_US:
        raise ValueError("the window must start on a UTC hour")
    e_us = -(-_us(last_end) // H_US) * H_US
    if e_us > TEST_START_US:
        raise ValueError(f"window [{start}, {last_end}) reaches the seal at {TEST_START} (F8)")
    return _dt(s_us), _dt(e_us)


def hour_grid(s: datetime, e: datetime) -> pl.DataFrame:
    """UTC hours of [s, e) with their Denver hour of day and local-day index."""
    ts = pl.datetime_range(s, e, "1h", time_unit="us", time_zone="UTC", eager=True,
                           closed="left")
    lt = ts.dt.convert_time_zone(TZ_NAME)
    d = lt.dt.date()
    return pl.DataFrame({"ts_utc": ts, "hour": lt.dt.hour().cast(pl.Int64),
                         "day": (d - d.min()).dt.total_days().cast(pl.Int64)})


# --------------------------------------------------------------------------- training-only rules


def _check_training(series: pl.DataFrame) -> None:
    if series.height:
        lo, hi = series["ts_utc"].min(), series["ts_utc"].max()
        if lo < TRAIN_START or hi >= TRAIN_END:
            raise ValueError(f"rows must lie in the training window [{TRAIN_START}, "
                             f"{TRAIN_END}); got [{lo}, {hi}] (no validation peeking)")


def training_schedule(series: pl.DataFrame, k: int = N_SCHEDULE_HOURS) -> dict:
    """Strategy A's hours from the training years only. `series`: ts_utc, value (PACE CI)."""
    _check_training(series)
    v = series.filter(pl.col("value").is_not_null() & pl.col("value").is_finite()).with_columns(
        pl.col("ts_utc").dt.convert_time_zone(TZ_NAME).dt.hour().alias("hour"))
    profile: list[float | None] = []
    n: list[int] = []
    for h in range(24):
        x = v.filter(pl.col("hour") == h).sort("ts_utc")["value"].to_list()
        n.append(len(x))
        profile.append(_mean(x))
    ok = [h for h in range(24) if profile[h] is not None]
    charge = sorted(sorted(ok, key=lambda h: (profile[h], h))[:k])
    rest = [h for h in ok if h not in charge]
    discharge = sorted(sorted(rest, key=lambda h: (-profile[h], h))[:k])
    return {"profile": profile, "n_hours": n, "charge_hours": charge,
            "discharge_hours": discharge}


def rush_threshold(net_train: pl.DataFrame, q: float = RUSH_QUANTILE) -> float:
    """The rush-hour net-load threshold (MW): the q-quantile of the training years' hourly PACE
    net load. `net_train`: ts_utc, value."""
    _check_training(net_train)
    v = net_train.filter(pl.col("value").is_not_null() & pl.col("value").is_finite())["value"]
    if v.len() == 0:
        raise ValueError("no training net-load hours")
    return float(np.quantile(v.to_numpy(), q, method="linear"))


# --------------------------------------------------------------------------- strategies


def _headroom(load: np.ndarray, p_kw: float, conn_kw: float) -> np.ndarray:
    return np.minimum(p_kw, np.maximum(0.0, conn_kw - np.asarray(load, dtype=float)))


def fixed_schedule(load: np.ndarray, local_hour: np.ndarray, charge_hours: Sequence[int],
                   discharge_hours: Sequence[int], *, e_kwh: float, p_kw: float, eta: float,
                   conn_kw: float = math.inf) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Strategy A: (grid charging kWh, delivered kWh, end-of-hour state of charge) per hour;
    chronological from empty."""
    if set(charge_hours) & set(discharge_hours):
        raise ValueError("charge and discharge hours overlap")
    n = len(load)
    c, d, soc = np.zeros(n), np.zeros(n), np.zeros(n)
    if e_kwh <= 0 or p_kw <= 0:
        return c, d, soc
    cap = _headroom(load, p_kw, conn_kw)
    ch = np.isin(local_hour, list(charge_hours))
    dh = np.isin(local_hour, list(discharge_hours))
    x = 0.0
    for i in range(n):
        if ch[i]:
            c[i] = min(cap[i], max(e_kwh - x, 0.0) / eta)
            x = min(e_kwh, x + eta * c[i])
        elif dh[i]:
            d[i] = min(p_kw, x, float(load[i]))
            x -= d[i]
        soc[i] = x
    return c, d, soc


EMPTY_TOL_KWH = 1e-6


def hindsight_heuristic(load: np.ndarray, ci: np.ndarray, day: np.ndarray, *, e_kwh: float,
                        p_kw: float, eta: float, conn_kw: float = math.inf,
                        ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Strategy B: each local day, the dispatch minimizing that day's CO₂ on its actual CI,
    starting from the state of charge the previous day left (always empty: midnight leftovers are
    worth nothing to the day's plan, checked). Returns (charge, delivered, chronological SOC)."""
    n = len(load)
    if e_kwh <= 0 or p_kw <= 0 or n == 0:
        return np.zeros(n), np.zeros(n), np.zeros(n)
    day = np.asarray(day)
    first = np.r_[True, day[1:] != day[:-1]]
    last = np.r_[day[1:] != day[:-1], True]
    idx = np.arange(n)
    # x = [c (n), d (n), s (n)]: s_h − s_{h−1} − η c_h + d_h = 0, s = 0 before each day's start
    # (the previous day ended empty; asserted below on the chronological SOC)
    rows = np.r_[idx, idx, idx, idx[~first]]
    cols = np.r_[idx, n + idx, 2 * n + idx, 2 * n + idx[~first] - 1]
    vals = np.r_[np.full(n, -eta), np.ones(n), np.ones(n), -np.ones((~first).sum())]
    a_eq = sparse.csr_matrix((vals, (rows, cols)), shape=(n, 3 * n))
    ci = np.asarray(ci, dtype=float)
    # a tiny charge cost breaks ties toward not cycling; leftover energy at midnight is free to
    # keep but worth nothing, so the plan never keeps any
    cost = np.r_[ci + 1e-9, -ci, np.zeros(n)]
    cmax = _headroom(load, p_kw, conn_kw)
    dmax = np.minimum(p_kw, np.asarray(load, dtype=float))
    bounds = np.c_[np.zeros(3 * n), np.r_[cmax, dmax, np.full(n, e_kwh)]]
    r = linprog(cost, A_eq=a_eq, b_eq=np.zeros(n), bounds=bounds, method="highs")
    if r.status != 0:
        raise RuntimeError(f"hindsight heuristic LP failed: {r.message}")
    c = np.clip(r.x[:n], 0, cmax)
    d = np.clip(r.x[n:2 * n], 0, dmax)
    soc = np.empty(n)
    x = 0.0
    for i in range(n):  # chronological across the whole window: no resets
        x = x + eta * c[i] - d[i]
        if x < -EMPTY_TOL_KWH:
            raise AssertionError(f"hour {i}: discharged energy that was never charged")
        x = max(x, 0.0)
        soc[i] = x
        if last[i] and x > EMPTY_TOL_KWH * max(1.0, e_kwh):
            raise AssertionError(f"day ending at hour {i} left {x} kWh stored")
    return c, d, soc


# --------------------------------------------------------------------------- outcomes


def outcome(load: np.ndarray, ci: np.ndarray, c: np.ndarray, d: np.ndarray,
            soc: np.ndarray | None = None) -> dict:
    """Cluster CO₂ with and without storage (kg) and the dispatch's energy (MWh). Energy left
    stored at the end is valued at zero: its charging CO₂ counts, nothing is credited."""
    load, ci, c, d = (np.asarray(x, dtype=float) for x in (load, ci, c, d))
    base = math.fsum((load * ci).tolist()) / 1000
    co2 = math.fsum(((load - d + c) * ci).tolist()) / 1000
    sc, sd = math.fsum(c.tolist()), math.fsum(d.tolist())
    return {"base_co2_kg": base, "co2_kg": co2, "cut_kg": base - co2,
            "cut_frac": (base - co2) / base if base else None,
            "shifted_mwh": sd / 1000, "charged_mwh": sc / 1000,
            "losses_mwh": (sc - sd) / 1000 - (float(soc[-1]) / 1000 if soc is not None and len(soc) else 0.0),
            "terminal_soc_mwh": float(soc[-1]) / 1000 if soc is not None and len(soc) else 0.0,
            "charge_ci_g_kwh": math.fsum((c * ci).tolist()) / sc if sc else None,
            "discharge_ci_g_kwh": math.fsum((d * ci).tolist()) / sd if sd else None}


def import_view(load: np.ndarray, c: np.ndarray, d: np.ndarray, hour: np.ndarray,
                rush: np.ndarray, charge_hours: Sequence[int]) -> dict:
    """The cluster's grid import (MW) before and after storage: the mean by local hour, in the
    rush hours, the annual maximum and the charging rebound."""
    load = np.asarray(load, dtype=float)
    after = load - d + c
    def by_h(x):
        return [None if (m := _mean(x[hour == h].tolist())) is None else m / 1000
                for h in range(24)]

    ch = np.isin(hour, list(charge_hours))
    return {"before_by_hour_mw": by_h(load), "after_by_hour_mw": by_h(after),
            "rush_before_mw": (_mean(load[rush].tolist()) or 0) / 1000 if rush.any() else None,
            "rush_after_mw": (_mean(after[rush].tolist()) or 0) / 1000 if rush.any() else None,
            "peak_before_mw": float(load.max()) / 1000, "peak_after_mw": float(after.max()) / 1000,
            "rebound_mw": (_mean((c[ch]).tolist()) or 0.0) / 1000 if ch.any() else 0.0,
            "rebound_max_mw": float(c.max()) / 1000}


def sweep(load: np.ndarray, ci: np.ndarray, grid: pl.DataFrame, sched: dict, *,
          sizes_mwh: Sequence[float] = SIZES_MWH, etas: Sequence[float] = ETAS,
          p_over_e: float = P_OVER_E, conn_kw: float = CONNECTION_KW) -> dict:
    """{strategy: {eta: [(outcome, (c, d, soc)) per size]}} for strategies A and B."""
    hour, day = grid["hour"].to_numpy(), grid["day"].to_numpy()
    out: dict = {"A": {}, "B": {}}
    for eta in etas:
        for strat in ("A", "B"):
            rows = []
            for e_mwh in sizes_mwh:
                e_kwh, p_kw = e_mwh * 1000.0, e_mwh * 1000.0 * p_over_e
                if strat == "A":
                    c, d, soc = fixed_schedule(load, hour, sched["charge_hours"],
                                               sched["discharge_hours"], e_kwh=e_kwh, p_kw=p_kw,
                                               eta=eta, conn_kw=conn_kw)
                else:
                    c, d, soc = hindsight_heuristic(load, ci, day, e_kwh=e_kwh, p_kw=p_kw,
                                                    eta=eta, conn_kw=conn_kw)
                rows.append((outcome(load, ci, c, d, soc), (c, d, soc)))
            out[strat][eta] = rows
    return out


def peak_relief(loads: dict[str, dict[str, np.ndarray]], rush: np.ndarray, peak_idx: int) -> dict:
    """`loads[policy][site]`: hourly kWh. Per policy: each site's mean MW in the rush hours and
    at PACE's net-load peak hour, and the change vs U."""
    out = {}
    u = loads["U"]
    for p, by in loads.items():
        out[p] = {}
        for s, x in by.items():
            m = (_mean(x[rush].tolist()) or 0.0) / 1000 if rush.any() else None
            mu = (_mean(u[s][rush].tolist()) or 0.0) / 1000 if rush.any() else None
            out[p][s] = {"rush_mean_mw": m, "at_peak_mw": float(x[peak_idx]) / 1000,
                         "rush_change_vs_U_mw": None if m is None else m - mu,
                         "at_peak_change_vs_U_mw": float(x[peak_idx] - u[s][peak_idx]) / 1000}
    return out


# --------------------------------------------------------------------------- inputs (pre-seal)


def _truth_ci(run_dir: Path, grid: pl.DataFrame) -> np.ndarray:
    t = pl.read_parquet(run_dir / "truth_fill.parquet").filter(pl.col("ts_utc") < TEST_START)
    t = t.filter(pl.col("ba") == SITE).select("ts_utc", "ci_g_kwh")
    j = grid.join(t, on="ts_utc", how="left")
    miss = j.filter(pl.col("ci_g_kwh").is_null() | ~pl.col("ci_g_kwh").is_finite())
    if miss.height:
        raise ValueError(f"{miss.height} window hours have no filled PACE truth")
    return j["ci_g_kwh"].to_numpy().astype(float)


def training_ci() -> pl.DataFrame:
    """PACE consumption-basis CI, tier 1 (published), training years only, via the pre-seal
    loader (`forecast.load_series`, which applies `drop_sealed` in the scan)."""
    from gridpilot.forecast import load_series

    s = load_series("ci_consumed")
    return s.filter((pl.col("ba") == SITE) & (pl.col("ts_utc") >= TRAIN_START)
                    & (pl.col("ts_utc") < TRAIN_END)).select("ts_utc", "value")


def net_load() -> pl.DataFrame:
    """PACE hourly net load (MW): adjusted demand with spikes removed (`add_demand_clean`) minus
    wind and solar, via the pre-seal loaders. ts_utc, value (null where any input is missing)."""
    from gridpilot.data.eia930 import add_demand_clean
    from gridpilot.forecast import load_series

    dem = add_demand_clean(load_series("demand").rename({"value": "demand_adj_mw"}))
    w = load_series("wind").select("ts_utc", pl.col("value").alias("wind"))
    s = load_series("solar").select("ts_utc", pl.col("value").alias("solar"))
    f = dem.select("ts_utc", "demand_clean_mw").join(w, on="ts_utc", how="left").join(
        s, on="ts_utc", how="left")
    return f.select("ts_utc", (pl.col("demand_clean_mw") - pl.col("wind").fill_null(0.0)
                               - pl.col("solar").fill_null(0.0)).alias("value")).sort("ts_utc")


# --------------------------------------------------------------------------- artifact


EVID = {"co2_t": ("t_CO2", "simulated"), "cut_t": ("t_CO2", "simulated"),
        "cut_frac": ("fraction", "simulated"), "shifted_mwh": ("MWh", "simulated"),
        "losses_mwh": ("MWh", "simulated"), "terminal_soc_mwh": ("MWh", "simulated"),
        "charge_ci_g_kwh": ("g/kWh", "simulated"), "discharge_ci_g_kwh": ("g/kWh", "simulated")}
_SCALE = {"co2_t": ("co2_kg", 1e-3), "cut_t": ("cut_kg", 1e-3)}


def _block(rows: list, pid: str) -> dict:
    out = {}
    for k, (unit, ev) in EVID.items():
        src, sc = _SCALE.get(k, (k, 1.0))
        v = [None if r[0][src] is None else r[0][src] * sc for r in rows]
        null = any(x is None for x in v)
        out[k] = env(v, unit, ev, f"{pid}:{k}",
                     reason="no storage (E = 0) or no energy dispatched" if null else None)
    return out


def headline_size(rows_a: list, sizes: Sequence[float]) -> float:
    cuts = [r[0]["cut_kg"] for r in rows_a]
    top = max(cuts)
    return next(s for s, c in zip(sizes, cuts, strict=True) if c >= 0.9 * top) if top > 0 \
        else sizes[0]


def _e(v, unit, ev, pid):
    return env(v, unit, ev, pid, reason=None if v is not None and not (
        isinstance(v, list) and any(x is None for x in v)) else "no hours in this cell")


def build_artifact(*, run_id: str, mob_run_id: str, window: tuple[datetime, datetime],
                   grid: pl.DataFrame, ci: np.ndarray, sched: dict, rush: dict, cases: dict,
                   totals: dict, relief: dict, sizes=SIZES_MWH, etas=ETAS) -> dict:
    """`cases`: {name: {"label", "source", "load", "sweep"}}; `totals`: the cohort CO₂ (kg) of
    U and of W under mobility ≤ 8 GPUs, every site and transfer counted once, and W's Utah
    execution CO₂; `rush`: {"threshold_mw", "mask", "peak_idx", "n_train"}."""
    pid = "storage"
    hour = grid["hour"].to_numpy()
    mask = rush["mask"]
    vprof = [_mean(ci[hour == h].tolist()) for h in range(24)]
    e_head = headline_size(cases["U"]["sweep"]["A"][ETA_DEFAULT], sizes)
    i_head = list(sizes).index(e_head)
    out_cases = {}
    for name, cs in cases.items():
        load = cs["load"]
        mean_kw = math.fsum(load.tolist()) / len(load)
        sw = cs["sweep"]
        base = sw["A"][etas[0]][0][0]
        imp = {}
        for s in ("A", "B"):
            c, d, _ = sw[s][ETA_DEFAULT][i_head][1]
            iv = import_view(load, c, d, hour, mask, sched["charge_hours"])
            imp[s] = {k: _e(v, "MW", "simulated", f"{pid}:{name}:import:{s}:{k}")
                      for k, v in iv.items()}
        out_cases[name] = {
            "label": cs["label"], "source": cs["source"],
            "energy_mwh": env(math.fsum(load.tolist()) / 1000, "MWh", "simulated",
                              f"{pid}:{name}:energy"),
            "mean_load_mw": env(mean_kw / 1000, "MW", "simulated", f"{pid}:{name}:mean_load"),
            "load_hours": env([s * 1000 / mean_kw for s in sizes], "h", "simulated",
                              f"{pid}:{name}:load_hours"),
            "base_co2_t": env(base["base_co2_kg"] / 1000, "t_CO2", "simulated",
                              f"{pid}:{name}:base_co2"),
            "strategies": {s: {f"{eta:.2f}": _block(sw[s][eta], f"{pid}:{name}:{s}:{eta:.2f}")
                               for eta in etas} for s in ("A", "B")},
            "import_at_headline": imp,
        }
    # move small, store for big (η 0.85): the cohort totals, every site and transfer once
    u_kg, w_kg = totals["U_kg"], totals["W_mob_kg"]
    mob = cases["mobility_le_8gpus_W"]["sweep"]
    comb = {s: [(u_kg - (w_kg - r[0]["cut_kg"])) / u_kg for r in mob[s][ETA_DEFAULT]]
            for s in ("A", "B")}
    # break-even: charging intensity / η must be below the displaced intensity
    tp = sched["profile"]
    ch_ci = _mean(tp[h] for h in sched["charge_hours"])
    dis_ci = _mean(tp[h] for h in sched["discharge_hours"])
    mb = {h: MARGINAL_BLOCKS_G_KWH[h // 6] for h in range(24)}
    m_ch = _mean(mb[h] for h in sched["charge_hours"])
    m_dis = _mean(mb[h] for h in sched["discharge_hours"])
    flat = {name: [-r[0]["losses_mwh"] * MARGINAL_FLAT_G_KWH for r in cs["sweep"]["A"][ETA_DEFAULT]]
            for name, cs in cases.items()}
    peak_ts = grid["ts_utc"][rush["peak_idx"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "illustrative",
        "note": NOTE,
        "title": "Move what you can, store for what you can't",
        "registered_run_id": run_id,
        "mobility_run_id": mob_run_id,
        "site": SITE,
        "local_tz": TZ_NAME,
        "window": {"start": iso(window[0]), "end": iso(window[1]),
                   "n_hours": env(grid.height, "hours", "simulated", f"{pid}:window:n_hours"),
                   "rule": "the registered cohort window: eval_start to the last hour a cohort "
                           "job (U, or W under mobility ≤ 8 GPUs) still runs"},
        "assumptions": {
            "sizes_mwh": env(list(sizes), "MWh", "assumed", f"{pid}:sizes"),
            "p_over_e": env(P_OVER_E, "1/h", "assumed", f"{pid}:p_over_e"),
            "etas": env(list(etas), "fraction", "assumed", f"{pid}:etas"),
            "eta_default": env(ETA_DEFAULT, "fraction", "assumed", f"{pid}:eta_default"),
            "connection_mw": env(CONNECTION_KW / 1000, "MW", "assumed", f"{pid}:connection"),
            "kw_per_gpu": env(GPU_KW, "kW", "assumed", f"{pid}:kw_per_gpu"),
            "pue": env(PUE, "ratio", "assumed", f"{pid}:pue"),
            "losses": "round-trip losses charged on the charging side (stores η × grid draw)",
            "power_limit": "charging ≤ min(P, connection − cluster load); discharge ≤ min(P, "
                           "cluster load); connection = 2,288 GPUs × 0.60 kW × PUE 1.20",
            "state_of_charge": "chronological over the whole window, starting empty; energy left "
                               "at the end is valued at zero",
            "ignored": "degradation, self-discharge, auxiliary loads, capital cost",
            "load": "cohort jobs only (warm-up occupancy not included), exact hourly overlap",
        },
        "schedule": {
            "rule": f"charge in the {N_SCHEDULE_HOURS} local hours with the lowest training-mean "
                    f"CI, discharge in the {N_SCHEDULE_HOURS} highest of the rest, every day",
            "train_window": [iso(TRAIN_START), iso(TRAIN_END)],
            "train_profile_g_kwh": env(tp, "g/kWh", "modeled", f"{pid}:train_profile",
                                       reason=None if all(v is not None for v in tp)
                                       else "no training hours"),
            "train_n_hours": env(sched["n_hours"], "hours", "measured", f"{pid}:train_n"),
            "charge_hours": env(sched["charge_hours"], "local_hour", "assumed", f"{pid}:charge"),
            "discharge_hours": env(sched["discharge_hours"], "local_hour", "assumed",
                                   f"{pid}:discharge"),
        },
        "validation_profile_g_kwh": env(vprof, "g/kWh", "modeled", f"{pid}:validation_profile"),
        "strategy_labels": {"A": "fixed daily schedule (training-year hours, no forecasts)",
                            "B": "hindsight heuristic (each day planned on that day's actual "
                                 "CI; not an optimum or a bound)"},
        "break_even": {
            "rule": "storage cuts CO₂ only if charging intensity / η < displaced intensity",
            "train_charge_ci_g_kwh": env(ch_ci, "g/kWh", "modeled", f"{pid}:be:charge_ci"),
            "train_discharge_ci_g_kwh": env(dis_ci, "g/kWh", "modeled", f"{pid}:be:dis_ci"),
            "train_charge_ci_over_eta_g_kwh": env([ch_ci / eta for eta in etas], "g/kWh",
                                                  "modeled", f"{pid}:be:charge_over_eta"),
            "marginal_threshold": {
                "kind": "threshold scenario (no defensible hourly marginal assignment)",
                "source": MARGINAL_SOURCE,
                "required_discharge_over_charge": env([1 / eta for eta in etas], "ratio",
                                                      "assumed", f"{pid}:be:m_ratio"),
                "reference_blocks_g_kwh": env(list(MARGINAL_BLOCKS_G_KWH), "g/kWh", "modeled",
                                              f"{pid}:be:m_blocks"),
                "reference_charge_hours_g_kwh": env(m_ch, "g/kWh", "modeled", f"{pid}:be:m_ch"),
                "reference_discharge_hours_g_kwh": env(m_dis, "g/kWh", "modeled",
                                                       f"{pid}:be:m_dis"),
                "flat_g_kwh": env(MARGINAL_FLAT_G_KWH, "g/kWh", "modeled", f"{pid}:be:m_flat"),
                "flat_scenario_cut_t_A": {k: env([x / 1000 for x in v], "t_CO2", "simulated",
                                                 f"{pid}:be:{k}:flat_A")
                                          for k, v in flat.items()},
            },
        },
        "rush": {
            "rule": f"validation hours with PACE net load ≥ the training years' "
                    f"{RUSH_QUANTILE:.0%} quantile (training-derived threshold)",
            "threshold_mw": env(rush["threshold_mw"], "MW", "observed", f"{pid}:rush:threshold"),
            "n_hours": env(int(mask.sum()), "hours", "observed", f"{pid}:rush:n"),
            "n_train_hours": env(rush["n_train"], "hours", "observed", f"{pid}:rush:n_train"),
            "by_local_hour": env(np.bincount(hour[mask], minlength=24).tolist(), "hours",
                                 "observed", f"{pid}:rush:by_hour"),
            "peak_hour_utc": iso(peak_ts),
            "peak_net_load_mw": env(rush["peak_mw"], "MW", "observed", f"{pid}:rush:peak"),
        },
        "peak_relief": {
            "rule": "each site's cluster load (cohort, registered ledgers) during the rush hours "
                    "and at PACE's net-load peak hour; change vs U; MW = MWh per hour",
            "run_id": run_id,
            "policies": {p: {s: {k: env(v, "MW", "simulated", f"{pid}:relief:{p}:{s}:{k}",
                                        reason=None if v is not None else "no rush hours")
                                 for k, v in by.items()}
                             for s, by in sites.items()} for p, sites in relief.items()},
        },
        "cases": out_cases,
        "combined": {
            "rule": "move small, store for big: (U − (W under mobility ≤ 8 GPUs − storage cut on "
                    "its Utah load)) / U over the registered cohort window, η 0.85; Utah "
                    "execution, remote execution and transfer energy each counted once; ratio "
                    "of totals, not the registered 4-week-block estimate",
            "U_co2_t": env(u_kg / 1000, "t_CO2", "simulated", f"{pid}:combined:U"),
            "W_mob_co2_t": env(w_kg / 1000, "t_CO2", "simulated", f"{pid}:combined:W_mob"),
            "W_mob_utah_exec_co2_t": env(totals["W_mob_utah_kg"] / 1000, "t_CO2", "simulated",
                                         f"{pid}:combined:W_mob_utah"),
            "move_only_cut_frac": env((u_kg - w_kg) / u_kg, "fraction", "simulated",
                                      f"{pid}:combined:move_only"),
            "move_and_store_cut_frac": {s: env(v, "fraction", "simulated",
                                               f"{pid}:combined:{s}") for s, v in comb.items()},
        },
        "headline": {"rule": HEADLINE_RULE,
                     "e_mwh": env(e_head, "MWh", "assumed", f"{pid}:headline:e")},
        "power_quality": PQ_LINE,
    }


def from_runs(run_dir: Path, mob_dir: Path) -> dict:
    """Read the registered run and the mobility ≤ 8 GPUs run (validation only) and build."""
    from gridpilot.eval.accounting import TruthTable, fsum_by, job_accounting

    cfg = json.loads((run_dir / "config.json").read_text())
    if cfg.get("window") != "validation":
        raise ValueError(f"{run_dir} is not a validation run")
    t_start = datetime.fromisoformat(cfg["eval_start"].replace("Z", "+00:00"))
    led = {p: pl.read_parquet(run_dir / f"ledger_{p}.parquet") for p in ("U", "S", "W")}
    led_mob = pl.read_parquet(mob_dir / "ledger_W.parquet")
    last_end = max(x["end_ts"].max() for x in (*led.values(), led_mob))
    win = cohort_window(t_start, last_end)
    grid = hour_grid(*win)
    t0, n = _us(win[0]), grid.height
    ci = _truth_ci(run_dir, grid)
    sched = training_schedule(training_ci())
    net = net_load()
    thr = rush_threshold(net.filter((pl.col("ts_utc") >= TRAIN_START)
                                    & (pl.col("ts_utc") < TRAIN_END)))
    n_train = net.filter((pl.col("ts_utc") >= TRAIN_START) & (pl.col("ts_utc") < TRAIN_END)
                         & pl.col("value").is_not_null()).height
    nv = grid.join(net, on="ts_utc", how="left")["value"].to_numpy().astype(float)
    mask = np.nan_to_num(nv, nan=-np.inf) >= thr
    peak_idx = int(np.nanargmax(nv))
    loads = {"U": hourly_load_kwh(led["U"], SITE, t0, n),
             "mobility_le_8gpus_W": hourly_load_kwh(led_mob, SITE, t0, n)}
    cases = {
        "U": {"label": "Every job in Utah (U local)", "source": f"{run_dir.name}/ledger_U"},
        "mobility_le_8gpus_W": {
            "label": "Jobs that stay in Utah when only jobs of 8 GPUs or fewer may move (W)",
            "source": f"mobility_le_8gpus/{mob_dir.name}/ledger_W"},
    }
    for k in cases:
        cases[k]["load"] = loads[k]
        cases[k]["sweep"] = sweep(loads[k], ci, grid, sched)
    tt = TruthTable(pl.read_parquet(run_dir / "truth_fill.parquet"))
    jobs = led["U"].select("job_uid",
                           pl.col("job_uid").str.split("#").list.first().alias("source_id"),
                           "arrival_ts", "gpus", "duration_s")
    acc_u = job_accounting(led["U"], jobs, tt)
    acc_w = job_accounting(led_mob, jobs, tt)
    w_utah = fsum_by(acc_w.filter(pl.col("site") == SITE), "execution_co2_kg")
    totals = {"U_kg": fsum_by(acc_u, "co2_kg"), "W_mob_kg": fsum_by(acc_w, "co2_kg"),
              "W_mob_utah_kg": w_utah}
    # the storage case's no-storage CO₂ is exactly the Utah execution CO₂ (same window, once)
    for name, kg in (("U", totals["U_kg"]), ("mobility_le_8gpus_W", w_utah)):
        b = cases[name]["sweep"]["A"][ETAS[0]][0][0]["base_co2_kg"]
        if not math.isclose(b, kg, rel_tol=1e-9):
            raise AssertionError(f"{name}: hourly-load CO₂ {b} != accounting {kg}")
    relief = peak_relief({p: {s: hourly_load_kwh(led[p], s, t0, n) for s in SITES}
                          for p in ("U", "S", "W")}, mask, peak_idx)
    return build_artifact(run_id=run_dir.name, mob_run_id=mob_dir.name, window=win, grid=grid,
                          ci=ci, sched=sched,
                          rush={"threshold_mw": thr, "mask": mask, "peak_idx": peak_idx,
                                "n_train": n_train, "peak_mw": float(nv[peak_idx])},
                          cases=cases, totals=totals, relief=relief)
