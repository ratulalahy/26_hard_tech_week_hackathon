"""F13.2 / F14.1 common prefix cohort on toy streams, and the F14.1 scenario transforms."""

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from gridpilot.cohort import (
    SCENARIOS,
    first_failure,
    prefix_cohort,
    scenario_jobs,
    scenario_sites,
)
from gridpilot.sim import SITES, u_bookings, warm_up

H = timedelta(hours=1)
T = datetime(2024, 11, 4, tzinfo=UTC)
TOY_SITES = {"PACE": 4, "CISO": 4}


def _jobs(rows):
    """rows: (uid, arrival offset h, duration h, gpus, max_delay h)."""
    return pl.DataFrame({
        "job_uid": [r[0] for r in rows],
        "source_id": [r[0].split("#")[0] for r in rows],
        "arrival_ts": [T + r[1] * H for r in rows],
        "duration_s": [r[2] * 3600.0 for r in rows],
        "gpus": [r[3] for r in rows],
        "job_type": ["Pretrain"] * len(rows),
        "flexible": [r[4] > 0 for r in rows],
        "max_delay_s": [int(r[4] * 3600) for r in rows],
        "mobile": [r[4] > 0 for r in rows],
    }, schema_overrides={"arrival_ts": pl.Datetime("us", "UTC"), "gpus": pl.Int64})


WARM = _jobs([("w0", -2, 3, 2, 0)])  # holds 2 GPUs over [T-2h, T+1h)
STREAM = _jobs([
    ("j1", 0, 1, 2, 0),  # with the warm job: 4 of 4 GPUs over [T, T+1h)
    ("j2", 1, 2, 2, 0),
    ("j3", 2, 3, 4, 0),  # waits for j2: [T+3h, T+6h), deadline T+6h
    ("j4", 5, 6, 1, 0),  # ends T+11h > F: the first failure
    ("j5", 5, 1, 1, 0),  # same arrival group as j4: dropped too
    ("j6", 6, 1, 1, 0),  # later: dropped
])
F = T + 10 * H


def _identity(jobs, sites):
    return jobs, sites


def test_prefix_drops_failing_group_and_later():
    c = prefix_cohort(WARM, STREAM, F, scenarios={"primary": _identity}, sites=TOY_SITES)
    assert c.A == T + 5 * H
    assert c.first_failure == {"primary": T + 5 * H}
    assert c.jobs["job_uid"].to_list() == ["j1", "j2", "j3"]
    assert c.n_excluded == 3
    assert c.prefix_unchanged
    b = c.bookings.sort("job_uid")
    assert b["job_uid"].to_list() == ["j1", "j2", "j3"]
    j3 = b.filter(pl.col("job_uid") == "j3").row(0, named=True)
    us = 3600 * 10**6
    t_us = int(T.timestamp()) * 10**6
    assert (j3["start_us"], j3["end_us"]) == (t_us + 3 * us, t_us + 6 * us)
    assert int(b["deadline_us"].max()) <= int(F.timestamp()) * 10**6
    assert len(c.ids_hash) == 64 and len(c.booking_hash) == 64


def test_prefix_bookings_equal_full_run_prefix():
    warm = warm_up(WARM, TOY_SITES)
    full = u_bookings(STREAM, TOY_SITES, warm=warm)
    c = prefix_cohort(WARM, STREAM, F, scenarios={"primary": _identity}, sites=TOY_SITES)
    pre = full.filter(pl.col("job_uid").is_in(c.jobs["job_uid"].to_list())).sort("job_uid")
    assert c.bookings.sort("job_uid").equals(pre)


def test_common_A_is_the_minimum_over_scenarios():
    def delay_j2(jobs, sites):  # j2's declared deadline T+1h+2h+8h = T+11h > F
        return jobs.with_columns(
            pl.when(pl.col("job_uid") == "j2").then(8 * 3600).otherwise(pl.col("max_delay_s"))
            .alias("max_delay_s")), sites

    c = prefix_cohort(WARM, STREAM, F, scenarios={"primary": _identity, "delay": delay_j2},
                      sites=TOY_SITES)
    assert c.first_failure == {"primary": T + 5 * H, "delay": T + 1 * H}
    assert c.A == T + 1 * H
    assert c.jobs["job_uid"].to_list() == ["j1"]
    # The primary scenario's bookings are used for the cohort, whatever set A.
    assert c.bookings["deadline_us"].to_list() == [int((T + H).timestamp()) * 10**6]


def test_capacity_scenario_can_move_A():
    def bigger(jobs, sites):
        return jobs, {**sites, "PACE": 8}

    def smaller_cap_fail(jobs, sites):  # 2 slots: j3 (4 GPUs) can never fit -> raises
        return jobs, {**sites, "PACE": 2}

    c = prefix_cohort(WARM, STREAM, F, scenarios={"primary": _identity, "big": bigger},
                      sites=TOY_SITES)
    assert c.first_failure["big"] == T + 5 * H  # j4 itself is too long for F
    assert c.A == T + 5 * H
    with pytest.raises(ValueError):
        prefix_cohort(WARM, STREAM, F, scenarios={"primary": _identity,
                                                  "small": smaller_cap_fail}, sites=TOY_SITES)


def test_no_failure_means_horizon_end():
    s = STREAM.filter(pl.col("job_uid").is_in(["j1", "j2", "j3"]))
    c = prefix_cohort(WARM, s, F, scenarios={"primary": _identity}, sites=TOY_SITES)
    assert c.first_failure == {"primary": None}
    assert c.A == F
    assert c.jobs.height == 3 and c.n_excluded == 0


def test_first_failure_uses_f1_deadline():
    warm = warm_up(WARM, TOY_SITES)
    b = u_bookings(STREAM, TOY_SITES, warm=warm)
    assert first_failure(b, STREAM, F) == T + 5 * H
    assert first_failure(b, STREAM, T + 20 * H) is None


def test_primary_must_be_registered():
    with pytest.raises(ValueError, match="primary"):
        prefix_cohort(WARM, STREAM, F, scenarios={"other": _identity}, sites=TOY_SITES)


# --------------------------------------------------------------------- scenario transforms


def _typed():
    return pl.DataFrame({
        "job_uid": ["a", "b", "c", "d", "e"],
        "source_id": ["a", "b", "c", "d", "e"],
        "arrival_ts": [T] * 5,
        "duration_s": [3600.0] * 5,
        "gpus": [8] * 5,
        "job_type": ["Pretrain", "SFT", "Eval", "Other", "MLLM"],
        "flexible": [True, False, True, False, True],
        "max_delay_s": [6 * 3600, 0, 3600, 0, 6 * 3600],
        "mobile": [True, False, True, False, True],
    }, schema_overrides={"arrival_ts": pl.Datetime("us", "UTC"), "gpus": pl.Int64})


def test_registered_scenarios():
    assert tuple(SCENARIOS) == ("primary", "batch_delay_0h", "batch_delay_24h", "no_flexible",
                                "all_candidates_flexible", "home_capacity_1.25x")
    j = _typed()
    assert scenario_jobs("primary", j).equals(j)
    d0 = scenario_jobs("batch_delay_0h", j)
    assert d0["max_delay_s"].to_list() == [0, 0, 3600, 0, 0]
    assert d0["flexible"].to_list() == j["flexible"].to_list()
    d24 = scenario_jobs("batch_delay_24h", j)
    assert d24["max_delay_s"].to_list() == [86400, 0, 3600, 0, 86400]  # Eval stays at 1 h
    nf = scenario_jobs("no_flexible", j)
    assert not nf["flexible"].any() and not nf["mobile"].any()
    assert nf["max_delay_s"].to_list() == [0] * 5
    af = scenario_jobs("all_candidates_flexible", j)
    assert af["flexible"].to_list() == [True, True, True, False, True]
    assert af["mobile"].to_list() == [True, True, True, False, True]
    assert af["max_delay_s"].to_list() == [21600, 21600, 3600, 0, 21600]
    assert scenario_sites("home_capacity_1.25x") == {**SITES, "PACE": 2864}  # 2860 -> 8-GPU node
    assert scenario_sites("primary") == SITES
