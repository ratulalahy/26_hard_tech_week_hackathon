"""Stage 3 T10 Part B: production-basis repricing of fixed ledgers and the F14.6 common-support
cohort (toy ledgers with hand-checkable values)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from gridpilot.eval import TruthTable, job_accounting
from gridpilot.extensions import common_support_cohort, policy_contrasts, reprice
from gridpilot.sim import LEDGER_COLUMNS, SITES

T0 = datetime(2024, 11, 4, 7, tzinfo=UTC)  # Monday 00:00 America/Denver
H = timedelta(hours=1)
WEEKS = 3
WINDOW = (T0, T0 + WEEKS * 7 * 24 * H)
N_H = WEEKS * 7 * 24 + 48
RATE = 0.6 * 1.2  # kWh per GPU-hour with PUE


def _truth(vals: dict[str, float], tier2: dict[str, set[int]] | None = None) -> pl.DataFrame:
    """Flat hourly truth per site; `tier2[site]` lists hours priced on tier 2."""
    tier2 = tier2 or {}
    rows = []
    for ba in SITES:
        for h in range(N_H):
            rows.append({"ba": ba, "ts_utc": T0 + h * H, "ci_g_kwh": vals.get(ba, 500.0),
                         "tier": 2 if h in tier2.get(ba, set()) else 1})
    return pl.DataFrame(rows, schema={"ba": pl.Utf8, "ts_utc": pl.Datetime("us", "UTC"),
                                      "ci_g_kwh": pl.Float64, "tier": pl.Int8})


def _jobs(n_per_week=2):
    rows = []
    for w in range(WEEKS):
        for k in range(n_per_week):
            uid = f"s{w}{k}#c0"
            rows.append({"job_uid": uid, "source_id": uid[:-3],
                         "arrival_ts": T0 + (w * 168 + 10 * k + 1) * H, "duration_s": 3600.0,
                         "gpus": 1, "job_type": "SFT", "flexible": True, "max_delay_s": 21600.0,
                         "mobile": True})
    return pl.DataFrame(rows, schema_overrides={"arrival_ts": pl.Datetime("us", "UTC")})


def _ledger(jobs, site_of):
    """Every job starts at arrival, on `site_of(uid)`."""
    rows = []
    for r in jobs.iter_rows(named=True):
        site = site_of(r["job_uid"])
        rows.append({"job_uid": r["job_uid"], "site": site, "start_ts": r["arrival_ts"],
                     "end_ts": r["arrival_ts"] + H, "transfer": site != "PACE", "late": False,
                     "deadline_ts": r["arrival_ts"] + 10 * H, "gpus": 1,
                     "arrival_ts": r["arrival_ts"], "duration_s": 3600.0,
                     "moved": site != "PACE", "booking_site": "PACE", "blocked": False,
                     "fit_rejected": False})
    return pl.DataFrame(rows, schema_overrides={
        c: pl.Datetime("us", "UTC") for c in ("start_ts", "end_ts", "deadline_ts", "arrival_ts")
    }).select(LEDGER_COLUMNS)


def test_policy_contrasts_saving_is_ratio_of_totals():
    jobs = _jobs()
    leds = {"U": _ledger(jobs, lambda u: "PACE"), "L": _ledger(jobs, lambda u: "BPAT")}
    tt = TruthTable(_truth({"PACE": 800.0, "BPAT": 100.0}))
    out = policy_contrasts(leds, jobs, tt, WINDOW)
    n = jobs.height
    u = n * RATE * 800 / 1000
    tr = n * 0.05 * 0.6 * 1.2 * 0.5 * (800 + 100) / 1000  # transfer, half at each end
    l_ = n * RATE * 100 / 1000 + tr
    assert out["totals"]["U"] == pytest.approx(u)
    assert out["totals"]["L"] == pytest.approx(l_)
    assert out["contrasts"]["L"][4]["saving"] == pytest.approx((u - l_) / u)
    assert out["n_weeks"] == WEEKS
    assert set(out["contrasts"]) == {"L"}


def test_reprice_keeps_schedules_and_changes_only_the_basis():
    jobs = _jobs()
    leds = {"U": _ledger(jobs, lambda u: "PACE"), "L": _ledger(jobs, lambda u: "BPAT")}
    cons = TruthTable(_truth({"PACE": 800.0, "BPAT": 100.0}))
    prod = TruthTable(_truth({"PACE": 800.0, "BPAT": 20.0}))  # hydro: lower production CI
    out = reprice(leds, jobs, {"consumption": cons, "production": prod}, WINDOW)
    assert set(out) == {"consumption", "production"}
    s_c = out["consumption"]["contrasts"]["L"][4]["saving"]
    s_p = out["production"]["contrasts"]["L"][4]["saving"]
    assert s_p > s_c
    # Same ledgers: energy is identical on both bases; only CO₂ changes.
    e = {b: job_accounting(leds["L"], jobs, tt)["energy_kwh"].sum()
         for b, tt in (("c", cons), ("p", prod))}
    assert e["c"] == e["p"]
    assert out["production"]["tier_ge2_kwh_share"]["L"] == 0.0


def test_common_support_drops_jobs_touching_tier2_under_any_policy():
    jobs = _jobs()
    moved = {"s00#c0", "s11#c0"}
    leds = {"U": _ledger(jobs, lambda u: "PACE"),
            "L": _ledger(jobs, lambda u: "CISO" if u in moved else "PACE")}
    # CISO hour of s00's execution is tier 2: s00 drops from both policies; s11 stays.
    s00 = jobs.filter(pl.col("job_uid") == "s00#c0")["arrival_ts"][0]
    h = int((s00 - T0) / H)
    tt = TruthTable(_truth({"PACE": 800.0, "CISO": 200.0}, tier2={"CISO": {h}}))
    cs = common_support_cohort(leds, jobs, tt, WINDOW)
    assert cs["dropped"] == ["s00#c0"]
    assert cs["n_cohort"] == jobs.height and cs["n_jobs"] == jobs.height - 1
    assert cs["share_jobs"] == pytest.approx((jobs.height - 1) / jobs.height)
    assert cs["energy_share"]["U"] == pytest.approx((jobs.height - 1) / jobs.height)
    # Savings on the cohort: only s11 moved (CISO 200 vs PACE 800, plus transfer).
    n = jobs.height - 1
    u = n * RATE * 800 / 1000
    l_ = (n - 1) * RATE * 800 / 1000 + RATE * 200 / 1000 + \
        0.05 * 0.6 * 1.2 * 0.5 * (800 + 200) / 1000
    got = cs["contrasts"]["contrasts"]["L"][4]["saving"]
    assert got == pytest.approx((u - l_) / u)


def test_common_support_on_all_tier1_truth_keeps_everyone():
    jobs = _jobs()
    leds = {"U": _ledger(jobs, lambda u: "PACE"), "L": _ledger(jobs, lambda u: "BPAT")}
    cs = common_support_cohort(leds, jobs, TruthTable(_truth({})), WINDOW)
    assert cs["dropped"] == [] and cs["share_jobs"] == 1.0 and cs["energy_share"]["U"] == 1.0
