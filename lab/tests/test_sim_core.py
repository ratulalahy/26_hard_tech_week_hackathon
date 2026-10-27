"""Simulator core: exact-interval capacity, F11 bookings, the ledger, and policies U/G/S.

Spec §8 "Core policy" and "Required comparison table"; §15 F1, F2, F3, F5, F10, F11.
The job frame is synthetic here, with the replay() columns of Task 3. Time is int µs.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gridpilot.sim import (
    LEDGER_COLUMNS,
    SITES,
    Action,
    Capacity,
    G,
    S,
    U,
    closed_intervals,
    simulate,
    u_bookings,
    warm_up,
)

T0 = datetime(2024, 11, 4, tzinfo=UTC)  # a Monday, inside validation
T0_US = int(T0.timestamp()) * 1_000_000
SEC = 1_000_000
MIN = 60 * SEC
HOUR = 60 * MIN
RANK = ["BPAT", "CISO", "NEVP"]


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
        "job_uid": pl.Utf8,
        "arrival_ts": pl.Datetime("us", "UTC"),
        "duration_s": pl.Float64,
        "gpus": pl.Int64,
        "job_type": pl.Utf8,
        "flexible": pl.Boolean,
        "max_delay_s": pl.Float64,
        "mobile": pl.Boolean,
    })


def run(jobs, policy, sites=SITES, **kw):
    """u_bookings + simulate, the F11 pairing every policy run uses."""
    warm = kw.pop("warm", None)
    bookings = u_bookings(jobs, sites, warm=warm)
    return simulate(jobs, policy, sites, bookings=bookings, warm=warm, **kw)


def row(ledger: pl.DataFrame, uid: str) -> dict:
    return ledger.filter(pl.col("job_uid") == uid).to_dicts()[0]


def minutes_after_t0(ts: datetime) -> float:
    return (ts - T0).total_seconds() / 60


# --------------------------------------------------------------------------- capacity


def test_gang_overlap_rejected():
    # 10 slots. A: 6 GPUs over [0, 90 min). B: 6 GPUs over [60, 120 min).
    # Hour [60, 120) has mean occupancy 6*0.5 + 6 = 9 <= 10, but the exact overlap is 12.
    cap = Capacity(10)
    cap.reserve(0, 90 * MIN, 6)
    assert cap.max_in(60 * MIN, 120 * MIN) == 6
    assert not cap.fits(60 * MIN, 120 * MIN, 6)
    with pytest.raises(ValueError):
        cap.reserve(60 * MIN, 120 * MIN, 6)
    # The earliest legal start for B is A's release instant, not 60 min.
    assert cap.earliest_start(60 * MIN, 60 * MIN, 6) == 90 * MIN
    # Touching half-open intervals do not overlap, to the microsecond.
    assert cap.fits(90 * MIN, 150 * MIN, 10)
    assert not cap.fits(90 * MIN - 1, 150 * MIN, 5)

    # Same case through the simulator: B starts at 90 min at PACE.
    sites = {"PACE": 10, "CISO": 0, "BPAT": 0, "NEVP": 0}
    jobs = jobs_frame([
        {"job_uid": "A", "at_min": 0, "dur_min": 90, "gpus": 6},
        {"job_uid": "B", "at_min": 60, "dur_min": 60, "gpus": 6},
    ])
    ledger = run(jobs, U(), sites)
    assert minutes_after_t0(row(ledger, "B")["start_ts"]) == 90


def _brute(resv: list[tuple[int, int, int]], t: int) -> int:
    return sum(g for s, e, g in resv if s <= t < e)


@settings(max_examples=300, deadline=None)
@given(
    st.lists(
        st.tuples(st.integers(0, 60), st.integers(1, 20), st.integers(1, 6), st.booleans()),
        max_size=40,
    ),
    st.integers(0, 70),
    st.integers(1, 25),
    st.integers(1, 8),
    st.one_of(st.none(), st.integers(0, 120)),
    st.integers(2, 5),
)
def test_capacity_matches_brute_force(ops, q_start, q_len, q_gpus, q_latest, chunk):
    """Reserve/release sequences on tiny chunks agree with a brute-force step function."""
    cap = Capacity(8, chunk=chunk)
    kept: list[tuple[int, int, int]] = []
    for s, length, g, drop in ops:
        e = s + length
        if drop and kept:  # release the oldest live reservation
            rs, re_, rg = kept.pop(0)
            cap.release(rs, re_, rg)
        elif cap.fits(s, e, g):
            cap.reserve(s, e, g)
            kept.append((s, e, g))
    qs, qe = q_start, q_start + q_len
    brute_max = max(_brute(kept, t) for t in range(qs, qe))
    assert cap.max_in(qs, qe) == brute_max
    assert cap.fits(qs, qe, q_gpus) == (brute_max + q_gpus <= 8)

    def ok(t):
        return all(_brute(kept, p) + q_gpus <= 8 for p in range(t, t + q_len))

    first = next(t for t in range(q_start, 300) if ok(t))
    expected = first if q_latest is None or first <= q_latest else None
    assert cap.earliest_start(qs, q_len, q_gpus, q_latest) == expected

    # The bulk builder gives the same answers.
    if kept:
        s_, e_, g_ = (np.array(x) for x in zip(*kept, strict=True))
        bulk = Capacity.from_intervals(8, s_, e_, g_, chunk=chunk)
        assert bulk.max_in(qs, qe) == brute_max
        assert bulk.earliest_start(qs, q_len, q_gpus, q_latest) == expected


@pytest.mark.parametrize("seed", range(6))
def test_capacity_random_stress(seed):
    """Many live reservations on 2-entry chunks: long ranges span many chunks, so the
    lazy per-chunk add, max and min paths are exercised against a brute-force array."""
    rng = np.random.default_rng(seed)
    horizon, slots = 400, 24
    cap = Capacity(slots, chunk=2)
    usage = np.zeros(horizon + 300, dtype=np.int64)
    live: list[tuple[int, int, int]] = []
    for _ in range(400):
        if live and rng.random() < 0.3:
            s, e, g = live.pop(int(rng.integers(len(live))))
            cap.release(s, e, g)
            usage[s:e] -= g
        else:
            s = int(rng.integers(0, horizon))
            e = s + int(rng.integers(1, 120))
            g = int(rng.integers(1, 5))
            if cap.fits(s, e, g):
                cap.reserve(s, e, g)
                usage[s:e] += g
                live.append((s, e, g))
            else:
                assert usage[s:e].max() + g > slots
        qs = int(rng.integers(0, horizon))
        ql = int(rng.integers(1, 150))
        qg = int(rng.integers(1, slots + 1))
        assert cap.max_in(qs, qs + ql) == usage[qs:qs + ql].max()
        free = [t for t in range(qs, horizon + 130) if usage[t:t + ql].max() + qg <= slots]
        assert cap.earliest_start(qs, ql, qg) == free[0]
    assert len(cap._T) > 50  # many chunks really were in play


def test_capacity_limits():
    cap = Capacity(4)
    assert cap.earliest_start(0, 10, 5) is None  # larger than the site: never fits
    cap.reserve(0, 100, 4)
    assert cap.earliest_start(0, 10, 1, latest=50) is None  # nothing by the latest start
    assert cap.earliest_start(0, 10, 1) == 100
    with pytest.raises(ValueError):
        cap.release(0, 200, 1)  # more than was reserved
    with pytest.raises(ValueError, match="slots"):
        Capacity.from_intervals(4, np.array([0, 5]), np.array([10, 20]), np.array([3, 2]))
    view = cap.view()
    assert view.fits(100, 200, 4) and view.slots == 4
    assert not hasattr(view, "reserve") and not hasattr(view, "release")


def test_advance_prunes_without_changing_answers():
    """Forgetting the past keeps every answer about the future, and refuses the past."""
    pruned, full = Capacity(16, chunk=4), Capacity(16, chunk=4)
    for k in range(3000):
        s, length, g = k, 7 + k % 5, 1 + k % 3
        for cap in (pruned, full):
            start = cap.earliest_start(s, length, g)
            cap.reserve(start, start + length, g)
        pruned.advance(k)
        assert pruned.max_in(k, k + 9) == full.max_in(k, k + 9)
        assert pruned.earliest_start(k, 4, 9) == full.earliest_start(k, 4, 9)
    assert pruned.n_breakpoints < full.n_breakpoints / 2  # the structure stays small
    with pytest.raises(ValueError, match="horizon"):
        pruned.max_in(0, 10)
    with pytest.raises(ValueError, match="backwards"):
        pruned.advance(0)


# --------------------------------------------------------------------------- F1/F11 bookings


def _overload_jobs() -> pl.DataFrame:
    # 8 PACE slots, 30 simultaneous and staggered arrivals of mixed sizes: heavy queueing.
    rows = []
    for i in range(30):
        rows.append({
            "job_uid": f"o{i:02d}#c0",
            "at_min": (i // 3) * 10,
            "dur_min": 30 + 15 * (i % 4),
            "gpus": [1, 2, 4, 8][i % 4],
            "flexible": i % 2 == 0,
            "delay_h": 1.0 if i % 2 == 0 else 0.0,
        })
    return jobs_frame(rows)


OVER_SITES = {"PACE": 8, "CISO": 4, "BPAT": 4, "NEVP": 4}


def test_u_bookings_are_f1_deadlines():
    jobs = _overload_jobs()
    b = u_bookings(jobs, OVER_SITES)
    assert b.columns == ["job_uid", "site", "start_us", "end_us", "deadline_us"]
    assert b.height == jobs.height and (b["site"] == "PACE").all()
    base = jobs.select(
        "job_uid",
        (pl.col("arrival_ts").dt.epoch("us")
         + ((pl.col("duration_s") + pl.col("max_delay_s")) * 1e6).cast(pl.Int64)).alias("base"),
    )
    chk = b.join(base, on="job_uid")
    # F1: deadline = max(declared deadline, U end), exactly, in integer µs.
    assert (chk["deadline_us"] == np.maximum(chk["base"], chk["end_us"])).all()
    assert (chk["end_us"] > chk["base"]).any()  # the workload really overloads PACE


def test_u_reproduces_its_bookings():
    jobs = _overload_jobs()
    b = u_bookings(jobs, OVER_SITES)
    ledger = simulate(jobs, U(), OVER_SITES, bookings=b)
    got = ledger.select(
        "job_uid", "site",
        pl.col("start_ts").dt.epoch("us").alias("start_us"),
        pl.col("end_ts").dt.epoch("us").alias("end_us"),
    )
    assert got.equals(b.select("job_uid", "site", "start_us", "end_us"))
    assert not ledger["moved"].any() and not ledger["late"].any()


def test_every_policy_on_time_under_bookings():
    jobs = _overload_jobs()
    b = u_bookings(jobs, OVER_SITES)
    for policy in (U(), G(), S(ranking=RANK)):
        ledger = simulate(jobs, policy, OVER_SITES, bookings=b)
        assert not ledger["late"].any(), policy.name
        assert (ledger["end_ts"] <= ledger["deadline_ts"]).all()
    g = simulate(jobs, G(), OVER_SITES, bookings=b)
    assert g["moved"].any() and g["transfer"].any()


def test_bookings_required_and_validated():
    jobs = _overload_jobs()
    b = u_bookings(jobs, OVER_SITES)
    with pytest.raises(TypeError):
        simulate(jobs, U(), OVER_SITES)  # bookings has no default
    with pytest.raises(ValueError, match="missing"):
        simulate(jobs, U(), OVER_SITES, bookings=b.head(10))
    extra = pl.concat([b, b.head(1).with_columns(pl.lit("ghost").alias("job_uid"))])
    with pytest.raises(ValueError, match="unknown"):
        simulate(jobs, U(), OVER_SITES, bookings=extra)


class _Prefer:
    """Proposes a fixed start offset at home (or None): exercises the booking fallback."""

    name = "prefer"

    def __init__(self, offset_min: float | None):
        self.offset = offset_min

    def choose(self, job, now, capacities, ctx):
        if self.offset is None or job.job_uid != "F":
            return None
        return Action(ctx.home, T0_US + int(self.offset * MIN))


def test_fallback_runs_on_booking():
    sites = {"PACE": 4, "CISO": 0, "BPAT": 0, "NEVP": 0}
    # F is booked at [0, 60); X (inflexible) arrives later and is booked at [400, 460).
    jobs = jobs_frame([
        {"job_uid": "F", "at_min": 0, "dur_min": 60, "gpus": 4, "flexible": True},
        {"job_uid": "X", "at_min": 400, "dur_min": 60, "gpus": 4},
    ])
    b = u_bookings(jobs, sites)
    # F prefers [360, 420): free now, but it overlaps X's future booking -> booking.
    led = simulate(jobs, _Prefer(360), sites, bookings=b)
    f = row(led, "F")
    assert minutes_after_t0(f["start_ts"]) == 0 and not f["moved"]
    assert f["blocked"]  # F12.7: the returned action was rejected for capacity
    # [300, 360) fits around X's booking and meets F's 7 h deadline -> moved.
    led = simulate(jobs, _Prefer(300), sites, bookings=b)
    assert minutes_after_t0(row(led, "F")["start_ts"]) == 300 and row(led, "F")["moved"]
    assert not led["blocked"].any()
    # A proposal that fits but is late (ends after 420 min), or None, also falls back,
    # but neither counts as reservation-blocked.
    for pref in (460, None):
        led = simulate(jobs, _Prefer(pref), sites, bookings=b)
        f = row(led, "F")
        assert minutes_after_t0(f["start_ts"]) == 0 and not f["moved"] and not f["blocked"]


# --------------------------------------------------------------------------- F3 mask


def test_mask_closes_destination():
    sites = {"PACE": 4, "CISO": 4, "BPAT": 4, "NEVP": 4}
    jobs = jobs_frame([
        {"job_uid": "blocker", "at_min": 0, "dur_min": 600, "gpus": 4},
        {"job_uid": "x", "at_min": 1, "dur_min": 60, "gpus": 2, "flexible": True},
    ])
    b = u_bookings(jobs, sites)
    # BPAT is closed for an hour touching x's first remote start; CISO all day.
    closed = {"BPAT": [(T0_US + 60 * MIN, T0_US + 2 * HOUR)], "CISO": [(T0_US, T0_US + 24 * HOUR)]}
    led = simulate(jobs, G(), sites, bookings=b, closed=closed)
    r = row(led, "x")
    # Starting at 31 min ends at 91 min, inside BPAT's closure; NEVP is open at 31 min.
    assert (r["site"], minutes_after_t0(r["start_ts"])) == ("NEVP", 31)
    # Close NEVP too: BPAT reopens at 120 min, the earliest open finish.
    closed["NEVP"] = [(T0_US, T0_US + 24 * HOUR)]
    r = row(simulate(jobs, G(), sites, bookings=b, closed=closed), "x")
    assert (r["site"], minutes_after_t0(r["start_ts"])) == ("BPAT", 120)
    # The engine rejects a masked action outright.
    with pytest.raises(ValueError, match="closed"):
        simulate(jobs, _At("CISO", 31, uid="x"), sites, bookings=b, closed=closed)


def test_remote_move_needs_arrival_hour_support():
    """F12.1: a remote move charges transfer energy in the arrival hour at both ends,
    so that hour must have truth at home and at the destination."""
    sites = {"PACE": 4, "CISO": 4, "BPAT": 4, "NEVP": 4}
    jobs = jobs_frame([
        {"job_uid": "blocker", "at_min": 0, "dur_min": 600, "gpus": 4},
        {"job_uid": "x", "at_min": 50, "dur_min": 60, "gpus": 2, "flexible": True},
    ])
    b = u_bookings(jobs, sites)
    r = row(simulate(jobs, G(), sites, bookings=b), "x")
    assert (r["site"], minutes_after_t0(r["start_ts"])) == ("BPAT", 80)
    # BPAT's arrival hour [0, 60) is closed; its execution hours [80, 140) are open.
    closed = {"BPAT": [(T0_US, T0_US + HOUR)]}
    r = row(simulate(jobs, G(), sites, bookings=b, closed=closed), "x")
    assert (r["site"], minutes_after_t0(r["start_ts"])) == ("CISO", 80)
    # Home's arrival hour closed: no remote move at all, so x runs on its PACE booking.
    closed = {"PACE": [(T0_US, T0_US + HOUR)]}
    r = row(simulate(jobs, G(), sites, bookings=b, closed=closed), "x")
    assert r["site"] == "PACE" and not r["moved"]
    with pytest.raises(ValueError, match="arrival hour"):
        simulate(jobs, _At("CISO", 80, uid="x"), sites, bookings=b, closed=closed)


def test_bookings_exempt_from_mask():
    sites = {"PACE": 4, "CISO": 0, "BPAT": 0, "NEVP": 0}
    jobs = jobs_frame([{"job_uid": "r", "at_min": 0, "dur_min": 60, "gpus": 4}])
    b = u_bookings(jobs, sites)
    closed = {"PACE": [(T0_US, T0_US + HOUR)]}
    r = row(simulate(jobs, G(), sites, bookings=b, closed=closed), "r")
    assert r["site"] == "PACE" and minutes_after_t0(r["start_ts"]) == 0 and not r["moved"]


def test_closed_intervals_from_site_mask():
    mask = pl.DataFrame({
        "ba": ["BPAT"] * 4 + ["CISO"] * 2,
        "ts_utc": [T0 + timedelta(hours=h) for h in (0, 1, 2, 3)]
        + [T0 + timedelta(hours=h) for h in (0, 1)],
        "truth_ok": [True, False, False, True, True, True],
    }).with_columns(pl.col("ts_utc").dt.cast_time_unit("us"))
    assert closed_intervals(mask) == {"BPAT": [(T0_US + HOUR, T0_US + 3 * HOUR)]}


# --------------------------------------------------------------------------- policies


def test_tie_break_order():
    sites = {"PACE": 4, "CISO": 4, "BPAT": 4, "NEVP": 4}
    # PACE is busy for exactly the 30-min transfer, so all four sites finish together.
    jobs = jobs_frame([
        {"job_uid": "blocker", "at_min": 0, "dur_min": 30, "gpus": 4},
        {"job_uid": "x", "at_min": 0, "dur_min": 60, "gpus": 4, "flexible": True},
    ])
    r = row(run(jobs, G(), sites), "x")
    assert (r["site"], minutes_after_t0(r["start_ts"]), r["moved"]) == ("PACE", 30, False)

    # PACE busy for longer: the three remote sites tie, and lexical BA code wins.
    jobs = jobs_frame([
        {"job_uid": "blocker", "at_min": 0, "dur_min": 300, "gpus": 4},
        {"job_uid": "x", "at_min": 0, "dur_min": 60, "gpus": 4, "flexible": True},
    ])
    r = row(run(jobs, G(), sites), "x")
    assert (r["site"], minutes_after_t0(r["start_ts"]), r["transfer"]) == ("BPAT", 30, True)
    assert r["moved"] and r["booking_site"] == "PACE"

    # Simultaneous arrivals: earlier declared deadline first, then job_uid.
    sites1 = {"PACE": 4, "CISO": 0, "BPAT": 0, "NEVP": 0}
    jobs = jobs_frame([
        {"job_uid": "b", "at_min": 0, "dur_min": 60, "gpus": 4},
        {"job_uid": "a", "at_min": 0, "dur_min": 60, "gpus": 4},
        {"job_uid": "c", "at_min": 0, "dur_min": 30, "gpus": 4},  # earliest deadline
    ])
    ledger = run(jobs, U(), sites1)
    assert ledger.sort("start_ts")["job_uid"].to_list() == ["c", "a", "b"]
    # Determinism: the same input in a different row order gives the same ledger.
    again = run(jobs.reverse(), U(), sites1)
    assert again.sort("job_uid").equals(ledger.sort("job_uid"))


def test_s_ranking_then_home():
    sites = {"PACE": 4, "CISO": 4, "BPAT": 4, "NEVP": 4}
    with pytest.raises(TypeError):
        S()  # the ranking is required
    jobs = jobs_frame([
        {"job_uid": f"f{i}", "at_min": 0, "dur_min": 60, "gpus": 4, "flexible": True}
        for i in range(4)
    ] + [{"job_uid": "rigid", "at_min": 0, "dur_min": 60, "gpus": 1}])
    ledger = run(jobs, S(ranking=["NEVP", "BPAT", "CISO"]), sites)
    # S takes its first-ranked site and queues there while the deadline still holds.
    assert {row(ledger, f"f{i}")["site"] for i in range(4)} == {"NEVP"}
    assert row(ledger, "rigid")["site"] == "PACE"

    # A mobile job with no slack cannot afford the transfer: S falls back to home.
    jobs = jobs_frame([{"job_uid": "m", "dur_min": 60, "gpus": 4, "flexible": True,
                        "delay_h": 0.0}])
    r = row(run(jobs, S(ranking=["NEVP", "BPAT", "CISO"]), sites), "m")
    assert (r["site"], minutes_after_t0(r["start_ts"])) == ("PACE", 0)

    # Slack for exactly one ranked site: 4 jobs, 45 min of slack, PACE booked in a queue.
    jobs = jobs_frame([
        {"job_uid": f"t{i}", "at_min": 0, "dur_min": 60, "gpus": 4, "flexible": True,
         "delay_h": 0.75}
        for i in range(4)
    ])
    ledger = run(jobs, S(ranking=["NEVP", "BPAT", "CISO"]), sites)
    # t0 (deadline 105 min) -> NEVP [30, 90); t1 (deadline = booking end 120) cannot
    # finish at NEVP by 120 (90 + 60 = 150), so BPAT; t2, t3 (deadlines 180, 240) fit
    # back at NEVP after t0.
    assert [row(ledger, f"t{i}")["site"] for i in range(4)] == ["NEVP", "BPAT", "NEVP", "NEVP"]
    assert not ledger["late"].any()


def test_immobile_jobs_stay_home():
    sites = {"PACE": 4, "CISO": 4, "BPAT": 4, "NEVP": 4}
    jobs = jobs_frame([
        {"job_uid": "blocker", "at_min": 0, "dur_min": 300, "gpus": 4},
        {"job_uid": "rigid", "at_min": 1, "dur_min": 60, "gpus": 4},
    ])
    for policy in (U(), G(), S(ranking=RANK)):
        r = row(run(jobs, policy, sites), "rigid")
        assert r["site"] == "PACE" and not r["transfer"], policy.name
        assert minutes_after_t0(r["start_ts"]) == 300


def test_remote_transfer_delay():
    sites = {"PACE": 4, "CISO": 4, "BPAT": 4, "NEVP": 4}
    jobs = jobs_frame([
        {"job_uid": "blocker", "at_min": 0, "dur_min": 600, "gpus": 4},
        {"job_uid": "x", "at_min": 5, "dur_min": 60, "gpus": 2, "flexible": True},
    ])
    arrival = T0 + timedelta(minutes=5)
    for policy in (G(), S(ranking=RANK)):
        r = row(run(jobs, policy, sites), "x")
        assert r["site"] != "PACE" and r["transfer"], policy.name
        assert r["start_ts"] == arrival + timedelta(seconds=1800)  # remote site is empty
    # The transfer time is a parameter (sensitivity 0 and 120 min).
    r = row(run(jobs, G(), sites, transfer_s=7200.0), "x")
    assert r["start_ts"] == arrival + timedelta(seconds=7200)


class _At:
    """Starts at `site`, `at_min` after T0, regardless of legality."""

    name = "at"

    def __init__(self, site: str, at_min: float, uid: str | None = None):
        self.site, self.at, self.uid = site, at_min, uid

    def choose(self, job, now, capacities, ctx):
        if self.uid is not None and job.job_uid != self.uid:
            return None
        return Action(self.site, T0_US + int(self.at * MIN))


def test_illegal_action_raises():
    jobs = jobs_frame([{"job_uid": "x", "gpus": 1, "flexible": True}])
    with pytest.raises(ValueError, match="transfer"):
        run(jobs, _At("BPAT", 0))  # remote start on arrival skips the transfer
    with pytest.raises(ValueError, match="legal"):
        run(jobs_frame([{"job_uid": "r", "gpus": 1}]), _At("BPAT", 60))  # immobile job


def test_policies_get_read_only_views():
    seen = {}

    class Spy:
        name = "spy"

        def choose(self, job, now, capacities, ctx):
            seen.update(capacities)

    run(jobs_frame([{"job_uid": "a"}]), Spy())
    assert seen and all(not hasattr(v, "reserve") for v in seen.values())


# --------------------------------------------------------------------------- warm-up


def test_warmup_carries_reservations():
    warm = warm_up(jobs_frame([{"job_uid": "w0", "at_min": -60, "dur_min": 120, "gpus": 8}]),
                   OVER_SITES)
    jobs = _overload_jobs()
    b = u_bookings(jobs, OVER_SITES, warm=warm)
    ledger = simulate(jobs, G(), OVER_SITES, bookings=b, warm=warm)
    # The warm-up job holds all 8 PACE slots until T0 + 60 min.
    pace = ledger.filter(pl.col("site") == "PACE")
    assert pace["start_ts"].min() >= T0 + timedelta(minutes=60)
    assert not ledger["late"].any()
    # The warm-up is reusable, and a run may not start before its last arrival.
    assert simulate(jobs, G(), OVER_SITES, bookings=b, warm=warm).equals(ledger)
    early = jobs_frame([{"job_uid": "e", "at_min": -90}])
    with pytest.raises(ValueError, match="warm-up"):
        u_bookings(early, OVER_SITES, warm=warm)


# --------------------------------------------------------------------------- contract


def test_ledger_schema_and_sites():
    assert SITES == {"PACE": 2288, "CISO": 512, "BPAT": 512, "NEVP": 512}
    jobs = jobs_frame([
        {"job_uid": "a", "at_min": 0, "gpus": 8, "flexible": True, "dur_s": 3600.25},
        {"job_uid": "b", "at_min": 3, "gpus": 1},
    ])
    ledger = run(jobs, G())
    assert ledger.columns == LEDGER_COLUMNS == [
        "job_uid", "site", "start_ts", "end_ts", "transfer", "late", "deadline_ts", "gpus",
        "arrival_ts", "duration_s", "moved", "booking_site", "blocked",
    ]
    for c in ("start_ts", "end_ts", "deadline_ts", "arrival_ts"):
        assert ledger.schema[c] == pl.Datetime("us", "UTC")
    for c in ("transfer", "late", "moved", "blocked"):
        assert ledger.schema[c] == pl.Boolean
    assert ledger.schema["gpus"] == pl.Int64
    a = row(ledger, "a")
    assert a["duration_s"] == 3600.25  # exact, from the input
    assert a["end_ts"] - a["start_ts"] == timedelta(seconds=3600.25)
    # Declared deadline (PACE is empty, so U's finish is earlier): arrival + duration + 6 h.
    assert a["deadline_ts"] == T0 + timedelta(hours=7, seconds=0.25)


def test_input_validation(caplog):
    good = jobs_frame([{"job_uid": "a"}, {"job_uid": "b", "mobile": True}])
    with caplog.at_level(logging.INFO, logger="gridpilot.sim.engine"):
        u_bookings(good, OVER_SITES)
    assert "1 rows are mobile but not flexible" in caplog.text
    with pytest.raises(ValueError, match="mobile"):
        u_bookings(good.drop("mobile"), OVER_SITES)
    with pytest.raises(ValueError, match="finite"):
        u_bookings(good.with_columns(pl.lit(float("inf")).alias("duration_s")), OVER_SITES)
    with pytest.raises(ValueError, match="integral"):
        u_bookings(good.with_columns(pl.lit(1.5).alias("gpus")), OVER_SITES)
    # Integral floats are fine (replay() gives ints, but be lenient on dtype).
    u_bookings(good.with_columns(pl.col("gpus").cast(pl.Float64)), OVER_SITES)
    with pytest.raises(ValueError, match="huge"):
        u_bookings(jobs_frame([{"job_uid": "huge", "gpus": 9}]), OVER_SITES)


# --------------------------------------------------------------------------- ledger invariant


@st.composite
def _workloads(draw):
    n = draw(st.integers(1, 30))
    rows = []
    for i in range(n):
        flexible = draw(st.booleans())
        rows.append({
            "job_uid": f"p{i:02d}",
            # Arrivals on a 15-min grid (many simultaneous); durations in µs-exact
            # fractional seconds, often whole multiples of 15 min so ends equal starts.
            "at_min": 15 * draw(st.integers(0, 8)),
            "dur_s": draw(st.one_of(
                st.integers(1, 8).map(lambda k: 900.0 * k),
                st.integers(1, 5_400_000_000).map(lambda us: us / 1e6),
            )),
            "gpus": draw(st.sampled_from([1, 2, 3, 4, 6, 8])),
            "flexible": flexible,
            "delay_h": draw(st.sampled_from([0.0, 0.25, 1.0, 6.0])) if flexible else 0.0,
            "mobile": flexible and draw(st.booleans()),
        })
    return jobs_frame(rows)


def _sweep_ok(ledger: pl.DataFrame, sites: dict[str, int]) -> None:
    for site, cap in sites.items():
        d = ledger.filter(pl.col("site") == site)
        if d.height == 0:
            continue
        s = d["start_ts"].dt.epoch("us").to_numpy()
        e = d["end_ts"].dt.epoch("us").to_numpy()
        g = d["gpus"].to_numpy()
        t = np.concatenate([s, e])
        dg = np.concatenate([g, -g])
        order = np.lexsort((dg, t))  # at equal times, ends (negative) before starts
        assert np.cumsum(dg[order]).max() <= cap, site


@settings(max_examples=150, deadline=None)
@given(_workloads(), st.booleans())
def test_ledger_invariants(jobs, masked):
    sites = {"PACE": 8, "CISO": 4, "BPAT": 6, "NEVP": 3}
    closed = {"BPAT": [(T0_US + HOUR, T0_US + 3 * HOUR)]} if masked else None
    bookings = u_bookings(jobs, sites)
    for policy in (U(), G(), S(ranking=["NEVP", "BPAT", "CISO"])):
        ledger = simulate(jobs, policy, sites, bookings=bookings, closed=closed)
        assert sorted(ledger["job_uid"]) == sorted(jobs["job_uid"])  # each job exactly once
        _sweep_ok(ledger, sites)
        j = ledger.join(jobs.select("job_uid", "mobile"), on="job_uid")
        assert (j["end_ts"] <= j["deadline_ts"]).all() and not j["late"].any()
        assert (j["start_ts"] >= j["arrival_ts"]).all()
        assert j.filter(~pl.col("mobile"))["site"].eq("PACE").all()
        remote = j.filter(pl.col("site") != "PACE")
        assert remote.select(
            (pl.col("start_ts") >= pl.col("arrival_ts") + pl.duration(seconds=1800)).all()
        ).item()
        if masked:  # no BPAT execution touches the closed window
            bp = j.filter(pl.col("site") == "BPAT")
            lo, hi = T0 + timedelta(hours=1), T0 + timedelta(hours=3)
            assert not ((bp["start_ts"] < hi) & (bp["end_ts"] > lo)).any()
            # F12.1: nor does a move to BPAT arrive inside it (transfer charged there).
            assert not ((bp["arrival_ts"] >= lo) & (bp["arrival_ts"] < hi)).any()
        if policy.name == "U":
            assert not ledger["moved"].any()


# --------------------------------------------------------------------------- hardening (Task 5)


def test_closed_must_be_hour_aligned():
    """M1: closures are whole UTC hours (F3, F14.5)."""
    jobs = jobs_frame([{"job_uid": "x", "flexible": True}])
    b = u_bookings(jobs)
    with pytest.raises(ValueError, match="hour-aligned"):
        simulate(jobs, G(), bookings=b, closed={"BPAT": [(T0_US + MIN, T0_US + HOUR)]})
    with pytest.raises(ValueError, match="hour-aligned"):
        u_bookings(jobs, closed={"PACE": [(T0_US, T0_US + 90 * MIN)]})


def test_transfer_hour_is_the_utc_hour_of_arrival():
    """F12.1/F14.5: the transfer charge sits in [floor_hour(arrival), +1 h)."""
    sites = {"PACE": 4, "CISO": 0, "BPAT": 4, "NEVP": 0}
    jobs = jobs_frame([
        {"job_uid": "blocker", "at_min": 0, "dur_min": 600, "gpus": 4},
        {"job_uid": "x", "at_min": 59, "dur_min": 60, "gpus": 2, "flexible": True},
    ])
    b = u_bookings(jobs, sites)
    closed = {"BPAT": [(T0_US, T0_US + HOUR)]}  # x arrives at 0:59, inside this hour
    r = row(simulate(jobs, G(), sites, bookings=b, closed=closed), "x")
    assert r["site"] == "PACE" and not r["moved"]
    closed = {"BPAT": [(T0_US + HOUR, T0_US + 2 * HOUR)]}  # x's execution [89, 149) touches it
    r = row(simulate(jobs, G(), sites, bookings=b, closed=closed), "x")
    assert (r["site"], minutes_after_t0(r["start_ts"])) == ("BPAT", 120)


def test_bookings_checked_for_deadline_and_site():
    """M3: a booking's deadline is max(arrival + duration + delay, end), and its site
    is legal for the job."""
    jobs = jobs_frame([{"job_uid": "a", "at_min": 0, "gpus": 2},
                       {"job_uid": "f", "at_min": 5, "gpus": 2, "flexible": True}])
    b = u_bookings(jobs, OVER_SITES)
    simulate(jobs, U(), OVER_SITES, bookings=b)
    longer = b.with_columns(pl.when(pl.col("job_uid") == "a").then(pl.col("deadline_us") + 1)
                            .otherwise(pl.col("deadline_us")).alias("deadline_us"))
    with pytest.raises(ValueError, match="deadline"):
        simulate(jobs, U(), OVER_SITES, bookings=longer)
    remote = b.with_columns(pl.when(pl.col("job_uid") == "a").then(pl.lit("BPAT"))
                            .otherwise(pl.col("site")).alias("site"))
    with pytest.raises(ValueError, match="legal"):
        simulate(jobs, U(), OVER_SITES, bookings=remote)  # an immobile job off home
    tiny = {"PACE": 8, "CISO": 1, "BPAT": 4, "NEVP": 4}
    b2 = u_bookings(jobs, tiny).with_columns(
        pl.when(pl.col("job_uid") == "f").then(pl.lit("CISO")).otherwise(pl.col("site"))
        .alias("site"))
    with pytest.raises(ValueError, match="legal"):
        simulate(jobs, U(), tiny, bookings=b2)  # 2 GPUs on a 1-slot site


def test_u_bookings_respect_closed():
    """M5: u_bookings takes the run's `closed`, so U reproduces its bookings under a mask."""
    sites = {"PACE": 4, "CISO": 0, "BPAT": 0, "NEVP": 0}
    jobs = jobs_frame([{"job_uid": "r", "at_min": 10, "dur_min": 30, "gpus": 2},
                       {"job_uid": "s", "at_min": 70, "dur_min": 30, "gpus": 2}])
    closed = {"PACE": [(T0_US, T0_US + HOUR)]}
    b = u_bookings(jobs, sites, closed=closed)
    assert b.filter(pl.col("job_uid") == "r")["start_us"].item() == T0_US + HOUR
    led = simulate(jobs, U(), sites, bookings=b, closed=closed)
    got = led.select("job_uid", pl.col("start_ts").dt.epoch("us").alias("start_us"))
    assert got.equals(b.select("job_uid", "start_us")) and not led["moved"].any()


def test_view_hides_capacity():
    """M2: a policy's view exposes no path to the mutable Capacity."""
    cap = Capacity(4)
    v = cap.view()
    for name in ("reserve", "release", "_c", "_range_add", "advance"):
        assert not hasattr(v, name), name
    for name in dir(v):
        obj = getattr(v, name)
        assert not isinstance(obj, Capacity), name
        assert not isinstance(getattr(obj, "__self__", None), Capacity), name
    with pytest.raises(AttributeError):
        v.fits = None
    assert v.fits(0, 10, 4) and v.slots == 4 and v.max_in(0, 10) == 0
    cap.reserve(0, 10, 3)
    assert v.max_in(0, 10) == 3 and v.earliest_start(0, 10, 2) == 10
    cap.advance(5)
    assert v.horizon == 5
