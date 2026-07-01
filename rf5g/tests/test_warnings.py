"""Tests for scenario validity warnings."""
import pytest
from rf5g.models.input_schema import RFSizingInput
from rf5g.cli import _run_sizing
from rf5g.engine.warnings import generate_warnings, WARNING_CODES_DESCRIPTIONS


class TestWarningCodes:
    """Verify warning codes are documented."""

    def test_all_warning_codes_have_descriptions(self):
        """Every warning code used should be documented."""
        from rf5g.engine.warnings import ScenarioWarning, WarningResult

        # Get all warning codes from the module
        import rf5g.engine.warnings as warnings_module
        codes_used = set()

        # Extract codes from functions
        import inspect
        source = inspect.getsource(warnings_module)
        import re
        codes_found = re.findall(r'code="([W0-9]+)"', source)
        codes_used = set(codes_found)

        # Verify all codes have descriptions
        for code in codes_used:
            assert code in WARNING_CODES_DESCRIPTIONS, f"Warning code {code} not documented"


class TestPropagationWarnings:
    """Test propagation-related warnings."""

    def test_small_cell_radius_warning(self):
        """Very small cell radius should trigger W001."""
        # Use high penetration loss to force small radius
        inp = RFSizingInput(
            project={"area_km2": 10},
            environment={"scenario": "UMa", "obstacle_density": "heavy"},
            margins={"penetration_db": 35},  # Very high penetration loss
        )
        result = _run_sizing(inp)
        warnings = generate_warnings(inp, result)

        if result.propagation.cell_radius_km < 0.05:
            assert any(w.code == "W001" for w in warnings.warnings)

    def test_large_cell_radius_warning(self):
        """Very large cell radius should trigger W002."""
        inp = RFSizingInput(
            project={"area_km2": 1000},
            environment={"scenario": "RMa", "obstacle_density": "light"},
            margins={"penetration_db": 0},
        )
        result = _run_sizing(inp)
        warnings = generate_warnings(inp, result)

        if result.propagation.cell_radius_km > 15:
            assert any(w.code == "W002" for w in warnings.warnings)


class TestThroughputWarnings:
    """Test throughput-related warnings."""

    def test_fdd_throughput_approximation_warning(self):
        """FDD duplex should trigger W010."""
        inp = RFSizingInput(
            frequency={"band": "n8", "duplex": "FDD"},
        )
        result = _run_sizing(inp)
        warnings = generate_warnings(inp, result)

        assert any(w.code == "W010" for w in warnings.warnings)

    def test_extreme_tdd_ratio_warning(self):
        """Extreme TDD ratio should trigger W011."""
        inp = RFSizingInput(
            frequency={"band": "n78", "tdd_dl_ratio": 0.95},  # 95% DL
        )
        result = _run_sizing(inp)
        warnings = generate_warnings(inp, result)

        assert any(w.code == "W011" for w in warnings.warnings)

    def test_low_sinr_warning(self):
        """Very low SINR should trigger W012."""
        inp = RFSizingInput(
            margins={"interference_db": 20},  # High interference
        )
        result = _run_sizing(inp)
        warnings = generate_warnings(inp, result)

        if result.sinr.sinr_db < -5:
            assert any(w.code == "W012" for w in warnings.warnings)


class TestCapacityWarnings:
    """Test capacity-related warnings."""

    def test_capacity_insufficient_warning(self):
        """Insufficient capacity should trigger W020."""
        inp = RFSizingInput(
            project={"area_km2": 50},
            qos={"users_per_km2": 500, "dl_per_user_mbps": 50},  # High demand
        )
        result = _run_sizing(inp)
        warnings = generate_warnings(inp, result)

        if result.capacity and not result.capacity.capacity_sufficient:
            assert any(w.code == "W020" for w in warnings.warnings)


class TestEquipmentWarnings:
    """Test equipment-related warnings."""

    def test_low_mimo_macro_warning(self):
        """Low-order MIMO in macro scenario should trigger W033."""
        inp = RFSizingInput(
            base_station={"antenna_config": "2T2R"},
            environment={"scenario": "UMa"},
        )
        result = _run_sizing(inp)
        warnings = generate_warnings(inp, result)

        assert any(w.code == "W033" for w in warnings.warnings)


class TestWarningIntegration:
    """Test warnings are included in CLI output."""

    def test_warnings_in_output(self):
        """Warnings should be included in SizingOutput."""
        inp = RFSizingInput()
        result = _run_sizing(inp)

        # Should have warnings list
        assert hasattr(result, "warnings")
        assert isinstance(result.warnings, list)


class TestWarningSeverity:
    """Test warning severity levels."""

    def test_warnings_sorted_by_severity(self):
        """Warnings should be sorted by severity (critical first)."""
        inp = RFSizingInput()
        result = _run_sizing(inp)
        warnings = generate_warnings(inp, result)

        if len(warnings.warnings) > 1:
            severity_order = {"critical": 0, "warning": 1, "info": 2}
            for i in range(len(warnings.warnings) - 1):
                curr_severity = severity_order.get(warnings.warnings[i].severity, 3)
                next_severity = severity_order.get(warnings.warnings[i + 1].severity, 3)
                assert curr_severity <= next_severity