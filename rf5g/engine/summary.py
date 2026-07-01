"""Executive summary generator — concise results for decision-making.

This module generates human-readable summaries of sizing results,
highlighting key metrics and recommended next actions.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from rf5g.models.output_schema import SizingOutput


@dataclass
class ExecutiveSummary:
    """Executive summary of sizing results."""
    limiting_factor: str  # "coverage" or "capacity"
    estimated_sites: int
    main_bottleneck: str
    cell_radius_m: float
    coverage_ratio: Optional[float] = None
    capacity_status: Optional[str] = None
    recommended_action: str = ""
    warnings_count: int = 0


def generate_executive_summary(result: "SizingOutput") -> ExecutiveSummary:
    """Generate an executive summary from sizing results.

    Args:
        result: SizingOutput from sizing calculation

    Returns:
        ExecutiveSummary with key decision-making information
    """
    # Determine limiting factor
    limiting_factor = "coverage"
    main_bottleneck = result.site_estimate.limiting_link

    # Check if capacity is the limiting factor
    if result.capacity:
        if not result.capacity.capacity_sufficient:
            limiting_factor = "capacity"
        elif result.capacity.total_sites > result.site_estimate.coverage_sites:
            limiting_factor = "capacity"

    # Estimated sites
    if result.capacity:
        estimated_sites = result.capacity.total_sites
    else:
        estimated_sites = result.site_estimate.coverage_sites

    # Capacity status
    capacity_status = None
    if result.capacity:
        if result.capacity.capacity_sufficient:
            capacity_status = "sufficient"
        else:
            capacity_status = f"need +{result.capacity.additional_sites_needed} sites"

    # Coverage ratio (for planning results)
    coverage_ratio = None
    if result.placement_plan:
        coverage_ratio = result.placement_plan.metrics.coverage_ratio

    # Warnings count
    warnings_count = len(result.warnings) if hasattr(result, 'warnings') and result.warnings else 0

    # Generate recommended action
    recommended_action = _generate_recommendation(
        result, limiting_factor, capacity_status, warnings_count
    )

    return ExecutiveSummary(
        limiting_factor=limiting_factor,
        estimated_sites=estimated_sites,
        main_bottleneck=main_bottleneck,
        cell_radius_m=result.propagation.cell_radius_m,
        coverage_ratio=coverage_ratio,
        capacity_status=capacity_status,
        recommended_action=recommended_action,
        warnings_count=warnings_count,
    )


def _generate_recommendation(
    result: "SizingOutput",
    limiting_factor: str,
    capacity_status: Optional[str],
    warnings_count: int,
) -> str:
    """Generate a recommended next action based on results."""
    recommendations = []

    # Based on limiting factor
    if limiting_factor == "capacity":
        if result.capacity and result.capacity.additional_sites_needed > 0:
            recommendations.append(
                f"Add {result.capacity.additional_sites_needed} more sites for capacity."
            )
        else:
            recommendations.append("Capacity drives site count, not coverage.")
    else:
        recommendations.append("Coverage drives site count.")

    # Based on limiting link
    if result.site_estimate.limiting_link == "UL":
        recommendations.append("Consider higher UE power class or UL CA for better UL performance.")

    # Based on SINR
    if result.sinr.sinr_db < 0:
        recommendations.append("Low SINR at cell edge — consider densification or antenna upgrades.")

    # Based on warnings
    if warnings_count > 0:
        recommendations.append(f"Review {warnings_count} warning(s) before proceeding.")

    # Based on planning
    if result.placement_plan:
        if result.placement_plan.metrics.coverage_ratio < 0.9:
            recommendations.append("Coverage ratio < 90% — consider adding more sites.")
        if result.placement_plan.spatial_capacity and result.placement_plan.spatial_capacity.overloaded_sites > 0:
            recommendations.append(
                f"{result.placement_plan.spatial_capacity.overloaded_sites} overloaded sites — consider load balancing."
            )

    # Default
    if not recommendations:
        recommendations.append("Results look reasonable. Proceed with detailed planning.")

    return " ".join(recommendations[:3])  # Limit to 3 recommendations


def format_summary_text(summary: ExecutiveSummary) -> str:
    """Format executive summary as plain text."""
    lines = [
        f"**Limiting Factor:** {summary.limiting_factor.upper()}",
        f"**Estimated Sites:** {summary.estimated_sites}",
        f"**Main Bottleneck:** {summary.main_bottleneck}",
        f"**Cell Radius:** {summary.cell_radius_m:.0f} m",
    ]

    if summary.coverage_ratio is not None:
        lines.append(f"**Coverage Ratio:** {summary.coverage_ratio:.1%}")

    if summary.capacity_status:
        lines.append(f"**Capacity:** {summary.capacity_status}")

    if summary.warnings_count > 0:
        lines.append(f"**Warnings:** {summary.warnings_count}")

    if summary.recommended_action:
        lines.append(f"**Next Action:** {summary.recommended_action}")

    return "\n".join(lines)


def format_summary_html(summary: ExecutiveSummary) -> str:
    """Format executive summary as HTML."""
    html = [
        '<div class="executive-summary" style="background: #f0f7ff; border-left: 4px solid #1976D2; padding: 15px; margin: 10px 0;">',
        '<h3 style="margin-top: 0; color: #1976D2;">📊 Executive Summary</h3>',
        '<table style="width: 100%; border-collapse: collapse;">',
    ]

    rows = [
        ("Limiting Factor", summary.limiting_factor.upper()),
        ("Estimated Sites", str(summary.estimated_sites)),
        ("Main Bottleneck", summary.main_bottleneck),
        ("Cell Radius", f"{summary.cell_radius_m:.0f} m"),
    ]

    if summary.coverage_ratio is not None:
        rows.append(("Coverage Ratio", f"{summary.coverage_ratio:.1%}"))

    if summary.capacity_status:
        rows.append(("Capacity", summary.capacity_status))

    if summary.warnings_count > 0:
        rows.append(("Warnings", str(summary.warnings_count)))

    for label, value in rows:
        html.append(f'<tr><td style="padding: 5px 10px; font-weight: bold;">{label}</td>')
        html.append(f'<td style="padding: 5px 10px;">{value}</td></tr>')

    html.append('</table>')

    if summary.recommended_action:
        html.append(f'<p style="margin-top: 10px; margin-bottom: 0;"><strong>Next Action:</strong> {summary.recommended_action}</p>')

    html.append('</div>')

    return "".join(html)


# ─────────────────────────────────────────────────────────────────────────────
# Planning Scorecard
# ─────────────────────────────────────────────────────────────────────────────

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rf5g.models.output_schema import PlacementPlanResult


@dataclass
class PlanningScorecard:
    """Planning scorecard with standard metrics for plan comparison."""
    # Coverage metrics
    service_area_km2: float
    covered_area_km2: float
    coverage_ratio: float

    # Site metrics
    total_sites: int
    locked_sites: int
    auto_selected_sites: int
    candidate_sites: int
    rejected_candidates: int

    # Exclusion metrics
    excluded_area_km2: float
    alignment_length_km: float

    # Capacity metrics (if available)
    demand_dl_gbps: float | None
    served_dl_gbps: float | None
    unserved_dl_gbps: float | None
    demand_ul_gbps: float | None
    served_ul_gbps: float | None
    unserved_ul_gbps: float | None
    hotspot_tiles: int | None
    overloaded_sites: int | None

    # Quality indicators
    capacity_sufficient: bool | None
    coverage_quality: str  # "excellent", "good", "fair", "poor"

    # Recommendations
    recommendations: list[str]


def generate_planning_scorecard(result: "SizingOutput") -> PlanningScorecard:
    """Generate a planning scorecard from sizing results.

    Args:
        result: SizingOutput from sizing calculation

    Returns:
        PlanningScorecard with metrics for plan evaluation
    """
    plan = result.placement_plan
    if not plan:
        raise ValueError("No placement plan in result")

    # Basic coverage metrics
    service_area_km2 = plan.metrics.service_area_km2
    covered_area_km2 = plan.metrics.covered_area_km2
    coverage_ratio = plan.metrics.coverage_ratio

    # Site metrics
    total_sites = plan.metrics.selected_sites
    locked_sites = plan.metrics.locked_sites
    auto_selected_sites = total_sites - locked_sites
    candidate_sites = plan.metrics.candidate_sites
    rejected_candidates = plan.metrics.rejected_candidates

    # Exclusion metrics
    excluded_area_km2 = plan.metrics.excluded_area_km2
    alignment_length_km = plan.metrics.alignment_length_km

    # Capacity metrics (if available)
    demand_dl_gbps = None
    served_dl_gbps = None
    unserved_dl_gbps = None
    demand_ul_gbps = None
    served_ul_gbps = None
    unserved_ul_gbps = None
    hotspot_tiles = None
    overloaded_sites = None
    capacity_sufficient = None

    if plan.spatial_capacity:
        sc = plan.spatial_capacity
        demand_dl_gbps = sc.demand_dl_gbps
        served_dl_gbps = sc.served_dl_gbps
        unserved_dl_gbps = sc.unserved_dl_gbps
        demand_ul_gbps = sc.demand_ul_gbps
        served_ul_gbps = sc.served_ul_gbps
        unserved_ul_gbps = sc.unserved_ul_gbps
        hotspot_tiles = sc.hotspot_tiles
        overloaded_sites = sc.overloaded_sites
        capacity_sufficient = sc.capacity_sufficient_spatial

    # Coverage quality assessment
    if coverage_ratio >= 0.95:
        coverage_quality = "excellent"
    elif coverage_ratio >= 0.85:
        coverage_quality = "good"
    elif coverage_ratio >= 0.70:
        coverage_quality = "fair"
    else:
        coverage_quality = "poor"

    # Generate recommendations
    recommendations = []

    if coverage_ratio < 0.85:
        recommendations.append(
            f"Coverage ratio ({coverage_ratio:.1%}) is below target. Consider adding more sites or reducing exclusion zones."
        )

    if overloaded_sites and overloaded_sites > 0:
        recommendations.append(
            f"{overloaded_sites} sites are overloaded. Consider capacity optimization or additional sites in high-demand areas."
        )

    if unserved_dl_gbps and unserved_dl_gbps > 0.1 * (demand_dl_gbps or 1):
        recommendations.append(
            f"Significant unserved DL demand ({unserved_dl_gbps:.2f} Gbps). Review traffic zone distribution."
        )

    if rejected_candidates > total_sites * 2:
        recommendations.append(
            f"High rejection count ({rejected_candidates}). Review site spacing and exclusion constraints."
        )

    if coverage_quality == "excellent" and (not overloaded_sites or overloaded_sites == 0):
        recommendations.append(
            "Plan achieves good coverage with no overloaded sites. Ready for detailed planning."
        )

    return PlanningScorecard(
        service_area_km2=service_area_km2,
        covered_area_km2=covered_area_km2,
        coverage_ratio=coverage_ratio,
        total_sites=total_sites,
        locked_sites=locked_sites,
        auto_selected_sites=auto_selected_sites,
        candidate_sites=candidate_sites,
        rejected_candidates=rejected_candidates,
        excluded_area_km2=excluded_area_km2,
        alignment_length_km=alignment_length_km,
        demand_dl_gbps=demand_dl_gbps,
        served_dl_gbps=served_dl_gbps,
        unserved_dl_gbps=unserved_dl_gbps,
        demand_ul_gbps=demand_ul_gbps,
        served_ul_gbps=served_ul_gbps,
        unserved_ul_gbps=unserved_ul_gbps,
        hotspot_tiles=hotspot_tiles,
        overloaded_sites=overloaded_sites,
        capacity_sufficient=capacity_sufficient,
        coverage_quality=coverage_quality,
        recommendations=recommendations,
    )


def format_scorecard_text(scorecard: PlanningScorecard) -> str:
    """Format planning scorecard as plain text."""
    lines = [
        f"**Coverage Quality:** {scorecard.coverage_quality.upper()}",
        f"**Service Area:** {scorecard.service_area_km2:.2f} km²",
        f"**Covered Area:** {scorecard.covered_area_km2:.2f} km² ({scorecard.coverage_ratio:.1%})",
        "",
        f"**Sites:**",
        f"  - Total: {scorecard.total_sites}",
        f"  - Locked/Existing: {scorecard.locked_sites}",
        f"  - Auto-selected: {scorecard.auto_selected_sites}",
    ]

    if scorecard.alignment_length_km > 0:
        lines.append(f"  - Alignment length: {scorecard.alignment_length_km:.2f} km")

    if scorecard.excluded_area_km2 > 0:
        lines.append(f"  - Excluded area: {scorecard.excluded_area_km2:.2f} km²")

    if scorecard.demand_dl_gbps is not None:
        lines.extend([
            "",
            f"**Capacity:**",
            f"  - DL Demand: {scorecard.demand_dl_gbps:.2f} Gbps",
            f"  - DL Served: {scorecard.served_dl_gbps:.2f} Gbps",
            f"  - DL Unserved: {scorecard.unserved_dl_gbps:.2f} Gbps",
        ])
        if scorecard.hotspot_tiles is not None:
            lines.append(f"  - Hotspot tiles: {scorecard.hotspot_tiles}")
        if scorecard.overloaded_sites is not None:
            lines.append(f"  - Overloaded sites: {scorecard.overloaded_sites}")

    if scorecard.recommendations:
        lines.extend([
            "",
            f"**Recommendations:**",
        ])
        for rec in scorecard.recommendations:
            lines.append(f"  - {rec}")

    return "\n".join(lines)


def format_scorecard_html(scorecard: PlanningScorecard) -> str:
    """Format planning scorecard as HTML table."""
    # Determine quality color
    quality_color = {
        "excellent": "#4CAF50",
        "good": "#8BC34A",
        "fair": "#FF9800",
        "poor": "#F44336",
    }.get(scorecard.coverage_quality, "#9E9E9E")

    html = [
        '<div class="planning-scorecard" style="background: white; border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin: 10px 0;">',
        '<h3 style="margin-top: 0; color: #1976D2;">📊 Planning Scorecard</h3>',
        '',
        '<div style="display: flex; flex-wrap: wrap; gap: 20px;">',
        '',
        # Coverage section
        '<div style="flex: 1; min-width: 200px;">',
        '<h4 style="margin: 0 0 10px 0; border-bottom: 1px solid #eee; padding-bottom: 5px;">Coverage</h4>',
        f'<p style="font-size: 32px; font-weight: bold; margin: 0; color: {quality_color};">{scorecard.coverage_ratio:.1%}</p>',
        f'<p style="color: #666; margin: 5px 0;">{scorecard.coverage_quality.upper()}</p>',
        f'<p style="color: #666; margin: 5px 0;">{scorecard.covered_area_km2:.2f} / {scorecard.service_area_km2:.2f} km²</p>',
        '</div>',
        '',
        # Sites section
        '<div style="flex: 1; min-width: 200px;">',
        '<h4 style="margin: 0 0 10px 0; border-bottom: 1px solid #eee; padding-bottom: 5px;">Sites</h4>',
        f'<p style="font-size: 32px; font-weight: bold; margin: 0; color: #1976D2;">{scorecard.total_sites}</p>',
        f'<p style="color: #666; margin: 5px 0;">Locked: {scorecard.locked_sites} | Auto: {scorecard.auto_selected_sites}</p>',
    ]

    if scorecard.alignment_length_km > 0:
        html.append(f'<p style="color: #666; margin: 5px 0;">Alignment: {scorecard.alignment_length_km:.2f} km</p>')

    html.append('</div>')

    # Capacity section (if available)
    if scorecard.demand_dl_gbps is not None:
        html.extend([
            '<div style="flex: 1; min-width: 200px;">',
            '<h4 style="margin: 0 0 10px 0; border-bottom: 1px solid #eee; padding-bottom: 5px;">Capacity</h4>',
            f'<p style="color: #666; margin: 5px 0;">DL Demand: {scorecard.demand_dl_gbps:.2f} Gbps</p>',
            f'<p style="color: #666; margin: 5px 0;">DL Unserved: {scorecard.unserved_dl_gbps:.2f} Gbps</p>',
        ])
        if scorecard.overloaded_sites is not None:
            overload_color = "#F44336" if scorecard.overloaded_sites > 0 else "#4CAF50"
            html.append(f'<p style="color: {overload_color}; margin: 5px 0;">Overloaded: {scorecard.overloaded_sites}</p>')
        html.append('</div>')

    html.append('</div>')  # End flex container

    # Recommendations
    if scorecard.recommendations:
        html.extend([
            '<div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #eee;">',
            '<h4 style="margin: 0 0 10px 0;">Recommendations</h4>',
            '<ul style="margin: 0; padding-left: 20px;">',
        ])
        for rec in scorecard.recommendations:
            html.append(f'<li style="margin: 5px 0;">{rec}</li>')
        html.extend([
            '</ul>',
            '</div>',
        ])

    html.append('</div>')  # End scorecard div

    return "".join(html)