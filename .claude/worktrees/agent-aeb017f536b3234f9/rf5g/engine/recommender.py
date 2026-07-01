"""Recommendation Engine — Rule-based recommendations for RF sizing results."""
from __future__ import annotations
from ..models.output_schema import SizingOutput


def generate_recommendations(result: SizingOutput) -> list[str]:
    """Generate rule-based recommendations based on sizing results.

    Rules from PRD FR-07:
    - UL limiting & UE PC3 → upgrade to PC2
    - Shadow fading > 12 dB → heavy clutter warning
    - Cell radius < 200m → small cell deployment
    - Cell radius > 5km → verify RMa model
    - ISD < 500m → ultra-dense, ICIC recommended
    - Capacity insufficient → add carrier/increase BW/deploy small cells
    - SINR too low for VoNR → increase TX/upgrade antenna/add sites
    """
    recs = []

    # UL limiting
    if result.site_estimate.limiting_link == "UL":
        dl_mapl = result.link_budget_dl.mapl_db
        ul_mapl = result.link_budget_ul.mapl_db
        gap = dl_mapl - ul_mapl
        recs.append(f"UL is limiting (MAPL={ul_mapl:.1f} dB vs DL={dl_mapl:.1f} dB, gap={gap:.1f} dB)")

        # Check UE power class
        if gap > 5:
            recs.append("Consider upgrading UE to Power Class 2 (+3 dB UL improvement)")
        if gap > 15:
            recs.append("Significant UL-DL imbalance. Consider UL CA or higher UE power class")

    # Cell radius recommendations
    radius_km = result.propagation.cell_radius_km
    if radius_km < 0.2:
        recs.append("Very small cell radius (<200m) — consider small cell deployment (4T4R/2T2R)")
    elif radius_km < 0.5:
        recs.append("Dense urban cell radius — consider 8T8R or 16T16R for capacity")
    elif radius_km > 5.0:
        recs.append("Large cell radius (>5km) — verify RMa model, terrain may limit coverage")
    elif radius_km > 2.0:
        recs.append("Suburban/rural cell radius — consider antenna downtilt optimization")

    # ISD recommendations
    isd_km = result.site_estimate.isd_km
    if isd_km < 0.5:
        recs.append("Ultra-dense ISD (<500m) — ICIC/eICIC recommended for interference management")
    elif isd_km > 10:
        recs.append("Very large ISD (>10km) — verify backhaul and timing advance limits")

    # SINR recommendations
    sinr = result.sinr.sinr_db
    if sinr < -5:
        recs.append(f"Very low SINR ({sinr:.1f} dB) — no reliable service at cell edge. Increase TX power or add sites")
    elif sinr < -3:
        recs.append(f"Low SINR ({sinr:.1f} dB) — VoNR may not be supported at cell edge")
    elif sinr < 0:
        recs.append(f"Marginal SINR ({sinr:.1f} dB) — basic data service only at cell edge")

    # Shadow fading
    sf = result.link_budget_dl.shadow_fading_margin_db
    if sf > 12:
        recs.append(f"Heavy shadow fading ({sf:.1f} dB) — consider more sites or lower reliability target")
    elif sf > 8:
        recs.append(f"Moderate shadow fading ({sf:.1f} dB) — typical for dense urban indoor coverage")

    # Capacity
    if result.capacity and not result.capacity.capacity_sufficient:
        recs.append(
            f"Capacity insufficient: {result.capacity.total_demand_dl_gbps:.1f} Gbps demand "
            f"vs {result.capacity.total_capacity_dl_gbps:.1f} Gbps supply — "
            f"add {result.capacity.additional_sites_needed} sites or increase BW"
        )
        recs.append("Consider: add carrier, increase BW, deploy small cells, or offload to Wi-Fi")

    # QoS failures
    failed_services = [q for q in result.qos_verification if not q.passed]
    if failed_services:
        svc_names = ", ".join(q.service for q in failed_services)
        recs.append(f"QoS failed for: {svc_names}. Consider antenna upgrades or additional sites")

    # Band-specific recommendations
    if result.band in ("n78", "n41", "n77"):
        if result.bandwidth_mhz >= 100:
            recs.append(f"Using {result.bandwidth_mhz:.0f} MHz bandwidth — good for capacity, verify spectrum availability")
    if result.band in ("n8", "n5", "n28"):
        recs.append(f"Low band ({result.band}) — excellent coverage but limited capacity. Consider carrier aggregation with mid-band")

    # Antenna config
    if result.antenna_config in ("2T2R", "4T4R") and radius_km < 0.5:
        recs.append(f"Consider upgrading to 8T8R or higher for better beamforming in dense deployment")
    if result.antenna_config in ("64T64R", "128T128R") and radius_km > 2:
        recs.append(f"Massive MIMO ({result.antenna_config}) in rural/suburban — consider 16T16R for cost efficiency")

    return recs