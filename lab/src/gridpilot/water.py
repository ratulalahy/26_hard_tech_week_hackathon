"""Water footprint illustration (Stage 3 T14, owner D-063/D-064, with the Astra review's water
caveats). **Illustrative and modeled.** Not part of the registered experiment; validation year
only; every grid read goes through the pre-seal loader (`drop_sealed` on the scan).

**Generation-associated water intensity, per BA-hour** (gal/MWh, `modeled`): the EIA-930 adjusted
generation by fuel (observed), negatives clipped to zero, weighted by NREL/TP-6A20-50900 median
operational *consumption* factors (`gridpilot.data.water_factors`; fuel → technology `assumed`):

    ex_hydro = Σ_{fuel ≠ hydro} gen_f · w_f / Σ gen_f        hydro = gen_hydro · w_hydro / Σ gen_f

over the fuels that enter the shares ("other" and "unknown" are left out, so they take the hour's
average). Hydro evaporation is reported separately and added for the "with hydro" view, because
allocating reservoir evaporation to power is uncertain and can dominate.

**Missing hours.** A BA-hour is missing when nothing is reported, the shares' generation is zero,
or a fuel the BA reports in at least 90% of the loaded hours is null (a fuel it reports less often
counts as 0 when null). Missing or absent hours are filled by linear interpolation in time of
each intensity within the BA (ends carried flat) and marked tier 2; the share of policy energy on
filled hours is reported.

**Policy water** (`simulated`): the registered ledgers (U, S, W, L) priced on these intensities by
`gridpilot.eval.accounting.job_accounting`, the same exact-overlap hourly energy as the carbon
accounting (execution at the site; transfer energy half at home and half at the destination, at
the arrival hour). With intensity in gal/MWh, its "co2_kg" column is gallons. The split by site
puts each transfer half where it is charged. A carbon re-run of the same call must reproduce the
registered metrics, which pins the energy.

**Direct cooling** (`simulated`, shown separately): IT kWh (facility kWh ÷ PUE 1.20) × the LBNL
site WUE range 0.36–0.48 L/kWh, in gallons. One national range for every site and policy, so it
moves only with the transfer energy.

Float totals use `math.fsum` in job_uid order (`fsum_by`).
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl

from gridpilot.data import water_factors as wf
from gridpilot.data.truth_fill import BALANCE_PATH
from gridpilot.results import SCHEMA_VERSION, env, iso
from gridpilot.sim import HOME, SITES
from gridpilot.sim.power import PUE
from gridpilot.splits import TEST_START, drop_sealed

POLICIES = ("U", "S", "W", "L")
# the fuels that partition generation, with hydro split into conventional and pumped storage
FUEL_COLS = ("coal", "gas", "oil", "nuclear", "hydro_conv", "pumped_storage", "solar", "wind",
             "geothermal", "battery", "other_storage", "unknown_storage", "other", "unknown")
REPORTED_SHARE = 0.90
MARGIN = timedelta(days=7)  # loaded before the window so the fill has neighbours
CAVEATS = (
    "Consumption, not withdrawal.",
    "Production-side fuel-mix weighting, not consumption-flow tracing.",
    "Technology medians; plant-level cooling not modelled.",
    "PACE is not the Great Salt Lake watershed; no claim of water returned to the lake.",
    "Hydro evaporation allocation is uncertain; shown separately.",
)
NOTE = ("illustrative; not part of the registered experiment; validation-year data; water "
        "factors are literature medians, not measurements of any plant or site")
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
H_US = 3600 * 1_000_000


# --------------------------------------------------------------------------- inputs (pre-seal)


def load_balance(start: datetime, end: datetime, bas=tuple(SITES)) -> pl.DataFrame:
    """EIA-930 adjusted generation by fuel for `bas` over [start, end), through the seal."""
    if end > TEST_START:
        raise ValueError(f"window end {end} reaches the seal at {TEST_START.isoformat()} (F8)")
    hydro_conv = pl.coalesce(pl.col("gen_hydro_conv_adj_mw"), pl.col("gen_hydro_adj_mw"))
    cols = [pl.col(f"gen_{f}_adj_mw").cast(pl.Float64)
            for f in FUEL_COLS if f != "hydro_conv"]
    return (drop_sealed(pl.scan_parquet(BALANCE_PATH))
            .filter((pl.col("ts_utc") >= start) & (pl.col("ts_utc") < end)
                    & pl.col("ba").cast(pl.Utf8).is_in(list(bas)))
            .select(pl.col("ba").cast(pl.Utf8), "ts_utc", *cols,
                    hydro_conv.cast(pl.Float64).alias("gen_hydro_conv_adj_mw"))
            .collect().sort("ba", "ts_utc"))


# --------------------------------------------------------------------------- intensity


def intensity(balance: pl.DataFrame) -> pl.DataFrame:
    """ba, ts_utc, gen_mw (the shares' generation), ex_hydro, hydro (gal/MWh), missing."""
    if balance.height and balance["ts_utc"].max() >= TEST_START:
        raise ValueError("the balance frame holds a row at or after the seal (F8)")
    w = wf.fuel_factors_gal_mwh()
    share_fuels = [f for f in FUEL_COLS if f in w]
    col = {f: f"gen_{f}_adj_mw" for f in FUEL_COLS}
    reported = (balance.group_by("ba").agg(
        [(pl.col(col[f]).is_not_null().mean() >= REPORTED_SHARE).alias(f) for f in FUEL_COLS]))
    b = balance.join(reported.rename({f: f"_req_{f}" for f in FUEL_COLS}), on="ba", how="left")
    any_req_null = pl.any_horizontal([pl.col(f"_req_{f}") & pl.col(col[f]).is_null()
                                      for f in FUEL_COLS])
    all_null = pl.all_horizontal([pl.col(col[f]).is_null() for f in FUEL_COLS])
    g = {f: pl.col(col[f]).fill_null(0.0).clip(lower_bound=0.0) for f in FUEL_COLS}
    den = pl.sum_horizontal([g[f] for f in share_fuels])
    ex = pl.sum_horizontal([g[f] * w[f] for f in share_fuels if f != "hydro_conv"])
    missing = any_req_null | all_null | (den <= 0)
    return b.select(
        "ba", "ts_utc", den.alias("gen_mw"),
        pl.when(missing).then(None).otherwise(ex / den).alias("ex_hydro"),
        pl.when(missing).then(None).otherwise(g["hydro_conv"] * w["hydro_conv"] / den)
        .alias("hydro"),
        missing.alias("missing"),
    ).sort("ba", "ts_utc")


def fill(fr: pl.DataFrame, start: datetime | None = None, end: datetime | None = None
         ) -> pl.DataFrame:
    """Each BA on the full hourly grid [start, end) (default: its first to last row); missing or
    absent hours get the linear interpolation in time of each intensity (ends carried flat) and
    tier 2. Columns: ba, ts_utc, ex_hydro, hydro, tier."""
    out = []
    for (ba,), g in fr.group_by("ba", maintain_order=True):
        s = start or g["ts_utc"].min()
        e = end or g["ts_utc"].max() + timedelta(hours=1)
        grid = pl.DataFrame({"ts_utc": pl.datetime_range(s, e, "1h", closed="left",
                                                         time_unit="us", time_zone="UTC",
                                                         eager=True)})
        j = grid.join(g.select("ts_utc", "ex_hydro", "hydro"), on="ts_utc", how="left")
        tier = pl.when(pl.col("ex_hydro").is_null()).then(2).otherwise(1).cast(pl.Int64)
        j = j.with_columns(tier.alias("tier"))
        j = j.with_columns([pl.col(c).interpolate().forward_fill().backward_fill()
                            for c in ("ex_hydro", "hydro")])
        out.append(j.select(pl.lit(ba).alias("ba"), "ts_utc", "ex_hydro", "hydro", "tier"))
    return pl.concat(out).sort("ba", "ts_utc")


def truth_tables(filled: pl.DataFrame) -> dict:
    """{"ex_hydro", "hydro"}: accounting TruthTables of the filled intensities (gal/MWh)."""
    from gridpilot.eval.accounting import TruthTable

    return {k: TruthTable(filled.select("ba", "ts_utc", pl.col(k).alias("ci_g_kwh"), "tier"))
            for k in ("ex_hydro", "hydro")}


# --------------------------------------------------------------------------- accounting


def _fsum(x) -> float:
    return math.fsum(np.asarray(x, dtype=float).tolist())


def policy_water(ledger: pl.DataFrame, jobs: pl.DataFrame, tts: dict) -> dict:
    """Gallons for one ledger under each intensity variant: total and by site (execution at the
    site; each transfer half where it is charged), plus energy, IT energy and the kWh on filled
    hours."""
    from gridpilot.eval.accounting import _us_np, fsum_by, job_accounting

    out: dict = {}
    for k, tt in tts.items():
        acc = job_accounting(ledger, jobs, tt).sort("job_uid")
        site = acc["site"].to_numpy().astype(str)
        rem = acc["remote"].to_numpy()
        half = 0.5 * acc["transfer_kwh"].to_numpy()
        arr = _us_np(acc["arrival_ts"])
        by = {s: _fsum(acc["execution_co2_kg"].to_numpy()[site == s]) for s in SITES}
        if rem.any():
            ci_home, _ = tt.point(HOME, arr[rem])
            by[HOME] = math.fsum([by[HOME], _fsum(half[rem] * ci_home / 1000)])
            for s in SITES:
                m = rem & (site == s)
                if m.any():
                    ci_d, _ = tt.point(s, arr[m])
                    by[s] = math.fsum([by[s], _fsum(half[m] * ci_d / 1000)])
        total = fsum_by(acc, "co2_kg")
        if not math.isclose(math.fsum(by.values()), total, rel_tol=1e-9, abs_tol=1e-6):
            raise AssertionError(f"{k}: the site split {math.fsum(by.values())} != total {total}")
        out[k] = {"total": total, "by_site": by}
        out["energy_kwh"] = fsum_by(acc, "energy_kwh")
        out["it_kwh"] = math.fsum([fsum_by(acc, "execution_kwh") / PUE,
                                   fsum_by(acc, "transfer_it_kwh")])
        out["kwh_filled"] = fsum_by(acc, "kwh_tier_ge2")
    return out


def direct_cooling_gal(it_kwh: float, wue_l_per_kwh: float) -> float:
    return it_kwh * wue_l_per_kwh / wf.L_PER_GAL


def change(x: float, ref: float) -> tuple[float, float | None]:
    d = x - ref
    return d, (d / ref if ref else None)


# --------------------------------------------------------------------------- artifact


def _sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(1 << 20):
            h.update(block)
    return h.hexdigest()


def check_sources(data_dir: Path, manifest_path: Path) -> dict:
    """The committed manifest lists each source with the sha256 the factors were transcribed
    from, and the raw PDFs (if present) still hash to it."""
    man = json.loads(manifest_path.read_text())
    recs = {f["path"]: f for f in man["files"]}
    out = {}
    for key, s in wf.SOURCES.items():
        rec = recs.get(s.path)
        if rec is None or rec["sha256"] != s.sha256:
            raise ValueError(f"{s.path}: the committed water manifest does not match the source")
        p = data_dir / s.path
        on_disk = _sha256(p) if p.exists() else None
        if on_disk is not None and on_disk != s.sha256:
            raise ValueError(f"{p}: sha256 {on_disk} != the manifest's {s.sha256}")
        out[key] = {"citation": s.citation, "url": s.url, "path": s.path, "sha256": s.sha256,
                    "manifest": "data/manifests/water.json", "license": rec["license"],
                    "raw_verified": on_disk is not None}
    return out


def _factor_block(pid: str) -> dict:
    out = {}
    for k, f in wf.NREL_FACTORS.items():
        src = f"NREL/TP-6A20-50900 {f.table} (printed p. {f.page}): {f.fuel_type}, {f.cooling}, {f.technology}"
        out[k] = {"source": src,
                  "median": env(f.median, f.unit, "observed", f"{pid}:factor:{k}"),
                  "min": env(f.min, f.unit, "observed", f"{pid}:factor:{k}:min"),
                  "max": env(f.max, f.unit, "observed", f"{pid}:factor:{k}:max"),
                  "n_studies": env(f.n, "studies", "observed", f"{pid}:factor:{k}:n")}
    return out


def _gal(v, pid, ev="simulated"):
    return env(v, "gal", ev, pid)


def build_artifact(*, run_id: str, window: tuple[datetime, datetime], arrivals_end: datetime,
                   filled: pl.DataFrame, gen: pl.DataFrame, res: dict, sources: dict,
                   crosscheck: dict) -> dict:
    pid = f"water:{run_id}"
    lo, hi = wf.WUE_L_PER_KWH["low"], wf.WUE_L_PER_KWH["high"]
    hf = wf.NREL_FACTORS["hydro"]
    s, e = window
    n_hours = int((e - s) / timedelta(hours=1))
    win = filled.filter((pl.col("ts_utc") >= s) & (pl.col("ts_utc") < e))
    gwin = gen.filter((pl.col("ts_utc") >= s) & (pl.col("ts_utc") < e))
    by_ba = {}
    for ba in SITES:
        x = win.filter(pl.col("ba") == ba)
        gx = gwin.filter(pl.col("ba") == ba)
        ex, hy = x["ex_hydro"].to_numpy(), x["hydro"].to_numpy()
        hydro_share = (_fsum(hy) / hf.median / x.height) if x.height else None
        by_ba[ba] = {
            "mean_ex_hydro_gal_mwh": env(_fsum(ex) / x.height, "gal/MWh", "modeled",
                                         f"{pid}:int:{ba}:ex"),
            "mean_hydro_evap_gal_mwh": env(_fsum(hy) / x.height, "gal/MWh", "modeled",
                                           f"{pid}:int:{ba}:hydro"),
            "mean_with_hydro_gal_mwh": env(_fsum(ex + hy) / x.height, "gal/MWh", "modeled",
                                           f"{pid}:int:{ba}:with"),
            "mean_hydro_share": env(hydro_share, "fraction", "modeled", f"{pid}:int:{ba}:hshare"),
            "mean_generation_mw": env(float(gx["gen_mw"].mean()) if gx.height else None, "MW",
                                      "observed", f"{pid}:int:{ba}:gen",
                                      reason=None if gx.height else "no rows"),
            "n_hours": env(x.height, "hours", "measured", f"{pid}:int:{ba}:n"),
            "n_filled": env(int((x["tier"] >= 2).sum()), "hours", "measured",
                            f"{pid}:int:{ba}:filled"),
        }
    u = res["U"]
    u_ex, u_hy = u["ex_hydro"]["total"], u["hydro"]["total"]
    pols = {}
    for p, r in res.items():
        ex, hy = r["ex_hydro"]["total"], r["hydro"]["total"]
        with_ = ex + hy
        d_ex, f_ex = change(ex, u_ex)
        d_w, f_w = change(with_, u_ex + u_hy)
        d_h, _ = change(hy, u_hy)
        q = f"{pid}:{p}"
        pols[p] = {
            "energy_kwh": env(r["energy_kwh"], "kWh", "simulated", f"{q}:energy"),
            "it_kwh": env(r["it_kwh"], "kWh", "simulated", f"{q}:it"),
            "kwh_share_filled": env(r["kwh_filled"] / r["energy_kwh"], "fraction", "simulated",
                                    f"{q}:filled"),
            "generation_gal": {
                "ex_hydro": _gal(ex, f"{q}:gen:ex"),
                "hydro_evap": _gal(hy, f"{q}:gen:hydro"),
                "with_hydro": _gal(with_, f"{q}:gen:with"),
                "with_hydro_at_hydro_min": _gal(ex + hy * hf.min / hf.median, f"{q}:gen:hmin"),
                "with_hydro_at_hydro_max": _gal(ex + hy * hf.max / hf.median, f"{q}:gen:hmax"),
                "by_site": {st: {
                    "ex_hydro": _gal(r["ex_hydro"]["by_site"][st], f"{q}:site:{st}:ex"),
                    "hydro_evap": _gal(r["hydro"]["by_site"][st], f"{q}:site:{st}:hydro"),
                    "with_hydro": _gal(r["ex_hydro"]["by_site"][st] + r["hydro"]["by_site"][st],
                                       f"{q}:site:{st}:with")} for st in SITES},
            },
            "change_vs_U": {
                "ex_hydro_gal": _gal(d_ex, f"{q}:d:ex"),
                "ex_hydro_frac": env(f_ex, "fraction", "simulated", f"{q}:d:ex:f",
                                     reason=None if f_ex is not None else "U is zero"),
                "hydro_evap_gal": _gal(d_h, f"{q}:d:hydro"),
                "with_hydro_gal": _gal(d_w, f"{q}:d:with"),
                "with_hydro_frac": env(f_w, "fraction", "simulated", f"{q}:d:with:f",
                                       reason=None if f_w is not None else "U is zero"),
            },
            "direct_cooling_gal": {
                "low": _gal(direct_cooling_gal(r["it_kwh"], lo.value), f"{q}:direct:lo"),
                "high": _gal(direct_cooling_gal(r["it_kwh"], hi.value), f"{q}:direct:hi"),
                "change_vs_U_low": _gal(direct_cooling_gal(r["it_kwh"] - u["it_kwh"], lo.value),
                                        f"{q}:direct:d:lo"),
                "change_vs_U_high": _gal(direct_cooling_gal(r["it_kwh"] - u["it_kwh"], hi.value),
                                         f"{q}:direct:d:hi"),
            },
        }
    movers = [p for p in POLICIES if p != "U" and p in res]
    d_ex = [pols[p]["change_vs_U"]["ex_hydro_gal"]["value"] for p in movers]
    d_w = [pols[p]["change_vs_U"]["with_hydro_gal"]["value"] for p in movers]
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": "water",
        "kind": "illustrative",
        "run_id": run_id,
        "note": NOTE,
        "caveats": list(CAVEATS),
        "window": {"start": iso(s), "end": iso(e), "arrivals_end": iso(arrivals_end),
                   "n_hours": env(n_hours, "hours", "measured", f"{pid}:window:n"),
                   "rule": "the registered cohort window: UTC hours from eval_start to the last "
                           "hour any U, S, W or L cohort job runs; totals are over this window "
                           "(the validation year), not annualised"},
        "sources": sources,
        "factors": _factor_block(pid),
        "fuel_map": {f: {"role": m.role, "factor": m.factor, "reason": m.reason,
                         "evidence": m.evidence} for f, m in wf.FUEL_MAP.items()},
        "fuel_rule": ("EIA-930 adjusted generation by fuel, negatives clipped to 0; shares over "
                      "the fuels with a factor or zero water ('other' and 'unknown' take the "
                      "hour's average); hydro = conventional hydro (pumped storage: zero). A "
                      "BA-hour is missing when nothing is reported, the shares' generation is 0, "
                      f"or a fuel reported in ≥ {REPORTED_SHARE:.0%} of the loaded hours is null; "
                      "missing hours are linearly interpolated in time (tier 2)"),
        "wue": {
            "low": env(lo.value, lo.unit, "observed", f"{pid}:wue:lo"),
            "high": env(hi.value, hi.unit, "observed", f"{pid}:wue:hi"),
            "low_source": f"LBNL-2001637 p. {lo.page}: {lo.quote}",
            "high_source": f"LBNL-2001637 p. {hi.page}: {hi.quote}",
            "rule": "assumed: the U.S.-average site WUE from 2023 (just over 0.36 L/kWh) to the "
                    "2028 scenario's upper end (0.48 L/kWh) brackets the validation year; one "
                    "national range for every site, applied to IT energy (facility kWh ÷ PUE)",
            "rule_evidence": "assumed",
        },
        "context": {
            "lbnl_us_grid_l_per_kwh": env(wf.LBNL_US_GRID_L_PER_KWH.value, "L/kWh", "observed",
                                          f"{pid}:ctx:us"),
            "lbnl_us_grid_gal_per_mwh": env(wf.LBNL_US_GRID_L_PER_KWH.value * 1000 / wf.L_PER_GAL,
                                            "gal/MWh", "observed", f"{pid}:ctx:us:gal"),
            "source": f"LBNL-2001637 p. {wf.LBNL_US_GRID_L_PER_KWH.page}: "
                      f"{wf.LBNL_US_GRID_L_PER_KWH.quote} (consumption-flow method of Siddik et "
                      f"al. 2024; not comparable one-to-one)",
            "gal_per_acre_foot": env(wf.GAL_PER_ACRE_FOOT, "gal/acre-ft", "observed",
                                     f"{pid}:ctx:af"),
        },
        "intensity": {"by_ba": by_ba,
                      "rule": "time mean of the hourly intensity over the window (filled hours "
                              "included)"},
        "policies": pols,
        "headline": {
            "policies": movers,
            "rule": "change vs U local (stay in Utah) over the window, generation-associated "
                    "water, without and with hydro evaporation; S, W and L",
            "change_ex_hydro_gal": env([min(d_ex), max(d_ex)], "gal", "simulated",
                                       f"{pid}:head:ex"),
            "change_with_hydro_gal": env([min(d_w), max(d_w)], "gal", "simulated",
                                         f"{pid}:head:with"),
        },
        "crosscheck": crosscheck,
    }


def from_run(run_dir: Path, metrics: dict, data_dir: Path, manifest_path: Path) -> dict:
    """Read the registered run (validation only) and build the artifact."""
    from gridpilot.eval.accounting import TruthTable, fsum_by, job_accounting
    from gridpilot.storage import cohort_window

    cfg = json.loads((run_dir / "config.json").read_text())
    if cfg.get("window") != "validation":
        raise ValueError(f"{run_dir} is not a validation run")
    if metrics.get("run_id") != run_dir.name:
        raise ValueError(f"metrics are for {metrics.get('run_id')}, not {run_dir.name}")
    t_start = datetime.fromisoformat(cfg["eval_start"])
    t_a = datetime.fromisoformat(cfg["A"])
    led = {p: pl.read_parquet(run_dir / f"ledger_{p}.parquet") for p in POLICIES}
    win = cohort_window(t_start, max(x["end_ts"].max() for x in led.values()))
    sources = check_sources(data_dir, manifest_path)
    bal = load_balance(win[0] - MARGIN, win[1])
    gen = intensity(bal)
    filled = fill(gen, start=win[0] - MARGIN, end=win[1])
    tts = truth_tables(filled)
    jobs = led["U"].select("job_uid",
                           pl.col("job_uid").str.split("#").list.first().alias("source_id"),
                           "arrival_ts", "gpus", "duration_s")
    carbon = TruthTable(drop_sealed(pl.read_parquet(run_dir / "truth_fill.parquet")))
    res, cc = {}, {}
    for p in POLICIES:
        res[p] = policy_water(led[p], jobs, tts)
        acc = job_accounting(led[p], jobs, carbon)
        reg = metrics["policies"][p]["metrics"]
        co2, kwh = fsum_by(acc, "co2_kg"), fsum_by(acc, "energy_kwh")
        ok = (math.isclose(co2, reg["co2_kg"]["value"], rel_tol=1e-9)
              and math.isclose(kwh, reg["energy_kwh"]["value"], rel_tol=1e-9)
              and math.isclose(res[p]["energy_kwh"], kwh, rel_tol=1e-12))
        if not ok:
            raise AssertionError(f"{p}: re-accounted CO₂ {co2} / energy {kwh} differ from the "
                                 f"registered metrics")
        cc[p] = {"co2_kg_reaccounted": env(co2, "kg_CO2", "simulated", f"water:cc:{p}:co2"),
                 "matches_registered": True}
    crosscheck = {"rule": "the carbon accounting re-run on the same ledgers, jobs and filled "
                          "carbon truth reproduces the registered co2_kg and energy_kwh (rel "
                          "1e-9), so the water uses the registered hourly energy",
                  "policies": cc}
    return build_artifact(run_id=run_dir.name, window=win, arrivals_end=t_a, filled=filled,
                          gen=gen, res=res, sources=sources, crosscheck=crosscheck)
