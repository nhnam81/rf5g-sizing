"""Capacity Dimensioning — Cell throughput, user capacity, demand vs supply.

3GPP TS 38.306 throughput formula with TDD support.
"""
from __future__ import annotations
import math
from ..models.input_schema import RFSizingInput
from ..models.lookup_tables import BandLookup, SINRCQILookup
from ..models.output_schema import CapacityResult
from .sinr_mapper import map_sinr_to_cqi, calculate_cell_throughput


def calculate_capacity(
    inp: RFSizingInput,
    sinr_db: float,
    coverage_sites: int,
    band_lookup: BandLookup | None = None,
    sinr_lookup: SINRCQILookup | None = None,
    area_km2: float | None = None,
) -> CapacityResult:
    """Calculate capacity dimensioning.

    Steps:
    1. Map SINR → CQI → SE
    2. Calculate cell throughput (DL + UL)
    3. Calculate total network capacity
    4. Calculate total user demand
    5. Determine if capacity is sufficient
    6. If not, calculate additional sites needed
    """
    if band_lookup is None:
        band_lookup = BandLookup()
    if sinr_lookup is None:
        sinr_lookup = SINRCQILookup()

    # Get parameters
    nrb = band_lookup.get_nrb(inp.frequency.bandwidth_mhz, inp.frequency.scs_khz)
    tdd_dl_ratio = inp.frequency.tdd_dl_ratio

    # Determine MIMO layers from antenna config
    layers = _get_layers(inp.base_station.antenna_config)

    # Map SINR to SE
    cqi_entry = map_sinr_to_cqi(sinr_db, sinr_lookup)
    se = cqi_entry["spectral_efficiency"]

    # Calculate cell throughput
    throughput = calculate_cell_throughput(
        nrb=nrb,
        scs_khz=inp.frequency.scs_khz,
        spectral_efficiency_bps_hz=se,
        layers=layers,
        overhead=0.15,
        tdd_dl_ratio=tdd_dl_ratio,
    )

    # Cell average throughput (cell edge SE * 0.7 for average over cell area)
    # Average SE ≈ cell_edge_SE × 1.5 (central users have better SINR)
    avg_se = se * 1.5
    avg_throughput = calculate_cell_throughput(
        nrb=nrb,
        scs_khz=inp.frequency.scs_khz,
        spectral_efficiency_bps_hz=avg_se,
        layers=layers,
        overhead=0.15,
        tdd_dl_ratio=tdd_dl_ratio,
    )

    cell_dl_mbps = avg_throughput["dl_mbps"]
    cell_ul_mbps = avg_throughput["ul_mbps"]

    # Total network capacity
    total_dl_gbps = cell_dl_mbps * coverage_sites / 1000.0
    total_ul_gbps = cell_ul_mbps * coverage_sites / 1000.0

    # User demand
    area = area_km2 if area_km2 is not None else inp.project.area_km2
    users_per_km2 = inp.qos.users_per_km2
    concurrent = inp.qos.concurrent_ratio
    total_users = int(users_per_km2 * area * concurrent)
    active_users_per_site = max(1, total_users // max(1, coverage_sites))

    dl_per_user = inp.qos.dl_per_user_mbps
    ul_per_user = inp.qos.ul_per_user_mbps

    # Total demand
    total_demand_dl_gbps = total_users * dl_per_user / 1000.0
    total_demand_ul_gbps = total_users * ul_per_user / 1000.0

    # Per-site demand
    demand_dl_per_site_mbps = active_users_per_site * dl_per_user
    demand_ul_per_site_mbps = active_users_per_site * ul_per_user

    # Capacity check
    capacity_sufficient_dl = cell_dl_mbps >= demand_dl_per_site_mbps
    capacity_sufficient_ul = cell_ul_mbps >= demand_ul_per_site_mbps
    capacity_sufficient = capacity_sufficient_dl and capacity_sufficient_ul

    # Additional sites needed if capacity limited
    if not capacity_sufficient:
        # Sites needed based on demand
        dl_sites_needed = math.ceil(total_demand_dl_gbps * 1000 / cell_dl_mbps) if cell_dl_mbps > 0 else coverage_sites * 2
        ul_sites_needed = math.ceil(total_demand_ul_gbps * 1000 / cell_ul_mbps) if cell_ul_mbps > 0 else coverage_sites * 2
        additional_sites = max(dl_sites_needed, ul_sites_needed) - coverage_sites
    else:
        additional_sites = 0

    return CapacityResult(
        cell_throughput_dl_mbps=round(cell_dl_mbps, 1),
        cell_throughput_ul_mbps=round(cell_ul_mbps, 1),
        total_sites=coverage_sites + additional_sites,
        total_capacity_dl_gbps=round(total_dl_gbps, 2),
        total_demand_dl_gbps=round(total_demand_dl_gbps, 2),
        capacity_sufficient=capacity_sufficient,
        additional_sites_needed=additional_sites,
    )


def _get_layers(antenna_config: str) -> int:
    """Map antenna config to MIMO layers."""
    config_map = {
        "2T2R": 2,
        "4T4R": 4,
        "8T8R": 4,
        "16T16R": 4,
        "32T32R": 4,
        "64T64R": 4,
        "128T128R": 4,
    }
    return config_map.get(antenna_config, 4)