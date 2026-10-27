import hashlib
from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from gridpilot import workload as W

DAY = timedelta(days=1)
CAND = {"Pretrain", "SFT", "MLLM", "Eval"}
A0 = W.ANCHOR.astimezone(UTC)
CYCLE0 = W.CYCLE_START.astimezone(UTC)


@pytest.fixture(scope="module")
def two_cycles() -> pl.DataFrame:
    return W.replay(A0, A0 + 2 * W.CYCLE_DAYS * DAY)


def _hash_flag(job_id: str) -> bool:
    return int(hashlib.sha256(f"{job_id}:42".encode()).hexdigest(), 16) % 2 == 0


def _cyc(df: pl.DataFrame, k: int) -> pl.DataFrame:
    return df.filter(pl.col("job_uid").str.ends_with(f"#c{k}"))


def test_constants():
    assert W.CYCLE_DAYS == 161
    assert W.CYCLE_START.utcoffset() == timedelta(hours=8)
    assert W.ANCHOR.utcoffset() == timedelta(hours=-7)
    assert (W.ANCHOR.year, W.ANCHOR.month, W.ANCHOR.day, W.ANCHOR.weekday()) == (2024, 1, 1, 0)


def test_schema(two_cycles):
    assert two_cycles.columns == [
        "job_uid", "source_id", "arrival_ts", "duration_s", "gpus", "job_type",
        "flexible", "max_delay_s", "mobile", "evidence_arrival", "evidence_duration",
    ]
    assert two_cycles["arrival_ts"].dtype == pl.Datetime("us", "UTC")
    assert two_cycles["gpus"].dtype.is_integer()
    assert set(two_cycles["evidence_arrival"]) == {"simulated"}
    assert set(two_cycles["evidence_duration"]) == {"measured"}
    assert (two_cycles["gpus"] > 0).all() and (two_cycles["duration_s"] > 0).all()
    assert two_cycles["job_uid"].n_unique() == two_cycles.height


def test_cycle_length(two_cycles):
    c0, c1 = _cyc(two_cycles, 0), _cyc(two_cycles, 1)
    assert c0.height == c1.height > 0
    # Cycle 1 repeats cycle 0 exactly 161 days later.
    j = c0.join(c1, on="source_id", suffix="_1")
    assert j.height == c0.height
    assert (j["arrival_ts_1"] - j["arrival_ts"]).unique().to_list() == [timedelta(days=161)]
    # Arrival offsets within the cycle are preserved: time since the source cycle start
    # equals time since the anchor, so the UTC+8 wall clock offset is gone.
    m = c0.join(W._cycle_jobs(), on="source_id")
    d = (m["arrival_ts"] - A0) - (m["submit_ts"] - CYCLE0)
    assert d.unique().to_list() == [timedelta(0)]
    assert c0["arrival_ts"].min() >= A0 and c0["arrival_ts"].max() < A0 + 161 * DAY
    # Complete durations are kept even when execution passes the cycle end.
    assert (m["duration_s"] == m["run_s"]).all()


def test_seam_ids_unique(two_cycles):
    assert two_cycles["job_uid"].n_unique() == two_cycles.height
    c0, c1 = _cyc(two_cycles, 0), _cyc(two_cycles, 1)
    j = c0.join(c1, on="source_id", suffix="_1")
    assert (j["job_uid"] != j["job_uid_1"]).all()
    assert (j["flexible"] == j["flexible_1"]).all()
    assert (j["max_delay_s"] == j["max_delay_s_1"]).all()
    assert c0["arrival_ts"].max() < c1["arrival_ts"].min()
    assert j["job_uid"].str.replace("#c0$", "").to_list() == j["source_id"].to_list()


def test_flex_hash(two_cycles):
    uniq = two_cycles.unique("source_id")
    for sid, jt, flex in uniq.select("source_id", "job_type", "flexible").iter_rows():
        assert flex == (jt in CAND and _hash_flag(sid))
    cand = uniq.filter(pl.col("job_type").is_in(CAND))
    assert 0.4 < cand["flexible"].mean() < 0.6
    assert not uniq.filter(~pl.col("job_type").is_in(CAND))["flexible"].any()
    assert (two_cycles["mobile"] == two_cycles["flexible"]).all()


def test_delays(two_cycles):
    d = two_cycles.group_by("job_type", "flexible").agg(pl.col("max_delay_s").unique().alias("d"))
    seen = {(r["job_type"], r["flexible"]): sorted(r["d"]) for r in d.iter_rows(named=True)}
    for (jt, flex), delays in seen.items():
        if not flex:
            assert delays == [0], (jt, flex)
        elif jt == "Eval":
            assert delays == [3600]
        elif jt in {"Pretrain", "SFT", "MLLM"}:
            assert delays == [21600]
        else:
            pytest.fail(f"unexpected flexible type {jt}")
    assert ("Pretrain", True) in seen and ("Eval", True) in seen
    assert seen[("Debug", False)] == [0]


def test_phase_offset():
    s, e = A0 + 300 * DAY, A0 + 330 * DAY
    base = W.replay(s - 49 * DAY, e - 49 * DAY, phase_days=0)
    shifted = W.replay(s, e, phase_days=49)
    assert shifted.height == base.height > 0
    j = base.join(shifted, on="job_uid", suffix="_p")
    assert j.height == base.height
    assert (j["arrival_ts_p"] - j["arrival_ts"]).unique().to_list() == [timedelta(days=49)]
    for col in ("duration_s", "gpus", "flexible", "max_delay_s"):
        assert (j[col] == j[f"{col}_p"]).all()


def test_window_is_half_open_and_sorted():
    s = A0 + 10 * DAY
    df = W.replay(s, s + DAY)
    assert df.height > 0
    assert df["arrival_ts"].min() >= s and df["arrival_ts"].max() < s + DAY
    assert df["arrival_ts"].is_sorted()


def test_requires_tz_aware():
    with pytest.raises(ValueError):
        W.replay(datetime(2024, 1, 1), datetime(2024, 1, 2))


def test_exclusions_logged(caplog):
    W._cycle_jobs.cache_clear()
    with caplog.at_level("INFO", logger="gridpilot.workload"):
        W._cycle_jobs()
    for reason in ("outside source cycle", "no GPU", "non-positive"):
        assert reason in caplog.text
