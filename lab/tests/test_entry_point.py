"""Stage 3 T11 B1: `run_slice --window test` is the only way to construct the test window.
It refuses (non-zero exit, reason on stderr, nothing read or logged) unless every check
passes; inside, every sealed read is logged. Synthetic repositories and data only: the real
repository has no freeze record, so the real CLI refuses."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import polars as pl
import pytest
import sealkit

from gridpilot import seal
from gridpilot.data import eia_co2, truth_fill
from gridpilot.paths import REPO_ROOT
from gridpilot.splits import TEST_START
from gridpilot.window import Window

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_slice.py"


@pytest.fixture(scope="module")
def rs():
    spec = importlib.util.spec_from_file_location("run_slice", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_real_cli_refuses_without_a_freeze_record(rs, capsys):
    if (REPO_ROOT / seal.FREEZE_REL).exists():  # T12 wrote it: tests never invoke the real CLI
        pytest.skip("a freeze record exists; the real --window test CLI is never run from tests")
    log = REPO_ROOT / seal.READ_LOG_REL
    before = log.read_bytes() if log.exists() else None
    assert rs.main(["--window", "test"]) == rs.REFUSED_RC
    assert "no freeze record" in capsys.readouterr().err
    assert (log.read_bytes() if log.exists() else None) == before
    assert seal.active() is None


def test_cli_argument_rules(rs):
    with pytest.raises(SystemExit):
        rs.main(["--window", "validation", "--rerun-reason", "x"])
    for extra in (["--scenario", "dest_slots_0"], ["--forecast-run", "/x"], ["--no-export"]):
        with pytest.raises(SystemExit):
            rs.main(["--window", "test", *extra])


def _stub(seen):
    """A tiny pipeline: build and read the synthetic test truth through the layers."""
    def run(window):
        assert seal.active() is not None and window == Window.test() and window.is_test
        eia_co2.build_carbon(window=window)
        filled = truth_fill.fill_truth(window.init, window.F, ["PACE"], window=window)
        seen.append(filled.filter(pl.col("ts_utc") >= TEST_START).height)
        return 0
    return run


def test_the_entry_point_opens_the_window_and_logs_every_read(rs, tmp_path):
    repo, data, results = sealkit.setup(tmp_path)
    seen = []
    rc = rs.run_test(repo_root=repo, data_dir=data, results_dir=results, pipeline=_stub(seen))
    assert rc == 0 and seen and seen[0] > 0
    log = sealkit.read_log(results)
    events = [r["event"] for r in log]
    assert events[0] == "invocation" and events[-1] == "close"
    assert events.count("read") == 4 + 2  # four workbooks, then the test table and the balance
    assert log[-1]["outcome"] == "ok" and log[-1]["n_reads"] == 6
    assert seal.active() is None
    with pytest.raises(seal.SealError):
        Window.test()


def _commit(repo, msg):
    sealkit.git(repo, "add", "-A")
    sealkit.git(repo, "commit", "-qm", msg)


REFUSALS = {
    "a_dirty": (lambda repo, data, res: (repo / "x.txt").write_text("x"), r"\(a\).*not clean"),
    "a_code": (lambda repo, data, res: ((repo / "code.py").write_text("X = 2\n"),
                                        _commit(repo, "code change")), r"\(a\).*differs"),
    "b_tag": (lambda repo, data, res: sealkit.git(repo, "tag", "-d", seal.FREEZE_TAG),
              r"\(b\) no tag"),
    "c_input": (lambda repo, data, res: (data / seal.TRACE_REL).write_text("edited\n"),
                r"\(c\).*trace_seren.csv changed"),
    "d_done": (lambda repo, data, res: ((res / "test").mkdir(parents=True),
                                        (res / "test" / "manifest.json").write_text("{}"),
                                        _commit(repo, "a completed run")),
               r"\(d\).*completed test run"),
}


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_each_refusal_exits_non_zero_with_its_reason_and_reads_nothing(rs, tmp_path, capsys,
                                                                       case):
    repo, data, results = sealkit.setup(tmp_path)
    mutate, reason = REFUSALS[case]
    mutate(repo, data, results)
    seen = []
    rc = rs.run_test(repo_root=repo, data_dir=data, results_dir=results, pipeline=_stub(seen))
    assert rc == rs.REFUSED_RC != 0
    err = capsys.readouterr().err
    assert "refused" in err
    import re

    assert re.search(reason, err), err
    assert seen == []  # the pipeline never ran
    assert not (results / "test_reads.jsonl").exists()  # nothing was opened, so nothing logged
    assert seal.active() is None


def test_a_rerun_with_a_reason_is_allowed_and_logged(rs, tmp_path):
    repo, data, results = sealkit.setup(tmp_path)
    REFUSALS["d_done"][0](repo, data, results)
    rc = rs.run_test(repo_root=repo, data_dir=data, results_dir=results,
                     rerun_reason="export bug fixed in abc123 (documented)", pipeline=_stub([]))
    assert rc == 0
    inv = sealkit.read_log(results)[0]
    assert inv["event"] == "invocation"
    assert inv["rerun_reason"] == "export bug fixed in abc123 (documented)"
    assert json.loads(json.dumps(inv))["test_F"] == seal.iso(sealkit.F_SYN)


def test_a_failing_pipeline_is_logged_as_an_error(rs, tmp_path):
    repo, data, results = sealkit.setup(tmp_path)

    def boom(window):
        raise RuntimeError("synthetic failure")

    with pytest.raises(RuntimeError):
        rs.run_test(repo_root=repo, data_dir=data, results_dir=results, pipeline=boom)
    assert sealkit.read_log(results)[-1]["outcome"].startswith("error: RuntimeError")
