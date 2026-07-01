"""Site estimator — hexagonal grid and omnidirectional cell layout."""
from __future__ import annotations
import math
from typing import Literal
from ..models.output_schema import SiteEstimateResult


def estimate_sites(
    area_km2: float,
    cell_radius_km: float,
    sectors: int = 3,
    overlap_factor: float = 0.25,
    limiting_link: str = "UL",
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

    # Cell area per site
    # 3-sector: hexagonal cell, each sector covers 120° → full 360° coverage
    # 1-sector omni: 360° coverage (omnidirectional antenna)
    # 6-sector: smaller cells, tighter frequency reuse
    if sectors == 3:
        # Hexagonal cell (3-sector)
        cell_area_km2 = 2.598 * cell_radius_km ** 2
    elif sectors == 1:
        # Omnidirectional (360° coverage)
        cell_area_km2 = math.pi * cell_radius_km ** 2
    elif sectors == 6:
        # 6-sector (rare)
        cell_area_km2 = 1.299 * cell_radius_km ** 2
    else:
        raise ValueError(f"Sectors must be 1, 3, or 6, got {sectors}")

    # Inter-site distance
    if sectors == 3:
        isd_km = math.sqrt(3) * cell_radius_km  # ISD = √3 × R for hexagonal
    elif sectors == 1:
        isd_km = 2.0 * cell_radius_km  # ISD = 2R for omni
    else:
        isd_km = 1.5 * cell_radius_km  # ISD = 1.5R for 6-sector

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