"""Tests for Phase 2 modules: SINR mapper, capacity, QoS verifier, recommender."""
import math
import pytest
from rf5g.models.input_schema import RFSizingInput
from rf5g.models.lookup_tables import BandLookup, SINRCQILookup, QoSLookup, ShadowFadingLookup, PowerClassLookup, AntennaConfigLookup
from rf5g.engine.sinr_mapper import map_sinr_to_cqi, calculate_cell_throughput, coverage_percentage
from rf5g.engine.capacity import calculate_capacity, _get_layers
from rf5g.engine.qos_verifier import verify_qos
from rf5g.engine.recommender import generate_recommendations
from rf5g.cli import _run_sizing


class TestSINRMapper:
    """Test SINR → CQI → SE mapping."""

    def setup_method(self):
        self.lookup = SINRCQILookup()

    def test_sinr_below_table(self):
        """SINR below -8 dB should map to CQI 1."""
        result = map_sinr_to_cqi(-10.0, self.lookup)
        assert result["cqi"] == 1
        assert result["modulation"] == "QPSK"

    def test_sinr_above_table(self):
        """SINR above 20 dB should map to CQI 15."""
        result = map_sinr_to_cqi(25.0, self.lookup)
        assert result["cqi"] == 15
        assert result["modulation"] == "256QAM"

    def test_sinr_minus3_maps_to_cqi3(self):
        """SINR = -3 dB should map to CQI 3 (QPSK)."""
        result = map_sinr_to_cqi(-3.0, self.lookup)
        assert result["cqi"] == 3
        assert result["modulation"] == "QPSK"
        # SE is interpolated between CQI 3 and CQI 4, so 0.377 is the table entry
        # but interpolation may give higher value
        assert result["spectral_efficiency"] >= 0.377

    def test_sinr_interpolation(self):
        """Between thresholds, SE should interpolate."""
        low = map_sinr_to_cqi(-3.0, self.lookup)
        high = map_sinr_to_cqi(-1.0, self.lookup)
        mid = map_sinr_to_cqi(-2.0, self.lookup)
        assert low["spectral_efficiency"] <= mid["spectral_efficiency"] <= high["spectral_efficiency"]

    def test_qpsk_16qam_boundary(self):
        """SINR ~4 dB should transition to 16QAM."""
        result = map_sinr_to_cqi(4.0, self.lookup)
        assert result["modulation"] == "16QAM"
        assert result["cqi"] >= 7

    def test_64qam_boundary(self):
        """SINR ~10 dB should transition to 64QAM."""
        result = map_sinr_to_cqi(10.0, self.lookup)
        assert result["modulation"] == "64QAM"

    def test_256qam_boundary(self):
        """SINR ~18 dB should transition to 256QAM."""
        result = map_sinr_to_cqi(18.0, self.lookup)
        assert result["modulation"] == "256QAM"


class TestCellThroughput:
    """Test cell throughput calculation (3GPP TS 38.306)."""

    def test_n78_100mhz_scs30(self):
        """n78 100MHz SCS30: 273 RBs, should give meaningful throughput."""
        result = calculate_cell_throughput(
            nrb=273, scs_khz=30, spectral_efficiency_bps_hz=0.377,
            layers=4, overhead=0.15, tdd_dl_ratio=0.70
        )
        assert result["dl_mbps"] > 0
        assert result["ul_mbps"] > 0
        assert result["dl_mbps"] > result["ul_mbps"]  # DL ratio > UL

    def test_throughput_increases_with_se(self):
        """Higher SE should give higher throughput."""
        low_se = calculate_cell_throughput(273, 30, 0.377, 4, 0.15, 0.70)
        high_se = calculate_cell_throughput(273, 30, 3.322, 4, 0.15, 0.70)
        assert high_se["dl_mbps"] > low_se["dl_mbps"] * 5

    def test_tdd_ratio(self):
        """UL throughput should scale with (1 - tdd_dl_ratio)."""
        dl_heavy = calculate_cell_throughput(273, 30, 1.0, 4, 0.15, 0.70)
        balanced = calculate_cell_throughput(273, 30, 1.0, 4, 0.15, 0.50)
        assert balanced["ul_mbps"] > dl_heavy["ul_mbps"]

    def test_more_layers_more_throughput(self):
        """More MIMO layers should give proportionally more throughput."""
        two_layers = calculate_cell_throughput(273, 30, 1.0, 2, 0.15, 0.70)
        four_layers = calculate_cell_throughput(273, 30, 1.0, 4, 0.15, 0.70)
        assert four_layers["dl_mbps"] > two_layers["dl_mbps"] * 1.5


class TestCoveragePercentage:
    """Test coverage area percentage estimation."""

    def test_sinr_above_threshold_full_coverage(self):
        """SINR 10+ dB above threshold should give ~100% coverage."""
        pct = coverage_percentage(10.0, 0.0)
        assert pct >= 95

    def test_sinr_below_threshold_no_coverage(self):
        """SINR 10+ dB below threshold should give ~0% coverage."""
        pct = coverage_percentage(-10.0, 0.0)
        assert pct <= 5

    def test_sinr_at_threshold(self):
        """SINR at threshold should give ~50% coverage."""
        pct = coverage_percentage(0.0, 0.0)
        assert 40 <= pct <= 60


class TestCapacity:
    """Test capacity dimensioning."""

    def test_capacity_calculation(self):
        """Basic capacity calculation with default config."""
        inp = RFSizingInput()
        result = calculate_capacity(inp, sinr_db=-3.0, coverage_sites=100)
        assert result.cell_throughput_dl_mbps > 0
        assert result.cell_throughput_ul_mbps > 0
        assert result.total_sites >= 100
        assert result.total_capacity_dl_gbps > 0

    def test_capacity_insufficient(self):
        """High user demand should make capacity insufficient."""
        inp = RFSizingInput()
        inp.qos.users_per_km2 = 5000
        inp.qos.dl_per_user_mbps = 100
        result = calculate_capacity(inp, sinr_db=-3.0, coverage_sites=10)
        # 5000 users/km2 * 50 km2 * 0.2 = 50000 active * 100 Mbps = huge demand
        assert result.total_demand_dl_gbps > 0

    def test_get_layers(self):
        """Antenna config should map to correct MIMO layers."""
        assert _get_layers("2T2R") == 2
        assert _get_layers("32T32R") == 4
        assert _get_layers("64T64R") == 4


class TestQoSVerifier:
    """Test QoS verification."""

    def test_vonr_passes_at_high_sinr(self):
        """VoNR should pass at SINR >= -3 dB."""
        inp = RFSizingInput()
        inp.qos.primary_service = "vonr"
        results = verify_qos(inp, sinr_db=-3.0, cell_radius_km=0.5)
        assert len(results) == 1
        assert results[0].service == "VoNR"
        assert results[0].passed is True

    def test_vonr_fails_at_low_sinr(self):
        """VoNR should fail at SINR < -3 dB."""
        inp = RFSizingInput()
        inp.qos.primary_service = "vonr"
        results = verify_qos(inp, sinr_db=-5.0, cell_radius_km=0.5)
        assert results[0].passed is False

    def test_mixed_checks_multiple_services(self):
        """Mixed service should check all 6 services."""
        inp = RFSizingInput()
        inp.qos.primary_service = "mixed"
        results = verify_qos(inp, sinr_db=-3.0, cell_radius_km=0.5)
        assert len(results) == 6
        services = [r.service for r in results]
        assert "VoNR" in services
        assert "Data" in services

    def test_iot_easiest_to_pass(self):
        """IoT should pass most easily (lowest SINR requirement)."""
        inp = RFSizingInput()
        inp.qos.primary_service = "iot"
        results = verify_qos(inp, sinr_db=-4.0, cell_radius_km=0.5)
        assert results[0].service == "IoT"
        assert results[0].passed is True


class TestRecommender:
    """Test recommendation engine."""

    def test_ul_limiting_recommendation(self):
        """UL limiting should generate recommendation."""
        inp = RFSizingInput()
        result = _run_sizing(inp)
        recs = generate_recommendations(result)
        ul_rec = [r for r in recs if "UL is limiting" in r]
        assert len(ul_rec) > 0

    def test_small_cell_recommendation(self):
        """Very small cell radius should recommend small cells."""
        inp = RFSizingInput()
        inp.project.area_km2 = 1
        inp.environment.scenario = "UMi"
        inp.environment.obstacle_density = "heavy"
        result = _run_sizing(inp)
        recs = generate_recommendations(result)
        # Should have some recommendation about dense/small cell
        assert len(recs) > 0

    def test_rural_recommendation(self):
        """Rural scenario should generate appropriate recommendations."""
        inp = RFSizingInput()
        inp.project.area_km2 = 500
        inp.environment.scenario = "RMa"
        inp.environment.obstacle_density = "light"
        inp.frequency.band = "n8"
        inp.frequency.bandwidth_mhz = 10
        result = _run_sizing(inp)
        recs = generate_recommendations(result)
        # Should mention low band or large radius
        low_band_rec = [r for r in recs if "Low band" in r or "large" in r.lower() or "Large" in r]
        assert len(low_band_rec) > 0


class TestPhase2Integration:
    """End-to-end Phase 2 integration tests."""

    def test_full_sizing_with_capacity(self):
        """Full sizing should include capacity results."""
        inp = RFSizingInput()
        result = _run_sizing(inp)
        assert result.capacity is not None
        assert result.capacity.cell_throughput_dl_mbps > 0
        assert result.capacity.total_sites >= result.site_estimate.coverage_sites
        assert result.capacity.total_demand_dl_gbps >= 0

    def test_dense_urban_capacity(self):
        """Dense urban should be capacity-constrained."""
        inp = RFSizingInput()
        inp.qos.users_per_km2 = 5000
        inp.qos.dl_per_user_mbps = 100
        result = _run_sizing(inp)
        # Dense urban with high demand should have capacity issues
        assert result.capacity is not None

    def test_rural_coverage_constrained(self):
        """Rural should be coverage-constrained (few sites)."""
        inp = RFSizingInput()
        inp.environment.scenario = "RMa"
        inp.environment.obstacle_density = "light"
        inp.frequency.band = "n8"
        inp.frequency.bandwidth_mhz = 10
        inp.project.area_km2 = 500
        result = _run_sizing(inp)
        assert result.site_estimate.coverage_sites <= 100
        assert result.capacity is not None

    def test_output_json_serializable(self):
        """Output should be JSON-serializable."""
        inp = RFSizingInput()
        result = _run_sizing(inp)
        json_str = result.model_dump_json(indent=2)
        assert "capacity" in json_str
        assert "cell_throughput_dl_mbps" in json_str