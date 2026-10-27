"""Stage 3 T11 fix round 1: the adversarial review's attack scenarios (rev-t11/scripts/attack.py,
freeze_types.py) as tests. D-059: the sealed year is opened exactly once; any rerun is logged.
Synthetic temp repos and data only."""

from __future__ import annotations

import copy
import dataclasses
import importlib.util
import json
import os
import stat
import subprocess
import threading
from pathlib import Path

import pytest
import sealkit
from sealkit import commit_all, git

from gridpilot import paths, seal
from gridpilot.splits import TEST_START
from gridpilot.window import Window, resolve

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_slice.py"
FIX = json.loads(sealkit.FIXTURE.read_text())


@pytest.fixture(autouse=True)
def _no_leaked_session():
    assert seal.active() is None
    yield
    assert seal.active() is None


@pytest.fixture(scope="module")
def rs():
    spec = importlib.util.spec_from_file_location("run_slice", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def refused(repo, data, pattern, **kw):
    with pytest.raises(seal.SealError, match=pattern):
        sealkit.authorize(repo, data, **kw)


def _write_log(results: Path, *events: str, config: str | None = None) -> None:
    results.mkdir(exist_ok=True)
    lines = [json.dumps({"event": e, **({"config_sha256": config} if config else {})})
             for e in events]
    (results / "test_reads.jsonl").write_text("".join(x + "\n" for x in lines))


# --------------------------------------------------------------------------- (a), I2


def test_S1_renaming_code_into_the_test_outputs_is_refused(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    (repo / "results" / "test").mkdir(parents=True)
    git(repo, "mv", "code.py", "results/test/code.py")
    commit_all(repo, "rename code into results/test")
    refused(repo, data, r"\(a\).*(D code.py|R)")


def test_S1b_a_plain_code_edit_after_the_freeze_is_refused(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    (repo / "code.py").write_text("FROZEN = True\n" * 30)
    commit_all(repo, "edit")
    refused(repo, data, r"\(a\).*M code.py")


def test_S4b_outputs_deleted_in_a_later_commit_are_refused(tmp_path):
    repo, data, results = sealkit.setup(tmp_path)
    (results / "test").mkdir(parents=True)
    (results / "test" / "manifest.json").write_text("{}")
    _write_log(results, "invocation")
    commit_all(repo, "outputs")
    refused(repo, data, r"\(d\).*already opened")  # S4a: a completed, committed run
    git(repo, "rm", "-rq", "results/test")
    git(repo, "commit", "-qm", "drop the outputs")
    refused(repo, data, r"\(a\).*D results/test/manifest.json", rerun_reason="x")


def test_S4c_a_truncated_read_log_is_refused(tmp_path):
    repo, data, results = sealkit.setup(tmp_path)
    _write_log(results, "invocation", "read", "close")
    commit_all(repo, "log")
    (results / "test_reads.jsonl").write_text("")
    commit_all(repo, "truncate the log")
    refused(repo, data, r"\(a\).*append-only", rerun_reason="x")
    # rewriting a line (same length) is refused too
    repo2, data2, res2 = sealkit.setup(tmp_path / "rw")
    _write_log(res2, "invocation", "read")
    commit_all(repo2, "log")
    _write_log(res2, "invocation", "rea_")
    commit_all(repo2, "rewrite")
    refused(repo2, data2, r"\(a\).*append-only", rerun_reason="x")


def test_appending_to_the_log_and_outputs_after_the_freeze_is_allowed_with_a_reason(tmp_path):
    repo, data, results = sealkit.setup(tmp_path)
    _write_log(results, "invocation", "read", "close")
    commit_all(repo, "run 1 log")
    with open(results / "test_reads.jsonl", "a") as f:
        f.write(json.dumps({"event": "invocation"}) + "\n")
    (results / "test").mkdir()
    (results / "test" / "metrics.json").write_text("{}")
    commit_all(repo, "run 2")
    assert sealkit.authorize(repo, data, rerun_reason="documented bug").prior_openings


# --------------------------------------------------------------------------- (d), I1


def test_S2b_a_deleted_uncommitted_run_is_still_detected_by_its_run_directory(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    (repo / "runs" / "test" / "20261028T030000Z").mkdir(parents=True)  # gitignored
    refused(repo, data, r"\(d\).*runs/test/")
    assert sealkit.authorize(repo, data, rerun_reason="r").prior_openings


def test_a_legacy_test_carbon_table_is_a_prior_opening(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    p = data / seal.LEGACY_CARBON_TEST_REL
    p.parent.mkdir(parents=True)
    p.write_bytes(b"x")
    refused(repo, data, r"\(d\).*test carbon table")


def test_S3_a_committed_log_of_a_crashed_run_is_a_prior_opening(tmp_path):
    repo, data, results = sealkit.setup(tmp_path)
    _write_log(results, "invocation", "read", "close")
    commit_all(repo, "commit the read log of a crashed run")
    refused(repo, data, r"\(d\).*committed read log holds 2")


def test_history_on_any_branch_is_a_prior_opening(tmp_path):
    repo, data, results = sealkit.setup(tmp_path)
    git(repo, "checkout", "-qb", "side")
    (results / "test").mkdir(parents=True)
    (results / "test" / "manifest.json").write_text("{}")
    commit_all(repo, "outputs on a side branch")
    git(repo, "checkout", "-q", "main")
    refused(repo, data, r"\(d\).*git history touches the test outputs")


def test_a_working_tree_log_alone_is_a_prior_opening(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    res = tmp_path / "res"  # outside the repo, so (a) does not see it
    _write_log(res, "invocation", "read")
    refused(repo, data, r"\(d\).*working-tree read log", results=res)


# --------------------------------------------------------------------------- (b), I3


def test_S5_an_edited_record_or_a_moved_tag_is_refused(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    p = repo / seal.FREEZE_REL
    d = json.loads(p.read_text())
    d["L_max_leaf_nodes"]["PACE/ci_consumed"] = 31
    p.write_text(json.dumps(d, indent=2) + "\n")
    commit_all(repo, "edit the freeze record")
    refused(repo, data, r"\(b\).*does not match")  # S5a: the old tag
    msg = seal.freeze_tag_message(seal.file_sha256(p))
    git(repo, "tag", "-f", "-a", seal.FREEZE_TAG, "-m", msg)
    refused(repo, data, r"\(b\).*exactly one parent, the freeze commit")  # S5b: re-tagged
    git(repo, "tag", "-f", "-a", seal.FREEZE_TAG, "-m", msg, d["freeze_commit"])
    refused(repo, data, r"\(b\).*targets .* not the last commit")  # S5c: tag on the freeze commit


def test_a_record_commit_that_changes_more_than_the_record_is_refused(tmp_path):
    data = sealkit.make_data_dir(tmp_path)
    repo = sealkit.make_repo(tmp_path, data, tag="none")
    git(repo, "reset", "-q", "--soft", "HEAD~1")
    (repo / "extra.txt").write_text("x\n")
    commit_all(repo, "freeze record plus something else")
    git(repo, "tag", "-a", seal.FREEZE_TAG, "-m",
        seal.freeze_tag_message(seal.file_sha256(repo / seal.FREEZE_REL)))
    refused(repo, data, r"\((a|b)\)")


def _with_origin(tmp_path, repo):
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    git(repo, "remote", "add", "origin", str(origin))
    return origin


def test_the_tag_must_equal_the_tag_on_origin(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    _with_origin(tmp_path, repo)
    refused(repo, data, r"\(b\).*on origin \(None")  # not pushed
    git(repo, "push", "-q", "origin", f"refs/tags/{seal.FREEZE_TAG}")
    a = sealkit.authorize(repo, data)
    assert a.remote_tag == git(repo, "rev-parse", f"refs/tags/{seal.FREEZE_TAG}")
    # moving the local tag (same target, new tag object) breaks the match
    msg = seal.freeze_tag_message(seal.file_sha256(repo / seal.FREEZE_REL))
    git(repo, "tag", "-f", "-a", seal.FREEZE_TAG, "-m", msg + "\nmoved\n")
    refused(repo, data, r"\(b\).*differs from the local tag")


def test_an_unreachable_origin_refuses_unless_an_override_is_logged(tmp_path):
    repo, data, results = sealkit.setup(tmp_path)
    git(repo, "remote", "add", "origin", str(tmp_path / "no-such-remote.git"))
    refused(repo, data, r"\(b\) cannot reach origin")
    a = sealkit.authorize(repo, data, remote_tag_override="offline at the venue")
    with seal.test_mode(a):
        pass
    inv = sealkit.read_log(results)[0]
    assert inv["remote_tag"] == "unverified: offline at the venue"


def test_an_earlier_invocation_with_a_different_record_is_refused(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    res = tmp_path / "res"
    _write_log(res, "invocation", config="f" * 64)
    refused(repo, data, r"\(b\).*freeze record ffffffffffff.*cannot be compared", results=res,
            rerun_reason="x")


# --------------------------------------------------------------------------- M2: hidden changes


def test_S6_skip_worktree_assume_unchanged_and_excluded_files_are_refused(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path / "a")
    git(repo, "update-index", "--skip-worktree", "code.py")
    (repo / "code.py").write_text("FROZEN = False  # changed after the freeze\n")
    refused(repo, data, r"\(a\).*skip-worktree or assume-unchanged")
    repo, data, _ = sealkit.setup(tmp_path / "b")
    git(repo, "update-index", "--assume-unchanged", "code.py")
    (repo / "code.py").write_text("FROZEN = False  # changed\n")
    refused(repo, data, r"\(a\).*skip-worktree or assume-unchanged")
    repo, data, _ = sealkit.setup(tmp_path / "c")
    (repo / ".git" / "info" / "exclude").write_text("evil.py\n")
    (repo / "evil.py").write_text("x = 1\n")
    refused(repo, data, r"\(a\).*\.git/info/exclude.*evil.py")


def test_ignored_code_under_lab_is_refused_but_caches_are_not(tmp_path):
    data = sealkit.make_data_dir(tmp_path)
    repo = sealkit.make_repo(tmp_path, data, extra_files={
        "lab/keep.py": "x = 1\n", "lab/.gitignore": "override.py\n__pycache__/\n.venv/\n"})
    (repo / "lab" / "__pycache__").mkdir()
    (repo / "lab" / "__pycache__" / "keep.cpython-312.pyc").write_bytes(b"x")
    (repo / "lab" / ".venv").mkdir()
    (repo / "lab" / ".venv" / "pyvenv.cfg").write_text("x")
    # hypothesis keeps a self-ignored cache under lab/ (as in the real checkout)
    (repo / "lab" / ".hypothesis" / "constants").mkdir(parents=True)
    (repo / "lab" / ".hypothesis" / ".gitignore").write_text("*\n")
    assert sealkit.authorize(repo, data).F == sealkit.F_SYN  # caches and the venv are fine
    (repo / "lab" / "override.py").write_text("PATCH = True\n")  # ignored, so git is blind
    refused(repo, data, r"\(a\) ignored files under lab/.*lab/override.py")


def test_this_checkouts_ignored_lab_files_are_all_tolerated():
    """A regression guard for the real run: every ignored path under lab/ in this checkout is a
    cache or the environment, so check (a) would not refuse it."""
    out = seal._git_out(paths.REPO_ROOT, "ls-files", "--others", "--ignored",
                        "--exclude-standard", "--directory", "--", "lab").splitlines()
    assert [p for p in out if not seal.LAB_IGNORED_OK.search(p)] == []


# --------------------------------------------------------------------------- I4: real roots


def test_real_use_requires_the_repository_roots(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    with pytest.raises(seal.SealError, match=r"\(I4\).*repo_root"):
        seal.authorize(repo_root=repo, data_dir=data, results_dir=repo / "results")
    (data / seal.SYNTHETIC_MARKER).unlink()
    with pytest.raises(seal.SealError, match=r"\(I4\).*SYNTHETIC"):
        sealkit.authorize(repo, data)
    with pytest.raises(seal.SealError, match=r"\(I4\)"):
        seal.authorize(repo_root=paths.REPO_ROOT, data_dir=data, synthetic=True)


def test_run_test_gates_pipeline_and_out_dir_behind_synthetic(rs, tmp_path, capsys):
    repo, data, results = sealkit.setup(tmp_path)
    for kw in ({"pipeline": lambda w: 0}, {"out_dir": tmp_path / "runs"}):
        rc = rs.run_test(repo_root=repo, data_dir=data, results_dir=results, **kw)
        assert rc == rs.REFUSED_RC
        assert "(I4)" in capsys.readouterr().err
    assert not (results / "test_reads.jsonl").exists()


def test_cli_rejects_out_with_the_test_window(rs):
    with pytest.raises(SystemExit):
        rs.main(["--window", "test", "--out", "/tmp/x"])
    with pytest.raises(SystemExit):
        rs.main(["--window", "validation", "--remote-tag-override", "x"])


# --------------------------------------------------------------------------- I5: manifests


def test_an_input_hash_must_match_its_committed_manifest(tmp_path):
    data = sealkit.make_data_dir(tmp_path)
    good = {rel: seal.file_sha256(data / rel) for rel in seal.TEST_INPUTS}
    # the record and the data agree on a doctored workbook, but the committed manifest does not
    wb = data / seal.WORKBOOK_REL.format(ba="PACE")
    repo = sealkit.make_repo(tmp_path, data)
    wb.write_bytes(wb.read_bytes() + b"\0")
    rec = json.loads((repo / seal.FREEZE_REL).read_text())
    rec["input_sha256"] = {**good, seal.WORKBOOK_REL.format(ba="PACE"): seal.file_sha256(wb)}
    (repo / seal.FREEZE_REL).write_text(json.dumps(rec, indent=2) + "\n")
    git(repo, "tag", "-d", seal.FREEZE_TAG)
    git(repo, "reset", "-q", "--soft", "HEAD~1")
    commit_all(repo, "freeze record")
    git(repo, "tag", "-a", seal.FREEZE_TAG, "-m",
        seal.freeze_tag_message(seal.file_sha256(repo / seal.FREEZE_REL)))
    refused(repo, data, r"\(I5\).*PACE.xlsx.*committed manifest eia930.json")


def test_the_balance_table_needs_its_derivation_record_or_a_logged_exception(tmp_path):
    repo, data, results = sealkit.setup(tmp_path)
    a = sealkit.authorize(repo, data)
    assert any("balance.parquet: no committed derivation record" in e for e in a.exceptions)
    with seal.test_mode(a):
        pass
    assert sealkit.read_log(results)[0]["exceptions"] == list(a.exceptions)


def _repo_with_derivation(tmp_path, mutate=None):
    """A synthetic repo whose freeze commit holds a balance derivation record (as T12's
    rebuild will commit), with its raw input listed in the committed eia930 manifest."""
    data = sealkit.make_data_dir(tmp_path)
    raw = data / "raw" / "eia930" / "EIA930_BALANCE_2025_Jul_Dec.csv"
    raw.write_text("synthetic balance csv\n")
    der = {"output": seal.BALANCE_REL,
           "output_sha256": seal.file_sha256(data / seal.BALANCE_REL),
           "inputs_sha256": {raw.relative_to(data).as_posix(): seal.file_sha256(raw)},
           "code": "gridpilot.data.eia930.build_balance", "lab_tree": "synthetic"}
    if mutate:
        mutate(der)
    repo = sealkit.make_repo(
        tmp_path, data, extra_files={seal.BALANCE_DERIVATION_REL: json.dumps(der) + "\n"},
        eia930_extra=[{"file": raw.name, "sha256": seal.file_sha256(raw)}])
    return repo, data


def test_a_matching_balance_derivation_record_clears_the_exception(tmp_path):
    repo, data = _repo_with_derivation(tmp_path)
    assert sealkit.authorize(repo, data).exceptions == ()


def test_a_mismatched_balance_derivation_record_is_refused(tmp_path):
    repo, data = _repo_with_derivation(
        tmp_path, lambda d: d["inputs_sha256"].update(
            {k: "0" * 64 for k in d["inputs_sha256"]}))
    refused(repo, data, r"\(I5\).*derivation input")


# --------------------------------------------------------------------------- M3: freeze types

TYPE_CASES = {
    "S means non-numeric": lambda d: d["s_ranking"].__setitem__(
        "mean_consumed_ci_g_kwh", {"PACE": "x", "BPAT": 1, "CISO": 2, "NEVP": 3}),
    "S means wrong sites": lambda d: d["s_ranking"].__setitem__(
        "mean_consumed_ci_g_kwh", {"ERCO": True}),
    "S means missing": lambda d: d["s_ranking"].pop("mean_consumed_ci_g_kwh"),
    "S means inconsistent with the order": lambda d: d["s_ranking"].__setitem__(
        "mean_consumed_ci_g_kwh", {"BPAT": 900.0, "CISO": 200.0, "NEVP": 320.0, "PACE": 580.0}),
    "S means NaN": lambda d: d["s_ranking"]["mean_consumed_ci_g_kwh"].__setitem__(
        "PACE", float("nan")),
    "L leaf 15.0 float": lambda d: d["L_max_leaf_nodes"].__setitem__("PACE/ci_consumed", 15.0),
    "L leaf bool": lambda d: d["L_max_leaf_nodes"].__setitem__("PACE/ci_consumed", True),
    "deployed_policy extra key": lambda d: d["deployed_policy"].__setitem__("extra", 1),
    "validation_run.run_id int": lambda d: d["validation_run"].__setitem__("run_id", 20261027),
    "rule_trace item extra key": lambda d: d["deployed_policy"]["rule_trace"][0].__setitem__(
        "x", 1),
    "s_ranking window reversed": lambda d: d["s_ranking"].__setitem__(
        "window", ["2025-10-29T00:00:00Z", "2023-01-01T00:00:00Z"]),
    "frozen_at in the future": lambda d: d.__setitem__("frozen_at", "2099-01-01T00:00:00Z"),
    "input key with ./": lambda d: d["input_sha256"].__setitem__(
        "./raw/eia930/ba_workbooks/PACE.xlsx", "0" * 64),
    "s_ranking fit_at": lambda d: d["s_ranking"].__setitem__("fit_at", "2025-10-30T00:00:00Z"),
}


@pytest.mark.parametrize("case", sorted(TYPE_CASES))
def test_freeze_type_attacks_are_refused(tmp_path, case):
    d = copy.deepcopy(FIX)
    TYPE_CASES[case](d)
    p = tmp_path / "freeze.json"
    p.write_text(json.dumps(d))
    with pytest.raises(seal.SealError, match="invalid"):
        seal.load_freeze(p)


def test_the_validation_reference_must_match_the_committed_results(tmp_path):
    vr = {"run_id": "20261027T160656Z", "metrics_canonical_sha256": "a" * 64}
    repo, data, _ = sealkit.setup(tmp_path, record_overrides={"validation_run": vr})
    refused(repo, data, r"\(M3\) validation_run")


def test_the_validation_reference_hashes_the_serialized_metrics(tmp_path):
    from gridpilot.results import canonical_hash

    repo, _data, _ = sealkit.setup(tmp_path)
    ref = seal.validation_reference(repo)
    met = json.loads((repo / "results" / "metrics.json").read_text())
    assert ref == {"run_id": "20261027T160656Z", "metrics_canonical_sha256": canonical_hash(met)}


# --------------------------------------------------------------------------- S7, M5, M6, M10


def test_S7_the_context_closes_and_an_authorization_is_single_use(tmp_path):
    repo, data, _results = sealkit.setup(tmp_path)
    a = sealkit.authorize(repo, data)
    forged = dataclasses.replace(a, rerun_reason="forged", input_sha256={})
    with pytest.raises(RuntimeError), seal.test_mode(a):
        w = Window.test()
        raise RuntimeError("boom")
    assert seal.active() is None
    with pytest.raises(seal.SealError):
        Window.test()
    with pytest.raises(seal.SealError):
        resolve(w)
    with pytest.raises(seal.SealError, match="unused Authorization"), seal.test_mode(a):
        pass  # S7d: reused
    with pytest.raises(seal.SealError, match="unused Authorization"), seal.test_mode(forged):
        pass  # S7h: a dataclasses.replace copy
    assert not a.lock_path.exists()


def test_S7e_another_thread_cannot_read_while_the_context_is_active(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    out = {}
    with seal.test_mode(sealkit.authorize(repo, data)) as s:
        def t():
            try:
                out["r"] = seal.sealed_read(data / seal.BALANCE_REL, purpose="thread",
                                            columns=["ts_utc"],
                                            time_range=(TEST_START, sealkit.F_SYN)).height
            except seal.SealError as e:
                out["r"] = e
        th = threading.Thread(target=t)
        th.start()
        th.join()
        assert seal.active() is s
        s.pid = -1  # another process (a forked child keeps the variable, not the pid)
        assert seal.active() is None
        s.pid = os.getpid()
    assert isinstance(out["r"], seal.SealError)


def test_M10_a_held_lock_refuses_a_second_session(tmp_path):
    repo, data, _results = sealkit.setup(tmp_path)
    a = sealkit.authorize(repo, data)
    a.lock_path.parent.mkdir(parents=True, exist_ok=True)
    a.lock_path.write_text("pid 1\n")  # pid 1 is alive
    with pytest.raises(seal.SealError, match="another test-mode session"), seal.test_mode(a):
        pass


def test_M11_unexpected_failures_are_refusals(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / seal.SYNTHETIC_MARKER).write_text("x")
    (tmp_path / "notarepo").mkdir()
    with pytest.raises(seal.SealError):
        seal.authorize(repo_root=tmp_path / "notarepo", data_dir=tmp_path / "data",
                       synthetic=True)


# --------------------------------------------------------------------------- M1, I6, M8


def test_M1_the_close_line_logs_rc_and_a_non_zero_rc_is_not_ok(rs, tmp_path):
    repo, data, results = sealkit.setup(tmp_path)
    assert rs.run_test(synthetic=True, repo_root=repo, data_dir=data, results_dir=results,
                       pipeline=lambda w: 3) == 3
    close = sealkit.read_log(results)[-1]
    assert close["event"] == "close" and close["rc"] == 3 and close["outcome"] == "rc=3"
    assert close["exported"] is False


def test_I6_run_directories_are_read_only_when_the_context_closes(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    run = tmp_path / "runs" / "20261028T000000Z"
    run.mkdir(parents=True)
    (run / "truth_fill.parquet").write_bytes(b"sealed")
    with seal.test_mode(sealkit.authorize(repo, data)) as s:
        s.run_dirs.append(run)
        assert os.access(run / "truth_fill.parquet", os.W_OK)
    mode = stat.S_IMODE((run / "truth_fill.parquet").stat().st_mode)
    assert mode == 0o444


def test_M8_verify_exports_against_the_last_export_line(tmp_path):
    res = tmp_path / "results"
    (res / "test").mkdir(parents=True)
    (res / "test" / "metrics.json").write_text('{"a": 1}\n')
    h = seal.file_sha256(res / "test" / "metrics.json")
    assert seal.verify_exports(res) == ["the read log has no export line"]
    (res / "test_reads.jsonl").write_text(
        json.dumps({"event": "export", "artifacts_sha256": {"metrics.json": h}}) + "\n")
    assert seal.verify_exports(res) == []
    (res / "test" / "metrics.json").write_text('{"a": 2}\n')
    (res / "test" / "extra.json").write_text("{}")
    assert seal.verify_exports(res) == ["metrics.json differs from the logged export",
                                        "extra.json was not in the logged export"]


def test_M9_a_rerun_archives_the_earlier_artifacts(rs, tmp_path):
    dst = tmp_path / "test"
    dst.mkdir()
    (dst / "manifest.json").write_text('{"run_id": "20261028T010000Z"}')
    (dst / "metrics.json").write_text("{}")
    hist = rs.archive_test_results(dst)
    assert hist == str(dst / "history" / "20261028T010000Z")
    assert sorted(p.name for p in Path(hist).iterdir()) == ["manifest.json", "metrics.json"]
    assert not list(dst.glob("*.json"))
    assert rs.archive_test_results(dst) is None


def test_the_test_window_is_never_constructible_from_a_mutated_validation_window():
    v = Window.validation()
    with pytest.raises(ValueError):
        dataclasses.replace(v, F=sealkit.F_SYN)
    assert v.read_end == TEST_START


# --------------------------------------------------------------------------- Astra F05


def test_s_ranking_uses_only_rows_published_by_the_fit_time(rs, tmp_path, monkeypatch):
    """S's ranking at fit_at counts a row only if ts_utc + 1 h + 96 h <= fit_at (the
    forecasts' consumed-CI envelope, forecast.as_of)."""
    from datetime import timedelta

    import polars as pl

    from gridpilot import forecast as fcmod

    fit = rs.RANK_FIT_AT
    env = fcmod.ENVELOPE_H["ci_consumed"]
    last_ok = fit - timedelta(hours=1 + env)  # published exactly at fit_at
    rows = []
    for ba, base in (("BPAT", 80.0), ("CISO", 200.0), ("NEVP", 300.0), ("PACE", 500.0)):
        rows += [(ba, last_ok - timedelta(hours=1), base), (ba, last_ok, base)]
    # one row an hour later (published after fit_at) would flip BPAT above PACE if counted
    rows.append(("BPAT", last_ok + timedelta(hours=1), 1e6))
    df = pl.DataFrame(rows, schema={"ba": pl.Utf8, "ts_utc": pl.Datetime("us", "UTC"),
                                    "ci_consumed_g_kwh": pl.Float64}, orient="row")
    p = tmp_path / "carbon.parquet"
    df.write_parquet(p)
    monkeypatch.setattr(rs, "CARBON_PATH", p)
    order, means = rs.s_ranking()
    assert order == ["BPAT", "CISO", "NEVP", "PACE"]
    assert means["BPAT"] == 80.0
    assert fcmod.as_of(df, fit, env)["ts_utc"].max() == last_ok  # the forecasts' rule
    assert rs.RANK_FIT_AT == fcmod.VAL_FIT_AT
