"""O2I (Outdoor-to-Indoor) Penetration Loss - 3GPP TR 38.901 Table 7.4.3-1.

Frequency-dependent building penetration loss model.

3GPP TR 38.901 V16.1.0 Section 7.4.3:
    O2I_Low  = 5.8 + 4.5*log10(fc_GHz) [dB]  (low loss - residential, lightweight)
    O2I_High = 14.8 + 6.2*log10(fc_GHz) [dB] (high loss - commercial, concrete)

Typical usage:
    - Low loss: Residential buildings, wood/drywall interior
    - High loss: Office buildings, concrete/glass facades
    - Weighted: Mix based on building type distribution
"""

from __future__ import annotations
import math
from typing import Literal


def calculate_o2i_loss(
    fc_mhz: float,
    loss_type: Literal["low", "high", "weighted"] = "weighted",
    building_ratio: float = 0.5,
) -> float:
    """Calculate O2I (Outdoor-to-Indoor) penetration loss.

    Args:
        fc_mhz: Center frequency in MHz
        loss_type: Type of building penetration loss model
            - "low": Low loss (residential, lightweight walls)
            - "high": High loss (commercial, concrete, thick glass)
            - "weighted": Weighted average of low/high
        building_ratio: For "weighted", ratio of high-loss buildings (0-1)
            Default 0.5 = 50% high-loss, 50% low-loss

    Returns:
        O2I penetration loss in dB

    Reference:
        3GPP TR 38.901 V16.1.0 Table 7.4.3-1
    """
    fc_ghz = fc_mhz / 1000.0

    # 3GPP TR 38.901 formulas
    o2i_low = 5.8 + 4.5 * math.log10(fc_ghz)
    o2i_high = 14.8 + 6.2 * math.log10(fc_ghz)

    if loss_type == "low":
        return round(o2i_low, 1)
    elif loss_type == "high":
        return round(o2i_high, 1)
    else:  # weighted
        # Weighted average: building_ratio is fraction of high-loss buildings
        # Typical urban: 0.5 (50% commercial/50% residential)
        # Dense urban: 0.7 (70% commercial)
        # Suburban: 0.3 (30% commercial)
        o2i_weighted = building_ratio * o2i_high + (1 - building_ratio) * o2i_low
        return round(o2i_weighted, 1)


def get_o2i_type_for_scenario(
    scenario: str,
    obstacle_density: str,
) -> tuple[str, float]:
    """Determine appropriate O2I loss type and building ratio for scenario.

    Args:
        scenario: Propagation scenario (UMa, UMi, RMa, InH)
        obstacle_density: Obstacle density (heavy, medium, light)

    Returns:
        Tuple of (loss_type, building_ratio)

    Mapping:
        - UMa + heavy: weighted, 0.7 (70% high-loss in dense urban)
        - UMa + medium: weighted, 0.5 (mixed urban)
        - UMa + light: weighted, 0.3 (suburban)
        - UMi + heavy: weighted, 0.8 (dense urban micro)
        - UMi + medium: weighted, 0.6
        - UMi + light: weighted, 0.4
        - RMa + any: low (rural, mostly residential)
        - InH + heavy: high (indoor, thick walls)
        - InH + light: low (indoor, open plan)
    """
    # Default mapping based on scenario and density
    if scenario == "RMa":
        # Rural: mostly residential, low loss
        return "low", 0.2

    if scenario == "InH":
        # Indoor hotspot
        if obstacle_density == "heavy":
            return "high", 1.0  # Thick walls, data centers
        else:
            return "low", 0.3  # Open plan offices

    # UMa, UMi
    density_to_ratio = {
        "heavy": 0.7,   # Dense urban: 70% commercial/high-loss
        "medium": 0.5,  # Mixed urban: 50/50
        "light": 0.3,   # Suburban: 30% commercial
    }

    building_ratio = density_to_ratio.get(obstacle_density, 0.5)
    return "weighted", building_ratio


# Pre-calculated values for common bands (for reference)
O2I_LOSS_TABLE = {
    "n8": {"fc_mhz": 942, "low": 5.7, "high": 14.6, "weighted_0.5": 10.2},
    "n28": {"fc_mhz": 780, "low": 5.3, "high": 14.1, "weighted_0.5": 9.7},
    "n40": {"fc_mhz": 2350, "low": 7.5, "high": 17.1, "weighted_0.5": 12.3},
    "n41": {"fc_mhz": 2595, "low": 7.7, "high": 17.4, "weighted_0.5": 12.5},
    "n77": {"fc_mhz": 3750, "low": 8.4, "high": 18.4, "weighted_0.5": 13.4},
    "n78": {"fc_mhz": 3500, "low": 8.2, "high": 18.2, "weighted_0.5": 13.2},
    "n258": {"fc_mhz": 25875, "low": 12.2, "high": 23.6, "weighted_0.5": 17.9},
    "n261": {"fc_mhz": 27925, "low": 12.3, "high": 23.8, "weighted_0.5": 18.0},
}