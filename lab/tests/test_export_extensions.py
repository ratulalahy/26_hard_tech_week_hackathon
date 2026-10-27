"""Stage 3 T10 export rules: which run is read, the not_run items and the manifest update."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from gridpilot.results import LIMIT_PHASES, unenveloped_numbers
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
    assert {"shadow_U", "missingness_blind"} <= set(ex.CUT_ITEMS)
    assert not set(ex.CUT_ITEMS) & set(EXTENSIONS)  # nothing that runs is listed as cut


def test_a_missing_run_is_not_run_with_the_hard_stop_reason(ex):
    b = ex.not_run_block(EXTENSIONS["phase_98"].note, ex.HARD_STOP_REASON, EXTENSIONS["phase_98"])
    assert b["status"] == "not_run" and b["reason"] == "hard stop 21:00 (F9)"
    assert b["scenario"]["knobs"]["phase_days"]["value"] == 98
    assert b["scenario"]["knobs"]["phase_days"]["evidence"] == "assumed"
    assert unenveloped_numbers(b) == []
    nr = ex.manifest_not_run(["phase_98"])
    assert nr[-1]["reason"] == "hard stop 21:00 (F9)" and nr[-1]["item"].startswith("phase_98")
    assert all(x["reason"] == "cut by owner (D-058)" for x in nr[:-1])


def test_patch_manifest_updates_not_run_and_the_phase_limitation(ex, tmp_path):
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps({"limitations": ["keep me", LIMIT_PHASES], "not_run": [],
                             "run_id": "r"}))
    ok = {"status": "ok"}
    ext = {"missing_runs": [], "phases": {"phase_49": ok, "phase_98": ok}}
    ex.patch_manifest(p, ext, "{}")
    m = json.loads(p.read_text())
    assert m["run_id"] == "r"
    assert m["limitations"] == ["keep me", ex.LIMIT_PHASES_RUN]
    assert [x["item"] for x in m["not_run"]] == [x["item"] for x in ex.rs.NOT_RUN]
    assert m["extensions"]["artifact"] == "extensions.json" and m["extensions"]["missing_runs"] == []
    # A phase that missed the hard stop keeps the "pending" limitation and is listed.
    ext = {"missing_runs": ["phase_98"],
           "phases": {"phase_49": ok, "phase_98": {"status": "not_run"}}}
    ex.patch_manifest(p, ext, "{}")
    m = json.loads(p.read_text())
    assert m["limitations"] == ["keep me", LIMIT_PHASES]
    assert m["not_run"][-1]["reason"] == "hard stop 21:00 (F9)"
