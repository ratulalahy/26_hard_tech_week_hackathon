"""Water factors for the illustrative water footprint (Stage 3 T14, D-063). Transcribed by hand
from the two source PDFs in `data/raw/water/` (recorded in `data/manifests/water.json`); every value
names its table or page. `tests/test_water_factors.py` pins them.

**Generation factors.** NREL/TP-6A20-50900: J. Macknick, R. Newmark, G. Heath and K.C. Hallett,
*A Review of Operational Water Consumption and Withdrawal Factors for Electricity Generating
Technologies*, NREL, March 2011. Table 1 (renewables, printed page 12, PDF page 19) and Table 2
(non-renewables, printed page 13, PDF page 20), "Water Consumption Factors ... (gal/MWh)". We use the
**median operational consumption** (not withdrawal, Table 3). Factors are technology medians from
the literature, irrespective of location: plant-level cooling is not modelled.

**Fuel → technology** (EIA-930 fuel categories; `assumed`, one reason each in `FUEL_MAP`):
recirculating (cooling-tower) technology for the thermal fuels, the aggregated in-stream and
reservoir factor for conventional hydro (shown separately, because the allocation of reservoir
evaporation to power is uncertain and can dominate), utility-scale PV for solar, ~0 for wind and
storage, and "other"/"unknown" left out of the shares (they take the hour's mix-average intensity).

**Direct (on-site) cooling water.** LBNL-2001637: A. Shehabi et al., *2024 United States Data
Center Energy Usage Report*, LBNL, December 2024. Site WUE in litres per IT kWh, from the text
of p. 48 (Figure 4.7): the U.S. average "stays just over 0.36 L/kWh through 2023", and "after 2023
... reaching between 0.45 and 0.48 L/kWh" (the 2028 scenario). We use 0.36–0.48 L/kWh as the range
(an `assumed` choice of two published endpoints; the 0.48 end is a published 2028 *scenario*,
so it is labelled `assumed (published scenario)`, the 0.36 end `observed`); the report's own figures are national averages
of simulated facilities, not a measurement of any site.
"""

from __future__ import annotations

from dataclasses import dataclass

L_PER_GAL = 3.785411784  # US liquid gallon (exact)
GAL_PER_ACRE_FOOT = 325851.4290  # 43,560 ft³ × 7.48051948 gal/ft³


@dataclass(frozen=True)
class Source:
    key: str
    citation: str
    url: str
    path: str  # data-dir-relative, as in data/manifests/water.json
    sha256: str


SOURCES = {
    "nrel": Source(
        "nrel",
        "Macknick, J., Newmark, R., Heath, G., Hallett, K.C. (2011). A Review of Operational Water "
        "Consumption and Withdrawal Factors for Electricity Generating Technologies. NREL/TP-6A20-50900.",
        "https://docs.nlr.gov/docs/fy11osti/50900.pdf",
        "raw/water/NREL-TP-6A20-50900.pdf",
        "dd1492c5a6b811d037ece63af4c74058aaaec69b04fcb1b4bcb70263ff95b3ca"),
    "lbnl": Source(
        "lbnl",
        "Shehabi, A., Smith, S.J., Hubbard, A., Newkirk, A., Lei, N., Siddik, M.A.B., Holecek, B., "
        "Koomey, J., Masanet, E., Sartor, D. (2024). 2024 United States Data Center Energy Usage "
        "Report. LBNL-2001637. doi:10.71468/P1WC7Q",
        "https://eta-publications.lbl.gov/sites/default/files/2024-12/"
        "lbnl-2024-united-states-data-center-energy-usage-report_1.pdf",
        "raw/water/LBNL-2001637.pdf",
        "3a2257cdf4c350356062ffd8f75e886f099b13781b0a37af5605d65d5e46c2eb"),
}


@dataclass(frozen=True)
class Factor:
    """One NREL table row: median operational water consumption, with its min, max and n."""
    table: str
    page: int  # printed page number
    fuel_type: str
    cooling: str
    technology: str
    median: float
    min: float
    max: float
    n: int
    unit: str = "gal/MWh"
    metric: str = "consumption"
    source: str = "nrel"


_T1, _T2 = ("Table 1", 12), ("Table 2", 13)
NREL_FACTORS: dict[str, Factor] = {
    # Table 2. Water Consumption Factors for Non-renewable Technologies (gal/MWh), printed p. 13
    "coal_tower_generic": Factor(*_T2, "Coal", "Tower", "Generic", 687, 480, 1100, 5),
    "gas_tower_cc": Factor(*_T2, "Natural Gas", "Tower", "Combined Cycle", 198, 130, 300, 5),
    "gas_tower_steam": Factor(*_T2, "Natural Gas", "Tower", "Steam", 826, 662, 1170, 4),
    "nuclear_tower": Factor(*_T2, "Nuclear", "Tower", "Generic", 672, 581, 845, 6),
    # Table 1. Water Consumption Factors for Renewable Technologies (gal/MWh), printed p. 12
    "hydro": Factor(*_T1, "Hydropower", "N/A", "Aggregated in-stream and reservoir",
                    4491, 1425, 18000, 3),
    "pv": Factor(*_T1, "PV", "N/A", "Utility Scale PV", 26, 0, 33, 3),
    "wind": Factor(*_T1, "Wind", "N/A", "Wind Turbine", 0, 0, 1, 2),
    "geo_dry_binary": Factor(*_T1, "Geothermal", "Dry", "Binary", 135, 0, 270, 2),
}


@dataclass(frozen=True)
class FuelMap:
    """How an EIA-930 fuel is weighted. role: factor (an NREL median), hydro (the hydro factor,
    reported separately), zero (counted in the generation, no water), mix_average (left out of
    the shares, so it takes the hour's average intensity of the rest)."""
    role: str
    factor: str | None
    reason: str
    evidence: str = "assumed"


FUEL_MAP: dict[str, FuelMap] = {
    "coal": FuelMap("factor", "coal_tower_generic",
                    "recirculating (cooling tower) steam; NREL coal tower, generic"),
    "gas": FuelMap("factor", "gas_tower_cc",
                   "combined cycle with a cooling tower (recirculating); peakers and steam units "
                   "are not separated in EIA-930"),
    "oil": FuelMap("factor", "gas_tower_steam",
                   "no oil row in NREL; proxied by a recirculating steam unit (gas, tower, steam)"),
    "nuclear": FuelMap("factor", "nuclear_tower", "recirculating (cooling tower), generic"),
    "hydro_conv": FuelMap("hydro", "hydro",
                          "aggregated in-stream and reservoir evaporation, all allocated to power; "
                          "reported separately because the allocation is uncertain"),
    "pumped_storage": FuelMap("zero", None,
                              "storage: time-shifted energy, its charging generation is already "
                              "counted where it was generated"),
    "solar": FuelMap("factor", "pv", "utility-scale PV (panel washing); CSP not separated"),
    "solar_batt": FuelMap("factor", "pv", "PV with integrated storage, as utility-scale PV"),
    "wind": FuelMap("factor", "wind", "wind turbine, about zero"),
    "wind_batt": FuelMap("factor", "wind", "wind with integrated storage, as wind"),
    "geothermal": FuelMap("factor", "geo_dry_binary",
                          "dry-cooled binary, the common western type; geothermal fluid use is "
                          "not freshwater (none reported separately in the four core BAs)"),
    "battery": FuelMap("zero", None, "storage discharge: no operational water of its own"),
    "other_storage": FuelMap("zero", None, "storage discharge: no operational water of its own"),
    "unknown_storage": FuelMap("zero", None, "storage discharge: no operational water of its own"),
    "other": FuelMap("mix_average", None,
                     "mixed category (biomass, geothermal, storage, ...): left out of the shares, "
                     "so it takes the hour's average intensity of the known fuels"),
    "unknown": FuelMap("mix_average", None,
                       "unknown fuel: left out of the shares (the hour's average intensity)"),
}


def fuel_factors_gal_mwh() -> dict[str, float]:
    """gal/MWh per fuel that enters the shares (zero-water fuels give 0; mix-average fuels are
    absent)."""
    out = {}
    for fuel, m in FUEL_MAP.items():
        if m.role in ("factor", "hydro"):
            out[fuel] = float(NREL_FACTORS[m.factor].median)
        elif m.role == "zero":
            out[fuel] = 0.0
    return out


@dataclass(frozen=True)
class Published:
    value: float
    unit: str
    page: int
    quote: str
    source: str = "lbnl"


WUE_L_PER_KWH = {
    "low": Published(0.36, "L/kWh (IT)", 48,
                     "the overall average WUE, which stays just over 0.36 L/kWh through 2023 "
                     "(Figure 4.7, annual average site WUE across all U.S. data centers)"),
    "high": Published(0.48, "L/kWh (IT)", 48,
                      "After 2023, the average WUE rises slightly, reaching between 0.45 and 0.48 "
                      "L/kWh (Figure 4.7; the 2028 scenario range, upper end)"),
}
# Context only (a different method: consumption-flow, plant-level EIA data; Siddik et al. 2024).
LBNL_US_GRID_L_PER_KWH = Published(
    4.35, "L/kWh", 57,
    "the average water intensity factor for electricity use in the U.S. overall is 4.35 L/kWh")
LBNL_DC_GRID_L_PER_KWH = Published(
    4.52, "L/kWh", 57,
    "energy consumption by a data center translates to national average of 4.52 L/kWh of "
    "indirect water consumption")
