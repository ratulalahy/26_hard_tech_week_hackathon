"""Stage 3 T17 (D-068): results/assumptions.json, the assumptions register and negative results
exported by notebooks/40_assumptions_and_reality.ipynb.

Every number in it must be read from a committed results file: each envelope's provenance_id is
`file#/json/pointer` (or `derived:op(a,b)` of two such pointers), and this test re-reads every
pointer and checks the value, unit and evidence. The envelope and seal checks are in
test_results.py (ARTIFACTS)."""

import hashlib
import json
import re
import subprocess

import pytest

from gridpilot.paths import REPO_ROOT, RESULTS_DIR

PATH = RESULTS_DIR / "assumptions.json"
NOTEBOOK = REPO_ROOT / "notebooks" / "40_assumptions_and_reality.ipynb"
WATER_REF = "origin/s3/t14-water"
BANNED = re.compile(r"\b(prove[sd]?|proving|confirm(s|ed)?)\b|(?<!not )\bavoided\b", re.IGNORECASE)

REGISTER_IDS = {"flexible_mobile", "dest_slots", "transfer", "kw_per_gpu", "pue", "bookings",
                "exact_runtimes", "replay_utah", "consumption_basis", "color_midpoint", "storage",
                "rush_threshold"}
NEGATIVE_IDS = {"waiting_in_utah", "g_zero", "h2_inconclusive", "h3_not_supported", "mobility_le_8",
                "dest_capacity_0", "storage_flat_marginal", "peak_relief_scale",
                "production_flatters_hydro", "illustrative_literal"}
OPS = {"ratio": lambda a, b: a / b, "abs_ratio": lambda a, b: abs(a) / b}


@pytest.fixture(scope="module")
def doc():
    if not PATH.exists():
        pytest.skip("results/assumptions.json not exported yet (run notebook 40)")
    return json.loads(PATH.read_text())


def _water_text() -> str | None:
    """The water illustration's text: results/water.json once merged, else the T14 branch's
    committed file (pending merge), else None. The notebook resolves it the same way."""
    p = RESULTS_DIR / "water.json"
    if p.exists():
        return p.read_text()
    r = subprocess.run(["git", "show", f"{WATER_REF}:results/water.json"], cwd=REPO_ROOT,
                       capture_output=True, text=True, check=False)
    return r.stdout if r.returncode == 0 else None


def _water():
    t = _water_text()
    return json.loads(t) if t is not None else None


def _sources():
    src = {p.name: json.loads(p.read_text()) for p in RESULTS_DIR.glob("*.json")
           if p.name != "assumptions.json"}
    if "water.json" not in src and (w := _water()) is not None:
        src["water.json"] = w
    return src


def _resolve(src, ref):
    """(value, unit, evidence) at `file#/pointer`; a pointer into an envelope's value list keeps
    the parent envelope's unit and evidence."""
    f, ptr = ref.split("#")
    if f not in src:
        return None
    node, parent = src[f], None
    for p in ptr.strip("/").split("/"):
        if isinstance(node, dict) and "value" in node and "evidence" in node:
            parent = node
        node = node[int(p)] if isinstance(node, list) else node[p]
    if isinstance(node, dict):
        return node["value"], node["unit"], node["evidence"]
    return node, parent["unit"], parent["evidence"]


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


def _strings(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k
            yield from _strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)
    elif isinstance(x, str):
        yield x


def test_every_number_is_read_from_a_results_file(doc):
    src = _sources()
    n_checked = 0
    for path, e in _envs(doc):
        pid = e["provenance_id"]
        if pid.startswith("derived:"):
            m = re.fullmatch(r"derived:(\w+)\(([^,]+),([^,]+)\)", pid)
            assert m, f"{path}: bad derived provenance {pid}"
            a, b = _resolve(src, m.group(2)), _resolve(src, m.group(3))
            assert a is not None and b is not None, f"{path}: unresolvable {pid}"
            assert e["value"] == pytest.approx(OPS[m.group(1)](a[0], b[0]), rel=1e-12), path
        else:
            assert "#/" in pid, f"{path}: provenance_id is not a file#/pointer: {pid}"
            got = _resolve(src, pid)
            assert got is not None, f"{path}: unresolvable source file in {pid}"
            assert e["value"] == pytest.approx(got[0], rel=1e-12, abs=0), f"{path}: {pid}"
            assert (e["unit"], e["evidence"]) == got[1:], f"{path}: {pid}"
        n_checked += 1
    assert n_checked > 50


def test_water_source_hash_matches_the_resolved_source(doc):
    """Water envelopes must come from the water file the notebook read: its recorded sha256 equals
    the sha256 of the source resolved now (results/water.json, or the T14 ref while it is pending).
    Water envelopes with no resolvable source fail; they never skip."""
    uses_water = any("water.json#" in e["provenance_id"] for _, e in _envs(doc))
    if not uses_water:
        assert "water.json" not in doc["sources"]
        return
    text = _water_text()
    assert text is not None, "water envelopes exist but no water.json source resolves"
    assert doc["sources"]["water.json"]["sha256"] == hashlib.sha256(text.encode()).hexdigest()


def test_register_rows_complete(doc):
    rows = {r["id"]: r for r in doc["register"]}
    assert REGISTER_IDS <= set(rows)
    decisions = (REPO_ROOT / "docs" / "decisions.md").read_text()
    for r in doc["register"]:
        for k in ("assumption", "value_text", "used_in", "reality", "result_text"):
            assert r[k].strip(), (r["id"], k)
        assert r["evidence"] in {"observed", "measured", "forecast", "modeled", "assumed",
                                 "simulated"}
        assert isinstance(r["tested"], bool)
        if r["tested"]:
            assert r["results"], f"{r['id']}: tested, but no result numbers"
        else:
            assert r["decision_ids"] and r["result_text"].startswith("Not"), r["id"]
        for d in r["decision_ids"]:
            assert f"## {d} " in decisions or f"### {d} " in decisions, (r["id"], d)


def test_negative_results_and_weather(doc):
    assert NEGATIVE_IDS <= {n["id"] for n in doc["negative_results"]}
    for n in doc["negative_results"]:
        assert n["values"], n["id"]
    w = doc["weather"]
    assert w["conclusion"].startswith("In this setup even perfect carbon foresight does not beat "
                                      "a fixed ranking")
    assert {"H_vs_S", "H_vs_U", "S_vs_U", "share_flexible_energy_in_coverage"} <= set(w["values"])


def test_not_done_lists_the_cuts_with_decisions(doc):
    items = " | ".join(d["item"] for d in doc["not_done"])
    for need in ("shadow-U", "missingness-blind", "runtime-overrun", "weather", "foundation-model"):
        assert need in items, need
    assert all(d["decision_ids"] for d in doc["not_done"])


def test_no_banned_words(doc):
    bad = [s for s in _strings(doc) if BANNED.search(s)]
    assert bad == []
    nb = json.loads(NOTEBOOK.read_text())
    texts = []
    for c in nb["cells"]:
        texts.append("".join(c["source"]))
        for o in c.get("outputs", []):
            texts.append("".join(o.get("text", "")))
            texts.append("".join(o.get("data", {}).get("text/markdown", "")))
    bad = [t[:80] for t in texts if BANNED.search(t)]
    assert bad == []


def test_notebook_executed_and_ends_with_decisions():
    nb = json.loads(NOTEBOOK.read_text())
    code = [c for c in nb["cells"] if c["cell_type"] == "code"]
    assert code and all(c["execution_count"] for c in code)
    assert not [o for c in code for o in c["outputs"] if o["output_type"] == "error"]
    assert "".join(nb["cells"][-1]["source"]).startswith("## Decisions this supports")
    assert "D-068" in "".join(nb["cells"][-1]["source"])
