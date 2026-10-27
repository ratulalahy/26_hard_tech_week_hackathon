"""Public GPU-cluster job traces, normalized to one job table.

Raw files live in data/raw/traces/<name>/ (see data/manifests/traces_<name>.json and
lab/scripts/recon_traces_download.py). Every loader returns one row per job with
the columns in JOB_COLUMNS. All values are `measured` (read from a real trace), except
`gpu_hours`, which is derived as gpu_count x run_s / 3600.

Time zones. The source clusters are in China (UTC+8, no DST). `submit_local` is the
wall-clock submission time at the cluster, used for hour-of-day and day-of-week
patterns:
- Acme Seren is written with +08:00 and Acme Kalos with +00:00; both are true instants.
- PAI 2020 times are shifted by an unknown constant. Read as Unix seconds in
  Asia/Shanghai they keep the true time of day and day of week but have fake dates
  (upstream README), so `submit_ts` is a pseudo-instant.
- Alibaba spot 2026 has seconds since the first submission only: no time of day.
"""

from __future__ import annotations

import io
import pickle
import tarfile
from functools import lru_cache
from pathlib import Path

import numpy as np
import polars as pl

from gridpilot.paths import RAW_DIR

TRACE_DIR = RAW_DIR / "traces"
CLUSTER_TZ = "Asia/Shanghai"

JOB_COLUMNS = [
    "trace",  # acme_seren | acme_kalos | pai2020 | spot2026
    "job_id",
    "user",
    "submit_ts",  # UTC instant (pseudo-instant for pai2020; offset seconds for spot2026)
    "submit_local",  # naive wall clock at the cluster (null for spot2026)
    "start_ts",
    "end_ts",
    "queue_s",
    "run_s",
    "gpu_count",  # GPUs requested; fractional for PAI GPU sharing
    "node_count",
    "gpu_type",
    "job_type",  # trace-specific workload label (see job_type_source)
    "job_type_source",
    "status",  # completed | failed | cancelled | preempted | unfinished | unknown
    "status_raw",
    "gpu_util",  # mean GPU utilization in [0, 1] if the trace has it, else null
    "gpu_hours",
]

_STATUS = {
    "COMPLETED": "completed",
    "FAILED": "failed",
    "TIMEOUT": "failed",
    "NODE_FAIL": "failed",
    "CANCELLED": "cancelled",
    "PREEMPTED": "preempted",
    "RUNNING": "unfinished",
    "Terminated": "completed",
    "Failed": "failed",
    "Running": "unfinished",
    "Waiting": "unfinished",
}


def _finish(df: pl.DataFrame) -> pl.DataFrame:
    df = df.with_columns(
        pl.col("status_raw").replace_strict(_STATUS, default="unknown").alias("status"),
        (pl.col("gpu_count") * pl.col("run_s") / 3600.0).alias("gpu_hours"),
    )
    for col in JOB_COLUMNS:
        if col not in df.columns:
            df = df.with_columns(pl.lit(None).alias(col))
    return df.select(JOB_COLUMNS)


def _read_tar_csv(archive: Path, header: Path, columns: list[str] | None = None) -> pl.DataFrame:
    """Read the single header-less CSV inside a PAI .tar.gz, naming columns from .header."""
    names = header.read_text().strip().split(",")
    with tarfile.open(archive, "r:gz") as tar:
        member = next(m for m in tar.getmembers() if m.name.endswith(".csv"))
        data = tar.extractfile(member).read()
    df = pl.read_csv(
        io.BytesIO(data), has_header=False, new_columns=names, infer_schema_length=100_000
    )
    return df.select(columns) if columns else df


# --------------------------------------------------------------------------- Acme


def load_acme(cluster: str = "seren", raw: Path | None = None) -> pl.DataFrame:
    """Acme (Shanghai AI Lab, NSDI '24): Seren (Mar-Aug 2023) or Kalos (May-Aug 2023).

    `type` is the operator's LLM-development label: Pretrain, SFT, MLLM, Eval, Debug,
    Other, CPU. CPU-only jobs are kept with gpu_count 0.
    """
    path = raw or TRACE_DIR / "acme" / f"trace_{cluster}.csv"
    df = pl.read_csv(path, infer_schema_length=100_000)
    ts = {c: pl.col(c).str.to_datetime("%Y-%m-%d %H:%M:%S%:z", time_zone="UTC") for c in
          ("submit_time", "start_time", "end_time")}
    df = df.with_columns(**{f"_{k}": v for k, v in ts.items()})
    out = df.select(
        pl.lit(f"acme_{cluster}").alias("trace"),
        pl.col("job_id").cast(pl.Utf8),
        pl.col("user"),
        pl.col("_submit_time").alias("submit_ts"),
        pl.col("_submit_time").dt.convert_time_zone(CLUSTER_TZ).dt.replace_time_zone(None)
        .alias("submit_local"),
        pl.col("_start_time").alias("start_ts"),
        pl.col("_end_time").alias("end_ts"),
        pl.col("queue").cast(pl.Float64).alias("queue_s"),
        pl.col("duration").cast(pl.Float64).alias("run_s"),
        pl.col("gpu_num").cast(pl.Float64).alias("gpu_count"),
        pl.col("node_num").cast(pl.Float64).alias("node_count"),
        pl.lit("A100-SXM-80GB").alias("gpu_type"),  # both clusters: 8x A100-SXM 80GB nodes (NSDI '24)
        pl.col("type").alias("job_type"),
        pl.lit("acme.type").alias("job_type_source"),
        pl.col("state").alias("status_raw"),
    )
    return _finish(out)


# ----------------------------------------------------------------------- PAI 2020


def _pai(name: str, columns: list[str] | None = None) -> pl.DataFrame:
    d = TRACE_DIR / "pai2020"
    return _read_tar_csv(d / f"{name}.tar.gz", d / f"{name}.header", columns)


@lru_cache(maxsize=1)
def _pai_tasks() -> pl.DataFrame:
    return _pai("pai_task_table")


def pai_job_util() -> pl.DataFrame:
    """Per-job GPU utilization from pai_sensor_table: sum of instance gpu_wrk_util over
    sum of instance plan_gpu (both in percent of one GPU). Lifetime averages per instance."""
    sensor = _pai(
        "pai_sensor_table", ["job_name", "task_name", "worker_name", "gpu_wrk_util"]
    )
    plan = _pai_tasks().select("job_name", "task_name", "plan_gpu")
    joined = sensor.join(plan, on=["job_name", "task_name"], how="inner").filter(
        pl.col("plan_gpu") > 0
    )
    return joined.group_by("job_name").agg(
        (pl.col("gpu_wrk_util").sum() / pl.col("plan_gpu").sum()).clip(0, 1).alias("gpu_util"),
        pl.len().alias("n_instances_sensed"),
    )


def load_pai2020(with_util: bool = True) -> pl.DataFrame:
    """Alibaba PAI GPU trace 2020 (NSDI '22): ~1.26 M jobs over ~2 months.

    Job submission is pai_job_table.start_time; the run is the span of its tasks
    (earliest task start to latest task end). GPU count is sum(plan_gpu/100 x inst_num)
    over tasks; gpu_type is the type of the largest GPU task. job_type is the role of the
    largest GPU task (task_name: tensorflow, PyTorchWorker, worker, ps, evaluator, ...),
    refined by the semantic `workload` tag where present (~9% of instances).
    """
    jobs = _pai("pai_job_table")
    tasks = _pai_tasks().with_columns(
        (pl.col("plan_gpu").fill_null(0) / 100.0 * pl.col("inst_num").fill_null(1)).alias("_gpus")
    )
    per_job = tasks.sort("_gpus", descending=True).group_by("job_name").agg(
        pl.col("_gpus").sum().alias("gpu_count"),
        pl.col("start_time").min().alias("_task_start"),
        # A job's run is known only if every task has an end time (mostly completed jobs).
        pl.when(pl.col("end_time").null_count() == 0)
        .then(pl.col("end_time").max())
        .alias("_task_end"),
        pl.col("gpu_type").first().alias("gpu_type"),
        pl.col("task_name").first().alias("_main_task"),
        pl.col("inst_num").sum().alias("_n_inst"),
    )
    tags = _pai("pai_group_tag_table", ["inst_id", "group", "workload", "gpu_type_spec"])
    tags = tags.group_by("inst_id").agg(
        pl.col("workload").drop_nulls().first(), pl.col("group").first()
    )
    df = jobs.join(per_job, on="job_name", how="left").join(tags, on="inst_id", how="left")
    if with_util:
        df = df.join(pai_job_util(), on="job_name", how="left")
    submit = pl.from_epoch(pl.col("start_time").cast(pl.Int64), time_unit="s").dt.replace_time_zone(
        "UTC"
    )
    out = df.select(
        pl.lit("pai2020").alias("trace"),
        pl.col("job_name").alias("job_id"),
        pl.col("user"),
        submit.alias("submit_ts"),
        submit.dt.convert_time_zone(CLUSTER_TZ).dt.replace_time_zone(None).alias("submit_local"),
        pl.from_epoch(pl.col("_task_start").cast(pl.Int64), time_unit="s")
        .dt.replace_time_zone("UTC").alias("start_ts"),
        pl.from_epoch(pl.col("_task_end").cast(pl.Int64), time_unit="s")
        .dt.replace_time_zone("UTC").alias("end_ts"),
        (pl.col("_task_start") - pl.col("start_time")).cast(pl.Float64).alias("queue_s"),
        (pl.col("_task_end") - pl.col("_task_start")).cast(pl.Float64).alias("run_s"),
        pl.col("gpu_count").cast(pl.Float64),
        pl.col("gpu_type"),
        pl.coalesce(pl.col("workload"), pl.col("_main_task")).alias("job_type"),
        pl.when(pl.col("workload").is_not_null()).then(pl.lit("pai.workload_tag"))
        .otherwise(pl.lit("pai.task_name")).alias("job_type_source"),
        pl.col("status").alias("status_raw"),
        (pl.col("gpu_util") if with_util else pl.lit(None, dtype=pl.Float64)).alias("gpu_util"),
    )
    return _finish(out)


def pai_groups() -> pl.DataFrame:
    """inst_id -> recurring-group tag (instances with the same scripts/inputs)."""
    return _pai("pai_group_tag_table", ["inst_id", "group", "workload"])


# ------------------------------------------------------------- Alibaba spot 2026


def load_spot2026(raw: Path | None = None) -> pl.DataFrame:
    """Alibaba cluster-trace-v2026-spot-gpu (ASPLOS '26): HP (strict SLO) vs Spot jobs.

    submit_time is seconds since the first submission; there is no status and no time
    of day, so submit_local is null. 3,588 HP jobs sit at t=0 (running before the trace
    began), so their durations are left-censored.
    """
    path = raw or TRACE_DIR / "alibaba_spot2026" / "job_info_df.csv"
    df = pl.read_csv(path)
    out = df.select(
        pl.lit("spot2026").alias("trace"),
        pl.col("job_name").cast(pl.Utf8).alias("job_id"),
        pl.col("organization").cast(pl.Utf8).alias("user"),
        pl.from_epoch(pl.col("submit_time").cast(pl.Int64), time_unit="s")
        .dt.replace_time_zone("UTC").alias("submit_ts"),
        pl.col("duration").cast(pl.Float64).alias("run_s"),
        (pl.col("gpu_request") * pl.col("worker_num")).cast(pl.Float64).alias("gpu_count"),
        pl.col("worker_num").cast(pl.Float64).alias("node_count"),
        pl.col("gpu_model").alias("gpu_type"),
        pl.col("job_type"),
        pl.lit("spot.job_type").alias("job_type_source"),
        pl.lit("n/a").alias("status_raw"),
    )
    return _finish(out)


# ------------------------------------------------------------ Acme power CDFs


class _NumpyOnlyUnpickler(pickle.Unpickler):
    """Unpickle numpy arrays only. The Acme util_pkl files reference nothing else
    (checked with pickletools); any other global is refused."""

    def find_class(self, module, name):
        try:
            from numpy._core.multiarray import _reconstruct
        except ImportError:  # numpy < 2
            from numpy.core.multiarray import _reconstruct
        allowed = {
            ("numpy.core.multiarray", "_reconstruct"): _reconstruct,
            ("numpy._core.multiarray", "_reconstruct"): _reconstruct,
            ("numpy", "ndarray"): np.ndarray,
            ("numpy", "dtype"): np.dtype,
        }
        if (module, name) not in allowed:
            raise pickle.UnpicklingError(f"refusing global {module}.{name}")
        return allowed[(module, name)]


ACME_POWER_CDFS = {
    # name: (file, pair index, description)
    "gpu_power_seren_w": ("gpu_power_seren.pkl", 0, "per-GPU board power, DCGM POWER_USAGE, Seren"),
    "gpu_power_kalos_w": ("gpu_power_kalos.pkl", 0, "per-GPU board power, DCGM POWER_USAGE, Kalos"),
    "gpu_server_power_w": ("server_power.pkl", 0, "8-GPU server total power, IPMI, Seren"),
    "cpu_server_power_w": ("server_power.pkl", 1, "CPU server total power, IPMI, Seren"),
}


def load_acme_power_cdf(name: str) -> pl.DataFrame:
    """Measured power CDF from Acme's processed util_pkl: columns watts, cdf (0..1).

    These are pooled over all sampled devices and times, idle ones included."""
    fname, pair, _ = ACME_POWER_CDFS[name]
    with (TRACE_DIR / "acme" / "util_pkl" / fname).open("rb") as f:
        arrays = _NumpyOnlyUnpickler(f).load()
    x, y = np.asarray(arrays[2 * pair], float), np.asarray(arrays[2 * pair + 1], float)
    return pl.DataFrame({"watts": x, "cdf": y / y.max()})


def cdf_quantile(cdf: pl.DataFrame, q: float) -> float:
    return float(np.interp(q, cdf["cdf"].to_numpy(), cdf["watts"].to_numpy()))


def cdf_mean(cdf: pl.DataFrame) -> float:
    x, f = cdf["watts"].to_numpy(), cdf["cdf"].to_numpy()
    return float(x[0] * f[0] + np.sum(x[1:] * np.diff(f)))


def load_all(with_util: bool = True) -> pl.DataFrame:
    """All traces, concatenated in the normalized schema."""
    frames = [load_acme("seren"), load_acme("kalos"), load_pai2020(with_util), load_spot2026()]
    return pl.concat(frames, how="vertical_relaxed")
