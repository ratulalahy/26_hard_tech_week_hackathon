"""Stage 3 T11 fix round 2: the re-checker's scenarios (rev-t11b/scripts/attack2.py, attack3.py)
as tests. N1 openings across git worktrees (the shared witness), N2 the lock in the git common
dir and the stale-lock recovery, N3 the bug-fix rerun (lead ruling), N4-N8, N11. Synthetic temp
repos and data only."""

from __future__ import annotations

import contextvars
import copy
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest
import sealkit
from sealkit import commit_all, git

from gridpilot import paths, seal
from gridpilot.data import eia_co2
from gridpilot.splits import TEST_START

FIX = json.loads(sealkit.FIXTURE.read_text())
TESTS = Path(__file__).resolve().parent


@pytest.fixture(autouse=True)
def _no_leaked_session():
    assert seal.active() is None
    yield
    assert seal.active() is None


def refused(repo, data, pattern, **kw):
    with pytest.raises(seal.SealError, match=pattern):
        sealkit.authorize(repo, data, **kw)


def run_session(repo, data, results=None, fail=False, **kw):
    """One synthetic test-mode session with one sealed read."""
    a = sealkit.authorize(repo, data, results=results, **kw)
    try:
        with seal.test_mode(a) as s:
            seal.sealed_read(s.data_path(seal.BALANCE_REL), purpose="probe",
                             columns=["ba", "ts_utc"], time_range=(TEST_START, sealkit.F_SYN))
            if fail:
                raise RuntimeError("bug in the pipeline")
            s.rc = 0
    except RuntimeError:
        pass
    return a


# --------------------------------------------------------------------------- N1: worktrees


def test_N1_an_opening_in_one_worktree_is_a_prior_opening_in_every_other(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    git(repo, "worktree", "add", "-q", "--detach", str(tmp_path / "wtA"), "HEAD")
    git(repo, "worktree", "add", "-q", "--detach", str(tmp_path / "wtB"), "HEAD")
    A, B = tmp_path / "wtA", tmp_path / "wtB"
    a = run_session(A, data, results=A / "results")
    w = a.witness_path
    assert w == (repo / ".git" / seal.WITNESS_REL).resolve()
    assert [r["event"] for r in sealkit.read_log(w.parent)] == []  # not the read log's name
    ev = [json.loads(x)["event"] for x in w.read_text().splitlines()]
    assert ev == ["invocation", "close"]
    refused(B, data, r"\(d\).*shared witness", results=B / "results")
    refused(repo, data, r"\(d\).*shared witness")
    assert sealkit.authorize(B, data, results=B / "results", rerun_reason="second worktree")


def test_N1_deleting_the_log_and_the_run_directories_leaves_the_witness(tmp_path):
    repo, data, results = sealkit.setup(tmp_path)
    run_session(repo, data)
    (results / "test_reads.jsonl").unlink()
    shutil.rmtree(repo / "runs", ignore_errors=True)
    refused(repo, data, r"\(d\).*shared witness \(gridpilot/test_openings.jsonl")


# --------------------------------------------------------------------------- N4: history


def _manual_log(results: Path) -> None:
    results.mkdir(exist_ok=True)
    (results / "test_reads.jsonl").write_text('{"event": "invocation"}\n')


def test_N4_a_log_removed_by_reset_hard_is_still_in_the_reflog(tmp_path):
    repo, data, results = sealkit.setup(tmp_path)
    _manual_log(results)
    commit_all(repo, "log")
    git(repo, "reset", "-q", "--hard", "HEAD~1")
    refused(repo, data, r"\(d\).*git history touches the test outputs")


def test_N4_a_log_on_an_orphan_branch_or_in_a_stash_is_found(tmp_path):
    repo, data, results = sealkit.setup(tmp_path / "orphan")
    git(repo, "checkout", "-q", "--orphan", "side")
    git(repo, "rm", "-rqf", ".")
    _manual_log(results)
    commit_all(repo, "orphan log")
    git(repo, "checkout", "-q", "-f", "main")
    refused(repo, data, r"\(d\).*git history")
    repo, data, results = sealkit.setup(tmp_path / "stash")
    _manual_log(results)
    git(repo, "stash", "-q", "-u")
    refused(repo, data, r"\(d\).*git history")


# --------------------------------------------------------------------------- N2: the lock

KILL = """
import os, signal, sys
sys.path.insert(0, {tests!r})
import sealkit
from gridpilot import seal
from pathlib import Path
a = sealkit.authorize(Path({repo!r}), Path({data!r}))
with seal.test_mode(a) as s:
    seal.sealed_read(s.data_path(seal.BALANCE_REL), purpose="p", columns=["ba", "ts_utc"],
                     time_range=(sealkit.TEST_START, sealkit.F_SYN))
    os.kill(os.getpid(), signal.SIGKILL)
"""


def test_N2_a_killed_session_leaves_a_stale_lock_and_the_documented_recovery_works(tmp_path):
    repo, data, _results = sealkit.setup(tmp_path)
    r = subprocess.run([sys.executable, "-c", KILL.format(tests=str(TESTS), repo=str(repo),
                                                          data=str(data))],
                       cwd=str(TESTS.parent), capture_output=True, text=True, check=False)
    assert r.returncode != 0
    lock = repo / ".git" / seal.LOCK_REL
    assert lock.exists()
    assert git(repo, "status", "--porcelain").splitlines() == ["?? results/test_reads.jsonl"]
    commit_all(repo, "commit only the read log of the crashed session")
    refused(repo, data, r"\(a\) a stale lock .*Recovery: delete the lock", rerun_reason="crash")
    lock.unlink()
    a = sealkit.authorize(repo, data, rerun_reason="session killed; fixed")
    assert any("shared witness" in p for p in a.prior_openings)


def test_N2_a_live_lock_names_the_open_session(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    lock = repo / ".git" / seal.LOCK_REL
    lock.parent.mkdir(parents=True)
    lock.write_text(f"pid {os.getpid()} now\n")
    refused(repo, data, rf"\(a\) another test-mode session is open \(pid {os.getpid()}")


# --------------------------------------------------------------------------- N3: bug-fix rerun


def _refreeze(repo: Path, mutate=None) -> dict:
    """A code fix after a crash: commit it, write a new record (new freeze_commit), commit
    the record alone, move the tag."""
    (repo / "code.py").write_text("FROZEN = True  # fixed the bug\n")
    commit_all(repo, "code fix")
    p = repo / seal.FREEZE_REL
    d = json.loads(p.read_text())
    d["freeze_commit"] = git(repo, "rev-parse", "HEAD")
    if mutate:
        mutate(d)
    p.write_text(json.dumps(d, indent=2) + "\n")
    commit_all(repo, "new freeze record")
    git(repo, "tag", "-f", "-a", seal.FREEZE_TAG, "-m",
        seal.freeze_tag_message(seal.file_sha256(p)))
    return d


def test_N3_a_bug_fix_rerun_with_a_new_record_is_accepted_and_logged(tmp_path):
    repo, data, results = sealkit.setup(tmp_path)
    run_session(repo, data, fail=True)
    old_sha = seal.file_sha256(repo / seal.FREEZE_REL)
    commit_all(repo, "commit the crashed run's read log")
    _refreeze(repo)
    refused(repo, data, r"\(d\).*already opened")
    a = sealkit.authorize(repo, data, rerun_reason="pipeline crashed: fixed bug X in abc")
    (ch,) = a.record_changes
    assert ch["old_sha256"] == old_sha and ch["new_sha256"] == a.freeze.sha256
    assert set(ch["changed"]) == {"freeze_commit"}
    with seal.test_mode(a) as s:
        s.rc = 0
    inv = [r for r in sealkit.read_log(results) if r["event"] == "invocation"][-1]
    assert inv["record_changes"][0]["old_sha256"] == old_sha


def test_N3_a_changed_decision_field_is_refused(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    run_session(repo, data, fail=True)
    commit_all(repo, "log")
    _refreeze(repo, lambda d: d["L_max_leaf_nodes"].__setitem__("PACE/ci_consumed", 31))
    refused(repo, data, r"\(b\).*changed \['L_max_leaf_nodes'\].*\(N3\)", rerun_reason="x")


def test_N3_a_new_freeze_commit_must_descend_from_the_old_one(tmp_path):
    repo, _data, _ = sealkit.setup(tmp_path)
    freeze = seal.parse_freeze(seal.committed_bytes(repo, seal.FREEZE_REL),
                               repo / seal.FREEZE_REL)
    tree = git(repo, "rev-parse", "HEAD^{tree}")
    orphan = git(repo, "commit-tree", tree, "-m", "unrelated")
    old = copy.deepcopy(freeze.raw)
    old["freeze_commit"] = orphan
    res = tmp_path / "res"
    res.mkdir()
    (res / "test_reads.jsonl").write_text(json.dumps(
        {"event": "invocation", "config_sha256": "e" * 64, "freeze_record": old}) + "\n")
    with pytest.raises(seal.SealError, match=r"does not descend from the earlier one"):
        seal._check_configs(repo, res, freeze, "rerun")


# --------------------------------------------------------------------------- N5: origin


def _bare(tmp_path, name):
    b = tmp_path / name
    subprocess.run(["git", "init", "-q", "--bare", str(b)], check=True)
    return b


def test_N5_real_use_needs_the_github_origin(tmp_path):
    repo, _data, _ = sealkit.setup(tmp_path)
    freeze = seal.parse_freeze(seal.committed_bytes(repo, seal.FREEZE_REL),
                               repo / seal.FREEZE_REL)
    head = git(repo, "rev-parse", "HEAD")
    with pytest.raises(seal.SealError, match=r"no origin.*github.com"):
        seal._check_tag(repo, freeze, head, None, synthetic=False)
    git(repo, "remote", "add", "origin", str(_bare(tmp_path, "evil.git")))
    with pytest.raises(seal.SealError, match=r"origin is .*evil.git, not https://github.com"):
        seal._check_tag(repo, freeze, head, None, synthetic=False)


def test_N5_a_decoy_ref_on_origin_does_not_match(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    git(repo, "remote", "add", "origin", str(_bare(tmp_path, "origin.git")))
    git(repo, "push", "-q", "origin", "main", "--tags")
    assert sealkit.authorize(repo, data).origin_url.endswith("origin.git")
    msg = seal.freeze_tag_message(seal.file_sha256(repo / seal.FREEZE_REL))
    git(repo, "tag", "-f", "-a", seal.FREEZE_TAG, "-m", msg + "moved\n")
    git(repo, "push", "-q", "origin", f"refs/tags/{seal.FREEZE_TAG}:refs/a/refs/tags/"
                                      f"{seal.FREEZE_TAG}")
    refused(repo, data, r"\(b\).*differs from the local tag")


# --------------------------------------------------------------------------- N6, N7


def test_N6_a_captured_context_cannot_read_after_close(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    with seal.test_mode(sealkit.authorize(repo, data)) as s:
        ctx = contextvars.copy_context()
        s.rc = 0
    assert ctx.run(seal.active) is None
    with pytest.raises(seal.SealError):
        ctx.run(lambda: seal.sealed_read(s.data_path(seal.BALANCE_REL), purpose="after close",
                                         columns=["ts_utc"],
                                         time_range=(TEST_START, sealkit.F_SYN)))


def test_N7_two_authorizations_cannot_both_open_the_window(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    a1, a2 = sealkit.authorize(repo, data), sealkit.authorize(repo, data)
    with seal.test_mode(a1) as s:
        s.rc = 0
    with pytest.raises(seal.SealError, match=r"\(d\).*opened after this authorization"), \
            seal.test_mode(a2):
        pass
    assert not a2.lock_path.exists()


# --------------------------------------------------------------------------- N8


def test_N8_synthetic_inputs_must_live_in_the_synthetic_dir(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    real = tmp_path / "realdata"
    data.rename(real)
    (real / seal.SYNTHETIC_MARKER).unlink()
    link = tmp_path / "data"
    link.mkdir()
    for n in ("raw", "interim"):
        (link / n).symlink_to(real / n)
    (link / seal.SYNTHETIC_MARKER).write_text("x")
    refused(repo, link, r"\(N8\).*resolves outside the synthetic data dir")


def test_N8_synthetic_results_may_not_land_in_the_repository(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    refused(repo, data, r"\(N8\).*results_dir", results=paths.REPO_ROOT / "results")


# --------------------------------------------------------------------------- N11


def test_N11_the_s_ranking_window_is_the_test_history(tmp_path):
    d = copy.deepcopy(FIX)
    d["s_ranking"]["window"] = ["2022-01-01T00:00:00Z", "2025-10-29T00:00:00Z"]
    p = tmp_path / "f.json"
    p.write_text(json.dumps(d))
    with pytest.raises(seal.SealError, match=r"s_ranking.window must be \[2023-01-01"):
        seal.load_freeze(p)


def test_N11_s_ranking_at_uses_the_publication_envelope(tmp_path):
    from gridpilot import forecast as fcmod

    assert eia_co2.CI_ENVELOPE_H == fcmod.ENVELOPE_H["ci_consumed"]
    fit = seal.TEST_FIT_AT
    last_ok = fit - timedelta(hours=1 + eia_co2.CI_ENVELOPE_H)
    rows = [(ba, last_ok, v) for ba, v in (("BPAT", 80.0), ("CISO", 200.0), ("NEVP", 300.0),
                                           ("PACE", 500.0))]
    rows.append(("BPAT", last_ok + timedelta(hours=1), 1e6))  # published after fit_at
    df = pl.DataFrame(rows, schema={"ba": pl.Utf8, "ts_utc": pl.Datetime("us", "UTC"),
                                    "ci_consumed_g_kwh": pl.Float64}, orient="row")
    p = tmp_path / "c.parquet"
    df.write_parquet(p)
    order, means = eia_co2.s_ranking_at(seal.TEST_HISTORY_START, fit, path=p)
    assert order == ["BPAT", "CISO", "NEVP", "PACE"] and means["BPAT"] == 80.0
    with pytest.raises(ValueError):
        eia_co2.s_ranking_at(seal.TEST_HISTORY_START, datetime(2025, 11, 2, tzinfo=UTC), path=p)
