"""Task 7: the registered validation run (phase 0) and the results export; Stage 3 T10:
the same pipeline for the D-058 extension scenarios.

    cd lab && uv run python scripts/run_slice.py [--window validation|fallback]
                                                 [--scenario primary|<extension>]
                                                 [--forecast-run runs/forecast/<id>]
    cd lab && uv run python scripts/run_slice.py --window test [--rerun-reason "<text>"]

`run_pipeline(window, scenario, out_dir, export=...)` is the pure entry point (T10 Part A);
the CLI only builds its arguments. The primary scenario reproduces the registered run.
An extension scenario (`gridpilot.scenario.EXTENSIONS`) runs U, S, K, W, L (plus time-only
W and L where it has destinations) into `runs/ext/<name>/<UTC>/` and writes `summary.json`
there; it never exports into `results/`.

Pipeline (Task 7 amendment; spec §15 F11–F14):
1. jobs: `replay(init, F)` at phase 0;
2. bookings: U under the primary scenario plus the F14.1 U-changing scenarios;
3. common A (F13.2, F14.1), the cohort record written before any grid value is read;
4. the F14.6 scoring truth fill over [init, F), its mask and closure calendar;
5. the support pre-check (hard gate);
6. policies U, G, S, K, W, L, H and time-only W, L on the primary scenario; G, S, K, W, L
   and H with the F14.7 diagnostic, and G once more without it (ledgers must be identical);
7. accounting: score, relaxed bound and the bound check, weekly totals, the paired block
   bootstrap vs U, S and W, H2, influence, common support, the F4 coverage stratum;
8. export: `runs/slice/<UTC>/` (atomic) with config.json, canonical ledger/metrics hashes
   and input hashes; then all four artifacts are staged and renamed into `results/`;
9. timing.json (written last, export included), and the policy table on stdout.

The fallback window labels every b = 8 interval low-n and makes no H2 decision statement
(F14.4).

Outside `--window test`, all numbers are **validation** results and the sealed window is
never read.

**`--window test` (Stage 3 T11)** is the only way to open the sealed test window. It runs
`gridpilot.seal.authorize` (refusing, with a non-zero exit and the reason, unless (a) HEAD is
the freeze commit and the tree is clean, (b) config/freeze.json matches the annotated tag
`config-freeze`, (c) every input hash matches the freeze record, (d) results/test/ holds no
completed run unless `--rerun-reason` is given; B7: manifests are read from git), then runs
the primary scenario inside `gridpilot.seal.test_mode`: every grid read goes through
`sealed_read` and is logged in results/test_reads.jsonl. The test truth is built into
processed/carbon/carbon_hourly_test.parquet; forecasts are fitted at 2025-10-29 with the frozen
L configuration; S's ranking comes from the freeze record. Outputs: `runs/test/<UTC>/` and
results/test/*.json (the same schema plus `window: "test"`, and the test grid and workload
profiles).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl

from gridpilot import forecast as fcmod
from gridpilot import grid_profile as gpmod
from gridpilot import seal
from gridpilot import workload_profile as wpmod
from gridpilot.cohort import SCENARIO_NOTES, SCENARIOS, ledger_hash, prefix_cohort
from gridpilot.data.eia_co2 import CARBON_PATH, CARBON_TEST_REL, build_carbon
from gridpilot.data.traces import TRACE_DIR
from gridpilot.data.truth_fill import (
    BALANCE_PATH,
    TIER_EVIDENCE,
    TIER_SOURCE,
    fill_mask,
    fill_truth,
    missing_hours,
    tier_counts,
)
from gridpilot.eval import (
    BOOTSTRAP_LABEL,
    BOUND_TOL_KG,
    TruthTable,
    common_support,
    fsum_by,
    h2_decision,
    influence,
    job_accounting,
    paired_block_bootstrap,
    relaxed_bound_jobs,
    score,
    support_check,
    weekly,
)
from gridpilot.paths import DATA_DIR, MANIFEST_DIR, REPO_ROOT, RESULTS_DIR
from gridpilot.results import (
    CLAIM_FRAME,
    IMPORT_CONVENTION,
    LIMIT_BOOKINGS_UNSIGNED,
    LIMIT_PHASES,
    LIMIT_SHADOW_U,
    LIMIT_TEST,
    LIMIT_VALIDATION_DEV,
    LIMIT_ZERO_MISSES,
    SCHEMA_VERSION,
    canonical_hash,
    check_claim_frame,
    env,
    iso,
    not_run,
    write_json_atomic,
)
from gridpilot.scenario import EXTENSIONS, PRIMARY_POLICIES, RunResult, Scenario, Window
from gridpilot.sim import (
    HOME,
    SITES,
    TRANSFER_S,
    CarbonSearch,
    G,
    S,
    U,
    closed_intervals,
    load_forecasts,
    simulate,
    tail_climatology,
)
from gridpilot.sim.power import GPU_KW, PUE, TRANSFER_FRACTION
from gridpilot.splits import drop_sealed
from gridpilot.workload import CYCLE_DAYS, cycle_stats, replay
from gridpilot.workload_profile import top_share as _top_share

log = logging.getLogger("run_slice")

# F14.7 blocked diagnostic: kept in the run (fix round 1 #4). `blocked` is read only from
# diagnosed runs.
DIAGNOSED_POLICIES = ("G", "S", "K", "W", "L", "H")
NOT_DIAGNOSED_REASON = "F14.7 is reported for G, S, K, W, L and H only"
FALLBACK_H2_REASON = "F14.4: the fallback makes no H2 decision statement"
TRACE_PATH = TRACE_DIR / "acme" / "trace_seren.csv"
SNAPSHOT_PATH = MANIFEST_DIR / "snapshot.json"

H1 = timedelta(hours=1)
WINDOW_NAMES = ("validation", "fallback", "test")
REFUSED_RC = 4  # `--window test` refused by the seal (the reason is on stderr)
RANK_TRAIN = (datetime(2022, 1, 1, tzinfo=UTC), datetime(2024, 10, 29, tzinfo=UTC))
PHASE_DAYS = 0  # the registered primary phase (Scenario.primary().phase_days)
POLICY_ORDER = PRIMARY_POLICIES
EXT_NOT_DIAGNOSED_REASON = "extension runs do not run the F14.7 blocked diagnostic"
REFERENCES = ("U", "S", "W")
BLOCKS = (2, 4, 8)
SNAPSHOT_ID = "05efabe781cc"  # the registered validation run's snapshot
# Snapshots a validation run may cite: the registered one, and its T11 refresh (B7), which
# changes only openmeteo (now final). The test run cites the freeze record's, read from git.
ACCEPTED_SNAPSHOT_IDS = {
    SNAPSHOT_ID: "registered validation snapshot (openmeteo still growing)",
    "8a1b36b24b91": "T11 refresh: openmeteo final; every other manifest byte-identical",
}
EIA_CI_PROVENANCE = "EIA's estimated consumption-basis hourly CO₂ intensity"
S_RANK_PROVENANCE = f"means of {EIA_CI_PROVENANCE}, 2022-01-01 to 2024-10-29"
TIME_ONLY_SITES = Scenario.primary().time_only_sites()
POLICY_NOTES = {
    "U": "earliest feasible execution at PACE (FIFO); local operational reference",
    "G": "earliest finish across core sites; no carbon input",
    "S": "fixed clean-region priority by training mean consumed CI",
    "K": "carbon reservation search on frozen calendar climatology",
    "W": "carbon reservation search on weekly seasonal forecasts",
    "L": "carbon reservation search on the learned forecasts (H2 candidate)",
    "H": "same search on realized (filled) truth; hindsight diagnostic, never a contender",
    "W_time": "W restricted to PACE (destination capacity 0): time-only",
    "L_time": "L restricted to PACE (destination capacity 0): time-only",
}


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True,
                          check=False).stdout.strip()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Timer:
    def __init__(self):
        self.t: dict[str, float] = {}

    def __call__(self, name):
        timer = self

        class _T:
            def __enter__(self):
                self.t0 = time.perf_counter()

            def __exit__(self, *exc):
                timer.t[name] = timer.t.get(name, 0.0) + time.perf_counter() - self.t0
                log.info("%s: %.1f s", name, timer.t[name])
        return _T()


class RemoteProbe:
    """Wraps a policy; at each flexible job's arrival, records the earliest on-time feasible
    start at every legal site in the capacity the policy sees (bookings held, its own
    released). Used on the U replay for the §11 illustrative-job rule."""

    def __init__(self, inner):
        self.inner, self.name = inner, inner.name
        self.actions: dict[str, dict[str, int]] = {}

    def choose(self, job, now, capacities, ctx):
        if job.flexible:
            acts = {}
            for site in ctx.legal_sites(job):
                s = ctx.earliest_start(job, site, capacities, latest=job.latest_start_us)
                if s is not None:
                    acts[site] = s
            if any(site != ctx.home for site in acts):
                self.actions[job.job_uid] = acts
        return self.inner.choose(job, now, capacities, ctx)


def _gpu_h(frame: pl.DataFrame) -> float:
    """Declared GPU-hours: math.fsum of gpus × duration_s (order-free; T10), / 3600."""
    return math.fsum((frame["gpus"] * frame["duration_s"]).to_list()) / 3600


def _us_dt(us: int) -> datetime:
    return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(microseconds=int(us))


def _dt_us(t: datetime) -> int:
    return (t - datetime(1970, 1, 1, tzinfo=UTC)) // timedelta(microseconds=1)


# --------------------------------------------------------------------------- pipeline


def s_ranking(window: Window | None = None) -> tuple[list[str], dict[str, float]]:
    """S's ranking: mean consumed CI over the training rows, ascending (PACE included).
    A lazy scan with the seal and the training filter, so no other row is loaded. With the
    test window: read from the freeze record (T11 B2), never recomputed in the test run."""
    if window is not None and window.is_test:
        fz = seal.require_active("s_ranking(test)").freeze
        means = fz.raw["s_ranking"].get("mean_consumed_ci_g_kwh") or {}
        return fz.s_order, {b: float(v) for b, v in means.items()}
    rows = (drop_sealed(pl.scan_parquet(CARBON_PATH))
            .filter((pl.col("ts_utc") >= RANK_TRAIN[0]) & (pl.col("ts_utc") < RANK_TRAIN[1])
                    & pl.col("ba").is_in(list(SITES)))
            .select("ba", "ts_utc", "ci_consumed_g_kwh").collect()
            .drop_nulls("ci_consumed_g_kwh").sort("ba", "ts_utc"))
    # Means as math.fsum / n, not a parallel group_by mean (T10 fix r1 M-4).
    means = {}
    for (ba,), g in rows.partition_by("ba", as_dict=True, maintain_order=True).items():
        v = g["ci_consumed_g_kwh"].to_list()
        means[ba] = math.fsum(v) / len(v)
    order = sorted(means, key=lambda b: (means[b], b))
    return order, {b: means[b] for b in order}


def bound_gap(acc: pl.DataFrame, per: pl.DataFrame) -> dict:
    """Cohort gap as math.fsum of per-job (policy − bound) differences (T6 #12). The job
    sets of the ledger and the bound must be identical."""
    if set(acc["job_uid"].to_list()) != set(per["job_uid"].to_list()):
        raise AssertionError("bound and ledger cover different job sets")
    j = acc.select("job_uid", "co2_kg").join(per.select("job_uid", pl.col("co2_kg").alias("b")),
                                             on="job_uid", how="inner")
    if j.height != acc.height:
        raise AssertionError("bound and ledger cover different jobs")
    d = (j["co2_kg"] - j["b"]).to_numpy()
    gap = math.fsum(d.tolist())
    return {"gap_kg": gap, "min_job_gap_kg": float(d.min()) if d.size else 0.0,
            "n_job_gap_lt0": int((d < 0).sum()), "ok": gap >= -BOUND_TOL_KG}


def _tail(fc_dir, window: Window | None = None):
    """The frozen K tail from the pinned run's climatology.parquet (checked by Task 5
    against that run's K rows)."""
    return tail_climatology(fc_dir, list(SITES), window=window)


def build_policies(ranking, fc_dir, filled, mask, scenario: Scenario | None = None,
                   window: Window | None = None):
    """Each policy in `scenario.policies()` is built once per run, with the scenario's
    sites (time-only variants: PACE only). K/W/L read the pinned forecast run `fc_dir`;
    H reads the F14.6 filled truth; all get the mask the closure calendar came from."""
    scenario = scenario or Scenario.primary()
    sites, t_sites = scenario.sites(), scenario.time_only_sites()
    forecasts = load_forecasts(fc_dir, window=window)
    tail = _tail(fc_dir, window)

    def search(sig, time_only=False):
        p = CarbonSearch(sig, forecasts, None, mask, tail=tail, window=window)
        if time_only:
            p.name = f"{sig}_time"
        return p, (t_sites if time_only else sites)

    make = {
        "U": lambda: (U(), sites), "G": lambda: (G(), sites), "S": lambda: (S(ranking), sites),
        "K": lambda: search("K"), "W": lambda: search("W"), "L": lambda: search("L"),
        "H": lambda: (CarbonSearch("H", None, filled, mask, truth_col="ci_g_kwh",
                                   window=window), sites),
        "W_time": lambda: search("W", True), "L_time": lambda: search("L", True),
    }
    out = {n: make[n]() for n in scenario.policies()}
    coverage = CarbonSearch("L", forecasts, None, mask, tail=tail,
                            window=window)  # coverage only (F4)
    return out, coverage


def in_coverage(cj, bookings, cov, sites=SITES) -> set[str]:
    f = cj.select("job_uid", pl.col("arrival_ts").dt.epoch("us").alias("a"), "gpus",
                  "mobile").join(bookings.select("job_uid", "deadline_us"), on="job_uid") \
        .sort("a", "job_uid")
    remote = sorted(s for s in sites if s != HOME)
    out = set()
    for uid, a, g, mob, dl in f.iter_rows():
        legal = [HOME] + ([s for s in remote if sites[s] >= g] if mob else [])
        if all(dl <= cov.coverage_end_us(a, s) for s in legal):
            out.add(uid)
    return out


def default_root(scenario: Scenario, window: Window | None = None) -> Path:
    if window is not None and window.is_test:
        return REPO_ROOT / seal.TEST_RUNS_REL
    if scenario.is_primary:
        return REPO_ROOT / "runs" / "slice"
    return REPO_ROOT / "runs" / "ext" / scenario.name


def run_pipeline(window: Window, scenario: Scenario, out_dir: Path | str | None = None, *,
                 export: bool, forecast_run: Path | str | None = None) -> RunResult:
    """One run of `scenario` on `window` into its own run directory `<out_dir>/<UTC>/`
    (default `default_root(scenario)`), written atomically. `export` copies the primary
    run's four artifacts into `results/`; an extension never exports there.
    `forecast_run` pins a Task 2 forecast run instead of building forecasts."""
    if not isinstance(window, Window) or not isinstance(scenario, Scenario):
        raise TypeError("run_pipeline needs a Window and a Scenario")
    if export and not scenario.is_primary:
        raise ValueError(f"scenario {scenario.name!r} is a sensitivity: it never exports "
                         f"into results/ (only the registered primary does)")
    if window.is_test:
        ses = seal.require_active("run_pipeline(test)")
        if not scenario.is_primary:
            raise ValueError("the test window runs the registered primary scenario only")
        if forecast_run is not None:
            raise ValueError("the test run builds its own forecasts (frozen configuration); "
                             "--forecast-run cannot be pinned on test")
    timer = Timer()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    if window.is_test:
        ses.run_id = run_id
        seal.log_event("run_start", run_id=run_id, scenario=scenario.name)
    root = Path(out_dir) if out_dir else default_root(scenario, window)
    root.mkdir(parents=True, exist_ok=True)
    tmp = root / f".tmp-{run_id}-{os.getpid()}"
    final = root / run_id
    tmp.mkdir()
    if window.is_test:
        # Check (a) verified HEAD and a clean tree at authorization; the read log has been
        # appended to since, so the live status is not the code's.
        sha, status = ses.auth.code_commit, ""
        (tmp / "git.txt").write_text(f"sha {sha}\nstatus: clean at authorization (seal check "
                                     f"(a)); freeze commit {ses.freeze.freeze_commit}\n")
    else:
        sha = _git("rev-parse", "HEAD")
        status = _git("status", "--porcelain")
        (tmp / "git.txt").write_text(f"sha {sha}\nstatus:\n{status}\n")
    fc = Path(forecast_run) if forecast_run else None
    try:
        rc, info = _pipeline(window, scenario, fc, timer, tmp, run_id, sha, status)
        os.rename(tmp, final)
    except BaseException:
        failed = root / f"failed-{run_id}"
        os.rename(tmp, failed)
        log.error("run failed; partial outputs in %s", failed)
        raise
    print(f"run directory: {final}")
    exported = False
    if rc == 0 and export:
        if window.is_test:
            dst = ses.auth.test_results_dir
            export_results(final / "results", dst, ARTIFACTS_TEST)
            seal.log_event("export", run_id=run_id, results=str(dst),
                           artifacts=list(ARTIFACTS_TEST))
        else:
            export_results(final / "results", RESULTS_DIR)
        exported = True
    return RunResult(run_id=run_id, run_dir=final, rc=rc, window=window, scenario=scenario,
                     exported=exported, **info)


ARTIFACTS = ("manifest.json", "metrics.json", "forecast-replay.json", "job-replay.json")
# The test run also writes its own grid and workload profiles; manifest.json goes last, as the
# completion marker check (d) looks for.
ARTIFACTS_TEST = ("metrics.json", "forecast-replay.json", "job-replay.json", "grid-profile.json",
                  "workload-profile.json", "manifest.json")


def export_results(src: Path, dst: Path, artifacts: tuple[str, ...] = ARTIFACTS) -> None:
    """Stage all artifacts next to `dst`, then rename them into place, so a failure
    while copying never leaves a mix of old and new files."""
    missing = [a for a in artifacts if not (src / a).exists()]
    if missing:
        raise FileNotFoundError(f"run results are missing {missing}")
    dst.mkdir(parents=True, exist_ok=True)
    staged = []
    try:
        for a in artifacts:
            tmp = dst / f".{a}.{os.getpid()}.staged"
            shutil.copyfile(src / a, tmp)
            staged.append((tmp, dst / a))
        for tmp, final in staged:
            os.replace(tmp, final)
    finally:
        for tmp, _ in staged:
            tmp.unlink(missing_ok=True)
    print(f"exported {len(artifacts)} artifacts to {dst}")


def _write_parquet_hashed(frame: pl.DataFrame, path: Path, hashes: dict) -> None:
    frame.write_parquet(path)
    hashes[path.name] = _sha256(path)


def _candidates_frame(probe: RemoteProbe, cj: pl.DataFrame) -> pl.DataFrame:
    """The §11 eligible set: flexible jobs with a feasible remote action in the U replay,
    with declared GPU-h and the earliest feasible start (µs) at each site (null = none)."""
    uids = sorted(probe.actions)
    cols = {"job_uid": uids}
    for site in SITES:
        cols[f"earliest_start_us_{site}"] = [probe.actions[u].get(site) for u in uids]
    frame = pl.DataFrame(cols, schema={"job_uid": pl.Utf8,
                                       **{f"earliest_start_us_{s}": pl.Int64 for s in SITES}})
    gh = cj.select("job_uid", (pl.col("gpus") * pl.col("duration_s") / 3600).alias("gpu_h"))
    return frame.join(gh, on="job_uid", how="left").select(
        "job_uid", "gpu_h", *[f"earliest_start_us_{s}" for s in SITES]).sort("job_uid")


def _cohort(warm_jobs, stream, F, scenario: Scenario):
    """F13.2 + F14.1. A is the minimum first failure over the registered F14.1 scenarios at
    this window and phase; the scored cohort and its bookings follow `scenario`. An
    extension whose knobs change the jobs is added as one more scenario for its own
    bookings, and must not move A (it only uses that common A)."""
    if _jobs_unchanged(scenario):  # U and its bookings do not see capacity or transfer
        return prefix_cohort(warm_jobs, stream, F, scenarios=SCENARIOS, sites=SITES)
    key = f"scored:{scenario.name}"
    coh = prefix_cohort(warm_jobs, stream, F, scenarios={**SCENARIOS, key: scenario.cohort_fn()},
                        sites=SITES, primary=key)
    hits = [t for n, t in coh.first_failure.items() if n != key and t is not None]
    a_common = min(hits) if hits else F
    if coh.A != a_common:
        raise AssertionError(f"{scenario.name}: A {coh.A} differs from the common F14.1 A "
                             f"{a_common}")
    return coh


def _jobs_unchanged(scenario: Scenario) -> bool:
    """True if the scenario leaves the job frame as the primary's (only phase, capacity or
    transfer differ), so the registered F14.1 set gives its cohort directly."""
    return (scenario.batch_delay_s == Scenario.primary().batch_delay_s
            and scenario.mobility_max_gpus is None)


def _pipeline(window: Window, scenario: Scenario, forecast_run: Path | None, timer, tmp, run_id,
              sha, status) -> tuple[int, dict]:
    init, eval_start, F = window.init, window.eval_start, window.F
    primary = scenario.is_primary
    sites, t_sites = scenario.sites(), scenario.time_only_sites()
    file_sha: dict[str, str] = {}
    test = window.is_test
    if test:
        ses = seal.require_active("the test pipeline")
        if ses.data_dir.resolve() != DATA_DIR.resolve():
            raise AssertionError(f"the authorized data dir {ses.data_dir} is not "
                                 f"GRIDPILOT_DATA_DIR {DATA_DIR}: every input must come from it")
        snapshot_id = ses.freeze.snapshot_id  # checked against git at HEAD by authorize (B7)
    else:
        snapshot_id = json.loads(SNAPSHOT_PATH.read_text())["snapshot_id"]
        if snapshot_id not in ACCEPTED_SNAPSHOT_IDS:
            raise AssertionError(f"data snapshot {snapshot_id} is not an accepted snapshot "
                                 f"{sorted(ACCEPTED_SNAPSHOT_IDS)}")

    # 0. Forecasts (Task 2): constructed fresh unless a run is given; pinned either way. The
    # test run first builds the test truth table (B2), then fits at 2025-10-29 with the frozen
    # L configuration.
    with timer("forecast_construction"):
        if test:
            carbon_test = build_carbon(window=window)
            fc_dir = fcmod.run_test(window, out_root=tmp / "forecast")
        elif forecast_run:
            fc_dir = Path(forecast_run)
        else:
            fc_dir = fcmod.run_validation(out_root=tmp / "forecast")
        forecasts = pl.read_parquet(fc_dir / "forecasts.parquet")
        fc_metrics = json.loads((fc_dir / "metrics.json").read_text())
    for c in ("issue_ts", "target_ts"):
        if forecasts[c].max() >= window.read_end:
            raise AssertionError("forecasts reach the seal (the window's read bound)")
    run_root = ("runs/test" if test else "runs/slice" if primary
                else f"runs/ext/{scenario.name}")
    fc_path = (str(fc_dir) if forecast_run
               else f"{run_root}/{run_id}/forecast/{fc_dir.name}")
    file_sha["forecasts.parquet"] = _sha256(fc_dir / "forecasts.parquet")
    file_sha["climatology.parquet"] = _sha256(fc_dir / "climatology.parquet")
    file_sha["balance.parquet"] = _sha256(BALANCE_PATH)
    if test:
        file_sha[Path(CARBON_TEST_REL).name] = _sha256(carbon_test)
        for rel, h in ses.auth.input_sha256.items():
            file_sha[f"input:{rel}"] = h
    else:
        file_sha["carbon_hourly.parquet"] = _sha256(CARBON_PATH)
    file_sha[TRACE_PATH.name] = _sha256(TRACE_PATH)

    # 1. Jobs.
    with timer("replay"):
        jobs = replay(init, F, phase_days=scenario.phase_days)
        warm_jobs = jobs.filter(pl.col("arrival_ts") < eval_start)
        stream = jobs.filter(pl.col("arrival_ts") >= eval_start)

    # 2–3. Bookings and the common A.
    with timer("bookings"):
        coh = _cohort(warm_jobs, stream, F, scenario)
    cj, bookings, warm = coh.jobs, coh.bookings, coh.warm
    wl = warm.ledger
    cohort_record = {
        "window": window.name, "phase_days": scenario.phase_days,
        "init": iso(init), "eval_start": iso(eval_start), "F": iso(F), "A": iso(coh.A),
        "first_failure": {k: iso(v) for k, v in coh.first_failure.items()},
        "n_stream": coh.n_stream, "n_cohort": cj.height, "n_excluded": coh.n_excluded,
        "excluded_gpu_h": coh.excluded_gpu_h,
        "cohort_ids_sha256": coh.ids_hash, "booking_sha256": coh.booking_hash,
        "prefix_bookings_unchanged": coh.prefix_unchanged,
        "drain": {"max_booking_end": iso(coh.max_booking_end),
                  "max_deadline": iso(coh.max_deadline), "drain_window": [iso(coh.A), iso(F)]},
        "warmup": {"n_jobs": wl.height,
                   "gpu_h": _gpu_h(wl),
                   "last_arrival": iso(_us_dt(warm.last_arrival_us)),
                   "last_completion": iso(wl["end_ts"].max())},
        "recorded_before_grid_scoring": True,
    }
    if not primary:
        cohort_record["scenario"] = scenario.name
    cohort_text = json.dumps(
        cohort_record | {"wallclock_written_at": datetime.now(UTC).isoformat()}, indent=1) + "\n"
    (tmp / "cohort.json").write_text(cohort_text)
    file_sha["cohort.json"] = hashlib.sha256(cohort_text.encode()).hexdigest()
    _write_parquet_hashed(bookings, tmp / "bookings.parquet", file_sha)
    log.info("A = %s, cohort %d jobs, %d excluded", coh.A, cj.height, coh.n_excluded)

    # 4. Scoring truth fill (F14.6).
    with timer("truth_fill"):
        filled = fill_truth(init, F, list(SITES), window=window)
        mask = fill_mask(filled)
        closed = closed_intervals(mask)
        tt = TruthTable(filled, mask, window=window)
    if any(closed.values()):
        # Bookings were built before the fill with no closures (F13.3 pre-check uses filled
        # truth); a non-empty calendar would require u_bookings(closed=...) first.
        raise AssertionError(f"closure calendar not empty after tier 4: {missing_hours(filled)}")
    tiers = tier_counts(filled)
    still_missing = missing_hours(filled)
    _write_parquet_hashed(filled, tmp / "truth_fill.parquet", file_sha)

    # 5. Support pre-check (hard gate).
    sc_b = support_check(bookings, tt, F, window=window)
    sc_w = support_check(wl, tt, F, window=window)
    support = {"bookings": {k: v for k, v in sc_b.items() if k != "failures"},
               "warmup_ledger": {k: v for k, v in sc_w.items() if k != "failures"}}
    if not (sc_b["ok"] and sc_w["ok"]):
        (tmp / "support_failure.json").write_text(json.dumps(
            {"bookings": sc_b, "warmup_ledger": sc_w}, indent=1, default=str))
        log.error("accounting-support failure: %s", support)
        return 2, {}

    # 6. Policies.
    ranking, rank_means = s_ranking(window)
    policies, cov = build_policies(ranking, fc_dir, filled, mask, scenario, window)
    ledgers: dict[str, pl.DataFrame] = {}
    probe = None
    for name in scenario.policies():
        pol, p_sites = policies[name]
        if name == "U" and primary:
            pol = probe = RemoteProbe(pol)
        kw = {"diagnose_blocked": True} if primary and name in DIAGNOSED_POLICIES else {}
        with timer(f"policy_{name}"):
            led = simulate(cj, pol, p_sites, bookings=bookings, warm=warm, closed=closed,
                           transfer_s=scenario.transfer_s, **kw)
        ledgers[name] = led
        _write_parquet_hashed(led, tmp / f"ledger_{name}.parquet", file_sha)
    ledger_sha = {n: ledger_hash(led) for n, led in ledgers.items()}
    if primary:
        # F14.7 cost and invariance: G once more without the diagnostic; placements match.
        with timer("policy_G_undiagnosed"):
            g_plain = simulate(cj, G(), sites, bookings=bookings, warm=warm, closed=closed,
                               transfer_s=scenario.transfer_s)
        if ledger_hash(g_plain) != ledger_sha["G"]:
            raise AssertionError("G's ledger differs with and without diagnose_blocked (F14.7)")
        cands = _candidates_frame(probe, cj)
        _write_parquet_hashed(cands, tmp / "illustrative_candidates.parquet", file_sha)

    # 7. Accounting.
    with timer("accounting"):
        acct = accounting(ledgers, policies, cj, bookings, warm, tt, eval_start, coh.A,
                          scenario=scenario)
        if primary:
            acct["stratum"] = stratum_estimates(ledgers, cj, bookings, cov, tt, eval_start,
                                                coh.A, sites=sites)
    repro = {"ledger_canonical_sha256": ledger_sha,
             "ledger_hash_rule": "sha256 over job_uid-sorted lines 'job_uid,site,start_us,end_us'",
             "file_sha256": file_sha, "snapshot_id": snapshot_id,
             "forecast_run": {"path": fc_path, "forecasts_sha256": file_sha["forecasts.parquet"]}}
    if primary:
        repro = {**repro, "g_ledger_equal_with_and_without_diagnose_blocked": True}
        repro = {k: repro[k] for k in ("ledger_canonical_sha256", "ledger_hash_rule",
                                       "g_ledger_equal_with_and_without_diagnose_blocked",
                                       "file_sha256", "snapshot_id", "forecast_run")}
    # 8. Export.
    info: dict = {"ledger_sha256": ledger_sha}
    metrics_canonical = summary_canonical = None
    hashes: dict[str, str] = {}
    with timer("export"):
        if primary:
            art = build_artifacts(
                window=window.name, win=window, run_id=run_id, sha=sha, status=status, init=init,
                eval_start=eval_start, F=F, coh=coh, cohort_record=cohort_record, tiers=tiers,
                still_missing=still_missing, support=support, ranking=ranking,
                rank_means=rank_means, ledgers=ledgers, acct=acct, cj=cj, bookings=bookings,
                tt=tt, filled=filled, forecasts=forecasts, fc_metrics=fc_metrics,
                fc_dir=fc_dir, fc_path=fc_path, probe=probe, cands=cands, warm=warm,
                timer=timer, repro=repro)
            out = tmp / "results"
            wj = {"window": window} if test else {}
            names = ["metrics.json", "forecast-replay.json", "job-replay.json"]
            if test:
                art["grid-profile.json"] = gpmod.build_profile(*gpmod.load_inputs(window),
                                                               window=window)
                art["workload-profile.json"] = workload_profile_for_test(ledgers, tt, run_id)
                names += ["grid-profile.json", "workload-profile.json"]
            for name in names:
                text = write_json_atomic(out / name, art[name], **wj)
                hashes[name] = hashlib.sha256(text.encode()).hexdigest()
            metrics_canonical = canonical_hash(art["metrics.json"])
            man = art["manifest.json"]
            man["artifact_sha256"] = hashes
            man["reproducibility"]["metrics_canonical_sha256"] = metrics_canonical
            man["timing_s"] = {k: env(v, "s", "measured", f"{run_id}:timing:{k}")
                               for k, v in timer.t.items()}
            check_claim_frame(man, window=window)
            write_json_atomic(out / "manifest.json", man, **wj)
            info["metrics_canonical_sha256"] = metrics_canonical
        else:
            summary = ext_summary(run_id=run_id, sha=sha, status=status, window=window,
                                  scenario=scenario, coh=coh, cj=cj, acct=acct,
                                  repro=repro, tiers=tiers)
            text = write_json_atomic(tmp / "summary.json", summary)
            hashes["summary.json"] = hashlib.sha256(text.encode()).hexdigest()
            summary_canonical = canonical_hash(summary)
            info["summary_canonical_sha256"] = summary_canonical
    config = {
        "run_id": run_id, "window": window.name, "git_sha": sha, "git_clean": status == "",
        "init": iso(init), "eval_start": iso(eval_start), "A": iso(coh.A), "F": iso(F),
        "phase_days": scenario.phase_days, "sites": sites, "time_only_sites": t_sites,
        "transfer_s": scenario.transfer_s, "kw_per_gpu": GPU_KW, "pue": PUE,
        "transfer_fraction": TRANSFER_FRACTION, "bound_tol_kg": BOUND_TOL_KG,
        "blocks": list(BLOCKS), "policies": list(scenario.policies()),
        "diagnosed_policies": list(DIAGNOSED_POLICIES) if primary else [],
        "s_ranking": ranking,
        "s_ranking_training_rows": [iso(RANK_TRAIN[0]), iso(RANK_TRAIN[1])],
        "scenarios_for_A": list(SCENARIOS), "reproducibility": repro,
        "metrics_canonical_sha256": metrics_canonical, "artifact_sha256": hashes,
        "scenario": scenario.config(),
    }
    if test:
        config["s_ranking_training_rows"] = [iso(t) for t in ses.freeze.s_window]
        config["freeze"] = _freeze_record(ses)
    if not primary:
        config["summary_canonical_sha256"] = summary_canonical
    (tmp / "config.json").write_text(json.dumps(config, indent=1) + "\n")
    print_table(acct, timer, scenario, window)
    # Written last, after export, so it includes the export time (fix round 1 #12).
    (tmp / "timing.json").write_text(json.dumps(
        {"run_id": run_id, "unit": "s", "evidence": "measured", "timing_s": timer.t},
        indent=1) + "\n")
    if not acct["bound_all_ok"]:
        log.error("feasible >= bound FAILED")
        return 3, info
    return 0, info


# --------------------------------------------------------------------------- accounting


def site_energy(acc: pl.DataFrame, sites) -> dict[str, float]:
    """Execution kWh by site: math.fsum over job_uid-sorted rows (T10 determinism; it was a
    parallel group_by sum)."""
    return {s: fsum_by(acc.filter(pl.col("site") == s), "execution_kwh") for s in sites}


def accounting(ledgers, policies, cj, bookings, warm, tt, eval_start, A, *,
               scenario: Scenario | None = None) -> dict:
    scenario = scenario or Scenario.primary()
    sites, t_sites = scenario.sites(), scenario.time_only_sites()
    per = relaxed_bound_jobs(cj, tt, bookings=bookings, sites=sites,
                             transfer_s=scenario.transfer_s)
    if per["co2_kg"].null_count():
        raise AssertionError("a cohort job has no legal action in the relaxed envelope")
    per_t = relaxed_bound_jobs(cj, tt, bookings=bookings, sites=t_sites,
                               transfer_s=scenario.transfer_s)
    bounds = {"primary": fsum_by(per, "co2_kg"), "time_only": fsum_by(per_t, "co2_kg")}
    scores, gaps, weeks = {}, {}, {}
    for name, led in ledgers.items():
        p_sites = policies[name][1]
        m = score(led, cj, tt, sites=p_sites, warm=warm)
        if m["fit_rejected_jobs"] != 0:  # the engine's F12.7 signal: nonzero is a bug
            raise AssertionError(f"{name}: {m['fit_rejected_jobs']} fit-rejected jobs")
        m["mobile_remote_share"] = mobile_remote_share(led, cj)
        acc = job_accounting(led, cj, tt)
        m["execution_kwh_by_site"] = site_energy(acc, sites)
        gaps[name] = {"primary": bound_gap(acc, per)}
        if name.endswith("_time"):
            gaps[name]["time_only"] = bound_gap(acc, per_t)
        if m["feasible"] and not all(g["ok"] for g in gaps[name].values()):
            log.error("%s: feasible but below the bound: %s", name, gaps[name])
        scores[name] = m
        weeks[name] = weekly(led, cj, tt, window=(eval_start, A))
    bound_all_ok = all(g["ok"] for n in gaps for g in gaps[n].values() if scores[n]["feasible"])
    contrasts = {}
    for ref in REFERENCES:
        if ref not in weeks:
            continue
        for name, wk in weeks.items():
            if name == ref:
                continue
            contrasts[f"{name}_vs_{ref}"] = {
                b: paired_block_bootstrap(weeks[ref], wk, block=b) for b in BLOCKS}
    h2 = h2_decision(weeks["W"], weeks["L"]) if "W" in weeks and "L" in weeks else None
    inf = influence({k: v for k, v in ledgers.items()}, cj, tt, k_list=(1, 5, 10))
    cs = common_support(ledgers, tt)
    n_weeks = weeks["U"].height
    return {"scores": scores, "gaps": gaps, "bounds": bounds, "bound_all_ok": bound_all_ok,
            "weeks": weeks, "contrasts": contrasts, "h2": h2, "influence": inf,
            "common_support": cs, "n_weeks": n_weeks, "bound_per_job": per}


def stratum_estimates(ledgers, cj, bookings, cov, tt, eval_start, A, *, sites=SITES) -> dict:
    """F4/F14.3: the coverage stratum is a pre-registered secondary estimate (no decision
    rule): its share of decision-relevant energy and the W − L intervals on it."""
    ids = in_coverage(cj, bookings, cov, sites)
    acc = job_accounting(ledgers["U"], cj, tt).join(cj.select("job_uid", "flexible"),
                                                     on="job_uid")
    flex = acc.filter(pl.col("flexible"))
    e_flex = fsum_by(flex, "execution_kwh")
    e_in = fsum_by(flex.filter(pl.col("job_uid").is_in(list(ids))), "execution_kwh")
    out = {"n_jobs": len(ids), "n_flexible": flex.height,
           "share_flexible_energy_in_coverage": e_in / e_flex if e_flex else None,
           "w_minus_l": None}
    if "W" in ledgers and "L" in ledgers and ids:
        sub = cj.filter(pl.col("job_uid").is_in(list(ids)))
        wk = {p: weekly(ledgers[p].filter(pl.col("job_uid").is_in(list(ids))), sub, tt,
                        window=(eval_start, A)) for p in ("W", "L")}
        out["w_minus_l"] = {b: paired_block_bootstrap(wk["W"], wk["L"], block=b)
                            for b in BLOCKS}
    return out


def mobile_remote_share(led, cj) -> float | None:
    m = led.join(cj.select("job_uid", "mobile"), on="job_uid").filter(pl.col("mobile"))
    return None if m.height == 0 else float((m["site"] != HOME).mean())


# --------------------------------------------------------------------------- export


EVIDENCE_POLICY = "simulated"
METRIC_UNITS = {
    "n_jobs": "jobs", "requested_gpu_s": "GPU_s", "completed_gpu_s": "GPU_s",
    "late_jobs": "jobs", "late_gpu_h": "GPU_h", "capacity_violations": "sites",
    "wait_p50_s": "s", "wait_p95_s": "s", "wait_max_s": "s", "wait_mean_s": "s",
    "execution_kwh": "kWh", "transfer_kwh": "kWh", "transfer_it_kwh": "kWh",
    "energy_kwh": "kWh", "kwh_share_tier_ge2": "fraction", "execution_co2_kg": "kg_CO2",
    "transfer_co2_kg": "kg_CO2", "co2_kg": "kg_CO2", "co2_kg_per_1000_gpu_h": "kg_CO2/1000_GPU_h",
    "moved_jobs": "jobs", "moved_share_jobs": "fraction", "moved_share_energy": "fraction",
    "remote_jobs": "jobs", "remote_energy_share": "fraction", "blocked_jobs": "jobs",
    "blocked_kwh": "kWh", "fit_rejected_jobs": "jobs", "fit_rejected_kwh": "kWh",
}


def _policy_record(name, m, gaps, run_id, *, diagnosed: bool | None = None,
                   not_diagnosed_reason: str = NOT_DIAGNOSED_REASON) -> dict:
    pid = f"{run_id}:{name}"
    diagnosed = name in DIAGNOSED_POLICIES if diagnosed is None else diagnosed
    rec = {"policy": name, "status": "ok", "reason": None, "note": POLICY_NOTES[name],
           "contender": name != "H", "feasible": bool(m["feasible"]),
           "conserved": bool(m["conserved"]),
           "metrics": {}}
    for k, unit in METRIC_UNITS.items():
        v = m.get(k)
        if k in ("blocked_jobs", "blocked_kwh") and not diagnosed:
            rec["metrics"][k] = not_run(unit, EVIDENCE_POLICY, f"{pid}:{k}",
                                        not_diagnosed_reason)
        elif v is None:
            rec["metrics"][k] = env(None, unit, EVIDENCE_POLICY, f"{pid}:{k}",
                                    status="unavailable", reason="undefined (zero denominator)")
        else:
            rec["metrics"][k] = env(v, unit, EVIDENCE_POLICY, f"{pid}:{k}")
    rec["metrics"]["mobile_remote_share"] = (
        env(m["mobile_remote_share"], "fraction", EVIDENCE_POLICY, f"{pid}:mobile_remote")
        if m.get("mobile_remote_share") is not None else
        env(None, "fraction", EVIDENCE_POLICY, f"{pid}:mobile_remote", "unavailable",
            "no mobile jobs"))
    rec["metrics"]["peak_gpus"] = {s: env(v, "GPUs", EVIDENCE_POLICY, f"{pid}:peak_gpus:{s}")
                                   for s, v in m["peak_gpus"].items()}
    rec["metrics"]["execution_kwh_by_site"] = {
        s: env(v, "kWh", EVIDENCE_POLICY, f"{pid}:execution_kwh:{s}")
        for s, v in m["execution_kwh_by_site"].items()}
    rec["bound_check"] = {
        basis: {"ok": g["ok"],
                "gap_kg": env(g["gap_kg"], "kg_CO2", "modeled", f"{pid}:bound_gap:{basis}"),
                "min_job_gap_kg": env(g["min_job_gap_kg"], "kg_CO2", "modeled",
                                      f"{pid}:min_job_gap:{basis}"),
                "n_job_gap_lt0": env(g["n_job_gap_lt0"], "jobs", "modeled",
                                     f"{pid}:n_job_gap_lt0:{basis}"),
                "tolerance_kg": env(BOUND_TOL_KG, "kg_CO2", "assumed", "F14.5:tolerance")}
        for basis, g in gaps.items()}
    return rec


def _interval(ci, unit, evidence, pid, null_reason="undefined") -> dict:
    if ci is None:
        return env(None, unit, evidence, pid, status="unavailable", reason=null_reason)
    return env(list(ci), unit, evidence, pid)


def _contrast_record(name, ref, by_b, run_id, n_weeks, window="validation") -> dict:
    """One paired contrast at every block length. b = 8 is labelled low-n when n ≤ 8, and
    always on the fallback window (F14.4)."""
    pid = f"{run_id}:{name}_vs_{ref}"
    out = {"candidate": name, "reference": ref, "method": BOOTSTRAP_LABEL,
           "definition": "reference − candidate (positive = candidate emits less); "
                         "saving = ratio of totals", "blocks": {}}
    for b, r in by_b.items():
        label = []
        if r["degenerate"]:
            label.append("degenerate (n_weeks <= block: interval collapses to the point)")
        if b == 8 and (n_weeks <= 8 or window == "fallback"):
            label.append("low-n")
        out["blocks"][str(b)] = {
            "primary": b == 4,
            "labels": label,
            "n_weeks": env(r["n_weeks"], "weeks", "measured", f"{pid}:b{b}:n_weeks"),
            "reps": env(r["reps"], "replicates", "assumed", "F12.4:reps"),
            "diff_kg": env(r["diff_kg"], "kg_CO2", "simulated", f"{pid}:b{b}:diff_kg",
                           *(("unavailable", "empty input") if r["diff_kg"] is None else ())),
            "diff_kg_ci95": _interval(r["diff_kg_ci"], "kg_CO2", "simulated",
                                      f"{pid}:b{b}:diff_kg_ci", "empty input"),
            "saving": env(r["saving"], "fraction", "simulated", f"{pid}:b{b}:saving",
                          *(("unavailable", "zero reference total") if r["saving"] is None
                            else ())),
            "saving_ci95": _interval(r["saving_ci"], "fraction", "simulated",
                                     f"{pid}:b{b}:saving_ci",
                                     r["saving_ci_null_reason"] or "undefined"),
        }
    return out


def _h2_record(h2, run_id, window="validation") -> dict:
    """H2 on the full phase-0 cohort (F14.3). The fallback window makes no H2 decision
    statement (F14.4): status not_evaluated, direction and decided null; the intervals are
    kept as estimates."""
    fallback = window == "fallback"
    return {"status": "not_evaluated" if fallback else "ok",
            "reason": FALLBACK_H2_REASON if fallback else h2["reason"],
            "population": "full phase-0 cohort (F14.3)",
            "statistic": h2["statistic"],
            "direction": None if fallback else h2["direction"],
            "decided": None if fallback else h2["decided"],
            "intervals_are": "estimates only" if fallback else "decision intervals (F13.4)",
            "n_weeks": env(h2["n_weeks"], "weeks", "measured", f"{run_id}:h2:n_weeks"),
            "intervals": {str(b): {
                "labels": ["low-n"] if int(b) == 8 and (fallback or h2["n_weeks"] <= 8)
                else [],
                "diff_kg": env(r["diff_kg"], "kg_CO2", "simulated", f"{run_id}:h2:b{b}:diff"),
                "diff_kg_ci95": _interval(r["diff_kg_ci"], "kg_CO2", "simulated",
                                          f"{run_id}:h2:b{b}:ci")}
                for b, r in h2["intervals"].items()}}


def _stratum_record(st, run_id, n_weeks, window="validation") -> dict:
    pid = f"{run_id}:stratum"
    out = {
        "definition": "jobs whose deadline lies inside issued forecast coverage (as of "
                      "arrival) at every legal site (F4); secondary estimate, no decision "
                      "rule (F14.3)",
        "status": "ok",
        "n_jobs": env(st["n_jobs"], "jobs", "simulated", f"{pid}:n"),
        "n_flexible_cohort": env(st["n_flexible"], "jobs", "assumed", f"{pid}:n_flex"),
        "share_flexible_energy_in_coverage": env(
            st["share_flexible_energy_in_coverage"], "fraction", "simulated", f"{pid}:share",
            *(("unavailable", "no flexible energy")
              if st["share_flexible_energy_in_coverage"] is None else ())),
    }
    if st["w_minus_l"] is None:
        out["w_minus_l"] = {"status": "unavailable", "reason": "empty stratum"}
    else:
        out["w_minus_l"] = _contrast_record("L", "W", st["w_minus_l"], f"{pid}", n_weeks,
                                            window)
    return out


def _weekly_record(weeks, run_id) -> dict:
    any_w = next(iter(weeks.values()))
    return {"week_start_local": [w.isoformat() for w in any_w["week"].to_list()],
            "tz": "America/Denver (Monday 00:00)",
            "co2_kg": {p: env(w["co2_kg"].to_numpy(), "kg_CO2", "simulated",
                              f"{run_id}:{p}:weekly_co2") for p, w in weeks.items()},
            "n_jobs": env(any_w["n_jobs"].to_numpy(), "jobs", "simulated",
                          f"{run_id}:weekly_n_jobs")}


def _flex_shares(cj, run_id) -> dict:
    gh = (cj["gpus"] * cj["duration_s"] / 3600).to_list()
    tot = math.fsum(gh)
    out = {}
    for flag in ("flexible", "mobile"):
        m = cj[flag]
        out[flag] = {"by_jobs": env(float(m.mean()), "fraction", "assumed",
                                    f"{run_id}:share_{flag}_jobs"),
                     "by_gpu_h": env(math.fsum(g for g, f in zip(gh, m, strict=True) if f)
                                     / tot, "fraction", "assumed",
                                     f"{run_id}:share_{flag}_gpu_h")}
    out["max_delay_s"] = {str(int(k)): env(int(v), "jobs", "assumed", f"{run_id}:delay_{k}")
                          for k, v in cj.group_by("max_delay_s").len().sort("max_delay_s")
                          .iter_rows()}
    return out


# D-058 cut items, each with its reason. The D-058 extensions that run (production basis,
# common support, phases 49 and 98, the five sensitivities) are in results/extensions.json;
# scripts/export_extensions.py adds any of them that missed the 21:00 hard stop (F9).
NOT_RUN_REASON = "cut by owner (D-058)"
NOT_RUN = [{"item": item, "reason": NOT_RUN_REASON} for item in (
    "shadow-U (no advance booking) sensitivity",
    "PUE, power, transfer-energy, idle-power and flexibility-share sensitivities",
    "1.25x home-capacity runs",
    "batch delay 0 h and transfer time 0 min sensitivities",
    "missingness-blind scheduling sensitivity")]

GREEDY_NOTE = ("Per-job greedy search, including hindsight H, is not a cohort optimum; holding "
               "scarce BPAT slots for cleaner hours pushes later jobs to dirtier sites.")


def _t(kg: float) -> str:
    t = kg / 1000
    return f"{0.0 if abs(t) < 0.05 else t:,.1f} t"  # no "-0.0 t"


def _ts(kg: float) -> str:
    """Signed tonnes: "+10.0 t", "-4.9 t", "0.0 t"."""
    t = kg / 1000
    return "0.0 t" if abs(t) < 0.05 else f"{t:+,.1f} t"


def framing_text(acct, window: str = "validation") -> str:
    """The validation (or test) reading of H3 and placement vs timing, every number from this
    run (fix round 1 #5). Each clause is chosen by the intervals, so it stays true."""
    c = acct["contrasts"]
    s = acct["scores"]

    def b4(cand, ref):
        r = c[f"{cand}_vs_{ref}"][4]
        return r["diff_kg"], r["diff_kg_ci"], r["saving"]

    dynamic = ("K", "W", "L")
    better, worse, same = [], [], []
    for p in dynamic:
        d, (lo, hi), _ = b4(p, "S")
        (better if lo > 0 else worse if hi < 0 else same).append((p, d, lo, hi))
    if better:
        head = ("; ".join(f"{p} emits less than S by {_t(d)} (b = 4 95% interval "
                          f"[{_t(lo)}, {_t(hi)}])" for p, d, lo, hi in better)
                + " (H3 supported for " + ", ".join(p for p, *_ in better) + ")")
    else:
        head = ("no dynamic carbon search (K, W, L) improves on the static clean-region "
                "ranking S (H3 not supported)")
    parts = [head]
    for p, d, lo, hi in worse:  # stated as candidate − S, so "more" is positive (C4)
        parts.append(f"{p} emits more than S ({_t(-d)} more; {p} − S = {_ts(-d)}, b = 4 95% "
                     f"interval [{_ts(-hi)}, {_ts(-lo)}]; the interval excludes zero)")
    if same:
        ps = [p for p, *_ in same]
        names = ps[0] if len(ps) == 1 else ", ".join(ps[:-1]) + " and " + ps[-1]
        detail = "; ".join(f"{p} − S = {_ts(-d)} [{_ts(-hi)}, {_ts(-lo)}]"
                           for p, d, lo, hi in same)
        parts.append(f"{names} {'is' if len(same) == 1 else 'are'} not distinguishable from S "
                     f"({detail})")
    t_save = [b4(p, "U")[2] for p in ("W_time", "L_time")]
    by_site = s["L"]["execution_kwh_by_site"]
    remote = {k: v for k, v in by_site.items() if k != HOME}
    top = max(remote, key=remote.get)
    share = remote[top] / sum(remote.values()) if sum(remote.values()) else 0.0
    l_save = b4("L", "U")[2]
    lead = "Test year" if window == "test" else "Validation"
    return (f"{lead}: {'; '.join(parts)}. Waiting in Utah alone saves about "
            f"{100 * sum(t_save) / 2:.1f}% (W_time {100 * t_save[0]:.2f}%, L_time "
            f"{100 * t_save[1]:.2f}% vs U); the saving comes from moving work (L "
            f"{100 * l_save:.2f}% vs U), mostly to {top} ({100 * share:.0f}% of L's remote "
            f"execution energy).")


def top_share(cj: pl.DataFrame, frac: float = 0.01) -> dict:
    """Energy share of the top `frac` of cohort jobs by declared GPU-h (ties to job_uid).
    Execution energy is 0.60 kW × PUE 1.20 per GPU-h for every job and policy, so the energy
    share equals the declared GPU-h share."""
    t = _top_share(cj.select("job_uid", (pl.col("gpus") * pl.col("duration_s") / 3600)
                             .alias("gpu_h")), frac)
    return {"n_jobs": t["n_jobs"], "n_cohort": t["n_cohort"], "gpu_h": t["gpu_h"],
            "energy_kwh": t["gpu_h"] * GPU_KW * PUE, "share": t["share"]}


def _workload_summary(cj, run_id) -> dict:
    t = top_share(cj)
    pid = f"{run_id}:workload:top1pct"
    return {"top_1pct_jobs_by_declared_gpu_h": {
        "definition": "the ceil(1%) of cohort jobs with the largest declared GPU-hours (ties "
                      "to job_uid); their share of cohort execution energy (equal to their "
                      "share of declared GPU-h, since every GPU-h carries 0.60 kW x PUE 1.20)",
        "n_jobs": env(t["n_jobs"], "jobs", "simulated", f"{pid}:n"),
        "energy_kwh": env(t["energy_kwh"], "kWh", "simulated", f"{pid}:kwh"),
        "energy_share": env(t["share"], "fraction", "simulated", f"{pid}:share",
                            *(("unavailable", "empty cohort") if t["share"] is None else ())),
    }}


def headline_wording(m) -> str:
    """F7 headline with the F12.5 frame; transfer energy is simulated (fix round 1 #6a)."""
    return ("attributed operational CO₂ (EIA consumption basis, modeled), including "
            f"{m['transfer_kwh'] / 1000:,.1f} MWh of simulated transfer energy; "
            "baseline-relative deadlines, exact declared runtimes; runtime uncertainty untested")


def _freeze_record(ses) -> dict:
    """What the test artifacts carry about the freeze and the logged entry point."""
    fz = ses.freeze
    return {"freeze_commit": fz.freeze_commit, "freeze_sha256": fz.sha256,
            "tag": seal.FREEZE_TAG, "wallclock_frozen_at": fz.raw["frozen_at"],
            "deployed_policy": fz.deployed_policy, "test_F": iso(fz.test_F),
            "validation_run": fz.raw["validation_run"], "rerun_reason": ses.auth.rerun_reason,
            "read_log": seal.READ_LOG_REL, "session": ses.session_id,
            "code_commit": ses.auth.code_commit}


def workload_profile_for_test(ledgers, tt, run_id, policy: str = "W") -> dict:
    """results/test/workload-profile.json from the in-memory ledgers and test truth (the test
    run never re-reads its own truth_fill.parquet outside the context)."""
    from gridpilot.eval import job_accounting as ja

    u = ledgers["U"]
    jobs = u.select("job_uid", pl.col("job_uid").str.split("#").list.first().alias("source_id"),
                    "arrival_ts", "gpus", "duration_s")
    art = wpmod.build_artifact(ja(u, jobs, tt), ja(ledgers[policy], jobs, tt), policy=policy,
                               run_id=run_id)
    return {**art, "window": "test"}




def build_artifacts(**k) -> dict:
    run_id, coh, acct = k["run_id"], k["coh"], k["acct"]
    scores, gaps = acct["scores"], acct["gaps"]
    cj = k["cj"]
    n_weeks = acct["n_weeks"]
    window = k["window"]
    win: Window = k.get("win") or Window.named(window)
    test = win.is_test
    ses = seal.require_active("test artifacts") if test else None

    # metrics.json
    policies = {name: _policy_record(name, scores[name], gaps[name], run_id)
                for name in POLICY_ORDER}
    contrasts = [_contrast_record(name, ref, acct["contrasts"][f"{name}_vs_{ref}"], run_id,
                                  n_weeks, window)
                 for ref in REFERENCES for name in POLICY_ORDER if name != ref]
    inf = acct["influence"]
    influence_rec = {
        "reference": inf["reference"], "rank_by": "declared GPU-hours per unique source attempt",
        "by_k": {str(kk): {
            "removed_sources": d["removed_sources"],
            "removed_jobs": env(d["removed_jobs"], "jobs", "simulated", f"{run_id}:inf:{kk}:n"),
            "saving_vs_U": {p: env(v["saving"], "fraction", "simulated",
                                   f"{run_id}:inf:{kk}:{p}",
                                   *(("unavailable", "zero reference") if v["saving"] is None
                                     else ()))
                            for p, v in d["vs_reference"].items()}}
            for kk, d in inf["by_k"].items()}}
    metrics = {
        "schema_version": SCHEMA_VERSION, "run_id": run_id, "window": window,
        "evidence_note": ("test-year results (sealed window, opened once after the freeze); "
                          if test else "validation results; ")
                         + "policy outcomes (CO₂, execution and transfer energy) simulated; "
                           "bound modeled",
        "covered": {"arrivals": [iso(k["eval_start"]), iso(coh.A)],
                    "drain": [iso(coh.A), iso(k["F"])]},
        "cohort": {
            "n_jobs": env(cj.height, "jobs", "simulated", f"{run_id}:cohort:n"),
            "declared_gpu_h": env(_gpu_h(cj), "GPU_h",
                                  "measured", f"{run_id}:cohort:gpu_h"),
            "n_excluded": env(coh.n_excluded, "jobs", "simulated", f"{run_id}:cohort:excluded"),
            "excluded_gpu_h": env(coh.excluded_gpu_h, "GPU_h", "measured",
                                  f"{run_id}:cohort:excluded_gpu_h"),
            "n_weeks": env(n_weeks, "weeks", "measured", f"{run_id}:n_weeks"),
            "flex_shares": _flex_shares(cj, run_id),
        },
        "workload": _workload_summary(cj, run_id),
        "policies": policies,
        "headline_wording": {p: headline_wording(scores[p]) for p in POLICY_ORDER},
        "relaxed_bound": {
            "primary": env(acct["bounds"]["primary"], "kg_CO2", "modeled", f"{run_id}:bound"),
            "time_only": env(acct["bounds"]["time_only"], "kg_CO2", "modeled",
                             f"{run_id}:bound_time_only"),
            "note": "C_relaxed: a lower bound (never a ceiling); its possible reduction belongs "
                    "in the evidence drawer only (F7)",
            "all_feasible_policies_ok": acct["bound_all_ok"],
        },
        "contrasts": contrasts,
        "h2": _h2_record(acct["h2"], run_id, window),
        "influence": influence_rec,
        "common_support": {
            "n_dropped_jobs": env(len(acct["common_support"]), "jobs", "simulated",
                                  f"{run_id}:common_support"),
            "status_rerun": "not_run",
            "reason": ("the test window runs the registered primary scenario only; the "
                       "common-support rerun is not part of the test run" if test else
                       "the common-support sensitivity rerun is scheduled after 18:00 (Task 7 "
                       "amendment step 7)")},
        "weekly": _weekly_record(acct["weeks"], run_id),
        "coverage_stratum": _stratum_record(acct["stratum"], run_id, n_weeks, window),
        "framing": {
            "placement_vs_timing": framing_text(acct, window),
            "greedy_search": GREEDY_NOTE,
            "h_is_diagnostic": "H uses realized (filled) truth; it is never a contender",
        },
    }

    # forecast-replay.json and job-replay.json
    frep = forecast_replay(k)
    jrep = job_replay(k)
    if test:
        frep["window"] = jrep["window"] = "test"

    # manifest.json: the test run reads the manifest hashes from git at HEAD (B7)
    m_inputs = (dict(ses.auth.manifests_sha256) if test else
                {p.name: _sha256(p) for p in sorted(MANIFEST_DIR.glob("*.json"))})
    tiers = k["tiers"]
    repro = k["repro"]
    t = k["timer"].t
    manifest = {
        "schema_version": SCHEMA_VERSION, "run_id": run_id, "git_sha": k["sha"],
        "git_clean": k["status"] == "", "snapshot_id": repro["snapshot_id"],
        "wallclock_generated_at": datetime.now(UTC).isoformat(),
        "reproduce": ("cd lab && uv run python scripts/run_slice.py --window test  # once, "
                      "after the freeze; refuses otherwise" if test else
                      f"make slice  # cd lab && uv run python scripts/run_slice.py --window "
                      f"{window}"),
        "evidence_scope": ("sealed test-window results [2025-11-01, F_test), opened once "
                           "through the logged entry point after the configuration freeze; "
                           "every read is in results/test_reads.jsonl" if test else
                           "validation (selection) results; the sealed test window "
                           "[2025-11-01, 2026-11-01) is never read"),
        "claim_frame": CLAIM_FRAME,
        "limitations": [
            fcmod.LIMITATION, IMPORT_CONVENTION, LIMIT_ZERO_MISSES, LIMIT_BOOKINGS_UNSIGNED,
            LIMIT_SHADOW_U, LIMIT_PHASES, LIMIT_TEST if test else LIMIT_VALIDATION_DEV,
            "EIA's 2025-26 emission factors may be a provisional vintage (F7).",
            ("Baseline bookings are an assumed advance-reservation calendar synthesized from "
             "the whole U replay (F11, F12.7); the result is not a historical online-router "
             "claim."),
            ("Missing truth hours are filled by the pre-registered F14.6 tiers; the closure "
             "calendar is an assumed advance-known calendar (F12.1)."),
        ],
        "inputs": {"data_manifests_sha256": m_inputs,
                   "carbon_hourly_sha256": repro["file_sha256"][
                       "carbon_hourly_test.parquet" if test else "carbon_hourly.parquet"],
                   "forecast_run": k["fc_path"],
                   "forecast_run_forecasts_sha256": repro["forecast_run"]["forecasts_sha256"],
                   "forecast_run_pinned": "K/W/L forecasts and the K tail climatology are "
                                          "read from this one run directory",
                   "forecast_metrics_run_id": k["fc_metrics"].get("run_id")},
        "reproducibility": dict(repro),
        "split": {"window": window, "init": iso(k["init"]),
                  "eval_start": iso(k["eval_start"]), "A": iso(coh.A), "F": iso(k["F"]),
                  "sealed_window": ("test window [TEST_START = 2025-11-01T00:00Z, "
                                    "2026-11-01T00:00Z): opened by this run through "
                                    "gridpilot.seal.sealed_read, up to F_test" if test else
                                    "test window [TEST_START = 2025-11-01T00:00Z, "
                                    "2026-11-01T00:00Z): never read by this run"),
                  "phase_days": env(PHASE_DAYS, "days", "assumed", "spec§7:phase"),
                  "s_ranking_training_rows": ([iso(t) for t in ses.freeze.s_window] if test
                                              else [iso(RANK_TRAIN[0]), iso(RANK_TRAIN[1])]),
                  "forecast_fit_at": iso(fcmod.TEST_FIT_AT if test else fcmod.VAL_FIT_AT)},
        "cohort_record": _cohort_record_env(k["cohort_record"], run_id),
        "scenarios_for_A": {n: {"note": SCENARIO_NOTES[n],
                                "first_failure": iso(coh.first_failure[n]),
                                "policies_run": n == "primary"} for n in SCENARIOS},
        "truth_fill": {
            "rule": "F14.6: first available of tiers 1-4; forecasts never used as fill",
            "tiers": {str(tr): {"source": TIER_SOURCE[tr], "evidence": TIER_EVIDENCE[tr]}
                      for tr in TIER_SOURCE},
            "hours_by_ba_evidence_note": "hour counts are measured (counted from the frozen "
                                         "snapshot); each tier's values carry its own label",
            "hours_by_ba": {ba: {tr: env(n, "hours", "measured", f"{run_id}:tier:{ba}:{tr}")
                                 for tr, n in row.items()} for ba, row in tiers.items()},
            "window": [iso(k["init"]), iso(k["F"])],
            "missing_after_tier4": k["still_missing"],
        },
        "support_check": _support_env(k["support"], run_id),
        "s_ranking": {"order": k["ranking"],
                      "mean_consumed_ci": {b: env(v, "g/kWh", "modeled",
                                                  f"{run_id}:rank:{b}")
                                           for b, v in k["rank_means"].items()},
                      "provenance": (f"frozen in config/freeze.json; {S_RANK_PROVENANCE}"
                                     if test else S_RANK_PROVENANCE),
                      "note": "unweighted hourly mean over training rows; never shown as an "
                              "attributed factor (F7)"},
        "assumptions": {
            "home_slots": env(SITES[HOME], "GPU_slots", "assumed", "spec§7:home_slots"),
            "destination_slots": {s: env(n, "GPU_slots", "assumed", f"spec§7:slots:{s}")
                                  for s, n in SITES.items() if s != HOME},
            "kw_per_gpu": env(GPU_KW, "kW", "assumed", "F7:kw_per_gpu"),
            "pue": env(PUE, "ratio", "assumed", "F7:pue"),
            "transfer_energy_fraction": env(TRANSFER_FRACTION, "fraction", "assumed",
                                            "F7:transfer_fraction"),
            "transfer_time_s": env(TRANSFER_S, "s", "assumed", "spec§7:transfer_time"),
            "allowed_delay_s": {tp: env(v, "s", "assumed", f"spec§7:delay:{tp}")
                                for tp, v in {"Pretrain": 21600, "SFT": 21600, "MLLM": 21600,
                                              "Eval": 3600, "other": 0}.items()},
            "flexibility_rule": "candidate type and int(sha256(f'{source_job_id}:42'), 16) % 2 "
                                "== 0; mobile iff flexible (assumed)",
            "deadline_rule": "max(arrival + duration + allowed delay, finish under U) (F1)",
            "bookings": "every job holds its U booking as a fallback (F11; assumed)",
            "home_capacity_1.25x_rounding": "round half up to an 8-GPU node: 2,288 x 1.25 = "
                                            "2,860 GPUs = 357.5 nodes -> 358 nodes = 2,864 slots",
            "replay": f"Seren {CYCLE_DAYS}-day cycle at phase 0 (simulated arrivals; measured "
                      f"durations and GPU counts)",
            "bootstrap": {"method": BOOTSTRAP_LABEL,
                          "blocks": env(list(BLOCKS), "weeks", "assumed", "F12.4:blocks"),
                          "primary_block": env(4, "weeks", "assumed", "F12.4:primary_block"),
                          "reps": env(2000, "replicates", "assumed", "F12.4:reps"),
                          "seed": "20261027"},
        },
        "workload": _workload_env(run_id),
        "f14_7_diagnostic": {
            "status": "run", "policies": list(DIAGNOSED_POLICIES),
            "g_ledger_identical_without_diagnostic": True,
            "timing_s": {
                "G_diagnosed": env(t["policy_G"], "s", "measured", f"{run_id}:timing:G_diag"),
                "G_undiagnosed": env(t["policy_G_undiagnosed"], "s", "measured",
                                     f"{run_id}:timing:G_plain")}},
        "not_run": NOT_RUN,
        "artifacts": list(ARTIFACTS_TEST if test else ARTIFACTS),
    }
    if test:
        manifest = {"schema_version": manifest.pop("schema_version"), "window": "test",
                    **manifest, "freeze": _freeze_record(ses)}
    return {"manifest.json": manifest, "metrics.json": metrics,
            "forecast-replay.json": frep, "job-replay.json": jrep}


# --------------------------------------------------------------------------- extensions

SCENARIO_KNOB_UNITS = {"dest_slots": "GPU_slots", "transfer_s": "s", "batch_delay_s": "s",
                       "mobility_max_gpus": "GPUs", "phase_days": "days"}
EXT_EVIDENCE_NOTE = ("validation results of a sensitivity scenario (D-058); policy outcomes "
                     "simulated, bound modeled, scenario knobs assumed; never pooled with the "
                     "registered primary result")


def scenario_record(scenario: Scenario, pid: str) -> dict:
    """The scenario definition: every knob is an `assumed` envelope (spec §7)."""
    knobs = {}
    for k, unit in SCENARIO_KNOB_UNITS.items():
        v = getattr(scenario, k)
        knobs[k] = env(v, unit, "assumed", f"{pid}:{k}",
                       reason=None if v is not None else "null = no mobility limit")
    return {"name": scenario.name, "note": scenario.note, "knobs": knobs,
            "changes_deadlines": scenario.changes_deadlines,
            "own_cohort": scenario.own_cohort, "policies": list(scenario.policies())}


def ext_summary(*, run_id, sha, status, window: Window, scenario: Scenario, coh, cj, acct,
                repro, tiers) -> dict:
    """summary.json of an extension run: the same enveloped policy records and contrasts as
    metrics.json, for this scenario's policies (no F14.7 diagnostic, no H2 decision: H2's
    rule applies to the primary phase-0 cohort only, F14.3)."""
    n_weeks = acct["n_weeks"]
    names = scenario.policies()
    policies = {n: _policy_record(n, acct["scores"][n], acct["gaps"][n], run_id, diagnosed=False,
                                  not_diagnosed_reason=EXT_NOT_DIAGNOSED_REASON) for n in names}
    contrasts = [_contrast_record(n, ref, acct["contrasts"][f"{n}_vs_{ref}"], run_id, n_weeks,
                                  window.name)
                 for ref in REFERENCES if ref in names for n in names if n != ref]
    pid = f"{run_id}:cohort"
    return {
        "schema_version": SCHEMA_VERSION, "run_id": run_id, "git_sha": sha,
        "git_clean": status == "", "window": window.name,
        "kind": "extension: one-axis sensitivity scenario (validation only; D-058)",
        "evidence_note": EXT_EVIDENCE_NOTE,
        "scenario": scenario_record(scenario, f"{run_id}:scenario"),
        "covered": {"arrivals": [iso(window.eval_start), iso(coh.A)],
                    "drain": [iso(coh.A), iso(window.F)]},
        "cohort": {
            "A": iso(coh.A),
            "A_rule": ("common F14.1 A of this phase (minimum first failure over the "
                       "registered F14.1 scenarios)"),
            "first_failure": {k: iso(v) for k, v in coh.first_failure.items()},
            "n_jobs": env(cj.height, "jobs", "simulated", f"{pid}:n"),
            "declared_gpu_h": env(_gpu_h(cj), "GPU_h", "measured", f"{pid}:gpu_h"),
            "n_excluded": env(coh.n_excluded, "jobs", "simulated", f"{pid}:excluded"),
            "excluded_gpu_h": env(coh.excluded_gpu_h, "GPU_h", "measured",
                                  f"{pid}:excluded_gpu_h"),
            "n_weeks": env(n_weeks, "weeks", "measured", f"{pid}:n_weeks"),
            "cohort_ids_sha256": coh.ids_hash, "booking_sha256": coh.booking_hash,
        },
        "policies": policies,
        "contrasts": contrasts,
        "relaxed_bound": {
            "primary": env(acct["bounds"]["primary"], "kg_CO2", "modeled", f"{run_id}:bound"),
            "time_only": env(acct["bounds"]["time_only"], "kg_CO2", "modeled",
                             f"{run_id}:bound_time_only"),
            "all_feasible_policies_ok": acct["bound_all_ok"]},
        "common_support": {"n_dropped_jobs": env(len(acct["common_support"]), "jobs",
                                                 "simulated", f"{run_id}:common_support")},
        "truth_fill_hours_by_ba": {ba: {tr: env(n, "hours", "measured",
                                                f"{run_id}:tier:{ba}:{tr}")
                                        for tr, n in row.items()} for ba, row in tiers.items()},
        "reproducibility": repro,
    }


def _cohort_record_env(r, run_id) -> dict:
    out = dict(r)
    out["phase_days"] = env(r["phase_days"], "days", "assumed", "spec§7:phase")
    out["n_stream"] = env(r["n_stream"], "jobs", "simulated", f"{run_id}:n_stream")
    out["n_cohort"] = env(r["n_cohort"], "jobs", "simulated", f"{run_id}:n_cohort")
    out["n_excluded"] = env(r["n_excluded"], "jobs", "simulated", f"{run_id}:n_excluded")
    out["excluded_gpu_h"] = env(r["excluded_gpu_h"], "GPU_h", "measured",
                                f"{run_id}:excluded_gpu_h")
    w = dict(r["warmup"])
    w["n_jobs"] = env(w["n_jobs"], "jobs", "simulated", f"{run_id}:warmup:n")
    w["gpu_h"] = env(w["gpu_h"], "GPU_h", "measured", f"{run_id}:warmup:gpu_h")
    out["warmup"] = w
    return out


def _support_env(s, run_id) -> dict:
    out = {}
    for part, d in s.items():
        out[part] = {"ok": d["ok"], "F": d["F"]}
        for key in ("n_checked", "n_after_f", "n_missing_truth", "n_filled_truth"):
            out[part][key] = env(d[key], "jobs", "simulated", f"{run_id}:support:{part}:{key}")
    return out


def _workload_env(run_id) -> dict:
    st = cycle_stats()
    units = {"unique_attempts": "attempts", "instances": "jobs", "gpu_hours": "GPU_h"}
    return {k: env(v, units.get(k, "fraction"), "measured", f"{run_id}:cycle:{k}")
            for k, v in st.items()}


# --------------------------------------------------------------------------- replays


def _replay_week(eval_start: datetime) -> tuple[datetime, datetime]:
    """The first complete Monday-00:00 America/Denver week starting at or after eval_start."""
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("America/Denver")
    d = eval_start.astimezone(tz).date()
    while True:
        start = datetime(d.year, d.month, d.day, tzinfo=tz)
        if d.weekday() == 0 and start >= eval_start:
            break
        d += timedelta(days=1)
    end = start + timedelta(days=7)
    end = datetime(end.year, end.month, end.day, tzinfo=tz)  # wall-clock Monday 00:00
    return start.astimezone(UTC), end.astimezone(UTC)


def forecast_replay(k) -> dict:
    run_id = k["run_id"]
    w0, w1 = _replay_week(k["eval_start"])
    fc = k["forecasts"].filter((pl.col("ba") == HOME) & (pl.col("target") == "ci_consumed")
                               & (pl.col("target_ts") >= w0) & (pl.col("target_ts") < w1))
    hours = pl.datetime_range(w0, w1 - H1, "1h", time_unit="us", time_zone="UTC", eager=True)
    hrs = pl.DataFrame({"target_ts": hours})
    filled = k["filled"].filter(pl.col("ba") == HOME)
    obs = hrs.join(filled.select(pl.col("ts_utc").alias("target_ts"), "ci_g_kwh", "tier"),
                   on="target_ts", how="left")
    truth_vals = [v if t == 1 else None for v, t in zip(obs["ci_g_kwh"], obs["tier"],
                                                        strict=True)]
    series, issues_by_model = {}, {}
    for model in ("K", "W", "L"):
        f = hrs.join(fc.filter(pl.col("model") == model).select("target_ts", "issue_ts", "value"),
                     on="target_ts", how="left")
        series[model] = f["value"].to_list()
        issues_by_model[model] = sorted({t for t in f["issue_ts"].to_list() if t is not None})
    empty = [m for m, v in issues_by_model.items() if not v]
    if empty:
        raise ValueError(f"forecast replay week [{iso(w0)}, {iso(w1)}) has no issued "
                         f"{HOME} ci_consumed forecast for model(s) {empty}; pick a week "
                         f"inside the forecast run's issue range")
    issues = sorted(set().union(*issues_by_model.values()))
    env_h = fcmod.ENVELOPE_H["ci_consumed"]
    issue_rows = [{"issue_ts": iso(i),
                   "target_day": [iso(fcmod.target_hours(i)[0]),
                                  iso(fcmod.target_hours(i)[-1] + H1)],
                   "data_cutoff_hour_start": iso(i - (1 + env_h) * H1)} for i in issues]
    # Tier-1 truth history ending at the first issue's publication cutoff (story beat 1).
    first = issues[0]
    cut = first - (1 + env_h) * H1
    hist_hours = pl.datetime_range(cut - 167 * H1, cut, "1h", time_unit="us", time_zone="UTC",
                                   eager=True)
    hist = pl.DataFrame({"ts_utc": hist_hours}).join(
        filled.select("ts_utc", "ci_g_kwh", "tier"), on="ts_utc", how="left")
    errors = {}
    obs_arr = np.array([np.nan if v is None else v for v in truth_vals])
    for model, vals in series.items():
        v = np.array([np.nan if x is None else x for x in vals])
        ok = np.isfinite(v) & np.isfinite(obs_arr)
        e = v[ok] - obs_arr[ok]
        errors[model] = {"mae": env(float(np.abs(e).mean()) if e.size else None, "g/kWh",
                                    "measured", f"{run_id}:fr:{model}:mae",
                                    *(() if e.size else ("unavailable", "no hours"))),
                         "bias": env(float(e.mean()) if e.size else None, "g/kWh", "measured",
                                     f"{run_id}:fr:{model}:bias",
                                     *(() if e.size else ("unavailable", "no hours"))),
                         "n_hours": env(int(ok.sum()), "hours", "measured",
                                        f"{run_id}:fr:{model}:n")}
    sel = k["fc_metrics"]["series"].get(f"{HOME}/ci_consumed", {})
    period = "test" if k.get("win") is not None and k["win"].is_test else "selection"
    sel_mae = {m: env(sel["models"][m][period]["mae"], "g/kWh", "measured",
                      f"{k['fc_metrics']['run_id']}:{HOME}/ci_consumed:{m}:{period}_mae")
               for m in ("K", "W", "L")} if sel else {}

    def nulls_reason(xs):
        return TRUTH_NULL if any(x is None for x in xs) else None

    truth_env = env(truth_vals, "g/kWh", "modeled", f"{run_id}:fr:truth",
                    reason=nulls_reason(truth_vals))
    hist_vals = [v if t == 1 else None for v, t in zip(hist["ci_g_kwh"], hist["tier"],
                                                        strict=True)]
    hist_env = env(hist_vals, "g/kWh", "modeled", f"{run_id}:fr:history",
                   reason=nulls_reason(hist_vals))

    return {
        "schema_version": SCHEMA_VERSION, "run_id": run_id, "ba": HOME,
        "target": "ci_consumed (EIA consumption-basis CO2 intensity)",
        "week": {"start": iso(w0), "end": iso(w1), "tz_display": "America/Denver",
                 "rule": "first complete Monday 00:00 America/Denver week at or after "
                         "eval_start (completeness only)"},
        "issue_rule": "daily at 10:00 America/Denver for the next Utah civil day; a row is "
                      f"usable iff ts_utc + 1 h + {env_h} h <= issue (assumed envelope)",
        "issues": issue_rows,
        "issues_by_model": {m: [iso(i) for i in v] for m, v in issues_by_model.items()},
        "hours": [iso(h) for h in hours.to_list()],
        "truth": truth_env,
        "truth_provenance": EIA_CI_PROVENANCE + " (tier 1 of the F14.6 scoring truth)",
        "forecasts": {m: env(v, "g/kWh", "forecast", f"{k['fc_metrics']['run_id']}:{m}",
                             reason=nulls_reason(v) and "null = no issued forecast")
                      for m, v in series.items()},
        "history_to_first_cutoff": {
            "hours": [iso(h) for h in hist_hours.to_list()],
            "truth": hist_env,
            "cutoff_hour_start": iso(cut)},
        "week_errors": errors,
        f"{period}_mae": sel_mae,
        "limitation": fcmod.LIMITATION,
        "forecast_note": "K/W/L forecasts are issued values; forecast values beyond issued "
                         "coverage are never shown here",
    }


def _action_co2(tt, gpus, duration_s, site, start_us, arrival_us) -> tuple[float, float]:
    d_us = round(duration_s * 1e6)
    val, miss = tt.integral(site, np.array([start_us]), np.array([start_us + d_us]))
    if miss[0]:
        raise AssertionError("illustrative action touches missing truth")
    ex = gpus * GPU_KW * PUE * val[0] / 1000
    tr = 0.0
    if site != HOME:
        t_fac = TRANSFER_FRACTION * gpus * GPU_KW * d_us / 3.6e9 * PUE
        ch, _ = tt.point(HOME, np.array([arrival_us]))
        cd, _ = tt.point(site, np.array([arrival_us]))
        tr = 0.5 * t_fac * (ch[0] + cd[0]) / 1000
    return float(ex), float(tr)


TRUTH_NULL = "null = hour without a tier-1 (EIA consumption-basis) value"


RULE_LITERAL = ("§11: among validation flexible jobs with a feasible remote action in the "
                "primary (U, bookings-held) replay, the job nearest the median GPU-hours of "
                "that set; ties by stable ID")
RULE_LITERAL_TEST = RULE_LITERAL.replace("among validation flexible jobs",
                                         "among the test cohort's flexible jobs")
RULE_V2 = ("illustration criterion v2 (D-054): over the same eligible set, sort by (declared "
           "GPU-h, job_uid) and take the first job whose cumulative declared GPU-h reaches 50% "
           "of the set's total (the GPU-hour-weighted median)")


def pick_literal(cands: pl.DataFrame) -> tuple[str, float]:
    """§11 literal rule: nearest the median GPU-h, ties by job_uid."""
    med = float(cands["gpu_h"].median())
    uid = cands.with_columns((pl.col("gpu_h") - med).abs().alias("dist")).sort(
        "dist", "job_uid")["job_uid"][0]
    return uid, med


def pick_weighted_median(cands: pl.DataFrame) -> tuple[str, float]:
    """D-054 criterion v2: the GPU-hour-weighted median job of the eligible set."""
    c = cands.sort("gpu_h", "job_uid").with_columns(pl.col("gpu_h").cum_sum().alias("cum"))
    total = float(c["gpu_h"].sum())
    uid = c.filter(pl.col("cum") >= 0.5 * total)["job_uid"][0]
    return uid, total


def _illustrative_record(uid, rule, k, extra) -> dict:
    run_id, cj, tt, ledgers, probe = k["run_id"], k["cj"], k["tt"], k["ledgers"], k["probe"]
    pick = cj.filter(pl.col("job_uid") == uid).with_columns(
        (pl.col("gpus") * pl.col("duration_s") / 3600).alias("gpu_h")).row(0, named=True)
    b = k["bookings"].filter(pl.col("job_uid") == uid).row(0, named=True)
    arr_us = _dt_us(pick["arrival_ts"])
    pid = f"{run_id}:job:{uid}"
    d_us = round(pick["duration_s"] * 1e6)
    actions = []
    for site, s in sorted(probe.actions[uid].items(), key=lambda kv: (kv[0] != HOME, kv[0])):
        ex, tr = _action_co2(tt, pick["gpus"], pick["duration_s"], site, s, arr_us)
        actions.append({
            "site": site, "kind": "stay" if site == HOME else "travel",
            "start": iso(_us_dt(s)), "end": iso(_us_dt(s + d_us)),
            "wait_s": env((s - arr_us) / 1e6, "s", "simulated", f"{pid}:{site}:wait"),
            "slack_s": env((b["deadline_us"] - s - d_us) / 1e6, "s", "simulated",
                           f"{pid}:{site}:slack"),
            "execution_co2_kg": env(ex, "kg_CO2", "modeled", f"{pid}:{site}:exec_co2"),
            "transfer_co2_kg": env(tr, "kg_CO2", "modeled", f"{pid}:{site}:transfer_co2"),
            "co2_kg": env(ex + tr, "kg_CO2", "modeled", f"{pid}:{site}:co2")})
    placements = {}
    for name, led in ledgers.items():
        one = led.filter(pl.col("job_uid") == uid)
        r = one.row(0, named=True)
        a = job_accounting(one, cj.filter(pl.col("job_uid") == uid), tt).row(0, named=True)
        placements[name] = {"site": r["site"], "start": iso(r["start_ts"]),
                            "end": iso(r["end_ts"]), "moved": r["moved"],
                            "co2_kg": env(a["co2_kg"], "kg_CO2", "simulated",
                                          f"{run_id}:{name}:job:{uid}:co2")}
    best = min(actions, key=lambda a: a["co2_kg"]["value"])
    stay = next((a for a in actions if a["site"] == HOME), None)
    expl = (f"Staying at {HOME} from its earliest feasible start would emit "
            f"{_num(stay['co2_kg']['value'])} kg CO2 (modeled); the lowest-CO2 earliest action "
            f"is {best['site']} at {_num(best['co2_kg']['value'])} kg including transfer."
            if stay else f"The lowest-CO2 earliest action is {best['site']}.")
    return {
        "rule": rule, **extra,
        "job_uid": uid, "source_id": pick["source_id"], "job_type": pick["job_type"],
        "arrival": iso(pick["arrival_ts"]),
        "gpus": env(pick["gpus"], "GPUs", "measured", f"{pid}:gpus"),
        "declared_duration_s": env(pick["duration_s"], "s", "measured", f"{pid}:duration"),
        "realized_duration_s": env(pick["duration_s"], "s", "assumed", f"{pid}:realized")
        | {"reason": "exact declared runtimes: realized = declared (runtime uncertainty "
                     "untested)"},
        "declared_gpu_h": env(pick["gpu_h"], "GPU_h", "measured", f"{pid}:gpu_h"),
        "flexible": pick["flexible"], "mobile": pick["mobile"],
        "flags_evidence": "assumed",
        "max_delay_s": env(pick["max_delay_s"], "s", "assumed", f"{pid}:max_delay"),
        "deadline": iso(_us_dt(b["deadline_us"])),
        "booking": {"site": b["site"], "start": iso(_us_dt(b["start_us"])),
                    "end": iso(_us_dt(b["end_us"])), "evidence": "simulated"},
        "available_actions": actions,
        "actions_note": "earliest on-time feasible start at each legal site, in the capacity "
                        "left by every other booking (the U replay state); CO2 priced on the "
                        "filled scoring truth",
        "placements": placements,
        "explanation": expl,
    }


def disclosure_text(uid: str, gpus: int, duration_s: float, job_type: str,
                    median_gpu_h: float) -> str:
    """D-054 disclosure: the reviewer's text verbatim, with the literal-rule job's ID and
    numbers filled from the run."""
    if duration_s < 3600:
        dur, length = f"{duration_s:.0f} s", f"{round(duration_s / 60)} minutes"
    else:
        dur, length = f"{duration_s / 3600:.1f} h", f"{duration_s / 3600:.1f} hours"
    return (f"The literal count-median job is a {gpus}-GPU, {dur} {job_type} job ({uid}; the "
            f"set's median is {median_gpu_h:.3f} GPU-h) because short jobs dominate the trace. "
            f"We show the job at the GPU-hour-weighted median, which represents where the set's "
            f"energy sits. The criterion was chosen after seeing that the count-median job is "
            f"{length} long, before seeing any outcome for the new pick.")


def _num(x: float) -> str:
    """Readable display number: thousands separators, three significant digits when small."""
    return f"{x:,.0f}" if abs(x) >= 100 else f"{x:.3g}"


def _describe(cj, uid) -> str:
    r = cj.filter(pl.col("job_uid") == uid).row(0, named=True)
    gh = r["gpus"] * r["duration_s"] / 3600
    dur = (f"{r['duration_s']:.0f} s" if r["duration_s"] < 3600
           else f"{r['duration_s'] / 3600:.1f} h")
    ghs = f"{gh:,.1f}" if gh >= 10 else f"{gh:.3g}"
    gpus = f"{r['gpus']} GPU" + ("" if r["gpus"] == 1 else "s")
    return f"{uid} ({r['job_type']}, {gpus}, {dur}, {ghs} GPU-h)"


def job_replay(k) -> dict:
    run_id, cj, ledgers = k["run_id"], k["cj"], k["ledgers"]
    cands = k["cands"]
    lit_uid, med = pick_literal(cands)
    v2_uid, total = pick_weighted_median(cands)
    n = cands.height
    lit = cj.filter(pl.col("job_uid") == lit_uid).row(0, named=True)
    disclosure = disclosure_text(lit_uid, lit["gpus"], lit["duration_s"], lit["job_type"], med)
    common = {
        "set_size": env(n, "jobs", "simulated", f"{run_id}:illustrative:set"),
        "set_median_gpu_h": env(med, "GPU_h", "measured", f"{run_id}:illustrative:median"),
        "set_total_gpu_h": env(total, "GPU_h", "measured", f"{run_id}:illustrative:total"),
        "candidates_file": "illustrative_candidates.parquet (run directory)",
    }
    illustrative = _illustrative_record(
        v2_uid, RULE_V2, k, {"criterion": "v2", "disclosure": disclosure, **common})
    rule = RULE_LITERAL_TEST if k.get("win") is not None and k["win"].is_test else RULE_LITERAL
    literal = _illustrative_record(lit_uid, rule, k, {"criterion": "literal", **common})
    # One week of placements, with arcs (the forecast-replay week).
    w0, w1 = _replay_week(k["eval_start"])
    wk = {}
    hours = pl.datetime_range(w0, w1 - H1, "1h", time_unit="us", time_zone="UTC", eager=True)
    h_us = hours.dt.epoch("us").to_numpy()
    wiv = k["warm"].intervals
    for name, led in ledgers.items():
        lw = led.filter((pl.col("arrival_ts") >= w0) & (pl.col("arrival_ts") < w1))
        arcs = []
        for site in sorted(s for s in SITES if s != HOME):
            r = lw.filter(pl.col("site") == site)
            arcs.append({"from": HOME, "to": site,
                         "jobs": env(r.height, "jobs", "simulated", f"{run_id}:{name}:arc:{site}"),
                         "gpu_h": env(_gpu_h(r),
                                      "GPU_h", "simulated", f"{run_id}:{name}:arcgh:{site}")})
        busy = {}
        s_us = np.concatenate([led["start_ts"].dt.epoch("us").to_numpy(),
                               wiv["start_us"].to_numpy()])
        e_us = np.concatenate([led["end_ts"].dt.epoch("us").to_numpy(), wiv["end_us"].to_numpy()])
        g = np.concatenate([led["gpus"].to_numpy(), wiv["gpus"].to_numpy()])
        sites_arr = np.concatenate([led["site"].to_numpy(), wiv["site"].to_numpy()])
        for site in SITES:
            m = sites_arr == site
            ss, ee, gg = s_us[m], e_us[m], g[m]
            occ = []
            for h in h_us:
                ov = np.clip(np.minimum(ee, h + 3_600_000_000) - np.maximum(ss, h), 0, None)
                occ.append(float((ov * gg).sum() / 3_600_000_000))
            busy[site] = env(occ, "GPU_h_per_h", "simulated", f"{run_id}:{name}:busy:{site}")
        wk[name] = {"n_arrivals": env(lw.height, "jobs", "simulated", f"{run_id}:{name}:wk_n"),
                    "arcs": arcs, "mean_busy_gpus_by_hour": busy}
    return {
        "schema_version": SCHEMA_VERSION, "run_id": run_id,
        "illustrative_job": illustrative,
        "illustrative_job_literal": literal,
        "week": {"start": iso(w0), "end": iso(w1), "hours": [iso(h) for h in hours.to_list()],
                 "note": "arcs count cohort jobs arriving in the week; mean_busy_gpus_by_hour "
                         "includes warm-up occupancy (cohort plus warm-up)",
                 "busy_includes_warmup": True,
                 "policies": wk},
    }


# --------------------------------------------------------------------------- table


def print_table(acct, timer, scenario: Scenario | None = None,
                window: Window | None = None) -> None:
    scenario = scenario or Scenario.primary()
    s = acct["scores"]
    if window is not None and window.is_test:
        print(f"\nTest-year results (sealed window to {iso(window.F)}; scenario "
              f"{scenario.name}; simulated outcomes; bound modeled).")
    else:
        print(f"\nValidation results (scenario {scenario.name}, phase {scenario.phase_days}; "
              f"simulated outcomes; bound modeled). Not test results.")
    hdr = (f"{'policy':8s} {'status':8s} {'feas':5s} {'late':>4s} {'tCO2':>10s} {'vs U %':>7s} "
           f"{'U-P b4 CI kg':>24s} {'moved%':>7s} {'remote%E':>8s} {'tier>=2%':>8s} "
           f"{'bound':>5s} {'sim s':>7s}")
    print(hdr)
    u = s["U"]["co2_kg"]
    for name in scenario.policies():
        m = s[name]
        c = acct["contrasts"].get(f"{name}_vs_U", {}).get(4)
        ci = f"[{c['diff_kg_ci'][0]:,.0f}, {c['diff_kg_ci'][1]:,.0f}]" if c else "-"
        ok = all(g["ok"] for g in acct["gaps"][name].values())
        print(f"{name:8s} {'ok':8s} {m['feasible']!s:5s} {m['late_jobs']:4d} "
              f"{m['co2_kg'] / 1000:10.1f} {100 * (u - m['co2_kg']) / u:7.2f} {ci:>24s} "
              f"{100 * (m['moved_share_jobs'] or 0):7.2f} "
              f"{100 * (m['remote_energy_share'] or 0):8.2f} "
              f"{100 * (m['kwh_share_tier_ge2'] or 0):8.3f} {ok!s:>5s} "
              f"{timer.t.get(f'policy_{name}', 0):7.1f}")
    st = acct.get("stratum")
    if st:
        wl = st["w_minus_l"][4] if st["w_minus_l"] else None
        print(f"coverage stratum (secondary): {st['n_jobs']} jobs, flexible-energy share "
              f"{st['share_flexible_energy_in_coverage']}; W-L b4 "
              f"{wl and (wl['diff_kg'], wl['diff_kg_ci'])}")
    if acct.get("h2"):
        h = acct["h2"]
        print(f"H2 (W-L, full cohort): {h['direction']} ({h['reason']}); "
              + ", ".join(f"b{b} {r['diff_kg']:.0f} [{r['diff_kg_ci'][0]:.0f}, "
                          f"{r['diff_kg_ci'][1]:.0f}]" for b, r in h["intervals"].items()))
    for name, m in s.items():
        print(f"  {name:7s} mobile_remote_share {m.get('mobile_remote_share')}, "
              f"blocked {m['blocked_jobs']} jobs / {m['blocked_kwh']:.0f} kWh"
              + ("" if name in DIAGNOSED_POLICIES else " (not diagnosed)"))
    print(f"relaxed bound (modeled): primary {acct['bounds']['primary'] / 1000:.1f} t, "
          f"time-only {acct['bounds']['time_only'] / 1000:.1f} t")
    for name, g in acct["gaps"].items():
        for basis, x in g.items():
            print(f"  bound check {name:7s} {basis:9s} gap {x['gap_kg']:.6f} kg "
                  f"min job gap {x['min_job_gap_kg']:.3e} kg ok={x['ok']}")
    if scenario.is_primary:
        print("framing: " + framing_text(acct, window.name if window else "validation"))
    print("timing (s): " + ", ".join(f"{k} {v:.1f}" for k, v in timer.t.items()))


def run_test(*, rerun_reason: str | None = None, repo_root: Path | None = None,
             data_dir: Path | None = None, results_dir: Path | None = None,
             out_dir: Path | None = None, pipeline=None) -> int:
    """The test-evaluation entry point: authorize (refusals (a)–(d), B7), then run the
    primary scenario on `Window.test()` inside the logged test-mode context and export to
    results/test/. Returns the exit code: REFUSED_RC with the reason on stderr when refused.
    `pipeline(window)` replaces the run in unit tests (synthetic data only)."""
    try:
        auth = seal.authorize(repo_root=repo_root, data_dir=data_dir, results_dir=results_dir,
                              rerun_reason=rerun_reason)
    except seal.SealError as e:
        print(f"run_slice --window test refused: {e}", file=sys.stderr)
        return REFUSED_RC
    with seal.test_mode(auth):
        window = Window.test()
        if pipeline is not None:
            return int(pipeline(window))
        res = run_pipeline(window, Scenario.primary(), out_dir, export=True)
    return res.rc




def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--window", choices=WINDOW_NAMES, default="validation",
                   help="validation (registered), fallback, or test: the sealed test window, "
                        "once, after the freeze (refuses otherwise)")
    p.add_argument("--rerun-reason", default=None,
                   help="--window test only: rerun over a completed test run; logged")
    p.add_argument("--scenario", choices=["primary", *EXTENSIONS], default="primary",
                   help="primary (registered) or a D-058 extension (gridpilot.scenario)")
    p.add_argument("--forecast-run", default=None,
                   help="reuse a Task 2 run directory instead of building forecasts")
    p.add_argument("--out", default=None, help="run root (default: runs/slice)")
    p.add_argument("--no-export", action="store_true",
                   help="do not copy into results/ (extensions never export)")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    if args.window == "test":
        if args.scenario != "primary" or args.forecast_run or args.no_export:
            p.error("--window test runs the primary scenario, builds its own forecasts and "
                    "always exports to results/test/")
        return run_test(rerun_reason=args.rerun_reason,
                        out_dir=Path(args.out) if args.out else None)
    if args.rerun_reason is not None:
        p.error("--rerun-reason applies to --window test only")
    scenario = Scenario.named(args.scenario)
    res = run_pipeline(Window.named(args.window), scenario, args.out,
                       export=scenario.is_primary and not args.no_export,
                       forecast_run=args.forecast_run)
    return res.rc


if __name__ == "__main__":
    sys.exit(main())
