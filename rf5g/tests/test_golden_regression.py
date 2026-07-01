"""Golden scenario regression tests — freeze key outputs for baseline scenarios.

These tests protect against unintended drift in core sizing outputs.
If a change is intentional, update the expected values below.

Run: pytest rf5g/tests/test_golden_regression.py -v

Last updated: 2026-07-01
"""
import json
import pytest
from pathlib import Path
from rf5g.models.input_schema import RFSizingInput
from rf5g.cli import _run_sizing


# Golden expected values for each scenario
# Update these when intentional model changes are made
GOLDEN_VALUES = {
    "dense_urban_n78": {
        # Cell radius and coverage
        "cell_radius_km": (0.1191, 0.001),  # (expected, tolerance)
        "coverage_sites": (1695, 10),  # tolerance: +/- 10 sites
        "limiting_link": "UL",

        # SINR and modulation
        "sinr_db": (-3.00, 0.1),
        "cqi": 3,
        "modulation": "QPSK",
        "spectral_efficiency_bps_hz": (0.4893, 0.01),

        # Link budget
        "dl_mapl_db": (149.81, 0.5),
        "ul_mapl_db": (123.30, 0.5),
        "path_loss_db": (123.30, 0.5),

        # Site layout
        "isd_km": (0.2064, 0.01),

        # Capacity
        "cell_throughput_dl_mbps": (160.2, 5.0),
        "cell_throughput_ul_mbps": (68.7, 3.0),
    },
    "suburban_n77": {
        "cell_radius_km": (0.2010, 0.001),
        "coverage_sites": (2287, 20),
        "limiting_link": "UL",

        "sinr_db": (-3.00, 0.1),
        "cqi": 3,
        "modulation": "QPSK",
        "spectral_efficiency_bps_hz": (0.4893, 0.01),

        "dl_mapl_db": (145.82, 0.5),
        "ul_mapl_db": (119.31, 0.5),
        "path_loss_db": (119.31, 0.5),

        "isd_km": (0.3482, 0.01),

        "cell_throughput_dl_mbps": (78.1, 3.0),
        "cell_throughput_ul_mbps": (33.5, 2.0),
    },
    "rural_n8": {
        "cell_radius_km": (8.7261, 0.1),  # larger tolerance for rural
        "coverage_sites": (3, 1),
        "limiting_link": "UL",

        "sinr_db": (-2.00, 0.1),
        "cqi": 4,
        "modulation": "QPSK",
        "spectral_efficiency_bps_hz": (0.6016, 0.01),

        "dl_mapl_db": (155.21, 0.5),
        "ul_mapl_db": (129.20, 0.5),
        "path_loss_db": (129.20, 0.5),

        "isd_km": (15.1141, 0.5),

        "cell_throughput_dl_mbps": (6.7, 1.0),
        "cell_throughput_ul_mbps": (6.7, 1.0),
    },
}


def load_scenario(scenario_name: str) -> RFSizingInput:
    """Load a scenario from examples/ directory."""
    config_path = Path(__file__).parent.parent.parent / "examples" / f"{scenario_name}.json"
    with open(config_path) as f:
        data = json.load(f)
    return RFSizingInput(**data)


def check_value(actual, expected_tuple, name: str, scenario: str):
    """Check a value against expected (value, tolerance) tuple."""
    if isinstance(expected_tuple, tuple):
        expected, tolerance = expected_tuple
        if not (expected - tolerance <= actual <= expected + tolerance):
            pytest.fail(
                f"[{scenario}] {name}: expected {expected} ± {tolerance}, got {actual}"
            )
    else:
        # Exact match (for strings, ints)
        if actual != expected_tuple:
            pytest.fail(
                f"[{scenario}] {name}: expected {expected_tuple}, got {actual}"
            )


class TestGoldenRegression:
    """Regression tests for baseline sizing scenarios."""

    @pytest.mark.parametrize("scenario", ["dense_urban_n78", "suburban_n77", "rural_n8"])
    def test_cell_radius(self, scenario):
        """Cell radius should match golden value."""
        inp = load_scenario(scenario)
        result = _run_sizing(inp)
        golden = GOLDEN_VALUES[scenario]

        check_value(
            result.propagation.cell_radius_km,
            golden["cell_radius_km"],
            "cell_radius_km",
            scenario
        )

    @pytest.mark.parametrize("scenario", ["dense_urban_n78", "suburban_n77", "rural_n8"])
    def test_coverage_sites(self, scenario):
        """Coverage site count should match golden value."""
        inp = load_scenario(scenario)
        result = _run_sizing(inp)
        golden = GOLDEN_VALUES[scenario]

        check_value(
            result.site_estimate.coverage_sites,
            golden["coverage_sites"],
            "coverage_sites",
            scenario
        )

    @pytest.mark.parametrize("scenario", ["dense_urban_n78", "suburban_n77", "rural_n8"])
    def test_limiting_link(self, scenario):
        """Limiting link should match golden value."""
        inp = load_scenario(scenario)
        result = _run_sizing(inp)
        golden = GOLDEN_VALUES[scenario]

        check_value(
            result.site_estimate.limiting_link,
            golden["limiting_link"],
            "limiting_link",
            scenario
        )

    @pytest.mark.parametrize("scenario", ["dense_urban_n78", "suburban_n77", "rural_n8"])
    def test_sinr_cqi(self, scenario):
        """SINR and CQI should match golden values."""
        inp = load_scenario(scenario)
        result = _run_sizing(inp)
        golden = GOLDEN_VALUES[scenario]

        check_value(result.sinr.sinr_db, golden["sinr_db"], "sinr_db", scenario)
        check_value(result.sinr.cqi, golden["cqi"], "cqi", scenario)
        check_value(result.sinr.modulation, golden["modulation"], "modulation", scenario)
        check_value(
            result.sinr.spectral_efficiency_bps_hz,
            golden["spectral_efficiency_bps_hz"],
            "spectral_efficiency_bps_hz",
            scenario
        )

    @pytest.mark.parametrize("scenario", ["dense_urban_n78", "suburban_n77", "rural_n8"])
    def test_link_budget(self, scenario):
        """MAPL values should match golden values."""
        inp = load_scenario(scenario)
        result = _run_sizing(inp)
        golden = GOLDEN_VALUES[scenario]

        check_value(result.link_budget_dl.mapl_db, golden["dl_mapl_db"], "dl_mapl_db", scenario)
        check_value(result.link_budget_ul.mapl_db, golden["ul_mapl_db"], "ul_mapl_db", scenario)
        check_value(result.propagation.path_loss_db, golden["path_loss_db"], "path_loss_db", scenario)

    @pytest.mark.parametrize("scenario", ["dense_urban_n78", "suburban_n77", "rural_n8"])
    def test_isd(self, scenario):
        """Inter-site distance should match golden value."""
        inp = load_scenario(scenario)
        result = _run_sizing(inp)
        golden = GOLDEN_VALUES[scenario]

        check_value(result.site_estimate.isd_km, golden["isd_km"], "isd_km", scenario)

    @pytest.mark.parametrize("scenario", ["dense_urban_n78", "suburban_n77", "rural_n8"])
    def test_capacity(self, scenario):
        """Cell throughput should match golden values."""
        inp = load_scenario(scenario)
        result = _run_sizing(inp)
        golden = GOLDEN_VALUES[scenario]

        assert result.capacity is not None, f"[{scenario}] capacity should not be None"

        check_value(
            result.capacity.cell_throughput_dl_mbps,
            golden["cell_throughput_dl_mbps"],
            "cell_throughput_dl_mbps",
            scenario
        )
        check_value(
            result.capacity.cell_throughput_ul_mbps,
            golden["cell_throughput_ul_mbps"],
            "cell_throughput_ul_mbps",
            scenario
        )


class TestGoldenSummary:
    """Summary test that prints all golden values for documentation."""

    @pytest.mark.parametrize("scenario", ["dense_urban_n78", "suburban_n77", "rural_n8"])
    def test_print_summary(self, scenario, capsys):
        """Print golden summary for manual verification."""
        inp = load_scenario(scenario)
        result = _run_sizing(inp)

        print(f"\n=== {scenario} ===")
        print(f"cell_radius_km: {result.propagation.cell_radius_km:.4f}")
        print(f"cell_radius_m: {result.propagation.cell_radius_m:.1f}")
        print(f"coverage_sites: {result.site_estimate.coverage_sites}")
        print(f"limiting_link: {result.site_estimate.limiting_link}")
        print(f"sinr_db: {result.sinr.sinr_db:.2f}")
        print(f"cqi: {result.sinr.cqi}")
        print(f"modulation: {result.sinr.modulation}")
        print(f"spectral_efficiency: {result.sinr.spectral_efficiency_bps_hz:.4f}")
        print(f"dl_mapl_db: {result.link_budget_dl.mapl_db:.2f}")
        print(f"ul_mapl_db: {result.link_budget_ul.mapl_db:.2f}")
        print(f"path_loss_db: {result.propagation.path_loss_db:.2f}")
        print(f"isd_km: {result.site_estimate.isd_km:.4f}")
        if result.capacity:
            print(f"cell_throughput_dl_mbps: {result.capacity.cell_throughput_dl_mbps:.1f}")
            print(f"cell_throughput_ul_mbps: {result.capacity.cell_throughput_ul_mbps:.1f}")
            print(f"total_sites: {result.capacity.total_sites}")


# Instructions for updating golden values
"""
## How to Update Golden Values

When intentional model changes cause regression tests to fail:

1. Run the tests to see the new values:
   pytest rf5g/tests/test_golden_regression.py -v

2. Run the summary test to get the new golden values:
   pytest rf5g/tests/test_golden_regression.py::TestGoldenSummary -v -s

3. Update the GOLDEN_VALUES dictionary above with the new expected values.

4. Document the reason for the change in the commit message:
   - "Update golden values: [reason for model change]"
   - Example: "Update golden values: O2I penetration loss model update per 3GPP TR 38.901"

5. Re-run tests to verify:
   pytest rf5g/tests/test_golden_regression.py -v
"""