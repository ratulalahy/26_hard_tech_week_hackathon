# Data profile: map assets (BA boundaries and offline basemap)

Status: built 2026-10-27 (UTC) by `cd lab && uv run python -I scripts/recon_geo.py`. Code: `lab/src/gridpilot/data/geo.py`. Manifests: `data/manifests/geo_ba_boundaries.json`, `data/manifests/geo_natural_earth.json`.

Every map asset is a local file: GeoJSON in EPSG:4326, plus one PNG. The dashboard needs no tile server, no glyph server and no network.

## Outputs

All paths are under `data/processed/geo/`. Total size: 5.68 MB.

| File | Bytes | Features | What |
|---|---:|---:|---|
| `ba_boundaries.geojson` | 380,916 | 54 | BA polygons: a gap-free, non-overlapping coverage of the lower 48 |
| `ba_points.geojson` | 19,831 | 54 | one point per BA (load center or pole of inaccessibility), plus a label point |
| `basemap/land.geojson` | 617,382 | 9 | NE 1:10m land |
| `basemap/land_context.geojson` | 241,003 | 385 | NE 1:50m land for a wider frame |
| `basemap/coastline.geojson` | 633,679 | 617 | NE 1:10m coastline (lines) |
| `basemap/lakes.geojson` | 497,778 | 385 | NE 1:10m lakes and reservoirs, `min_zoom` ≤ 7 |
| `basemap/rivers.geojson` | 299,474 | 183 | NE 1:10m major rivers, `min_zoom` ≤ 6 |
| `basemap/urban_areas.geojson` | 343,006 | 663 | NE 1:10m urban footprints, `min_zoom` ≤ 7 |
| `basemap/cities.geojson` | 61,444 | 258 | major cities (filter below), with a `rank` for label priority |
| `basemap/roads.geojson` | 543,115 | 1,610 | US Interstates; Canada/Mexico major highways |
| `basemap/states.geojson` | 276,085 | 49 | lower-48 states + DC (large lakes cut out), with NE label points |
| `basemap/state_lines.geojson` | 130,721 | 184 | admin-1 boundary lines for the USA, Canada and Mexico |
| `basemap/countries.geojson` | 679,932 | 36 | country polygons in the frame: USA, Canada, Mexico, Caribbean, Central America |
| `basemap/country_borders.geojson` | 33,442 | 21 | international land borders |
| `basemap/relief.png` | 916,764 | — | 2048×1489 grayscale shaded relief, Web Mercator rows |
| `basemap/relief.json` | 826 | — | relief bounds and corner coordinates |

Each output's sha256 is in its manifest's `outputs` list. Outputs are written atomically (temp file, then rename).

- `ba_boundaries.geojson` and `ba_points.geojson` carry the attribution in a top-level `metadata` member.
- Each basemap file carries its source URL, its attribution and a note.

Raw downloads (74 MB) are in `data/raw/geo/`, one directory per download; they are read in place from the zips. The EIA-930 reference table is not duplicated: it is read from `data/raw/eia930/`, and its record is cited from `eia930.json`.

## Sources, licenses, attribution

| Source | Used for | License | Attribution text |
|---|---|---|---|
| Electricity Maps, `geo/world.geojson` in [electricitymaps-contrib](https://github.com/electricitymaps/electricitymaps-contrib) at commit `501e61d` (2026-10-26) | BA polygons (US zones keyed `US-<region>-<EIA code>`) | **AGPL-3.0**: the repository license since v1.5.0. Copyleft: the derived `ba_boundaries.geojson` must be redistributed under AGPL-3.0 with this notice. The license text is saved next to the download. | "BA boundaries: Electricity Maps contributors, electricitymaps-contrib zone geometries (commit 501e61d), AGPL-3.0, simplified." |
| EIA-930 reference tables (`EIA930_Reference_Tables.xlsx`, sheet `BAs`) | BA codes, names, regions, time zones, active, generation-only and retirement flags | Public domain (U.S. government work) | "Source: U.S. Energy Information Administration, Form EIA-930." |
| Natural Earth 1:10m and 1:50m vectors; 1:50m Shaded Relief (`SR_50M`), from naciscdn.org | basemap layers and relief; the lower-48 land mask that the BA coastlines follow; city points | Public domain ([terms](https://www.naturalearthdata.com/about/terms-of-use/)): "No permission is needed to use Natural Earth. Crediting the authors is unnecessary." | "Made with Natural Earth. Free vector and raster map data @ naturalearthdata.com." |

Attribution line for the map:

> BA boundaries © Electricity Maps contributors (AGPL-3.0). BA codes: U.S. EIA Form EIA-930. Basemap: Natural Earth.

### Why Electricity Maps

On 2026-10-27, no public-domain BA polygon source was online. Every rejected source is listed in the manifest's `rejected_sources`.

**Rejected sources:**
- **HIFLD Open "Control Areas":** retired. Its ArcGIS services answer "Invalid URL", and ORNL's Open Energy Hub keeps only a tombstone record dated 2026-03-16.
- **EIA Energy Atlas `Balancing_Authorities`:** returns "Token Required". None of EIA's 79 public ArcGIS feature services has BA polygons.
- **NASA's mirror of HIFLD Open:** refused connections.
- **Third-party re-uploads on ArcGIS Online:** reachable, but they have no license or provenance metadata. HIFLD-style control areas also overlap each other.
- **EIA Grid Monitor:** embeds only the 13 regions and state outlines.

**Why Electricity Maps:**
- It is maintained (pushed 2026-10-26).
- Its zones are keyed by EIA-930 codes, so the mapping is exact.
- Its zones already tile without overlaps, which extruded 3D polygons need.

**Cost:** the AGPL copyleft, and coarse boundaries. The 53 US zones have only 4,476 vertices in total.

## How the BA polygons are built

1. Keep the Electricity Maps zones whose key starts with `US-` and whose last part is an EIA-930 code (`US-NW-PACE` → `PACE`).
   - The mapping is exact for all 53 lower-48 zones.
   - `US-AK`, `US-AK-SEAPA` and `US-HI` are dropped: EIA-930 has no Alaska or Hawaii BAs.
2. **Fit to the basemap.**
   - Clip each zone to Natural Earth 1:10m admin-0 USA (large lakes cut out), in the window [-126, 24, -66, 50].
   - Give every uncovered land sliver (coastal strips, border strips, islands) to the nearest zone, using an ordered Voronoi of the zone boundaries densified to 0.02°.
   - Run `shapely.coverage_clean`.
   - As a result, BA coastlines and borders match the basemap's land, so extruded polygons sit on the coast.
3. `shapely.coverage_simplify` at 0.005° (~500 m, under a pixel up to zoom 7). This keeps shared edges identical, so neighbours never gap. Coordinates are rounded to 4 decimals (~11 m).
4. **SWPW (SPP West BA, active since 2026-04-01)** has no published polygon yet.
   - It replaced WACM and WAUW, which retired that day, when SPP's RTO West went live.
   - It is drawn as the union of the WACM and WAUW polygons, with `approximate: true` and `evidence: modeled`.

**Checks** (from the manifest's `build.checks`):

| Stage | Valid coverage | Overlap | Vertices |
|---|---|---|---:|
| Electricity Maps as published | no: 3 mismatched edges (JEA, SEC, SOCO), 0.05 km² overlap | 0.053 km² | 4,476 |
| fitted to land | yes | 0 | 24,134 |
| simplified (web) | yes | 0 | 18,192 |
| active set (excludes WACM, WAUW) | yes | 0 | 18,185 |
| pre-2026-04 set (excludes SWPW) | yes | 0 | 18,192 |

The fitted coverage's area, 7,786,694 km², equals the land mask's: nothing on lower-48 land is left uncovered.

**Draw one non-overlapping set.** SWPW overlaps WACM and WAUW by design.
- Filter `active == true` for current data (from 2026-04-01).
- Filter `code != 'SWPW'` for history before April 2026.

### Feature properties

- **`ba_boundaries.geojson`:**
  - identity: `code` (also the feature `id`), `name`, `region`, `region_name`, `time_zone`;
  - status: `active`, `generation_only`, `activation_date`, `retirement_date`, `replaced_by`, `replaces`;
  - geometry provenance: `approximate`, `geometry_source`, `em_zone`;
  - size and label: `area_km2`, `evidence` (`observed`, or `modeled` for SWPW).
- **`ba_points.geojson`:**
  - identity and method: `code`, `name`, `method`, `city`, `city_pop_max`, `snap_km`;
  - label point: `label_lon`, `label_lat` (always the pole of inaccessibility: best for labels);
  - status: `active`, `approximate`, `evidence` (`modeled`).
  - The point geometry is the arc endpoint.

### Point methods

- `load_center` (39 BAs): the BA's main city lies inside its polygon; the point is that city. The city comes from a curated table (`LOAD_CENTERS` in `geo.py`) of the dominant city each BA serves, matched to Natural Earth 1:10m populated places.
- `load_center_snapped` (6 BAs): the city falls just outside the coarse polygon (≤ 60 km away). The point is moved to the nearest spot 0.02° inside the polygon. `snap_km` gives the distance.
- `pole_of_inaccessibility` (9 BAs): the center of the largest inscribed circle of the polygon's largest part, computed in EPSG:5070. Used when there is no dominant city: rural co-ops, federal power marketers, small PUDs.

The table is curated because "largest city inside the polygon" picked the wrong city in several BAs: Miami fell in HST, Tulsa in AECI, Reno in PACW, Raleigh in DUK, and Billings in WAUW.

PJM's point is Chicago, its largest metro, which sits at PJM's western edge. Use `label_lon`/`label_lat` for its label. If the story wants Northern Virginia's data centers, override that one endpoint in the UI.

## BA-to-feature mapping

| EIA-930 code | Name | Electricity Maps zone | Geometry | Active | Area (km²) | Point method | Point city |
|---|---|---|---|---|---:|---|---|
| AECI | Associated Electric Cooperative, Inc. | US-MIDW-AECI | Electricity Maps | yes | 218,489 | pole_of_inaccessibility | — |
| AVA | Avista Corporation | US-NW-AVA | Electricity Maps | yes | 107,879 | load_center | Spokane, Washington |
| AZPS | Arizona Public Service Company | US-SW-AZPS | Electricity Maps | yes | 97,414 | load_center_snapped | Phoenix, Arizona (snapped 30.6 km) |
| BANC | Balancing Authority of Northern California | US-CAL-BANC | Electricity Maps | yes | 10,297 | load_center | Sacramento, California |
| BPAT | Bonneville Power Administration | US-NW-BPAT | Electricity Maps | yes | 89,201 | load_center | Vancouver, Washington |
| CHPD | Public Utility District No. 1 of Chelan County | US-NW-CHPD | Electricity Maps | yes | 7,547 | load_center | Wenatchee, Washington |
| CISO | California Independent System Operator | US-CAL-CISO | Electricity Maps | yes | 317,899 | load_center | Los Angeles, California |
| CPLE | Duke Energy Progress East | US-CAR-CPLE | Electricity Maps | yes | 52,417 | load_center_snapped | Raleigh, North Carolina (snapped 16.6 km) |
| CPLW | Duke Energy Progress West | US-CAR-CPLW | Electricity Maps | yes | 13,187 | load_center | Asheville, North Carolina |
| DOPD | PUD No. 1 of Douglas County | US-NW-DOPD | Electricity Maps | yes | 12,699 | pole_of_inaccessibility | — |
| DUK | Duke Energy Carolinas | US-CAR-DUK | Electricity Maps | yes | 67,931 | load_center | Charlotte, North Carolina |
| EPE | El Paso Electric Company | US-SW-EPE | Electricity Maps | yes | 60,181 | load_center | El Paso, Texas |
| ERCO | Electric Reliability Council of Texas, Inc. | US-TEX-ERCO | Electricity Maps | yes | 564,768 | load_center | Dallas, Texas |
| FMPP | Florida Municipal Power Pool | US-FLA-FMPP | Electricity Maps | yes | 13,882 | load_center | Orlando, Florida |
| FPC | Duke Energy Florida, Inc. | US-FLA-FPC | Electricity Maps | yes | 14,909 | load_center | St. Petersburg, Florida |
| FPL | Florida Power & Light Co. | US-FLA-FPL | Electricity Maps | yes | 34,386 | load_center_snapped | Miami, Florida (snapped 20.3 km) |
| GCPD | Public Utility District No. 2 of Grant County, Washington | US-NW-GCPD | Electricity Maps | yes | 7,342 | pole_of_inaccessibility | — |
| GVL | Gainesville Regional Utilities | US-FLA-GVL | Electricity Maps | yes | 3,004 | load_center | Gainesville, Florida |
| HST | City of Homestead | US-FLA-HST | Electricity Maps | yes | 5,407 | load_center | Homestead, Florida |
| IID | Imperial Irrigation District | US-CAL-IID | Electricity Maps | yes | 17,673 | load_center | El Centro, California |
| IPCO | Idaho Power Company | US-NW-IPCO | Electricity Maps | yes | 198,062 | load_center | Boise, Idaho |
| ISNE | ISO New England | US-NE-ISNE | Electricity Maps | yes | 170,056 | load_center | Boston, Massachusetts |
| JEA | JEA | US-FLA-JEA | Electricity Maps | yes | 10,466 | load_center | Jacksonville, Florida |
| LDWP | Los Angeles Department of Water and Power | US-CAL-LDWP | Electricity Maps | yes | 5,448 | load_center_snapped | Los Angeles, California (snapped 3.0 km) |
| LGEE | Louisville Gas and Electric Company and Kentucky Utilities Company | US-MIDW-LGEE | Electricity Maps | yes | 8,354 | load_center | Louisville, Kentucky |
| MISO | Midcontinent Independent System Operator, Inc. | US-MIDW-MISO | Electricity Maps | yes | 1,125,806 | load_center_snapped | Detroit, Michigan (snapped 0.1 km) |
| NEVP | Nevada Power Company | US-NW-NEVP | Electricity Maps | yes | 314,833 | load_center | Las Vegas, Nevada |
| NWMT | NorthWestern Corporation | US-NW-NWMT | Electricity Maps | yes | 257,716 | load_center_snapped | Billings, Montana (snapped 31.9 km) |
| NYIS | New York Independent System Operator | US-NY-NYIS | Electricity Maps | yes | 127,567 | load_center | New York, New York |
| PACE | PacifiCorp East | US-NW-PACE | Electricity Maps | yes | 452,704 | load_center | Salt Lake City, Utah |
| PACW | PacifiCorp West | US-NW-PACW | Electricity Maps | yes | 237,905 | pole_of_inaccessibility | — |
| PGE | Portland General Electric Company | US-NW-PGE | Electricity Maps | yes | 10,456 | load_center | Portland, Oregon |
| PJM | PJM Interconnection, LLC | US-MIDA-PJM | Electricity Maps | yes | 580,538 | load_center | Chicago, Illinois |
| PNM | Public Service Company of New Mexico | US-SW-PNM | Electricity Maps | yes | 215,029 | load_center | Albuquerque, New Mexico |
| PSCO | Public Service Company of Colorado | US-NW-PSCO | Electricity Maps | yes | 99,701 | load_center | Denver, Colorado |
| PSEI | Puget Sound Energy, Inc. | US-NW-PSEI | Electricity Maps | yes | 19,561 | load_center | Olympia, Washington |
| SC | South Carolina Public Service Authority | US-CAR-SC | Electricity Maps | yes | 27,100 | load_center | Myrtle Beach, South Carolina |
| SCEG | Dominion Energy South Carolina, Inc. | US-CAR-SCEG | Electricity Maps | yes | 34,936 | load_center | Columbia, South Carolina |
| SCL | Seattle City Light | US-NW-SCL | Electricity Maps | yes | 336 | load_center | Seattle, Washington |
| SEC | Seminole Electric Cooperative | US-FLA-SEC | Electricity Maps | yes | 45,307 | pole_of_inaccessibility | — |
| SOCO | Southern Company Services, Inc. - Trans | US-SE-SOCO | Electricity Maps | yes | 303,279 | load_center | Atlanta, Georgia |
| SPA | Southwestern Power Administration | US-CENT-SPA | Electricity Maps | yes | 1,187 | pole_of_inaccessibility | — |
| SRP | Salt River Project Agricultural Improvement and Power District | US-SW-SRP | Electricity Maps | yes | 26,883 | load_center | Phoenix, Arizona |
| SWPP | Southwest Power Pool | US-CENT-SWPP | Electricity Maps | yes | 919,507 | load_center | Kansas City, Missouri |
| SWPW | Southwest Power Pool West Balancing Authority Area | — | approximate: union of WACM+WAUW | yes (from 2026-04-01) | 542,608 | load_center | Colorado Springs, Colorado |
| TAL | City of Tallahassee | US-FLA-TAL | Electricity Maps | yes | 123 | load_center | Tallahassee, Florida |
| TEC | Tampa Electric Company | US-FLA-TEC | Electricity Maps | yes | 4,342 | load_center | Tampa, Florida |
| TEPC | Tucson Electric Power | US-SW-TEPC | Electricity Maps | yes | 22,623 | load_center | Tucson, Arizona |
| TIDC | Turlock Irrigation District | US-CAL-TIDC | Electricity Maps | yes | 1,949 | pole_of_inaccessibility | — |
| TPWR | City of Tacoma, Department of Public Utilities, Light Division | US-NW-TPWR | Electricity Maps | yes | 18,629 | load_center | Tacoma, Washington |
| TVA | Tennessee Valley Authority | US-TEN-TVA | Electricity Maps | yes | 199,752 | load_center | Nashville, Tennessee |
| WACM | Western Area Power Administration - Rocky Mountain Region | US-NW-WACM | Electricity Maps | no, retired 2026-04-01 | 409,270 | load_center | Colorado Springs, Colorado |
| WALC | Western Area Power Administration - Desert Southwest Region | US-SW-WALC | Electricity Maps | yes | 89,506 | pole_of_inaccessibility | — |
| WAUW | Western Area Power Administration - Upper Great Plains West | US-NW-WAUW | Electricity Maps | no, retired 2026-04-01 | 133,338 | pole_of_inaccessibility | — |

## Coverage gaps

### EIA-930 US BA codes with no polygon (18)

| Code | Name | Active | Generation-only | Retired | Why |
|---|---|---|---|---|---|
| AVRN | Avangrid Renewables, LLC | yes | yes | | generation-only: no load territory |
| DEAA | Arlington Valley, LLC | yes | yes | | generation-only |
| GRID | Gridforce Energy Management, LLC | yes | yes | | generation-only |
| GWA | NaturEner Power Watch, LLC | yes | yes | | generation-only |
| SEPA | Southeastern Power Administration | yes | yes | | generation-only |
| SIKE | Sikeston Board Of Municipal Utilities | yes | yes | | generation-only (active since 2025-06-01) |
| YAD | Alcoa Power Generating, Inc. - Yadkin Division | yes | yes | | generation-only |
| **BHBA** | Black Hills Energy | yes (since 2026-04-01) | no | | **the only active load-serving BA without a polygon.** It started inside the old WACM area, so SWPW's approximate polygon covers its territory. |
| EEI | Electric Energy, Inc. | no | yes | 2020-02-29 | retired, generation-only |
| GLHB | GridLiance | no | yes | 2022-09-01 | retired, generation-only |
| GRIF | Griffith Energy, LLC | no | yes | 2023-11-01 | retired, generation-only |
| GRMA | Gila River Power, LLC | no | yes | 2018-05-03 | retired, generation-only |
| HGMA | New Harquahala Generating Company, LLC | no | yes | 2025-06-01 | retired, generation-only |
| WWA | NaturEner Wind Watch, LLC | no | yes | 2025-10-01 | retired, generation-only |
| AEC | PowerSouth Energy Cooperative | no | no | 2021-09-01 | retired; its former area lies inside SOCO's polygon |
| NSB | Utilities Commission of New Smyrna Beach | no | no | 2020-01-08 | retired; its area lies inside FPL's polygon |
| OVEC | Ohio Valley Electric Corporation | no | no | 2018-12-01 | retired |
| WAUE | Western Area Power Administration - Upper Great Plains East | no | no | 2015-10-01 | retired |

- **Retired BAs with data and a polygon:** WACM and WAUW retired 2026-04-01, inside the sealed test window.
  - Their polygons are kept for history; SWPW covers the same area from that date.
  - A region set that includes the Rockies has to handle this switch.
- **Canada and Mexico:** EIA-930's 9 Canadian and Mexican BAs (AESO, BCHA, HQT, IESO, MHEB, NBSO, SPC, CEN, CFE) appear only as interchange partners. They have no polygons here; `countries.geojson` gives Canada and Mexico as context.

### Accuracy caveats

- **Boundaries are approximate by nature.** BAs have no legal boundary, and Electricity Maps' zones are coarse. Use them for a national or regional map, not for city-level claims.
  - Several cities fall inside the "wrong" zone polygon: Miami in HST (whose polygon is 5,407 km², against roughly 40 km² for Homestead itself), Tulsa in AECI, Reno in PACW, Raleigh in DUK, Billings in WAUW, and Everett in PSEI.
  - The curated load-center points correct for this; the polygons do not.
- **Interior BA-to-BA lines** are Electricity Maps' coarse lines. Only the outer coast and border follow Natural Earth 1:10m.
- **SWPW is an approximation** (WACM ∪ WAUW). It includes BHBA's territory, and it may not match SPP West's footprint exactly.

## Basemap layers (Natural Earth, public domain)

**Frame.** All layers except `land_context` are clipped to [-140, 14, -50, 62]. That is the lower 48 plus a margin of roughly 15° west, 10° south, 17° east and 13° north, so a pitched camera at zoom 3–7 stays inside real data. `land_context` (1:50m) covers [-180, 0, -20, 84]; draw it under `land` in the same fill so the frame's edge never shows.

**Simplification.**
- Polygons and lines: `shapely.simplify(preserve_topology=True)` at 0.005°, the same as the BA layer, with coordinates rounded to 4 decimals.
- `land_context`: 0.02° and 3 decimals.

Every feature keeps Natural Earth's `min_zoom`, so the front end can thin layers by zoom: one MapLibre layer per zoom band (`minzoom`/`maxzoom` plus a static `min_zoom` filter), or a filter on the current zoom in deck.gl.

| Layer | Source | Filter |
|---|---|---|
| `land` | `ne_10m_land` | none |
| `land_context` | `ne_50m_land` | none |
| `coastline` | `ne_10m_coastline` | none |
| `lakes` | `ne_10m_lakes` | `min_zoom` ≤ 7 |
| `rivers` | `ne_10m_rivers_lake_centerlines` | `min_zoom` ≤ 6 ("major rivers"; lake centerlines keep the network connected) |
| `urban_areas` | `ne_10m_urban_areas` | `min_zoom` ≤ 7 |
| `cities` | `ne_10m_populated_places` | US: `pop_max` ≥ 150k, or a state capital with ≥ 50k. Canada and Mexico: ≥ 500k or the national capital. Fields: `name`, `adm0_a3`, `adm1name`, `pop_max`, `capital`, `scalerank`, `labelrank`, `min_zoom`, `rank` (1 = biggest). |
| `roads` | `ne_10m_roads` | US `level == Interstate`; Canada and Mexico `type == Major Highway` with `min_zoom` ≤ 6 |
| `states` | `ne_10m_admin_1_states_provinces_lakes` | USA without AK and HI. Fields: `name`, `postal`, `iso_3166_2`, `type_en`, `label_lon`, `label_lat` |
| `state_lines` | `ne_10m_admin_1_states_provinces_lines` | USA, CAN, MEX; `featurecla == Admin-1 boundary` |
| `countries` | `ne_10m_admin_0_countries_lakes` | every country in the frame |
| `country_borders` | `ne_10m_admin_0_boundary_lines_land` | every border in the frame |
| `relief.png` | `SR_50M` (1:50m shaded relief) | cropped to the frame, rows resampled to Web Mercator, resized to 2048 px wide |

**Trade-offs that keep the basemap at 5.3 MB (vectors 4.4 MB, relief 0.9 MB):**
- **Detail.** The 0.005° simplification (~500 m) is invisible up to zoom 7. Coasts look slightly smoothed at zoom 8 and above.
- **Dropped features.** Small urban patches and minor lakes (`min_zoom` > 7) are dropped, and so are minor rivers (`min_zoom` > 6).
- **Roads.** Only Interstates are kept; US and state highways are dropped.
- **Cities.** 258 cities are kept, not Natural Earth's 1,244 in the frame.
- **Relief.** It is 1:50m (native ~3.7 km/px), downsampled to about 4.9 km/px, so it is soft at zoom 6–7. The 1:10m relief would be about 4× larger.
- **Ocean.** There is no ocean polygon: the ocean is the map background color, and `coastline` provides the shore stroke.
- **Not used.** This replaces the Protomaps PMTiles idea in the plan: there is no tile server, and nothing depends on OSM.

## Loading offline in MapLibre GL and deck.gl

`data/processed/` is gitignored. Copy the assets into the web app's static folder as a build step, for example `cp -r data/processed/geo web/public/geo`, or commit them under `results/` if the lead prefers.

Keep the AGPL notice with `ba_boundaries.geojson` wherever it is redistributed.

### 1. MapLibre style: local sources only, no glyphs, no sprite

```ts
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

const G = '/geo';  // served from web/public/geo by Vite; works from a static build with no network
const style: maplibregl.StyleSpecification = {
  version: 8,
  // No "glyphs" and no "sprite": with no symbol layers that draw text or icons,
  // MapLibre never fetches anything. Labels come from deck.gl TextLayer (below).
  sources: {
    landContext: { type: 'geojson', data: `${G}/basemap/land_context.geojson` },
    land:        { type: 'geojson', data: `${G}/basemap/land.geojson` },
    lakes:       { type: 'geojson', data: `${G}/basemap/lakes.geojson` },
    urban:       { type: 'geojson', data: `${G}/basemap/urban_areas.geojson` },
    rivers:      { type: 'geojson', data: `${G}/basemap/rivers.geojson` },
    roads:       { type: 'geojson', data: `${G}/basemap/roads.geojson` },
    stateLines:  { type: 'geojson', data: `${G}/basemap/state_lines.geojson` },
    borders:     { type: 'geojson', data: `${G}/basemap/country_borders.geojson` },
    coast:       { type: 'geojson', data: `${G}/basemap/coastline.geojson` },
    relief: {
      type: 'image', url: `${G}/basemap/relief.png`,
      // relief.json "maplibre_coordinates": TL, TR, BR, BL
      coordinates: [[-140, 62], [-50, 62], [-50, 14], [-140, 14]],
    },
  },
  layers: [
    { id: 'ocean', type: 'background', paint: { 'background-color': '#0b1420' } },
    { id: 'land-context', type: 'fill', source: 'landContext', paint: { 'fill-color': '#18222e' } },
    { id: 'land', type: 'fill', source: 'land', paint: { 'fill-color': '#18222e' } },
    { id: 'relief', type: 'raster', source: 'relief', paint: { 'raster-opacity': 0.18 } },
    { id: 'urban', type: 'fill', source: 'urban', paint: { 'fill-color': '#2a3646' } },
    { id: 'lakes', type: 'fill', source: 'lakes', paint: { 'fill-color': '#0b1420' } },
    { id: 'rivers-major', type: 'line', source: 'rivers', maxzoom: 5,
      filter: ['<=', ['get', 'min_zoom'], 4], paint: { 'line-color': '#1d3550', 'line-width': 0.8 } },
    { id: 'rivers', type: 'line', source: 'rivers', minzoom: 5,
      paint: { 'line-color': '#1d3550', 'line-width': 0.8 } },
    { id: 'roads', type: 'line', source: 'roads', minzoom: 5, paint: { 'line-color': '#2b3644', 'line-width': 0.6 } },
    { id: 'state-lines', type: 'line', source: 'stateLines', paint: { 'line-color': '#3a4757', 'line-width': 0.6 } },
    { id: 'borders', type: 'line', source: 'borders', paint: { 'line-color': '#5b6878', 'line-width': 1.2 } },
    { id: 'coast', type: 'line', source: 'coast', paint: { 'line-color': '#2c4a66', 'line-width': 0.8 } },
  ],
};

const map = new maplibregl.Map({
  container: 'map', style,
  center: [-98, 39], zoom: 3.6, pitch: 45, minZoom: 3, maxZoom: 7.5,
  maxBounds: [[-140, 14], [-50, 62]],   // the data frame
  attributionControl: { customAttribution:
    'BA boundaries © Electricity Maps contributors (AGPL-3.0) · BA codes: U.S. EIA-930 · Basemap: Natural Earth' },
});
```

For hover or selection styling in MapLibre itself, add the BA source with `promoteId: 'code'` and use `feature-state`.

### 2. deck.gl layers interleaved into MapLibre

```ts
import { MapboxOverlay } from '@deck.gl/mapbox';
import { GeoJsonLayer, ArcLayer, TextLayer } from '@deck.gl/layers';

const [bas, pts] = await Promise.all([
  fetch('/geo/ba_boundaries.geojson').then(r => r.json()),
  fetch('/geo/ba_points.geojson').then(r => r.json()),
]);
// One non-overlapping set: current data -> active; history before 2026-04 -> code !== 'SWPW'.
const current = { ...bas, features: bas.features.filter(f => f.properties.active) };
const P = Object.fromEntries(pts.features.map(f => [f.properties.code, f]));

const overlay = new MapboxOverlay({
  interleaved: true,
  layers: [
    new GeoJsonLayer({
      id: 'ba', data: current, extruded: true, wireframe: false, pickable: true,
      getElevation: f => 4e3 + 120e3 * (stress[f.properties.code] ?? 0),   // stress in [0, 1]
      getFillColor: f => colorFor(stress[f.properties.code]),
      getLineColor: [255, 255, 255, 60],
      updateTriggers: { getElevation: stressVersion, getFillColor: stressVersion },
      transitions: { getElevation: 600, getFillColor: 600 },
      material: { ambient: 0.5, diffuse: 0.6, shininess: 16 },
    }),
    new ArcLayer({
      id: 'moves', data: moves,   // [{from: 'PACE', to: 'CISO', mwh}]
      getSourcePosition: d => P[d.from].geometry.coordinates,
      getTargetPosition: d => P[d.to].geometry.coordinates,
      getWidth: d => 1 + Math.sqrt(d.mwh), getSourceColor: [0, 255, 200], getTargetColor: [255, 180, 0],
    }),
    new TextLayer({
      id: 'labels', data: pts.features.filter(f => f.properties.active),
      getPosition: f => [f.properties.label_lon, f.properties.label_lat],
      getText: f => f.properties.code,
      fontFamily: 'Inter, system-ui, sans-serif',   // self-host the font via @fontsource; no glyph server
      characterSet: 'auto', getSize: 12, getColor: [230, 238, 245],
      outlineWidth: 2, outlineColor: [11, 20, 32], fontSettings: { sdf: true },
    }),
  ],
});
map.addControl(overlay);
```

- **Labels.** deck.gl's TextLayer builds its glyph atlas on a canvas from a font the page already has. With the font self-hosted (`@fontsource/<font>` imported in the app), nothing is fetched.
  - City labels: `cities.geojson`, sorted by `rank` and filtered by `min_zoom`.
  - State labels: `states.geojson` `label_lon`/`label_lat`.
- **Relief in deck.gl** instead of MapLibre: `new BitmapLayer({ image: '/geo/basemap/relief.png', bounds: [-140, 14, -50, 62] })`.
  - The PNG's rows are already in Web Mercator, so the default image coordinate system is correct; do not set `_imageCoordinateSystem: LNGLAT`.
  - Blend it softly: `opacity: 0.15–0.25`, or `parameters` for multiply.
- **If MapLibre text labels are wanted after all**, self-host glyphs and add `glyphs: '/glyphs/{fontstack}/{range}.pbf'` to the style.
  - Generate the `.pbf` ranges once from the app's own TTF with MapLibre's font tooling, or unpack a released glyph archive (a data file).
  - Put them under `web/public/glyphs/<Font Name>/0-255.pbf` and so on, and use that exact font name in `text-font`.
  - Nothing else in this recipe needs glyphs.

## Reproduce

```sh
cd lab
uv run python -I scripts/recon_geo.py            # downloads only what is missing, then rebuilds everything
uv run python -I scripts/recon_geo.py download   # downloads + manifests only
```

- **Inputs.**
  - Downloads: Electricity Maps `world.geojson` and `LICENSE.md` at commit `501e61d`, and 13 Natural Earth zips.
  - Read from the EIA-930 recon: the reference table.
- **Outputs.** The rebuild is deterministic for the same inputs, except `built_at`.
- **Environment.** No package beyond `lab/pyproject.toml` is needed: shapely 2.2 on GEOS 3.14 supplies `coverage_clean`, `coverage_simplify` and `maximum_inscribed_circle`.
