"""The evidence trail stays consistent: executed notebooks, their HTML exports and the decision log.

Checks the committed files only (no data access): `make notebooks` regenerates them.
"""

import json
import re

import pytest

from gridpilot.paths import REPO_ROOT

NOTEBOOK_DIR = REPO_ROOT / "notebooks"
EVIDENCE_DIR = REPO_ROOT / "docs" / "evidence"
DECISIONS = REPO_ROOT / "docs" / "decisions.md"
NOTEBOOKS = sorted(NOTEBOOK_DIR.glob("[0-9][0-9]_*.ipynb"))
ABSOLUTE_PATH = re.compile(r"(/home/|/Users/|/tmp/|/root/|/private/var/|[A-Za-z]:\\\\)")
MAX_BYTES = 5 * 1024 * 1024


def decision_ids() -> list[str]:
    # D-001..D-043 are `###` entries under the index; D-044 onward are `##` entries (T17).
    return re.findall(r"^#{2,3} (D-\d{3})\b", DECISIONS.read_text(), flags=re.MULTILINE)


def test_decision_ids_are_unique_and_sequential():
    ids = decision_ids()
    assert len(ids) >= 25
    assert ids == [f"D-{i:03d}" for i in range(1, len(ids) + 1)]


def test_there_are_notebooks():
    assert len(NOTEBOOKS) >= 5


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_is_executed_small_and_free_of_absolute_paths(path):
    assert path.stat().st_size < MAX_BYTES
    nb = json.loads(path.read_text())
    code = [c for c in nb["cells"] if c["cell_type"] == "code"]
    assert code and all(c.get("execution_count") for c in code), "run `make notebooks`"
    for cell in code:
        for out in cell.get("outputs", []):
            assert out.get("output_type") != "error", cell["source"]
            text = json.dumps(out.get("text", "")) + json.dumps(out.get("data", {}).get("text/plain", ""))
            text += json.dumps(out.get("data", {}).get("text/html", ""))
            assert not ABSOLUTE_PATH.search(text), f"absolute path in output of: {cell['source'][:80]}"


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_opens_with_a_question_and_ends_with_its_decisions(path):
    nb = json.loads(path.read_text())
    md = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "markdown"]
    assert "**Question" in md[0]
    assert md[-1].lstrip().startswith("## Decisions this supports")
    cited = set(re.findall(r"D-\d{3}", md[-1]))
    assert cited and cited <= set(decision_ids())


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_has_an_html_export(path):
    assert (EVIDENCE_DIR / f"{path.stem}.html").exists(), "run `make notebooks`"
