"""Write results/case-days.json: "Utah's toughest grid days" (Stage 3 T16, D-066; validation only).

    cd lab && uv run python scripts/export_case_days.py --registered-run <abs runs/slice/<run_id>>

The registered run must be the one named in results/manifest.json. The days come from the
pre-registered D-066 rule (`gridpilot.case_days`); the public context below is looked up per
date after the rule chose it, and is context, never evidence. The manifest gets a `case_days`
pointer (artifact, sha256, canonical_sha256); no other field changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from gridpilot.case_days import from_run
from gridpilot.paths import RESULTS_DIR
from gridpilot.results import canonical_hash, write_json_atomic

SEARCHED = ("EIA Today in Energy, NERC and WECC reports, NWS Salt Lake City products, Rocky "
            "Mountain Power notices and Utah news (KSL, KUTV, KTVX/ABC4, Fox 13), searched "
            "27 Oct 2026")
NONE = {"kind": "none", "sentence": "No public event record found for this date.",
        "searched": SEARCHED}
JULY = {"kind": "month", "title": "The Curious Case of July 2025",
        "publisher": "Wasatch Weather Weenies (Jim Steenburgh, Professor of Atmospheric "
                     "Sciences, University of Utah)",
        "published": "1 August 2025",
        "url": "https://wasatchweatherweenies.blogspot.com/2025/08/the-curious-case-of-july-2025.html",
        "sentence": ("July 2025 was the 12th-warmest July on record at Salt Lake City airport "
                     "(mean 82.9 °F), with no record highs and three days at 100 °F."),
        "scope": "the whole month, not this date"}
SOURCES = {
    "2025-07-08": [NONE, JULY],
    "2025-07-16": [NONE, JULY, {
        "kind": "adjacent", "title": "Dangerous heat early this week, with an elevated fire "
                                     "threat returning to Utah",
        "publisher": "KTVX ABC4 Utah (via Yahoo News), Alana Brophy",
        "published": "14 July 2025",
        "url": "https://www.yahoo.com/news/dangerous-heat-early-week-elevated-233638717.html",
        "sentence": ("A forecast issued on Monday 14 July called for highs around 100 °F along "
                     "the Wasatch Front on Tuesday 15 July, the day before this date."),
        "scope": "a forecast for the day before; not this date"}],
    "2025-09-02": [NONE],
}


def patch_manifest(path: Path, art: dict, text: str) -> None:
    man = json.loads(path.read_text())
    man["case_days"] = {"artifact": "case-days.json", "kind": art["kind"],
                        "sha256": hashlib.sha256(text.encode()).hexdigest(),
                        "canonical_sha256": canonical_hash(art)}
    write_json_atomic(path, man)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registered-run", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=RESULTS_DIR / "case-days.json")
    a = ap.parse_args()
    man = json.loads((a.out.parent / "manifest.json").read_text())
    if a.registered_run.name != man["run_id"]:
        raise SystemExit(f"{a.registered_run} is not the registered run {man['run_id']}")
    art = from_run(a.registered_run, SOURCES)
    chosen = [d["date"] for d in art["days"]]
    if sorted(chosen) != sorted(SOURCES):
        raise SystemExit(f"the rule chose {chosen}; the context table covers {sorted(SOURCES)} "
                         "(look up context for the chosen days; never change the days)")
    text = write_json_atomic(a.out, art)
    patch_manifest(a.out.parent / "manifest.json", art, text)
    for d in art["days"]:
        p = d["policies"]
        print(f"#{d['rank']['value']} {d['date']} peak {d['peak']['net_load_mw']['value']:.0f} MW "
              f"at {d['peak']['local_label']}; SLC max "
              f"{d['weather']['PACE_SLC']['tmax_f']['value']:.1f} F; CO2 t U "
              f"{p['U']['co2_t']['value']:.2f} S {p['S']['co2_t']['value']:.2f} W "
              f"{p['W']['co2_t']['value']:.2f}; Utah at peak U "
              f"{p['U']['utah_cluster_at_peak_mw']['value']:.3f} S "
              f"{p['S']['utah_cluster_at_peak_mw']['value']:.3f} W "
              f"{p['W']['utah_cluster_at_peak_mw']['value']:.3f} MW")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
