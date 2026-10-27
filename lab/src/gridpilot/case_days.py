"""Stage 3 T16 (D-066): "Utah's toughest grid days", an illustrative case study.

**Day rule (pre-registered in D-066 before any day was examined; never changed, never
substituted).** Validation days are the America/Denver calendar dates in [2024-11-01,
2025-10-24). A day's stress is PACE's daily maximum hourly **net load**: EIA-930 adjusted
demand with isolated spikes removed (`gridpilot.data.eia930.add_demand_clean`, the existing
spike rule) minus wind minus solar (missing wind or solar counts as 0, as in
`gridpilot.storage.net_load` and `gridpilot.grid_profile`). The case study shows the **top 3
days** by that maximum; ties go to the earlier date. A day's peak hour is the hour holding the
maximum; ties go to the earlier hour. Every chosen day's rank is reported.

**Per day.** From the registered run's ledgers (validation only; no new simulation):
- hourly PACE net load, demand, solar and wind (`observed`, EIA-930);
- hourly PACE carbon intensity: the F14.6-filled truth stored with the run (`modeled`: EIA's
  consumption-basis estimate, with modeled fills in any tier ≥ 2 hour);
- the Utah cluster's hourly load under U, S and W (`simulated`), and the energy each site ran
  that day (where the moved work went);
- that day's attributed CO₂ under U, S and W (`simulated`), **day-sliced**: execution energy is
  counted in the hour it ran (exact overlap of each ledger interval with each UTC hour of the
  local day, at the execution site's hourly intensity) and transfer energy at its arrival hour
  (F14.5: half at home, half at the destination), so a job that spans midnight is split between
  days. The sum over every hour of the cohort window equals the registered job accounting
  (checked in `from_run`);
- the Utah cluster's load in that day's net-load peak hour under each policy.

**Weather (owner addendum; descriptive only).** Daily max and min 2 m temperature and degree
days (base 65 °F, from the mean of max and min) for Salt Lake City, the one PACE load-centre
point in the archive, plus PACE's two resource points (Milford UT solar, Medicine Bow WY wind),
which are resource sites and not load-weighted. The archive holds forecast products only, so
the values are labelled `forecast`: Salt Lake City from the Historical Forecast API (each hour
from a run issued a few hours earlier: the issue closest before the hour), the resource points
from the Previous Runs API's latest run (`previous_day0`). Weather never feeds any model or
decision here; it describes the day.

**Seal.** Every grid read goes through the pre-seal loaders (`gridpilot.forecast.load_series`,
`gridpilot.data.weather.load`) or is the direct argument of `drop_sealed`; no day at or after
the validation end is accepted, and nothing reaches the test window.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from gridpilot.results import SCHEMA_VERSION, env, iso
from gridpilot.sim import HOME, SITES
from gridpilot.sim.power import GPU_KW, PUE, TRANSFER_FRACTION
from gridpilot.splits import TEST_START, drop_sealed
from gridpilot.storage import hourly_load_kwh

TZ_NAME = "America/Denver"
TZ = ZoneInfo(TZ_NAME)
DAY_START = date(2024, 11, 1)  # first validation day (local)
DAY_END = date(2025, 10, 24)  # exclusive: F's date
K = 3
RULE = ("D-066 (pre-registered before any day was examined): the top 3 validation days "
        "(America/Denver dates in [2024-11-01, 2025-10-24)) by PACE daily maximum hourly net "
        "load (EIA-930 adjusted demand, isolated spikes removed, minus wind and solar); ties go "
        "to the earlier date; each day's rank is reported; no day is ever substituted")
POLICIES = ("U", "S", "W")
POLICY_LABEL = {"U": "U local (stay in Utah)", "S": "S static clean-region ranking",
                "W": "W weekly profile"}  # the dashboard's one name per policy (lead ruling R1)
PROV = "case-days"
H_US = 3600 * 1_000_000
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
RATE_KW = GPU_KW * PUE
BASE_F = 65.0
WEATHER_POINTS = (
    ("PACE_SLC", "historical-forecast", "Salt Lake City UT", "load centre"),
    ("PACE_SOLAR_UT", "previous-runs", "Milford UT", "solar resource site"),
    ("PACE_WIND_WY", "previous-runs", "Medicine Bow WY", "wind resource site"),
)
ACCOUNTING_NOTE = ("day-sliced accounting: execution energy counted in the hour it ran (exact "
                   "overlap with each UTC hour of the local day) at the execution site's hourly "
                   "intensity; transfer energy at its arrival hour, half at home and half at the "
                   "destination (F14.5). A job spanning midnight is split between days. Summed "
                   "over every hour of the cohort window, it equals the registered accounting")


def _us(t: datetime) -> int:
    return (t - _EPOCH) // timedelta(microseconds=1)


# --------------------------------------------------------------------------- calendar


def local_day_utc(d: date) -> tuple[datetime, int]:
    """The UTC start and hour count (23, 24 or 25) of the America/Denver day `d`."""
    if not DAY_START <= d < DAY_END:
        raise ValueError(f"{d} is not a validation day [{DAY_START}, {DAY_END})")
    a = datetime(d.year, d.month, d.day, tzinfo=TZ).astimezone(UTC)
    n1 = d + timedelta(days=1)
    b = datetime(n1.year, n1.month, n1.day, tzinfo=TZ).astimezone(UTC)
    if b > TEST_START:
        raise ValueError(f"{d} reaches the seal")
    return a, int((b - a) / timedelta(hours=1))


# --------------------------------------------------------------------------- the day rule


def _local(frame: pl.DataFrame) -> pl.DataFrame:
    lt = pl.col("ts_utc").dt.convert_time_zone(TZ_NAME)
    return frame.with_columns(lt.dt.date().alias("date"), lt.dt.hour().alias("hour_local"))


def daily_max(net: pl.DataFrame) -> pl.DataFrame:
    """Per validation day (America/Denver): max_mw, the peak hour (earliest on a tie), and the
    hour and null counts. `net`: ts_utc, value (MW)."""
    if net.height and net["ts_utc"].max() >= TEST_START:
        raise ValueError("net load holds sealed rows (at or after the seal)")
    f = _local(net).filter((pl.col("date") >= DAY_START) & (pl.col("date") < DAY_END))
    ranked = f.filter(pl.col("value").is_not_null()).sort(
        ["date", "value", "ts_utc"], descending=[False, True, False])
    peak = ranked.group_by("date", maintain_order=True).first().select(
        "date", pl.col("value").alias("max_mw"), pl.col("ts_utc").alias("peak_ts_utc"),
        "hour_local")
    counts = f.group_by("date").agg(pl.len().alias("n_hours"),
                                    pl.col("value").null_count().alias("n_null"))
    # the local hour index within the day (0..n-1), which differs from the clock hour on
    # the fall-back day; it is what the 24-value series below are indexed by
    out = peak.join(counts, on="date", how="left").with_columns(
        ((pl.col("peak_ts_utc") - pl.col("date").map_elements(
            lambda d: local_day_utc(d)[0], return_dtype=pl.Datetime("us", "UTC")))
         .dt.total_hours()).cast(pl.Int64).alias("peak_hour_local"))
    return out.select("date", "max_mw", "peak_ts_utc", "peak_hour_local", "n_hours",
                      pl.col("n_null").cast(pl.Int64)).sort("date")


def select_days(daily: pl.DataFrame, k: int = K) -> pl.DataFrame:
    """The top `k` days by max_mw; ties go to the earlier date. Adds `rank` (1..k)."""
    top = daily.sort(["max_mw", "date"], descending=[True, False]).head(k)
    return top.with_columns(pl.int_range(1, top.height + 1, dtype=pl.Int64).alias("rank"))


# --------------------------------------------------------------------------- day accounting


def day_load_kwh(ledger: pl.DataFrame, site: str, d: date) -> np.ndarray:
    """Facility kWh at `site` in each UTC hour of the local day `d` (exact overlap)."""
    t0, n = local_day_utc(d)
    return hourly_load_kwh(ledger, site, _us(t0), n)


def day_co2(ledger: pl.DataFrame, d: date, ci: dict[str, np.ndarray]) -> dict:
    """Day-sliced attributed CO₂ of one policy's ledger on day `d`. `ci[site]`: g/kWh for each
    hour of the day. Execution by hour; transfer at its arrival hour (F14.5)."""
    t0, n = local_day_utc(d)
    loads = {s: day_load_kwh(ledger, s, d) for s in SITES}
    for s in SITES:
        if ci[s].shape != (n,) or not np.isfinite(ci[s]).all():
            raise ValueError(f"{s}: need {n} finite hourly intensities for {d}")
    exec_kg = math.fsum(math.fsum((loads[s] * ci[s] / 1000).tolist()) for s in SITES)
    t0_us = _us(t0)
    r = ledger.filter((pl.col("site") != HOME)
                      & (pl.col("arrival_ts") >= t0)
                      & (pl.col("arrival_ts") < t0 + timedelta(hours=n))).sort("job_uid")
    tr = []
    for site, arr, g, dur in r.select(
            "site", pl.col("arrival_ts").dt.epoch("us"), "gpus", "duration_s").iter_rows():
        k = (arr - t0_us) // H_US
        req_us = round(dur * 1_000_000)
        fac = TRANSFER_FRACTION * g * GPU_KW * req_us / H_US * PUE
        tr.append(0.5 * fac * (ci[HOME][k] + ci[site][k]) / 1000)
    tr_kg = math.fsum(tr)
    return {"execution_kg": exec_kg, "transfer_kg": tr_kg, "total_kg": exec_kg + tr_kg,
            "n_transfers": len(tr),
            "energy_mwh_by_site": {s: math.fsum(loads[s].tolist()) / 1000 for s in SITES},
            "load_kwh": loads}


# --------------------------------------------------------------------------- weather


def c_to_f(c: float) -> float:
    return c * 9.0 / 5.0 + 32.0


def degree_days(tmax_f: float, tmin_f: float, base: float = BASE_F) -> tuple[float, float]:
    """(CDD, HDD) from the mean of the daily max and min, base 65 °F."""
    m = (tmax_f + tmin_f) / 2
    return max(0.0, m - base), max(0.0, base - m)


def day_weather(frame: pl.DataFrame, d: date, col: str = "temperature_2m") -> dict:
    """Daily max/min (°F) over the instants valid in the local day, and degree days.
    `frame`: valid_time_utc, <col> in °C (Open-Meteo)."""
    t0, n = local_day_utc(d)
    x = frame.filter((pl.col("valid_time_utc") >= t0)
                     & (pl.col("valid_time_utc") < t0 + timedelta(hours=n))
                     & pl.col(col).is_not_null())[col].cast(pl.Float64)
    if x.len() == 0:
        return {"n": 0, "tmax_f": None, "tmin_f": None, "cdd": None, "hdd": None}
    hi, lo = c_to_f(float(x.max())), c_to_f(float(x.min()))
    cdd, hdd = degree_days(hi, lo)
    return {"n": x.len(), "tmax_f": hi, "tmin_f": lo, "cdd": cdd, "hdd": hdd}


# --------------------------------------------------------------------------- inputs (pre-seal)


def balance_hourly() -> pl.DataFrame:
    """PACE hourly demand (spikes removed), wind, solar and net load via the pre-seal loader."""
    from gridpilot.data.eia930 import add_demand_clean
    from gridpilot.forecast import load_series

    dem = add_demand_clean(load_series("demand").rename({"value": "demand_adj_mw"}))
    w = load_series("wind").select("ts_utc", pl.col("value").alias("wind_mw"))
    s = load_series("solar").select("ts_utc", pl.col("value").alias("solar_mw"))
    f = dem.select("ts_utc", "demand_clean_mw").join(w, on="ts_utc", how="left").join(
        s, on="ts_utc", how="left")
    return f.with_columns(
        (pl.col("demand_clean_mw") - pl.col("wind_mw").fill_null(0.0)
         - pl.col("solar_mw").fill_null(0.0)).alias("net_load_mw")).sort("ts_utc")


def weather_frames() -> dict[str, pl.DataFrame]:
    from gridpilot.data.weather import load

    out = {}
    for pid, api, _, _ in WEATHER_POINTS:
        f = load(api, point_ids=[pid])  # pre-seal: drop_sealed inside
        out[pid] = f.select("valid_time_utc", "temperature_2m") if f.height else f
    return out


def _truth(run_dir: Path) -> pl.DataFrame:
    return drop_sealed(pl.read_parquet(run_dir / "truth_fill.parquet"))


def _day_series(frame: pl.DataFrame, d: date, cols: list[str]) -> dict[str, list]:
    t0, n = local_day_utc(d)
    grid = pl.DataFrame({"ts_utc": [t0 + timedelta(hours=k) for k in range(n)]},
                        schema={"ts_utc": pl.Datetime("us", "UTC")})
    j = grid.join(frame, on="ts_utc", how="left").sort("ts_utc")
    return {c: [None if v is None else float(v) for v in j[c].to_list()] for c in cols}


def _r(x, nd=4):
    return None if x is None else round(float(x), nd)


# --------------------------------------------------------------------------- artifact


def _e(v, unit, ev, pid, reason=None):
    if isinstance(v, list):
        v = [_r(x) for x in v]
        nul = any(x is None for x in v)
        return env(v, unit, ev, pid, reason=reason if nul else None)
    v = _r(v)
    return env(v, unit, ev, pid, status="ok" if v is not None else "unavailable",
               reason=None if v is not None else (reason or "no value"))


def build_day(d: date, row: dict, bal: pl.DataFrame, truth: pl.DataFrame,
              ledgers: dict[str, pl.DataFrame], weather: dict[str, pl.DataFrame],
              sources: list[dict]) -> dict:
    t0, n = local_day_utc(d)
    pid = f"{PROV}:{d.isoformat()}"
    ser = _day_series(bal, d, ["demand_clean_mw", "wind_mw", "solar_mw", "net_load_mw"])
    ci, tier = {}, {}
    for s in SITES:
        t = truth.filter(pl.col("ba") == s).select("ts_utc", "ci_g_kwh", "tier")
        x = _day_series(t, d, ["ci_g_kwh", "tier"])
        if any(v is None for v in x["ci_g_kwh"]):
            raise ValueError(f"{s} {d}: missing filled truth")
        ci[s] = np.asarray(x["ci_g_kwh"], dtype=float)
        tier[s] = [int(v) for v in x["tier"]]
    pk = int(row["peak_hour_local"])
    acc = {p: day_co2(ledgers[p], d, ci) for p in POLICIES}
    u_kg = acc["U"]["total_kg"]
    pol = {}
    for p in POLICIES:
        a = acc[p]
        pace = a["load_kwh"][HOME] / 1000  # kWh per hour → mean MW in the hour
        pol[p] = {
            "label": POLICY_LABEL[p],
            "utah_cluster_mw": _e(pace.tolist(), "MW", "simulated", f"{pid}:{p}:pace_mw"),
            "utah_cluster_at_peak_mw": _e(pace[pk], "MW", "simulated", f"{pid}:{p}:pace_peak"),
            "utah_cluster_at_peak_change_vs_U_mw": _e(
                pace[pk] - acc["U"]["load_kwh"][HOME][pk] / 1000, "MW", "simulated",
                f"{pid}:{p}:pace_peak_dU"),
            "energy_mwh_by_site": {s: _e(a["energy_mwh_by_site"][s], "MWh", "simulated",
                                         f"{pid}:{p}:mwh:{s}") for s in SITES},
            "moved_energy_mwh": _e(math.fsum(a["energy_mwh_by_site"][s] for s in SITES
                                             if s != HOME), "MWh", "simulated",
                                   f"{pid}:{p}:moved_mwh"),
            "co2_t": _e(a["total_kg"] / 1000, "t_CO2", "simulated", f"{pid}:{p}:co2_t"),
            "execution_co2_t": _e(a["execution_kg"] / 1000, "t_CO2", "simulated",
                                  f"{pid}:{p}:exec_t"),
            "transfer_co2_t": _e(a["transfer_kg"] / 1000, "t_CO2", "simulated",
                                 f"{pid}:{p}:transfer_t"),
            "co2_change_vs_U_frac": _e((a["total_kg"] - u_kg) / u_kg if u_kg else None,
                                       "fraction", "simulated", f"{pid}:{p}:dU_frac"),
        }
    wx = {}
    for pid_w, api, name, role in WEATHER_POINTS:
        w = day_weather(weather[pid_w], d) if weather.get(pid_w) is not None \
            and weather[pid_w].height else {"n": 0, "tmax_f": None, "tmin_f": None,
                                            "cdd": None, "hdd": None}
        why = f"no {api} temperatures for {name} on this day"
        wx[pid_w] = {
            "name": name, "role": role, "api": api,
            "product": ("Historical Forecast API, best_match: each hour from a run issued a "
                        "few hours before it (the issue closest before the hour)"
                        if api == "historical-forecast" else
                        "Previous Runs API, best_match, previous_day0 (the latest run)"),
            "tmax_f": _e(w["tmax_f"], "degF", "forecast", f"{pid}:wx:{pid_w}:tmax", why),
            "tmin_f": _e(w["tmin_f"], "degF", "forecast", f"{pid}:wx:{pid_w}:tmin", why),
            "cdd_65f": _e(w["cdd"], "degF_day", "forecast", f"{pid}:wx:{pid_w}:cdd", why),
            "hdd_65f": _e(w["hdd"], "degF_day", "forecast", f"{pid}:wx:{pid_w}:hdd", why),
            "n_instants": env(w["n"], "hours", "measured", f"{pid}:wx:{pid_w}:n"),
        }
    filled = sum(1 for v in tier[HOME] if v >= 2)
    return {
        "date": d.isoformat(),
        "weekday": d.strftime("%A"),
        "rank": env(int(row["rank"]), "rank", "observed", f"{pid}:rank"),
        "hours_utc": {"start": iso(t0), "n": env(n, "hours", "measured", f"{pid}:n_hours")},
        "peak": {
            "net_load_mw": _e(row["max_mw"], "MW", "observed", f"{pid}:peak_mw"),
            "hour_index": env(pk, "hour", "observed", f"{pid}:peak_hour"),
            "ts_utc": iso(row["peak_ts_utc"]),
            "local_label": row["peak_ts_utc"].astimezone(TZ).strftime("%H:%M %Z"),
        },
        "pace": {
            "demand_mw": _e(ser["demand_clean_mw"], "MW", "observed", f"{pid}:demand",
                            "isolated spike removed by the spike rule"),
            "wind_mw": _e(ser["wind_mw"], "MW", "observed", f"{pid}:wind", "not reported"),
            "solar_mw": _e(ser["solar_mw"], "MW", "observed", f"{pid}:solar", "not reported"),
            "net_load_mw": _e(ser["net_load_mw"], "MW", "observed", f"{pid}:net",
                              "demand hour removed by the spike rule"),
            "ci_g_kwh": _e(ci[HOME].tolist(), "g/kWh", "modeled", f"{pid}:ci"),
            "ci_filled_hours": env(filled, "hours", "measured", f"{pid}:ci_filled"),
        },
        "policies": pol,
        "weather": wx,
        "context": sources,
    }


def build_artifact(*, run_id: str, daily: pl.DataFrame, top: pl.DataFrame,
                   days: list[dict], check: dict) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "illustrative",
        "title": "Utah's toughest grid days",
        "window": "validation",
        "note": ("illustrative case study; validation days only; from the registered run's "
                 "ledgers (no new simulation); not part of the registered experiment"),
        "registered_run_id": run_id,
        "local_tz": TZ_NAME,
        "rule": RULE,
        "days_considered": {
            "first": DAY_START.isoformat(),
            "last": (DAY_END - timedelta(days=1)).isoformat(),
            "n": env(daily.height, "days", "measured", f"{PROV}:n_days"),
            "n_with_null_hours": env(int((daily["n_null"] > 0).sum()), "days", "measured",
                                     f"{PROV}:n_days_null"),
        },
        "ranking_top10": [
            {"date": r["date"].isoformat(),
             "max_net_load_mw": _e(r["max_mw"], "MW", "observed", f"{PROV}:top10:{i}")}
            for i, r in enumerate(daily.sort(["max_mw", "date"], descending=[True, False])
                                  .head(10).iter_rows(named=True))],
        "accounting": ACCOUNTING_NOTE,
        "accounting_check": check,
        "hour_index": ("index i of every hourly series is the i-th hour of the local "
                       "(America/Denver) day, starting at local midnight"),
        "weather_note": ("descriptive context only: it never feeds any model or decision. "
                         "Archived forecast products (Open-Meteo, CC BY 4.0), so labelled "
                         "forecast; daily max and min over the hourly instants of the local "
                         "day; degree days from the mean of max and min, base 65 °F. Salt Lake "
                         "City is the only PACE load-centre point in the archive; Milford and "
                         "Medicine Bow are resource sites, not load-weighted"),
        "context_note": ("context, not evidence for any result: public sources found for each "
                         "date (accessed 27 Oct 2026); no cause is inferred beyond the source"),
        "days": days,
    }


def from_run(run_dir: Path, sources: dict[str, list[dict]]) -> dict:
    """Read the registered validation run and the pre-seal grid and weather; build."""
    from gridpilot.eval.accounting import TruthTable, fsum_by, job_accounting

    cfg = json.loads((run_dir / "config.json").read_text())
    if cfg.get("window") != "validation":
        raise ValueError(f"{run_dir} is not a validation run")
    bal = balance_hourly()
    daily = daily_max(bal.select("ts_utc", pl.col("net_load_mw").alias("value")))
    top = select_days(daily)
    led = {p: pl.read_parquet(run_dir / f"ledger_{p}.parquet") for p in POLICIES}
    truth = _truth(run_dir)
    # whole-window check: day slicing (hourly loads × hourly truth) reproduces the
    # registered execution accounting exactly
    tt = TruthTable(truth)
    jobs = led["U"].select("job_uid",
                           pl.col("job_uid").str.split("#").list.first().alias("source_id"),
                           "arrival_ts", "gpus", "duration_s")
    t_start = datetime.fromisoformat(cfg["eval_start"])
    last = max(x["end_ts"].max() for x in led.values())
    n_all = -(-(_us(last) - _us(t_start)) // H_US)
    grid = pl.DataFrame({"ts_utc": [t_start + timedelta(hours=k) for k in range(n_all)]},
                        schema={"ts_utc": pl.Datetime("us", "UTC")})
    check = {"rule": "Σ over every hour of the cohort window of hourly kWh × hourly intensity "
                     "equals Σ execution_co2_kg of the registered job accounting (rel 1e-9)"}
    for p in POLICIES:
        acc = job_accounting(led[p], jobs, tt)
        want = fsum_by(acc, "execution_co2_kg")
        got = []
        for s in SITES:
            c = grid.join(truth.filter(pl.col("ba") == s), on="ts_utc", how="left")
            civ = c["ci_g_kwh"].fill_null(0.0).to_numpy()
            got.append(math.fsum((hourly_load_kwh(led[p], s, _us(t_start), n_all) * civ
                                  / 1000).tolist()))
        g = math.fsum(got)
        if not math.isclose(g, want, rel_tol=1e-9):
            raise AssertionError(f"{p}: hourly-sliced CO₂ {g} != accounting {want}")
        check[p] = {"hourly_sliced_t": _e(g / 1000, "t_CO2", "simulated",
                                          f"{PROV}:check:{p}:sliced"),
                    "accounting_t": _e(want / 1000, "t_CO2", "simulated",
                                       f"{PROV}:check:{p}:acc")}
    wx = weather_frames()
    days = [build_day(r["date"], r, bal, truth, led, wx, sources.get(r["date"].isoformat(), []))
            for r in top.iter_rows(named=True)]
    return build_artifact(run_id=run_dir.name, daily=daily, top=top, days=days, check=check)
