"""Driver-level export rules (Task 7 fix round 1): the fallback's low-n and H2 statement,
the illustrative-job criteria, staged export, and the data-driven framing."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from gridpilot.eval import h2_decision, paired_block_bootstrap
from gridpilot.results import unenveloped_numbers

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_slice.py"


@pytest.fixture(scope="module")
def rs():
    spec = importlib.util.spec_from_file_location("run_slice", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _weeks(n, seed, scale=1.0):
    rng = np.random.default_rng(seed)
    return rng.normal(100.0, 10.0, n) * scale


def _by_b(a, b):
    return {k: paired_block_bootstrap(a, b, block=k, reps=200) for k in (2, 4, 8)}


def test_contrast_b8_low_n_on_fallback_even_when_n_is_large(rs):
    a, b = _weeks(13, 1), _weeks(13, 2, 0.9)
    val = rs._contrast_record("L", "U", _by_b(a, b), "r", 13, "validation")
    fb = rs._contrast_record("L", "U", _by_b(a, b), "r", 13, "fallback")
    assert "low-n" not in val["blocks"]["8"]["labels"]
    assert "low-n" in fb["blocks"]["8"]["labels"]
    assert "low-n" not in fb["blocks"]["4"]["labels"]
    assert fb["blocks"]["8"]["n_weeks"]["evidence"] == "measured"
    # n <= 8 is low-n on any window.
    small = rs._contrast_record("L", "U", _by_b(a[:6], b[:6]), "r", 6, "validation")
    assert "low-n" in small["blocks"]["8"]["labels"]
    assert unenveloped_numbers(fb) == []


def test_h2_fallback_makes_no_decision_statement(rs):
    w, l_ = _weeks(13, 3), _weeks(13, 4, 0.8)  # L clearly lower: a decision on validation
    h = h2_decision(w, l_, reps=200)
    assert h["decided"]
    val = rs._h2_record(h, "r", "validation")
    assert val["status"] == "ok" and val["direction"] == h["direction"] and val["decided"]
    fb = rs._h2_record(h, "r", "fallback")
    assert fb["status"] == "not_evaluated"
    assert fb["direction"] is None and fb["decided"] is None
    assert fb["reason"] == "F14.4: the fallback makes no H2 decision statement"
    # The intervals are kept as estimates.
    assert fb["intervals"]["4"]["diff_kg_ci95"]["value"] == list(h["intervals"][4]["diff_kg_ci"])
    assert "low-n" in fb["intervals"]["8"]["labels"]
    assert fb["n_weeks"]["evidence"] == "measured"
    assert unenveloped_numbers(fb) == []


def test_illustrative_criteria(rs):
    c = pl.DataFrame({"job_uid": ["a", "b", "c", "d", "e"],
                      "gpu_h": [0.1, 0.2, 0.2, 5.0, 100.0]})
    uid, med = rs.pick_literal(c)
    assert (uid, med) == ("b", 0.2)  # ties at the median go to the smaller ID
    uid, total = rs.pick_weighted_median(c)
    assert total == pytest.approx(105.5)
    assert uid == "e"  # cumulative 5.5 < 52.75 until e
    c2 = pl.DataFrame({"job_uid": ["x", "y", "z"], "gpu_h": [1.0, 1.0, 2.0]})
    assert rs.pick_weighted_median(c2)[0] == "y"  # cumulative 2.0 >= 2.0 at y


def test_export_results_stages_all_four(rs, tmp_path):
    src, dst = tmp_path / "run", tmp_path / "results"
    src.mkdir()
    for a in rs.ARTIFACTS:
        (src / a).write_text(json.dumps({"name": a}))
    rs.export_results(src, dst)
    assert sorted(p.name for p in dst.iterdir()) == sorted(rs.ARTIFACTS)
    (src / "metrics.json").unlink()
    (dst / "manifest.json").write_text("old")
    with pytest.raises(FileNotFoundError):
        rs.export_results(src, dst)
    assert (dst / "manifest.json").read_text() == "old"  # nothing replaced on failure
    assert not list(dst.glob(".*staged"))


def _acct(k_vs_s, w_vs_s, l_vs_s):
    def c(d, lo, hi, sav=0.0):
        return {4: {"diff_kg": d, "diff_kg_ci": (lo, hi), "saving": sav}}

    sites = {"PACE": 10.0, "BPAT": 70.0, "CISO": 20.0, "NEVP": 10.0}
    return {"contrasts": {"K_vs_S": c(*k_vs_s), "W_vs_S": c(*w_vs_s), "L_vs_S": c(*l_vs_s),
                          "W_time_vs_U": c(1, 0, 2, 0.0072), "L_time_vs_U": c(1, 0, 2, 0.0075),
                          "L_vs_U": c(1, 0, 2, 0.2251)},
            "scores": {"L": {"execution_kwh_by_site": sites}}}


def test_framing_follows_the_intervals(rs):
    txt = rs.framing_text(_acct((-10007, -19330, -1522), (-4940, -14832, 3642),
                                (-5104, -15294, 4152)))
    assert txt.startswith("Validation: no dynamic carbon search (K, W, L) improves on the "
                          "static clean-region ranking S (H3 not supported)")
    assert "K emits more than S (10.0 t more" in txt
    assert "the interval excludes zero" in txt
    assert "W and L are not distinguishable from S" in txt
    assert "Waiting in Utah alone saves about 0.7%" in txt
    assert "mostly to BPAT (70% of L's remote execution energy)" in txt
    better = rs.framing_text(_acct((5000, 1000, 9000), (-1, -5, 5), (-1, -5, 5)))
    assert "K emits less than S" in better and "H3 supported for K" in better
