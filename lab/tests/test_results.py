"""Results export contract (spec §11, F12.5, Task 7): envelopes, the seal, the claim frame."""

import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from gridpilot.forecast import LIMITATION as FORECAST_LIMITATION
from gridpilot.paths import REPO_ROOT, RESULTS_DIR
from gridpilot.results import (
    CLAIM_FRAME,
    EVIDENCE_CLASSES,
    IMPORT_CONVENTION,
    LIMIT_BOOKINGS_UNSIGNED,
    LIMIT_VALIDATION_DEV,
    LIMIT_ZERO_MISSES,
    canonical_hash,
    check_claim_frame,
    env,
    sealed_timestamps,
    unenveloped_numbers,
    validate_artifact,
    write_json_atomic,
)

ARTIFACTS = ("manifest.json", "metrics.json", "forecast-replay.json", "job-replay.json",
             "grid-profile.json", "workload-profile.json", "extensions.json")


# --------------------------------------------------------------------------- env()


def test_env_shape_and_numpy():
    e = env(np.float64(1.5), "kg_CO2", "simulated", "run:U:co2_kg")
    assert e == {"value": 1.5, "unit": "kg_CO2", "evidence": "simulated",
                 "provenance_id": "run:U:co2_kg", "status": "ok", "reason": None}
    assert type(env(np.int64(3), "jobs", "simulated", "p")["value"]) is int
    s = env(np.array([1.0, 2.0]), "g/kWh", "forecast", "p")
    assert s["value"] == [1.0, 2.0]
    assert json.dumps(s)


def test_env_rejects_bad_evidence_and_unexplained_nulls():
    with pytest.raises(ValueError, match="evidence"):
        env(1.0, "kg", "guessed", "p")
    with pytest.raises(ValueError, match="reason"):
        env(None, "kg", "simulated", "p")
    with pytest.raises(ValueError, match="reason"):
        env([1.0, None], "kg", "simulated", "p")
    with pytest.raises(ValueError, match="reason"):
        env(1.0, "kg", "simulated", "p", status="not_run")
    with pytest.raises(ValueError, match="status"):
        env(1.0, "kg", "simulated", "p", status="great")
    # NaN is never a number in an artifact: it becomes null and needs a reason.
    with pytest.raises(ValueError, match="reason"):
        env(float("nan"), "kg", "simulated", "p")
    e = env(float("nan"), "kg", "simulated", "p", status="unavailable", reason="no data")
    assert e["value"] is None
    assert set(EVIDENCE_CLASSES) == {"observed", "measured", "forecast", "modeled", "assumed",
                                     "simulated"}


# --------------------------------------------------------------------------- validators


def test_unenveloped_numbers_found_with_paths():
    good = {"a": env(1.0, "kg", "simulated", "p"), "b": "text", "c": [env(2, "n", "measured", "q")],
            "flag": True}
    assert unenveloped_numbers(good) == []
    bad = {"a": 1.0, "b": {"c": [1, 2]}, "d": {"value": 3.0, "unit": "kg"},
           "e": {**env(1.0, "kg", "simulated", "p"), "evidence": "vibes"}}
    paths = unenveloped_numbers(bad)
    assert "$.a" in paths
    assert "$.b.c[0]" in paths and "$.b.c[1]" in paths
    assert any(p.startswith("$.d") for p in paths)
    assert any(p.startswith("$.e") for p in paths)


def test_sealed_timestamps_found_and_wallclock_exempt():
    ok = {"ts": "2025-10-31T23:00:00+00:00", "d": "2024-11-01", "s": "PACE",
          "wallclock_generated_at": "2026-10-27T09:00:00Z", "run_id": "20261027T090000Z",
          "path": "runs/slice/20261027T101902Z/forecast", "text": "window [2024-11-01, A)",
          "sealed_window": "test window [2025-11-01T00:00Z, 2026-11-01T00:00Z): never read",
          "evidence_scope": "the sealed window [2025-11-01, 2026-11-01) is never read",
          "note": "EIA's 2025-26 factors"}
    assert sealed_timestamps(ok) == []
    bad = {"x": ["2025-11-01T00:00:00+00:00"], "y": {"2026-01-01": 1},
           "z": "2025-10-31T18:00:00-07:00", "w": "2025-11-01",
           "sub": "arrivals until 2025-11-03T00:00Z were read",
           "wallclock_other": "2026-10-27T09:00:00Z"}
    found = sealed_timestamps(bad)
    assert "$.x[0]" in found
    assert any("2026-01-01" in p for p in found)
    assert "$.z" in found  # 2025-11-01T01:00Z
    assert "$.w" in found
    assert "$.sub" in found  # a date substring inside a longer string
    assert "$.wallclock_other" in found  # only the exact key wallclock_generated_at is exempt


def test_validate_artifact_and_claim_frame():
    req = [FORECAST_LIMITATION, IMPORT_CONVENTION, LIMIT_ZERO_MISSES, LIMIT_BOOKINGS_UNSIGNED,
           LIMIT_VALIDATION_DEV]
    m = {"claim_frame": CLAIM_FRAME, "limitations": req}
    assert validate_artifact(m) == []
    check_claim_frame(m)
    with pytest.raises(ValueError):
        check_claim_frame({"claim_frame": "something else", "limitations": req})
    with pytest.raises(ValueError):
        check_claim_frame({"claim_frame": CLAIM_FRAME, "limitations": [IMPORT_CONVENTION]})
    for drop in (LIMIT_ZERO_MISSES, LIMIT_BOOKINGS_UNSIGNED, LIMIT_VALIDATION_DEV):
        with pytest.raises(ValueError):
            check_claim_frame({"claim_frame": CLAIM_FRAME,
                               "limitations": [x for x in req if x != drop]})
    errs = validate_artifact({"n": 5, "t": "2025-12-01T00:00:00Z"})
    assert len(errs) == 2


def test_write_json_atomic_refuses_invalid(tmp_path: Path):
    p = tmp_path / "x.json"
    write_json_atomic(p, {"a": env(1.0, "kg", "simulated", "p")})
    assert json.loads(p.read_text())["a"]["value"] == 1.0
    with pytest.raises(ValueError):
        write_json_atomic(tmp_path / "y.json", {"a": 1.0})
    assert not (tmp_path / "y.json").exists()
    assert not list(tmp_path.glob(".*tmp*"))


def test_claim_frame_text_is_verbatim():
    assert CLAIM_FRAME == (
        "simulated advance-reservation scheduling scenario; baseline-relative deadlines; "
        "exact declared runtimes; runtime uncertainty untested; EIA-attributed "
        "(consumption-basis) emissions; conditional temporal block-resampling intervals")


# --------------------------------------------------------------------------- committed results


def test_canonical_hash_ignores_provenance_and_tiny_float_noise():
    a = {"run_id": "r1", "x": env(1.00000000001, "kg", "simulated", "r1:x"), "y": [0.0, -0.0]}
    b = {"run_id": "r2", "x": env(1.00000000004, "kg", "simulated", "r2:x"), "y": [-0.0, 0.0]}
    assert canonical_hash(a) == canonical_hash(b)  # 10 significant digits (T10)
    c = {"run_id": "r1", "x": env(1.000001, "kg", "simulated", "r1:x"), "y": [0.0, 0.0]}
    assert canonical_hash(a) != canonical_hash(c)


def _tracked_artifacts() -> list[str]:
    out = subprocess.run(["git", "ls-files", "results"], cwd=REPO_ROOT, capture_output=True,
                         text=True, check=False).stdout.split()
    return [Path(p).name for p in out if Path(p).name in ARTIFACTS]


def _committed():
    tracked = _tracked_artifacts()
    missing = [a for a in tracked if not (RESULTS_DIR / a).exists()]
    assert not missing, f"tracked results/ artifacts are missing on disk: {missing}"
    found = [RESULTS_DIR / a for a in ARTIFACTS if (RESULTS_DIR / a).exists()]
    if not tracked and not found:
        pytest.skip("no results/ artifacts tracked or exported yet (run `make slice`)")
    return found


def test_results_artifacts_all_present():
    found = _committed()
    assert {p.name for p in found} == set(ARTIFACTS)


def test_every_number_enveloped():
    for p in _committed():
        bad = unenveloped_numbers(json.loads(p.read_text()))
        assert bad == [], f"{p.name}: numbers outside a valid envelope at {bad[:10]}"


def test_no_sealed_dates():
    for p in _committed():
        bad = sealed_timestamps(json.loads(p.read_text()))
        assert bad == [], f"{p.name}: timestamps at or after TEST_START at {bad[:10]}"


def _envs(x, path="$"):
    if isinstance(x, dict):
        if "value" in x and "evidence" in x:
            yield path, x
            return
        for k, v in x.items():
            yield from _envs(v, f"{path}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from _envs(v, f"{path}[{i}]")


def test_extensions_evidence_classes():
    """T10: repricing, common support and policy outcomes are simulated; scenario knobs are
    assumed; the D-058 cuts are not_run with the owner's reason; the seal holds."""
    _committed()
    ext = json.loads((RESULTS_DIR / "extensions.json").read_text())
    for path, e in _envs(ext):
        leaf = path.rsplit(".", 1)[-1]
        if ".scenario.knobs." in path:
            assert e["evidence"] == "assumed", path
        elif leaf in ("saving", "saving_ci95", "diff_kg", "diff_kg_ci95", "co2_kg"):
            assert e["evidence"] == "simulated", path
    for k, v in ext["not_run"].items():
        assert v["status"] == "not_run" and v["reason"].startswith("cut by owner (D-058)"), k
    assert ext["export_git_clean"] is True  # exported at a clean commit (fix r1 M-3)
    rep = ext["primary_reproduction"]
    assert rep["metrics_canonical_equal"] and all(rep["ledgers_equal"].values())
    blocks = {**ext["phases"], **ext["sensitivities"]}
    assert set(blocks) == {"phase_49", "phase_98", "dest_slots_0", "dest_slots_1024",
                           "transfer_120min", "batch_delay_24h", "mobility_le_8gpus"}
    for name, b in blocks.items():
        if b["status"] == "ok":
            assert b["all_on_time"], name  # late count stays 0 under bookings
            assert b["run_id"] and b["canonical_hashes"]["summary_canonical_sha256"], name
        else:
            assert b["status"] == "not_run" and b["reason"], name
    for b in (ext["repricing"], ext["common_support"]):
        assert b["canonical_hashes"]["run_id"] == ext["registered_run_id"]
        assert b["scenario"]["name"] == "primary"
    man = json.loads((RESULTS_DIR / "manifest.json").read_text())
    assert man["extensions"]["missing_runs"] == ext["missing_runs"]
    assert man["extensions"]["canonical_sha256"] == canonical_hash(ext)
    assert man["common_support_rerun"] == "see extensions.json#common_support"


def test_manifest_carries_claim_frame():
    _committed()
    m = json.loads((RESULTS_DIR / "manifest.json").read_text())
    check_claim_frame(m)
    assert m["snapshot_id"] == "05efabe781cc"
