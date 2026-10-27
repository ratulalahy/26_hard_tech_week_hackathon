"""Results export contract (spec §11, F12.5, Task 7): envelopes, the seal, the claim frame."""

import json
from pathlib import Path

import numpy as np
import pytest

from gridpilot.forecast import LIMITATION as FORECAST_LIMITATION
from gridpilot.paths import RESULTS_DIR
from gridpilot.results import (
    CLAIM_FRAME,
    EVIDENCE_CLASSES,
    IMPORT_CONVENTION,
    check_claim_frame,
    env,
    sealed_timestamps,
    unenveloped_numbers,
    validate_artifact,
    write_json_atomic,
)

ARTIFACTS = ("manifest.json", "metrics.json", "forecast-replay.json", "job-replay.json")


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
          "wallclock_generated_at": "2026-10-27T09:00:00Z", "run_id": "20261027T090000Z"}
    assert sealed_timestamps(ok) == []
    bad = {"x": ["2025-11-01T00:00:00+00:00"], "y": {"2026-01-01": 1},
           "z": "2025-10-31T18:00:00-07:00", "w": "2025-11-01"}
    found = sealed_timestamps(bad)
    assert "$.x[0]" in found
    assert any("2026-01-01" in p for p in found)
    assert "$.z" in found  # 2025-11-01T01:00Z
    assert "$.w" in found


def test_validate_artifact_and_claim_frame():
    m = {"claim_frame": CLAIM_FRAME, "limitations": [FORECAST_LIMITATION, IMPORT_CONVENTION]}
    assert validate_artifact(m) == []
    check_claim_frame(m)
    with pytest.raises(ValueError):
        check_claim_frame({"claim_frame": "something else", "limitations": []})
    with pytest.raises(ValueError):
        check_claim_frame({"claim_frame": CLAIM_FRAME, "limitations": [IMPORT_CONVENTION]})
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


def _committed():
    found = [RESULTS_DIR / a for a in ARTIFACTS if (RESULTS_DIR / a).exists()]
    if not found:
        pytest.skip("no exported results/ artifacts yet (run `make slice`)")
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


def test_manifest_carries_claim_frame():
    _committed()
    m = json.loads((RESULTS_DIR / "manifest.json").read_text())
    check_claim_frame(m)
    assert m["snapshot_id"] == "05efabe781cc"
