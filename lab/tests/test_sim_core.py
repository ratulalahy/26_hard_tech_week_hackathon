"""Simulator core: exact-interval capacity, the reservation ledger, and policies U/G/S.

Spec §8 "Core policy" and "Required comparison table"; §15 F1, F2, F5, F10.
The job frame is synthetic here, with the replay() columns of Task 3.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gridpilot.sim import (
    SITES,
    Action,
    Capacity,
    G,
    S,
    U,
    simulate,
    u_finish_deadlines,
    warm_up,
)

T0 = datetime(2024, 11, 4, tzinfo=UTC)  # a Monday, inside validation
MIN = 60.0
HOUR = 3600.0

LEDGER_COLUMNS = [
    "job_uid", "site", "start_ts", "end_ts", "transfer", "late", "deadline_ts", "gpus",
]


def jobs_frame(rows: list[dict]) -> pl.DataFrame:
    """Synthetic replay() frame. `at_min` is the arrival offset from T0 in minutes."""
    out = []
    for i, r in enumerate(rows):
        flexible = r.get("flexible", False)
        out.append({
            "job_uid": r.get("job_uid", f"j{i:03d}#c0"),
            "arrival_ts": T0 + timedelta(minutes=r.get("at_min", 0.0)),
            "duration_s": float(r.get("dur_min", 60.0) * MIN),
            "gpus": int(r.get("gpus", 1)),
            "job_type": r.get("job_type", "SFT" if flexible else "Other"),
            "flexible": flexible,
            "max_delay_s": float(r.get("delay_h", 6.0 if flexible else 0.0) * HOUR),
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


def row(ledger: pl.DataFrame, uid: str) -> dict:
    return ledger.filter(pl.col("job_uid") == uid).to_dicts()[0]


def minutes_after_t0(ts: datetime) -> float:
    return (ts - T0).total_seconds() / MIN


# --------------------------------------------------------------------------- capacity


def test_gang_overlap_rejected():
    # 10 slots. A: 6 GPUs over [0, 90 min). B: 6 GPUs over [60, 120 min).
    # Hour [60, 120) has mean occupancy 6*0.5 + 6 = 9 <= 10, but the exact overlap is 12.
    cap = Capacity(10)
    cap.reserve(0.0, 90 * MIN, 6)
    assert cap.max_in(60 * MIN, 120 * MIN) == 6
    assert not cap.fits(60 * MIN, 120 * MIN, 6)
    with pytest.raises(ValueError):
        cap.reserve(60 * MIN, 120 * MIN, 6)
    # The earliest legal start for B is A's release instant, not 60 min.
    assert cap.earliest_start(60 * MIN, 60 * MIN, 6) == 90 * MIN
    # Touching half-open intervals do not overlap.
    assert cap.fits(90 * MIN, 150 * MIN, 10)

    # Same case through the simulator: B starts at 90 min at PACE.
    sites = {"PACE": 10, "CISO": 0, "BPAT": 0, "NEVP": 0}
    jobs = jobs_frame([
        {"job_uid": "A", "at_min": 0, "dur_min": 90, "gpus": 6},
        {"job_uid": "B", "at_min": 60, "dur_min": 60, "gpus": 6},
    ])
    ledger = simulate(jobs, U(), sites=sites)
    assert minutes_after_t0(row(ledger, "B")["start_ts"]) == 90
    assert row(ledger, "B")["late"]  # B had zero allowed delay


def _brute_usage(resv: list[tuple[float, float, int]], t: float) -> int:
    return sum(g for s, e, g in resv if s <= t < e)


@settings(max_examples=200, deadline=None)
@given(
    st.lists(
        st.tuples(st.integers(0, 40), st.integers(1, 15), st.integers(1, 6)),
        max_size=25,
    ),
    st.integers(0, 50),
    st.integers(1, 20),
    st.integers(1, 8),
)
def test_capacity_matches_brute_force(resv, q_start, q_len, q_gpus):
    """max_in, fits and earliest_start agree with a brute-force scan of the step function."""
    cap = Capacity(8)
    kept: list[tuple[float, float, int]] = []
    for s, length, g in resv:
        s, e = float(s), float(s + length)
        if cap.fits(s, e, g):
            cap.reserve(s, e, g)
            kept.append((s, e, g))
    # Every instant where usage can change is an integer here, so test the midpoints too.
    qs, qe = float(q_start), float(q_start + q_len)
    probes = [qs + k / 2 for k in range(int(2 * (qe - qs)))]
    brute_max = max(_brute_usage(kept, t) for t in probes)
    assert cap.max_in(qs, qe) == brute_max
    assert cap.fits(qs, qe, q_gpus) == (brute_max + q_gpus <= 8)

    # Earliest start >= qs: the true answer is qs or a release instant (an integer).
    def ok(t):
        return all(_brute_usage(kept, p) + q_gpus <= 8 for p in
                   [t + k / 2 for k in range(int(2 * q_len))])

    expected = next(float(t) for t in range(q_start, 200) if ok(float(t)))
    assert cap.earliest_start(qs, float(q_len), q_gpus) == expected


def test_capacity_limits():
    cap = Capacity(4)
    assert cap.earliest_start(0.0, 10.0, 5) is None  # larger than the site: never fits
    cap.reserve(0.0, 100.0, 4)
    assert cap.earliest_start(0.0, 10.0, 1, latest=50.0) is None  # nothing by the latest start
    assert cap.earliest_start(0.0, 10.0, 1) == 100.0
    copy = cap.copy()
    copy.reserve(100.0, 200.0, 4)
    assert cap.fits(100.0, 200.0, 4)  # the copy is independent
    assert not copy.fits(100.0, 200.0, 1)


def test_advance_prunes_without_changing_answers():
    """Forgetting the past keeps every answer about the future, and refuses the past."""
    pruned, full = Capacity(16), Capacity(16)
    for k in range(3000):
        s, e, g = float(k), float(k + 7 + k % 5), 1 + k % 3
        for cap in (pruned, full):
            start = cap.earliest_start(s, e - s, g)
            cap.reserve(start, start + (e - s), g)
        pruned.advance(float(k))
        q = float(k)
        assert pruned.max_in(q, q + 9) == full.max_in(q, q + 9)
        assert pruned.earliest_start(q, 4.0, 9) == full.earliest_start(q, 4.0, 9)
    assert len(pruned._t) < len(full._t) / 2  # the structure stays small
    with pytest.raises(ValueError, match="horizon"):
        pruned.max_in(0.0, 10.0)
    with pytest.raises(ValueError, match="backwards"):
        pruned.advance(0.0)


# --------------------------------------------------------------------------- F1 deadlines


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


def test_u_feasible_with_f1():
    sites = {"PACE": 8, "CISO": 4, "BPAT": 4, "NEVP": 4}
    jobs = _overload_jobs()
    plain = simulate(jobs, U(), sites=sites)
    assert plain["late"].sum() > 0  # the synthetic workload really overloads PACE

    deadlines = u_finish_deadlines(jobs, sites=sites)
    assert deadlines.columns == ["job_uid", "deadline_ts"]
    assert deadlines.height == jobs.height
    ledger = simulate(jobs, U(), sites=sites, deadlines=deadlines)
    assert ledger["late"].sum() == 0
    assert (ledger["site"] == "PACE").all()
    # F1: the deadline is the later of the declared deadline and the U finish.
    base = jobs.select(
        "job_uid",
        (pl.col("arrival_ts") + pl.duration(
            microseconds=((pl.col("duration_s") + pl.col("max_delay_s")) * 1e6).cast(pl.Int64)
        )).alias("base"),
    )
    chk = deadlines.join(base, on="job_uid").join(ledger.select("job_uid", "end_ts"), on="job_uid")
    assert (chk["deadline_ts"] >= chk["base"]).all()
    assert (chk["deadline_ts"] >= chk["end_ts"]).all()
    # Either bound is tight: the deadline is exactly one of them (to the microsecond).
    tight = (chk["deadline_ts"] == chk["base"]) | (chk["deadline_ts"] == chk["end_ts"])
    assert tight.all()


def test_f1_deadlines_with_warmup():
    sites = {"PACE": 8, "CISO": 4, "BPAT": 4, "NEVP": 4}
    warm = jobs_frame([{"job_uid": "w0", "at_min": -60, "dur_min": 120, "gpus": 8}])
    state = warm_up(warm, sites=sites)
    jobs = _overload_jobs()
    deadlines = u_finish_deadlines(jobs, sites=sites, warmup_state=state)
    ledger = simulate(jobs, U(), sites=sites, deadlines=deadlines, warmup_state=state)
    assert ledger["late"].sum() == 0
    # The warm-up job holds all 8 slots until T0 + 60 min, so nothing starts earlier.
    assert ledger["start_ts"].min() >= T0 + timedelta(minutes=60)
    # The warm-up state is not consumed by a run.
    again = simulate(jobs, U(), sites=sites, deadlines=deadlines, warmup_state=state)
    assert again.equals(ledger)


# --------------------------------------------------------------------------- late queue


def test_late_queue_never_drops():
    sites = {"PACE": 8, "CISO": 8, "BPAT": 8, "NEVP": 8}
    jobs = jobs_frame([
        # Fills every site for 10 hours.
        {"job_uid": "big-pace", "at_min": 0, "dur_min": 600, "gpus": 8},
        {"job_uid": "big-ciso", "at_min": 0, "dur_min": 600, "gpus": 8, "flexible": True},
        {"job_uid": "big-bpat", "at_min": 0, "dur_min": 600, "gpus": 8, "flexible": True},
        {"job_uid": "big-nevp", "at_min": 0, "dur_min": 600, "gpus": 8, "flexible": True},
        # Impossible: needs to finish within 1 h + 1 h of slack, everything is busy.
        {"job_uid": "late-flex", "at_min": 1, "dur_min": 60, "gpus": 4, "flexible": True,
         "delay_h": 1.0},
        {"job_uid": "late-rigid", "at_min": 2, "dur_min": 30, "gpus": 2},
    ])
    requested = (jobs["duration_s"] * jobs["gpus"]).sum()
    for policy in (U(), G(), S(ranking=["BPAT", "CISO", "NEVP"])):
        ledger = simulate(jobs, policy, sites=sites)
        assert ledger.height == jobs.height, policy.name
        assert set(ledger["job_uid"]) == set(jobs["job_uid"])
        for uid in ("late-flex", "late-rigid"):
            r = row(ledger, uid)
            assert r["late"], (policy.name, uid)
            assert r["end_ts"] > r["deadline_ts"]
            assert r["start_ts"] >= T0 + timedelta(minutes=600)  # earliest legal start
        done = ledger.select(
            ((pl.col("end_ts") - pl.col("start_ts")).dt.total_microseconds() / 1e6
             * pl.col("gpus")).sum()
        ).item()
        assert done == pytest.approx(requested, abs=1e-3)
        # The rigid job never leaves home.
        assert row(ledger, "late-rigid")["site"] == "PACE"


def test_oversize_job_raises():
    sites = {"PACE": 8, "CISO": 4, "BPAT": 4, "NEVP": 4}
    jobs = jobs_frame([{"job_uid": "huge", "gpus": 9, "flexible": True}])
    with pytest.raises(ValueError, match="huge"):
        simulate(jobs, G(), sites=sites)


# --------------------------------------------------------------------------- tie breaks


def test_tie_break_order():
    sites = {"PACE": 4, "CISO": 4, "BPAT": 4, "NEVP": 4}
    # PACE is busy for exactly the 30-min transfer, so all four sites finish together.
    jobs = jobs_frame([
        {"job_uid": "blocker", "at_min": 0, "dur_min": 30, "gpus": 4},
        {"job_uid": "x", "at_min": 0, "dur_min": 60, "gpus": 4, "flexible": True},
    ])
    ledger = simulate(jobs, G(), sites=sites)
    assert row(ledger, "x")["site"] == "PACE"  # equal finish: home first
    assert minutes_after_t0(row(ledger, "x")["start_ts"]) == 30

    # PACE busy for longer: the three remote sites tie, and lexical BA code wins.
    jobs = jobs_frame([
        {"job_uid": "blocker", "at_min": 0, "dur_min": 300, "gpus": 4},
        {"job_uid": "x", "at_min": 0, "dur_min": 60, "gpus": 4, "flexible": True},
    ])
    r = row(simulate(jobs, G(), sites=sites), "x")
    assert (r["site"], minutes_after_t0(r["start_ts"]), r["transfer"]) == ("BPAT", 30, True)

    # Simultaneous arrivals: earlier declared deadline first, then job_uid.
    sites1 = {"PACE": 4, "CISO": 0, "BPAT": 0, "NEVP": 0}
    jobs = jobs_frame([
        {"job_uid": "b", "at_min": 0, "dur_min": 60, "gpus": 4},
        {"job_uid": "a", "at_min": 0, "dur_min": 60, "gpus": 4},
        {"job_uid": "c", "at_min": 0, "dur_min": 30, "gpus": 4},  # earliest deadline
    ])
    ledger = simulate(jobs, U(), sites=sites1)
    order = ledger.sort("start_ts")["job_uid"].to_list()
    assert order == ["c", "a", "b"]
    # Determinism: the same input in a different row order gives the same ledger.
    again = simulate(jobs.reverse(), U(), sites=sites1)
    assert again.sort("job_uid").equals(ledger.sort("job_uid"))


def test_s_ranking_then_home():
    sites = {"PACE": 4, "CISO": 4, "BPAT": 4, "NEVP": 4}
    jobs = jobs_frame([
        {"job_uid": "f1", "at_min": 0, "dur_min": 60, "gpus": 4, "flexible": True},
        {"job_uid": "f2", "at_min": 0, "dur_min": 60, "gpus": 4, "flexible": True},
        {"job_uid": "f3", "at_min": 0, "dur_min": 60, "gpus": 4, "flexible": True},
        {"job_uid": "f4", "at_min": 0, "dur_min": 60, "gpus": 4, "flexible": True},
        {"job_uid": "rigid", "at_min": 0, "dur_min": 60, "gpus": 1},
    ])
    ledger = simulate(jobs, S(ranking=["NEVP", "BPAT", "CISO"]), sites=sites)
    # S takes its first-ranked site and queues there while the deadline still holds.
    sites_used = [row(ledger, u)["site"] for u in ("f1", "f2", "f3", "f4")]
    assert sites_used[0] == "NEVP"
    # NEVP can run f1..f4 back to back inside 6 h + 1 h, so S keeps them there.
    assert set(sites_used) == {"NEVP"}
    assert row(ledger, "rigid")["site"] == "PACE"

    # Tight slack: only the first ranked site's immediate slot meets the deadline,
    # so later jobs move down the ranking, then home.
    jobs = jobs_frame([
        {"job_uid": f"t{i}", "at_min": 0, "dur_min": 60, "gpus": 4, "flexible": True,
         "delay_h": 0.75}
        for i in range(5)
    ])
    ledger = simulate(jobs, S(ranking=["NEVP", "BPAT", "CISO"]), sites=sites)
    got = [row(ledger, f"t{i}")["site"] for i in range(5)]
    assert got[:4] == ["NEVP", "BPAT", "CISO", "PACE"]
    assert not any(row(ledger, f"t{i}")["late"] for i in range(4))
    # t4 cannot make it anywhere: late, at the earliest finish (PACE, after t3).
    r4 = row(ledger, "t4")
    assert r4["late"] and r4["site"] == "PACE"
    assert minutes_after_t0(r4["start_ts"]) == 60


def test_immobile_jobs_stay_home():
    sites = {"PACE": 4, "CISO": 4, "BPAT": 4, "NEVP": 4}
    jobs = jobs_frame([
        {"job_uid": "blocker", "at_min": 0, "dur_min": 300, "gpus": 4},
        {"job_uid": "rigid", "at_min": 1, "dur_min": 60, "gpus": 4},
    ])
    for policy in (U(), G(), S()):
        r = row(simulate(jobs, policy, sites=sites), "rigid")
        assert r["site"] == "PACE" and not r["transfer"], policy.name
        assert minutes_after_t0(r["start_ts"]) == 300


# --------------------------------------------------------------------------- transfer


def test_remote_transfer_delay():
    sites = {"PACE": 4, "CISO": 4, "BPAT": 4, "NEVP": 4}
    jobs = jobs_frame([
        {"job_uid": "blocker", "at_min": 0, "dur_min": 600, "gpus": 4},
        {"job_uid": "x", "at_min": 5, "dur_min": 60, "gpus": 2, "flexible": True},
    ])
    for policy in (G(), S()):
        r = row(simulate(jobs, policy, sites=sites), "x")
        assert r["site"] != "PACE" and r["transfer"], policy.name
        arrival = T0 + timedelta(minutes=5)
        assert r["start_ts"] >= arrival + timedelta(seconds=1800)
        assert r["start_ts"] == arrival + timedelta(seconds=1800)  # remote site is empty
    # The transfer time is a parameter (sensitivity 0 and 120 min).
    r = row(simulate(jobs, G(), sites=sites, transfer_s=7200.0), "x")
    assert r["start_ts"] == T0 + timedelta(minutes=5, seconds=7200)


class _CheatRemote:
    """Starts remotely on arrival, skipping the transfer: the engine must refuse it."""

    name = "cheat"

    def choose(self, job, now, capacities, ctx):
        return Action("BPAT", now)


def test_illegal_action_raises():
    jobs = jobs_frame([{"job_uid": "x", "gpus": 1, "flexible": True}])
    with pytest.raises(ValueError, match="transfer"):
        simulate(jobs, _CheatRemote())


# --------------------------------------------------------------------------- contract


def test_ledger_schema_and_sites():
    assert SITES == {"PACE": 2288, "CISO": 512, "BPAT": 512, "NEVP": 512}
    jobs = jobs_frame([
        {"job_uid": "a", "at_min": 0, "gpus": 8, "flexible": True},
        {"job_uid": "b", "at_min": 3, "gpus": 1},
    ])
    ledger = simulate(jobs, G())
    assert ledger.columns == LEDGER_COLUMNS
    assert ledger.schema["start_ts"] == pl.Datetime("us", "UTC")
    assert ledger.schema["end_ts"] == pl.Datetime("us", "UTC")
    assert ledger.schema["deadline_ts"] == pl.Datetime("us", "UTC")
    assert ledger.schema["transfer"] == pl.Boolean
    assert ledger.schema["late"] == pl.Boolean
    assert ledger.schema["gpus"] == pl.Int64
    # Declared deadline without F1: arrival + duration + allowed delay.
    assert row(ledger, "a")["deadline_ts"] == T0 + timedelta(hours=7)


def test_missing_columns_raise():
    jobs = jobs_frame([{"job_uid": "a"}]).drop("mobile")
    with pytest.raises(ValueError, match="mobile"):
        simulate(jobs, U())
