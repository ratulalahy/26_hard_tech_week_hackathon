"""Stage 3 T20 (D-071): the pre-registered, secondary and descriptive analyses of the sealed
test year, and their validation counterparts.

The rules are fixed here, in the frozen `lab/` tree, before the seal opens; every result is
reported whatever it shows. Nothing here replaces the headline, the deployed policy (S) or any
frozen decision field. The test-year side runs only inside the single logged opening
(`run_slice --window test`, after the primary run is exported, same session, lock and witness);
every test-window grid read goes through `gridpilot.seal.sealed_read` inside a
`seal.purpose_scope` naming its D-071 item. Outputs: `results/test/extras.json`, labelled
"test year, pre-registered secondary (D-071)". The validation counterparts that need a
computation (items 2b, 5 and 6) are exported before the freeze to
`results/extras-validation.json` (`make extras-validation`), so the test run only reads
committed numbers for its frozen rules and the drift table.

Items (D-071; brief `docs/superpowers/plans/amendments/stage3-T20-test-year-extras.md`):
1. the seven D-058 extension scenarios on the test year, with the frozen test forecasts (the
   runner is `run_slice.run_test_extension`; this module formats their summaries);
2. storage: the 4 MWh / 1 MW headline and the 8 MWh plateau, on the test U ledger and the test
   mobility ≤ 8 GPUs W ledger, with the committed validation schedule (charge/discharge hours
   from the training years) and rush threshold, fixed schedule (A) and daily hindsight (B);
2b. (D-073) a second, peak-aimed fixed schedule from the training years only: discharge in the
   4 local hours most often among the day's top 4 net-load hours, charge in the 4 hours (of
   the rest) most often the day's lowest net load; the same battery, efficiency and site cap;
   on validation and the test year, with rush-hour import, peak import, attributed CO₂ and the
   flat-marginal line beside the carbon schedule. A design comparison; the carbon headline is
   unchanged;
3. toughest days: the D-066 rule on [TEST_START, F): the top 3 PACE local days by daily maximum
   net load, ties to the earlier date; U/S/W CO₂ by day incl. transfer, the whole-window
   execution/transfer/total checks, and the Salt Lake City archive temperature;
4. water: the T14 method on the test ledgers under both hydro conventions, the sign under each;
5. seasonal split: S and W vs U by meteorological season of each arrival week's Monday
   (America/Denver), paired block bootstrap where a season has at least 8 weeks;
6. forecast skill: per frozen series, MAE of K (calendar climatology), W and L, L and W relative
   to K, PACE demand against EIA's day-ahead forecast, the p10/p90 coverage of the frozen
   intervals (validation residual quantiles before the selection cutoff), and L permutation
   importance by feature group (5 shuffles, seed 20261027);
7. the validation → test drift table: every headline number and every item.
"""

from __future__ import annotations

import io
import json
import math
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from gridpilot.results import env, iso
from gridpilot.splits import TEST_START, VALIDATION_START

LABEL = "test year, pre-registered secondary (D-071)"
LABEL_VALIDATION = "validation counterpart of the pre-registered test-year extras (D-071)"
TZ_NAME = "America/Denver"
TZ = ZoneInfo(TZ_NAME)
SEED = 20261027
N_SHUFFLES = 5
BLOCKS = (2, 4, 8)
MIN_SEASON_WEEKS = 8
SEASONS = ("DJF", "MAM", "JJA", "SON")
SEASON_OF_MONTH = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM", 6: "JJA",
                   7: "JJA", 8: "JJA", 9: "SON", 10: "SON", 11: "SON"}
SEASON_RULE = ("each arrival week (Monday 00:00 America/Denver, as the registered weekly totals) "
               "belongs to the meteorological season of its Monday's month (DJF, MAM, JJA, SON); "
               "a season's weeks need not be contiguous (SON joins the window's two ends); "
               "the paired block bootstrap (blocks 2, 4 and 8; 4 primary) runs on a season's "
               "weekly totals only when it has at least 8 weeks; descriptive only")
STORAGE_SIZES = (4.0, 8.0)  # the D-067 headline and the validation plateau
STORAGE_ETA = 0.85
PEAK_K = 4  # D-073: hours in each leg of the peak-aimed schedule
PEAK_RULE = ("D-073 (pre-registered before the opening): from the training years' PACE net load "
             "(2022-01-01 to 2024-10-29, the storage training window), each America/Denver day's "
             "top 4 hours and its lowest hour (complete days only); discharge in the 4 local "
             "hours most often among the day's top 4 (ties to the earlier hour), charge in the 4 "
             "other hours most often the day's lowest (ties to the earlier hour); same battery, "
             "η 0.85, P = E/4 and site cap as D-061/D-067; a design comparison, not the headline")
EXT_POLICIES = ("U", "S", "W", "L")
DAY_POLICIES = ("U", "S", "W")
WATER_POLICIES = ("U", "S", "W", "L")
K_DAYS = 3
# validation windows of the item 6 statistics (targets) and the frozen intervals (issues)
VAL_SKILL = (VALIDATION_START, datetime(2025, 10, 24, tzinfo=UTC))
FEATURE_GROUPS = {
    "calendar": ("lead_h", "hour", "month", "dow", "weekend", "doy"),
    "weekly memory": ("lag_168", "lag_336", "lag_504", "lag_672", "lag_median", "n_lags"),
    "most recent": ("last_value", "last_age_h", "same_hour_value", "same_hour_days"),
    "recent level": ("trail7_mean", "trail7_range", "trail7_n", "trail24_mean"),
    "missing-data flags": ("miss_lag_168", "miss_lag_336", "miss_lag_504", "miss_lag_672",
                           "miss_last", "miss_same_hour"),
}
INTERVAL_RULE = ("frozen empirical interval: the 10th and 90th percentiles of daily-forecast "
                 "residuals (truth − forecast) per series and model, over the validation "
                 "selection issues [2024-11-01, 2025-10-24) of the registered forecast run (spec "
                 "§6); coverage = share of scored hours with p10 ≤ residual ≤ p90; no guaranteed "
                 "conditional coverage")
PI_RULE = ("L permutation importance: the frozen L refitted exactly (its forecasts must match "
           "the run's), each feature group's columns shuffled together across the scored rows, "
           "MAE increase over the unshuffled MAE, averaged over 5 shuffles (numpy default_rng "
           "seed 20261027 per series and group)")
EIA_DF_COL = "demand_forecast_mw"
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
H = timedelta(hours=1)
H_US = 3600 * 1_000_000


def _us(t: datetime) -> int:
    return (t - _EPOCH) // timedelta(microseconds=1)


def E(v, unit: str, ev: str, pid: str, reason: str | None = None) -> dict:
    """An envelope; a None value becomes `unavailable` with its reason."""
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return env(None, unit, ev, pid, status="unavailable", reason=reason or "undefined")
    return env(v, unit, ev, pid)


def not_run(pid: str, reason: str) -> dict:
    return {"status": "not_run", "reason": reason, "provenance_id": pid}


def _jobs(ledger_u: pl.DataFrame) -> pl.DataFrame:
    """The accounting job frame from the U ledger (as storage, water and case days build it)."""
    return ledger_u.select("job_uid",
                           pl.col("job_uid").str.split("#").list.first().alias("source_id"),
                           "arrival_ts", "gpus", "duration_s")


# --------------------------------------------------------------------------- item 1


def extension_section(name: str, summary: dict | None, error: str | None, pid: str) -> dict:
    """One extension scenario on the test year, from its run's summary.json: each policy's CO₂
    and its contrasts against U (the registered paired block bootstrap, blocks 2, 4, 8)."""
    if summary is None:
        return {"scenario": name, **not_run(f"{pid}:{name}", error or "the run did not finish")}
    pols = summary["policies"]
    return {"scenario": name, "status": "ok", "run_id": summary["run_id"],
            "knobs": summary["scenario"]["knobs"], "note": summary["scenario"]["note"],
            "covered": summary["covered"], "n_weeks": summary["cohort"]["n_weeks"],
            "policies": {p: {"co2_kg": pols[p]["metrics"]["co2_kg"],
                             "late_jobs": pols[p]["metrics"]["late_jobs"],
                             "feasible": pols[p]["feasible"]} for p in pols},
            "vs_U": {c["candidate"]: c["blocks"] for c in summary["contrasts"]
                     if c["reference"] == "U"},
            "relaxed_bound_ok": summary["relaxed_bound"]["all_feasible_policies_ok"]}


# --------------------------------------------------------------------------- item 2 / 2b


def peak_schedule(net_train: pl.DataFrame, k: int = PEAK_K) -> dict:
    """D-073: the peak-aimed schedule from training-year net load (`ts_utc`, `value`). Days
    with a missing hour are skipped."""
    from gridpilot import storage as st

    f = net_train.filter((pl.col("ts_utc") >= st.TRAIN_START) & (pl.col("ts_utc") < st.TRAIN_END))
    if f.height and f["ts_utc"].max() >= TEST_START:
        raise ValueError("training net load reaches the seal")
    lt = pl.col("ts_utc").dt.convert_time_zone(TZ_NAME)
    f = f.with_columns(lt.dt.date().alias("date"), lt.dt.hour().alias("hour"))
    full = f.group_by("date").agg(pl.col("value").null_count().alias("nn"), pl.len().alias("n"))
    ok = full.filter((pl.col("nn") == 0) & (pl.col("n") >= 23))["date"]
    f = f.filter(pl.col("date").is_in(ok.implode()))
    top = (f.sort(["date", "value", "ts_utc"], descending=[False, True, False])
           .group_by("date", maintain_order=True).head(k))
    low = f.sort(["date", "value", "ts_utc"]).group_by("date", maintain_order=True).head(1)
    top_n = np.bincount(top["hour"].to_numpy(), minlength=24)
    low_n = np.bincount(low["hour"].to_numpy(), minlength=24)
    dis = sorted(sorted(range(24), key=lambda h: (-top_n[h], h))[:k])
    chg = sorted(sorted((h for h in range(24) if h not in dis), key=lambda h: (-low_n[h], h))[:k])
    return {"rule": PEAK_RULE, "charge_hours": chg, "discharge_hours": dis,
            "n_days": int(ok.len()), "top4_counts": top_n.tolist(),
            "lowest_counts": low_n.tolist()}


def schedule_comparison(*, loads: Mapping[str, np.ndarray], ci: np.ndarray, grid: pl.DataFrame,
                        mask: np.ndarray, schedules: Mapping[str, dict], pid: str) -> dict:
    """D-073: each fixed schedule × case × size at η 0.85: attributed CO₂ with and without
    storage, the flat-marginal line, and the cluster's grid import in the rush hours and at its
    annual peak, before and after storage."""
    from gridpilot import storage as st

    hour = grid["hour"].to_numpy()
    out = {}
    for name, sch in schedules.items():
        out[name] = {"charge_hours": E(list(sch["charge_hours"]), "local_hour", "assumed",
                                       f"{pid}:{name}:charge"),
                     "discharge_hours": E(list(sch["discharge_hours"]), "local_hour", "assumed",
                                          f"{pid}:{name}:discharge"), "cases": {}}
        for case, load in loads.items():
            rows = {}
            for e_mwh in STORAGE_SIZES:
                c, d, soc = st.fixed_schedule(load, hour, sch["charge_hours"],
                                              sch["discharge_hours"], e_kwh=e_mwh * 1000,
                                              p_kw=e_mwh * 1000 * st.P_OVER_E, eta=STORAGE_ETA,
                                              conn_kw=st.CONNECTION_KW)
                o = st.outcome(load, ci, c, d, soc)
                iv = st.import_view(load, c, d, hour, mask, sch["charge_hours"])
                q = f"{pid}:{name}:{case}:{e_mwh:g}"
                rows[f"{e_mwh:g}"] = {
                    "co2_t": E(o["co2_kg"] / 1000, "t_CO2", "simulated", f"{q}:co2"),
                    "base_co2_t": E(o["base_co2_kg"] / 1000, "t_CO2", "simulated", f"{q}:base"),
                    "cut_t": E(o["cut_kg"] / 1000, "t_CO2", "simulated", f"{q}:cut"),
                    "cut_frac": E(o["cut_frac"], "fraction", "simulated", f"{q}:cut_frac"),
                    "flat_marginal_cut_t": E(o["flat_cut_kg"] / 1000, "t_CO2", "simulated",
                                             f"{q}:flat"),
                    "rush_import_before_mw": E(iv["rush_before_mw"], "MW", "simulated",
                                               f"{q}:rush0", "no rush hours"),
                    "rush_import_after_mw": E(iv["rush_after_mw"], "MW", "simulated",
                                              f"{q}:rush1", "no rush hours"),
                    "peak_import_before_mw": E(iv["peak_before_mw"], "MW", "simulated",
                                               f"{q}:peak0"),
                    "peak_import_after_mw": E(iv["peak_after_mw"], "MW", "simulated",
                                              f"{q}:peak1"),
                    "rush_hours_discharging": E(int((d[mask] > 0).sum()), "hours", "simulated",
                                                f"{q}:rush_dis")}
            out[name]["cases"][case] = rows
    return {"rule": PEAK_RULE, "label_note": "a design comparison; the carbon schedule stays the "
                                             "headline", "schedules": out}


def storage_section(*, ledgers: Mapping[str, pl.DataFrame], mob_w: pl.DataFrame | None,
                    filled: pl.DataFrame, eval_start: datetime, net: pl.DataFrame,
                    committed: dict | None, pid: str, peak: dict | None = None,
                    window=None, label: str = LABEL) -> dict:
    """D-061/D-067 storage on the test ledgers; schedule and rush threshold are the committed
    validation artifact's (the training-year rules), never refitted on test. With `peak`
    (D-073), the peak-aimed schedule is compared with the carbon one."""
    from gridpilot import storage as st
    from gridpilot.eval.accounting import TruthTable, fsum_by, job_accounting
    from gridpilot.sim import SITES

    if committed is None:
        return not_run(pid, "results/storage.json (the frozen schedule and threshold) is absent")

    def _v(x):
        return x["value"] if isinstance(x, dict) else x

    sched = {"charge_hours": [int(h) for h in _v(committed["schedule"]["charge_hours"])],
             "discharge_hours": [int(h) for h in _v(committed["schedule"]["discharge_hours"])]}
    thr = float(committed["rush"]["threshold_mw"]["value"])
    cases_led = {"U": ledgers["U"]}
    if mob_w is not None:
        cases_led["mobility_le_8gpus_W"] = mob_w
    last_end = max(x["end_ts"].max() for x in (*[ledgers[p] for p in ("U", "S", "W")],
                                                *cases_led.values()))
    win = st.cohort_window(eval_start, last_end)
    grid = st.hour_grid(*win)
    t0, n = _us(win[0]), grid.height
    ci = (grid.join(filled.filter(pl.col("ba") == st.SITE).select("ts_utc", "ci_g_kwh"),
                    on="ts_utc", how="left")["ci_g_kwh"])
    if ci.null_count():
        raise ValueError(f"{ci.null_count()} window hours have no filled PACE truth")
    ci = ci.to_numpy().astype(float)
    nv = grid.join(net, on="ts_utc", how="left")["value"].to_numpy().astype(float)
    mask = np.nan_to_num(nv, nan=-np.inf) >= thr
    peak_idx = int(np.nanargmax(nv))
    out_cases = {}
    loads = {k: st.hourly_load_kwh(v, st.SITE, t0, n) for k, v in cases_led.items()}
    sw = {k: st.sweep(loads[k], ci, grid, sched, sizes_mwh=STORAGE_SIZES, etas=(STORAGE_ETA,))
          for k in cases_led}
    for k in cases_led:
        rows = {}
        for strat in ("A", "B"):
            rows[strat] = {}
            for e_mwh, (o, _) in zip(STORAGE_SIZES, sw[k][strat][STORAGE_ETA], strict=True):
                q = f"{pid}:{k}:{strat}:{e_mwh:g}"
                rows[strat][f"{e_mwh:g}"] = {
                    "base_co2_t": E(o["base_co2_kg"] / 1000, "t_CO2", "simulated", f"{q}:base"),
                    "cut_t": E(o["cut_kg"] / 1000, "t_CO2", "simulated", f"{q}:cut"),
                    "cut_frac": E(o["cut_frac"], "fraction", "simulated", f"{q}:cut_frac"),
                    "losses_mwh": E(o["losses_mwh"], "MWh", "simulated", f"{q}:losses"),
                    "flat_marginal_cut_t": E(o["flat_cut_kg"] / 1000, "t_CO2", "simulated",
                                             f"{q}:flat")}
        out_cases[k] = rows
    # move small + store: (U − (W_mob − its storage cut)) / U, every site and transfer once
    tt = TruthTable(filled, window=window or _active_window())
    jobs = _jobs(ledgers["U"])
    u_kg = fsum_by(job_accounting(ledgers["U"], jobs, tt), "co2_kg")
    combined = {"rule": committed["combined"]["rule"].replace("registered cohort window",
                                                              "cohort window")}
    if mob_w is not None:
        w_kg = fsum_by(job_accounting(mob_w, jobs, tt), "co2_kg")
        combined["U_co2_t"] = E(u_kg / 1000, "t_CO2", "simulated", f"{pid}:combined:U")
        combined["W_mob_co2_t"] = E(w_kg / 1000, "t_CO2", "simulated", f"{pid}:combined:W_mob")
        combined["move_only_cut_frac"] = E((u_kg - w_kg) / u_kg, "fraction", "simulated",
                                           f"{pid}:combined:move_only")
        combined["move_and_store_cut_frac"] = {
            strat: {f"{e:g}": E((u_kg - (w_kg - o["cut_kg"])) / u_kg, "fraction", "simulated",
                                f"{pid}:combined:{strat}:{e:g}")
                    for e, (o, _) in zip(STORAGE_SIZES, sw["mobility_le_8gpus_W"][strat]
                                         [STORAGE_ETA], strict=True)}
            for strat in ("A", "B")}
    else:
        combined.update(not_run(f"{pid}:combined", "the mobility ≤ 8 GPUs run did not finish"))
    site_loads = {p: {s: st.hourly_load_kwh(ledgers[p], s, t0, n) for s in SITES}
                  for p in ("U", "S", "W")}
    relief = st.peak_relief(site_loads, mask, peak_idx)
    if peak is not None:  # D-073 (item 2b): the peak-aimed schedule beside the carbon one
        comparison = schedule_comparison(loads=loads, ci=ci, grid=grid, mask=mask,
                                         schedules={"carbon": sched, "peak": peak},
                                         pid=f"{pid}:2b")
        comparison["peak_schedule_from"] = peak.get("from", "computed here (training years)")
    else:
        comparison = not_run(f"{pid}:2b", "no peak-aimed schedule (results/extras-validation"
                                          ".json absent)")
    return {
        "status": "ok", "label": label, "schedule_comparison": comparison,
        "rule": ("D-061/D-067 method unchanged: battery at the Utah cluster, η 0.85, P = E/4, "
                 "headline 4 MWh / 1 MW and the 8 MWh plateau; strategy A = the committed "
                 "fixed training-year schedule, B = the daily hindsight heuristic; the "
                 "flat-marginal line prices storage's net draw at 618 g/kWh, an associational "
                 "regression slope (not a causal marginal factor)"),
        "window": {"start": iso(win[0]), "end": iso(win[1]),
                   "n_hours": E(n, "hours", "measured", f"{pid}:n_hours")},
        "schedule": {"charge_hours": E(sched["charge_hours"], "local_hour", "assumed",
                                       f"{pid}:charge_hours"),
                     "discharge_hours": E(sched["discharge_hours"], "local_hour", "assumed",
                                          f"{pid}:discharge_hours"),
                     "source": "results/storage.json (training years 2022-01-01 to 2024-10-29)"},
        "flat_marginal_g_kwh": E(st.MARGINAL_FLAT_G_KWH, "g/kWh", "assumed",
                                 f"{pid}:flat_g_kwh"),
        "flat_marginal_label": "associational slope (PACE ΔCO₂/Δnet load OLS), not causal",
        "cases": out_cases,
        "combined": combined,
        "rush": {"threshold_mw": E(thr, "MW", "observed", f"{pid}:rush:thr"),
                 "threshold_source": "results/storage.json (the training years' 99% quantile)",
                 "n_hours": E(int(mask.sum()), "hours", "measured", f"{pid}:rush:n"),
                 "peak_net_load_mw": E(float(nv[peak_idx]), "MW", "observed", f"{pid}:rush:peak"),
                 "peak_hour_utc": iso(grid["ts_utc"][peak_idx])},
        "peak_relief": {p: {s: {k: E(v, "MW", "simulated", f"{pid}:relief:{p}:{s}:{k}",
                                     "no rush hours") for k, v in by.items()}
                            for s, by in sites.items()} for p, sites in relief.items()},
    }


def _active_window():
    from gridpilot.window import Window

    return Window.test()


# --------------------------------------------------------------------------- item 3


def test_days(F: datetime) -> list[date]:
    """America/Denver dates whose whole local day lies in [TEST_START, F)."""
    d = TEST_START.astimezone(TZ).date()
    out = []
    while True:
        a, b = local_day(d)
        if b > F:
            break
        if a >= TEST_START:
            out.append(d)
        d += timedelta(days=1)
    return out


def local_day(d: date) -> tuple[datetime, datetime]:
    a = datetime(d.year, d.month, d.day, tzinfo=TZ).astimezone(UTC)
    n1 = d + timedelta(days=1)
    return a, datetime(n1.year, n1.month, n1.day, tzinfo=TZ).astimezone(UTC)


def daily_max(net: pl.DataFrame, days: list[date]) -> pl.DataFrame:
    """Per local day: max_mw and the peak hour (earliest on a tie). `net`: ts_utc, value."""
    lt = pl.col("ts_utc").dt.convert_time_zone(TZ_NAME)
    f = net.with_columns(lt.dt.date().alias("date")).filter(pl.col("date").is_in(days))
    ranked = f.filter(pl.col("value").is_not_null()).sort(["date", "value", "ts_utc"],
                                                         descending=[False, True, False])
    return ranked.group_by("date", maintain_order=True).first().select(
        "date", pl.col("value").alias("max_mw"), pl.col("ts_utc").alias("peak_ts_utc"))


def select_days(daily: pl.DataFrame, k: int = K_DAYS) -> pl.DataFrame:
    top = daily.sort(["max_mw", "date"], descending=[True, False]).head(k)
    return top.with_columns(pl.int_range(1, top.height + 1, dtype=pl.Int64).alias("rank"))


def _ci_hours(filled: pl.DataFrame, t0: datetime, n: int) -> dict[str, np.ndarray]:
    from gridpilot.sim import SITES

    grid = pl.DataFrame({"ts_utc": [t0 + k * H for k in range(n)]},
                        schema={"ts_utc": pl.Datetime("us", "UTC")})
    return {s: grid.join(filled.filter(pl.col("ba") == s).select("ts_utc", "ci_g_kwh"),
                         on="ts_utc", how="left")["ci_g_kwh"].fill_null(0.0).to_numpy()
            for s in SITES}


def _sliced(ledger: pl.DataFrame, t0: datetime, n: int, ci: dict) -> dict:
    from gridpilot.case_days import transfer_by_arrival_kg
    from gridpilot.sim import SITES
    from gridpilot.storage import hourly_load_kwh

    loads = {s: hourly_load_kwh(ledger, s, _us(t0), n) for s in SITES}
    ex = math.fsum(math.fsum((loads[s] * ci[s] / 1000).tolist()) for s in SITES)
    tr = math.fsum(transfer_by_arrival_kg(ledger, t0, n, ci))
    return {"execution": ex, "transfer": tr, "total": ex + tr,
            "mwh_by_site": {s: math.fsum(loads[s].tolist()) / 1000 for s in SITES},
            "pace_kwh": loads["PACE"]}


def read_weather_json(buf: io.BytesIO) -> pl.DataFrame:
    """An Open-Meteo archive file as `ts_utc` (label − 1 h), `valid_time_utc`, temperature_2m."""
    hourly = json.loads(buf.read())["hourly"]
    f = pl.DataFrame({"time": hourly["time"], "temperature_2m": hourly["temperature_2m"]},
                     schema={"time": pl.Utf8, "temperature_2m": pl.Float64})
    vt = pl.col("time").str.to_datetime("%Y-%m-%dT%H:%M", time_zone="UTC", time_unit="us")
    return f.select(vt.alias("valid_time_utc"), (vt - pl.duration(hours=1)).alias("ts_utc"),
                    "temperature_2m")


def toughest_days_section(*, ledgers: Mapping[str, pl.DataFrame], cj: pl.DataFrame,
                          filled: pl.DataFrame, eval_start: datetime, F: datetime,
                          net: pl.DataFrame, weather: pl.DataFrame | None,
                          weather_reason: str | None, pid: str) -> dict:
    from gridpilot.case_days import degree_days
    from gridpilot.eval.accounting import TruthTable, fsum_by, job_accounting

    days = test_days(F)
    top = select_days(daily_max(net, days))
    tt = TruthTable(filled, window=_active_window())
    jobs = _jobs(ledgers["U"])
    last = max(ledgers[p]["end_ts"].max() for p in DAY_POLICIES)
    n_all = -(-(_us(last) - _us(eval_start)) // H_US)
    ci_all = _ci_hours(filled, eval_start, n_all)
    check = {"rule": "over every hour of the test cohort window, execution CO₂ sliced by hour, "
                     "transfer CO₂ by arrival hour and their total each equal the job "
                     "accounting (rel 1e-9)"}
    for p in DAY_POLICIES:
        acc = job_accounting(ledgers[p], jobs, tt)
        got = _sliced(ledgers[p], eval_start, n_all, ci_all)
        want = {"execution": fsum_by(acc, "execution_co2_kg"),
                "transfer": fsum_by(acc, "transfer_co2_kg"), "total": fsum_by(acc, "co2_kg")}
        check[p] = {k: {"ok": math.isclose(got[k], want[k], rel_tol=1e-9, abs_tol=1e-9),
                        "sliced_kg": E(got[k], "kg_CO2", "simulated", f"{pid}:check:{p}:{k}:s"),
                        "accounting_kg": E(want[k], "kg_CO2", "simulated",
                                           f"{pid}:check:{p}:{k}:a")}
                    for k in ("execution", "transfer", "total")}
    out_days = []
    for r in top.iter_rows(named=True):
        d = r["date"]
        a, b = local_day(d)
        n = int((b - a) / H)
        ci = _ci_hours(filled, a, n)
        per = {p: _sliced(ledgers[p], a, n, ci) for p in DAY_POLICIES}
        k_peak = int((r["peak_ts_utc"] - a) / H)
        q = f"{pid}:{d.isoformat()}"
        pol = {}
        for p in DAY_POLICIES:
            x, u = per[p], per["U"]
            pol[p] = {
                "co2_t": E(x["total"] / 1000, "t_CO2", "simulated", f"{q}:{p}:co2"),
                "execution_co2_t": E(x["execution"] / 1000, "t_CO2", "simulated", f"{q}:{p}:ex"),
                "transfer_co2_t": E(x["transfer"] / 1000, "t_CO2", "simulated", f"{q}:{p}:tr"),
                "co2_change_vs_U_frac": E((x["total"] - u["total"]) / u["total"]
                                          if u["total"] else None, "fraction", "simulated",
                                          f"{q}:{p}:dU", "no U CO₂ that day"),
                "energy_mwh_by_site": {s: E(v, "MWh", "simulated", f"{q}:{p}:mwh:{s}")
                                       for s, v in x["mwh_by_site"].items()},
                "utah_cluster_at_peak_mw": E(float(x["pace_kwh"][k_peak]) / 1000, "MW",
                                             "simulated", f"{q}:{p}:peak_mw")}
        wx = {"status": "not_run", "reason": weather_reason or "no archive rows"}
        if weather is not None:
            x = weather.filter((pl.col("valid_time_utc") >= a) & (pl.col("valid_time_utc") < b)
                               & pl.col("temperature_2m").is_not_null())["temperature_2m"]
            if x.len():
                hi, lo = float(x.max()) * 9 / 5 + 32, float(x.min()) * 9 / 5 + 32
                cdd, hdd = degree_days(hi, lo)
                wx = {"label": "Salt Lake City only", "status": "ok",
                      "source": "Open-Meteo Historical Forecast API archive (forecast product)",
                      "tmax_f": E(hi, "degF", "forecast", f"{q}:slc:tmax"),
                      "tmin_f": E(lo, "degF", "forecast", f"{q}:slc:tmin"),
                      "cdd_65f": E(cdd, "degF_day", "forecast", f"{q}:slc:cdd"),
                      "hdd_65f": E(hdd, "degF_day", "forecast", f"{q}:slc:hdd")}
        out_days.append({"date": d.isoformat(),
                         "rank": E(r["rank"], "rank", "observed", f"{q}:rank"),
                         "peak": {"net_load_mw": E(r["max_mw"], "MW", "observed", f"{q}:peak"),
                                  "hour_index": E(k_peak, "hour", "observed", f"{q}:peak_hour"),
                                  "ts_utc": iso(r["peak_ts_utc"])},
                         "policies": pol, "temperature": wx})
    return {"status": "ok", "label": LABEL,
            "rule": ("D-066 applied to the test window: the top 3 America/Denver days whose "
                     "whole day lies in [TEST_START, F), by PACE daily maximum hourly net load "
                     "(adjusted demand, isolated spikes removed, minus wind and solar), ties to "
                     "the earlier date; day-sliced CO₂ incl. transfer"),
            "days_considered": E(len(days), "days", "measured", f"{pid}:n_days"),
            "check": check,
            "all_checks_ok": all(c["ok"] for p in DAY_POLICIES for c in check[p].values()),
            "days": out_days}


# --------------------------------------------------------------------------- item 4


def water_balance_columns() -> list[str]:
    from gridpilot.water import FUEL_COLS

    return ["ba", "ts_utc", *[f"gen_{f}_adj_mw" for f in FUEL_COLS if f != "hydro_conv"],
            "gen_hydro_conv_adj_mw", "gen_hydro_adj_mw"]


def water_section(*, ledgers: Mapping[str, pl.DataFrame], balance: pl.DataFrame,
                  win: tuple[datetime, datetime], pid: str) -> dict:
    """T14 water on the test ledgers. `balance`: the sealed read of the fuel mix over
    [win[0] − MARGIN, win[1]). No water-saving claim: the sign is reported per convention."""
    from gridpilot import water as wa
    from gridpilot.data import water_factors as wf

    hydro_conv = pl.coalesce(pl.col("gen_hydro_conv_adj_mw"), pl.col("gen_hydro_adj_mw"))
    bal = balance.select(pl.col("ba").cast(pl.Utf8), "ts_utc",
                         *[pl.col(f"gen_{f}_adj_mw").cast(pl.Float64)
                           for f in wa.FUEL_COLS if f != "hydro_conv"],
                         hydro_conv.cast(pl.Float64).alias("gen_hydro_conv_adj_mw")
                         ).sort("ba", "ts_utc")
    gen = wa.intensity(bal)
    filled = wa.fill(gen, start=win[0] - wa.MARGIN, end=win[1])
    tts = wa.truth_tables(filled, window=_active_window())
    jobs = _jobs(ledgers["U"])
    res = {p: wa.policy_water(ledgers[p], jobs, tts) for p in WATER_POLICIES}
    lo, hi = wf.WUE_L_PER_KWH["low"], wf.WUE_L_PER_KWH["high"]
    lo, hi = (getattr(lo, "value", lo), getattr(hi, "value", hi))
    u = res["U"]
    pols = {}
    for p in WATER_POLICIES:
        r = res[p]
        ex, hy = r["ex_hydro"]["total"], r["hydro"]["total"]
        uex, uhy = u["ex_hydro"]["total"], u["hydro"]["total"]
        q = f"{pid}:{p}"
        d_ex, d_with = ex - uex, (ex + hy) - (uex + uhy)
        pols[p] = {
            "generation_gal": {"ex_hydro": E(ex, "gal", "simulated", f"{q}:ex"),
                               "hydro_evap": E(hy, "gal", "simulated", f"{q}:hydro"),
                               "with_hydro": E(ex + hy, "gal", "simulated", f"{q}:with")},
            "direct_cooling_gal": E([wa.direct_cooling_gal(r["it_kwh"], lo),
                                     wa.direct_cooling_gal(r["it_kwh"], hi)], "gal",
                                    "simulated", f"{q}:direct"),
            "kwh_share_filled": E(r["kwh_filled"] / r["energy_kwh"] if r["energy_kwh"] else None,
                                  "fraction", "simulated", f"{q}:filled"),
            "change_vs_U": {
                "ex_hydro_gal": E(d_ex, "gal", "simulated", f"{q}:d:ex"),
                "ex_hydro_frac": E(d_ex / uex if uex else None, "fraction", "simulated",
                                   f"{q}:d:ex:f"),
                "with_hydro_gal": E(d_with, "gal", "simulated", f"{q}:d:with"),
                "with_hydro_frac": E(d_with / (uex + uhy) if uex + uhy else None, "fraction",
                                     "simulated", f"{q}:d:with:f"),
                "sign_ex_hydro": "less" if d_ex < 0 else "more" if d_ex > 0 else "equal",
                "sign_with_hydro": "less" if d_with < 0 else "more" if d_with > 0 else "equal"},
        }
    return {"status": "ok", "label": LABEL, "caveats": list(wa.CAVEATS),
            "claim": "none: no water-saving claim; the sign under each hydro convention is "
                     "reported as found",
            "window": {"start": iso(win[0]), "end": iso(win[1])}, "policies": pols}


# --------------------------------------------------------------------------- item 5


def _season(week: datetime) -> str:
    return SEASON_OF_MONTH[week.astimezone(TZ).month]


def _boot_record(r: dict, n: int, pid: str) -> dict:
    labels = []
    if r["degenerate"]:
        labels.append("degenerate (n_weeks <= block)")
    if r["block"] == 8 and n <= 8:
        labels.append("low-n")
    return {"primary": r["block"] == 4, "labels": labels,
            "saving": E(r["saving"], "fraction", "simulated", f"{pid}:saving", "zero reference"),
            "saving_ci95": E(None if r["saving_ci"] is None else list(r["saving_ci"]),
                             "fraction", "simulated", f"{pid}:saving_ci",
                             r.get("saving_ci_null_reason") or "undefined"),
            "diff_kg": E(r["diff_kg"], "kg_CO2", "simulated", f"{pid}:diff"),
            "diff_kg_ci95": E(None if r["diff_kg_ci"] is None else list(r["diff_kg_ci"]),
                              "kg_CO2", "simulated", f"{pid}:diff_ci")}


def seasonal_section(*, ledgers: Mapping[str, pl.DataFrame], cj: pl.DataFrame, tt,
                     window: tuple[datetime, datetime], pid: str, label: str = LABEL,
                     policies: tuple[str, ...] = ("S", "W")) -> dict:
    from gridpilot.eval import paired_block_bootstrap, weekly

    weeks = {p: weekly(ledgers[p], cj, tt, window=window) for p in ("U", *policies)}
    season = [_season(w) for w in weeks["U"]["week"].to_list()]
    out = {}
    for s in SEASONS:
        m = pl.Series([x == s for x in season])
        n = int(m.sum())
        u = weeks["U"].filter(m)
        rec = {"n_weeks": E(n, "weeks", "measured", f"{pid}:{s}:n"),
               "weeks": [w.isoformat() for w in u["week"].to_list()], "policies": {}}
        for p in policies:
            b = weeks[p].filter(m)
            ua, pa = math.fsum(u["co2_kg"].to_list()), math.fsum(b["co2_kg"].to_list())
            q = f"{pid}:{s}:{p}"
            pr = {"U_co2_kg": E(ua, "kg_CO2", "simulated", f"{q}:U"),
                  "co2_kg": E(pa, "kg_CO2", "simulated", f"{q}:co2"),
                  "saving": E((ua - pa) / ua if ua else None, "fraction", "simulated",
                              f"{q}:saving", "zero U total")}
            if n >= MIN_SEASON_WEEKS:
                pr["blocks"] = {str(bk): _boot_record(paired_block_bootstrap(u, b, block=bk),
                                                      n, f"{q}:b{bk}") for bk in BLOCKS}
            else:
                pr["blocks"] = not_run(f"{q}:blocks", f"{n} weeks < {MIN_SEASON_WEEKS}: point "
                                                      f"estimate only")
            rec["policies"][p] = pr
        out[s] = rec
    return {"status": "ok", "label": label, "rule": SEASON_RULE,
            "arrivals": [iso(window[0]), iso(window[1])], "seasons": out}


# --------------------------------------------------------------------------- item 6


def _joined(fc: pl.DataFrame, truth: pl.DataFrame) -> pl.DataFrame:
    return fc.join(truth.select("ba", pl.col("ts_utc").alias("target_ts"),
                                pl.col("value").alias("truth")), on=["ba", "target_ts"],
                   how="inner").drop_nulls("truth")


def residual_quantiles(fc: pl.DataFrame, truth: pl.DataFrame) -> tuple[float, float, int]:
    """p10, p90 of truth − forecast over the joined hours (numpy linear percentiles)."""
    j = _joined(fc, truth)
    r = (j["truth"] - j["value"]).to_numpy()
    if r.size == 0:
        return float("nan"), float("nan"), 0
    return float(np.percentile(r, 10)), float(np.percentile(r, 90)), int(r.size)


def _mae(fc: pl.DataFrame, truth: pl.DataFrame) -> tuple[float | None, int]:
    j = _joined(fc, truth)
    if j.height == 0:
        return None, 0
    return float((j["value"] - j["truth"]).abs().mean()), j.height


def _coverage(fc: pl.DataFrame, truth: pl.DataFrame, lo: float,
              hi: float) -> tuple[float | None, int]:
    j = _joined(fc, truth)
    if j.height == 0 or not (math.isfinite(lo) and math.isfinite(hi)):
        return None, j.height
    r = (j["truth"] - j["value"]).to_numpy()
    return float(((r >= lo) & (r <= hi)).mean()), j.height


def permutation_importance(fitted, feats: pl.DataFrame, truth: pl.DataFrame, leaf: int,
                           frozen_l: pl.DataFrame) -> dict:
    """MAE increase per feature group (5 shuffles, seed 20261027), and the check that the
    refitted L reproduces the run's frozen L forecasts."""
    from gridpilot.forecast import FEATURES, NONNEGATIVE, predict

    if set().union(*FEATURE_GROUPS.values()) != set(FEATURES):
        raise AssertionError("the feature groups must partition forecast.FEATURES")
    base, _ = predict(fitted, feats, "L", leaf)
    j = base.join(frozen_l.select("issue_ts", "target_ts", pl.col("value").alias("frozen")),
                  on=["issue_ts", "target_ts"], how="inner")
    max_dev = float((j["value"] - j["frozen"]).abs().max()) if j.height else None
    reproduces = (j.height == base.height == frozen_l.height and max_dev is not None
                  and max_dev <= 1e-9)
    tr = truth.select(pl.col("ts_utc").alias("target_ts"), pl.col("value").alias("truth"))
    keep = feats.join(tr, on="target_ts", how="inner").drop_nulls("truth")
    x = keep.select(FEATURES).to_numpy()
    y = keep["truth"].to_numpy()
    hgb = fitted.hgb[leaf]
    clip = fitted.target in NONNEGATIVE

    def mae(xm):
        p = hgb.predict(xm)
        if clip:
            p = np.maximum(p, 0.0)
        return float(np.abs(p - y).mean())

    m0 = mae(x)
    out = {}
    idx = {f: i for i, f in enumerate(FEATURES)}
    for g, cols in FEATURE_GROUPS.items():
        rng = np.random.default_rng(SEED)
        ci = [idx[c] for c in cols]
        incs = []
        for _ in range(N_SHUFFLES):
            perm = rng.permutation(x.shape[0])
            xs = x.copy()
            xs[:, ci] = x[perm][:, ci]
            incs.append(mae(xs) - m0)
        out[g] = {"mae_increase": float(np.mean(incs)), "mae_increase_runs": incs}
    return {"n_rows": int(x.shape[0]), "mae_unshuffled": m0, "groups": out,
            "reproduces_frozen_forecasts": bool(reproduces), "max_abs_dev": max_dev}


def skill_series(*, key: str, fc: pl.DataFrame, truth: pl.DataFrame, intervals: dict | None,
                 eia_df: pl.DataFrame | None, pi: dict | None, unit: str, pid: str) -> dict:
    """One series: MAE of K, W, L on the scored targets, L and W relative to K, EIA's
    day-ahead demand forecast where it exists, coverage of the frozen intervals, and the
    permutation importance."""
    out: dict = {"models": {}}
    mae = {}
    for m in ("K", "W", "L"):
        f = fc.filter(pl.col("model") == m)
        mae[m], n = _mae(f, truth)
        rec = {"mae": E(mae[m], unit, "measured", f"{pid}:{key}:{m}:mae"),
               "n_hours": E(n, "hours", "measured", f"{pid}:{key}:{m}:n")}
        if m != "K":
            rec["mae_vs_climatology"] = E(mae[m] / mae["K"] if mae[m] and mae["K"] else None,
                                          "ratio", "measured", f"{pid}:{key}:{m}:rel_K")
        if intervals is not None and m in intervals:
            lo, hi = intervals[m]
            cov, _ = _coverage(f, truth, lo, hi)
            rec["interval"] = {"p10": E(lo, unit, "measured", f"{pid}:{key}:{m}:p10"),
                               "p90": E(hi, unit, "measured", f"{pid}:{key}:{m}:p90"),
                               "width": E(hi - lo, unit, "measured", f"{pid}:{key}:{m}:width"),
                               "coverage": E(cov, "fraction", "measured",
                                             f"{pid}:{key}:{m}:coverage", "no scored hours"),
                               "nominal": E(0.8, "fraction", "assumed", f"{pid}:nominal")}
        out["models"][m] = rec
    if eia_df is not None:
        lf = fc.filter(pl.col("model") == "L").select("ba", "target_ts").unique()
        d = eia_df.join(lf, on=["ba", "target_ts"], how="inner")
        m_eia, n_eia = _mae(d, truth)
        m_l, _ = _mae(fc.filter(pl.col("model") == "L").join(
            d.select("ba", "target_ts"), on=["ba", "target_ts"], how="inner"), truth)
        out["eia_day_ahead"] = {
            "note": "EIA-930 demand forecast (DF) on the same target hours; EIA's forecast is "
                    "its own product, not issued at our 10:00 Denver time",
            "mae": E(m_eia, unit, "measured", f"{pid}:{key}:eia:mae", "no common hours"),
            "n_hours": E(n_eia, "hours", "measured", f"{pid}:{key}:eia:n"),
            "L_mae_same_hours": E(m_l, unit, "measured", f"{pid}:{key}:eia:L", "no common hours"),
            "L_vs_eia": E(m_l / m_eia if m_l and m_eia else None, "ratio", "measured",
                          f"{pid}:{key}:eia:ratio", "no common hours")}
    else:
        out["eia_day_ahead"] = not_run(f"{pid}:{key}:eia", "EIA publishes a day-ahead "
                                                           "forecast for demand only")
    if pi is not None:
        out["permutation_importance"] = {
            "rule": PI_RULE,
            "n_rows": E(pi["n_rows"], "rows", "measured", f"{pid}:{key}:pi:n"),
            "mae_unshuffled": E(pi["mae_unshuffled"], unit, "measured", f"{pid}:{key}:pi:m0"),
            "reproduces_frozen_forecasts": pi["reproduces_frozen_forecasts"],
            "groups": {g: {"mae_increase": E(v["mae_increase"], unit, "measured",
                                             f"{pid}:{key}:pi:{g}"),
                           "mae_increase_runs": E(v["mae_increase_runs"], unit, "measured",
                                                  f"{pid}:{key}:pi:{g}:runs")}
                       for g, v in pi["groups"].items()}}
    return out


def forecast_skill(*, fc_dir: Path, fit_at: datetime, history_start: datetime,
                   leaves: dict[str, int], issues: list[datetime],
                   scored: tuple[datetime, datetime], load: Callable[[str], pl.DataFrame],
                   eia_df: pl.DataFrame | None, intervals: dict | None, pid: str,
                   label: str) -> dict:
    """Item 6 on one window. `load(target)` returns the series (validation: the pre-seal
    loader; test: the sealed loader). `issues`: the window's forecast issues (all of the run's);
    `scored`: the target window. `intervals`: {ba: {target: {model: (p10, p90)}}} (frozen), or
    None to derive them here (validation: residuals over the selection issues). Series are
    nested by BA and target, so that '/'-paths address them."""
    from gridpilot.forecast import (
        BA_TZ,
        RUN_SERIES,
        SELECTION_END,
        UNITS,
        _one_ba,
        fit,
        issue_features,
        prepare,
    )

    forecasts = pl.read_parquet(Path(fc_dir) / "forecasts.parquet")
    data = {t: load(t) for t in sorted({t for _, t in RUN_SERIES})}
    series: dict = {}
    derived: dict = {}
    for ba, target in RUN_SERIES:
        key = f"{ba}/{target}"
        s = _one_ba(data[target], ba, history_start)
        truth_all = prepare(s, target).drop_nulls("value")
        truth = truth_all.filter((pl.col("ts_utc") >= scored[0])
                                 & (pl.col("ts_utc") < scored[1]))
        fc = forecasts.filter((pl.col("ba") == ba) & (pl.col("target") == target)
                              & (pl.col("target_ts") >= scored[0])
                              & (pl.col("target_ts") < scored[1]))
        if intervals is None:
            sel = forecasts.filter((pl.col("ba") == ba) & (pl.col("target") == target)
                                   & (pl.col("issue_ts") >= VALIDATION_START)
                                   & (pl.col("issue_ts") < SELECTION_END))
            iv = {m: residual_quantiles(sel.filter(pl.col("model") == m), truth_all)[:2]
                  for m in ("K", "W", "L")}
            derived.setdefault(ba, {})[target] = iv
        else:
            iv = {m: tuple(v) for m, v in intervals.get(ba, {}).get(target, {}).items()} or None
        fitted = fit(data[target], ba, target, fit_at, history_start, leaf_nodes=(leaves[key],))
        feats = issue_features(s, target, issues, BA_TZ[ba]).filter(
            (pl.col("target_ts") >= scored[0]) & (pl.col("target_ts") < scored[1]))
        frozen_l = fc.filter(pl.col("model") == "L").select("issue_ts", "target_ts", "value")
        pi = permutation_importance(fitted, feats, truth, leaves[key], frozen_l)
        rec = skill_series(key=key, fc=fc, truth=truth, intervals=iv,
                           eia_df=eia_df if target == "demand" else None, pi=pi,
                           unit=UNITS[target], pid=pid)
        rec["L_max_leaf_nodes"] = E(leaves[key], "leaves", "assumed", f"{pid}:{key}:leaves")
        series.setdefault(ba, {})[target] = rec
    out = {"status": "ok", "label": label, "rule": INTERVAL_RULE, "pi_rule": PI_RULE,
           "scored_targets": [iso(scored[0]), iso(scored[1])], "series": series,
           "feature_groups": {g: list(c) for g, c in FEATURE_GROUPS.items()}}
    if intervals is None:
        out["frozen_intervals"] = {
            ba: {t: {m: E(list(v), UNITS[t], "measured", f"{pid}:{ba}/{t}:{m}:interval",
                          "no residuals") for m, v in d.items()} for t, d in by.items()}
            for ba, by in derived.items()}
    return out


def eia_day_ahead(balance: pl.DataFrame) -> pl.DataFrame:
    """EIA's day-ahead demand forecast as a forecast frame (ba, target_ts, value)."""
    return balance.select(pl.col("ba").cast(pl.Utf8), pl.col("ts_utc").alias("target_ts"),
                          pl.col(EIA_DF_COL).cast(pl.Float64).alias("value")).drop_nulls("value")


# --------------------------------------------------------------------------- item 7


def _resolve(doc: dict | None, path: str) -> tuple:
    """(value, unit, evidence) at a '/'-separated path (list indices as integers). A path into
    an envelope's value list (…/value/3) keeps the envelope's unit and evidence."""
    if doc is None:
        raise KeyError("missing document")
    node, parent = doc, None
    for p in path.strip("/").split("/"):
        if isinstance(node, dict) and "value" in node and "evidence" in node:
            parent = node
        node = node[int(p)] if isinstance(node, list) else node[p]
    if isinstance(node, dict) and "value" in node and "evidence" in node:
        return node["value"], node.get("unit"), node.get("evidence")
    if parent is not None and (node is None or isinstance(node, (int, float))):
        return node, parent.get("unit"), parent.get("evidence")
    raise KeyError(f"{path} is not an envelope")


def drift_row(item: str, metric: str, v_doc: dict | None, v_path: str, t_doc: dict | None,
              t_path: str, pid: str) -> dict:
    """One row: validation, test and test − validation (scalars of the same unit). A side that
    cannot be read is reported `unavailable` with the reason; no row is ever dropped."""
    row = {"item": item, "metric": metric, "validation_from": v_path, "test_from": t_path}
    vals = {}
    for side, doc, path in (("validation", v_doc, v_path), ("test", t_doc, t_path)):
        try:
            v, unit, ev = _resolve(doc, path)
            row[side] = E(v, unit, ev, f"{pid}:{side}", "null in the source")
            vals[side] = (v, unit, ev)
        except (KeyError, IndexError, TypeError, ValueError) as e:
            row[side] = E(None, "-", "simulated", f"{pid}:{side}",
                          f"not available: {type(e).__name__} {e}"[:200])
    if len(vals) == 2:
        (a, ua, _), (b, ub, eb) = vals["validation"], vals["test"]
        ok = all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (a, b))
        row["difference"] = E(b - a if ok and ua == ub else None, ub or "-", eb or "simulated",
                              f"{pid}:diff", "not a scalar pair of the same unit")
    else:
        row["difference"] = E(None, "-", "simulated", f"{pid}:diff", "a side is unavailable")
    return row


def drift_table(*, val: dict[str, dict | None], test: dict[str, dict | None],
                extension_names: list[str], pid: str = "extras:drift") -> dict:
    """Item 7: validation → test for every headline number and every item. `val`/`test` map
    a source name to its document: metrics (results/metrics.json, results/test/metrics.json),
    extensions, storage, case_days, water, extras (results/extras-validation.json / this
    run's extras sections)."""
    rows = []

    def add(item, metric, vsrc, vpath, tsrc, tpath):
        rows.append(drift_row(item, metric, val.get(vsrc), vpath, test.get(tsrc), tpath,
                              f"{pid}:{len(rows)}"))

    vm, tm = val.get("metrics"), test.get("metrics")

    def contrast_path(doc, cand, ref="U"):
        if doc is None:
            return "contrasts/?"
        i = next((i for i, c in enumerate(doc.get("contrasts", []))
                  if c["candidate"] == cand and c["reference"] == ref), None)
        return f"contrasts/{i if i is not None else '?'}"

    for p in ("U", "G", "S", "K", "W", "L", "H", "W_time", "L_time"):
        add("headline", f"{p} CO₂ (kg)", "metrics", f"policies/{p}/metrics/co2_kg",
            "metrics", f"policies/{p}/metrics/co2_kg")
    for p in ("G", "S", "K", "W", "L", "H", "W_time", "L_time"):
        for k in ("saving", "saving_ci95"):
            add("headline", f"{p} vs U {k} (b = 4)", "metrics",
                f"{contrast_path(vm, p)}/blocks/4/{k}", "metrics",
                f"{contrast_path(tm, p)}/blocks/4/{k}")
    for p in ("K", "W", "L"):
        add("headline", f"{p} vs S saving (b = 4)", "metrics",
            f"{contrast_path(vm, p, 'S')}/blocks/4/saving", "metrics",
            f"{contrast_path(tm, p, 'S')}/blocks/4/saving")
    add("headline", "H2 W − L (kg, b = 4)", "metrics", "h2/intervals/4/diff_kg", "metrics",
        "h2/intervals/4/diff_kg")
    add("headline", "H2 W − L 95% interval (kg, b = 4)", "metrics",
        "h2/intervals/4/diff_kg_ci95", "metrics", "h2/intervals/4/diff_kg_ci95")
    for name in extension_names:
        group = "phases" if name.startswith("phase_") else "sensitivities"
        for p in EXT_POLICIES[1:]:
            add("1 extensions", f"{name}: {p} vs U saving (b = 4)", "extensions",
                f"{group}/{name}/policies/{p}/vs_U/4/saving", "extras",
                f"extensions/{name}/vs_U/{p}/4/saving")
    sizes = ((4.0, 3), (8.0, 4))  # (size, index in the validation size grid 0, 1, 2, 4, 8, …)
    for case in ("U", "mobility_le_8gpus_W"):
        for e, i in sizes:
            for strat in ("A", "B"):
                add("2 storage", f"{case}: {e:g} MWh {strat} cut fraction", "storage",
                    f"cases/{case}/strategies/{strat}/0.85/cut_frac/value/{i}", "extras",
                    f"storage/cases/{case}/{strat}/{e:g}/cut_frac")
            add("2 storage", f"{case}: {e:g} MWh A flat-marginal change (t)", "storage",
                f"cases/{case}/strategies/A/0.85/flat_marginal_cut_t/value/{i}", "extras",
                f"storage/cases/{case}/A/{e:g}/flat_marginal_cut_t")
    for e, i in sizes:
        add("2 storage", f"move small + store, {e:g} MWh A", "storage",
            f"combined/move_and_store_cut_frac/A/value/{i}", "extras",
            f"storage/combined/move_and_store_cut_frac/A/{e:g}")
    add("2 storage", "move only (mobility ≤ 8 GPUs W)", "storage", "combined/move_only_cut_frac",
        "extras", "storage/combined/move_only_cut_frac")
    add("2 storage", "rush hours", "storage", "rush/n_hours", "extras", "storage/rush/n_hours")
    for p in ("S", "W"):
        add("2 storage", f"{p} rush-hour PACE relief (MW)", "storage",
            f"peak_relief/policies/{p}/PACE/rush_change_vs_U_mw", "extras",
            f"storage/peak_relief/{p}/PACE/rush_change_vs_U_mw")
    for sch in ("carbon", "peak"):
        for case in ("U", "mobility_le_8gpus_W"):
            for k in ("cut_frac", "flat_marginal_cut_t", "rush_import_after_mw",
                      "peak_import_after_mw", "rush_hours_discharging"):
                add("2b storage schedules", f"{sch} schedule, {case}, 4 MWh: {k}", "extras",
                    f"storage_peak/schedules/{sch}/cases/{case}/4/{k}", "extras",
                    f"storage/schedule_comparison/schedules/{sch}/cases/{case}/4/{k}")
    for k in range(K_DAYS):
        add("3 toughest days", f"rank {k + 1}: peak net load (MW)", "case_days",
            f"days/{k}/peak/net_load_mw", "extras", f"toughest_days/days/{k}/peak/net_load_mw")
        for p in ("S", "W"):
            add("3 toughest days", f"rank {k + 1}: {p} day CO₂ change vs U", "case_days",
                f"days/{k}/policies/{p}/co2_change_vs_U_frac", "extras",
                f"toughest_days/days/{k}/policies/{p}/co2_change_vs_U_frac")
    for p in ("S", "W", "L"):
        for c in ("ex_hydro_frac", "with_hydro_frac"):
            add("4 water", f"{p} {c} vs U", "water", f"policies/{p}/change_vs_U/{c}", "extras",
                f"water/policies/{p}/change_vs_U/{c}")
    for s in SEASONS:
        for p in ("S", "W"):
            add("5 seasonal", f"{s}: {p} saving vs U", "extras",
                f"seasonal/seasons/{s}/policies/{p}/saving", "extras",
                f"seasonal/seasons/{s}/policies/{p}/saving")
    from gridpilot.forecast import RUN_SERIES

    for ba, t in RUN_SERIES:
        key = f"{ba}/{t}"
        for m in ("K", "W", "L"):
            add("6 forecast skill", f"{key} {m} MAE", "extras",
                f"forecast_skill/series/{key}/models/{m}/mae", "extras",
                f"forecast_skill/series/{key}/models/{m}/mae")
            add("6 forecast skill", f"{key} {m} p10–p90 coverage", "extras",
                f"forecast_skill/series/{key}/models/{m}/interval/coverage", "extras",
                f"forecast_skill/series/{key}/models/{m}/interval/coverage")
        add("6 forecast skill", f"{key} L MAE / K MAE", "extras",
            f"forecast_skill/series/{key}/models/L/mae_vs_climatology", "extras",
            f"forecast_skill/series/{key}/models/L/mae_vs_climatology")
        for g in FEATURE_GROUPS:
            add("6 permutation importance", f"{key} L {g} (MAE increase)", "extras",
                f"forecast_skill/series/{key}/permutation_importance/groups/{g}/mae_increase",
                "extras",
                f"forecast_skill/series/{key}/permutation_importance/groups/{g}/mae_increase")
    add("6 forecast skill", "PACE/demand L vs EIA day-ahead (MAE ratio)", "extras",
        "forecast_skill/series/PACE/demand/eia_day_ahead/L_vs_eia", "extras",
        "forecast_skill/series/PACE/demand/eia_day_ahead/L_vs_eia")
    return {"rule": "every headline number and every D-071 item: validation, test, and test − "
                    "validation (same unit); a side that cannot be read is listed as unavailable "
                    "with the reason; no row is dropped",
            "n_rows": E(len(rows), "rows", "measured", f"{pid}:n"), "rows": rows}


__all__ = ["LABEL", "LABEL_VALIDATION", "drift_table", "extension_section", "forecast_skill",
           "peak_schedule", "schedule_comparison", "seasonal_section", "storage_section",
           "toughest_days_section", "water_section"]
