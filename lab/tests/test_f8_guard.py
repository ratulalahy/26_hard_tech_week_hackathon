"""Stage 3 T11 B3 and fix round 1 (I6, M4, M5), spec F8: a static guard on every grid read in
lab/src, lab/scripts and the evidence notebooks.

A **reader** is a call that loads data: polars/pandas `read_parquet`, `scan_parquet`,
`read_excel`, `read_csv`, `scan_csv`, `read_ipc`, `scan_ipc`; pyarrow `read_table`, `dataset`,
`ParquetFile`; openpyxl `load_workbook`; duckdb `sql`/`query`/`execute`/`read_parquet`/
`from_parquet`; `open()` on a data file; and the BA-workbook parser `parse_ba_workbook`. Import
aliases (`from polars import read_parquet as rp`), name aliases (`r = pl.read_parquet`) and
`getattr(pl, "read_parquet")` are resolved.

A reader is a **grid read** when its module parses grid sources, or when its path text matches
the grid pattern. The path text is the call itself plus the assignments (in the function or at
module level) of every name its path uses, plus, when the path is a parameter, the arguments
at the function's call sites in the same module.

Every grid read must be the **direct first argument** of `drop_sealed(...)` (the window filter;
anything else in between, e.g. a `.with_columns(...)` that could rebuild `ts_utc`, does not
count), or sit inside `gridpilot.seal.sealed_read`, or be on the small allowlist below, keyed by
(file, function, reader) with its reason. The guard flags planted leaks, so it can fail.

It also checks that only the test entry point (`scripts/run_slice.py`) calls `test_mode`,
`authorize` or `run_test`, and that nothing outside `gridpilot.seal` touches the session state.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
REPO = LAB.parent
ROOTS = (LAB / "src", LAB / "scripts")
NOTEBOOKS = REPO / "notebooks"
READERS = {"read_parquet", "scan_parquet", "read_excel", "read_csv", "scan_csv", "read_ipc",
           "scan_ipc", "read_table", "dataset", "ParquetFile", "load_workbook",
           "parse_ba_workbook", "from_parquet"}
DUCKDB = {"sql", "query", "execute"}
WRAPPERS = {"drop_sealed"}
GRID_PATTERN = re.compile(
    r"CARBON|BALANCE|WORKBOOK|INTERIM_EIA|eia930|carbon_hourly|balance\.parquet|ba_workbooks|"
    r"truth_fill|PROCESSED_DIR\s*/\s*['\"]carbon|['\"]carbon['\"]|runs/test|TEST_RUNS|"
    r"runs_root|carbon_test")
DATA_EXT = re.compile(r"\.(parquet|xlsx|xls|csv|feather|arrow|ipc)\b|CARBON|BALANCE|WORKBOOK")
# Modules whose readers take a path argument that is always a grid source.
GRID_FILES = {"src/gridpilot/data/eia930.py", "src/gridpilot/data/eia_co2.py",
              "src/gridpilot/data/truth_fill.py", "src/gridpilot/completeness.py"}
# (file, enclosing function, reader) -> reason. Counts-only reads and the raw-source parsers.
ALLOWLIST = {
    ("scripts/recon_grid.py", "main", "read_parquet"):
        "counts only: the test-window completeness table (row counts, missing hours; the "
        "AGENTS.md exception); every value statistic runs on drop_sealed(full)",
    ("scripts/recon_grid.py", "eia_co2_crosscheck", "read_excel"):
        "the cross-check derives ts_utc from 'UTC time' and passes that frame straight to "
        "drop_sealed before any use (it cannot be the reader's direct argument)",
    ("notebooks/01_grid_profile.ipynb", "<module>", "read_parquet"):
        "counts only: §1.2's test-window row counts and missing hours (the AGENTS.md "
        "exception); every value statistic runs on drop_sealed(full)",
    ("src/gridpilot/data/eia_co2.py", "load_carbon", "scan_parquet"):
        "counts only: the number of rows at or after TEST_START, so that such a file is refused "
        "outside test mode (I6); its values are read through drop_sealed",
    ("src/gridpilot/data/eia930.py", "parse_balance_csv", "read_csv"):
        "raw-source parser (raw/ -> interim/ cleaning, nothing summarised); every reader of "
        "balance.parquet is itself checked here",
    ("src/gridpilot/data/eia930.py", "parse_interchange_csv", "read_csv"):
        "raw-source parser (raw/ -> interim/ cleaning, nothing summarised); interchange is not "
        "read by any analysis",
    ("src/gridpilot/completeness.py", "_workbook_presence", "read_excel"):
        "counts only (T12, B4): the time column and whether the consumed-CI cell is empty, "
        "reduced to row/null/complete-day counts and timestamps by test_cutoff; no value is "
        "returned or logged",
    ("src/gridpilot/completeness.py", "_balance_presence", "scan_parquet"):
        "counts only (T12, B4): PACE's ts_utc and the null flag of demand_adj_mw (the value is "
        "never materialized), reduced to counts and timestamps by test_cutoff",
    ("src/gridpilot/data/eia_co2.py", "parse_ba_workbook", "read_excel"):
        "the BA-workbook parser; its calls are checked (build_carbon wraps it in drop_sealed, "
        "the test build passes it to sealed_read as the reader)",
}
SEALED_READ = ("src/gridpilot/seal.py", "sealed_read")
TEST_MODE_CALLERS = {"scripts/run_slice.py"}
ENTRY_NAMES = {"test_mode", "authorize", "run_test"}
SESSION_NAMES = {"_SESSION", "_ISSUED", "_ACTIVE"}


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


def _aliases(tree: ast.AST) -> dict[str, str]:
    """Local names bound to a reader: `from x import read_parquet as rp`, `r = pl.read_parquet`."""
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name in READERS:
                    out[a.asname or a.name] = a.name
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            v = node.value
            name = v.attr if isinstance(v, ast.Attribute) else v.id if isinstance(v, ast.Name) \
                else None
            if name in READERS:
                out[node.targets[0].id] = name
    return out


def _reader(call: ast.Call, aliases: dict[str, str]) -> str | None:
    f = call.func
    if isinstance(f, ast.Attribute):
        if f.attr in READERS:
            return f.attr
        if f.attr in DUCKDB and "duckdb" in ast.unparse(f.value):
            return f"duckdb.{f.attr}"
    if isinstance(f, ast.Name):
        if f.id in READERS:
            return f.id
        if f.id in aliases:
            return aliases[f.id]
        if f.id == "open":
            return "open"
    if isinstance(f, ast.Call) and isinstance(f.func, ast.Name) and f.func.id == "getattr" \
            and len(f.args) >= 2 and isinstance(f.args[1], ast.Constant) \
            and f.args[1].value in READERS:
        return f.args[1].value
    return None


def _assignments(scope: ast.AST, names: set[str]) -> list[str]:
    out = []
    for node in ast.walk(scope):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in names for t in node.targets):
            out.append(ast.unparse(node.value))
        elif isinstance(node, (ast.For, ast.comprehension)) and isinstance(node.target, ast.Name) \
                and node.target.id in names:
            out.append(ast.unparse(node.iter))
    return out


def _path_text(call: ast.Call, fn, tree, reader: str) -> str:
    """The call's text, plus the assignments of the names its path uses (function and module
    level), plus the call-site arguments when the path is a parameter (not for `open`)."""
    text = ast.unparse(call)
    arg = call.args[0] if call.args else None
    if arg is None:
        return text
    names = {n.id for n in ast.walk(arg) if isinstance(n, ast.Name)}
    scopes = [fn] if fn is not None else []
    scopes.append(ast.Module(body=[n for n in tree.body if isinstance(n, ast.Assign)],
                             type_ignores=[]))
    for sc in scopes:
        text += " " + " ".join(_assignments(sc, names))
    if fn is not None and reader != "open":
        params = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
        if names & params:
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                        and node.func.id == fn.name:
                    text += " " + " ".join(ast.unparse(a) for a in node.args)
    return text


def _wrapped(node, parents) -> bool:
    """The reader is the direct first argument of drop_sealed(...)."""
    p = parents.get(node)
    return (isinstance(p, ast.Call) and isinstance(p.func, (ast.Name, ast.Attribute))
            and (p.func.id if isinstance(p.func, ast.Name) else p.func.attr) in WRAPPERS
            and bool(p.args) and p.args[0] is node)


def violations(source: str, rel: str) -> list[tuple[str, str, int, str]]:
    """(file, function, line, call) for every unwrapped, un-allowlisted grid read."""
    tree = ast.parse(source)
    parents = _parents(tree)
    aliases = _aliases(tree)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        reader = _reader(node, aliases)
        if reader is None:
            continue
        fn = _enclosing(node, parents)
        fname = fn.name if fn is not None else "<module>"
        text = _path_text(node, fn, tree, reader)
        if reader == "open":
            first = ast.unparse(node.args[0]) if node.args else ""
            grid = DATA_EXT.search(first) and GRID_PATTERN.search(text)
        else:
            grid = rel in GRID_FILES or GRID_PATTERN.search(text)
        if not grid or _wrapped(node, parents) or (rel, fname) == SEALED_READ:
            continue
        if (rel, fname, reader) in ALLOWLIST:
            continue
        out.append((rel, fname, node.lineno, ast.unparse(node)[:100]))
    return out


def _notebook_source(path: Path) -> str:
    import nbformat

    nb = nbformat.read(path, as_version=4)
    lines = []
    for c in nb.cells:
        if c.cell_type == "code":
            lines += [ln for ln in c.source.splitlines() if not ln.lstrip().startswith(("%", "!"))]
            lines.append("")
    return "\n".join(lines)


def _sources():
    for root in ROOTS:
        for p in sorted(root.rglob("*.py")):
            yield p.relative_to(LAB).as_posix(), p.read_text()
    for p in sorted(NOTEBOOKS.glob("*.ipynb")):
        yield p.relative_to(REPO).as_posix(), _notebook_source(p)


def test_every_grid_read_is_sealed_or_allowlisted():
    bad = [v for rel, src in _sources() for v in violations(src, rel)]
    assert bad == [], "unsealed grid reads (wrap in drop_sealed or sealed_read):\n" + "\n".join(
        f"  {f}:{line} in {fn}: {call}" for f, fn, line, call in bad)


def test_the_notebooks_are_scanned():
    names = [rel for rel, _ in _sources() if rel.endswith(".ipynb")]
    assert len(names) >= 5 and "notebooks/01_grid_profile.ipynb" in names


def test_the_allowlist_is_small_has_reasons_and_no_stale_entries():
    assert len(ALLOWLIST) <= 9  # T12: +2 counts-only completeness reads (B4)
    assert all(len(r) > 30 for r in ALLOWLIST.values())
    used = set()
    for rel, src in _sources():
        tree = ast.parse(src)
        parents = _parents(tree)
        aliases = _aliases(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and (r := _reader(node, aliases)):
                fn = _enclosing(node, parents)
                used.add((rel, fn.name if fn else "<module>", r))
    assert set(ALLOWLIST) <= used, f"stale allowlist entries: {set(ALLOWLIST) - used}"


PLANTED = {
    "plain": "import polars as pl\nfrom gridpilot.data.eia_co2 import CARBON_PATH\n"
             "def f():\n    return pl.read_parquet(CARBON_PATH)\n",
    "by_name": "import polars as pl\ndef f():\n    p = INTERIM_DIR / 'eia930' / 'balance.parquet'\n"
               "    return pl.scan_parquet(p).collect()\n",
    "alias_import": "from polars import read_parquet as rp\n"
                    "from gridpilot.data.eia_co2 import CARBON_PATH\ndef f():\n"
                    "    return rp(CARBON_PATH)\n",
    "alias_var": "import polars as pl\nfrom gridpilot.data.eia_co2 import CARBON_PATH\ndef f():\n"
                 "    r = pl.read_parquet\n    return r(CARBON_PATH)\n",
    "getattr": "import polars as pl\nfrom gridpilot.data.eia_co2 import CARBON_PATH\ndef f():\n"
               "    return getattr(pl, 'read_parquet')(CARBON_PATH)\n",
    "pandas": "import pandas as pd\nfrom gridpilot.data.eia_co2 import CARBON_PATH\ndef f():\n"
              "    return pd.read_parquet(CARBON_PATH)\n",
    "pyarrow": "import pyarrow.parquet as pq\nfrom gridpilot.data.eia_co2 import CARBON_PATH\n"
               "def f():\n    return pq.read_table(CARBON_PATH)\n",
    "pyarrow_dataset": "import pyarrow.dataset as ds\n"
                       "from gridpilot.data.eia_co2 import CARBON_PATH\ndef f():\n"
                       "    return ds.dataset(CARBON_PATH).to_table()\n",
    "duckdb": "import duckdb\ndef f():\n    return duckdb.sql(\"select * from "
              "'data/processed/carbon/carbon_hourly.parquet'\").pl()\n",
    "open": "from gridpilot.data.eia_co2 import CARBON_PATH\ndef f():\n"
            "    return open(CARBON_PATH,'rb').read()\n",
    "openpyxl": "from openpyxl import load_workbook\n"
                "from gridpilot.data.eia_co2 import WORKBOOK_DIR\ndef f():\n"
                "    return load_workbook(WORKBOOK_DIR/'PACE.xlsx')\n",
    "param_path": "import polars as pl\ndef f(path):\n    return pl.read_parquet(path)\n"
                  "def g():\n    from gridpilot.data.eia_co2 import CARBON_PATH\n"
                  "    return f(CARBON_PATH)\n",
    "module_const_neutral_name": "import polars as pl\nfrom gridpilot.paths import PROCESSED_DIR\n"
                                 "TRUTH = PROCESSED_DIR / 'carbon' / 'x.parquet'\ndef f():\n"
                                 "    return pl.read_parquet(TRUTH)\n",
    "module_const_named": "import polars as pl\nfrom gridpilot.paths import PROCESSED_DIR\n"
                          "T = PROCESSED_DIR / 'carbon' / 'carbon_hourly_test.parquet'\n"
                          "def f():\n    return pl.read_parquet(T)\n",
    "fake_wrap": "import polars as pl\nfrom gridpilot.splits import drop_sealed\n"
                 "from gridpilot.data.eia_co2 import CARBON_PATH\ndef f():\n    x = []\n"
                 "    drop_sealed(pl.DataFrame({'ts_utc':[]}), x.append(pl.read_parquet(CARBON_PATH)))\n"
                 "    return x[0]\n",
    "read_ipc": "import polars as pl\nfrom gridpilot.data.eia_co2 import CARBON_PATH\ndef f():\n"
                "    return pl.read_ipc(CARBON_PATH)\n",
    "wrap_wrong_col": "import polars as pl\nfrom gridpilot.splits import drop_sealed\n"
                      "from gridpilot.data.eia_co2 import CARBON_PATH\ndef f():\n"
                      "    return drop_sealed(pl.read_parquet(CARBON_PATH).with_columns("
                      "ts_utc=pl.lit(None)))\n",
    "test_run_dir": "import polars as pl\ndef f(root):\n"
                    "    return pl.read_parquet(root / 'runs/test' / 'x' / 'ledger_U.parquet')\n",
}
CLEAN = {
    "wrapped": "import polars as pl\nfrom gridpilot.splits import drop_sealed\n"
               "from gridpilot.data.eia_co2 import CARBON_PATH\ndef f():\n"
               "    return drop_sealed(pl.scan_parquet(CARBON_PATH)).collect()\n",
    "not_grid": "import polars as pl\ndef f(run_dir):\n"
                "    return pl.read_parquet(run_dir / 'ledger_U.parquet')\n",
    "hash_only": "def sha(path):\n    with open(path, 'rb') as f:\n        return f.read()\n"
                 "def g():\n    from gridpilot.data.eia_co2 import CARBON_PATH\n"
                 "    return sha(CARBON_PATH)\n",
}


def test_the_guard_flags_every_planted_leak_and_passes_clean_code():
    missed = [k for k, src in PLANTED.items() if not violations(src, "src/gridpilot/planted.py")]
    assert missed == []
    flagged = [k for k, src in CLEAN.items() if violations(src, "src/gridpilot/planted.py")]
    assert flagged == []


def _calls_and_names(src: str) -> tuple[set[str], set[str]]:
    tree = ast.parse(src)
    calls, names = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            n = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
            if n:
                calls.add(n)
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return calls, names


def test_only_the_entry_point_enters_test_mode_and_only_seal_touches_the_session():
    """M5: an AST check over lab/src, lab/scripts and the notebooks."""
    callers, touchers = set(), set()
    for rel, src in _sources():
        if rel == "src/gridpilot/seal.py":
            continue
        calls, names = _calls_and_names(src)
        if calls & ENTRY_NAMES:
            callers.add(rel)
        if names & SESSION_NAMES:
            touchers.add(rel)
    assert callers == TEST_MODE_CALLERS
    assert touchers == set()


def test_the_notebooks_hold_no_test_mode_call():
    for p in NOTEBOOKS.glob("*.ipynb"):
        assert "test_mode(" not in json.dumps(json.loads(p.read_text()))
