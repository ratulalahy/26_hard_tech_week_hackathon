"""Stage 3 T11: the freeze record, the refusal checks (a)–(d) and B7, the test-mode context
and `sealed_read` with its append-only read log. Every test uses synthetic sealed rows in a
temporary data directory and a temporary git repository; the real sealed window is never
read."""

from __future__ import annotations

import copy
import json
import os
from datetime import UTC, datetime, timedelta

import jsonschema
import polars as pl
import pytest
import sealkit

from gridpilot import seal
from gridpilot.splits import TEST_START
from gridpilot.window import Window

SCHEMA = json.loads((sealkit.FIXTURE.parents[3] / seal.FREEZE_SCHEMA_REL).read_text())
FIX = json.loads(sealkit.FIXTURE.read_text())


@pytest.fixture(autouse=True)
def _no_leaked_session():
    assert seal.active() is None
    yield
    assert seal.active() is None


# --------------------------------------------------------------------------- freeze record


def test_fixture_matches_the_json_schema_and_loads():
    jsonschema.validate(FIX, SCHEMA)
    f = seal.load_freeze(sealkit.FIXTURE)
    assert f.test_F == datetime(2026, 10, 25, tzinfo=UTC)
    assert f.test_fit_at == seal.TEST_FIT_AT == datetime(2025, 10, 29, tzinfo=UTC)
    assert f.test_history_start == seal.TEST_HISTORY_START == datetime(2023, 1, 1, tzinfo=UTC)
    assert set(f.l_max_leaf_nodes) == set(seal.SERIES)
    assert f.s_order == ["BPAT", "CISO", "NEVP", "PACE"]


def test_series_and_leaf_grid_match_the_forecast_module():
    from gridpilot import forecast

    assert seal.SERIES == tuple(f"{ba}/{t}" for ba, t in forecast.RUN_SERIES)
    assert seal.LEAF_NODES == forecast.MAX_LEAF_NODES


BAD = {
    "fit_at": ("test_fit_at", "2025-10-30T00:00:00Z"),
    "history": ("test_history_start", "2022-01-01T00:00:00Z"),
    "F_past_end": ("test_F", "2026-11-02T00:00:00Z"),
    "F_at_seal": ("test_F", "2025-11-01T00:00:00Z"),
    "F_not_midnight": ("test_F", "2026-10-24T12:00:00Z"),
    "leaf": ("L_max_leaf_nodes", {**FIX["L_max_leaf_nodes"], "PACE/solar": 63}),
    "series": ("L_max_leaf_nodes", {k: 15 for k in list(FIX["L_max_leaf_nodes"])[:-1]}),
    "s_order": ("s_ranking", {**FIX["s_ranking"], "order": ["BPAT", "CISO", "PACE", "PACE"]}),
    "s_window_sealed": ("s_ranking", {**FIX["s_ranking"],
                                      "window": ["2025-01-01T00:00:00Z", "2025-12-01T00:00:00Z"]}),
    "commit": ("freeze_commit", "abc"),
    "policy": ("deployed_policy", {"name": "H", "rule_trace": FIX["deployed_policy"]["rule_trace"]}),
    "trace": ("deployed_policy", {"name": "W", "rule_trace": []}),
    "input_sha": ("input_sha256", {"raw/x.xlsx": "nope"}),
    "input_abs": ("input_sha256", {"/abs/x.xlsx": "0" * 64}),
    "snapshot": ("snapshot_id", "05efabe78"),
    "validation": ("validation_run", {"run_id": "x"}),
}


@pytest.mark.parametrize("case", sorted(BAD))
def test_load_freeze_refuses_an_invalid_record(tmp_path, case):
    key, value = BAD[case]
    d = copy.deepcopy(FIX)
    d[key] = value
    p = tmp_path / "freeze.json"
    p.write_text(json.dumps(d))
    with pytest.raises(seal.SealError, match="invalid"):
        seal.load_freeze(p)


@pytest.mark.parametrize("case", ["fit_at", "history", "leaf", "series", "commit", "policy",
                                  "trace", "input_sha", "snapshot", "validation"])
def test_the_json_schema_rejects_the_same_records(case):
    key, value = BAD[case]
    d = copy.deepcopy(FIX)
    d[key] = value
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(d, SCHEMA)


def test_load_freeze_refuses_missing_and_unknown_keys(tmp_path):
    for mutate in (lambda d: d.pop("snapshot_id"), lambda d: d.update(extra=1)):
        d = copy.deepcopy(FIX)
        mutate(d)
        p = tmp_path / "f.json"
        p.write_text(json.dumps(d))
        with pytest.raises(seal.SealError):
            seal.load_freeze(p)
    with pytest.raises(seal.SealError, match="not frozen"):
        seal.load_freeze(tmp_path / "absent.json")


# --------------------------------------------------------------------------- outside the context


def test_sealed_read_refuses_outside_test_mode_and_logs_nothing(tmp_path):
    data = sealkit.make_data_dir(tmp_path)
    with pytest.raises(seal.SealError, match="test-mode context"):
        seal.sealed_read(data / seal.BALANCE_REL, purpose="x", columns=["ts_utc"],
                         time_range=(TEST_START, sealkit.F_SYN))
    assert not list(tmp_path.rglob("test_reads.jsonl"))


def test_window_test_refuses_outside_test_mode():
    with pytest.raises(seal.SealError):
        Window.test()
    with pytest.raises(seal.SealError):
        Window.named("test")
    with pytest.raises(seal.SealError):
        Window("test", seal.TEST_INIT, TEST_START, sealkit.F_SYN)


def test_test_mode_accepts_only_an_authorization_from_authorize(tmp_path):
    repo, data, _results = sealkit.setup(tmp_path)
    auth = sealkit.authorize(repo, data)
    forged = seal.Authorization(**{k: getattr(auth, k) for k in (
        "freeze", "repo_root", "data_dir", "results_dir", "code_commit", "rerun_reason",
        "manifests_sha256", "input_sha256")})
    with pytest.raises(seal.SealError, match="Authorization"), seal.test_mode(forged):
        pass
    with pytest.raises(seal.SealError), seal.test_mode(object()):
        pass


# --------------------------------------------------------------------------- refusals (a)–(d), B7


def test_a_clean_synthetic_repo_is_authorized(tmp_path):
    repo, data, _results = sealkit.setup(tmp_path)
    auth = sealkit.authorize(repo, data)
    assert auth.F == sealkit.F_SYN
    assert auth.code_commit == sealkit.git(repo, "rev-parse", "HEAD")
    assert auth.rerun_reason is None


def test_a_refuses_a_dirty_tree(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    (repo / "scratch.txt").write_text("untracked\n")
    with pytest.raises(seal.SealError, match=r"\(a\).*not clean"):
        sealkit.authorize(repo, data)
    (repo / "scratch.txt").unlink()
    (repo / "code.py").write_text("FROZEN = False\n")
    with pytest.raises(seal.SealError, match=r"\(a\).*not clean"):
        sealkit.authorize(repo, data)


def test_a_refuses_a_head_that_changed_code_after_the_freeze(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    (repo / "code.py").write_text("FROZEN = 'changed'\n")
    sealkit.git(repo, "commit", "-qam", "post-freeze code change")
    with pytest.raises(seal.SealError, match=r"\(a\).*differs from the freeze commit.*code.py"):
        sealkit.authorize(repo, data)


def test_a_refuses_a_head_that_is_not_a_descendant(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path, record_overrides={"freeze_commit": "1" * 40})
    with pytest.raises(seal.SealError, match=r"\(a\) HEAD .* is not the freeze commit"):
        sealkit.authorize(repo, data)


def test_a_allows_committed_test_outputs_after_the_freeze(tmp_path):
    repo, data, results = sealkit.setup(tmp_path)
    (results / "test").mkdir(parents=True)
    (results / "test" / "metrics.json").write_text("{}\n")
    (results / "test_reads.jsonl").write_text("")
    sealkit.git(repo, "add", "-A")
    sealkit.git(repo, "commit", "-qm", "test outputs")
    assert sealkit.authorize(repo, data).F == sealkit.F_SYN


def test_b_refuses_a_missing_or_lightweight_tag(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path / "none", tag="none")
    with pytest.raises(seal.SealError, match=r"\(b\) no tag"):
        sealkit.authorize(repo, data)
    repo, data, _ = sealkit.setup(tmp_path / "light", tag="lightweight")
    with pytest.raises(seal.SealError, match=r"\(b\).*lightweight"):
        sealkit.authorize(repo, data)


def test_b_refuses_a_freeze_record_whose_sha_differs_from_the_tag(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path, tag_sha="f" * 64)
    with pytest.raises(seal.SealError, match=r"\(b\).*does not match"):
        sealkit.authorize(repo, data)


def test_b_refuses_an_edited_and_recommitted_freeze_record(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    p = repo / seal.FREEZE_REL
    d = json.loads(p.read_text())
    d["L_max_leaf_nodes"]["PACE/ci_consumed"] = 31
    p.write_text(json.dumps(d, indent=2) + "\n")
    sealkit.git(repo, "commit", "-qam", "retune L after the freeze")
    with pytest.raises(seal.SealError, match=r"\(b\).*does not match"):
        sealkit.authorize(repo, data)


def test_c_refuses_a_changed_or_missing_input(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    bal = data / seal.BALANCE_REL
    pl.read_parquet(bal).head(10).write_parquet(bal)
    with pytest.raises(seal.SealError, match=r"\(c\).*balance.parquet changed"):
        sealkit.authorize(repo, data)
    bal.unlink()
    with pytest.raises(seal.SealError, match=r"\(c\).*missing"):
        sealkit.authorize(repo, data)


def test_c_refuses_a_record_without_every_test_input(tmp_path):
    data = sealkit.make_data_dir(tmp_path)
    only = {seal.BALANCE_REL: seal.file_sha256(data / seal.BALANCE_REL)}
    repo = sealkit.make_repo(tmp_path, data, record_overrides={"input_sha256": only})
    with pytest.raises(seal.SealError, match=r"\(c\).*no hash for the test inputs"):
        sealkit.authorize(repo, data)


def test_d_refuses_a_completed_run_unless_a_reason_is_given(tmp_path):
    repo, data, results = sealkit.setup(tmp_path)
    (results / "test").mkdir(parents=True)
    (results / "test" / "manifest.json").write_text("{}\n")
    sealkit.git(repo, "add", "-A")
    sealkit.git(repo, "commit", "-qm", "a completed test run")
    with pytest.raises(seal.SealError, match=r"\(d\).*completed test run"):
        sealkit.authorize(repo, data)
    with pytest.raises(seal.SealError, match=r"\(d\).*must not be empty"):
        sealkit.authorize(repo, data, rerun_reason="   ")
    auth = sealkit.authorize(repo, data, rerun_reason="bug #12 in the export (documented)")
    with seal.test_mode(auth):
        pass
    inv = [r for r in sealkit.read_log(results) if r["event"] == "invocation"]
    assert inv[-1]["rerun_reason"] == "bug #12 in the export (documented)"


def test_b7_refuses_a_snapshot_mismatch(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path, record_overrides={"snapshot_id": "0" * 12})
    with pytest.raises(seal.SealError, match=r"\(B7\).*snapshot"):
        sealkit.authorize(repo, data)


def test_b7_reads_manifests_from_git_not_the_working_copy(tmp_path):
    repo, data, _ = sealkit.setup(tmp_path)
    man = repo / "data" / "manifests" / "eia930.json"
    man.write_text('{"edited": true}\n')
    sealkit.git(repo, "commit", "-qam", "edit a manifest after the freeze")
    # HEAD changed a manifest: (a) refuses before B7 even looks.
    with pytest.raises(seal.SealError, match=r"\(a\)"):
        sealkit.authorize(repo, data)


def test_b7_refuses_a_growing_manifest(tmp_path):
    repo, _data, _ = sealkit.setup(tmp_path)
    snap = json.loads(seal.committed_bytes(repo, seal.SNAPSHOT_REL))
    snap["sources"]["eia930"]["status"] = "growing"
    freeze = seal.load_freeze(repo / seal.FREEZE_REL)
    with pytest.raises(seal.SealError, match=r"\(B7\)"):
        p = repo / seal.SNAPSHOT_REL
        p.write_text(json.dumps(snap))
        sealkit.git(repo, "commit", "-qam", "x")
        seal._check_manifests(repo, freeze)


def test_scenario_catalog_must_match_the_code(tmp_path):
    cat = copy.deepcopy(FIX["scenario_catalog"])
    cat["primary"]["dest_slots"] = 1024
    repo, data, _ = sealkit.setup(tmp_path, record_overrides={"scenario_catalog": cat})
    with pytest.raises(seal.SealError, match="primary scenario differs"):
        sealkit.authorize(repo, data)


# --------------------------------------------------------------------------- inside the context


def test_sealed_read_logs_before_returning_sealed_rows(tmp_path, monkeypatch):
    repo, data, results = sealkit.setup(tmp_path)
    synced = []
    real_fsync = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (synced.append(fd), real_fsync(fd)))
    auth = sealkit.authorize(repo, data)
    with seal.test_mode(auth) as s:
        assert Window.test().F == sealkit.F_SYN
        assert Window.test().read_end == sealkit.F_SYN
        t0 = TEST_START - timedelta(days=1)
        rows = seal.sealed_read(data / seal.BALANCE_REL, purpose="unit test: sentinel rows",
                                columns=["ba", "ts_utc", "demand_adj_mw"],
                                time_range=(t0, sealkit.F_SYN), where=pl.col("ba") == "PACE")
        assert s.n_reads == 1
    assert rows["ts_utc"].max() == sealkit.F_SYN - timedelta(hours=1)
    assert rows["ts_utc"].min() == t0
    assert set(rows.filter(pl.col("ts_utc") >= TEST_START)["demand_adj_mw"]) == {9000.0}
    assert rows.columns == ["ba", "ts_utc", "demand_adj_mw"]
    log = sealkit.read_log(results)
    assert [r["event"] for r in log] == ["invocation", "read", "close"]
    r = log[1]
    for k in ("utc", "purpose", "path", "sha256", "columns", "time_range", "code_commit",
              "config_sha256", "caller"):
        assert r[k], k
    assert r["sha256"] == seal.file_sha256(data / seal.BALANCE_REL)
    assert r["config_sha256"] == seal.file_sha256(repo / seal.FREEZE_REL)
    assert r["code_commit"] == auth.code_commit
    assert r["time_range"] == [seal.iso(t0), seal.iso(sealkit.F_SYN)]
    assert "test_seal:test_sealed_read_logs_before_returning_sealed_rows" in r["caller"]
    assert log[2]["outcome"] == "ok" and log[2]["n_reads"] == 1
    assert len(synced) == 3  # one fsync per line


def test_the_read_log_is_append_only_across_sessions(tmp_path):
    repo, data, _results = sealkit.setup(tmp_path)
    for _ in range(2):
        with seal.test_mode(sealkit.authorize(repo, data, results=tmp_path / "res")):
            seal.sealed_read(data / seal.BALANCE_REL, purpose="p", columns=["ts_utc"],
                             time_range=(TEST_START, sealkit.F_SYN))
    log = sealkit.read_log(tmp_path / "res")
    assert [r["event"] for r in log] == ["invocation", "read", "close"] * 2
    assert log[0]["session"] != log[3]["session"]


def test_sealed_read_refuses_past_F_unfrozen_or_changed_files(tmp_path):
    repo, data, results = sealkit.setup(tmp_path)
    other = data / "interim" / "other.parquet"
    pl.DataFrame({"ts_utc": [TEST_START]}).write_parquet(other)
    with seal.test_mode(sealkit.authorize(repo, data)):
        with pytest.raises(seal.SealError, match="after the test cutoff"):
            seal.sealed_read(data / seal.BALANCE_REL, purpose="p", columns=["ts_utc"],
                             time_range=(TEST_START, sealkit.F_SYN + timedelta(hours=1)))
        with pytest.raises(seal.SealError, match="neither a frozen input"):
            seal.sealed_read(other, purpose="p", columns=["ts_utc"],
                             time_range=(TEST_START, sealkit.F_SYN))
        with pytest.raises(seal.SealError, match="purpose"):
            seal.sealed_read(data / seal.BALANCE_REL, purpose=" ", columns=["ts_utc"],
                             time_range=(TEST_START, sealkit.F_SYN))
        bal = data / seal.BALANCE_REL
        pl.read_parquet(bal).head(5).write_parquet(bal)
        with pytest.raises(seal.SealError, match="changed since the freeze"):
            seal.sealed_read(bal, purpose="p", columns=["ts_utc"],
                             time_range=(TEST_START, sealkit.F_SYN))
    assert [r["event"] for r in sealkit.read_log(results)] == ["invocation", "close"]


def test_after_the_context_everything_is_sealed_again(tmp_path):
    repo, data, _results = sealkit.setup(tmp_path)
    with seal.test_mode(sealkit.authorize(repo, data)):
        w = Window.test()
    with pytest.raises(seal.SealError):
        w.check_active("read")
    with pytest.raises(seal.SealError):
        seal.sealed_read(data / seal.BALANCE_REL, purpose="p", columns=["ts_utc"],
                         time_range=(TEST_START, sealkit.F_SYN))
    with pytest.raises(seal.SealError):
        Window.test()


def test_an_error_inside_the_context_is_logged_and_closes_it(tmp_path):
    repo, data, results = sealkit.setup(tmp_path)
    with pytest.raises(RuntimeError), seal.test_mode(sealkit.authorize(repo, data)):
        raise RuntimeError("boom")
    assert sealkit.read_log(results)[-1]["outcome"].startswith("error: RuntimeError: boom")


def test_nested_test_mode_is_refused(tmp_path):
    repo, data, _results = sealkit.setup(tmp_path)
    auth = sealkit.authorize(repo, data)
    with seal.test_mode(auth), pytest.raises(seal.SealError, match="already active"):  # noqa: SIM117
        with seal.test_mode(auth):
            pass


# --------------------------------------------------------------------------- B7 snapshot refresh

REGISTERED_SNAPSHOT = "05efabe781cc"
REGISTERED_OPENMETEO = "aa1b514a8d3ad6e824696b6929c0919db49b281a2c14ebd657cba6adc7f2552d"
REPO = sealkit.FIXTURE.parents[3]


def _repo_snapshot() -> dict:
    """The repository's (committed) data/manifests/snapshot.json."""
    return json.loads((REPO / seal.SNAPSHOT_REL).read_text())


def test_the_snapshot_is_frozen_and_differs_from_the_registered_one_only_in_openmeteo():
    snap = _repo_snapshot()
    sources = snap["sources"]
    assert all(v["status"] == "frozen" for v in sources.values())  # openmeteo is final
    assert seal.snapshot_id_of(sources) == snap["snapshot_id"]
    for name, rec in sources.items():
        got = seal.file_sha256(REPO / seal.MANIFESTS_REL / f"{name}.json")
        assert got == rec["manifest_sha256"], name
    # Put back the registered openmeteo hash: the registered validation snapshot id returns,
    # so no other manifest changed since the validation run.
    old = {k: dict(v) for k, v in sources.items()}
    old["openmeteo"]["manifest_sha256"] = REGISTERED_OPENMETEO
    assert seal.snapshot_id_of(old) == REGISTERED_SNAPSHOT


def test_run_slice_accepts_the_registered_and_the_refreshed_snapshot():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "run_slice", sealkit.FIXTURE.parents[2] / "scripts" / "run_slice.py")
    rs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rs)
    assert set(rs.ACCEPTED_SNAPSHOT_IDS) == {REGISTERED_SNAPSHOT, _repo_snapshot()["snapshot_id"]}
