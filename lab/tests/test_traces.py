import pickle
from datetime import datetime

import numpy as np
import polars as pl
import pytest

from gridpilot.data import traces as T

ACME_SEREN = """job_id,user,node_num,gpu_num,cpu_num,type,state,submit_time,start_time,end_time,duration,queue,gpu_time
1,u1,1,8,128,Pretrain,CANCELLED,2023-03-01 00:18:22+08:00,2023-03-01 00:18:54+08:00,2023-03-01 02:18:54+08:00,7200,32,57600.0
2,u2,1,0,4,CPU,COMPLETED,2023-03-01 10:00:00+08:00,2023-03-01 10:00:01+08:00,2023-03-01 10:01:01+08:00,60,1,0.0
3,u3,1,1,8,Eval,PREEMPTED,2023-03-01 10:00:00+08:00,2023-03-01 10:00:01+08:00,2023-03-01 10:01:01+08:00,60,1,60.0
"""
ACME_KALOS = """job_id,user,node_num,gpu_num,cpu_num,mem_per_pod_GB,shared_mem_per_pod,type,state,submit_time,start_time,end_time,fail_time,stop_time,duration,queue,gpu_time
a,u1,8,64,960,1000,100.0,Other,NODE_FAIL,2023-05-17 11:00:58+00:00,2023-05-17 11:01:08+00:00,2023-05-17 11:01:16+00:00,2023-05-17 11:01:16+00:00,,8,10.0,512.0
"""
SPOT = """job_name,organization,gpu_model,cpu_request,gpu_request,worker_num,submit_time,duration,job_type
7,13,A100-SXM4-80GB,15.0,1.0,16,9589663.0,3600.0,Spot
"""


def test_acme_times_status_and_gpu_hours(tmp_path):
    path = tmp_path / "trace_seren.csv"
    path.write_text(ACME_SEREN)
    df = T.load_acme("seren", raw=path)
    assert df.columns == T.JOB_COLUMNS
    first = df.row(0, named=True)
    # +08:00 wall clock is kept as local time; the instant is UTC.
    assert first["submit_local"] == datetime(2023, 3, 1, 0, 18, 22)
    assert first["submit_ts"].isoformat().startswith("2023-02-28T16:18:22")
    assert first["status"] == "cancelled"
    assert first["gpu_hours"] == pytest.approx(16.0)  # 8 GPUs x 2 h
    assert df["status"].to_list() == ["cancelled", "completed", "preempted"]
    assert df.filter(pl.col("job_type") == "CPU")["gpu_hours"].item() == 0


def test_kalos_utc_times_map_to_cluster_local_time(tmp_path):
    path = tmp_path / "trace_kalos.csv"
    path.write_text(ACME_KALOS)
    row = T.load_acme("kalos", raw=path).row(0, named=True)
    assert row["submit_local"] == datetime(2023, 5, 17, 19, 0, 58)  # UTC+8
    assert row["status"] == "failed"  # NODE_FAIL counts as failed


def test_spot_gpu_count_is_per_worker_times_workers(tmp_path):
    path = tmp_path / "job_info_df.csv"
    path.write_text(SPOT)
    row = T.load_spot2026(raw=path).row(0, named=True)
    assert row["gpu_count"] == 16
    assert row["gpu_hours"] == pytest.approx(16.0)
    assert row["submit_local"] is None  # no time of day in this trace
    assert row["status"] == "unknown"


def test_power_unpickler_accepts_numpy_and_refuses_other_globals(tmp_path):
    good = tmp_path / "good.pkl"
    good.write_bytes(pickle.dumps([np.array([60.0, 400.0]), np.array([0.0, 100.0])]))
    with good.open("rb") as f:
        arrays = T._NumpyOnlyUnpickler(f).load()
    assert arrays[0].tolist() == [60.0, 400.0]

    bad = tmp_path / "bad.pkl"
    bad.write_bytes(pickle.dumps(datetime(2020, 1, 1)))
    with bad.open("rb") as f, pytest.raises(pickle.UnpicklingError):
        T._NumpyOnlyUnpickler(f).load()


def test_cdf_helpers():
    cdf = pl.DataFrame({"watts": [0.0, 100.0, 200.0], "cdf": [0.0, 0.5, 1.0]})
    assert T.cdf_quantile(cdf, 0.5) == pytest.approx(100.0)
    assert T.cdf_mean(cdf) == pytest.approx(150.0)
