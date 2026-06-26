"""Site estimator — hexagonal grid and omnidirectional cell layout."""
from __future__ import annotations
import math
from ..models.antenna_pattern import AntennaPattern, derive_site_geometry_mode
from ..models.output_schema import SiteEstimateResult


def estimate_sites(
    area_km2: float,
    cell_radius_km: float,
    sectors: int = 3,
    overlap_factor: float = 0.25,
    limiting_link: str = "UL",
    antenna_pattern: AntennaPattern | None = None,
) -> SiteEstimateResult:
    """Estimate number of sites from area and cell radius.

    For 3-sector (hexagonal): Area_per_site = 2.598 * R^2
    For omni (circular): Area_per_site = pi * R^2

    Args:
        area_km2: Total coverage area in km²
        cell_radius_km: Cell radius in km (from propagation model)
        sectors: 1 (omni), 3 (tri-sectored), or 6 (hex-sectored)
        overlap_factor: Cell overlap factor (0.15 planned, 0.25 typical, 0.35 conservative)
        limiting_link: "DL" or "UL" — which link limits the cell radius

    Returns:
        SiteEstimateResult with site count, cell area, ISD
    """
    if cell_radius_km <= 0:
        raise ValueError("Cell radius must be positive")
    if area_km2 <= 0:
        raise ValueError("Area must be positive")

    if sectors not in {1, 3, 6}:
        raise ValueError(f"Sectors must be 1, 3, or 6, got {sectors}")

    pattern = antenna_pattern or AntennaPattern(name="fallback", pattern_type="omni", beamwidth_h_deg=360.0)
    geometry_mode = derive_site_geometry_mode(sectors, pattern)

    # Cell area per site
    # sector_3: classic 3-sector hexagonal macro assumptions
    # sector_6: denser multi-sector layout
    # directional_1_sector: reduced effective footprint vs omni because one beam only covers one angular slice
    if geometry_mode == "sector_3":
        cell_area_km2 = 2.598 * cell_radius_km ** 2
        isd_km = math.sqrt(3) * cell_radius_km
    elif geometry_mode == "sector_6":
        cell_area_km2 = 1.299 * cell_radius_km ** 2
        isd_km = 1.5 * cell_radius_km
    elif geometry_mode == "directional_1_sector":
        beam_fraction = max(0.12, min(0.5, pattern.beamwidth_h_deg / 360.0))
        cell_area_km2 = math.pi * cell_radius_km ** 2 * beam_fraction * 0.67
        isd_km = max(0.8 * cell_radius_km, 2.0 * cell_radius_km * max(0.35, math.sqrt(beam_fraction) * 0.85))
    else:
        cell_area_km2 = math.pi * cell_radius_km ** 2
        isd_km = 2.0 * cell_radius_km

    # Number of sites (with overlap)
    n_sites_raw = area_km2 / cell_area_km2
    n_sites = math.ceil(n_sites_raw * (1 + overlap_factor))

    return SiteEstimateResult(
        coverage_sites=n_sites,
        cell_radius_km=round(cell_radius_km, 4),
        cell_area_km2=round(cell_area_km2, 4),
        isd_km=round(isd_km, 4),
        limiting_link=limiting_link,
        overlap_factor=overlap_factor,
        sectors=sectors,
    )