"""Output schema contract tests — ensure consistency across CLI, API, and UI.

These tests verify that:
1. The output schema is stable and well-defined
2. Key fields are present and have expected types
3. Naming is consistent across surfaces

Run: pytest rf5g/tests/test_output_schema.py -v
"""
import json
import pytest
from pathlib import Path
from rf5g.models.input_schema import RFSizingInput
from rf5g.models.output_schema import SizingOutput, ScenarioWarning
from rf5g.cli import _run_sizing


# Expected field structure for SizingOutput
EXPECTED_TOP_LEVEL_FIELDS = {
    "project_name": str,
    "environment": str,
    "band": str,
    "bandwidth_mhz": float,
    "antenna_config": str,
    "tx_power_w": float,
    "input_antenna_config": str,
    "input_tx_power_w": float,
    "effective_antenna_gain_dbi": (type(None), float),
    "effective_pattern_source": (type(None), str),
    "catalog_overrides_applied": bool,
    "link_budget_dl": object,  # LinkBudgetResult
    "link_budget_ul": object,  # LinkBudgetResult
    "propagation": object,  # PropagationResult
    "site_estimate": object,  # SiteEstimateResult
    "sinr": object,  # SINRResult
    "qos_verification": list,
    "capacity": (type(None), object),  # CapacityResult
    "recommendations": list,
    "placement_plan": (type(None), object),  # PlacementPlanResult
    "warnings": list,
}

EXPECTED_LINK_BUDGET_FIELDS = {
    "direction": str,
    "eirp_dbm": float,
    "rx_sensitivity_dbm": float,
    "mapl_db": float,
    "tx_power_dbm": float,
    "tx_gain_db": float,
    "rx_gain_db": float,
    "cable_loss_db": float,
    "body_loss_db": float,
    "interference_margin_db": float,
    "shadow_fading_margin_db": float,
    "rain_margin_db": float,
    "penetration_loss_db": float,
    "noise_floor_dbm": float,
    "noise_figure_db": float,
    "snr_required_db": float,
}

EXPECTED_PROPAGATION_FIELDS = {
    "model": str,
    "path_loss_db": float,
    "cell_radius_km": float,
    "cell_radius_m": float,
    "los_probability": (type(None), float),
    "combined_path_loss_db": (type(None), float),
}

EXPECTED_SITE_ESTIMATE_FIELDS = {
    "coverage_sites": int,
    "cell_radius_km": float,
    "cell_area_km2": float,
    "isd_km": float,
    "limiting_link": str,
    "overlap_factor": float,
    "sectors": int,
}

EXPECTED_SINR_FIELDS = {
    "sinr_db": float,
    "cqi": int,
    "modulation": str,
    "spectral_efficiency_bps_hz": float,
    "code_rate": float,
}

EXPECTED_CAPACITY_FIELDS = {
    "cell_throughput_dl_mbps": float,
    "cell_throughput_ul_mbps": float,
    "total_sites": int,
    "total_capacity_dl_gbps": float,
    "total_demand_dl_gbps": float,
    "capacity_sufficient": bool,
    "additional_sites_needed": int,
}


class TestOutputSchemaStructure:
    """Test that output schema has expected structure."""

    @pytest.fixture
    def sample_result(self):
        """Create a sample sizing result for testing."""
        inp = RFSizingInput()
        return _run_sizing(inp)

    def test_top_level_fields_exist(self, sample_result):
        """All expected top-level fields should exist."""
        for field_name in EXPECTED_TOP_LEVEL_FIELDS:
            assert hasattr(sample_result, field_name), f"Missing field: {field_name}"

    def test_top_level_field_types(self, sample_result):
        """Top-level fields should have expected types."""
        for field_name, expected_type in EXPECTED_TOP_LEVEL_FIELDS.items():
            value = getattr(sample_result, field_name)
            if expected_type == object:
                assert value is not None, f"Field {field_name} should not be None"
            elif isinstance(expected_type, tuple):
                # Handle union types (e.g., (type(None), float))
                if value is None:
                    continue  # None is acceptable for optional fields
                # For object types in tuple, just check not None
                if object in expected_type:
                    assert value is not None, f"Field {field_name} should not be None"
                else:
                    assert type(value) in expected_type, \
                        f"Field {field_name} has type {type(value)}, expected one of {expected_type}"
            else:
                assert isinstance(value, expected_type), \
                    f"Field {field_name} has type {type(value)}, expected {expected_type}"

    def test_link_budget_structure(self, sample_result):
        """Link budget results should have expected structure."""
        for lb in [sample_result.link_budget_dl, sample_result.link_budget_ul]:
            for field_name in EXPECTED_LINK_BUDGET_FIELDS:
                assert hasattr(lb, field_name), f"Link budget missing field: {field_name}"

    def test_propagation_structure(self, sample_result):
        """Propagation result should have expected structure."""
        prop = sample_result.propagation
        for field_name in EXPECTED_PROPAGATION_FIELDS:
            assert hasattr(prop, field_name), f"Propagation missing field: {field_name}"

    def test_site_estimate_structure(self, sample_result):
        """Site estimate should have expected structure."""
        site = sample_result.site_estimate
        for field_name in EXPECTED_SITE_ESTIMATE_FIELDS:
            assert hasattr(site, field_name), f"Site estimate missing field: {field_name}"

    def test_sinr_structure(self, sample_result):
        """SINR result should have expected structure."""
        sinr = sample_result.sinr
        for field_name in EXPECTED_SINR_FIELDS:
            assert hasattr(sinr, field_name), f"SINR missing field: {field_name}"

    def test_capacity_structure(self, sample_result):
        """Capacity result should have expected structure."""
        if sample_result.capacity:
            cap = sample_result.capacity
            for field_name in EXPECTED_CAPACITY_FIELDS:
                assert hasattr(cap, field_name), f"Capacity missing field: {field_name}"

    def test_warnings_structure(self, sample_result):
        """Warnings should be a list of ScenarioWarning objects."""
        assert isinstance(sample_result.warnings, list)
        for w in sample_result.warnings:
            assert isinstance(w, ScenarioWarning)
            assert hasattr(w, "code")
            assert hasattr(w, "severity")
            assert hasattr(w, "category")
            assert hasattr(w, "message")


class TestOutputSchemaSerialization:
    """Test that output schema can be serialized/deserialized."""

    @pytest.fixture
    def sample_result(self):
        """Create a sample sizing result for testing."""
        inp = RFSizingInput()
        return _run_sizing(inp)

    def test_json_serialization(self, sample_result):
        """Output should be serializable to JSON."""
        json_str = sample_result.model_dump_json()
        assert isinstance(json_str, str)
        # Should be valid JSON
        data = json.loads(json_str)
        assert isinstance(data, dict)

    def test_json_roundtrip(self, sample_result):
        """Output should survive JSON serialization roundtrip."""
        json_str = sample_result.model_dump_json()
        data = json.loads(json_str)
        reconstructed = SizingOutput(**data)
        assert reconstructed.project_name == sample_result.project_name
        assert reconstructed.band == sample_result.band


class TestOutputConsistencyAcrossScenarios:
    """Test that output schema is consistent across different scenarios."""

    @pytest.mark.parametrize("scenario_name", ["dense_urban_n78", "suburban_n77", "rural_n8"])
    def test_output_structure_consistent(self, scenario_name):
        """Output structure should be consistent across scenarios."""
        config_path = Path(__file__).parent.parent.parent / "examples" / f"{scenario_name}.json"
        with open(config_path) as f:
            data = json.load(f)
        inp = RFSizingInput(**data)
        result = _run_sizing(inp)

        # All expected fields should exist
        for field_name in EXPECTED_TOP_LEVEL_FIELDS:
            assert hasattr(result, field_name), f"[{scenario_name}] Missing field: {field_name}"

        # Key metrics should be present
        assert result.propagation.cell_radius_km > 0
        assert result.site_estimate.coverage_sites > 0
        assert result.sinr.sinr_db is not None
        assert result.capacity is not None


class TestNamingConsistency:
    """Test that naming is consistent across CLI, API, and UI."""

    def test_cell_radius_naming(self):
        """Cell radius should be consistently named."""
        inp = RFSizingInput()
        result = _run_sizing(inp)

        # Both km and m versions should exist
        assert hasattr(result.propagation, "cell_radius_km")
        assert hasattr(result.propagation, "cell_radius_m")

        # Values should be consistent
        assert abs(result.propagation.cell_radius_km * 1000 - result.propagation.cell_radius_m) < 1

    def test_sites_naming(self):
        """Site count should be consistently named."""
        inp = RFSizingInput()
        result = _run_sizing(inp)

        # coverage_sites in site_estimate
        assert hasattr(result.site_estimate, "coverage_sites")

        # total_sites in capacity (if present)
        if result.capacity:
            assert hasattr(result.capacity, "total_sites")
            # total_sites should be >= coverage_sites
            assert result.capacity.total_sites >= result.site_estimate.coverage_sites

    def test_limiting_link_values(self):
        """Limiting link should only be UL or DL."""
        inp = RFSizingInput()
        result = _run_sizing(inp)

        assert result.site_estimate.limiting_link in ["UL", "DL"]

    def test_bandwidth_naming(self):
        """Bandwidth should be consistently named."""
        inp = RFSizingInput()
        result = _run_sizing(inp)

        # Should be bandwidth_mhz, not bandwidth
        assert hasattr(result, "bandwidth_mhz")
        assert result.bandwidth_mhz > 0


class TestSummaryFields:
    """Test that summary fields needed by UI are present."""

    def test_ui_key_metrics_present(self):
        """Key metrics needed by UI should be present."""
        inp = RFSizingInput()
        result = _run_sizing(inp)

        # These fields are used in guided.py
        assert hasattr(result.propagation, "cell_radius_m")
        assert hasattr(result.site_estimate, "coverage_sites")
        assert hasattr(result.site_estimate, "limiting_link")
        assert hasattr(result.sinr, "sinr_db")
        assert hasattr(result.link_budget_dl, "mapl_db")
        assert hasattr(result.link_budget_ul, "mapl_db")

        if result.capacity:
            assert hasattr(result.capacity, "capacity_sufficient")
            assert hasattr(result.capacity, "total_sites")

    def test_planning_summary_fields_present(self):
        """Planning summary fields should be present when placement_plan exists."""
        inp = RFSizingInput()
        result = _run_sizing(inp)

        if result.placement_plan:
            plan = result.placement_plan
            assert hasattr(plan, "metrics")
            assert hasattr(plan.metrics, "selected_sites")
            assert hasattr(plan.metrics, "coverage_ratio")
            assert hasattr(plan.metrics, "service_area_km2")

            if plan.spatial_capacity:
                assert hasattr(plan.spatial_capacity, "unserved_dl_gbps")