"""Workload concentration export (Task 8 fix R9): how much of the energy and of a policy's
saving sits in the largest jobs. Read from a registered run's per-job accounting."""

import polars as pl
import pytest

from gridpilot import workload_profile as wp
from gridpilot.results import sealed_timestamps, unenveloped_numbers


def _acct(rows):
    return pl.DataFrame(rows, schema={"job_uid": pl.Utf8, "requested_gpu_s": pl.Float64,
                                      "energy_kwh": pl.Float64, "co2_kg": pl.Float64},
                        orient="row")


def _pair():
    # 100 jobs: one huge, 99 tiny. The huge job holds most energy and most of the saving.
    u = [("big", 3600.0 * 1000, 900.0, 500.0)] + [(f"j{i:02d}", 360.0, 1.0, 0.5)
                                                   for i in range(99)]
    p = [("big", 3600.0 * 1000, 900.0, 100.0)] + [(f"j{i:02d}", 360.0, 1.0, 0.4)
                                                   for i in range(99)]
    return _acct(u), _acct(p)


def test_shares_for_the_top_fraction():
    u, p = _pair()
    c = wp.concentration(u, p, qs=(0.01,))
    top = c["top"][0]
    assert top["n_jobs"] == 1
    assert top["gpu_h_share"] == pytest.approx(1000 / (1000 + 99 * 0.1))
    assert top["energy_share"] == pytest.approx(900 / (900 + 99))
    assert top["saving_share"] == pytest.approx(400 / (400 + 99 * 0.1))
    assert c["share_jobs_under_1_gpu_h"] == pytest.approx(0.99)
    assert c["median_gpu_h"] == pytest.approx(0.1)


def test_sets_must_match():
    u, p = _pair()
    with pytest.raises(ValueError, match="same jobs"):
        wp.concentration(u, p.filter(pl.col("job_uid") != "big"))


def test_artifact_is_enveloped():
    u, p = _pair()
    art = wp.build_artifact(u, p, policy="W", run_id="20261027T000000Z")
    assert unenveloped_numbers(art) == []
    assert sealed_timestamps(art) == []
    e = art["top"][1]
    assert e["energy_share"]["evidence"] == "simulated"
    assert e["gpu_h_share"]["evidence"] == "measured"
    assert art["policy"] == "W"
