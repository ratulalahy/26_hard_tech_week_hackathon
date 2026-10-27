"""Write results/grid-profile.json: the dashboard's validation-year grid context.

    cd lab && uv run python scripts/export_grid_profile.py     # or: make profile

Reads the cached EIA tables through the seal (`drop_sealed`), restricted to
[2024-11-01, 2025-10-24); see `gridpilot.grid_profile` for the contents. The artifact is
validated (every number enveloped, no sealed timestamp) and written atomically.
"""

from __future__ import annotations

from gridpilot.grid_profile import build_profile, load_inputs
from gridpilot.paths import RESULTS_DIR
from gridpilot.results import write_json_atomic


def main() -> None:
    carbon, balance = load_inputs()
    prof = build_profile(carbon, balance)
    out = RESULTS_DIR / "grid-profile.json"
    write_json_atomic(out, prof)
    pace = prof["ci"]["by_ba"]["PACE"]["year_mean"]["value"]
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB); PACE year mean {pace:.1f} g/kWh")


if __name__ == "__main__":
    main()
