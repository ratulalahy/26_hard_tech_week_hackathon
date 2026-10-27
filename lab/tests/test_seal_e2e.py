"""Stage 3 T11: the full `--window test` pipeline, end to end, on synthetic grid data.

Opt-in (about a minute): `GRIDPILOT_SEAL_E2E=1 uv run pytest tests/test_seal_e2e.py`.
It builds a synthetic data directory (complete BA workbooks and a balance table from 2022-12
to a synthetic F_test = 2025-12-01, plus a copy of the unsealed workload trace from
GRIDPILOT_DATA_DIR), a synthetic git repository with a freeze record and its annotated tag,
and runs the real entry point (`run_slice.run_test`) in a subprocess whose
GRIDPILOT_DATA_DIR is the synthetic directory. No real sealed value is read: every grid file
the run sees is synthetic.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sealkit

from gridpilot import paths, seal
from gridpilot.results import sealed_timestamps, unenveloped_numbers

LAB = Path(__file__).resolve().parents[1]
F = datetime(2025, 12, 1, tzinfo=UTC)
DRIVER = """
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("run_slice", sys.argv[1])
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)
sys.exit(rs.run_test(repo_root=Path(sys.argv[2]), data_dir=Path(sys.argv[3]),
                     results_dir=Path(sys.argv[4]), out_dir=Path(sys.argv[5]),
                     rerun_reason=sys.argv[6] or None))
"""

pytestmark = pytest.mark.skipif(not os.environ.get("GRIDPILOT_SEAL_E2E"),
                                reason="opt-in: set GRIDPILOT_SEAL_E2E=1 (about a minute)")


def _run(repo, data, results, runs, reason=""):
    driver = repo.parent / "driver.py"
    driver.write_text(DRIVER)
    env = {**os.environ, "GRIDPILOT_DATA_DIR": str(data)}
    return subprocess.run([sys.executable, str(driver), str(LAB / "scripts" / "run_slice.py"),
                           str(repo), str(data), str(results), str(runs), reason],
                          cwd=LAB, env=env, capture_output=True, text=True, timeout=3600,
                          check=False)


def test_the_full_test_pipeline_on_synthetic_data(tmp_path):
    trace = paths.DATA_DIR / seal.TRACE_REL
    if not trace.exists():
        pytest.skip(f"no workload trace at {trace} (set GRIDPILOT_DATA_DIR)")
    data = sealkit.make_full_data_dir(tmp_path, F, trace)
    repo = sealkit.make_repo(tmp_path, data, F=F)
    results, runs = repo / "results", tmp_path / "runs"
    r = _run(repo, data, results, runs)
    (tmp_path / "stdout.txt").write_text(r.stdout + "\n--- stderr ---\n" + r.stderr)
    assert r.returncode == 0, r.stderr[-4000:]

    # Outputs: one run directory and the six test artifacts, all declaring window "test".
    (run_dir,) = [p for p in runs.iterdir() if p.is_dir() and not p.name.startswith(".")]
    out = results / "test"
    names = sorted(p.name for p in out.glob("*.json"))
    assert names == sorted(["manifest.json", "metrics.json", "forecast-replay.json",
                            "job-replay.json", "grid-profile.json", "workload-profile.json"])
    for name in names:
        art = json.loads((out / name).read_text())
        w = art["window"]["name"] if isinstance(art["window"], dict) else art["window"]
        assert w == "test", name
        assert unenveloped_numbers(art) == [], name
        # no validation wording on test numbers (the freeze record's key names the run it cites)
        text = (out / name).read_text().replace('"validation_run"', "")
        assert "validation" not in text.lower(), name
        if name != "workload-profile.json":  # the only artifact without timestamps
            # sealed_timestamps (validation rule) flags stamps at/after TEST_START: test data
            assert sealed_timestamps(art), f"{name}: no test-window timestamp"
    man = json.loads((out / "manifest.json").read_text())
    assert man["freeze"]["freeze_commit"] == seal.load_freeze(repo / seal.FREEZE_REL).freeze_commit
    assert man["git_sha"] == sealkit.git(repo, "rev-parse", "HEAD")
    assert man["snapshot_id"] == seal.load_freeze(repo / seal.FREEZE_REL).snapshot_id
    assert man["split"]["F"] == seal.iso(F)
    metrics = json.loads((out / "metrics.json").read_text())
    assert metrics["window"] == "test" and metrics["covered"]["drain"][1] == seal.iso(F)
    assert "Validation results are development evidence" not in json.dumps(man)
    cfg = json.loads((run_dir / "config.json").read_text())
    assert cfg["window"] == "test" and cfg["freeze"]["test_F"] == seal.iso(F)
    fz = seal.load_freeze(repo / seal.FREEZE_REL)
    assert cfg["s_ranking"] == fz.s_order

    # The test truth went to its own path; the validation table was never written.
    assert (data / "processed" / "carbon" / "carbon_hourly_test.parquet").exists()
    assert not (data / "processed" / "carbon" / "carbon_hourly.parquet").exists()

    # The read log: one invocation, logged reads of frozen or session-built files, one close.
    log = sealkit.read_log(results)
    ev = [x["event"] for x in log]
    assert ev[0] == "invocation" and ev[-1] == "close" and log[-1]["outcome"] == "ok"
    assert {"run_start", "export"} <= set(ev)
    reads = [x for x in log if x["event"] == "read"]
    assert len(reads) == log[-1]["n_reads"] > 10
    for x in reads:
        assert Path(x["path"]).is_relative_to(data)
        assert x["purpose"] and x["caller"] and x["sha256"] and x["time_range"][1] <= seal.iso(F)
        assert x["code_commit"] == man["git_sha"]

    # A second run is refused: first the uncommitted outputs (a); once committed, (d).
    r2 = _run(repo, data, results, runs)
    assert r2.returncode == 4 and "(a)" in r2.stderr
    sealkit.git(repo, "add", "-A")
    sealkit.git(repo, "commit", "-qm", "test outputs")
    r3 = _run(repo, data, results, runs)
    assert r3.returncode == 4 and "(d)" in r3.stderr
