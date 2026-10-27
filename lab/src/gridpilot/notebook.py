"""Helpers for the evidence notebooks in ``notebooks/`` (decision log: ``docs/decisions.md``).

The notebooks reproduce the data-profile figures and tables by importing the recon scripts in
``lab/scripts/``. Those scripts write figures to ``docs/data-profile/figures/`` and tables to an
OUT_DIR taken from the command line. :func:`import_recon` redirects both to a scratch directory,
so running a notebook never rewrites the committed profile.

Nothing here prints an absolute path: notebook outputs are committed, and paths are shown
relative to ``$GRIDPILOT_DATA_DIR`` or the repository root (:func:`display_path`).
"""

from __future__ import annotations

import hashlib
import importlib
import sys
from collections.abc import Iterable
from pathlib import Path
from types import ModuleType

import polars as pl

from gridpilot.paths import DATA_DIR, REPO_ROOT

SCRIPTS_DIR = REPO_ROOT / "lab" / "scripts"
FIG_DPI = 100  # every embedded figure is rendered at <= 110 dpi to keep notebooks small


def _ipython():
    try:
        from IPython import get_ipython
    except ImportError:  # plain Python (tests): nothing to configure
        return None
    return get_ipython()


def setup(dpi: int = FIG_DPI) -> None:
    """Inline figures at ``dpi`` and readable Polars tables. Call once at the top of a notebook,
    and again after importing a recon script (they switch matplotlib to Agg at import)."""
    import matplotlib.pyplot as plt

    ip = _ipython()
    if ip is not None:
        ip.run_line_magic("matplotlib", "inline")
    plt.rcParams.update({"figure.dpi": dpi, "savefig.dpi": dpi})
    pl.Config.set_tbl_rows(60)
    pl.Config.set_tbl_cols(30)
    pl.Config.set_fmt_str_lengths(80)
    pl.Config.set_tbl_hide_dataframe_shape(True)
    pl.Config.set_tbl_hide_column_data_types(True)


def _quiet(*_args, **_kwargs) -> None:
    """Replaces ``print`` inside recon modules: they print absolute output paths."""


def import_recon(name: str, scratch: Path, dpi: int = FIG_DPI) -> ModuleType:
    """Import ``lab/scripts/<name>.py`` with its figure and table outputs sent to ``scratch``.

    ``recon_grid`` reads its OUT_DIR from ``sys.argv[1]`` at import time, so argv is set to the
    scratch directory for the import. After the import, ``FIG_DIR`` and ``OUT_DIR`` point at
    ``scratch``, the module's own ``style()`` (if any) is applied, its prints are silenced, and the
    figure resolution is capped at ``dpi``.
    """
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    argv = sys.argv
    sys.argv = [f"{name}.py", str(scratch)]
    try:
        module = importlib.import_module(name)
    finally:
        sys.argv = argv
    for attr in ("FIG_DIR", "OUT_DIR"):
        if hasattr(module, attr):
            setattr(module, attr, scratch)
    module.print = _quiet
    if callable(getattr(module, "style", None)):
        module.style()
    setup(dpi)
    return module


def show(path: Path) -> None:
    """Display a PNG written by a recon function."""
    from IPython.display import Image, display

    display(Image(filename=str(path)))


def display_path(path: Path) -> str:
    """A path for printing: relative to ``$GRIDPILOT_DATA_DIR`` or the repo, never absolute."""
    path = Path(path).resolve()
    for root, label in ((DATA_DIR.resolve(), "$GRIDPILOT_DATA_DIR"), (REPO_ROOT.resolve(), ".")):
        if path.is_relative_to(root):
            return f"{label}/{path.relative_to(root).as_posix()}"
    return path.name


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def file_inventory(paths: Iterable[Path]) -> pl.DataFrame:
    """One row per input file: display path, bytes and sha256, sorted by path."""
    rows = [{"file": display_path(p), "bytes": Path(p).stat().st_size, "sha256": sha256_file(p)}
            for p in paths]
    return pl.DataFrame(rows, schema={"file": pl.Utf8, "bytes": pl.Int64,
                                      "sha256": pl.Utf8}).sort("file")


def inventory_digest(inventory: pl.DataFrame) -> str:
    """One sha256 over a file inventory, so a notebook can pin and re-check its inputs."""
    lines = "".join(f"{r['file']}\t{r['bytes']}\t{r['sha256']}\n"
                    for r in inventory.sort("file").iter_rows(named=True))
    return hashlib.sha256(lines.encode()).hexdigest()
