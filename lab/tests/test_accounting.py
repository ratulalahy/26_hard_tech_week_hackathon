"""Evaluation layer: work and carbon accounting, the relaxed bound, weekly totals, the
frozen paired block bootstrap, H2, influence and the support check.

Spec §8 "Relaxed hindsight bound", §9; §15 F5, F11, F12.3, F12.4, F13.1, F13.4; the
Task 6 amendment. Toy ledgers and truth tables have hand-computed expected values.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl
import pytest

from gridpilot.data.eia_co2 import site_mask
from gridpilot.eval import (
    BOOTSTRAP_LABEL,
    TruthTable,
    block_indices,
    bound_ok,
    common_support,
    denver_weeks,
    h2_decision,
    influence,
    job_accounting,
    paired_block_bootstrap,
    relaxed_bound,
    relaxed_bound_jobs,
    score,
    support_check,
    weekly,
)
from gridpilot.sim import (
    LEDGER_COLUMNS,
    SITES,
    G,
    S,
    U,
    closed_intervals,
    simulate,
    u_bookings,
    warm_up,
)
from gridpilot.splits import TEST_START

T0 = datetime(2024, 11, 4, tzinfo=UTC)  # a Monday, inside validation
US = 1_000_000
HOUR_US = 3600 * US
HIGH = 900.0


# --------------------------------------------------------------------------- builders


def truth_frame(values: dict[str, list[float | None]], start: datetime = T0) -> pl.DataFrame:
    """Hourly consumed-basis truth from `start`; None is a missing hour."""
    rows = []
    for ba, vals in values.items():
        for h, v in enumerate(vals):
            rows.append({"ba": ba, "ts_utc": start + timedelta(hours=h), "ci_consumed_g_kwh": v})
    return pl.DataFrame(rows, schema={"ba": pl.Utf8, "ts_utc": pl.Datetime("us", "UTC"),
                                      "ci_consumed_g_kwh": pl.Float64})


def flat_truth(hours: int, start: datetime = T0, **override) -> pl.DataFrame:
    vals = {s: [HIGH] * hours for s in SITES}
    vals.update(override)
    return truth_frame(vals, start)


def mins(m: float, base: datetime = T0) -> datetime:
    return base + timedelta(minutes=m)


def jobs_frame(rows: list[dict], base: datetime = T0) -> pl.DataFrame:
    out = []
    for i, r in enumerate(rows):
        flexible = r.get("flexible", False)
        uid = r.get("job_uid", f"j{i:03d}#c0")
        out.append({
            "job_uid": uid,
            "source_id": r.get("source_id", uid.split("#")[0]),
            "arrival_ts": mins(r.get("at_min", 0.0), base),
            "duration_s": float(r.get("dur_min", 60.0) * 60),
            "gpus": r.get("gpus", 1),
            "job_type": r.get("job_type", "SFT" if flexible else "Other"),
            "flexible": flexible,
            "max_delay_s": float(r.get("delay_h", 6.0 if flexible else 0.0) * 3600),
            "mobile": r.get("mobile", flexible),
        })
    return pl.DataFrame(out, schema={
        "job_uid": pl.Utf8, "source_id": pl.Utf8, "arrival_ts": pl.Datetime("us", "UTC"),
        "duration_s": pl.Float64, "gpus": pl.Int64, "job_type": pl.Utf8,
        "flexible": pl.Boolean, "max_delay_s": pl.Float64, "mobile": pl.Boolean,
    })


def ledger_frame(rows: list[dict], base: datetime = T0) -> pl.DataFrame:
    """A hand-built ledger in Task 4's columns. Times are minutes after `base`."""
    out = []
    for r in rows:
        start = mins(r["start_min"], base)
        site = r.get("site", "PACE")
        out.append({
            "job_uid": r["job_uid"],
            "site": site,
            "start_ts": start,
            "end_ts": start + timedelta(minutes=r.get("run_min", r["dur_min"])),
            "transfer": site != "PACE",
            "late": False,
            "deadline_ts": mins(r.get("deadline_min", 10_000), base),
            "gpus": r.get("gpus", 1),
            "arrival_ts": mins(r.get("at_min", 0.0), base),
            "duration_s": float(r["dur_min"] * 60),
            "moved": r.get("moved", False),
            "booking_site": "PACE",
            "blocked": r.get("blocked", False),
        })
    schema = {
        "job_uid": pl.Utf8, "site": pl.Utf8, "start_ts": pl.Datetime("us", "UTC"),
        "end_ts": pl.Datetime("us", "UTC"), "transfer": pl.Boolean, "late": pl.Boolean,
        "deadline_ts": pl.Datetime("us", "UTC"), "gpus": pl.Int64,
        "arrival_ts": pl.Datetime("us", "UTC"), "duration_s": pl.Float64,
        "moved": pl.Boolean, "booking_site": pl.Utf8, "blocked": pl.Boolean,
    }
    return pl.DataFrame(out, schema=schema).select(LEDGER_COLUMNS)


# The worked example of the score tests (all values by hand).
#   a: 2 GPUs at PACE, arrives 0, runs [30, 120) min.   PACE h0=100, h1=200.
#      exec kWh = 2*0.6*1.5*1.2 = 2.16;  CO2 = 2*0.72*(0.5*100 + 1*200) g = 360 g.
#   b: 4 GPUs moved to CISO, arrives 10, runs [50, 170). CISO h0=50, h1=60, h2=70.
#      exec kWh = 4*0.6*2*1.2 = 5.76; CO2 = 4*0.72*(10/60*50 + 60 + 50/60*70) = 364.8 g.
#      transfer IT = 0.05*4*0.6*2 = 0.24 kWh; with PUE 0.288 kWh, half at PACE h0 (100)
#      and half at CISO h0 (50): 0.144*100 + 0.144*50 = 21.6 g.
#   c: 1 GPU at PACE, blocked, arrives 60, runs [60, 120). 0.72 kWh, 0.72*200 = 144 g.
EX_TRUTH = {"PACE": [100, 200, 300, 400], "CISO": [50, 60, 70, 80],
            "BPAT": [HIGH] * 4, "NEVP": [HIGH] * 4}
EX_JOBS = [
    {"job_uid": "a#c0", "at_min": 0, "dur_min": 90, "gpus": 2},
    {"job_uid": "b#c0", "at_min": 10, "dur_min": 120, "gpus": 4, "flexible": True},
    {"job_uid": "c#c0", "at_min": 60, "dur_min": 60, "gpus": 1, "flexible": True},
]
EX_LEDGER = [
    {"job_uid": "a#c0", "at_min": 0, "start_min": 30, "dur_min": 90, "gpus": 2},
    {"job_uid": "b#c0", "at_min": 10, "start_min": 50, "dur_min": 120, "gpus": 4,
     "site": "CISO", "moved": True},
    {"job_uid": "c#c0", "at_min": 60, "start_min": 60, "dur_min": 60, "gpus": 1,
     "blocked": True},
]


def example():
    return ledger_frame(EX_LEDGER), jobs_frame(EX_JOBS), truth_frame(EX_TRUTH)


# --------------------------------------------------------------------------- score


def test_conservation():
    led, jobs, truth = example()
    m = score(led, jobs, truth)
    assert m["requested_gpu_s"] == 2 * 5400 + 4 * 7200 + 3600
    assert m["completed_gpu_s"] == m["requested_gpu_s"]
    assert m["conserved"] is True


def test_short_run_is_not_conserved_and_not_feasible():
    rows = [dict(r) for r in EX_LEDGER]
    rows[0]["run_min"] = 60  # ran 60 of its 90 minutes
    m = score(ledger_frame(rows), jobs_frame(EX_JOBS), truth_frame(EX_TRUTH))
    assert m["completed_gpu_s"] == m["requested_gpu_s"] - 2 * 1800
    assert m["conserved"] is False
    assert m["feasible"] is False


def test_score_hand_values():
    m = score(*example())
    assert m["n_jobs"] == 3
    assert m["execution_kwh"] == pytest.approx(2.16 + 5.76 + 0.72, abs=1e-12)
    assert m["transfer_kwh"] == pytest.approx(0.288, abs=1e-12)
    assert m["transfer_it_kwh"] == pytest.approx(0.24, abs=1e-12)
    assert m["energy_kwh"] == pytest.approx(8.64 + 0.288, abs=1e-12)
    assert m["execution_co2_kg"] == pytest.approx(0.360 + 0.3648 + 0.144, abs=1e-12)
    assert m["transfer_co2_kg"] == pytest.approx(0.0216, abs=1e-12)
    assert m["co2_kg"] == pytest.approx(0.8904, abs=1e-12)
    assert m["co2_kg_per_1000_gpu_h"] == pytest.approx(0.8904 / 0.012, rel=1e-12)
    assert m["wait_p50_s"] == pytest.approx(1800.0)
    assert m["wait_p95_s"] == pytest.approx(2340.0)
    assert m["wait_max_s"] == pytest.approx(2400.0)
    assert m["late_jobs"] == 0 and m["late_gpu_h"] == 0.0 and m["feasible"] is True
    assert m["moved_jobs"] == 1
    assert m["moved_share_jobs"] == pytest.approx(1 / 3)
    assert m["moved_share_energy"] == pytest.approx(5.76 / 8.64)
    assert m["remote_jobs"] == 1
    assert m["blocked_jobs"] == 1
    assert m["blocked_kwh"] == pytest.approx(0.72)
    assert m["evidence"]["co2_kg"] == "modeled"


def test_job_accounting_rows():
    acc = job_accounting(*example()).sort("job_uid")
    b = acc.filter(pl.col("job_uid") == "b#c0").to_dicts()[0]
    assert b["execution_co2_kg"] == pytest.approx(0.3648, abs=1e-12)
    assert b["transfer_co2_kg"] == pytest.approx(0.0216, abs=1e-12)
    assert b["wait_s"] == pytest.approx(2400.0)
    assert b["remote"] is True


def test_late_job_counts():
    rows = [dict(r) for r in EX_LEDGER]
    rows[1]["deadline_min"] = 160  # b ends at 170
    m = score(ledger_frame(rows), jobs_frame(EX_JOBS), truth_frame(EX_TRUTH))
    assert m["late_jobs"] == 1
    assert m["late_gpu_h"] == pytest.approx(8.0)  # 4 GPUs x 2 h
    assert m["feasible"] is False


def test_ledger_must_match_jobs():
    led, jobs, truth = example()
    with pytest.raises(ValueError, match="missing"):
        score(led.head(2), jobs, truth)
    with pytest.raises(ValueError, match="duplicate"):
        score(pl.concat([led, led.head(1)]), jobs, truth)
    with pytest.raises(ValueError, match="gpus"):
        score(led.with_columns(pl.lit(7).cast(pl.Int64).alias("gpus")), jobs, truth)


def test_missing_truth_touched_raises():
    led, jobs, _ = example()
    t = dict(EX_TRUTH)
    t["CISO"] = [50, 60, None, 80]  # b runs into CISO h2
    with pytest.raises(ValueError, match="missing truth"):
        score(led, jobs, truth_frame(t))


def one_hour_mask(ba: str, hour: int, ok: bool | None) -> pl.DataFrame:
    return pl.DataFrame({"ba": [ba], "ts_utc": [T0 + timedelta(hours=hour)],
                         "truth_ok": [ok]},
                        schema={"ba": pl.Utf8, "ts_utc": pl.Datetime("us", "UTC"),
                                "truth_ok": pl.Boolean})


def test_mask_closing_a_valued_hour_raises():
    """The mask must come from the same (filled) truth (fix r1 #6)."""
    led, jobs, truth = example()
    with pytest.raises(ValueError, match="mask closes"):
        score(led, jobs, truth, mask=one_hour_mask("CISO", 1, False))
    with pytest.raises(ValueError, match="mask closes"):  # a null truth_ok means closed
        TruthTable(truth, one_hour_mask("CISO", 1, None))


def test_mask_from_the_same_truth_is_consistent():
    led, jobs, _ = example()
    t = dict(EX_TRUTH)
    t["BPAT"] = [HIGH, None, HIGH, HIGH]  # nobody runs at BPAT
    truth = truth_frame(t)
    mask = site_mask(truth)
    assert not mask.filter((pl.col("ba") == "BPAT") & ~pl.col("truth_ok")).is_empty()
    assert score(led, jobs, truth, mask=mask)["co2_kg"] == pytest.approx(0.8904, abs=1e-12)


def test_tier_must_be_1_to_4_where_valued():
    for bad in (None, 0, 5):
        t = ex_tiered().with_columns(
            pl.when((pl.col("ba") == "PACE") & (pl.col("ts_utc") == T0)).then(pl.lit(bad))
            .otherwise(pl.col("tier")).cast(pl.Int8).alias("tier"))
        with pytest.raises(ValueError, match="tier"):
            TruthTable(t)
    # a null tier on a row with no value is fine (the hour is simply missing)
    t = ex_tiered().with_columns(
        pl.when((pl.col("ba") == "NEVP") & (pl.col("ts_utc") == T0)).then(None)
        .otherwise(pl.col("ci_g_kwh")).alias("ci_g_kwh"),
        pl.when((pl.col("ba") == "NEVP") & (pl.col("ts_utc") == T0)).then(None)
        .otherwise(pl.col("tier")).cast(pl.Int8).alias("tier"))
    TruthTable(t)


def _hour_walk(ci: dict[int, float | None], s: int, e: int) -> tuple[float, bool]:
    """Pure-Python reference: walk [s, e) hour by hour (µs ints, hour index -> value)."""
    acc, miss, t = 0.0, False, s
    while t < e:
        h = t // HOUR_US
        nxt = min(e, (h + 1) * HOUR_US)
        v = ci.get(h)
        if v is None:
            miss = True
        else:
            acc += (nxt - t) / HOUR_US * v
        t = nxt
    return acc, miss


def test_integral_matches_pure_python_hour_walk():
    """Fix r1 #7: TruthTable.integral against an independent hour walk, µs-level times."""
    rng = np.random.default_rng(2026)
    hours = 72
    vals = [None if rng.random() < 0.05 else float(rng.uniform(10, 900)) for _ in range(hours)]
    tt = TruthTable(truth_frame({"PACE": vals}))
    h0 = int(T0.timestamp()) * US // HOUR_US
    ci = {h0 + i: v for i, v in enumerate(vals)}
    t0 = h0 * HOUR_US
    s = t0 + rng.integers(-HOUR_US, (hours - 1) * HOUR_US, size=400)
    d = rng.integers(1, 30 * HOUR_US, size=400)
    d[:20] = rng.integers(1, 1000, size=20)  # sub-millisecond jobs
    s[20:40] = t0 + rng.integers(0, hours, size=20) * HOUR_US  # hour-aligned starts
    e = s + d
    val, miss = tt.integral("PACE", s, e)
    n_checked = 0
    for i in range(s.size):
        ref, ref_miss = _hour_walk(ci, int(s[i]), int(e[i]))
        assert bool(miss[i]) == ref_miss, i
        if not ref_miss:
            assert val[i] == pytest.approx(ref, rel=1e-12, abs=1e-9), i
            n_checked += 1
    assert n_checked > 100


def test_truth_request_at_or_after_seal_raises():
    base = TEST_START - timedelta(hours=2)
    truth = flat_truth(2, start=base)
    jobs = jobs_frame([{"job_uid": "x#c0", "at_min": 0, "dur_min": 180}], base=base)
    led = ledger_frame([{"job_uid": "x#c0", "start_min": 0, "dur_min": 180}], base=base)
    with pytest.raises(ValueError, match="TEST_START"):
        score(led, jobs, truth)
    # ending exactly at TEST_START is fine
    jobs = jobs_frame([{"job_uid": "x#c0", "at_min": 0, "dur_min": 120}], base=base)
    led = ledger_frame([{"job_uid": "x#c0", "start_min": 0, "dur_min": 120}], base=base)
    assert score(led, jobs, truth)["co2_kg"] == pytest.approx(2 * 0.72 * HIGH / 1000)


def test_truth_table_drops_sealed_rows():
    truth = flat_truth(4, start=TEST_START - timedelta(hours=2))
    tt = TruthTable(truth)
    assert tt.end_us == int(TEST_START.timestamp()) * US


def test_empty_ledger_scores_to_zero_with_null_waits():
    jobs = jobs_frame(EX_JOBS).head(0)
    led = ledger_frame(EX_LEDGER).head(0)
    m = score(led, jobs, truth_frame(EX_TRUTH))
    assert m["n_jobs"] == 0 and m["co2_kg"] == 0.0
    assert m["wait_p50_s"] is None and m["co2_kg_per_1000_gpu_h"] is None


def tiered(values: dict[str, list[tuple[float | None, int]]]) -> pl.DataFrame:
    """F14.6 scoring truth (ba, ts_utc, ci_g_kwh, tier) from (value, tier) pairs."""
    rows = [{"ba": ba, "ts_utc": T0 + timedelta(hours=h), "ci_g_kwh": v, "tier": t}
            for ba, vals in values.items() for h, (v, t) in enumerate(vals)]
    return pl.DataFrame(rows, schema={"ba": pl.Utf8, "ts_utc": pl.Datetime("us", "UTC"),
                                      "ci_g_kwh": pl.Float64, "tier": pl.Int8})


def ex_tiered(pace_tiers=(1, 1, 1, 1), ciso_tiers=(1, 1, 1, 1)):
    return tiered({
        "PACE": list(zip(EX_TRUTH["PACE"], pace_tiers, strict=True)),
        "CISO": list(zip(EX_TRUTH["CISO"], ciso_tiers, strict=True)),
        "BPAT": [(HIGH, 1)] * 4, "NEVP": [(HIGH, 1)] * 4,
    })


def test_tiered_truth_all_tier1_matches_consumed_basis():
    led, jobs, truth = example()
    a, b = score(led, jobs, truth), score(led, jobs, ex_tiered())
    assert b["co2_kg"] == pytest.approx(a["co2_kg"], abs=1e-15)
    assert a["kwh_share_tier_ge2"] == 0.0 and b["kwh_share_tier_ge2"] == 0.0


def test_kwh_share_tier_ge2():
    # PACE h1 is a tier-3 fill. Charged kWh there: a's 1 h at 2 GPUs = 1.44 kWh, c's 1 h
    # at 1 GPU = 0.72 kWh. Total charged = 8.64 exec + 0.288 transfer = 8.928 kWh.
    led, jobs, _ = example()
    m = score(led, jobs, ex_tiered(pace_tiers=(1, 3, 1, 1)))
    assert m["kwh_share_tier_ge2"] == pytest.approx((1.44 + 0.72) / 8.928, rel=1e-12)
    # CISO h0 tier 2: b's 10 min there (0.48 kWh) and the CISO half of its transfer (0.144)
    m = score(led, jobs, ex_tiered(ciso_tiers=(2, 1, 1, 1)))
    assert m["kwh_share_tier_ge2"] == pytest.approx((0.48 + 0.144) / 8.928, rel=1e-12)


def test_tiered_null_value_is_still_missing():
    led, jobs, _ = example()
    t = ex_tiered().with_columns(
        pl.when((pl.col("ba") == "CISO") & (pl.col("ts_utc") == T0 + timedelta(hours=2)))
        .then(None).otherwise(pl.col("ci_g_kwh")).alias("ci_g_kwh"))
    with pytest.raises(ValueError, match="missing truth"):
        score(led, jobs, t)


def test_common_support_unions_policies():
    led_u = ledger_frame(EX_LEDGER)
    rows = [dict(r) for r in EX_LEDGER]
    rows[0].update(site="NEVP", start_min=30)  # a at NEVP in policy X
    led_x = ledger_frame(rows)
    # NEVP h0 is filled: under X, a touches it (exec at h0 and its arrival-hour transfer)
    t = ex_tiered().with_columns(
        pl.when((pl.col("ba") == "NEVP") & (pl.col("ts_utc") == T0)).then(4)
        .otherwise(pl.col("tier")).cast(pl.Int8).alias("tier"))
    assert common_support({"U": led_u}, t) == []
    assert common_support({"U": led_u, "X": led_x}, t) == ["a#c0"]
    # a transfer-only touch counts too: CISO h0 filled, b executes from 50 min in CISO h0
    # and its CISO transfer half is charged at h0.
    assert common_support({"U": led_u}, ex_tiered(ciso_tiers=(2, 1, 1, 1))) == ["b#c0"]
    # PACE h2 filled touches nobody (a and c end at 120 min = h2 start; half-open)
    assert common_support({"U": led_u}, ex_tiered(pace_tiers=(1, 1, 2, 1))) == []


# --------------------------------------------------------------------------- relaxed bound


def bound_job(**kw):
    """One flexible mobile 1-GPU 60-minute job arriving at T0, deadline T0 + 4 h."""
    jobs = jobs_frame([{"job_uid": "f#c0", "flexible": True, "dur_min": 60, **kw}])
    return jobs.with_columns(pl.lit(T0 + timedelta(hours=4)).dt.cast_time_unit("us")
                             .alias("deadline_ts"))


def test_bound_hand_value_picks_remote():
    # PACE window [0, 3 h]: best start 0 -> 0.72*100 = 72 g.
    # CISO window [0.5 h, 3 h]: best start 0.5 h -> 0.72*(0.5*50 + 0.5*60) = 39.6 g,
    #   plus transfer 0.018*100 + 0.018*50 = 2.7 g -> 42.3 g.
    truth = truth_frame({"PACE": [100, 200, 300, 400], "CISO": [50, 60, 70, 80],
                         "BPAT": [HIGH] * 4, "NEVP": [HIGH] * 4})
    per = relaxed_bound_jobs(bound_job(), truth)
    r = per.to_dicts()[0]
    assert r["site"] == "CISO"
    assert r["start_ts"] == T0 + timedelta(minutes=30)
    assert r["co2_kg"] == pytest.approx(0.0423, abs=1e-12)
    assert relaxed_bound(bound_job(), truth) == pytest.approx(0.0423, abs=1e-12)


def test_bound_respects_missing_execution_hour():
    # CISO h1 missing: CISO starts must avoid [1 h, 2 h) -> start in [2 h, 3 h]:
    # 0.72*70 + 2.7 = 53.1 g < PACE 72 g.
    truth = truth_frame({"PACE": [100, 200, 300, 400], "CISO": [50, None, 70, 80],
                         "BPAT": [HIGH] * 4, "NEVP": [HIGH] * 4})
    r = relaxed_bound_jobs(bound_job(), truth).to_dicts()[0]
    assert (r["site"], r["start_ts"]) == ("CISO", T0 + timedelta(hours=2))
    assert r["co2_kg"] == pytest.approx(0.0531, abs=1e-12)


def test_bound_respects_missing_arrival_hour_for_transfer():
    # CISO h0 missing: the arrival-hour transfer charge has no truth -> CISO closed (F12.1).
    truth = truth_frame({"PACE": [100, 200, 300, 400], "CISO": [None, 1, 1, 1],
                         "BPAT": [HIGH] * 4, "NEVP": [HIGH] * 4})
    r = relaxed_bound_jobs(bound_job(), truth).to_dicts()[0]
    assert (r["site"], r["co2_kg"]) == ("PACE", pytest.approx(0.072, abs=1e-12))


def test_bound_with_mask_from_same_truth():
    truth = truth_frame({"PACE": [100, 200, 300, 400], "CISO": [50, None, 70, 80],
                         "BPAT": [HIGH] * 4, "NEVP": [HIGH] * 4})
    r = relaxed_bound_jobs(bound_job(), truth, site_mask(truth)).to_dicts()[0]
    assert r["co2_kg"] == pytest.approx(0.0531, abs=1e-12)
    with pytest.raises(ValueError, match="mask closes"):
        relaxed_bound_jobs(bound_job(), truth, one_hour_mask("CISO", 0, False))


def test_bound_immobile_and_gang_limits():
    truth = truth_frame({"PACE": [100, 200, 300, 400], "CISO": [1, 1, 1, 1],
                         "BPAT": [1, 1, 1, 1], "NEVP": [1, 1, 1, 1]})
    immobile = bound_job(mobile=False)
    assert relaxed_bound_jobs(immobile, truth)["site"][0] == "PACE"
    big = bound_job(gpus=600)  # larger than every 512-slot destination
    assert relaxed_bound_jobs(big, truth)["site"][0] == "PACE"


def test_bound_no_legal_action_raises():
    truth = truth_frame({"PACE": [None] * 4, "CISO": [1] * 4, "BPAT": [1] * 4,
                         "NEVP": [1] * 4})
    with pytest.raises(ValueError, match="no legal action"):
        relaxed_bound(bound_job(mobile=False), truth)


def _brute_force(jobs: pl.DataFrame, truth: pl.DataFrame, step_min: int = 1) -> float:
    """Every start on a 1-minute grid (all breakpoints are minute-aligned in the toy)."""
    tt = TruthTable(truth)
    total = 0.0
    for j in jobs.iter_rows(named=True):
        arr = int(j["arrival_ts"].timestamp()) * US
        dl = int(j["deadline_ts"].timestamp()) * US
        dur = round(j["duration_s"] * US)
        sites = ["PACE"] + (["BPAT", "CISO", "NEVP"] if j["mobile"] else [])
        best = np.inf
        for site in sites:
            if SITES[site] < j["gpus"]:
                continue
            remote = site != "PACE"
            lo = arr + (1800 * US if remote else 0)
            starts = np.arange(lo, dl - dur + 1, step_min * 60 * US, dtype=np.int64)
            if starts.size == 0:
                continue
            tco2 = 0.0
            if remote:
                ch, mh = tt.point("PACE", np.array([arr]))
                cd, md = tt.point(site, np.array([arr]))
                if mh[0] or md[0]:
                    continue
                tkwh = 0.05 * j["gpus"] * 0.6 * dur / HOUR_US * 1.2
                tco2 = 0.5 * tkwh * (ch[0] + cd[0])
            val, miss = tt.integral(site, starts, starts + dur)
            val = np.where(miss, np.inf, j["gpus"] * 0.72 * val + tco2)
            best = min(best, float(val.min()))
        total += best / 1000
    return total


def random_instance(seed: int, n_jobs: int = 25, hours: int = 40, missing: bool = True):
    rng = np.random.default_rng(seed)
    vals = {}
    for s in SITES:
        v = rng.integers(20, 800, size=hours).astype(float).tolist()
        if missing and s != "PACE":
            for h in rng.choice(hours, size=3, replace=False):
                v[int(h)] = None
        vals[s] = v
    truth = truth_frame(vals)
    rows = []
    for i in range(n_jobs):
        flex = bool(rng.random() < 0.6)
        rows.append({
            "job_uid": f"r{i:03d}#c0",
            "at_min": int(rng.integers(0, 10 * 60)),
            "dur_min": int(rng.integers(5, 240)),
            "gpus": int(rng.choice([1, 8, 64, 256, 600, 1200])),
            "flexible": flex,
            "delay_h": float(rng.choice([1, 6])) if flex else 0.0,
        })
    return jobs_frame(rows), truth


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_bound_matches_brute_force(seed):
    jobs, truth = random_instance(seed, n_jobs=12)
    bookings = u_bookings(jobs)
    jd = jobs.join(bookings.select("job_uid", "deadline_us"), on="job_uid").with_columns(
        pl.from_epoch("deadline_us", time_unit="us").dt.replace_time_zone("UTC")
        .alias("deadline_ts"))
    got = relaxed_bound(jobs, truth, bookings=bookings)
    assert got == pytest.approx(_brute_force(jd, truth), abs=1e-9)


@pytest.mark.parametrize("seed", [11, 12, 13, 14])
def test_bound_below_feasible(seed):
    """Every feasible policy's co2_kg is >= relaxed_bound within 1e-6 (spec §8)."""
    jobs, truth = random_instance(seed)
    # PACE stays fully supported so every booking is legal (F12.3 support check).
    mask = site_mask(truth)
    tt = TruthTable(truth, mask)
    closed = closed_intervals(mask)
    bookings = u_bookings(jobs)
    assert support_check(bookings, truth, TEST_START)["ok"]
    bound = relaxed_bound(jobs, truth, mask, bookings=bookings)
    moved = 0
    for pol in (U(), G(), S(["BPAT", "CISO", "NEVP", "PACE"])):
        led = simulate(jobs, pol, bookings=bookings, closed=closed)
        m = score(led, jobs, tt)
        assert m["feasible"] and m["conserved"]
        assert bound_ok(m["co2_kg"], bound), (pol.name, m["co2_kg"], bound)
        assert m["co2_kg"] >= bound - 1e-6
        moved += m["moved_jobs"]
    assert moved > 0  # the instance exercises moves, not just bookings


def test_bound_uses_ledger_deadlines():
    jobs, truth = random_instance(5, n_jobs=8, missing=False)
    bookings = u_bookings(jobs)
    led = simulate(jobs, U(), bookings=bookings)
    a = relaxed_bound(jobs, truth, bookings=bookings)
    b = relaxed_bound(jobs.join(led.select("job_uid", "deadline_ts"), on="job_uid"), truth)
    assert a == pytest.approx(b, abs=1e-12)


# --------------------------------------------------------------------------- weekly


def test_weekly_denver_arrival_weeks_with_zero_weeks():
    # Denver weeks: Mon 2024-10-28 00:00 MDT (06:00Z), Mon 2024-11-04 00:00 MST (07:00Z),
    # 11-11 and 11-18. DST ends Sun 2024-11-03.
    base = datetime(2024, 10, 30, tzinfo=UTC)
    hours = 24 * 25
    truth = flat_truth(hours, start=base, PACE=[100.0] * hours)
    sunday_late = datetime(2024, 11, 4, 6, 30, tzinfo=UTC)  # Sun 23:30 MST
    monday = datetime(2024, 11, 4, 7, 0, tzinfo=UTC)  # Mon 00:00 MST
    last = datetime(2024, 11, 18, 12, 0, tzinfo=UTC)

    def at(ts):
        return (ts - base).total_seconds() / 60

    jrows = [
        {"job_uid": "p#c0", "at_min": at(sunday_late), "dur_min": 120},  # crosses the week
        {"job_uid": "q#c0", "at_min": at(monday), "dur_min": 60},
        {"job_uid": "r#c0", "at_min": at(last), "dur_min": 60, "gpus": 3},
    ]
    lrows = [{**r, "start_min": r["at_min"]} for r in jrows]
    jobs, led = jobs_frame(jrows, base), ledger_frame(lrows, base)
    w = weekly(led, jobs, truth, window=(base, datetime(2024, 11, 20, tzinfo=UTC)))
    assert w.columns[:3] == ["week", "co2_kg", "energy_kwh"]
    assert w.schema["week"] == pl.Datetime("us", "America/Denver")
    wk = [d.astimezone(UTC) for d in w["week"].to_list()]
    assert wk == [datetime(2024, 10, 28, 6, tzinfo=UTC), datetime(2024, 11, 4, 7, tzinfo=UTC),
                  datetime(2024, 11, 11, 7, tzinfo=UTC), datetime(2024, 11, 18, 7, tzinfo=UTC)]
    # p's full 2 h land in its arrival week; q 1 h; nothing in 11-11; r 3 GPU-h.
    assert w["energy_kwh"].to_list() == pytest.approx([2 * 0.72, 0.72, 0.0, 3 * 0.72])
    assert w["co2_kg"].to_list() == pytest.approx([0.144, 0.072, 0.0, 0.216])
    assert w["n_jobs"].to_list() == [1, 1, 0, 1]
    assert w["co2_kg"].sum() == pytest.approx(score(led, jobs, truth)["co2_kg"])


def test_weekly_spring_forward_week():
    # DST starts Sun 2025-03-09 02:00 MST. Weeks: Mon 03-03 00:00 MST (07:00Z) and
    # Mon 03-10 00:00 MDT (06:00Z), which is only 167 h later.
    base = datetime(2025, 3, 1, tzinfo=UTC)
    hours = 24 * 16
    truth = flat_truth(hours, start=base, PACE=[100.0] * hours)

    def at(ts):
        return (ts - base).total_seconds() / 60

    sun_late = datetime(2025, 3, 10, 5, 30, tzinfo=UTC)  # Sun 23:30 MDT
    mon = datetime(2025, 3, 10, 6, 0, tzinfo=UTC)  # Mon 00:00 MDT
    jrows = [{"job_uid": "s#c0", "at_min": at(sun_late), "dur_min": 60},
             {"job_uid": "m#c0", "at_min": at(mon), "dur_min": 60, "gpus": 2}]
    jobs = jobs_frame(jrows, base)
    led = ledger_frame([{**r, "start_min": r["at_min"]} for r in jrows], base)
    w = weekly(led, jobs, truth, window=(datetime(2025, 3, 5, tzinfo=UTC),
                                         datetime(2025, 3, 12, tzinfo=UTC)))
    wk = [d.astimezone(UTC) for d in w["week"].to_list()]
    assert wk == [datetime(2025, 3, 3, 7, tzinfo=UTC), datetime(2025, 3, 10, 6, tzinfo=UTC)]
    assert w["n_jobs"].to_list() == [1, 1]
    assert w["co2_kg"].to_list() == pytest.approx([0.072, 0.144])


def test_weekly_window_is_required_and_tz_aware():
    led, jobs, truth = example()
    with pytest.raises(TypeError):
        weekly(led, jobs, truth)  # the window is a required keyword
    with pytest.raises(ValueError, match="timezone-aware"):
        weekly(led, jobs, truth, window=(datetime(2024, 11, 4), datetime(2024, 11, 11)))
    with pytest.raises(ValueError, match="timezone-aware"):
        denver_weeks(datetime(2024, 11, 4), T0 + timedelta(days=7))


def test_weekly_rejects_arrivals_outside_window():
    led, jobs, truth = example()
    with pytest.raises(ValueError, match="outside"):
        weekly(led, jobs, truth, window=(T0 + timedelta(hours=1), T0 + timedelta(days=7)))


# --------------------------------------------------------------------------- bootstrap


# Frozen F13.4/F14.8 reference: n=10, b=4, reps=3, Generator(PCG64(20261027)); per
# replicate starts = rng.integers(0, 10, size=3) -> [7, 9, 2], [9, 6, 0], [0, 4, 9].
FIXTURE_10_4_3 = [
    [7, 8, 9, 0, 9, 0, 1, 2, 2, 3],
    [9, 0, 1, 2, 6, 7, 8, 9, 0, 1],
    [0, 1, 2, 3, 4, 5, 6, 7, 9, 0],
]


def test_block_indices_fixture():
    """A reimplementation of the frozen draw must reproduce exactly this sequence."""
    assert block_indices(10, 4, reps=3).tolist() == FIXTURE_10_4_3
    # the stream is per replicate, in replicate order: a longer run extends the fixture
    assert block_indices(10, 4, reps=5)[:3].tolist() == FIXTURE_10_4_3


def test_block_indices_trim_and_wrap():
    idx = block_indices(5, 4, reps=50)
    assert idx.shape == (50, 5)
    # each row: a block of 4 consecutive weeks (mod 5, wrapping), then the first week of
    # a second block; the rest of that block is trimmed
    for row in idx:
        assert [(row[0] + j) % 5 for j in range(4)] == row[:4].tolist()
    assert idx.min() == 0 and idx.max() == 4
    assert block_indices(0, 4, reps=3).shape == (3, 0)


def weeks(vals):
    return np.asarray(vals, dtype=float)


def test_bootstrap_deterministic():
    rng = np.random.default_rng(0)
    a, b = rng.uniform(50, 100, 30), rng.uniform(40, 100, 30)
    r1 = paired_block_bootstrap(a, b)
    r2 = paired_block_bootstrap(a, b)
    assert r1 == r2
    assert r1["method"] == BOOTSTRAP_LABEL
    assert (r1["block"], r1["reps"], r1["seed"], r1["n_weeks"]) == (4, 2000, 20261027, 30)
    r3 = paired_block_bootstrap(a, b, seed=1)
    assert r3["diff_kg_ci"] != r1["diff_kg_ci"]


def test_bootstrap_matches_direct_computation():
    rng = np.random.default_rng(3)
    a, b = rng.uniform(50, 100, 13), rng.uniform(40, 100, 13)
    r = paired_block_bootstrap(a, b, block=4, reps=200)
    idx = block_indices(13, 4, reps=200)
    A, B = a[idx].sum(1), b[idx].sum(1)
    lo, hi = np.quantile(A - B, [0.025, 0.975], method="linear")
    assert r["diff_kg_ci"] == pytest.approx((lo, hi), abs=1e-12)
    slo, shi = np.quantile((A - B) / A, [0.025, 0.975], method="linear")
    assert r["saving_ci"] == pytest.approx((slo, shi), abs=1e-15)
    assert r["diff_kg"] == pytest.approx(a.sum() - b.sum())
    assert r["saving"] == pytest.approx((a.sum() - b.sum()) / a.sum())


def test_negative_saving_survives():
    """A policy worse than U yields a negative saving and a negative CI midpoint."""
    rng = np.random.default_rng(7)
    u = rng.uniform(80, 120, 20)
    worse = u * 1.10 + rng.uniform(0, 2, 20)
    r = paired_block_bootstrap(u, worse)
    assert r["saving"] < 0 and r["diff_kg"] < 0
    lo, hi = r["saving_ci"]
    assert (lo + hi) / 2 < 0
    lo, hi = r["diff_kg_ci"]
    assert (lo + hi) / 2 < 0 and hi < 0


def test_negative_saving_survives_from_ledgers():
    """Ledger -> weekly -> bootstrap keeps the sign (review focus 4)."""
    led_u, jobs, truth = example()
    rows = [dict(r) for r in EX_LEDGER]
    rows[1].update(site="NEVP")  # b moves somewhere dirtier than its home slot
    led_x = ledger_frame(rows)
    window = (T0, T0 + timedelta(days=7))
    wu = weekly(led_u, jobs, truth, window=window)
    wx = weekly(led_x, jobs, truth, window=window)
    r = paired_block_bootstrap(wu, wx, block=1, reps=10)
    assert r["diff_kg"] < 0 and r["saving"] < 0
    assert r["diff_kg"] == pytest.approx(score(led_u, jobs, truth)["co2_kg"]
                                         - score(led_x, jobs, truth)["co2_kg"])


def test_zero_reference_pct_is_none():
    r = paired_block_bootstrap(np.zeros(8), np.ones(8))
    assert r["saving"] is None and r["saving_ci"] is None
    assert r["diff_kg"] == pytest.approx(-8.0)
    assert r["diff_kg_ci"] is not None


def test_zero_reference_replicate_gives_null_ratio_interval():
    a = np.zeros(10)
    a[0] = 5.0  # some replicates miss week 0 and have a zero reference total
    r = paired_block_bootstrap(a, np.ones(10), block=2, reps=200)
    assert r["saving"] is not None
    assert r["saving_ci"] is None


def test_empty_input_gives_null_intervals():
    r = paired_block_bootstrap(np.array([]), np.array([]))
    assert r["n_weeks"] == 0
    assert r["diff_kg"] is None and r["diff_kg_ci"] is None
    assert r["saving"] is None and r["saving_ci"] is None


def test_bootstrap_rejects_mismatched_weeks():
    with pytest.raises(ValueError, match="length"):
        paired_block_bootstrap(np.ones(3), np.ones(4))
    led, jobs, truth = example()
    w1 = weekly(led, jobs, truth, window=(T0, T0 + timedelta(days=7)))
    w2 = weekly(led, jobs, truth, window=(T0 - timedelta(days=7), T0 + timedelta(days=7)))
    with pytest.raises(ValueError, match="week"):
        paired_block_bootstrap(w1, w2.tail(1))


def test_h2_decision_directions():
    rng = np.random.default_rng(11)
    w = rng.uniform(90, 110, 40)
    fav = h2_decision(w, w - 5 - rng.uniform(0, 1, 40))  # L clearly lower than W
    assert fav["direction"] == "favourable" and fav["decided"] is True
    assert sorted(fav["intervals"]) == [2, 4, 8]
    assert all(fav["intervals"][b]["diff_kg_ci"][0] > 0 for b in (2, 4, 8))
    adv = h2_decision(w, w + 5 + rng.uniform(0, 1, 40))
    assert adv["direction"] == "adverse" and adv["decided"] is True
    inc = h2_decision(w, w + rng.normal(0, 5, 40))
    assert inc["direction"] == "inconclusive" and inc["decided"] is False
    assert fav["method"] == BOOTSTRAP_LABEL
    empty = h2_decision(np.array([]), np.array([]))
    assert empty["direction"] == "inconclusive" and empty["decided"] is False
    assert empty["reason"] == "degenerate"


# W − L by week (24 weeks): a slow seasonal swing around a small positive mean. Short
# blocks give an interval above zero; b = 8 keeps whole swings together and straddles 0.
SPLIT_D = [1.1, 1.618, 2.1, 2.514, 2.832, 3.032, 3.1, 3.032, 2.832, 2.514, 2.1, 1.618, 1.1,
           0.582, 0.1, -0.314, -0.632, -0.832, -0.9, -0.832, -0.632, -0.314, 0.1, 0.582]


def test_h2_two_blocks_decide_third_does_not():
    d = np.array(SPLIT_D)
    r = h2_decision(100 + d, np.full(d.size, 100.0))
    lo = {b: r["intervals"][b]["diff_kg_ci"][0] for b in (2, 4, 8)}
    hi8 = r["intervals"][8]["diff_kg_ci"][1]
    assert lo[2] > 0 and lo[4] > 0
    assert lo[8] <= 0 < hi8
    assert r["direction"] == "inconclusive" and r["decided"] is False
    assert r["reason"] == "intervals do not all lie on one side of zero"


def test_degenerate_when_n_le_block():
    a, b = np.arange(1.0, 5.0), np.arange(1.0, 5.0) * 0.5
    r = paired_block_bootstrap(a, b, block=4)
    assert r["degenerate"] is True
    # every replicate is a rotation of all n weeks: the interval collapses to the point
    assert r["diff_kg_ci"] == pytest.approx((r["diff_kg"], r["diff_kg"]))
    assert paired_block_bootstrap(np.ones(5), np.ones(5), block=4)["degenerate"] is False
    # clearly favourable data, but n = 8 <= max(blocks): no decision
    w = np.full(8, 100.0)
    h = h2_decision(w, w - 10)
    assert h["direction"] == "inconclusive" and h["reason"] == "degenerate"
    assert h["decided"] is False
    assert h2_decision(np.full(9, 100.0), np.full(9, 90.0))["direction"] == "favourable"


def test_bootstrap_rejects_mixed_inputs():
    led, jobs, truth = example()
    w = weekly(led, jobs, truth, window=(T0, T0 + timedelta(days=7)))
    with pytest.raises(TypeError, match="mixed"):
        paired_block_bootstrap(w, np.ones(w.height))
    with pytest.raises(TypeError, match="mixed"):
        paired_block_bootstrap(np.ones(w.height), w)


# --------------------------------------------------------------------------- influence


def test_influence_removes_every_instance_of_top_sources():
    # declared GPU-h: big = 8 GPU x 2 h = 16 (two instances); mid = 4 x 1 = 4;
    # tie1/tie2 = 2 x 1 = 2 each (ties go to source_id order).
    jrows = [
        {"job_uid": "big#c0", "at_min": 0, "dur_min": 120, "gpus": 8, "flexible": True},
        {"job_uid": "big#c1", "at_min": 300, "dur_min": 120, "gpus": 8, "flexible": True},
        {"job_uid": "mid#c0", "at_min": 0, "dur_min": 60, "gpus": 4},
        {"job_uid": "tie2#c0", "at_min": 0, "dur_min": 60, "gpus": 2},
        {"job_uid": "tie1#c0", "at_min": 0, "dur_min": 60, "gpus": 2},
    ]
    jobs = jobs_frame(jrows)
    truth = flat_truth(12, PACE=[100.0] * 12, CISO=[50.0] * 12)
    lu = ledger_frame([{**r, "start_min": r["at_min"]} for r in jrows])
    lx = ledger_frame([{**r, "start_min": r["at_min"] + (30 if r.get("flexible") else 0),
                        "site": "CISO" if r.get("flexible") else "PACE",
                        "moved": bool(r.get("flexible"))} for r in jrows])
    out = influence({"U": lu, "X": lx}, jobs, truth, k_list=(1, 2, 3))
    assert [r["source_id"] for r in out["ranking"]] == ["big", "mid", "tie1"]  # top max(k)
    k0, k1, k3 = out["by_k"][0], out["by_k"][1], out["by_k"][3]
    assert k1["removed_sources"] == ["big"] and k1["removed_jobs"] == 2
    assert k3["removed_sources"] == ["big", "mid", "tie1"]
    # without big, X equals U (only big moved)
    assert k1["totals"]["X"] == pytest.approx(k1["totals"]["U"])
    assert k1["vs_reference"]["X"]["diff_kg"] == pytest.approx(0.0, abs=1e-12)
    assert k0["vs_reference"]["X"]["diff_kg"] > 0
    assert k0["totals"]["U"] == pytest.approx(score(lu, jobs, truth)["co2_kg"])
    assert k3["totals"]["U"] == pytest.approx(2 * 0.72 * 100 / 1000)  # only tie2 left


def test_influence_requires_one_declared_attempt_per_source():
    jrows = [{"job_uid": "a#c0", "dur_min": 60}, {"job_uid": "a#c1", "at_min": 120,
                                                  "dur_min": 90}]
    jobs = jobs_frame(jrows)
    led = ledger_frame([{**r, "start_min": r.get("at_min", 0)} for r in jrows])
    with pytest.raises(ValueError, match="different durations"):
        influence({"U": led}, jobs, flat_truth(6), k_list=(1,))


# --------------------------------------------------------------------------- support check


def test_support_check_reports_every_failure():
    truth = truth_frame({"PACE": [100, None, 100, 100, 100, 100]})
    F = T0 + timedelta(hours=5)
    b = pl.DataFrame({
        "job_uid": ["ok#c0", "gap#c0", "late#c0", "both#c0"],
        "site": ["PACE"] * 4,
        "start_us": [0, HOUR_US // 2, 4 * HOUR_US, HOUR_US],
        "end_us": [HOUR_US, HOUR_US + 1, 6 * HOUR_US, 7 * HOUR_US],
        "deadline_us": [HOUR_US, 2 * HOUR_US, 6 * HOUR_US, 7 * HOUR_US],
    }).with_columns(pl.col("start_us", "end_us", "deadline_us")
                    + int(T0.timestamp()) * US)
    r = support_check(b, truth, F)
    assert r["ok"] is False
    assert r["n_checked"] == 4
    assert r["n_after_f"] == 2 and r["n_missing_truth"] == 2
    got = {f["job_uid"]: sorted(f["reasons"]) for f in r["failures"]}
    assert got == {"gap#c0": ["missing_truth"], "late#c0": ["ends_after_f"],
                   "both#c0": ["ends_after_f", "missing_truth"]}
    clean = support_check(b.head(1), truth, F)
    assert clean["ok"] is True and clean["failures"] == []


def test_support_check_accepts_ledgers_and_never_reads_past_seal():
    base = TEST_START - timedelta(hours=2)
    truth = flat_truth(2, start=base)
    led = ledger_frame([{"job_uid": "x#c0", "start_min": 0, "dur_min": 180}], base=base)
    r = support_check(led, truth, TEST_START)
    assert r["ok"] is False
    assert sorted(r["failures"][0]["reasons"]) == ["ends_after_f", "missing_truth"]


def test_support_check_end_equal_to_f_passes_and_f_must_be_aware():
    truth = flat_truth(4)
    t0 = int(T0.timestamp()) * US
    b = pl.DataFrame({"job_uid": ["edge#c0"], "site": ["PACE"], "start_us": [t0 + HOUR_US],
                      "end_us": [t0 + 3 * HOUR_US], "deadline_us": [t0 + 3 * HOUR_US]})
    r = support_check(b, truth, T0 + timedelta(hours=3))
    assert r["ok"] is True and r["n_after_f"] == 0
    assert support_check(b, truth, T0 + timedelta(hours=3) - timedelta(microseconds=1))[
        "n_after_f"] == 1
    with pytest.raises(ValueError, match="timezone-aware"):
        support_check(b, truth, datetime(2024, 11, 4, 3))


# --------------------------------------------------------------------------- capacity


def test_capacity_check_includes_warm_up():
    # cohort: 2,000 GPUs at PACE for [0, 60) min; warm-up: 500 GPUs still running to 30 min
    jobs = jobs_frame([{"job_uid": "big#c0", "dur_min": 60, "gpus": 2000}])
    led = ledger_frame([{"job_uid": "big#c0", "start_min": 0, "dur_min": 60, "gpus": 2000}])
    warm_led = ledger_frame([{"job_uid": "w#c0", "at_min": -60, "start_min": -30,
                              "dur_min": 60, "gpus": 500}])
    truth = flat_truth(2)
    alone = score(led, jobs, truth)
    assert alone["capacity_violations"] == 0 and alone["feasible"] is True
    m = score(led, jobs, truth, warm=warm_led)
    assert m["peak_gpus"]["PACE"] == 2500
    assert m["capacity_violations"] == 1 and m["feasible"] is False
    assert m["co2_kg"] == alone["co2_kg"]  # warm-up work and energy are not added
    # ending exactly when the cohort job starts does not overlap (half-open)
    touch = ledger_frame([{"job_uid": "w#c0", "at_min": -60, "start_min": -60,
                           "dur_min": 60, "gpus": 500}])
    assert score(led, jobs, truth, warm=touch)["capacity_violations"] == 0


def test_capacity_check_accepts_warmup_state():
    jobs, truth = random_instance(21, n_jobs=10, missing=False)
    early = jobs.with_columns(pl.col("arrival_ts") - timedelta(hours=12),
                              (pl.col("job_uid") + "w").alias("job_uid"))
    warm = warm_up(early)
    bookings = u_bookings(jobs, warm=warm)
    led = simulate(jobs, G(), bookings=bookings, warm=warm)
    m = score(led, jobs, truth, warm=warm)
    assert m["capacity_violations"] == 0 and m["feasible"] is True
