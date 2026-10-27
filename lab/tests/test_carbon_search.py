"""Emissions-first carbon search K/W/L/H on the F11 engine.

Spec §8 "Core policy"; §15 F3, F10, F11, F12.1–F12.3, F12.7, F13.1, F14.5–F14.7, and the
Task 5 amendments. Signals are synthetic: one forecast issue (or a few) plus a constant
climatology tail, so every expected kg can be written down by hand. Time is int µs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gridpilot.forecast import BA_TZ, fit_climatology
from gridpilot.sim import (
    Action,
    Capacity,
    G,
    S,
    U,
    closed_intervals,
    simulate,
    u_bookings,
)
from gridpilot.sim.carbon_search import (
    GPU_KW,
    PUE,
    CarbonSearch,
    job_energy_kwh,
    transfer_kwh,
)
from gridpilot.sim.engine import Job, SimContext

T0 = datetime(2024, 11, 4, tzinfo=UTC)  # a Monday, inside validation
T0_US = int(T0.timestamp()) * 1_000_000
SEC = 1_000_000
MIN = 60 * SEC
HOUR = 60 * MIN
GRID = (T0 - timedelta(days=2), T0 + timedelta(days=10))
CORE = ("PACE", "CISO", "BPAT", "NEVP")
BIG = {"PACE": 64, "CISO": 64, "BPAT": 64, "NEVP": 64}
TAIL_G = 999.0  # the constant climatology tail used by the K/W/L fixtures


def jobs_frame(rows: list[dict]) -> pl.DataFrame:
    """Synthetic replay() frame. `at_min` is the arrival offset from T0 in minutes."""
    out = []
    for i, r in enumerate(rows):
        flexible = r.get("flexible", False)
        out.append({
            "job_uid": r.get("job_uid", f"j{i:03d}#c0"),
            "arrival_ts": T0 + timedelta(minutes=r.get("at_min", 0.0)),
            "duration_s": float(r.get("dur_s", r.get("dur_min", 60.0) * 60)),
            "gpus": r.get("gpus", 1),
            "job_type": r.get("job_type", "SFT" if flexible else "Other"),
            "flexible": flexible,
            "max_delay_s": float(r.get("delay_h", 6.0 if flexible else 0.0) * 3600),
            "mobile": r.get("mobile", flexible),
        })
    return pl.DataFrame(out, schema={
        "job_uid": pl.Utf8, "arrival_ts": pl.Datetime("us", "UTC"), "duration_s": pl.Float64,
        "gpus": pl.Int64, "job_type": pl.Utf8, "flexible": pl.Boolean,
        "max_delay_s": pl.Float64, "mobile": pl.Boolean,
    })


def hourly(fn, bas=CORE, first_h=-24, n_h=72) -> dict[str, list[tuple[int, float]]]:
    """{ba: [(hour offset from T0, value)]} for hours [first_h, first_h + n_h)."""
    return {ba: [(h, float(fn(ba, h))) for h in range(first_h, first_h + n_h)] for ba in bas}


def fc_frame(values: dict, issue: datetime, model: str = "K") -> pl.DataFrame:
    rows = [{"ba": ba, "target": "ci_consumed", "model": model, "issue_ts": issue,
             "target_ts": T0 + timedelta(hours=h), "value": v, "evidence": "forecast"}
            for ba, hv in values.items() for h, v in hv]
    return pl.DataFrame(rows).with_columns(
        pl.col("issue_ts").dt.cast_time_unit("us"), pl.col("target_ts").dt.cast_time_unit("us"))


def truth_frame(values: dict) -> pl.DataFrame:
    rows = [{"ba": ba, "ts_utc": T0 + timedelta(hours=h), "ci_consumed_g_kwh": v}
            for ba, hv in values.items() for h, v in hv]
    return pl.DataFrame(rows).with_columns(pl.col("ts_utc").dt.cast_time_unit("us"))


def const_tail(value: float = TAIL_G, bas=CORE):
    labels = pl.DataFrame({"ts_utc": [T0 - timedelta(days=30) + timedelta(hours=h)
                                      for h in range(24 * 14)]}).with_columns(
        pl.col("ts_utc").dt.cast_time_unit("us"), pl.lit(value).alias("value"))
    return {ba: fit_climatology(labels, BA_TZ[ba]) for ba in bas}


def k_policy(fn, *, issue=T0 - timedelta(hours=20), first_h=-24, n_h=72, signal="K",
             extra: pl.DataFrame | None = None, **kw) -> CarbonSearch:
    fc = fc_frame(hourly(fn, first_h=first_h, n_h=n_h), issue, model=signal)
    if extra is not None:
        fc = pl.concat([fc, extra])
    return CarbonSearch(signal, fc, None, tail=const_tail(), grid=GRID, **kw)


def h_policy(fn, **kw) -> CarbonSearch:
    return CarbonSearch("H", None, truth_frame(hourly(fn, first_h=-48, n_h=24 * 11)),
                        grid=GRID, **kw)


def run(jobs, policy, sites=BIG, **kw):
    closed = kw.pop("closed", None)
    b = u_bookings(jobs, sites, closed=closed)
    return simulate(jobs, policy, sites, bookings=b, closed=closed, **kw)


def row(ledger: pl.DataFrame, uid: str) -> dict:
    return ledger.filter(pl.col("job_uid") == uid).to_dicts()[0]


def at(r: dict) -> tuple[str, float]:
    return r["site"], (r["start_ts"] - T0).total_seconds() / 60


def mkjob(*, arr=0, dur=HOUR, gpus=1, flexible=True, delay=6 * HOUR, mobile=None,
          booking_start=None, deadline=None) -> Job:
    mobile = flexible if mobile is None else mobile
    a = T0_US + arr
    dl = deadline if deadline is not None else a + dur + delay
    b = Action("PACE", a if booking_start is None else T0_US + booking_start)
    return Job("x", a, dur, dur / SEC, gpus, "SFT", flexible, delay, mobile, dl, b)


def views(sites=BIG):
    return {s: Capacity(n).view() for s, n in sites.items()}


# --------------------------------------------------------------------------- energy


def test_energy_constants():
    assert job_energy_kwh(8, 3600) == pytest.approx(8 * 0.60 * 1.20)
    assert transfer_kwh(8, 3600) == pytest.approx(0.05 * 8 * 0.60)  # IT; PUE per half
    assert (GPU_KW, PUE) == (0.60, 1.20)


def test_integral_partial_hours():
    """A 90-minute job starting at :30 weighs its first hour 0.5 and its second 1.0."""
    vals = {0: 100.0, 1: 200.0, 2: 400.0}
    pol = h_policy(lambda ba, h: vals.get(h, 50.0))
    job = mkjob(arr=30 * MIN, dur=90 * MIN, gpus=4)
    kg = pol.predicted_kg(job, [Action("PACE", T0_US + 30 * MIN)], T0_US + 30 * MIN, "PACE")
    assert kg[0] == pytest.approx(4 * GPU_KW * PUE * (0.5 * 100 + 1.0 * 200) / 1000, rel=1e-12)
    # And a µs-fractional start inside one hour weighs exactly its overlap.
    s = T0_US + 10 * MIN + 7
    kg = pol.predicted_kg(job, [Action("PACE", s)], s, "PACE")
    w0 = (HOUR - 10 * MIN - 7) / HOUR
    assert kg[0] == pytest.approx(4 * GPU_KW * PUE * (w0 * 100 + (1.5 - w0) * 200) / 1000,
                                  rel=1e-12)  # ends at 1:40 + 7 µs, inside hour 1


def test_transfer_energy_charged_at_arrival_hour():
    """F7/F14.5: 5% of IT energy at arrival, half at home and half at the destination,
    PUE at each end, priced in the UTC hour containing the arrival."""
    pol = h_policy(lambda ba, h: {"PACE": 600.0, "BPAT": 100.0}.get(ba, 300.0) + h)
    job = mkjob(arr=10 * MIN, dur=2 * HOUR, gpus=8)
    s = T0_US + 2 * HOUR  # BPAT hours 2 and 3: 102 and 103
    kg = pol.predicted_kg(job, [Action("BPAT", s)], job.arrival_us, "PACE")[0]
    exec_kg = 8 * GPU_KW * PUE * (102 + 103) / 1000
    t = transfer_kwh(8, 7200)
    assert kg == pytest.approx(exec_kg + 0.5 * t * PUE * (600 + 100) / 1000, rel=1e-12)


# --------------------------------------------------------------------------- signals


def test_tail_uses_climatology():
    """Hours past the last issued target use the K climatology (modeled) tail."""
    pol = k_policy(lambda ba, h: 100.0, first_h=0, n_h=24)  # coverage ends at T0 + 24 h
    job = mkjob(arr=22 * HOUR + 30 * MIN, dur=3 * HOUR, gpus=2)
    s = T0_US + 22 * HOUR + 30 * MIN  # 1.5 h covered at 100, 1.5 h tail at TAIL_G
    kg = pol.predicted_kg(job, [Action("PACE", s)], s, "PACE")[0]
    assert kg == pytest.approx(2 * GPU_KW * PUE * (1.5 * 100 + 1.5 * TAIL_G) / 1000)
    assert pol.coverage_end_us(s, "PACE") == T0_US + 24 * HOUR


def test_no_future_issue():
    """Leakage: an issue published 1 s after the arrival must not change the choice;
    the same issue published at the arrival does (so the test bites)."""
    base = lambda ba, h: {"PACE": 500.0}.get(ba, 400.0)
    jobs = jobs_frame([{"job_uid": "x", "at_min": 0, "dur_min": 60, "gpus": 1,
                        "flexible": True}])
    arrival = T0
    absurd = fc_frame({"NEVP": [(4, -1e6)]}, arrival + timedelta(seconds=1))
    ref = row(run(jobs, k_policy(base)), "x")
    got = row(run(jobs, k_policy(base, extra=absurd)), "x")
    assert at(got) == at(ref)
    leak = fc_frame({"NEVP": [(4, -1e6)]}, arrival)
    assert at(row(run(jobs, k_policy(base, extra=leak)), "x")) == ("NEVP", 240)


def test_latest_issue_wins():
    """Each hour uses the latest issue at or before the arrival that covers it."""
    old = fc_frame(hourly(lambda ba, h: 100.0, first_h=0, n_h=24), T0 - timedelta(hours=20))
    new = fc_frame(hourly(lambda ba, h: 300.0, first_h=0, n_h=2), T0 - timedelta(hours=1))
    pol = CarbonSearch("W", old.vstack(new).with_columns(pl.lit("W").alias("model")), None,
                       tail=const_tail(), grid=GRID)
    job = mkjob(dur=4 * HOUR)
    kg = pol.predicted_kg(job, [Action("PACE", T0_US)], T0_US, "PACE")[0]
    assert kg == pytest.approx(GPU_KW * PUE * (300 + 300 + 100 + 100) / 1000)
    kg = pol.predicted_kg(job, [Action("PACE", T0_US)], T0_US - 2 * HOUR, "PACE")[0]
    assert kg == pytest.approx(GPU_KW * PUE * 400 / 1000)  # before the new issue


def test_H_uses_truth():
    """H's choice equals the brute-force argmin of realized kg over the operational
    candidates (hourly boundaries, earliest feasible start, booking), F13.1."""
    rng = np.random.default_rng(7)
    table = {ba: rng.uniform(50, 800, 24 * 11) for ba in CORE}
    fn = lambda ba, h: table[ba][h + 48]
    pol = h_policy(fn)
    for arr_min, dur_min, delay_h in [(17, 95, 6.0), (0, 60, 6.0), (41, 30, 1.0),
                                      (5, 400, 6.0), (59, 61, 1.0)]:
        jobs = jobs_frame([{"job_uid": "x", "at_min": arr_min, "dur_min": dur_min,
                            "gpus": 2, "flexible": True, "delay_h": delay_h}])
        got = at(row(run(jobs, pol), "x"))
        a = arr_min * MIN
        d = dur_min * MIN
        latest = a + d + int(delay_h * HOUR) - d
        cands = set()
        for site in CORE:
            ready = a + (0 if site == "PACE" else 30 * MIN)
            starts = {ready} | set(range(-(-ready // HOUR) * HOUR, latest + 1, HOUR))
            cands |= {(site, s) for s in starts if s <= latest}
        cands.add(("PACE", a))

        def brute(c, a=a, d=d):
            site, s = c
            tot = 0.0
            for h in range(-2, 24 * 8):
                ov = max(0, min(s + d, (h + 1) * HOUR) - max(s, h * HOUR))
                tot += ov / HOUR * fn(site, h)
            kg = 2 * GPU_KW * PUE * tot / 1000
            if site != "PACE":
                ha = a // HOUR
                kg += 0.5 * transfer_kwh(2, d / SEC) * PUE * (fn("PACE", ha) + fn(site, ha)) / 1000
            return kg, s + d, site != "PACE", site, s

        site, s = min(cands, key=brute)
        assert got == (site, s / MIN), (arr_min, dur_min, delay_h)


# --------------------------------------------------------------------------- legality


def test_mask_closes_destination():
    """F3: a masked BPAT hour that every BPAT start in the window touches makes BPAT
    illegal; the next-cleanest site wins. Without the mask BPAT wins."""
    pol = h_policy(lambda ba, h: {"BPAT": 10.0, "NEVP": 50.0}.get(ba, 600.0))
    jobs = jobs_frame([{"job_uid": "x", "at_min": 0, "dur_min": 120, "gpus": 2,
                        "flexible": True, "job_type": "Eval", "delay_h": 1.0}])
    assert at(row(run(jobs, pol), "x"))[0] == "BPAT"
    closed = {"BPAT": [(T0_US + 2 * HOUR, T0_US + 3 * HOUR)]}  # starts in [30, 60] min touch it
    r = row(run(jobs, pol, closed=closed), "x")
    assert r["site"] == "NEVP" and r["moved"]


def test_mask_param_must_match_engine_calendar():
    mask = pl.DataFrame({"ba": ["BPAT"] * 3, "ts_utc": [T0 + timedelta(hours=h) for h in (0, 1, 2)],
                         "truth_ok": [True, False, True]}).with_columns(
        pl.col("ts_utc").dt.cast_time_unit("us"))
    pol = h_policy(lambda ba, h: 100.0, mask=mask)
    jobs = jobs_frame([{"job_uid": "x", "flexible": True}])
    run(jobs, pol, closed=closed_intervals(mask))  # same calendar: fine
    pol = h_policy(lambda ba, h: 100.0, mask=mask)
    with pytest.raises(ValueError, match="mask"):
        run(jobs, pol)  # the engine runs without the closure


def test_inflexible_stays():
    """F12.2: a non-flexible job lands at PACE inside [arrival, U start]; when U start
    is the arrival it starts at arrival, even if a cleaner hour comes later."""
    pol = k_policy(lambda ba, h: 900.0 if h == 0 else 10.0)
    jobs = jobs_frame([{"job_uid": "r", "at_min": 0, "dur_min": 60, "gpus": 2}])
    r = row(run(jobs, pol), "r")
    assert at(r) == ("PACE", 0) and not r["moved"]


def test_inflexible_retimes_in_queue_window():
    """Capacity freed by an earlier move lets an inflexible job choose a cleaner start
    inside its baseline queue window [arrival, U start]."""
    sites = {"PACE": 4, "CISO": 0, "BPAT": 4, "NEVP": 0}
    pace = {0: 500.0, 1: 100.0, 2: 300.0}
    pol = k_policy(lambda ba, h: pace.get(h, 500.0) if ba == "PACE" else 50.0)
    jobs = jobs_frame([
        {"job_uid": "B", "at_min": 0, "dur_min": 120, "gpus": 4, "flexible": True},
        {"job_uid": "X", "at_min": 1, "dur_min": 60, "gpus": 4},
    ])
    b = u_bookings(jobs, sites)
    assert b.filter(pl.col("job_uid") == "X")["start_us"].item() == T0_US + 2 * HOUR
    led = simulate(jobs, pol, sites, bookings=b)
    assert row(led, "B")["site"] == "BPAT"
    x = row(led, "X")
    assert at(x) == ("PACE", 60) and x["moved"]


def test_booking_is_a_candidate():
    """F12.7: the exact (non-hourly) booking is an explicit candidate and can win."""
    sites = {"PACE": 4, "CISO": 0, "BPAT": 4, "NEVP": 0}
    pace = {0: 500.0, 1: 500.0, 2: 10.0}
    pol = k_policy(lambda ba, h: pace.get(h, 500.0) if ba == "PACE" else 50.0)
    jobs = jobs_frame([
        {"job_uid": "B", "at_min": 0, "dur_min": 95, "gpus": 4, "flexible": True},
        {"job_uid": "X", "at_min": 1, "dur_min": 60, "gpus": 4},
    ])
    b = u_bookings(jobs, sites)
    assert b.filter(pl.col("job_uid") == "X")["start_us"].item() == T0_US + 95 * MIN
    led = simulate(jobs, pol, sites, bookings=b)
    assert row(led, "B")["site"] == "BPAT"
    x = row(led, "X")
    assert at(x) == ("PACE", 95) and not x["moved"]  # earliest (1 min) and 60 min lose


def test_candidates():
    """F10 + F12.3: hourly boundaries in [ready, deadline − duration], plus the earliest
    feasible start at each legal site, plus the booking; masked starts are dropped."""
    pol = h_policy(lambda ba, h: 100.0)
    ctx = SimContext(sites={"PACE": 8, "CISO": 0, "BPAT": 8, "NEVP": 8},
                     closed={"NEVP": (np.array([T0_US]), np.array([T0_US + 24 * HOUR]))})
    job = mkjob(arr=10 * MIN, dur=HOUR, delay=2 * HOUR, gpus=2)
    got = sorted((a.site, (a.start_us - T0_US) // MIN)
                 for a in pol.candidates(job, views(ctx.sites), ctx))
    assert got == [("BPAT", 40), ("BPAT", 60), ("BPAT", 120),
                   ("PACE", 10), ("PACE", 60), ("PACE", 120)]
    # F1 deadline later than the declared one (U queued the job): the window follows it.
    job = mkjob(arr=0, dur=HOUR, delay=0, flexible=False, deadline=T0_US + 4 * HOUR,
                booking_start=3 * HOUR)
    got = sorted((a.site, (a.start_us - T0_US) // MIN)
                 for a in pol.candidates(job, views(ctx.sites), ctx))
    assert got == [("PACE", 0), ("PACE", 60), ("PACE", 120), ("PACE", 180)]


def test_best_that_fits_and_ties():
    """The best-ranked candidate that fits the view wins; ties within 1e-9 kg go to the
    earlier completion, then PACE, then BA code."""
    flat = h_policy(lambda ba, h: 100.0)
    ctx = SimContext(sites=BIG)
    job = mkjob(arr=0, dur=HOUR, gpus=2)
    assert flat.choose(job, job.arrival_us, views(), ctx) is None  # booking: PACE at 0
    # Remote ties: CISO and NEVP identical; CISO wins on BA code at the earliest finish.
    pol = h_policy(lambda ba, h: {"CISO": 5.0, "NEVP": 5.0}.get(ba, 900.0))
    assert pol.choose(job, job.arrival_us, views(), ctx) == Action("CISO", T0_US + 30 * MIN)
    # CISO full at the earliest start: the earliest feasible later CISO start, or NEVP?
    caps = {s: Capacity(n) for s, n in BIG.items()}
    caps["CISO"].reserve(T0_US, T0_US + 2 * HOUR, 64)
    v = {s: c.view() for s, c in caps.items()}
    assert pol.choose(job, job.arrival_us, v, ctx) == Action("NEVP", T0_US + 30 * MIN)


# --------------------------------------------------------------------------- F14.7 diagnostic


def _pending_case(with_earlier_move: bool):
    sites = {"PACE": 4, "CISO": 0, "BPAT": 0, "NEVP": 0}
    pace = {3: 100.0, 5: 200.0}
    pol = k_policy(lambda ba, h: pace.get(h, 500.0))
    rows = [{"job_uid": "F", "at_min": 0, "dur_min": 60, "gpus": 4, "flexible": True}]
    if with_earlier_move:  # E is processed first (same arrival, uid E < F) and takes hour 3
        rows.insert(0, {"job_uid": "E", "at_min": 0, "dur_min": 60, "gpus": 4,
                        "flexible": True})
    else:  # X's pending booking holds hour 3 when F decides
        rows.append({"job_uid": "X", "at_min": 180, "dur_min": 60, "gpus": 4})
    jobs = jobs_frame(rows)
    b = u_bookings(jobs, sites)
    return pol, jobs, b, sites


def test_blocked_by_pending_booking():
    pol, jobs, b, sites = _pending_case(False)
    plain = simulate(jobs, pol, sites, bookings=b)
    diag = simulate(jobs, pol, sites, bookings=b, diagnose_blocked=True)
    assert at(row(plain, "F")) == ("PACE", 300)  # hour 3 is held by X's booking
    assert plain.drop("blocked").equals(diag.drop("blocked"))  # state follows the real view
    assert not plain["blocked"].any()
    assert row(diag, "F")["blocked"] and diag["blocked"].sum() == 1


def test_not_blocked_by_earlier_move():
    pol, jobs, b, sites = _pending_case(True)
    diag = simulate(jobs, pol, sites, bookings=b, diagnose_blocked=True)
    assert at(row(diag, "E")) == ("PACE", 180)
    assert at(row(diag, "F")) == ("PACE", 300)
    assert not diag["blocked"].any()  # earlier committed moves are kept in both views


def test_blocked_needs_a_better_score():
    """A different counterfactual choice that does not improve kg by > 1e-9 is not
    blocked (F14.7)."""
    pol = h_policy(lambda ba, h: 100.0)
    ctx = SimContext(sites={"PACE": 4, "CISO": 0, "BPAT": 0, "NEVP": 0})
    job = mkjob(arr=0, dur=HOUR, gpus=4, booking_start=2 * HOUR)
    real = {s: Capacity(n) for s, n in ctx.sites.items()}
    real["PACE"].reserve(T0_US, T0_US + 2 * HOUR, 4)  # a pending booking
    cf = views(ctx.sites)
    actual = Action("PACE", T0_US + 2 * HOUR)
    rv = {s: c.view() for s, c in real.items()}
    assert not pol.blocked(job, job.arrival_us, actual, rv, cf, ctx)  # flat: no gain
    pol = h_policy(lambda ba, h: 50.0 if h == 0 else 100.0)
    assert pol.blocked(job, job.arrival_us, actual, rv, cf, ctx)


def test_blocked_for_G_and_S():
    """F14.7 for the carbon-blind policies: G by an earlier finish, S by a higher-ranked
    site (or the same site, earlier)."""
    ctx = SimContext(sites={"PACE": 4, "CISO": 0, "BPAT": 4, "NEVP": 0})
    job = mkjob(arr=0, dur=HOUR, gpus=4, booking_start=2 * HOUR)
    real = {s: Capacity(n) for s, n in ctx.sites.items()}
    real["PACE"].reserve(T0_US, T0_US + 2 * HOUR, 4)
    real["BPAT"].reserve(T0_US, T0_US + 3 * HOUR, 4)
    rv = {s: c.view() for s, c in real.items()}
    cf = views(ctx.sites)
    actual = Action("PACE", T0_US + 2 * HOUR)
    assert G().blocked(job, job.arrival_us, actual, rv, cf, ctx)
    assert not G().blocked(job, job.arrival_us, Action("PACE", T0_US), rv, cf, ctx)
    s = S(ranking=["BPAT", "PACE"])
    assert s.blocked(job, job.arrival_us, actual, rv, cf, ctx)  # BPAT at 30 min ranks higher
    assert not s.blocked(job, job.arrival_us, Action("BPAT", T0_US + 30 * MIN), rv, cf, ctx)
    assert not U().blocked(job, job.arrival_us, Action("PACE", T0_US), rv, cf, ctx)


def test_diagnose_runs_for_every_policy():
    jobs = jobs_frame([
        {"job_uid": f"j{i}", "at_min": 7 * i, "dur_min": 30 + 11 * i, "gpus": 1 + i % 4,
         "flexible": i % 3 != 0} for i in range(12)])
    sites = {"PACE": 4, "CISO": 2, "BPAT": 3, "NEVP": 2}
    b = u_bookings(jobs, sites)
    for p in (U(), G(), S(ranking=["BPAT", "CISO", "NEVP"]),
              k_policy(lambda ba, h: 100.0 + 37 * ((h * 7 + len(ba)) % 5))):
        plain = simulate(jobs, p, sites, bookings=b)
        diag = simulate(jobs, p, sites, bookings=b, diagnose_blocked=True)
        assert plain.drop("blocked").equals(diag.drop("blocked")), p.name
    assert not simulate(jobs, U(), sites, bookings=b, diagnose_blocked=True)["blocked"].any()


# --------------------------------------------------------------------------- guards


def test_signal_guards():
    with pytest.raises(ValueError, match="signal"):
        CarbonSearch("X", None, None)
    with pytest.raises(ValueError, match="truth"):
        CarbonSearch("H", None, None, grid=GRID)
    with pytest.raises(ValueError, match="tail"):
        CarbonSearch("K", fc_frame(hourly(lambda ba, h: 1.0), T0), None, grid=GRID)
    sealed = datetime(2025, 11, 1, tzinfo=UTC)
    bad = fc_frame({"PACE": [(0, 1.0)]}, T0).with_columns(pl.lit(sealed).dt.cast_time_unit("us")
                                                            .alias("target_ts"))
    with pytest.raises(ValueError, match="seal"):
        CarbonSearch("K", bad, None, tail=const_tail(), grid=GRID)
    with pytest.raises(ValueError, match="seal"):
        CarbonSearch("K", fc_frame({"PACE": [(0, 1.0)]}, T0), None, tail=const_tail(),
                     grid=(GRID[0], sealed + timedelta(hours=1)))
    dup = fc_frame({"PACE": [(0, 1.0), (0, 2.0)]}, T0)
    with pytest.raises(ValueError, match="duplicate"):
        CarbonSearch("K", dup, None, tail=const_tail(), grid=GRID)
    # A candidate outside the signal grid raises instead of inventing values.
    pol = h_policy(lambda ba, h: 1.0)
    late = mkjob(arr=12 * 24 * HOUR)
    with pytest.raises(ValueError, match="grid"):
        pol.predicted_kg(late, [Action("PACE", late.arrival_us)], late.arrival_us, "PACE")
    # H on a missing truth hour raises (the mask or the F14.6 fill must cover it).
    holes = truth_frame({ba: [(h, 1.0) for h in range(-48, 200) if not (ba == "PACE" and h == 1)]
                         for ba in CORE})
    pol = CarbonSearch("H", None, holes, grid=GRID)
    with pytest.raises(ValueError, match="missing"):
        pol.predicted_kg(mkjob(), [Action("PACE", T0_US + 30 * MIN)], T0_US, "PACE")


def test_never_calls_forecast(monkeypatch):
    """L is fitted once upstream; the policy only reads the issued frame."""
    import gridpilot.forecast as fcmod

    def boom(*a, **k):
        raise AssertionError("forecast() called inside the policy")

    monkeypatch.setattr(fcmod, "forecast", boom)
    monkeypatch.setattr(fcmod, "predict", boom)
    pol = k_policy(lambda ba, h: 100.0 + h, signal="L")
    run(jobs_frame([{"job_uid": "x", "flexible": True}]), pol)


# --------------------------------------------------------------------------- invariants


@st.composite
def _workloads(draw):
    n = draw(st.integers(1, 25))
    rows = []
    for i in range(n):
        flexible = draw(st.booleans())
        rows.append({
            "job_uid": f"p{i:02d}",
            "at_min": 15 * draw(st.integers(0, 8)) + draw(st.sampled_from([0, 7])),
            "dur_s": draw(st.one_of(st.integers(1, 8).map(lambda k: 900.0 * k),
                                    st.integers(1, 9_000_000_000).map(lambda us: us / 1e6))),
            "gpus": draw(st.sampled_from([1, 2, 3, 4, 6, 8])),
            "flexible": flexible,
            "delay_h": draw(st.sampled_from([0.0, 0.25, 1.0, 6.0])) if flexible else 0.0,
            "mobile": flexible and draw(st.booleans()),
        })
    return jobs_frame(rows)


@settings(max_examples=40, deadline=None)
@given(_workloads(), st.booleans(), st.integers(0, 10_000))
def test_carbon_search_ledger_invariants(jobs, masked, seed):
    sites = {"PACE": 8, "CISO": 4, "BPAT": 6, "NEVP": 3}
    rng = np.random.default_rng(seed)
    table = {ba: rng.uniform(50, 800, 24 * 11) for ba in CORE}
    closed = {"BPAT": [(T0_US + HOUR, T0_US + 3 * HOUR)]} if masked else None
    b = u_bookings(jobs, sites, closed=closed)
    for pol in (h_policy(lambda ba, h: table[ba][h + 48]),
                k_policy(lambda ba, h: table[ba][(h * 5) % 200], signal="W")):
        led = simulate(jobs, pol, sites, bookings=b, closed=closed)
        assert sorted(led["job_uid"]) == sorted(jobs["job_uid"])
        j = led.join(jobs.select("job_uid", "mobile"), on="job_uid")
        assert (j["end_ts"] <= j["deadline_ts"]).all() and not j["late"].any()
        assert (j["start_ts"] >= j["arrival_ts"]).all()
        assert j.filter(~pl.col("mobile"))["site"].eq("PACE").all()
        for site, cap in sites.items():
            d = led.filter(pl.col("site") == site)
            if d.height:
                t = np.concatenate([d["start_ts"].dt.epoch("us"), d["end_ts"].dt.epoch("us")])
                g = np.concatenate([d["gpus"], -d["gpus"]])
                o = np.lexsort((g, t))
                assert np.cumsum(g[o]).max() <= cap
        if masked:
            bp = j.filter(pl.col("site") == "BPAT")
            lo, hi = T0 + timedelta(hours=1), T0 + timedelta(hours=3)
            assert not ((bp["start_ts"] < hi) & (bp["end_ts"] > lo)).any()
