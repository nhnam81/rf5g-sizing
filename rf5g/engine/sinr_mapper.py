"""SINR Mapper — SINR → CQI → MCS → Spectral Efficiency.

Maps SINR at cell edge to CQI, modulation, and spectral efficiency
using 3GPP TS 38.214 Table 5.2.2.1-2.
"""
from __future__ import annotations
from ..models.lookup_tables import SINRCQILookup


def map_sinr_to_cqi(sinr_db: float, lookup: SINRCQILookup | None = None) -> dict:
    """Map SINR to CQI entry using 3GPP TS 38.214 table.

    Uses linear interpolation between SINR thresholds for smooth mapping.

    Returns dict with: cqi, modulation, spectral_efficiency, code_rate_x1024,
    sinr_db, tbs_factor.
    """
    if lookup is None:
        lookup = SINRCQILookup()

    table = lookup._table
    # Find the CQI entry whose SINR threshold is <= our SINR
    best = table[0]
    for entry in table:
        if sinr_db >= entry["sinr_db"]:
            best = entry

    # Interpolate spectral efficiency between best and next
    idx = table.index(best)
    if idx < len(table) - 1 and sinr_db > best["sinr_db"]:
        next_entry = table[idx + 1]
        # Linear interpolation of SE
        sinr_range = next_entry["sinr_db"] - best["sinr_db"]
        if sinr_range > 0:
            frac = min(1.0, (sinr_db - best["sinr_db"]) / sinr_range)
            se = best["spectral_efficiency"] + frac * (next_entry["spectral_efficiency"] - best["spectral_efficiency"])
        else:
            se = best["spectral_efficiency"]
    else:
        se = best["spectral_efficiency"]

    return {
        "cqi": best["cqi"],
        "modulation": best["modulation"],
        "spectral_efficiency": se,
        "code_rate_x1024": best["code_rate_x1024"],
        "sinr_db": sinr_db,
        "tbs_factor": best["spectral_efficiency"],  # Nominal TBS factor from table
    }


def calculate_cell_throughput(
    nrb: int,
    scs_khz: int,
    spectral_efficiency_bps_hz: float,
    layers: int = 4,
    overhead: float = 0.15,
    tdd_dl_ratio: float = 0.70,
) -> dict:
    """Calculate cell throughput using 3GPP TS 38.306 formula.

    Throughput = N_RB × 12 × 14 × SCS_ratio × SE × layers × (1-OH) × TDD_share

    Args:
        nrb: Number of resource blocks
        scs_khz: Subcarrier spacing in kHz
        spectral_efficiency_bps_hz: SE from SINR→CQI mapping
        layers: MIMO layers (1, 2, or 4)
        overhead: Overhead ratio (control, reference signals, etc.)
        tdd_dl_ratio: TDD DL share (0.70 for DDDSU pattern)

    Returns:
        Dict with dl_mbps, ul_mbps, total_mbps
    """
    # Symbols per slot = 14
    # Subcarriers per RB = 12
    # Slots per ms depends on SCS
    slots_per_ms = scs_khz / 15  # SCS30 = 2 slots/ms, SCS15 = 1 slot/ms

    # Throughput per ms per layer
    # TBS ≈ N_RB × 12 subcarriers × 14 symbols × SE
    # Per second: × 1000 ms/s × slots_per_ms
    raw_bits_per_second = nrb * 12 * 14 * spectral_efficiency_bps_hz * slots_per_ms * 1000 * layers

    # Apply overhead and TDD ratio
    dl_mbps = raw_bits_per_second * (1 - overhead) * tdd_dl_ratio / 1e6
    ul_mbps = raw_bits_per_second * (1 - overhead) * (1 - tdd_dl_ratio) / 1e6

    return {
        "dl_mbps": round(dl_mbps, 1),
        "ul_mbps": round(ul_mbps, 1),
        "total_mbps": round(dl_mbps + ul_mbps, 1),
        "nrb": nrb,
        "scs_khz": scs_khz,
        "layers": layers,
        "overhead": overhead,
        "tdd_dl_ratio": tdd_dl_ratio,
        "spectral_efficiency_bps_hz": spectral_efficiency_bps_hz,
    }


def estimate_sinr_at_distance(
    sinr_cell_edge_db: float,
    cell_radius_m: float,
    distance_m: float,
) -> float:
    """Estimate SINR at a given distance from BS.

    Uses simplified path loss gradient: SINR improves closer to BS.
    SINR(d) ≈ SINR_edge + 10 × log10(cell_radius / d) for d < cell_radius.
    For d >= cell_radius, returns sinr_cell_edge_db.
    """
    if distance_m >= cell_radius_m:
        return sinr_cell_edge_db
    # Simplified: SINR improves as ~35*log10(R/d) for typical urban
    improvement = 35 * math.log10(cell_radius_m / max(distance_m, 1.0))
    return sinr_cell_edge_db + improvement


def coverage_percentage(
    sinr_cell_edge_db: float,
    sinr_threshold_db: float,
) -> float:
    """Estimate % of cell area where SINR >= threshold.

    Uses simplified model:
    - If SINR_edge >= threshold: nearly full coverage
    - If SINR_edge < threshold: inner area has higher SINR
    - Area% ≈ 100 × min(1, 0.5 + 0.5 × (SINR_edge - threshold + 10) / 20)

    More accurate: uses log-normal fading approximation.
    """
    delta = sinr_cell_edge_db - sinr_threshold_db
    if delta >= 10:
        return 100.0
    elif delta <= -10:
        return 0.0
    else:
        # Simplified sigmoid-like coverage model
        return round(max(0.0, min(100.0, 50.0 + 5.0 * delta)), 1)


import math