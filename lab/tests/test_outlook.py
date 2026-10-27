"""Stage 3 T19: the grid outlook's leakage boundary, seal refusals and artifact contract, on
synthetic series (no grid file is read here)."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from gridpilot import forecast as fc
from gridpilot import outlook as ol
from gridpilot.paths import RESULTS_DIR
from gridpilot.results import validate_artifact
from gridpilot.splits import TEST_START

LAB = Path(__file__).resolve().parents[1]
FIT_AT = datetime(2024, 6, 1, tzinfo=UTC)
HIST = datetime(2024, 3, 1, tzinfo=UTC)
ISSUE = datetime(2024, 9, 15, 16, tzinfo=UTC)  # 10:00 MDT


def _series(end: datetime = datetime(2024, 10, 1, tzinfo=UTC)) -> pl.DataFrame:
    ts = pl.datetime_range(HIST, end, interval="1h", closed="left", time_unit="us",
                           time_zone="UTC", eager=True)
    rng = np.random.default_rng(0)
    h = np.arange(len(ts))
    frames = []
    for k, ba in enumerate(ol.SITES):
        v = 300 + 100 * k + 60 * np.sin(2 * np.pi * h / 24) + 20 * np.sin(2 * np.pi * h / 168)
        v = v + rng.normal(0, 10, len(ts))
        frames.append(pl.DataFrame({"ba": ba, "ts_utc": ts, "value": v}))
    return pl.concat(frames)


@pytest.fixture(scope="module")
def setup():
    s = _series()
    models = {ba: ol.fit_models(s, ba, FIT_AT, HIST, leaves=(15,)) for ba in ol.SITES}
    issues = fc.issue_times(datetime(2024, 6, 2, tzinfo=UTC), datetime(2024, 6, 22, tzinfo=UTC))
    skill = ol.skill_by_horizon(s, models, issues)
    return s, models, skill


def _build(series, models, skill, issue=ISSUE, **kw):
    kw.setdefault("days", 7)
    return ol.build_outlook(series, models, skill, issue, ranking=["BPAT", "CISO", "NEVP", "PACE"],
                            ranking_means={"BPAT": 1.0, "CISO": 2.0, "NEVP": 3.0, "PACE": 4.0},
                            ranking_note="synthetic", run_id="20240101T000000Z", **kw)


def _strip(art: dict) -> dict:
    return {k: v for k, v in art.items() if k not in ("regions", "days")} | {
        "regions": {b: {k: v for k, v in r.items() if k != "last_published_hour_utc"}
                    for b, r in art["regions"].items()}, "days": art["days"]}


# ------------------------------------------------------------------------ horizon


def test_day_one_is_the_day_ahead_target_and_dst_days_have_23_or_25_hours():
    assert ol.day_hours(ISSUE, 1) == fc.target_hours(ISSUE)
    fall = datetime(2024, 11, 1, 16, tzinfo=UTC)  # issue Fri; D+2 = Sun Nov 3 (DST ends)
    assert len(ol.day_hours(fall, 2)) == 25
    spring = datetime(2025, 3, 7, 17, tzinfo=UTC)  # D+2 = Sun Mar 9 (DST starts)
    assert len(ol.day_hours(spring, 2)) == 23


def test_latest_issue_is_the_last_10am_denver_at_or_before_now():
    assert ol.latest_issue(datetime(2026, 10, 28, 3, tzinfo=UTC)) == datetime(2026, 10, 27, 16,
                                                                             tzinfo=UTC)
    assert ol.latest_issue(datetime(2026, 10, 27, 16, tzinfo=UTC)) == datetime(2026, 10, 27, 16,
                                                                              tzinfo=UTC)


def test_skill_issues_end_before_the_seal():
    iss = ol.skill_issues()
    assert iss and ol.day_hours(iss[-1], ol.MAX_DAYS)[-1] + fc.H <= TEST_START
    assert iss[0] >= datetime(2024, 11, 1, tzinfo=UTC)


# ------------------------------------------------------------------------ leakage


def test_no_value_published_after_the_issue_changes_the_outlook(setup):
    s, models, skill = setup
    base = _build(s, models, skill)
    late = pl.col("ts_utc") + pl.duration(hours=1 + ol.ENV_H) > ISSUE
    poisoned = s.with_columns(pl.when(late).then(1e6).otherwise(pl.col("value")).alias("value"))
    assert _build(poisoned, models, skill) == base
    cut = s.filter(~late)
    assert _strip(_build(cut, models, skill)) == _strip(base)


def test_a_value_published_just_before_the_issue_does_change_it(setup):
    s, models, skill = setup  # the cut is not over-conservative: the newest published row counts
    base = _build(s, models, skill)
    newest = ISSUE - timedelta(hours=1 + ol.ENV_H)
    bumped = s.with_columns(pl.when(pl.col("ts_utc") > newest - timedelta(hours=200))
                            .then(pl.col("value") + 500).otherwise(pl.col("value")).alias("value"))
    assert _build(bumped, models, skill)["regions"] != base["regions"]


def test_features_refuse_an_unpublished_row():
    s = _series().filter(pl.col("ba") == "PACE")
    with pytest.raises(fc.LeakageError):
        fc.l_features(s.filter(pl.col("ts_utc") < ISSUE), ISSUE, ol.ENV_H, "America/Denver",
                      target=ol.TARGET, targets=ol.horizon_hours(ISSUE)[0])
    f = ol.horizon_features(s, ISSUE, "America/Denver")  # cuts with as_of itself
    assert f.height == len(ol.horizon_hours(ISSUE)[0]) and set(f["day"]) == set(range(1, 8))


def test_models_refuse_an_issue_before_their_fit(setup):
    s, models, _ = setup
    f = ol.horizon_features(s.filter(pl.col("ba") == "PACE"), FIT_AT - timedelta(days=3),
                            "America/Denver")
    with pytest.raises(fc.LeakageError):
        models["PACE"].predict(f, "W")


# ------------------------------------------------------------------------ seal


def test_an_issue_reaching_the_seal_is_refused_without_live(setup):
    s, models, skill = setup
    for issue, days in ((datetime(2025, 10, 31, 16, tzinfo=UTC), 1),
                        (datetime(2025, 10, 26, 16, tzinfo=UTC), 7),
                        (datetime(2026, 10, 27, 16, tzinfo=UTC), 7)):
        with pytest.raises(ol.OutlookSealError):
            _build(s, models, skill, issue=issue, days=days)


def test_skill_refuses_targets_in_the_sealed_window(setup):
    s, models, _ = setup
    with pytest.raises(ol.OutlookSealError):
        ol.skill_by_horizon(s, models, [datetime(2025, 10, 27, 16, tzinfo=UTC)])


def test_the_cli_refuses_sealed_dates_and_live_before_any_read(monkeypatch, tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("outlook_cli", LAB / "scripts" / "outlook.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)

    def boom(*a, **k):
        raise AssertionError("a series was loaded before the refusal")

    monkeypatch.setattr(cli.fc, "load_series", boom)
    monkeypatch.setattr(cli.ol, "seal_opened", lambda *a, **k: False)
    out = ["--out", str(tmp_path / "o.json"), "--runs", str(tmp_path / "runs")]
    assert cli.main(["--issue", "2025-10-30", *out]) == 2
    assert cli.main(["--issue", "2026-10-28", *out]) == 2
    assert cli.main(["--live", *out]) == 2
    assert not (tmp_path / "o.json").exists() and not (tmp_path / "runs").exists()


RUN = "20261028T040000Z"


def _parquet(tmp_path: Path) -> Path:
    d = tmp_path / "runs" / RUN / "raw"
    d.mkdir(parents=True)
    p = d / "PACE.parquet"
    ts = [TEST_START + timedelta(hours=k) for k in range(48)]
    pl.DataFrame({"ba": "PACE", "ts_utc": ts, "ci_consumed_g_kwh": np.arange(48.0)}).with_columns(
        pl.col("ts_utc").dt.cast_time_unit("us")).write_parquet(p)
    return p


def _repo(tmp_path: Path, tag: bool) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    g = ["git", "-C", str(r), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*g, "init", "-q"], check=True)
    subprocess.run([*g, "commit", "-q", "--allow-empty", "-m", "x"], check=True)
    if tag:
        subprocess.run([*g, "tag", "-a", "config-freeze", "-m", "t"], check=True)
    return r


def _open(results: Path, log: bool = True) -> None:
    (results / "test").mkdir(parents=True, exist_ok=True)
    (results / "test" / "manifest.json").write_text("{}")
    if log:
        (results / "test_reads.jsonl").write_text('{"event": "invocation"}\n')


def _read(p, tmp_path, live=True, purpose="test read", repo=None):
    return ol.live_read(p, purpose=purpose, columns=["ts_utc", "ci_consumed_g_kwh"],
                        time_range=(TEST_START, TEST_START + timedelta(hours=24)), live=live,
                        reader=lambda b: pl.read_parquet(b), results_dir=tmp_path / "results",
                        repo_root=repo or tmp_path / "repo", live_root=tmp_path / "runs")


def test_seal_opened_needs_the_manifest_a_read_log_and_the_freeze_tag(tmp_path):
    results = tmp_path / "results"
    assert not ol.seal_opened(results, _repo(tmp_path, tag=True))
    _open(results, log=False)
    assert not ol.seal_opened(results, tmp_path / "repo")
    _open(results)
    assert ol.seal_opened(results, tmp_path / "repo")
    untagged = tmp_path / "u"
    untagged.mkdir()
    assert not ol.seal_opened(results, _repo(untagged, tag=False))


def test_live_read_refuses_without_live_or_before_the_seal_opens(tmp_path):
    p = _parquet(tmp_path)
    _repo(tmp_path, tag=True)
    with pytest.raises(ol.OutlookSealError, match="--live"):
        _read(p, tmp_path, live=False)
    with pytest.raises(ol.OutlookSealError, match="not been opened"):
        _read(p, tmp_path)
    _open(tmp_path / "results")
    with pytest.raises(ol.OutlookSealError, match="purpose"):
        _read(p, tmp_path, purpose=" ")
    assert not (tmp_path / "results" / ol.LIVE_LOG_NAME).exists()


def test_live_read_refuses_anything_but_a_fresh_download_in_a_run_dir(tmp_path):
    p = _parquet(tmp_path)
    _repo(tmp_path, tag=True)
    _open(tmp_path / "results")
    frozen = tmp_path / "data" / "processed" / "carbon_hourly.parquet"
    frozen.parent.mkdir(parents=True)
    frozen.write_bytes(p.read_bytes())
    stray = tmp_path / "runs" / RUN / "PACE.parquet"
    stray.write_bytes(p.read_bytes())
    for bad in (frozen, stray, tmp_path / "runs" / "latest" / "raw" / "PACE.parquet"):
        with pytest.raises(ol.OutlookSealError, match="live_read reads only"):
            _read(bad, tmp_path)
    assert not (tmp_path / "results" / ol.LIVE_LOG_NAME).exists()


def test_live_read_logs_every_read_before_returning_rows(tmp_path):
    p = _parquet(tmp_path)
    _repo(tmp_path, tag=True)
    _open(tmp_path / "results")
    rows = _read(p, tmp_path)
    assert rows.height == 24 and rows.columns == ["ts_utc", "ci_consumed_g_kwh"]
    _read(p, tmp_path, purpose="second")
    log = tmp_path / "results" / ol.LIVE_LOG_NAME
    lines = [json.loads(x) for x in log.read_text().splitlines()]
    assert [x["purpose"] for x in lines] == ["test read", "second"]
    assert lines[0]["sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()
    assert lines[0]["time_range"][0].startswith("2025-11-01") and lines[0]["code_commit"]


def test_stale_live_data_is_refused():
    issue = datetime(2026, 10, 27, 16, tzinfo=UTC)
    ts = [issue - timedelta(days=5, hours=k) for k in range(48)]
    fresh = pl.DataFrame({"ba": [b for b in ol.SITES for _ in ts], "ts_utc": ts * 4,
                          "value": [1.0] * 192})
    assert set(ol.check_fresh(fresh, issue)) == set(ol.SITES)
    old = fresh.with_columns(pl.when(pl.col("ba") == "NEVP").then(None)
                             .otherwise(pl.col("value")).alias("value"))
    with pytest.raises(ol.StaleDataError, match="NEVP"):
        ol.check_fresh(old, issue)
    with pytest.raises(ol.StaleDataError, match="PACE"):
        ol.check_fresh(fresh.with_columns(pl.col("ts_utc") - timedelta(days=3)), issue)


def test_only_the_outlook_cli_uses_live_read():
    """Any reference counts (a call, a callback, an alias import), not just a call by name."""
    users = set()
    for root in (LAB / "src", LAB / "scripts"):
        for f in root.rglob("*.py"):
            rel = f.relative_to(LAB).as_posix()
            if rel == "src/gridpilot/outlook.py":
                continue
            for n in ast.walk(ast.parse(f.read_text())):
                hit = (isinstance(n, ast.Name) and n.id == "live_read") or (
                    isinstance(n, ast.Attribute) and n.attr == "live_read") or (
                    isinstance(n, ast.ImportFrom) and any(a.name == "live_read" for a in n.names)) or (
                    isinstance(n, ast.Constant) and n.value == "live_read")
                if hit:
                    users.add(rel)
    assert users == {"scripts/outlook.py"}


# ------------------------------------------------------------------------ artifact


def test_the_outlook_is_enveloped_banded_and_labelled(setup, tmp_path):
    s, models, skill = setup
    art = _build(s, models, skill)
    assert validate_artifact(art) == [] and art["window"] == "validation" and art["demo"]
    n = len(art["hours_utc"])
    for r in art["regions"].values():
        p10, p50, p90 = (np.array(r[k]["value"]) for k in ("p10", "p50", "p90"))
        assert len(p50) == n and (p10 <= p50).all() and (p50 <= p90).all()
        assert r["p50"]["evidence"] == "forecast" and r["climatology"]["evidence"] == "modeled"
    assert [d["day"] for d in art["days"]] == [f"D+{k}" for k in range(1, 8)]
    for d in art["days"]:
        assert d["router_s_pick"] == "BPAT"
        assert set(d["regions"]) == set(ol.SITES)
        assert all(r["status"] in ("forecast", "climatology_only") for r in d["regions"].values())
    path = tmp_path / "outlook.json"
    ol.write_outlook(path, art, live=False)
    assert json.loads(path.read_text()) == json.loads(json.dumps(art))


def test_write_outlook_refuses_sealed_dates_in_a_demo_and_needs_window_live(tmp_path):
    bad = {"window": "validation", "issue_utc": "2026-10-27T16:00:00Z"}
    with pytest.raises(ValueError, match="contract errors"):  # m7: the full validator in live mode
        ol.write_outlook(tmp_path / "o.json", {"window": "live", "x": {
            "value": 1.0, "unit": "g", "evidence": "guessed", "provenance_id": "p", "status": "ok",
            "reason": None}}, live=True)
    with pytest.raises(ValueError, match="sealed timestamp"):
        ol.write_outlook(tmp_path / "o.json", bad, live=False)
    with pytest.raises(ValueError, match="window 'live'"):
        ol.write_outlook(tmp_path / "o.json", bad, live=True)
    ol.write_outlook(tmp_path / "o.json", bad | {"window": "live"}, live=True)
    assert not (tmp_path / "o.json").with_name(".o.json.tmp").exists()


def test_bands_widen_or_hold_with_horizon_on_synthetic_noise(setup):
    _, _, skill = setup
    w = [skill["PACE"][d]["q"]["K"][1] - skill["PACE"][d]["q"]["K"][0] for d in range(1, 8)]
    assert all(x > 0 for x in w)


def test_the_committed_outlook_is_a_labelled_demo_or_a_live_run_after_the_seal():
    p = RESULTS_DIR / "outlook.json"
    if not p.exists():
        pytest.skip("no results/outlook.json yet (make outlook)")
    art = json.loads(p.read_text())
    assert art["kind"] == "outlook"
    if art["window"] == "validation":
        assert art["demo"] is True and "demo" in art["note"]
        assert validate_artifact(art) == []
        assert art["lineage"]["git_clean"] is True, "export the demo at a clean commit (M2)"
        issue = datetime.fromisoformat(art["issue_utc"])
        assert issue not in ol.skill_issues(), "the demo issue must not be a skill issue (m5)"
    else:
        assert art["window"] == "live" and art["demo"] is False and ol.seal_opened()
