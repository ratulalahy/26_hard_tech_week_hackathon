"""Stage 3 T11 B3, spec F8: a static guard on every grid read in lab/src and lab/scripts.

A grid read is a `read_parquet`, `scan_parquet`, `read_excel`, `read_csv` (or the BA-workbook
parser `parse_ba_workbook`) call on a grid path: the EIA carbon tables and workbooks, the
EIA-930 balance table, the scoring truth fill. Each must sit inside a `drop_sealed(...)` call
(the window filter), or inside `gridpilot.seal.sealed_read`, or be on the small allowlist
below, with its reason. The guard also checks that only the test entry point enters the
test-mode context, and that it flags a planted unwrapped read (it can fail)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
ROOTS = (LAB / "src", LAB / "scripts")
READERS = {"read_parquet", "scan_parquet", "read_excel", "read_csv", "scan_csv",
           "parse_ba_workbook"}
WRAPPERS = {"drop_sealed"}
# Text that marks a read's path as a grid path (the call, or the assignment of its path name).
GRID_PATTERN = re.compile(r"CARBON|BALANCE|WORKBOOK|INTERIM_EIA|eia930|carbon_hourly|"
                          r"balance\.parquet|ba_workbooks|truth_fill")
# Modules whose readers take a path argument that is always a grid source.
GRID_FILES = {"src/gridpilot/data/eia930.py", "src/gridpilot/data/eia_co2.py",
              "src/gridpilot/data/truth_fill.py"}
# (file, enclosing function) -> reason. Keep it small: files read for counts only, and the
# raw-source parsers whose every caller is itself checked.
ALLOWLIST = {
    ("scripts/recon_grid.py", "main"):
        "counts only: the test-window completeness table (row counts, missing hours; the "
        "AGENTS.md exception); every value statistic runs on drop_sealed(full)",
    ("src/gridpilot/data/eia930.py", "parse_balance_csv"):
        "raw-source parser (raw/ -> interim/ cleaning, nothing summarised); every reader of "
        "balance.parquet is itself checked here",
    ("src/gridpilot/data/eia930.py", "parse_interchange_csv"):
        "raw-source parser (raw/ -> interim/ cleaning, nothing summarised); interchange is not "
        "read by any analysis",
    ("src/gridpilot/data/eia_co2.py", "parse_ba_workbook"):
        "the BA-workbook parser; its calls are checked (build_carbon wraps it in drop_sealed, "
        "the test build passes it to sealed_read as the reader)",
}
SEALED_READ = ("src/gridpilot/seal.py", "sealed_read")
TEST_MODE_CALLERS = {"scripts/run_slice.py"}


def _name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    out = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            out[child] = node
    return out


def _enclosing(node, parents):
    p = parents.get(node)
    while p is not None and not isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef)):
        p = parents.get(p)
    return p


def _wrapped(node, parents) -> bool:
    p = parents.get(node)
    while p is not None and not isinstance(p, ast.stmt):
        if isinstance(p, ast.Call) and _name(p.func) in WRAPPERS:
            return True
        p = parents.get(p)
    return False


def _path_text(call: ast.Call, fn: ast.AST | None) -> str:
    """The call's text plus the assignments of any name its first argument uses."""
    text = ast.unparse(call)
    if call.args and fn is not None:
        names = {n.id for n in ast.walk(call.args[0]) if isinstance(n, ast.Name)}
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id in names for t in node.targets):
                text += " " + ast.unparse(node.value)
            elif isinstance(node, ast.For) and isinstance(node.target, ast.Name) \
                    and node.target.id in names:
                text += " " + ast.unparse(node.iter)
    return text


def violations(source: str, rel: str) -> list[tuple[str, str, int, str]]:
    """(file, function, line, call) for every unwrapped, un-allowlisted grid read."""
    tree = ast.parse(source)
    parents = _parents(tree)
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _name(node.func) in READERS):
            continue
        fn = _enclosing(node, parents)
        fname = fn.name if fn is not None else "<module>"
        grid = rel in GRID_FILES or GRID_PATTERN.search(_path_text(node, fn))
        if not grid or _wrapped(node, parents) or (rel, fname) == SEALED_READ:
            continue
        if (rel, fname) in ALLOWLIST:
            continue
        out.append((rel, fname, node.lineno, ast.unparse(node)[:100]))
    return out


def _sources():
    for root in ROOTS:
        for p in sorted(root.rglob("*.py")):
            yield p.relative_to(LAB).as_posix(), p.read_text()


def test_every_grid_read_is_sealed_or_allowlisted():
    bad = [v for rel, src in _sources() for v in violations(src, rel)]
    assert bad == [], "unsealed grid reads (wrap in drop_sealed or sealed_read):\n" + "\n".join(
        f"  {f}:{line} in {fn}: {call}" for f, fn, line, call in bad)


def test_the_allowlist_is_small_has_reasons_and_no_stale_entries():
    assert len(ALLOWLIST) <= 5
    assert all(len(r) > 30 for r in ALLOWLIST.values())
    used = set()
    for rel, src in _sources():
        tree = ast.parse(src)
        parents = _parents(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _name(node.func) in READERS:
                fn = _enclosing(node, parents)
                used.add((rel, fn.name if fn else "<module>"))
    assert set(ALLOWLIST) <= used, f"stale allowlist entries: {set(ALLOWLIST) - used}"


def test_the_guard_flags_a_planted_unwrapped_grid_read():
    planted = (
        "import polars as pl\n"
        "from gridpilot.data.eia_co2 import CARBON_PATH\n"
        "from gridpilot.splits import drop_sealed\n"
        "def leak():\n"
        "    return pl.read_parquet(CARBON_PATH)\n"
        "def leak_by_name():\n"
        "    p = INTERIM_DIR / 'eia930' / 'balance.parquet'\n"
        "    return pl.scan_parquet(p).collect()\n"
        "def fine():\n"
        "    return drop_sealed(pl.scan_parquet(CARBON_PATH)).collect()\n"
        "def not_grid(run_dir):\n"
        "    return pl.read_parquet(run_dir / 'ledger_U.parquet')\n")
    got = {fn for _, fn, _, _ in violations(planted, "src/gridpilot/planted.py")}
    assert got == {"leak", "leak_by_name"}


def test_only_the_entry_point_enters_test_mode():
    pat = re.compile(r"\b(test_mode|authorize)\(")
    callers = {rel for rel, src in _sources() if rel != "src/gridpilot/seal.py"
               and any(pat.search(line) and not line.lstrip().startswith(("#", "def "))
                       for line in src.splitlines())}
    assert callers == TEST_MODE_CALLERS
