"""Stage 3 T10 export rules: which run is read, the not_run items and the manifest update."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from gridpilot.results import LIMIT_PHASES, LIMIT_SHADOW_U, unenveloped_numbers
from gridpilot.scenario import EXTENSIONS

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export_extensions.py"


@pytest.fixture(scope="module")
def ex():
    spec = importlib.util.spec_from_file_location("export_extensions", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_latest_run_skips_partial_and_failed_runs(ex, tmp_path):
    for name, done in (("20261027T170000Z", True), ("20261027T180000Z", False),
                       ("failed-20261027T190000Z", True), (".tmp-20261027T200000Z-1", True)):
        d = tmp_path / name
        d.mkdir()
        if done:
            (d / "summary.json").write_text("{}")
    assert ex.latest_run(tmp_path).name == "20261027T170000Z"
    assert ex.latest_run(tmp_path / "missing") is None


def test_cut_items_are_not_run_with_the_owner_reason(ex):
    for k, v in ex.CUT_ITEMS.items():
        b = ex.not_run_block(v, ex.CUT_REASON)
        assert b == {"item": v, "status": "not_run", "reason": "cut by owner (D-058)"}, k
    assert {"shadow_U", "missingness_blind", "batch_delay_0h", "transfer_0min"} <= set(ex.CUT_ITEMS)
    assert set(ex.CUT_ITEMS_S7) == {"civil_time_dst_alignment", "runtime_overrun_25pct"}
    assert ex.CUT_REASON_S7 == "cut by owner (D-058): remaining §7 sensitivities"
    cut = set(ex.CUT_ITEMS) | set(ex.CUT_ITEMS_S7)
    assert not cut & set(EXTENSIONS)  # nothing that runs is listed as cut


def test_a_missing_run_fails_the_export_unless_allowed(ex, tmp_path):
    """Fix r1 I-1: a wrong or empty --ext-root must not silently export not_run blocks."""
    with pytest.raises(ex.MissingRunError, match="allow-missing"):
        ex.collect_runs(tmp_path, "validation")
    blocks, missing = ex.collect_runs(tmp_path, "validation", allow_missing=True)
    assert missing == list(EXTENSIONS)
    assert all(b["status"] == "not_run" and b["reason"] == "hard stop 21:00 (F9)"
               for b in blocks.values())


def test_a_missing_run_is_not_run_with_the_hard_stop_reason(ex):
    b = ex.not_run_block(EXTENSIONS["phase_98"].note, ex.HARD_STOP_REASON, EXTENSIONS["phase_98"])
    assert b["status"] == "not_run" and b["reason"] == "hard stop 21:00 (F9)"
    assert b["scenario"]["knobs"]["phase_days"]["value"] == 98
    assert b["scenario"]["knobs"]["phase_days"]["evidence"] == "assumed"
    assert unenveloped_numbers(b) == []
    nr = ex.manifest_not_run(["phase_98"])
    assert nr[-1]["reason"] == "hard stop 21:00 (F9)" and nr[-1]["item"].startswith("phase_98")
    assert all(x["reason"].startswith("cut by owner (D-058)") for x in nr[:-1])
    assert sum(x["reason"] == ex.CUT_REASON_S7 for x in nr) == 2


def test_patch_manifest_updates_not_run_and_the_phase_limitation(ex, tmp_path):
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps({"limitations": ["keep me", LIMIT_SHADOW_U, LIMIT_PHASES],
                             "not_run": [], "run_id": "r"}))
    ok = {"status": "ok"}
    ext = {"missing_runs": [], "phases": {"phase_49": ok, "phase_98": ok}}
    ex.patch_manifest(p, ext, "{}")
    m = json.loads(p.read_text())
    assert m["run_id"] == "r"
    assert m["limitations"] == ["keep me", ex.LIMIT_SHADOW_U_CUT, ex.LIMIT_PHASES_RUN]
    assert [x["item"] for x in m["not_run"]] == (
        [x["item"] for x in ex.rs.NOT_RUN] + list(ex.CUT_ITEMS_S7.values()))
    assert m["common_support_rerun"] == "see extensions.json#common_support"
    assert m["extensions"]["artifact"] == "extensions.json" and m["extensions"]["missing_runs"] == []
    # A phase that missed the hard stop keeps the "pending" limitation and is listed.
    ext = {"missing_runs": ["phase_98"],
           "phases": {"phase_49": ok, "phase_98": {"status": "not_run"}}}
    ex.patch_manifest(p, ext, "{}")
    m = json.loads(p.read_text())
    assert m["limitations"] == ["keep me", ex.LIMIT_SHADOW_U_CUT, LIMIT_PHASES]
    assert m["not_run"][-1]["reason"] == "hard stop 21:00 (F9)"
