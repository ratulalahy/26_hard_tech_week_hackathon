"""Map assets for the offline dashboard: BA boundaries, BA points and a Natural Earth basemap.

Sources (the license of every download is recorded in ``data/manifests/geo_*.json``):

- BA polygons: Electricity Maps zone geometries (``geo/world.geojson`` in
  github.com/electricitymaps/electricitymaps-contrib), pinned to one commit. AGPL-3.0.
- EIA-930 BA code list: EIA-930 reference tables (U.S. EIA, public domain), read from the
  copy the EIA-930 recon already downloaded (``data/raw/eia930/``, manifest ``eia930.json``).
- Basemap vectors and shaded relief: Natural Earth 1:10m / 1:50m (public domain).

Everything is written as plain GeoJSON in EPSG:4326 so the dashboard can load it from
disk with no tile server, glyph server or network access.

Evidence labels (AGENTS.md): polygons and basemap geometry are ``observed`` (published
reference geometry, simplified for display; BA boundaries are approximate by nature).
Representative points are ``modeled`` (computed from published data by a stated rule).
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import geopandas as gpd
import httpx
import numpy as np
import pandas as pd
import pyogrio
import shapely
import shapely.ops

from gridpilot.paths import DATA_DIR, MANIFEST_DIR, PROCESSED_DIR, RAW_DIR

# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

GEO_RAW_DIR = RAW_DIR / "geo"
GEO_DIR = PROCESSED_DIR / "geo"
BASEMAP_DIR = GEO_DIR / "basemap"

#: Lower-48 extent (lon_min, lat_min, lon_max, lat_max).
CONUS_BBOX = (-124.8, 24.4, -66.9, 49.4)
#: CONUS plus a margin: what the camera can see at zoom 3-7 with some pitch.
BASEMAP_BBOX = (-140.0, 14.0, -50.0, 62.0)
#: Wider frame for the coarse 1:50m land, so a pitched camera never sees a hard edge.
CONTEXT_BBOX = (-180.0, 0.0, -20.0, 84.0)

USER_AGENT = "gridpilot-hackathon-recon/0.1 (offline map assets)"

# ---------------------------------------------------------------------------
# Source definitions and licenses
# ---------------------------------------------------------------------------

EM_REPO = "electricitymaps/electricitymaps-contrib"
EM_COMMIT = "501e61d61c5f460ae4d811db3169ec47d34c7aac"  # master on 2026-10-26
EM_WORLD_URL = f"https://raw.githubusercontent.com/{EM_REPO}/{EM_COMMIT}/geo/world.geojson"
EM_LICENSE_URL = f"https://raw.githubusercontent.com/{EM_REPO}/{EM_COMMIT}/LICENSE.md"
EM_LICENSE = (
    "AGPL-3.0 (GNU Affero General Public License v3.0; electricitymaps-contrib repository "
    "license since v1.5.0, contributions before commit cb9664f were MIT). Copyleft: "
    "redistribution and derived geometry must stay under AGPL-3.0 with attribution."
)
EM_ATTRIBUTION = (
    "BA boundaries: Electricity Maps contributors, electricitymaps-contrib zone geometries "
    f"(commit {EM_COMMIT[:7]}), AGPL-3.0, simplified."
)

EIA930_REF_URL = "https://www.eia.gov/electricity/930-content/EIA930_Reference_Tables.xlsx"
#: Downloaded by the EIA-930 recon (never duplicated here); see data/manifests/eia930.json.
EIA930_REF_PATH = RAW_DIR / "eia930" / "EIA930_Reference_Tables.xlsx"
EIA_LICENSE = (
    "Public domain (U.S. government work). EIA asks for the acknowledgment "
    "'Source: U.S. Energy Information Administration'."
)
EIA_ATTRIBUTION = "BA codes and names: U.S. Energy Information Administration, Form EIA-930."

NE_BASE_URL = "https://naciscdn.org/naturalearth"
NE_LICENSE = (
    "Public domain. Natural Earth terms of use: 'All versions of Natural Earth raster + "
    "vector map data found on this website are in the public domain. You may use the maps "
    "in any manner ... No permission is needed to use Natural Earth. Crediting the authors "
    "is unnecessary.' https://www.naturalearthdata.com/about/terms-of-use/"
)
NE_ATTRIBUTION = "Made with Natural Earth. Free vector and raster map data @ naturalearthdata.com."

# ---------------------------------------------------------------------------
# Downloads and manifests
# ---------------------------------------------------------------------------


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def data_relpath(path: Path) -> str:
    """Path relative to the data directory, as stored in manifests."""
    try:
        return str(Path(path).resolve().relative_to(DATA_DIR.resolve()))
    except ValueError:
        return str(path)


def load_manifest(name: str) -> dict:
    path = MANIFEST_DIR / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def write_manifest(name: str, manifest: dict) -> Path:
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    path = MANIFEST_DIR / f"{name}.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return path


def fetch(
    url: str,
    dest: Path,
    *,
    license: str,
    prior: Iterable[dict] = (),
    extra: dict | None = None,
) -> dict:
    """Download ``url`` to ``dest`` once and return its manifest record.

    Raw data is immutable: an existing file whose sha256 matches a prior manifest record
    is reused with that record's ``retrieved_at``. A file is never overwritten in place;
    delete it explicitly to re-download.
    """
    dest = Path(dest)
    rel = data_relpath(dest)
    known = {r["path"]: r for r in prior if "path" in r}
    if dest.exists():
        digest = sha256_file(dest)
        rec = known.get(rel)
        if rec and rec.get("sha256") == digest:
            return rec
        # Present but unrecorded (e.g. manifest deleted): record it without re-downloading.
        rec = {
            "url": url,
            "path": rel,
            "retrieved_at": datetime.fromtimestamp(dest.stat().st_mtime, UTC).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "bytes": dest.stat().st_size,
            "sha256": digest,
            "license": license,
        }
        return {**rec, **(extra or {})}

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    timeout = httpx.Timeout(60.0, read=300.0)
    with httpx.stream(
        "GET", url, follow_redirects=True, timeout=timeout, headers={"User-Agent": USER_AGENT}
    ) as resp:
        resp.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in resp.iter_bytes(1 << 20):
                f.write(chunk)
    retrieved_at = utc_now()
    tmp.replace(dest)
    dest.chmod(0o444)
    return {
        "url": url,
        "path": rel,
        "retrieved_at": retrieved_at,
        "bytes": dest.stat().st_size,
        "sha256": sha256_file(dest),
        "license": license,
        **(extra or {}),
    }


def output_record(path: Path, **extra) -> dict:
    return {
        "path": data_relpath(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        **extra,
    }


# ---------------------------------------------------------------------------
# EIA-930 reference table (BA list)
# ---------------------------------------------------------------------------

_XLSX_NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def _col_index(cell_ref: str) -> int:
    letters = re.match(r"[A-Z]+", cell_ref).group(0)
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - 64)
    return idx - 1


def read_xlsx_sheet(path: Path, sheet: str | None = None) -> list[list[str]]:
    """Minimal stdlib .xlsx reader: one sheet as rows of strings (no formulas, no styles)."""
    m = _XLSX_NS["m"]
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {r.get("Id"): r.get("Target") for r in rels}
        sheets = {
            s.get("name"): targets[s.get(f"{{{_XLSX_NS['r']}}}id")]
            for s in wb.find("m:sheets", _XLSX_NS)
        }
        name = sheet if sheet is not None else next(iter(sheets))
        target = sheets[name].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", _XLSX_NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{m}}}t")))
        rows: list[list[str]] = []
        for row in ET.fromstring(z.read(target)).iter(f"{{{m}}}row"):
            cells: dict[int, str] = {}
            for c in row.findall("m:c", _XLSX_NS):
                kind = c.get("t")
                v = c.find("m:v", _XLSX_NS)
                if kind == "s" and v is not None:
                    val = shared[int(v.text)]
                elif kind == "inlineStr":
                    val = "".join(t.text or "" for t in c.iter(f"{{{m}}}t"))
                else:
                    val = v.text if v is not None and v.text is not None else ""
                cells[_col_index(c.get("r"))] = val.strip()
            rows.append([cells.get(i, "") for i in range(max(cells) + 1)] if cells else [])
    return rows


def xlsx_sheet_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        return [s.get("name") for s in wb.find("m:sheets", _XLSX_NS)]


def read_eia930_bas(path: Path) -> pd.DataFrame:
    """The 'BAs' sheet of EIA930_Reference_Tables.xlsx as a DataFrame keyed by BA code."""
    names = xlsx_sheet_names(path)
    sheet = next((n for n in names if n.strip().lower() in {"bas", "ba", "balancing authorities"}), None)
    rows = read_xlsx_sheet(path, sheet or names[0])
    header_i = next(i for i, r in enumerate(rows) if any(c.strip().lower() == "ba code" for c in r))
    header = [c.strip() for c in rows[header_i]]
    body = [r + [""] * (len(header) - len(r)) for r in rows[header_i + 1 :] if r and r[0].strip()]
    df = pd.DataFrame([r[: len(header)] for r in body], columns=header)
    df = df.rename(columns={c: _snake(c) for c in df.columns})
    return df


def _snake(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.strip().lower()).strip("_")


def _yes(v: object) -> bool:
    return str(v).strip().lower() in {"yes", "y", "true", "1"}


# ---------------------------------------------------------------------------
# GeoJSON writing
# ---------------------------------------------------------------------------


def round_geometry(geoms, decimals: int):
    """Round coordinates (vectorised) and drop the repeated points rounding creates."""
    out = shapely.transform(geoms, lambda xy: np.round(xy, decimals))
    return shapely.remove_repeated_points(out)


def _clean_props(props: dict) -> dict:
    out = {}
    for k, v in props.items():
        if v is None:
            out[k] = None
        elif isinstance(v, (np.integer,)):
            out[k] = int(v)
        elif isinstance(v, (np.floating, float)):
            out[k] = None if math.isnan(float(v)) else round(float(v), 6)
        elif isinstance(v, (np.bool_, bool)):
            out[k] = bool(v)
        elif isinstance(v, (pd.Timestamp, datetime)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def write_geojson(
    gdf: gpd.GeoDataFrame,
    path: Path,
    *,
    decimals: int,
    properties: list[str] | None = None,
    id_field: str | None = None,
    meta: dict | None = None,
) -> Path:
    """Write a compact GeoJSON FeatureCollection in EPSG:4326 with rounded coordinates."""
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()]
    geoms = round_geometry(gdf.geometry.values, decimals)
    cols = properties if properties is not None else [c for c in gdf.columns if c != "geometry"]
    feats = []
    records = gdf[cols].to_dict("records") if cols else [{}] * len(gdf)
    for geom, props in zip(geoms, records):
        if geom is None or shapely.is_empty(geom):
            continue
        feat = {"type": "Feature"}
        if id_field is not None:
            feat["id"] = props[id_field]
        feat["properties"] = _clean_props(props)
        feat["geometry"] = json.loads(shapely.to_geojson(geom))
        feats.append(feat)
    fc = {"type": "FeatureCollection"}
    if meta:
        fc["metadata"] = meta
    fc["features"] = feats
    write_atomic(path, json.dumps(fc, separators=(",", ":"), ensure_ascii=False).encode())
    return path


def write_atomic(path: Path, data: bytes) -> None:
    """Write to a temp file in the same directory, then rename (AGENTS.md data rules)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


# ---------------------------------------------------------------------------
# What to download
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NESource:
    """One Natural Earth zip from the official CDN (naciscdn.org)."""

    scale: str  # "10m" | "50m"
    theme: str  # "physical" | "cultural" | "raster"
    name: str  # e.g. "ne_10m_land"

    @property
    def url(self) -> str:
        return f"{NE_BASE_URL}/{self.scale}/{self.theme}/{self.name}.zip"

    @property
    def path(self) -> Path:
        # Each download gets its own directory (downloads are untrusted data).
        return GEO_RAW_DIR / "natural_earth" / self.name / f"{self.name}.zip"

    def vsi(self, member: str | None = None) -> str:
        """GDAL virtual path to a shapefile inside the zip (read without extracting)."""
        return f"/vsizip/{self.path}/{member or self.name + '.shp'}"


NE_SOURCES: dict[str, NESource] = {
    s.name: s
    for s in [
        NESource("10m", "physical", "ne_10m_land"),
        NESource("10m", "physical", "ne_10m_coastline"),
        NESource("10m", "physical", "ne_10m_lakes"),
        NESource("10m", "physical", "ne_10m_rivers_lake_centerlines"),
        NESource("10m", "cultural", "ne_10m_urban_areas"),
        NESource("10m", "cultural", "ne_10m_populated_places"),
        NESource("10m", "cultural", "ne_10m_roads"),
        NESource("10m", "cultural", "ne_10m_admin_1_states_provinces_lakes"),
        NESource("10m", "cultural", "ne_10m_admin_1_states_provinces_lines"),
        NESource("10m", "cultural", "ne_10m_admin_0_countries_lakes"),
        NESource("10m", "cultural", "ne_10m_admin_0_boundary_lines_land"),
        NESource("50m", "physical", "ne_50m_land"),
        NESource("50m", "raster", "SR_50M"),
    ]
}

EM_WORLD_PATH = GEO_RAW_DIR / "electricitymaps" / EM_COMMIT[:12] / "world.geojson"
EM_LICENSE_PATH = GEO_RAW_DIR / "electricitymaps" / EM_COMMIT[:12] / "LICENSE.md"

BA_MANIFEST = "geo_ba_boundaries"
NE_MANIFEST = "geo_natural_earth"


def download_sources() -> tuple[dict, dict]:
    """Fetch every geo source (idempotent) and write the two download manifests."""
    prior_ba = load_manifest(BA_MANIFEST).get("files", [])
    prior_ne = load_manifest(NE_MANIFEST).get("files", [])

    ba_files = [
        fetch(EM_WORLD_URL, EM_WORLD_PATH, license=EM_LICENSE, prior=prior_ba,
              extra={"file": "world.geojson", "commit": EM_COMMIT}),
        fetch(EM_LICENSE_URL, EM_LICENSE_PATH, license=EM_LICENSE, prior=prior_ba,
              extra={"file": "LICENSE.md", "commit": EM_COMMIT}),
    ]
    ne_files = [
        fetch(s.url, s.path, license=NE_LICENSE, prior=prior_ne, extra={"file": s.path.name})
        for s in NE_SOURCES.values()
    ]
    return {"files": ba_files}, {"files": ne_files}


# ---------------------------------------------------------------------------
# BA boundaries
# ---------------------------------------------------------------------------

#: Window that holds the whole lower 48 and nothing of Alaska, Hawaii or Puerto Rico.
CONUS_MASK_WINDOW = (-126.0, 24.0, -66.0, 50.0)
#: Electricity Maps US zones that are not EIA-930 balancing authorities.
EM_NON_EIA_ZONES = {"US-AK", "US-AK-SEAPA", "US-HI"}
#: EIA-930 BAs that replaced others on one date, approximated by the union of the old
#: polygons (no published polygon yet). SPP's RTO West expansion went live 2026-04-01:
#: the new SPP West BA (SWPW) took over WAPA Rocky Mountain (WACM) and WAPA Upper Great
#: Plains West (WAUW). Black Hills Energy (BHBA) started the same day inside that area,
#: so the approximation also covers BHBA's territory.
SUCCESSOR_APPROXIMATIONS = {"SWPW": ("WACM", "WAUW")}

EQUAL_AREA_CRS = 5070  # NAD83 / Conus Albers


def em_zone_to_eia(zone_name: str, eia_codes: set[str]) -> str | None:
    """Electricity Maps zone key -> EIA-930 code: 'US-NW-PACE' -> 'PACE'."""
    if not zone_name.startswith("US-") or zone_name in EM_NON_EIA_ZONES:
        return None
    code = zone_name.rsplit("-", 1)[-1]
    return code if code in eia_codes else None


def load_eia930_bas() -> pd.DataFrame:
    if not EIA930_REF_PATH.exists():
        raise FileNotFoundError(
            f"{EIA930_REF_PATH} is missing; it is downloaded by the EIA-930 recon "
            f"({EIA930_REF_URL})."
        )
    bas = read_eia930_bas(EIA930_REF_PATH)
    bas["is_us"] = bas["u_s_ba"].map(_yes)
    bas["is_active"] = bas["active_ba"].map(_yes)
    bas["is_generation_only"] = bas["generation_only_ba"].map(_yes)
    return bas


def load_em_us_zones(eia_codes: set[str]) -> gpd.GeoDataFrame:
    world = gpd.read_file(EM_WORLD_PATH)
    us = world[world["zoneName"].str.startswith("US-")].copy()
    us["code"] = [em_zone_to_eia(z, eia_codes) for z in us["zoneName"]]
    return us.rename(columns={"zoneName": "em_zone"})[["em_zone", "code", "geometry"]]


def conus_land_mask() -> shapely.Geometry:
    """Lower-48 land (Natural Earth 1:10m admin-0 USA, large lakes cut out)."""
    src = NE_SOURCES["ne_10m_admin_0_countries_lakes"]
    countries = pyogrio.read_dataframe(src.vsi(), columns=["ADM0_A3"])
    usa = countries.loc[countries["ADM0_A3"] == "USA", "geometry"].union_all()
    return shapely.make_valid(shapely.clip_by_rect(usa, *CONUS_MASK_WINDOW))


def _nearest_zone_partition(geoms: np.ndarray, spacing: float, window) -> np.ndarray:
    """Split the plane into regions closest to each polygon's boundary (ordered Voronoi
    of densified boundary vertices). Returns one region per input polygon."""
    pts, labels = [], []
    for i, g in enumerate(geoms):
        b = shapely.segmentize(shapely.boundary(g), spacing)
        xy = shapely.get_coordinates(b)
        pts.append(xy)
        labels.append(np.full(len(xy), i))
    xy = np.vstack(pts)
    lab = np.concatenate(labels)
    xy, first = np.unique(np.round(xy, 9), axis=0, return_index=True)
    lab = lab[first]
    cells = shapely.voronoi_polygons(
        shapely.multipoints(xy), extend_to=shapely.box(*window), ordered=True
    )
    cells = np.asarray(shapely.get_parts(cells))
    return np.array(
        [shapely.union_all(cells[lab == i]) if np.any(lab == i) else shapely.Polygon()
         for i in range(len(geoms))],
        dtype=object,
    )


def conflate_to_land(geoms: np.ndarray, mask: shapely.Geometry, spacing: float = 0.02) -> np.ndarray:
    """Make a coverage whose outer edge is ``mask``: clip to it, then hand every uncovered
    piece of land (coastal and border slivers, islands) to the nearest polygon."""
    clipped = np.array([shapely.make_valid(shapely.intersection(g, mask)) for g in geoms], dtype=object)
    gaps = shapely.difference(mask, shapely.union_all(clipped))
    window = tuple(np.array(shapely.bounds(mask)) + np.array([-1, -1, 1, 1]))
    regions = _nearest_zone_partition(clipped, spacing, window)
    out = []
    for g, region in zip(clipped, regions):
        extra = shapely.intersection(gaps, region)
        merged = shapely.union_all([g, extra])
        out.append(shapely.make_valid(_polygonal(merged)))
    # Snap the pieces into an exact coverage (identical shared edges, no slivers).
    cleaned = shapely.coverage_clean(np.array(out, dtype=object), gap_width=1e-4)
    return np.array([_polygonal(g) for g in cleaned], dtype=object)


def _polygonal(g: shapely.Geometry) -> shapely.Geometry:
    """Keep only the polygonal parts of a geometry (drops lines and points)."""
    parts = [p for p in shapely.get_parts(g) if p.geom_type in ("Polygon", "MultiPolygon")]
    if not parts:
        return shapely.MultiPolygon()
    polys = []
    for p in parts:
        polys.extend(shapely.get_parts(p) if p.geom_type == "MultiPolygon" else [p])
    return shapely.MultiPolygon(polys)


def coverage_report(geoms: np.ndarray) -> dict:
    """Topology checks for a set of polygons that should tile without overlaps."""
    invalid_edges = shapely.coverage_invalid_edges(geoms)
    n_bad = int(sum(not shapely.is_empty(e) for e in invalid_edges))
    s = gpd.GeoSeries(list(geoms), crs=4326).to_crs(EQUAL_AREA_CRS)
    total = float(s.area.sum())
    union = float(shapely.union_all(s.values).area)
    return {
        "n": int(len(geoms)),
        "all_valid": bool(shapely.is_valid(geoms).all()),
        "coverage_valid": bool(shapely.coverage_is_valid(geoms)),
        "polygons_with_invalid_edges": n_bad,
        "overlap_km2": round((total - union) / 1e6, 3),
        "area_km2": round(total / 1e6, 1),
        "vertices": int(shapely.get_num_coordinates(geoms).sum()),
    }


BA_SIMPLIFY_DEG = 0.005  # ~500 m: under one pixel up to zoom 7
BA_DECIMALS = 4  # ~11 m


def _iso_date(us_date: str) -> str | None:
    """'4/1/2026' -> '2026-04-01'."""
    if not us_date:
        return None
    try:
        return datetime.strptime(us_date, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return us_date


def load_us_places() -> gpd.GeoDataFrame:
    """All Natural Earth 1:10m populated places in the USA (for load centers)."""
    src = NE_SOURCES["ne_10m_populated_places"]
    cols = ["NAME", "ADM0_A3", "ADM1NAME", "POP_MAX", "FEATURECLA"]
    pp = pyogrio.read_dataframe(src.vsi(), columns=cols, bbox=CONUS_MASK_WINDOW)
    pp = pp[pp["ADM0_A3"] == "USA"].copy()
    pp.columns = [c.lower() if c != "geometry" else c for c in pp.columns]
    return pp.set_geometry("geometry")


def pole_of_inaccessibility(geom: shapely.Geometry, tolerance_m: float = 500.0) -> shapely.Point:
    """Center of the largest inscribed circle, computed in Conus Albers (meters) on the
    largest part so the point sits deep inside the main body of the polygon."""
    parts = gpd.GeoSeries(list(shapely.get_parts(geom)), crs=4326).to_crs(EQUAL_AREA_CRS)
    main = parts.iloc[int(np.argmax(parts.area.values))]
    mic = shapely.maximum_inscribed_circle(main, tolerance_m)
    center = shapely.get_point(mic, 0)
    return gpd.GeoSeries([center], crs=EQUAL_AREA_CRS).to_crs(4326).iloc[0]


#: Main load center per BA: the dominant city it serves (Natural Earth name, state).
#: Curated because the polygons are coarse: "largest city inside the polygon" picks the
#: wrong city for several BAs (Miami falls in HST's polygon, Tulsa in AECI's, Reno in
#: PACW's, Raleigh in DUK's). BAs in POLE_ONLY have no dominant city (rural co-ops,
#: federal power marketers, small PUDs) and use the pole of inaccessibility.
LOAD_CENTERS: dict[str, tuple[str, str]] = {
    "AVA": ("Spokane", "Washington"),
    "AZPS": ("Phoenix", "Arizona"),
    "BANC": ("Sacramento", "California"),
    "BPAT": ("Vancouver", "Washington"),
    "CHPD": ("Wenatchee", "Washington"),
    "CISO": ("Los Angeles", "California"),
    "CPLE": ("Raleigh", "North Carolina"),
    "CPLW": ("Asheville", "North Carolina"),
    "DUK": ("Charlotte", "North Carolina"),
    "EPE": ("El Paso", "Texas"),
    "ERCO": ("Dallas", "Texas"),
    "FMPP": ("Orlando", "Florida"),
    "FPC": ("St. Petersburg", "Florida"),
    "FPL": ("Miami", "Florida"),
    "GVL": ("Gainesville", "Florida"),
    "HST": ("Homestead", "Florida"),
    "IID": ("El Centro", "California"),
    "IPCO": ("Boise", "Idaho"),
    "ISNE": ("Boston", "Massachusetts"),
    "JEA": ("Jacksonville", "Florida"),
    "LDWP": ("Los Angeles", "California"),
    "LGEE": ("Louisville", "Kentucky"),
    "MISO": ("Detroit", "Michigan"),
    "NEVP": ("Las Vegas", "Nevada"),
    "NWMT": ("Billings", "Montana"),
    "NYIS": ("New York", "New York"),
    "PACE": ("Salt Lake City", "Utah"),
    "PGE": ("Portland", "Oregon"),
    "PJM": ("Chicago", "Illinois"),
    "PNM": ("Albuquerque", "New Mexico"),
    "PSCO": ("Denver", "Colorado"),
    "PSEI": ("Olympia", "Washington"),
    "SC": ("Myrtle Beach", "South Carolina"),
    "SCEG": ("Columbia", "South Carolina"),
    "SCL": ("Seattle", "Washington"),
    "SOCO": ("Atlanta", "Georgia"),
    "SRP": ("Phoenix", "Arizona"),
    "SWPP": ("Kansas City", "Missouri"),
    "SWPW": ("Colorado Springs", "Colorado"),
    "TAL": ("Tallahassee", "Florida"),
    "TEC": ("Tampa", "Florida"),
    "TEPC": ("Tucson", "Arizona"),
    "TPWR": ("Tacoma", "Washington"),
    "TVA": ("Nashville", "Tennessee"),
    "WACM": ("Colorado Springs", "Colorado"),
}
POLE_ONLY = {"AECI", "DOPD", "GCPD", "PACW", "SEC", "SPA", "TIDC", "WALC", "WAUW"}
#: A curated city outside its (coarse) polygon is moved to the nearest point at least
#: SNAP_INSET_DEG inside the polygon, if it is within SNAP_MAX_KM of it.
SNAP_MAX_KM = 60.0
SNAP_INSET_DEG = 0.02


def representative_points(bas: gpd.GeoDataFrame, places: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """One point per BA. Methods, in order of preference:

    - ``load_center``: the curated main city lies inside the polygon; the point is the city.
    - ``load_center_snapped``: the city lies just outside the coarse polygon (<= 60 km);
      the point is the nearest point 0.02 deg inside the polygon.
    - ``pole_of_inaccessibility``: no dominant city, or the city is too far away.
    """
    by_name = {(r["name"], r["adm1name"]): r for _, r in places.iterrows()}
    rows = []
    for _, ba in bas.iterrows():
        geom = ba.geometry
        pole = pole_of_inaccessibility(geom)
        pt, method, city_name, city_pop, snap_km = pole, "pole_of_inaccessibility", None, None, None
        key = LOAD_CENTERS.get(ba.code)
        if key and ba.code not in POLE_ONLY and key in by_name:
            city = by_name[key]
            c = city.geometry
            dist_km = float(
                gpd.GeoSeries([c, shapely.ops.nearest_points(geom, c)[0]], crs=4326)
                .to_crs(EQUAL_AREA_CRS).pipe(lambda s: s.iloc[0].distance(s.iloc[1])) / 1000
            )
            if geom.contains(c):
                pt, method = c, "load_center"
            elif dist_km <= SNAP_MAX_KM:
                inner = geom.buffer(-SNAP_INSET_DEG)
                target = inner if not inner.is_empty else geom
                pt, method = shapely.ops.nearest_points(target, c)[0], "load_center_snapped"
                snap_km = round(dist_km, 1)
            if method != "pole_of_inaccessibility":
                city_name, city_pop = f"{key[0]}, {key[1]}", int(city["pop_max"])
        rows.append({
            "code": ba.code,
            "name": ba["name"],
            "method": method,
            "city": city_name,
            "city_pop_max": city_pop,
            "snap_km": snap_km,
            "label_lon": round(pole.x, 4),
            "label_lat": round(pole.y, 4),
            "active": bool(ba.active),
            "approximate": bool(ba.approximate),
            "evidence": "modeled",
            "geometry": pt,
        })
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=4326)


@dataclass
class BALayers:
    full: gpd.GeoDataFrame  # conflated, before simplification
    web: gpd.GeoDataFrame  # simplified coverage, written to ba_boundaries.geojson
    points: gpd.GeoDataFrame
    eia930: pd.DataFrame
    unmapped_em_zones: list[str]
    missing: list[dict] = field(default_factory=list)
    checks: dict = field(default_factory=dict)


def build_ba_layers(tolerance: float = BA_SIMPLIFY_DEG) -> BALayers:
    eia = load_eia930_bas()
    eia_us = eia[eia["is_us"]].set_index("ba_code")
    em = load_em_us_zones(set(eia_us.index))
    unmapped = sorted(z for z, c in zip(em["em_zone"], em["code"]) if c is None)
    em = em[em["code"].notna()].sort_values("code").reset_index(drop=True)
    if em["code"].duplicated().any():  # one feature per BA expected; dissolve if not
        em = em.dissolve(by="code", as_index=False, aggfunc="first")

    mask = conus_land_mask()
    full_geoms = conflate_to_land(em.geometry.values, mask)
    web_geoms = shapely.coverage_simplify(full_geoms, tolerance)
    checks = {
        "electricitymaps_raw": coverage_report(em.geometry.values),
        "conflated_full": coverage_report(full_geoms),
        "simplified_web": coverage_report(web_geoms),
    }

    def frame(geoms) -> gpd.GeoDataFrame:
        g = gpd.GeoDataFrame(
            {"code": em["code"].values, "em_zone": em["em_zone"].values},
            geometry=list(geoms), crs=4326,
        )
        g["geometry_source"] = "electricitymaps"
        g["approximate"] = False
        # Successor BAs with no published polygon: union of the predecessors' polygons.
        extra = []
        for new, olds in SUCCESSOR_APPROXIMATIONS.items():
            if new in eia_us.index and new not in set(g["code"]) and set(olds) <= set(g["code"]):
                union = shapely.coverage_union_all(g.loc[g["code"].isin(olds), "geometry"].values)
                extra.append({
                    "code": new, "em_zone": None, "geometry": union,
                    "geometry_source": "union:" + "+".join(olds), "approximate": True,
                })
        if extra:
            g = gpd.GeoDataFrame(
                pd.concat([g, pd.DataFrame(extra)], ignore_index=True), geometry="geometry", crs=4326
            )
        ref = eia_us.loc[g["code"]]
        g["name"] = ref["ba_name"].values
        g["region"] = ref["region_country_code"].values
        g["region_name"] = ref["region_country_name"].values
        g["time_zone"] = ref["time_zone"].values
        g["active"] = ref["is_active"].values
        g["generation_only"] = ref["is_generation_only"].values
        g["activation_date"] = [_iso_date(v) for v in ref["activation_date"]]
        g["retirement_date"] = [_iso_date(v) for v in ref["retirement_date"]]
        replaced_by = {o: n for n, olds in SUCCESSOR_APPROXIMATIONS.items() for o in olds}
        g["replaced_by"] = [replaced_by.get(c) if c in set(g["code"]) and replaced_by.get(c) in set(g["code"]) else None for c in g["code"]]
        g["replaces"] = [",".join(SUCCESSOR_APPROXIMATIONS[c]) if c in SUCCESSOR_APPROXIMATIONS else None for c in g["code"]]
        g["area_km2"] = (g.to_crs(EQUAL_AREA_CRS).area / 1e6).round(0).astype(int).values
        g["evidence"] = np.where(g["approximate"], "modeled", "observed")
        return g.sort_values("code").reset_index(drop=True)

    full = frame(full_geoms)
    web = frame(web_geoms)
    # The two non-overlapping views the dashboard can draw (checked here):
    for label, keep in {
        "active_set": web["active"],
        "pre_2026_04_set": web["code"] != "SWPW",
    }.items():
        checks[f"simplified_web_{label}"] = coverage_report(web.loc[keep, "geometry"].values)

    points = representative_points(full, load_us_places())

    have = set(full["code"])
    missing = []
    for code, row in eia_us.iterrows():
        if code in have:
            continue
        if row["is_generation_only"]:
            why = "generation-only BA: no load service territory, so no polygon in any source"
        elif not row["is_active"]:
            why = "retired BA; Electricity Maps has no polygon for it"
        else:
            why = "active BA with no polygon in Electricity Maps"
        if code == "BHBA":
            why += "; started 2026-04-01 inside the old WACM area, covered by the SWPW approximation"
        missing.append({
            "code": code, "name": row["ba_name"], "region": row["region_country_code"],
            "active": bool(row["is_active"]), "generation_only": bool(row["is_generation_only"]),
            "activation_date": _iso_date(row["activation_date"]),
            "retirement_date": _iso_date(row["retirement_date"]), "reason": why,
        })
    return BALayers(full, web, points, eia, unmapped, missing, checks)


BA_PROPERTIES = [
    "code", "name", "region", "region_name", "time_zone", "active", "generation_only",
    "activation_date", "retirement_date", "replaced_by", "replaces", "approximate",
    "geometry_source", "em_zone", "area_km2", "evidence",
]
POINT_PROPERTIES = [
    "code", "name", "method", "city", "city_pop_max", "snap_km", "label_lon", "label_lat", "active",
    "approximate", "evidence",
]


def write_ba_layers(layers: BALayers) -> dict[str, Path]:
    meta = {
        "attribution": EM_ATTRIBUTION + " Lower-48 coastline and borders: " + NE_ATTRIBUTION,
        "license": "AGPL-3.0 (derived from Electricity Maps zone geometries)",
        "crs": "EPSG:4326",
        "simplification": f"shapely.coverage_simplify, tolerance {BA_SIMPLIFY_DEG} deg; "
                          f"coordinates rounded to {BA_DECIMALS} decimals",
        "built_at": utc_now(),
    }
    out = {
        "boundaries": write_geojson(
            layers.web, GEO_DIR / "ba_boundaries.geojson", decimals=BA_DECIMALS,
            properties=BA_PROPERTIES, id_field="code", meta=meta,
        ),
        "points": write_geojson(
            layers.points, GEO_DIR / "ba_points.geojson", decimals=BA_DECIMALS,
            properties=POINT_PROPERTIES, id_field="code",
            meta={**meta, "method": "load_center = the BA's curated main city (Natural Earth "
                  "1:10m populated place) when it lies inside the polygon; load_center_snapped = "
                  "that city moved to the nearest point 0.02 deg inside the coarse polygon "
                  "(city within 60 km); pole_of_inaccessibility = center of the largest "
                  "inscribed circle of the polygon's largest part (EPSG:5070). label_lon/label_lat "
                  "is always the pole of inaccessibility."},
        ),
    }
    return out


# ---------------------------------------------------------------------------
# Natural Earth basemap
# ---------------------------------------------------------------------------

BASEMAP_SIMPLIFY_DEG = 0.005  # ~500 m, matches the BA layer
BASEMAP_DECIMALS = 4
NEIGHBOURS = ("CAN", "MEX")


def read_ne(name: str, *, columns: list[str] | None = None, bbox=BASEMAP_BBOX) -> gpd.GeoDataFrame:
    """Read one Natural Earth layer straight from its zip, lower-case the columns."""
    df = pyogrio.read_dataframe(NE_SOURCES[name].vsi(), columns=columns, bbox=bbox)
    df.columns = [c if c == "geometry" else c.lower() for c in df.columns]
    return df.set_geometry("geometry")


def clip_simplify(gdf: gpd.GeoDataFrame, bbox, tol: float) -> gpd.GeoDataFrame:
    """Clip to the bbox and simplify each geometry (topology-preserving per feature)."""
    geoms = gdf.geometry.values
    box = shapely.box(*bbox)
    if gdf.geom_type.str.contains("Polygon").any():
        geoms = shapely.intersection(shapely.make_valid(geoms), box)
    else:
        geoms = shapely.clip_by_rect(geoms, *bbox)
    geoms = shapely.simplify(geoms, tol, preserve_topology=True)
    out = gdf.copy()
    out["geometry"] = geoms
    out = out[~shapely.is_empty(out.geometry.values)]
    if gdf.geom_type.str.contains("Polygon").any():
        out["geometry"] = [_polygonal(g) for g in out.geometry.values]
        out = out[~shapely.is_empty(out.geometry.values)]
    return out.reset_index(drop=True)


@dataclass(frozen=True)
class BasemapLayer:
    key: str  # output file stem
    source: str  # NE_SOURCES key
    build: Callable[[], gpd.GeoDataFrame]
    note: str
    decimals: int = BASEMAP_DECIMALS


def _land() -> gpd.GeoDataFrame:
    return clip_simplify(read_ne("ne_10m_land", columns=["min_zoom"]), BASEMAP_BBOX, BASEMAP_SIMPLIFY_DEG)


def _land_context() -> gpd.GeoDataFrame:
    g = read_ne("ne_50m_land", columns=["min_zoom"], bbox=CONTEXT_BBOX)
    return clip_simplify(g, CONTEXT_BBOX, 0.02)


def _coastline() -> gpd.GeoDataFrame:
    return clip_simplify(read_ne("ne_10m_coastline", columns=["min_zoom"]), BASEMAP_BBOX, BASEMAP_SIMPLIFY_DEG)


def _lakes() -> gpd.GeoDataFrame:
    g = read_ne("ne_10m_lakes", columns=["name", "featurecla", "scalerank", "min_zoom"])
    return clip_simplify(g[g["min_zoom"] <= 7], BASEMAP_BBOX, BASEMAP_SIMPLIFY_DEG)


def _rivers() -> gpd.GeoDataFrame:
    g = read_ne("ne_10m_rivers_lake_centerlines", columns=["name", "featurecla", "scalerank", "min_zoom"])
    return clip_simplify(g[g["min_zoom"] <= 6], BASEMAP_BBOX, BASEMAP_SIMPLIFY_DEG)


def _urban_areas() -> gpd.GeoDataFrame:
    g = read_ne("ne_10m_urban_areas", columns=["area_sqkm", "min_zoom"])
    g = clip_simplify(g[g["min_zoom"] <= 7], BASEMAP_BBOX, BASEMAP_SIMPLIFY_DEG)
    g["area_sqkm"] = g["area_sqkm"].round(1)
    return g


def _cities() -> gpd.GeoDataFrame:
    cols = ["NAME", "ADM0_A3", "ADM1NAME", "POP_MAX", "FEATURECLA", "SCALERANK", "LABELRANK", "MIN_ZOOM"]
    g = read_ne("ne_10m_populated_places", columns=cols)
    capital = g["featurecla"].str.contains("capital", case=False)
    us = (g["adm0_a3"] == "USA") & ((g["pop_max"] >= 150_000) | (capital & (g["pop_max"] >= 50_000)) | (g["featurecla"] == "Admin-0 capital"))
    nb = g["adm0_a3"].isin(NEIGHBOURS) & ((g["pop_max"] >= 500_000) | (g["featurecla"] == "Admin-0 capital"))
    g = g[us | nb].copy()
    g["capital"] = np.select(
        [g["featurecla"].str.startswith("Admin-0 capital"), g["featurecla"].str.startswith("Admin-1 capital")],
        ["national", "state"], default="",
    )
    g = g.sort_values("pop_max", ascending=False)
    g["rank"] = np.arange(1, len(g) + 1)  # label priority: 1 = biggest
    return g[["name", "adm0_a3", "adm1name", "pop_max", "capital", "scalerank", "labelrank", "min_zoom", "rank", "geometry"]].reset_index(drop=True)


def _roads() -> gpd.GeoDataFrame:
    g = read_ne("ne_10m_roads", columns=["name", "label", "level", "type", "sov_a3", "scalerank", "min_zoom", "expressway"])
    keep = ((g["sov_a3"] == "USA") & (g["level"] == "Interstate")) | (
        g["sov_a3"].isin(NEIGHBOURS) & (g["type"] == "Major Highway") & (g["min_zoom"] <= 6)
    )
    g = clip_simplify(g[keep], BASEMAP_BBOX, BASEMAP_SIMPLIFY_DEG)
    return g.drop(columns=["expressway"])


def _states() -> gpd.GeoDataFrame:
    cols = ["name", "postal", "iso_3166_2", "adm0_a3", "type_en", "latitude", "longitude"]
    g = read_ne("ne_10m_admin_1_states_provinces_lakes", columns=cols)
    g = g[(g["adm0_a3"] == "USA") & ~g["postal"].isin(["AK", "HI"])]
    g = clip_simplify(g, BASEMAP_BBOX, BASEMAP_SIMPLIFY_DEG)
    return g.rename(columns={"latitude": "label_lat", "longitude": "label_lon"}).drop(columns=["adm0_a3"])


def _state_lines() -> gpd.GeoDataFrame:
    g = read_ne("ne_10m_admin_1_states_provinces_lines", columns=["FEATURECLA", "NAME", "ADM0_A3", "MIN_ZOOM"])
    g = g[g["adm0_a3"].isin(("USA",) + NEIGHBOURS) & (g["featurecla"] == "Admin-1 boundary")]
    return clip_simplify(g.drop(columns=["featurecla"]), BASEMAP_BBOX, BASEMAP_SIMPLIFY_DEG)


def _countries() -> gpd.GeoDataFrame:
    g = read_ne("ne_10m_admin_0_countries_lakes", columns=["NAME", "ADM0_A3", "MIN_ZOOM"])
    return clip_simplify(g, BASEMAP_BBOX, BASEMAP_SIMPLIFY_DEG)


def _country_borders() -> gpd.GeoDataFrame:
    g = read_ne("ne_10m_admin_0_boundary_lines_land", columns=["FEATURECLA", "ADM0_A3_L", "ADM0_A3_R", "MIN_ZOOM"])
    return clip_simplify(g, BASEMAP_BBOX, BASEMAP_SIMPLIFY_DEG)


BASEMAP_LAYERS = [
    BasemapLayer("land", "ne_10m_land", _land, "1:10m land, clipped to the basemap frame"),
    BasemapLayer("land_context", "ne_50m_land", _land_context,
                 "1:50m land for a wider frame; draw under `land` so a pitched camera never sees an edge", 3),
    BasemapLayer("coastline", "ne_10m_coastline", _coastline, "1:10m coastline lines (ocean = map background)"),
    BasemapLayer("lakes", "ne_10m_lakes", _lakes, "1:10m lakes and reservoirs with min_zoom <= 7"),
    BasemapLayer("rivers", "ne_10m_rivers_lake_centerlines", _rivers, "1:10m major rivers (min_zoom <= 6)"),
    BasemapLayer("urban_areas", "ne_10m_urban_areas", _urban_areas, "1:10m urban footprints with min_zoom <= 7"),
    BasemapLayer("cities", "ne_10m_populated_places", _cities,
                 "US places with pop_max >= 150k or state/national capitals >= 50k; Canada and Mexico >= 500k or national capital"),
    BasemapLayer("roads", "ne_10m_roads", _roads, "US Interstates; Canada/Mexico major highways with min_zoom <= 6"),
    BasemapLayer("states", "ne_10m_admin_1_states_provinces_lakes", _states, "Lower-48 states + DC polygons (large lakes cut out), with NE label points"),
    BasemapLayer("state_lines", "ne_10m_admin_1_states_provinces_lines", _state_lines, "admin-1 boundary lines for USA, Canada, Mexico"),
    BasemapLayer("countries", "ne_10m_admin_0_countries_lakes", _countries, "country polygons in the frame (USA, Canada, Mexico, Caribbean, Central America)"),
    BasemapLayer("country_borders", "ne_10m_admin_0_boundary_lines_land", _country_borders, "international land borders in the frame"),
]


def build_basemap() -> list[dict]:
    records = []
    for layer in BASEMAP_LAYERS:
        gdf = layer.build()
        path = write_geojson(
            gdf, BASEMAP_DIR / f"{layer.key}.geojson", decimals=layer.decimals,
            meta={"attribution": NE_ATTRIBUTION, "license": "public domain (Natural Earth)",
                  "source": NE_SOURCES[layer.source].url, "note": layer.note, "crs": "EPSG:4326"},
        )
        records.append(output_record(
            path, layer=layer.key, source=NE_SOURCES[layer.source].name, features=len(gdf),
            vertices=int(shapely.get_num_coordinates(gdf.geometry.values).sum()), note=layer.note,
        ))
    return records


# ---------------------------------------------------------------------------
# Shaded relief raster (for a deck.gl BitmapLayer or a MapLibre image source)
# ---------------------------------------------------------------------------

RELIEF_PX_PER_DEG = 30  # SR_50M is 10800 x 5400 over the globe
RELIEF_OUT_WIDTH = 2048


def _merc_y(lat_deg):
    return np.log(np.tan(np.pi / 4 + np.radians(lat_deg) / 2))


def build_relief(bbox=BASEMAP_BBOX, out_width: int = RELIEF_OUT_WIDTH) -> dict:
    """Crop Natural Earth 1:50m shaded relief to ``bbox``, resample its rows to Web Mercator
    (so a linear image between the corner coordinates lines up on a Mercator map) and write
    an 8-bit grayscale PNG plus its bounds."""
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = 10800 * 5400 + 1
    src = NE_SOURCES["SR_50M"]
    with zipfile.ZipFile(src.path) as z:
        member = next(n for n in z.namelist() if n.lower().endswith((".tif", ".tiff")))
        img = Image.open(io.BytesIO(z.read(member)))
        img.load()
    arr = np.asarray(img.convert("L"), dtype=np.float32)
    h, w = arr.shape
    ppd = w / 360.0
    west, south, east, north = bbox
    c0, c1 = int(round((west + 180) * ppd)), int(round((east + 180) * ppd))
    crop = arr[:, c0:c1]
    # Output rows evenly spaced in Mercator y; sample source rows (evenly spaced in lat).
    width_rad = np.radians(east - west)
    y_n, y_s = _merc_y(north), _merc_y(south)
    out_h_full = int(round(crop.shape[1] * (y_n - y_s) / width_rad))
    ys = y_n - (np.arange(out_h_full) + 0.5) * (y_n - y_s) / out_h_full
    lats = np.degrees(2 * np.arctan(np.exp(ys)) - np.pi / 2)
    rows = (90.0 - lats) * ppd - 0.5
    r0 = np.clip(np.floor(rows).astype(int), 0, h - 1)
    r1 = np.clip(r0 + 1, 0, h - 1)
    f = (rows - r0)[:, None]
    merc = crop[r0] * (1 - f) + crop[r1] * f
    out = Image.fromarray(np.clip(merc + 0.5, 0, 255).astype(np.uint8), mode="L")
    if out.width > out_width:
        out = out.resize((out_width, int(round(out.height * out_width / out.width))), Image.LANCZOS)
    png = BASEMAP_DIR / "relief.png"
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    write_atomic(png, buf.getvalue())
    meta = {
        "image": "relief.png",
        "bounds": [west, south, east, north],
        "deckgl_bounds": [west, south, east, north],
        "maplibre_coordinates": [[west, north], [east, north], [east, south], [west, south]],
        "projection": "rows resampled to Web Mercator (EPSG:3857) between the bounds; "
                      "columns linear in longitude",
        "width": out.width,
        "height": out.height,
        "source": src.url,
        "attribution": NE_ATTRIBUTION,
        "license": "public domain (Natural Earth)",
        "note": "8-bit grayscale hillshade (Natural Earth 1:50m 'Shaded Relief'); "
                "blend with multiply/screen or use as opacity.",
    }
    meta_path = BASEMAP_DIR / "relief.json"
    write_atomic(meta_path, (json.dumps(meta, indent=2) + "\n").encode())
    return {"png": output_record(png, layer="relief", source=src.name, width=out.width, height=out.height),
            "json": output_record(meta_path, layer="relief_bounds")}
