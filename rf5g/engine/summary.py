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