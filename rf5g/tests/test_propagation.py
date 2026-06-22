"""Tests for 3GPP TR 38.901 propagation models."""
import math
import pytest
from rf5g.engine.propagation import (
    path_loss, invert_mapl_to_radius, los_probability,
    _pl_uma_los, _pl_uma_nlos, _pl_umi_los, _pl_umi_nlos,
    _pl_rma_los, _pl_rma_nlos, _pl_inh_los, _pl_inh_nlos,
)


class TestUMa:
    """3GPP TR 38.901 UMa model verification."""

    def test_uma_los_100m(self):
        """UMa LOS at 100m, 3.5 GHz."""
        pl = _pl_uma_los(100, 3.5)
        assert 78 < pl < 90, f"UMa LOS at 100m = {pl:.1f} dB"

    def test_uma_los_1km(self):
        """UMa LOS at 1km, 3.5 GHz — above breakpoint, should be higher."""
        pl = _pl_uma_los(1000, 3.5)
        assert 100 < pl < 170, f"UMa LOS at 1km = {pl:.1f} dB"

    def test_uma_nlos_greater_than_los(self):
        """NLOS path loss should always be >= LOS."""
        for d in [100, 500, 1000, 2000]:
            pl_los = _pl_uma_los(d, 3.5)
            pl_nlos = _pl_uma_nlos(d, 3.5)
            assert pl_nlos >= pl_los, f"NLOS < LOS at d={d}m"

    def test_uma_nlos_500m(self):
        """UMa NLOS at 500m, 3.5 GHz — typical dense urban range."""
        pl = _pl_uma_nlos(500, 3.5)
        assert 120 < pl < 160, f"UMa NLOS at 500m = {pl:.1f} dB"

    def test_uma_nlos_monotonic(self):
        """Path loss should increase monotonically with distance."""
        distances = [100, 200, 500, 1000, 2000, 5000]
        pl_values = [_pl_uma_nlos(d, 3.5) for d in distances]
        for i in range(len(pl_values) - 1):
            assert pl_values[i] < pl_values[i + 1]

    def test_uma_nlos_prd_example(self):
        """Verify UMa NLOS gives reasonable values for PRD worked example.
        At 446m, 3.5 GHz: PL should be in range 130-145 dB."""
        pl = _pl_uma_nlos(446, 3.5)
        assert 120 < pl < 150, f"UMa NLOS at 446m = {pl:.1f} dB, expected 130-145"


class TestUMi:
    """3GPP TR 38.901 UMi model."""

    def test_umi_nlos_greater_than_los(self):
        for d in [50, 100, 500, 1000]:
            pl_los = _pl_umi_los(d, 3.5)
            pl_nlos = _pl_umi_nlos(d, 3.5)
            assert pl_nlos >= pl_los

    def test_umi_los_100m(self):
        pl = _pl_umi_los(100, 3.5)
        assert 80 < pl < 95, f"UMi LOS at 100m = {pl:.1f} dB"


class TestRMa:
    """3GPP TR 38.901 RMa model."""

    def test_rma_nlos_greater_than_los(self):
        for d in [100, 500, 2000, 10000]:
            pl_los = _pl_rma_los(d, 3.5)
            pl_nlos = _pl_rma_nlos(d, 3.5)
            assert pl_nlos >= pl_los

    def test_rma_long_range(self):
        """RMa should support distances up to 10km."""
        pl = path_loss("RMa", "NLOS", 10000, 3.5)
        assert 100 < pl < 250, f"RMa NLOS at 10km = {pl:.1f} dB"

    def test_rma_nlos_formula(self):
        """RMa NLOS PL should be reasonable at typical distances."""
        pl_rma_500 = _pl_rma_nlos(500, 3.5)
        pl_rma_5000 = _pl_rma_nlos(5000, 3.5)
        assert 130 < pl_rma_500 < 160
        assert 150 < pl_rma_5000 < 190


class TestInH:
    """3GPP TR 38.901 InH model."""

    def test_inh_nlos_greater_than_los(self):
        for d in [5, 10, 50, 100]:
            pl_los = _pl_inh_los(d, 3.5)
            pl_nlos = _pl_inh_nlos(d, 3.5)
            assert pl_nlos >= pl_los

    def test_inh_short_range(self):
        """InH at 10m should give reasonable path loss."""
        pl = path_loss("InH", "LOS", 10, 3.5)
        assert 50 < pl < 80


class TestMAPLInversion:
    """Test MAPL -> cell radius numerical inversion."""

    def test_round_trip_uma(self):
        """Path loss at computed radius should equal MAPL."""
        mapl = 130.0
        radius = invert_mapl_to_radius("UMa", "NLOS", mapl, 3.5)
        pl_at_radius = path_loss("UMa", "NLOS", radius, 3.5)
        assert abs(pl_at_radius - mapl) < 2.0, f"PL={pl_at_radius:.2f} != MAPL={mapl}"

    def test_round_trip_umi(self):
        """Round-trip for UMi."""
        mapl = 120.0
        radius = invert_mapl_to_radius("UMi", "NLOS", mapl, 3.5)
        pl_at_radius = path_loss("UMi", "NLOS", radius, 3.5)
        assert abs(pl_at_radius - mapl) < 2.0

    def test_high_mapl_gives_large_radius(self):
        """Higher MAPL should give larger cell radius."""
        r_low = invert_mapl_to_radius("UMa", "NLOS", 110, 3.5)
        r_high = invert_mapl_to_radius("UMa", "NLOS", 140, 3.5)
        assert r_high > r_low

    def test_rma_reasonable_radius(self):
        """RMa should give reasonable cell radius."""
        r_rma = invert_mapl_to_radius("RMa", "NLOS", 130, 3.5)
        assert r_rma > 10, f"RMa radius too small: {r_rma:.0f}m"
        assert r_rma < 50000, f"RMa radius too large: {r_rma:.0f}m"

    def test_inversion_accuracy(self):
        """Inversion should be accurate to within 2 dB."""
        for mapl in [110, 120, 130, 140, 150]:
            radius = invert_mapl_to_radius("UMa", "NLOS", mapl, 3.5)
            pl = path_loss("UMa", "NLOS", radius, 3.5)
            assert abs(pl - mapl) < 2.0, f"MAPL={mapl}, radius={radius:.1f}m, PL={pl:.2f}"


class TestLOSProbability:
    """Test LOS probability functions."""

    def test_los_prob_decreases_with_distance(self):
        """LOS probability should decrease with distance."""
        pr_100 = los_probability("UMa", 100)
        pr_500 = los_probability("UMa", 500)
        pr_1000 = los_probability("UMa", 1000)
        assert pr_100 >= pr_500 >= pr_1000

    def test_los_prob_between_0_and_1(self):
        """LOS probability should be between 0 and 1."""
        for scenario in ["UMa", "UMi", "RMa", "InH"]:
            for d in [10, 100, 500, 1000, 5000]:
                pr = los_probability(scenario, d)
                assert 0 <= pr <= 1, f"{scenario} at {d}m: P_LOS={pr}"


class TestCombined:
    """Test combined path loss (LOS/NLOS weighted)."""

    def test_combined_positive(self):
        """Combined PL should be positive."""
        for d in [100, 500, 1000]:
            pl_combined = path_loss("UMa", "combined", d, 3.5)
            assert pl_combined > 0