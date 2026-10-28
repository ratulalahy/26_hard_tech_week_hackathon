"""Price lens (Stage 3 T22): what moving and waiting cost or save in dollars, as a **wholesale
scenario**, on the registered validation run.

**Wholesale scenario, not a bill.** Every dollar here is the cluster's simulated hourly energy
priced at each site's CAISO/WEIM *real-time* wholesale LMP. A data center does not pay that: it
pays a retail tariff or a contract, with demand charges, transmission and fees. The numbers say
which way and roughly how far the wholesale signal points, nothing more.

**Validation only.** The cohort window lies before the seal (2025-11-01T00Z). Only raw price files
whose manifest window starts before the seal are opened, each file's sha256 is checked against
`data/manifests/prices_caiso.json`, and every parsed frame goes through `drop_sealed` first.

**Prices (observed).** CAISO OASIS `PRC_RTPD_LMP` (15-minute fifteen-minute-market LMP, real time
for every site, including the WEIM load points), averaged to UTC hours. Real-time marks are used
everywhere because PACE has no day-ahead price before EDAM (2026-05-01, inside the sealed window).
Site → node (assumed): PACE `ELAP_PACE-APND`, BPAT `ELAP_BPAT-APND`, NEVP `ELAP_NEVP-APND` (the
WEIM load aggregation points) and CISO `DLAP_PGAE-APND` (PG&E's default load aggregation point;
`DLAP_SCE-APND` is the one sensitivity).

**Coverage rule (registered here, policy-independent).** An hour is *priced at a site* when all
four of its 15-minute intervals have an LMP. An hour is *priced* when it is priced at every site.
Unpriced hours are excluded for every policy: their energy, cost and CO₂ count zero in every
total below, and each policy's excluded energy share is reported.

**Cost (simulated).** Exactly the CO₂ accounting of `gridpilot.eval.accounting.job_accounting`
with $/MWh in place of g/kWh: execution energy is an exact-overlap integral of the site's hourly
price, and remote-run transfer energy is priced half at home and half at the destination at the
arrival hour. kWh × $/MWh / 1000 = $.

**Cost per attributed tonne (simulated).** (cost_P − cost_U) / (attributed CO₂_U − CO₂_P), both on
the priced hours. Negative = the policy is both cheaper and lower-carbon. Null when the policy does
not lower attributed CO₂. It is a wholesale-scenario ratio on attributed (average-intensity)
emissions, not a marginal abatement cost.

**Level vs timing (exact, additive).** With p̄_s the plain mean price of site s over the priced
hours: level_P = Σ_s MWh_Ps · p̄_s and timing_P = cost_P − level_P (when, within the year, the
energy is drawn relative to that site's mean). Δ vs U splits again: Δlevel = extra energy
(ΔMWh · p̄_PACE, the transfer overhead) + location (Σ_s MWh_Ps · (p̄_s − p̄_PACE); U runs only at
PACE). So Δcost = extra energy + location + timing.

**Interval.** The frozen paired block bootstrap (`gridpilot.eval.bootstrap`, b = 2, 4, 8 weeks,
2,000 reps, seed 20261027) over weekly cost totals by arrival week, as for CO₂.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import polars as pl

from gridpilot.data.prices import read_oasis_zip
from gridpilot.eval.accounting import TruthTable, fsum_by, job_accounting, weekly
from gridpilot.eval.bootstrap import (
    BLOCKS,
    BOOTSTRAP_LABEL,
    PRIMARY_BLOCK,
    REPS,
    SEED,
    block_indices,
    paired_block_bootstrap,
)
from gridpilot.paths import DATA_DIR
from gridpilot.results import SCHEMA_VERSION, env, iso
from gridpilot.sim import HOME, SITES
from gridpilot.splits import TEST_START, drop_sealed
from gridpilot.storage import cohort_window, hour_grid

SCENARIO = "wholesale scenario"
CAVEAT = ("Wholesale scenario: simulated energy priced at CAISO/WEIM real-time wholesale LMPs. "
          "A data center pays a retail tariff or contract (demand charges, transmission, fees), "
          "not these prices.")
NODES = {"PACE": "ELAP_PACE-APND", "CISO": "DLAP_PGAE-APND", "BPAT": "ELAP_BPAT-APND",
         "NEVP": "ELAP_NEVP-APND"}
CISO_SENS_NODE = "DLAP_SCE-APND"
INTERVALS_PER_HOUR = 4
POLICIES = ("U", "S", "W", "L", "W_time")
EXT_NAME = "mobility_le_8gpus"
EXT_POLICY = "W"
MANIFEST = "manifests/prices_caiso.json"
PRICE_FILE_PREFIX = "raw/prices/caiso/rtpd/"
LOCAL_TZ = "America/Denver"
POLICY_LABELS = {
    "U": "Every job in Utah, run on arrival",
    "S": "Static ranking: move to the cleanest-on-average site",
    "W": "Wait and move (forecast-driven)",
    "L": "Wait and move (learned forecast)",
    "W_time": "Wait only, stay in Utah",
    f"{EXT_NAME}:W": "Wait and move, only jobs of 8 GPUs or fewer may move",
}


def _utc(s: str) -> datetime:
    return datetime.fromisoformat(s).astimezone(UTC)


# --------------------------------------------------------------------------- prices


def price_files(window: tuple[datetime, datetime], data_dir: Path = DATA_DIR) -> list[dict]:
    """The RTPD manifest entries that overlap `window` and start before the seal."""
    man = json.loads((data_dir / MANIFEST).read_text())
    out = []
    for f in man["files"]:
        if not f["path"].startswith(PRICE_FILE_PREFIX) or f.get("status") != "ok":
            continue
        s, e = _utc(f["start_utc"]), _utc(f["end_utc"])
        if s < TEST_START and s < window[1] and e > window[0]:
            out.append(f)
    return sorted(out, key=lambda f: f["path"])


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_rt_intervals(nodes: list[str], window: tuple[datetime, datetime],
                      data_dir: Path = DATA_DIR) -> tuple[pl.DataFrame, list[dict]]:
    """15-minute RTPD LMPs (ts_utc, node, lmp) in `window`, before the seal. Each file's
    sha256 is checked against the manifest; each parsed frame goes through drop_sealed."""
    if window[1] > TEST_START:
        raise ValueError(f"price window {window} reaches the seal at {TEST_START} (F8)")
    files, frames = price_files(window, data_dir), []
    for f in files:
        path = data_dir / f["path"]
        got = _sha256(path)
        if got != f["sha256"]:
            raise ValueError(f"{f['path']}: sha256 {got} != manifest {f['sha256']}")
        raw = read_oasis_zip(path)
        if raw is None:
            continue
        df = drop_sealed(raw.select(
            pl.col("INTERVALSTARTTIME_GMT").str.to_datetime(
                "%Y-%m-%dT%H:%M:%S%:z", time_zone="UTC").dt.cast_time_unit("us").alias("ts_utc"),
            pl.col("NODE").alias("node"), pl.col("LMP_TYPE").alias("lmp_type"),
            pl.col("PRC").cast(pl.Float64).alias("lmp")))
        frames.append(df.filter((pl.col("lmp_type") == "LMP") & pl.col("node").is_in(nodes)
                                & (pl.col("ts_utc") >= window[0])
                                & (pl.col("ts_utc") < window[1])).drop("lmp_type"))
    if not frames:
        raise ValueError("no price rows in the window")
    df = pl.concat(frames).unique(["ts_utc", "node"], keep="first").sort("node", "ts_utc")
    return df, [{"path": f["path"], "sha256": f["sha256"]} for f in files]


def hourly_prices(intervals: pl.DataFrame) -> pl.DataFrame:
    """ts_utc (hour start), node, lmp (mean of the hour's intervals), n_intervals."""
    return (intervals.filter(pl.col("lmp").is_finite())
            .with_columns(pl.col("ts_utc").dt.truncate("1h"))
            .group_by("ts_utc", "node")
            .agg(pl.col("lmp").mean(), pl.len().alias("n_intervals"))
            .sort("node", "ts_utc"))


def coverage(grid: pl.DataFrame, hourly: pl.DataFrame, nodes: dict[str, str]) -> dict:
    """Apply the coverage rule on the hour grid. Returns `price` (site → hourly $/MWh, 0 where
    unpriced), `covered` (bool per hour, priced at every site) and the per-site counts."""
    n = grid.height
    price, ok, counts = {}, np.ones(n, dtype=bool), {}
    for site, node in nodes.items():
        h = hourly.filter(pl.col("node") == node)
        j = grid.select("ts_utc").join(h, on="ts_utc", how="left")
        k = j["n_intervals"].fill_null(0).to_numpy()
        v = j["lmp"].fill_null(0.0).to_numpy().astype(float)
        full = k == INTERVALS_PER_HOUR
        counts[site] = {"node": node, "complete": int(full.sum()),
                        "partial": int(((k > 0) & ~full).sum()), "missing": int((k == 0).sum())}
        price[site] = v
        ok &= full
    price = {site: np.where(ok, v, 0.0) for site, v in price.items()}
    return {"price": price, "covered": ok, "sites": counts}


def site_table(grid: pl.DataFrame, values: dict[str, np.ndarray]) -> TruthTable:
    """A TruthTable whose 'intensity' is `values[site]` per hour (every hour finite)."""
    ts = grid["ts_utc"]
    frames = [pl.DataFrame({"ba": [s] * grid.height, "ts_utc": ts,
                            "ci_g_kwh": np.asarray(v, dtype=float)})
              for s, v in values.items()]
    return TruthTable(pl.concat(frames))


# --------------------------------------------------------------------------- per policy


def policy_totals(ledger: pl.DataFrame, jobs: pl.DataFrame, tables: dict[str, TruthTable],
                  home: str = HOME) -> dict:
    """Totals of one ledger on the price ('usd'), level ('level'), priced-indicator ('mwh'),
    full-energy ('mwh_all') and priced-CO₂ ('co2') tables. Each table's 'co2_kg' column is
    Σ kWh × value / 1000: $ for $/MWh, MWh for 1, kg for g/kWh."""
    out, per_site = {}, {}
    for k, tt in tables.items():
        a = job_accounting(ledger, jobs, tt, home=home)
        out[k] = fsum_by(a, "co2_kg")
        out[f"{k}_transfer"] = fsum_by(a, "transfer_co2_kg")
        per_site[k] = {s: fsum_by(a.filter(pl.col("site") == s), "execution_co2_kg")
                       for s in SITES}
    out["site"] = per_site
    return out


def decompose(p: dict, u: dict, mean_price: dict[str, float], home: str = HOME) -> dict:
    """Δcost vs U = extra energy + location + timing (exact; see the module docstring). The
    level total prices every priced kWh (execution and transfer) at its site's mean price."""
    lv_p, lv_u = p["level"], u["level"]
    d_cost = p["usd"] - u["usd"]
    d_level = lv_p - lv_u
    extra = (p["mwh"] - u["mwh"]) * mean_price[home]
    return {"delta_usd": d_cost, "level_usd": d_level, "timing_usd": d_cost - d_level,
            "extra_energy_usd": extra, "location_usd": d_level - extra,
            "level_total_usd": lv_p, "timing_total_usd": p["usd"] - lv_p}


def ratio_interval(u_w: np.ndarray, p_w: np.ndarray, u_c: np.ndarray, p_c: np.ndarray,
                   block: int) -> tuple[list[float] | None, str | None]:
    """Bootstrap interval of (Σ p_$ − Σ u_$) / (Σ u_t − Σ p_t) with the frozen indices; null when
    any replicate has no attributed CO₂ reduction (the ratio is then undefined)."""
    idx = block_indices(u_w.size, block, REPS, SEED)
    dc = p_w[idx].sum(axis=1) - u_w[idx].sum(axis=1)
    dt = (u_c[idx].sum(axis=1) - p_c[idx].sum(axis=1)) / 1000
    if (dt <= 0).any():
        return None, "a replicate has no attributed CO₂ reduction (ratio undefined)"
    lo, hi = np.quantile(dc / dt, [0.025, 0.975], method="linear")
    return [float(lo), float(hi)], None


# --------------------------------------------------------------------------- build


def _jobs(u: pl.DataFrame) -> pl.DataFrame:
    return u.select("job_uid", pl.col("job_uid").str.split("#").list.first().alias("source_id"),
                    "arrival_ts", "gpus", "duration_s")


def _ledgers(run_dir: Path, ext_dir: Path | None) -> dict[str, pl.DataFrame]:
    led = {p: pl.read_parquet(run_dir / f"ledger_{p}.parquet") for p in POLICIES}
    if ext_dir is not None:
        led[f"{EXT_NAME}:{EXT_POLICY}"] = pl.read_parquet(ext_dir / f"ledger_{EXT_POLICY}.parquet")
        ext_u = pl.read_parquet(ext_dir / "ledger_U.parquet")
        cols = ["job_uid", "site", "start_ts", "end_ts"]
        if not ext_u.select(cols).sort("job_uid").equals(led["U"].select(cols).sort("job_uid")):
            raise ValueError(f"{ext_dir}: its U ledger differs from the registered U")
    return led


def compute(run_dir: Path, ext_dir: Path | None = None, *, data_dir: Path = DATA_DIR,
            nodes: dict[str, str] | None = None, with_bootstrap: bool = True) -> dict:
    """Everything the artifact needs, for one site → node mapping."""
    nodes = dict(nodes or NODES)
    cfg = json.loads((run_dir / "config.json").read_text())
    if cfg.get("window") != "validation":
        raise ValueError(f"{run_dir} is not a validation run")
    t0, t_a = _utc(cfg["eval_start"]), _utc(cfg["A"])
    led = _ledgers(run_dir, ext_dir)
    win = cohort_window(t0, max(x["end_ts"].max() for x in led.values()))
    grid = hour_grid(*win)
    iv, files = load_rt_intervals(sorted(set(nodes.values())), win, data_dir)
    cov = coverage(grid, hourly_prices(iv), nodes)
    ok = cov["covered"]
    if not ok.any():
        raise ValueError("no hour is priced at every site")
    mean_price = {s: math.fsum(cov["price"][s][ok].tolist()) / int(ok.sum()) for s in SITES}
    truth = drop_sealed(pl.read_parquet(run_dir / "truth_fill.parquet"))
    ci = {}
    for s in SITES:
        j = grid.select("ts_utc").join(truth.filter(pl.col("ba") == s).select("ts_utc", "ci_g_kwh"),
                                       on="ts_utc", how="left")["ci_g_kwh"].to_numpy()
        j = np.asarray(j, dtype=float)
        if not np.isfinite(j).all():
            raise ValueError(f"{s}: {int((~np.isfinite(j)).sum())} window hours have no filled truth")
        ci[s] = j
    one = np.ones(grid.height)
    tables = {
        "usd": site_table(grid, cov["price"]),
        "level": site_table(grid, {s: np.where(ok, mean_price[s], 0.0) for s in SITES}),
        "mwh": site_table(grid, {s: ok.astype(float) for s in SITES}),
        "mwh_all": site_table(grid, {s: one for s in SITES}),
        "co2": site_table(grid, {s: np.where(ok, ci[s], 0.0) for s in SITES}),
        "co2_all": site_table(grid, ci),
    }
    jobs = _jobs(led["U"])
    tot = {p: policy_totals(lg, jobs, tables) for p, lg in led.items()}
    hour = grid["hour"].to_numpy()
    profile = {s: [float(np.mean(cov["price"][s][ok & (hour == h)]))
                   if (ok & (hour == h)).any() else None for h in range(24)] for s in SITES}
    out = {"run_id": run_dir.name, "ext_run_id": ext_dir.name if ext_dir else None,
           "window": win, "arrivals": (t0, t_a), "grid_hours": grid.height,
           "coverage": cov, "mean_price": mean_price, "totals": tot, "nodes": nodes,
           "files": files, "profile": profile, "decomp": {}, "boot": {}}
    for p, t in tot.items():
        out["decomp"][p] = decompose(t, tot["U"], mean_price)
    if with_bootstrap:
        warr = (t0, t_a)
        wk = {p: {k: weekly(lg, jobs, tables[k], window=warr)["co2_kg"].to_numpy()
                  for k in ("usd", "co2")} for p, lg in led.items()}
        for p in tot:
            if p == "U":
                continue
            res = {}
            for b in BLOCKS:
                r = paired_block_bootstrap(wk["U"]["usd"], wk[p]["usd"], b, REPS, SEED)
                ri, why = ratio_interval(wk["U"]["usd"], wk[p]["usd"], wk["U"]["co2"],
                                         wk[p]["co2"], b)
                res[b] = {"n_weeks": r["n_weeks"], "degenerate": r["degenerate"],
                          "saving_usd": r["diff_kg"], "saving_usd_ci": r["diff_kg_ci"],
                          "saving_frac": r["saving"], "saving_frac_ci": r["saving_ci"],
                          "usd_per_t_ci": ri, "usd_per_t_ci_reason": why}
            out["boot"][p] = res
    return out


# --------------------------------------------------------------------------- artifact


def _ok(v, unit, ev, pid, reason=None):
    return env(v, unit, ev, pid, reason=reason if v is None else None)


def build_artifact(main: dict, sens: dict | None = None) -> dict:
    pid = "prices"
    tot, dec, cov = main["totals"], main["decomp"], main["coverage"]
    ok = cov["covered"]
    u = tot["U"]
    pols = {}
    for p, t in tot.items():
        d = dec[p]
        d_t = (u["co2"] - t["co2"]) / 1000
        per_t = None if p == "U" or d_t <= 0 else d["delta_usd"] / d_t
        per_t_reason = ("the reference" if p == "U" else
                        "no attributed CO₂ reduction vs U on the priced hours")
        q = f"{pid}:{p}"
        rec = {
            "label": POLICY_LABELS[p], "scenario": SCENARIO,
            "source": (f"{main['ext_run_id']}/ledger_{EXT_POLICY}" if ":" in p
                       else f"{main['run_id']}/ledger_{p}"),
            "cost_usd": env(t["usd"], "USD", "simulated", f"{q}:cost"),
            "energy_priced_mwh": env(t["mwh"], "MWh", "modeled", f"{q}:mwh"),
            "energy_all_mwh": env(t["mwh_all"], "MWh", "modeled", f"{q}:mwh_all"),
            "excluded_energy_share": env(1 - t["mwh"] / t["mwh_all"], "fraction", "modeled",
                                         f"{q}:excluded_share"),
            "avg_price_paid_usd_mwh": env(t["usd"] / t["mwh"], "USD/MWh", "simulated",
                                          f"{q}:avg_price"),
            "co2_priced_t": env(t["co2"] / 1000, "t_CO2", "simulated", f"{q}:co2"),
            "co2_all_t": env(t["co2_all"] / 1000, "t_CO2", "simulated", f"{q}:co2_all"),
            "cost_by_site_usd": {s: env(v, "USD", "simulated", f"{q}:site:{s}")
                                 for s, v in t["site"]["usd"].items()},
            "energy_by_site_mwh": {s: env(v, "MWh", "modeled", f"{q}:site_mwh:{s}")
                                   for s, v in t["site"]["mwh"].items()},
            "transfer_cost_usd": env(t["usd_transfer"], "USD", "simulated", f"{q}:transfer"),
            "delta_vs_U_usd": env(d["delta_usd"], "USD", "simulated", f"{q}:delta"),
            "delta_vs_U_frac": env(d["delta_usd"] / u["usd"], "fraction", "simulated",
                                   f"{q}:delta_frac"),
            "attributed_co2_cut_vs_U_t": env(d_t, "t_CO2", "simulated", f"{q}:co2_cut"),
            "cost_per_attributed_tonne_usd_t": _ok(per_t, "USD/t_CO2", "simulated",
                                                   f"{q}:per_t", per_t_reason),
            "decomposition_vs_U_usd": {
                k: env(d[k], "USD", "simulated", f"{q}:dec:{k}")
                for k in ("level_usd", "timing_usd", "extra_energy_usd", "location_usd")},
        }
        if p in main["boot"]:
            rec["interval"] = {
                "method": BOOTSTRAP_LABEL, "statistic": "U − policy, $ (positive = policy is "
                "cheaper than U); weekly totals by arrival week",
                "primary_block": env(PRIMARY_BLOCK, "weeks", "assumed", f"{q}:primary_block"),
                "reps": env(REPS, "replicates", "assumed", f"{q}:reps"),
                "seed": env(SEED, "seed", "assumed", f"{q}:seed"),
                "blocks": {str(b): {
                    "n_weeks": env(r["n_weeks"], "weeks", "observed", f"{q}:b{b}:n"),
                    "degenerate": r["degenerate"],
                    "saving_usd": env(r["saving_usd"], "USD", "simulated", f"{q}:b{b}:saving"),
                    "saving_usd_ci95": env(r["saving_usd_ci"], "USD", "simulated",
                                           f"{q}:b{b}:saving_ci"),
                    "saving_frac_ci95": _ok(r["saving_frac_ci"], "fraction", "simulated",
                                            f"{q}:b{b}:frac_ci", "a zero reference replicate"),
                    "cost_per_attributed_tonne_ci95": _ok(
                        r["usd_per_t_ci"], "USD/t_CO2", "simulated", f"{q}:b{b}:per_t_ci",
                        r["usd_per_t_ci_reason"]),
                } for b, r in main["boot"][p].items()},
            }
        pols[p] = rec
    n_cov = int(ok.sum())
    out = {
        "schema_version": SCHEMA_VERSION,
        "kind": "illustrative",
        "scenario": SCENARIO,
        "caveat": CAVEAT,
        "note": ("not part of the registered experiment; validation window only; wholesale "
                 "real-time prices applied to registered ledgers after the fact (the router "
                 "never saw a price)"),
        "title": "What moving and waiting cost, at wholesale real-time prices",
        "registered_run_id": main["run_id"],
        "extension_run_id": main["ext_run_id"],
        "window": {"start": iso(main["window"][0]), "end": iso(main["window"][1]),
                   "arrivals": [iso(main["arrivals"][0]), iso(main["arrivals"][1])],
                   "rule": "the registered cohort window: eval_start to the last hour any "
                           "priced cohort ledger still runs"},
        "prices": {
            "source": "CAISO OASIS PRC_RTPD_LMP (15-minute market, real time), hourly mean",
            "manifest": MANIFEST,
            "files": main["files"],
            "why_real_time": "PACE has no day-ahead price before EDAM (May 2026, inside the "
                             "sealed window); real-time marks are used for every site",
            "nodes": {"evidence": "assumed", "map": dict(main["nodes"]),
                      "rule": "the load aggregation point a load at each site would settle at: "
                              "WEIM ELAPs, and PG&E's DLAP for CISO (SCE's is the sensitivity)"},
            "mean_usd_mwh": {s: env(v, "USD/MWh", "observed", f"{pid}:mean:{s}")
                             for s, v in main["mean_price"].items()},
            "by_local_hour_usd_mwh": {
                "tz": LOCAL_TZ,
                **{s: env(v, "USD/MWh", "observed", f"{pid}:profile:{s}",
                          reason=None if all(x is not None for x in v) else "no priced hours")
                   for s, v in main["profile"].items()}},
        },
        "coverage": {
            "rule": "an hour is priced at a site when all four 15-minute LMPs exist; an hour "
                    "counts only when it is priced at every site; unpriced hours are excluded "
                    "for every policy (energy, cost and CO₂ count zero there)",
            "window_hours": env(main["grid_hours"], "hours", "observed", f"{pid}:cov:n"),
            "priced_hours": env(n_cov, "hours", "observed", f"{pid}:cov:priced"),
            "priced_share": env(n_cov / main["grid_hours"], "fraction", "observed",
                                f"{pid}:cov:share"),
            "by_site": {s: {"node": c["node"],
                            **{k: env(c[k], "hours", "observed", f"{pid}:cov:{s}:{k}")
                               for k in ("complete", "partial", "missing")}}
                        for s, c in cov["sites"].items()},
        },
        "decomposition_rule": ("Δcost vs U = level + timing; level = Σ_site MWh × the site's mean "
                               "price over the priced hours, minus U's; level = extra energy "
                               "(ΔMWh × PACE mean price: transfer overhead) + location (MWh "
                               "placed at a site whose mean price differs from PACE's); timing "
                               "= the rest (when the energy is drawn vs each site's mean)"),
        "per_tonne_rule": ("cost per attributed tonne = (cost − cost_U) / (attributed CO₂_U − "
                           "CO₂) on the priced hours; negative = cheaper and lower-carbon; "
                           "attributed (average-intensity) CO₂, not a marginal abatement cost"),
        "policies": pols,
    }
    if sens is not None:
        out["sensitivity"] = {
            "ciso_node": {
                "rule": f"CISO priced at {CISO_SENS_NODE} instead of {NODES['CISO']}; the "
                        "coverage rule re-applied to that node set",
                "priced_hours": env(int(sens["coverage"]["covered"].sum()), "hours", "observed",
                                    f"{pid}:sens:priced"),
                "delta_vs_U_usd": {p: env(d["delta_usd"], "USD", "simulated",
                                          f"{pid}:sens:{p}:delta")
                                   for p, d in sens["decomp"].items()},
                "delta_vs_U_frac": {p: env(d["delta_usd"] / sens["totals"]["U"]["usd"],
                                           "fraction", "simulated", f"{pid}:sens:{p}:frac")
                                    for p, d in sens["decomp"].items()},
            }}
    return out
