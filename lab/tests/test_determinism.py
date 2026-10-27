"""Stage 3 T10 determinism item (T9 finding): every float aggregation that feeds an export is
`math.fsum` over values sorted by job_uid, so it does not depend on row order or thread
scheduling; the canonical metrics hash rounds floats to 10 significant digits."""

from __future__ import annotations

import importlib.util
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from gridpilot.eval import fsum_by, influence, job_accounting, score, weekly
from gridpilot.results import canonical_hash, env
from gridpilot.sim import LEDGER_COLUMNS, SITES

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_slice.py"
T0 = datetime(2024, 11, 4, tzinfo=UTC)
N_JOBS, N_HOURS = 4000, 24 * 30


@pytest.fixture(scope="module")
def rs():
    spec = importlib.util.spec_from_file_location("run_slice", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def world():
    """A random multi-site ledger with awkward float values (seeded)."""
    rng = np.random.default_rng(7)
    truth = pl.DataFrame({
        "ba": np.repeat(list(SITES), N_HOURS),
        "ts_utc": [T0 + timedelta(hours=h) for _ in SITES for h in range(N_HOURS)],
        "ci_consumed_g_kwh": rng.uniform(13.37, 911.1, len(SITES) * N_HOURS),
    }).with_columns(pl.col("ts_utc").dt.cast_time_unit("us").dt.replace_time_zone("UTC"))
    arr = rng.integers(0, (N_HOURS - 100) * 3600, N_JOBS)
    dur = rng.uniform(17.0, 40 * 3600.0, N_JOBS).round(3)
    gpus = rng.integers(1, 9, N_JOBS)
    site = rng.choice(list(SITES), N_JOBS)
    wait = rng.integers(0, 7200, N_JOBS)
    uid = [f"s{i:05d}#c0" for i in range(N_JOBS)]
    a_ts = [T0 + timedelta(seconds=int(x)) for x in arr]
    s_ts = [t + timedelta(seconds=int(w)) for t, w in zip(a_ts, wait, strict=True)]
    jobs = pl.DataFrame({
        "job_uid": uid, "source_id": [u.split("#")[0] for u in uid], "arrival_ts": a_ts,
        "duration_s": dur, "gpus": gpus, "job_type": ["SFT"] * N_JOBS,
        "flexible": [True] * N_JOBS, "max_delay_s": [21600.0] * N_JOBS,
        "mobile": [True] * N_JOBS,
    }).with_columns(pl.col("arrival_ts").dt.cast_time_unit("us"))
    led = pl.DataFrame({
        "job_uid": uid, "site": site, "start_ts": s_ts,
        "end_ts": [s + timedelta(microseconds=round(d * 1e6)) for s, d in
                   zip(s_ts, dur, strict=True)],
        "transfer": site != "PACE", "late": [False] * N_JOBS,
        "deadline_ts": [T0 + timedelta(days=60)] * N_JOBS, "gpus": gpus, "arrival_ts": a_ts,
        "duration_s": dur, "moved": site != "PACE", "booking_site": ["PACE"] * N_JOBS,
        "blocked": [False] * N_JOBS, "fit_rejected": [False] * N_JOBS,
    }).with_columns(pl.col("start_ts", "end_ts", "deadline_ts", "arrival_ts")
                    .dt.cast_time_unit("us")).select(LEDGER_COLUMNS)
    return led, jobs, truth


def _shuffles(frame, k=5):
    return [frame.sample(fraction=1.0, shuffle=True, seed=s) for s in range(k)]


def test_fsum_by_is_order_free_and_exact():
    rng = np.random.default_rng(1)
    v = rng.normal(0, 1e6, 10_000)
    f = pl.DataFrame({"job_uid": [f"j{i:05d}" for i in range(v.size)], "x": v})
    got = {fsum_by(s, "x") for s in _shuffles(f)}
    assert got == {math.fsum(v.tolist())}
    assert fsum_by(f.head(0), "x") == 0.0


def test_five_repeated_score_aggregations_give_identical_floats(world):
    led, jobs, truth = world
    outs = [score(s, jobs, truth) for s in _shuffles(led)]
    keys = [k for k, v in outs[0].items() if isinstance(v, float)]
    assert "co2_kg" in keys and "execution_kwh" in keys
    for k in keys:
        assert len({o[k] for o in outs}) == 1, k
    acc = job_accounting(led, jobs, truth)
    assert outs[0]["co2_kg"] == math.fsum(acc.sort("job_uid")["co2_kg"].to_list())


def test_five_repeated_weekly_aggregations_give_identical_floats(world):
    led, jobs, truth = world
    window = (T0, T0 + timedelta(hours=N_HOURS))
    outs = [weekly(s, jobs, truth, window=window) for s in _shuffles(led)]
    for o in outs[1:]:
        assert o.equals(outs[0])
    acc = job_accounting(led, jobs, truth)
    assert math.fsum(outs[0]["co2_kg"].to_list()) == pytest.approx(
        math.fsum(acc["co2_kg"].to_list()), rel=1e-15)


def test_five_repeated_influence_totals_give_identical_floats(world):
    led, jobs, truth = world
    outs = [influence({"U": s, "L": s}, jobs, truth, k_list=(1, 5)) for s in _shuffles(led)]
    for o in outs[1:]:
        assert o["by_k"] == outs[0]["by_k"]


def test_five_repeated_site_energy_aggregations_give_identical_floats(rs, world):
    led, jobs, truth = world
    acc = job_accounting(led, jobs, truth)
    outs = [rs.site_energy(s, SITES) for s in _shuffles(acc)]
    assert all(o == outs[0] for o in outs)
    assert set(outs[0]) == set(SITES)
    k = acc.filter(pl.col("site") == "BPAT").sort("job_uid")["execution_kwh"].to_list()
    assert outs[0]["BPAT"] == math.fsum(k)


def test_canonical_hash_rounds_to_ten_significant_digits():
    def doc(x):
        return {"run_id": "r", "x": env(x, "kg", "simulated", "r:x")}

    big = 3_501_300.123456
    # Absolute noise far above 1e-6 on a large total is below 10 significant digits.
    assert canonical_hash(doc(big)) == canonical_hash(doc(big + 3e-5))
    assert canonical_hash(doc(big)) != canonical_hash(doc(big + 0.01))
    # Tiny values keep their own 10 significant digits (no absolute floor).
    assert canonical_hash(doc(1.234567890123e-9)) == canonical_hash(doc(1.2345678901e-9))
    assert canonical_hash(doc(1.2345e-9)) != canonical_hash(doc(1.2346e-9))
    assert canonical_hash(doc(0.0)) == canonical_hash(doc(-0.0))
