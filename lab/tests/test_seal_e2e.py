"""Stage 3 T11: the full `--window test` pipeline, end to end, on synthetic grid data.

Opt-in (about a minute): `GRIDPILOT_SEAL_E2E=1 uv run pytest tests/test_seal_e2e.py`.
It builds a synthetic data directory (complete BA workbooks and a balance table from 2022-12
to a synthetic F_test = 2025-12-01, plus a copy of the unsealed workload trace from
GRIDPILOT_DATA_DIR), a synthetic git repository with a freeze record and its annotated tag,
and runs the real entry point (`run_slice.run_test`) in a subprocess whose
GRIDPILOT_DATA_DIR is the synthetic directory. No real sealed value is read: every grid file
the run sees is synthetic.

T20 (D-071): the same run also exercises every pre-registered test-year extra end to end: the
seven extension scenarios on the synthetic test year, storage, the toughest days (with
synthetic Salt Lake City archive files listed in the freeze record), water, the seasonal split,
forecast skill with the L permutation importance, and the drift table, against copies of the
committed validation artifacts. Every extra read is logged with its D-071 item.
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
                     rerun_reason=sys.argv[6] or None, synthetic=True))
"""

VALIDATION_COPIES = ("storage.json", "extensions.json", "case-days.json", "water.json",
                     "extras-validation.json")
ITEMS = ("extensions", "storage", "toughest_days", "water", "seasonal", "forecast_skill", "drift")

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
    weather = sealkit.write_weather_slc(data, datetime(2025, 1, 1, tzinfo=UTC), F)
    inputs = {rel: seal.file_sha256(data / rel) for rel in (*seal.TEST_INPUTS, *weather)}
    committed = {f"results/{n}": (paths.RESULTS_DIR / n).read_text() for n in VALIDATION_COPIES}
    repo = sealkit.make_repo(tmp_path, data, F=F, record_overrides={"input_sha256": inputs},
                             extra_files=committed)
    results, runs = repo / "results", tmp_path / "runs"
    r = _run(repo, data, results, runs)
    (tmp_path / "stdout.txt").write_text(r.stdout + "\n--- stderr ---\n" + r.stderr)
    assert r.returncode == 0, r.stderr[-4000:]

    # Outputs: one run directory and the six test artifacts, all declaring window "test".
    (run_dir,) = [p for p in runs.iterdir() if p.is_dir() and not p.name.startswith(".")
                  and p.name not in ("ext", "extras")]
    out = results / "test"
    names = sorted(p.name for p in out.glob("*.json"))
    assert names == sorted(["manifest.json", "metrics.json", "forecast-replay.json",
                            "job-replay.json", "grid-profile.json", "workload-profile.json",
                            "extras.json"])
    for name in sorted(set(names) - {"extras.json"}):
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

    # The test truth went into the run directory (I6), never the shared data dir; the
    # validation table was never written; the run directory is read-only.
    assert (run_dir / seal.CARBON_TEST_NAME).exists()
    assert not (data / seal.LEGACY_CARBON_TEST_REL).exists()
    assert not (data / "processed" / "carbon" / "carbon_hourly.parquet").exists()
    assert all(not os.access(f, os.W_OK) for f in run_dir.rglob("*") if f.is_file())
    assert seal.verify_exports(results) == []  # M8
    assert man["s_ranking"]["fit_at"] == "2025-10-29T00:00:00Z"

    # The read log: one invocation, logged reads of frozen or session-built files, one close.
    log = sealkit.read_log(results)
    ev = [x["event"] for x in log]
    assert ev[0] == "invocation" and ev[-1] == "close" and log[-1]["outcome"] == "ok"
    assert {"run_start", "export"} <= set(ev)
    assert log[-1]["rc"] == 0 and log[-1]["exported"] is True  # M1
    reads = [x for x in log if x["event"] == "read"]
    assert len(reads) == log[-1]["n_reads"] > 10
    for x in reads:
        assert Path(x["path"]).is_relative_to(data) or Path(x["path"]).is_relative_to(runs)
        assert x["purpose"] and x["caller"] and x["sha256"] and x["time_range"][1] <= seal.iso(F)
        assert x["code_commit"] == man["git_sha"]

    _check_extras(out, runs, log, data, run_dir)

    # A second run is refused: first the uncommitted outputs (a); once committed, (d).
    r2 = _run(repo, data, results, runs)
    assert r2.returncode == 4 and "(a)" in r2.stderr
    sealkit.git(repo, "add", "-A")
    sealkit.git(repo, "commit", "-qm", "test outputs")
    r3 = _run(repo, data, results, runs)
    assert r3.returncode == 4 and "(d)" in r3.stderr


def _check_extras(out, runs, log, data, run_dir):
    """T20: every D-071 item ran end to end, was exported with the logged artifacts, and every
    extra read named its item."""
    ex = json.loads((out / "extras.json").read_text())
    primary_cohort = json.loads((run_dir / "cohort.json").read_text())
    assert ex["window"] == "test" and ex["label"] == "test year, pre-registered secondary (D-071)"
    assert unenveloped_numbers(ex) == []
    for key in ITEMS:
        sec = ex[key]
        if key != "extensions":
            assert sec.get("status", "ok") == "ok", (key, sec.get("reason"))
    for name in ("phase_49", "phase_98", "dest_slots_0", "dest_slots_1024", "transfer_120min",
                 "batch_delay_24h", "mobility_le_8gpus"):
        sec = ex["extensions"][name]
        assert sec["status"] == "ok", (name, sec.get("reason"))
        assert {"U", "S", "W", "L"} <= set(sec["policies"]) and "S" in sec["vs_U"]
        (d,) = [p for p in (runs / "ext" / name).iterdir() if not p.name.startswith(".")]
        assert json.loads((d / "summary.json").read_text())["window"] == "test"
        coh = json.loads((d / "cohort.json").read_text())
        reused = name in ("dest_slots_0", "dest_slots_1024", "transfer_120min")
        assert coh.get("cohort_reused_from_primary_run", False) is reused, name
        if reused:  # the primary's exact cohort and bookings
            assert coh["cohort_ids_sha256"] == primary_cohort["cohort_ids_sha256"]
            assert coh["booking_sha256"] == primary_cohort["booking_sha256"]
    assert set(ex["storage"]["cases"]) == {"U", "mobility_le_8gpus_W"}
    assert set(ex["storage"]["cases"]["U"]["A"]) == {"4", "8"}
    assert ex["storage"]["flat_marginal_g_kwh"]["value"] == 618.0
    # 2b (D-073): the peak-aimed schedule from the committed validation file, beside the carbon one
    cmp_ = ex["storage"]["schedule_comparison"]["schedules"]
    assert set(cmp_) == {"carbon", "peak"}
    vpeak = json.loads((paths.RESULTS_DIR / "extras-validation.json").read_text())[
        "storage_peak"]["peak_schedule"]
    assert cmp_["peak"]["discharge_hours"]["value"] == vpeak["discharge_hours"]["value"]
    for sch in cmp_.values():
        for case in ("U", "mobility_le_8gpus_W"):
            r = sch["cases"][case]["4"]
            assert {"co2_t", "flat_marginal_cut_t", "rush_import_after_mw",
                    "peak_import_after_mw"} <= set(r)
    days = ex["toughest_days"]["days"]
    assert len(days) == 3 and ex["toughest_days"]["all_checks_ok"]
    assert all(d["temperature"]["label"] == "Salt Lake City only" for d in days)
    for p in ("S", "W", "L"):
        cv = ex["water"]["policies"][p]["change_vs_U"]
        assert cv["sign_ex_hydro"] in ("less", "more", "equal")
        assert cv["sign_with_hydro"] in ("less", "more", "equal")
    assert set(ex["seasonal"]["seasons"]) == {"DJF", "MAM", "JJA", "SON"}
    sk = ex["forecast_skill"]["series"]
    assert set(sk) == {"PACE", "CISO", "BPAT", "NEVP"} and len(sk["PACE"]) == 4
    for ba, by in sk.items():
        for t, r in by.items():
            assert r["permutation_importance"]["reproduces_frozen_forecasts"], (ba, t)
            assert set(r["permutation_importance"]["groups"]) == {
                "calendar", "weekly memory", "most recent", "recent level", "missing-data flags"}
            assert "coverage" in r["models"]["L"]["interval"]
    assert sk["PACE"]["demand"]["eia_day_ahead"]["mae"]["status"] == "ok"
    rows = ex["drift"]["rows"]
    assert len(rows) == ex["drift"]["n_rows"]["value"] > 100
    assert {r["item"] for r in rows} >= {"headline", "1 extensions", "2 storage", "2b storage schedules",
                                          "3 toughest days", "4 water", "5 seasonal",
                                          "6 forecast skill", "6 permutation importance"}
    with_both = [r for r in rows if r["validation"]["status"] == "ok" and r["test"]["status"] == "ok"]
    assert len(with_both) > 50
    # The last export line lists every test artifact, extras.json included (M8).
    assert seal.verify_exports(out.parent) == []
    ev = [x for x in log if x["event"] == "export"]
    assert len(ev) == 2 and "extras.json" in ev[-1]["artifacts_sha256"]
    # Every read after the primary export names its D-071 item; none reaches past F.
    first = next(i for i, x in enumerate(log) if x["event"] == "export")
    late = [x for x in log[first:] if x["event"] == "read"]
    assert late and all(x["scope"] and x["purpose"].startswith("D-071 item") for x in late)
    for k in (1, 2, 3, 4, 6):  # item 5 reads nothing new: it uses the primary's ledgers
        assert any(f"item {k}" in x["scope"] or "items 2-6" in x["scope"] for x in late), k
    assert any("item 3" in x["scope"] and "PACE_SLC" in x["path"] for x in late)
