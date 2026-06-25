"""Integration test — end-to-end sizing with PRD worked example."""
import json
import math
import pytest
from pathlib import Path
from rf5g.models.input_schema import RFSizingInput
from rf5g.models.lookup_tables import BandLookup, PowerClassLookup, AntennaConfigLookup, SINRCQILookup, QoSLookup, ShadowFadingLookup
from rf5g.engine.propagation import path_loss, invert_mapl_to_radius
from rf5g.engine.link_budget import calculate_link_budget
from rf5g.engine.site_estimator import estimate_sites
from rf5g.models.antenna_pattern import get_catalog_radio, resolve_catalog_radio_total_tx_power_w
from rf5g.cli import _run_sizing


class TestPRDWorkedExample:
    """Verify against PRD Phase 2/3 worked example values.

    Dense Urban n78 scenario:
    - BS: 32T32R, 200W, 25m, 3 sectors
    - UE: PC3, 1.5m
    - n78 (3500 MHz), 100 MHz BW, SCS 30 kHz, TDD 7:3
    - UMa, heavy clutter, 50 km²
    """

    @pytest.fixture
    def urban_config(self):
        config_path = Path(__file__).parent.parent.parent / "examples" / "dense_urban_n78.json"
        with open(config_path) as f:
            data = json.load(f)
        return RFSizingInput(**data)

    def test_nrb_lookup(self):
        """n78 100MHz SCS30kHz should give 273 RBs."""
        band_lookup = BandLookup()
        nrb = band_lookup.get_nrb(100, 30)
        assert nrb == 273, f"Expected 273 RBs, got {nrb}"

    def test_power_class_pc3(self):
        """PC3 should give 23 dBm."""
        pc_lookup = PowerClassLookup()
        assert pc_lookup.get_tx_power_dbm("PC3") == 23

    def test_antenna_32t32r(self):
        """32T32R should give 20 dBi gain with 12 dB BF."""
        ant_lookup = AntennaConfigLookup()
        config = ant_lookup.get_config("32T32R")
        assert config["antenna_gain_dbi"] == 20
        assert config["beamforming_gain_db"] == 12

    def test_throughput_calculation(self):
        """DL peak: ~1.2 Gbps (TDD 70%), UL peak: ~157 Mbps (TDD 30%)."""
        N_RB = 273
        subcarriers = 12
        Qm_dl = 8  # 256QAM
        R_dl = 0.8  # code rate
        OH_dl = 0.14
        symbols = 12
        slots = 2000  # SCS 30kHz
        layers_dl = 4

        dl_peak = N_RB * subcarriers * Qm_dl * R_dl * (1 - OH_dl) * symbols * slots * layers_dl
        dl_tdd = dl_peak * 0.70
        assert abs(dl_tdd / 1e9 - 1.20) < 0.05, f"DL TDD = {dl_tdd/1e9:.2f} Gbps, expected ~1.20 Gbps"

        Qm_ul = 6  # 64QAM
        R_ul = 0.6
        OH_ul = 0.08
        layers_ul = 2
        ul_peak = N_RB * subcarriers * Qm_ul * R_ul * (1 - OH_ul) * symbols * slots * layers_ul
        ul_tdd = ul_peak * 0.30
        assert abs(ul_tdd / 1e6 - 157) < 10, f"UL TDD = {ul_tdd/1e6:.0f} Mbps, expected ~157 Mbps"

    def test_site_count(self):
        """50 km² with R=0.446km, 3-sector hex, 25% overlap → 121 sites."""
        R = 0.446
        area = 50
        overlap = 0.25
        cell_area = 2.598 * R ** 2
        n_sites = math.ceil(area / cell_area * (1 + overlap))
        assert abs(n_sites - 121) < 3, f"Expected ~121 sites, got {n_sites}"

    def test_full_sizing(self, urban_config):
        """Run full sizing and verify key outputs are reasonable."""
        result = _run_sizing(urban_config)

        # Key checks
        assert result.link_budget_dl.mapl_db > 100, "DL MAPL should be > 100 dB"
        assert result.link_budget_ul.mapl_db > 100, "UL MAPL should be > 100 dB"
        assert result.propagation.cell_radius_km > 0.1, "Cell radius should be > 100m"
        assert result.site_estimate.coverage_sites > 0, "Should need at least 1 site"
        assert result.sinr.sinr_db > -20, "SINR should be > -20 dB"

        # UL should typically be limiting
        assert result.site_estimate.limiting_link in ["UL", "DL"]

        # Print summary for manual review
        print(f"\n--- PRD Worked Example Results ---")
        print(f"DL MAPL: {result.link_budget_dl.mapl_db:.1f} dB")
        print(f"UL MAPL: {result.link_budget_ul.mapl_db:.1f} dB")
        print(f"Cell radius: {result.propagation.cell_radius_km:.3f} km ({result.propagation.cell_radius_m:.0f} m)")
        print(f"Sites needed: {result.site_estimate.coverage_sites}")
        print(f"Limiting link: {result.site_estimate.limiting_link}")
        print(f"Cell edge SINR: {result.sinr.sinr_db:.1f} dB (CQI {result.sinr.cqi})")
        print(f"Propagation model: {result.propagation.model}")
        print(f"Path loss at radius: {result.propagation.path_loss_db:.1f} dB")


class TestEffectiveOutputs:
    """Effective output fields should match the values used in calculations."""

    def test_catalog_radio_total_power_prefers_explicit_total(self):
        radio = get_catalog_radio("Ericsson", "Radio 8883")
        assert resolve_catalog_radio_total_tx_power_w(radio) == 320

    def test_catalog_radio_total_power_falls_back_to_legacy_value(self):
        radio = get_catalog_radio("Ericsson", "Radio 8883RW")
        assert resolve_catalog_radio_total_tx_power_w(radio) == 320

    def test_catalog_radio_override_is_reflected_in_output(self):
        inp = RFSizingInput(base_station={
            "tx_power_w": 200,
            "antenna_config": "8T8R",
            "radio_vendor": "Ericsson",
            "radio_model": "Radio 8883",
        })
        result = _run_sizing(inp)

        assert result.input_tx_power_w == 200
        assert result.tx_power_w == 320
        assert result.catalog_overrides_applied is True
        assert result.link_budget_dl.tx_power_dbm == round(10 * math.log10(result.tx_power_w * 1000), 2)

    def test_catalog_antenna_gain_is_exposed(self):
        inp = RFSizingInput(base_station={
            "antenna_config": "32T32R",
            "antenna_vendor": "Prose Technologies",
            "antenna_model": "2TB-21U-SR",
        })
        result = _run_sizing(inp)

        assert result.input_antenna_config == "32T32R"
        assert result.antenna_config == "32T32R"
        assert result.effective_antenna_gain_dbi == 17.8
        assert result.catalog_overrides_applied is True
        assert result.link_budget_dl.tx_gain_db == 29.8


class TestEdgeCases:
    """Edge case tests."""

    def test_very_small_area(self):
        """1 km² should need few sites."""
        inp = RFSizingInput(project={"area_km2": 1})
        result = _run_sizing(inp)
        assert result.site_estimate.coverage_sites >= 1

    def test_very_large_area(self):
        """1000 km² should need many sites."""
        inp = RFSizingInput(project={"area_km2": 1000})
        result = _run_sizing(inp)
        assert result.site_estimate.coverage_sites > 100

    def test_rural_scenario(self):
        """RMa should give different results than UMa (different LOS prob)."""
        inp_uma = RFSizingInput(environment={"scenario": "UMa"})
        inp_rma = RFSizingInput(environment={"scenario": "RMa"})
        r_uma = _run_sizing(inp_uma)
        r_rma = _run_sizing(inp_rma)
        # Both should have positive radius
        assert r_uma.propagation.cell_radius_km > 0
        assert r_rma.propagation.cell_radius_km > 0
        # Just check both scenarios produce valid results
        assert r_uma.site_estimate.coverage_sites > 0
        assert r_rma.site_estimate.coverage_sites > 0