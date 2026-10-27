from gridpilot import notebook as nb
from gridpilot.paths import DATA_DIR, REPO_ROOT


def test_import_recon_redirects_outputs_and_silences_prints(tmp_path):
    rg = nb.import_recon("recon_grid", tmp_path / "scratch")
    assert rg.FIG_DIR == tmp_path / "scratch"
    assert rg.OUT_DIR == tmp_path / "scratch"
    assert rg.FIG_DIR != REPO_ROOT / "docs" / "data-profile" / "figures" / "grid"
    assert rg.print("would print an absolute path") is None
    import matplotlib.pyplot as plt

    assert plt.rcParams["savefig.dpi"] <= 110


def test_display_path_never_shows_an_absolute_path(tmp_path):
    assert nb.display_path(DATA_DIR / "raw" / "x.json") == "$GRIDPILOT_DATA_DIR/raw/x.json"
    assert nb.display_path(REPO_ROOT / "docs" / "brief.md") == "./docs/brief.md"
    assert nb.display_path(tmp_path / "elsewhere.csv") == "elsewhere.csv"


def test_inventory_digest_is_stable_and_detects_changes(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("one")
    b.write_text("two")
    inv = nb.file_inventory([b, a])
    assert inv["file"].to_list() == ["a.txt", "b.txt"]
    digest = nb.inventory_digest(inv)
    assert digest == nb.inventory_digest(nb.file_inventory([a, b]))
    b.write_text("changed")
    assert digest != nb.inventory_digest(nb.file_inventory([a, b]))
