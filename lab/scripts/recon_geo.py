"""Build the offline map assets: BA boundaries, BA points, Natural Earth basemap, relief.

Run from lab/ in isolated mode (it reads downloaded files):

    uv run python -I scripts/recon_geo.py             # download (if needed) + build everything
    uv run python -I scripts/recon_geo.py download    # downloads + manifests only

Downloads are idempotent: a file already on disk whose sha256 matches its manifest record is
reused. Outputs go to data/processed/geo/ (written atomically); manifests to
data/manifests/geo_ba_boundaries.json and data/manifests/geo_natural_earth.json.
"""

from __future__ import annotations

import argparse
import json
import sys

from gridpilot.data import geo
from gridpilot.paths import MANIFEST_DIR

REJECTED_BA_SOURCES = [
    {
        "name": "HIFLD Open 'Control Areas' (public domain)",
        "url": "https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Control_Areas/FeatureServer/0",
        "status": "retired: the HIFLD Open services answer 'Invalid URL' (checked 2026-10-27); "
                  "ORNL Open Energy Hub's 'control-areas' entry is a tombstone dated 2026-03-16",
    },
    {
        "name": "EIA U.S. Energy Atlas 'Balancing_Authorities' feature service",
        "url": "https://services7.arcgis.com/FGr1D95XCGALKXqM/arcgis/rest/services/Balancing_Authorities/FeatureServer",
        "status": "not public: 'Token Required' (checked 2026-10-27); none of EIA's 79 public "
                  "ArcGIS feature services carries BA or control-area polygons",
    },
    {
        "name": "NASA NCCS mirror of HIFLD Open (hifld_open/energy/FeatureServer/23)",
        "url": "https://maps.nccs.nasa.gov/mapping/rest/services/hifld_open/energy/FeatureServer/23",
        "status": "unreachable from this machine (connection refused)",
    },
    {
        "name": "Third-party ArcGIS Online copies of HIFLD/EIA BA layers",
        "url": "https://services5.arcgis.com/bsqU0jSPAuI04L89/arcgis/rest/services/Balancing_Authorities/FeatureServer",
        "status": "reachable but personal re-uploads with no license or provenance metadata; "
                  "HIFLD-style control areas also overlap each other",
    },
    {
        "name": "EIA Hourly Electric Grid Monitor bundle",
        "url": "https://www.eia.gov/electricity/gridmonitor/",
        "status": "embeds only the 13 EIA regions and state outlines, no BA polygons",
    },
]


def eia930_input_record() -> dict:
    """The EIA-930 reference table is downloaded by the EIA-930 recon; cite its record."""
    rel = geo.data_relpath(geo.EIA930_REF_PATH)
    eia = json.loads((MANIFEST_DIR / "eia930.json").read_text())
    rec = next((f for f in eia.get("files", []) if f.get("file", "").endswith("EIA930_Reference_Tables.xlsx")), {})
    digest = geo.sha256_file(geo.EIA930_REF_PATH)
    return {
        "file": "EIA930_Reference_Tables.xlsx",
        "path": rel,
        "url": rec.get("url", geo.EIA930_REF_URL),
        "retrieved_at": rec.get("retrieved_at"),
        "bytes": geo.EIA930_REF_PATH.stat().st_size,
        "sha256": digest,
        "license": rec.get("license", geo.EIA_LICENSE),
        "recorded_in": "eia930.json",
        "sha256_matches_eia930_manifest": rec.get("sha256") == digest,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", nargs="?", default="all", choices=["download", "all"])
    args = ap.parse_args(argv)

    ba_dl, ne_dl = geo.download_sources()
    ba_manifest = {
        "source": "Electricity Maps zone geometries (electricitymaps-contrib geo/world.geojson), "
                  "mapped to EIA-930 BA codes and fitted to Natural Earth 1:10m lower-48 land",
        "base_url": f"https://github.com/{geo.EM_REPO}/tree/{geo.EM_COMMIT}/geo",
        "license": geo.EM_LICENSE,
        "attribution": f"{geo.EM_ATTRIBUTION} {geo.EIA_ATTRIBUTION} {geo.NE_ATTRIBUTION}",
        "files": ba_dl["files"],
        "inputs": [eia930_input_record()],
        "rejected_sources": REJECTED_BA_SOURCES,
    }
    ne_manifest = {
        "source": "Natural Earth 1:10m and 1:50m vectors, 1:50m shaded relief",
        "base_url": geo.NE_BASE_URL,
        "license": geo.NE_LICENSE,
        "attribution": geo.NE_ATTRIBUTION,
        "files": ne_dl["files"],
    }
    if args.step == "download":
        geo.write_manifest(geo.BA_MANIFEST, ba_manifest)
        geo.write_manifest(geo.NE_MANIFEST, ne_manifest)
        for rec in ba_dl["files"] + ne_dl["files"]:
            print(f"{rec['bytes']:>12,}  {rec['sha256'][:12]}  {rec['path']}")
        return 0

    built_at = geo.utc_now()
    command = "cd lab && uv run python -I scripts/recon_geo.py"

    layers = geo.build_ba_layers()
    ba_paths = geo.write_ba_layers(layers)
    ba_manifest["outputs"] = [
        geo.output_record(ba_paths["boundaries"], features=len(layers.web),
                          vertices=layers.checks["simplified_web"]["vertices"]),
        geo.output_record(ba_paths["points"], features=len(layers.points)),
    ]
    ba_manifest["build"] = {
        "command": command,
        "built_at": built_at,
        "electricitymaps_commit": geo.EM_COMMIT,
        "steps": [
            ("keep Electricity Maps zones 'US-*' whose last key part is an EIA-930 BA code "
             "(drops US-AK, US-AK-SEAPA, US-HI)"),
            ("clip each zone to Natural Earth 1:10m admin-0 USA (large lakes cut out), "
             f"window {list(geo.CONUS_MASK_WINDOW)}"),
            ("give every uncovered land sliver to the nearest zone (ordered Voronoi of zone "
             "boundaries densified to 0.02 deg), then shapely.coverage_clean"),
            (f"shapely.coverage_simplify tolerance {geo.BA_SIMPLIFY_DEG} deg; round to "
             f"{geo.BA_DECIMALS} decimals"),
            "SWPW (SPP West, active 2026-04-01) = coverage union of WACM + WAUW (approximate)",
        ],
        "checks": layers.checks,
        "unmapped_electricitymaps_zones": layers.unmapped_em_zones,
    }
    ba_manifest["mapping"] = [
        {k: r[k] for k in ["code", "em_zone", "geometry_source", "approximate", "active", "area_km2"]}
        for _, r in layers.web.iterrows()
    ]
    ba_manifest["points"] = [
        {k: (None if (isinstance(r[k], float) and r[k] != r[k]) else r[k])
         for k in ["code", "method", "city", "snap_km"]}
        for _, r in layers.points.iterrows()
    ]
    ba_manifest["missing_eia930_codes"] = layers.missing
    geo.write_manifest(geo.BA_MANIFEST, json.loads(json.dumps(ba_manifest, default=_jsonable)))

    basemap = geo.build_basemap()
    relief = geo.build_relief()
    ne_manifest["outputs"] = basemap + [relief["png"], relief["json"]]
    ne_manifest["build"] = {
        "command": command,
        "built_at": built_at,
        "basemap_bbox": list(geo.BASEMAP_BBOX),
        "context_bbox": list(geo.CONTEXT_BBOX),
        "simplify": f"shapely.simplify(preserve_topology=True) {geo.BASEMAP_SIMPLIFY_DEG} deg "
                    "(land_context 0.02 deg); coordinates rounded to 4 decimals (land_context 3)",
    }
    geo.write_manifest(geo.NE_MANIFEST, json.loads(json.dumps(ne_manifest, default=_jsonable)))

    total = 0
    for rec in ba_manifest["outputs"] + ne_manifest["outputs"]:
        total += rec["bytes"]
        print(f"{rec['bytes']:>10,}  {rec['path']}")
    print(f"{total:>10,}  total")
    print("missing EIA-930 codes:", ", ".join(m["code"] for m in layers.missing))
    for name, chk in layers.checks.items():
        print(f"{name:34s} coverage_valid={chk['coverage_valid']} overlap_km2={chk['overlap_km2']} "
              f"vertices={chk['vertices']}")
    return 0


def _jsonable(o):
    if hasattr(o, "item"):
        return o.item()
    return str(o)


if __name__ == "__main__":
    sys.exit(main())
