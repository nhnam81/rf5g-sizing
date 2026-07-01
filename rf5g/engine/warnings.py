"""Scenario validity warnings — detect and report weak-confidence or suspicious inputs.

This module provides warnings for scenarios where:
- Parameters push the tool beyond comfortable planning bounds
- Approximations may be less reliable
- Unusual combinations deserve caution

Usage:
    from rf5g.engine.warnings import generate_warnings
    warnings = generate_warnings(input_config, result)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rf5g.models.input_schema import RFSizingInput
    from rf5g.models.output_schema import SizingOutput


@dataclass
class ScenarioWarning:
    """A single warning about scenario validity."""
    code: str  # e.g., "W001"
    severity: str  # "info", "warning", "critical"
    category: str  # "propagation", "throughput", "capacity", "planning", "equipment"
    message: str
    detail: str = ""
    recommendation: str = ""


@dataclass
class WarningResult:
    """Collection of warnings for a scenario."""
    warnings: list[ScenarioWarning] = field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    @property
    def has_critical(self) -> bool:
        return any(w.severity == "critical" for w in self.warnings)

    @property
    def critical_count(self) -> int:
        return sum(1 for w in self.warnings if w.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for w in self.warnings if w.severity == "warning")

    @property
    def info_count(self) -> int:
        return sum(1 for w in self.warnings if w.severity == "info")


def generate_warnings(inp: "RFSizingInput", result: "SizingOutput") -> WarningResult:
    """Generate warnings for a sizing scenario.

    Args:
        inp: Input configuration
        result: Sizing output result

    Returns:
        WarningResult with list of warnings
    """
    warnings = WarningResult()

    # Propagation warnings
    _check_propagation(inp, result, warnings)

    # Throughput warnings
    _check_throughput(inp, result, warnings)

    # Capacity warnings
    _check_capacity(inp, result, warnings)

    # Equipment warnings
    _check_equipment(inp, result, warnings)

    # Planning warnings
    _check_planning(inp, result, warnings)

    # Sort by severity (critical first, then warning, then info)
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    warnings.warnings.sort(key=lambda w: severity_order.get(w.severity, 3))

    return warnings


def _add_warning(warnings: WarningResult, code: str, severity: str, category: str,
                 message: str, detail: str = "", recommendation: str = ""):
    """Helper to add a warning."""
    warnings.warnings.append(ScenarioWarning(
        code=code,
        severity=severity,
        category=category,
        message=message,
        detail=detail,
        recommendation=recommendation,
    ))


def _check_propagation(inp: "RFSizingInput", result: "SizingOutput", warnings: WarningResult):
    """Check propagation-related warnings."""

    # Very small cell radius (may indicate unrealistic assumptions)
    if result.propagation.cell_radius_km < 0.05:  # < 50m
        _add_warning(
            warnings,
            code="W001",
            severity="warning",
            category="propagation",
            message="Very small cell radius detected",
            detail=f"Cell radius is {result.propagation.cell_radius_m:.0f}m, which is unusually small for macrocell planning.",
            recommendation="Check penetration loss and MAPL assumptions. Consider small cell / indoor planning instead."
        )

    # Very large cell radius (may indicate unreliable coverage)
    if result.propagation.cell_radius_km > 15:  # > 15km
        _add_warning(
            warnings,
            code="W002",
            severity="warning",
            category="propagation",
            message="Very large cell radius detected",
            detail=f"Cell radius is {result.propagation.cell_radius_km:.1f}km, which may indicate optimistic assumptions.",
            recommendation="Verify LOS assumptions and terrain conditions. Coverage reliability may be lower than predicted."
        )

    # Low LOS probability with LOS path type
    if result.propagation.los_probability and result.propagation.los_probability < 0.3:
        path_type = result.propagation.model.split("_")[-1] if "_" in result.propagation.model else "unknown"
        if path_type == "LOS":
            _add_warning(
                warnings,
                code="W003",
                severity="warning",
                category="propagation",
                message="LOS path type assumed but LOS probability is low",
                detail=f"LOS probability is {result.propagation.los_probability:.1%} but LOS path type is selected.",
                recommendation="Consider using 'combined' or 'NLOS' path type for more realistic planning."
            )


def _check_throughput(inp: "RFSizingInput", result: "SizingOutput", warnings: WarningResult):
    """Check throughput-related warnings."""

    duplex = inp.frequency.duplex
    tdd_ratio = inp.frequency.tdd_dl_ratio

    # FDD throughput approximation
    if duplex == "FDD":
        _add_warning(
            warnings,
            code="W010",
            severity="info",
            category="throughput",
            message="FDD throughput is approximated",
            detail="FDD throughput calculation uses simplified approximation without HARQ modeling.",
            recommendation="Results are suitable for planning-level estimates. For detailed capacity planning, use a full simulator."
        )

    # Extreme TDD ratio
    if duplex == "TDD" and (tdd_ratio < 0.3 or tdd_ratio > 0.9):
        _add_warning(
            warnings,
            code="W011",
            severity="warning",
            category="throughput",
            message="Extreme TDD DL ratio may cause UL issues",
            detail=f"TDD DL ratio is {tdd_ratio:.0%}, which leaves only {(1-tdd_ratio):.0%} for UL.",
            recommendation="Verify UL capacity is sufficient. Consider more balanced TDD ratio for symmetric traffic."
        )

    # Very low SINR
    if result.sinr.sinr_db < -5:
        _add_warning(
            warnings,
            code="W012",
            severity="warning",
            category="throughput",
            message="Very low cell-edge SINR",
            detail=f"Cell-edge SINR is {result.sinr.sinr_db:.1f} dB, which may result in poor user experience.",
            recommendation="Consider site densification, improved antenna configuration, or reduced coverage area per site."
        )

    # Low spectral efficiency
    if result.sinr.spectral_efficiency_bps_hz < 0.5:
        _add_warning(
            warnings,
            code="W013",
            severity="info",
            category="throughput",
            message="Low spectral efficiency at cell edge",
            detail=f"Spectral efficiency is {result.sinr.spectral_efficiency_bps_hz:.2f} bps/Hz (CQI {result.sinr.cqi}).",
            recommendation="Cell edge users will experience significantly lower throughput than cell center users."
        )


def _check_capacity(inp: "RFSizingInput", result: "SizingOutput", warnings: WarningResult):
    """Check capacity-related warnings."""

    if not result.capacity:
        return

    # Capacity insufficient
    if not result.capacity.capacity_sufficient:
        _add_warning(
            warnings,
            code="W020",
            severity="warning",
            category="capacity",
            message="Capacity insufficient for demand",
            detail=f"Total DL capacity: {result.capacity.total_capacity_dl_gbps:.2f} Gbps, Demand: {result.capacity.total_demand_dl_gbps:.2f} Gbps",
            recommendation=f"Additional {result.capacity.additional_sites_needed} sites needed for capacity. Consider increasing sites or reducing demand assumptions."
        )

    # High site count
    if result.capacity.total_sites > 500:
        _add_warning(
            warnings,
            code="W021",
            severity="info",
            category="capacity",
            message="Very high site count",
            detail=f"Total sites: {result.capacity.total_sites}. This may indicate a large deployment or inefficient configuration.",
            recommendation="Verify coverage area and demand assumptions. Consider sectorization or higher-order MIMO for capacity."
        )

    # High users per site
    if inp.qos and inp.qos.users_per_km2 > 0:
        users_per_site = inp.qos.users_per_km2 * inp.project.area_km2 / max(1, result.capacity.total_sites)
        if users_per_site > 1000:
            _add_warning(
                warnings,
                code="W022",
                severity="info",
                category="capacity",
                message="High users per site",
                detail=f"Estimated {users_per_site:.0f} users per site may cause congestion during peak hours.",
                recommendation="Verify demand assumptions and consider capacity densification."
            )


def _check_equipment(inp: "RFSizingInput", result: "SizingOutput", warnings: WarningResult):
    """Check equipment-related warnings."""

    # MIMO mismatch with catalog
    if result.catalog_overrides_applied:
        if inp.base_station.antenna_config and result.antenna_config != inp.base_station.antenna_config:
            _add_warning(
                warnings,
                code="W030",
                severity="info",
                category="equipment",
                message="Antenna config overridden by catalog",
                detail=f"Requested: {inp.base_station.antenna_config}, Effective: {result.antenna_config}",
                recommendation="Catalog equipment has different MIMO configuration. Verify this matches your deployment plan."
            )

    # TX power override
    if inp.base_station.tx_power_w and result.tx_power_w != inp.base_station.tx_power_w:
        _add_warning(
            warnings,
            code="W031",
            severity="info",
            category="equipment",
            message="TX power overridden by catalog",
            detail=f"Requested: {inp.base_station.tx_power_w}W, Effective: {result.tx_power_w}W",
            recommendation="Catalog radio has different power rating. Verify this matches your deployment plan."
        )

    # Default pattern fallback
    if result.effective_pattern_source and "cosine" in result.effective_pattern_source.lower():
        _add_warning(
            warnings,
            code="W032",
            severity="info",
            category="equipment",
            message="Using default cosine antenna pattern",
            detail="No catalog or custom antenna pattern provided. Using simplified cosine model.",
            recommendation="For accurate coverage prediction, import actual antenna pattern from vendor datasheet."
        )

    # Unusual MIMO configuration
    mimo = inp.base_station.antenna_config
    if mimo in ["2T2R", "4T4R"] and inp.environment.scenario in ["UMa", "RMa"]:
        _add_warning(
            warnings,
            code="W033",
            severity="info",
            category="equipment",
            message="Low-order MIMO for macro scenario",
            detail=f"{mimo} configuration in {inp.environment.scenario} scenario may limit capacity.",
            recommendation="Consider 8T8R or higher for macro deployments in urban/suburban areas."
        )


def _check_planning(inp: "RFSizingInput", result: "SizingOutput", warnings: WarningResult):
    """Check planning-related warnings."""

    if not result.placement_plan:
        return

    metrics = result.placement_plan.metrics

    # Low coverage ratio
    if metrics.coverage_ratio < 0.7:
        _add_warning(
            warnings,
            code="W040",
            severity="warning",
            category="planning",
            message="Low coverage ratio in placement plan",
            detail=f"Coverage ratio: {metrics.coverage_ratio:.1%} of service area is covered.",
            recommendation="Consider adding more sites or adjusting exclusion zones to improve coverage."
        )

    # High overload
    if result.placement_plan.spatial_capacity and result.placement_plan.spatial_capacity.overloaded_sites > 0:
        sc = result.placement_plan.spatial_capacity
        overload_pct = sc.overloaded_sites / max(1, metrics.selected_sites) * 100
        if overload_pct > 20:
            _add_warning(
                warnings,
                code="W041",
                severity="warning",
                category="planning",
                message="Many overloaded sites in plan",
                detail=f"{sc.overloaded_sites} sites ({overload_pct:.0f}%) are overloaded. Unserved DL demand: {sc.unserved_dl_gbps:.3f} Gbps",
                recommendation="Consider adding sites in high-demand areas or increasing site capacity."
            )

    # No locked sites with alignment
    if metrics.alignment_length_km > 0 and metrics.locked_sites == 0:
        _add_warning(
            warnings,
            code="W042",
            severity="info",
            category="planning",
            message="No sites locked along alignment",
            detail=f"Alignment length: {metrics.alignment_length_km:.1f}km but no locked sites.",
            recommendation="Consider locking key sites along the alignment for more predictable coverage."
        )


# Warning code registry for documentation
WARNING_CODES_DESCRIPTIONS = {
    "W001": "Very small cell radius (< 50m)",
    "W002": "Very large cell radius (> 15km)",
    "W003": "LOS path type with low LOS probability",
    "W010": "FDD throughput approximation",
    "W011": "Extreme TDD DL ratio",
    "W012": "Very low cell-edge SINR",
    "W013": "Low spectral efficiency at cell edge",
    "W020": "Capacity insufficient for demand",
    "W021": "Very high site count",
    "W022": "High users per site",
    "W030": "Antenna config overridden by catalog",
    "W031": "TX power overridden by catalog",
    "W032": "Using default cosine antenna pattern",
    "W033": "Low-order MIMO for macro scenario",
    "W040": "Low coverage ratio in placement plan",
    "W041": "Many overloaded sites in plan",
    "W042": "No sites locked along alignment",
}