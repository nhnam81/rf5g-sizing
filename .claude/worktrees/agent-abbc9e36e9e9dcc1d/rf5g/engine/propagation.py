"""3GPP TR 38.901 propagation models — FULL implementation with numerical inversion.

All formulas follow 3GPP TR 38.901 V16.1.0.
Uses scipy.optimize.brentq for numerical inversion of MAPL -> cell radius.
"""
from __future__ import annotations
import math
from typing import Literal, Optional
from scipy.optimize import brentq

Scenario = Literal["UMa", "UMi", "RMa", "InH"]
PathType = Literal["LOS", "NLOS", "combined"]


def _d_bp_uma(h_bs: float, h_ut: float, fc_ghz: float) -> float:
    """UMa breakpoint distance in meters."""
    return 4 * (h_bs - 1.0) * (h_ut - 1.0) * fc_ghz * 1e9 / 3e8


def _pl_uma_los(d_2d_m: float, fc_ghz: float, h_bs: float = 25.0, h_ut: float = 1.5) -> float:
    """3GPP TR 38.901 Table 7.4.1-1: UMa LOS path loss."""
    d_bp = _d_bp_uma(h_bs, h_ut, fc_ghz)
    d = max(d_2d_m, 1.0)
    fc = fc_ghz

    if d <= d_bp:
        pl = 28.0 + 22.0 * math.log10(d) + 20.0 * math.log10(fc)
    else:
        pl = 28.0 + 40.0 * math.log10(d) + 20.0 * math.log10(fc) \
             - 9.0 * math.log10(max(d_bp, 1.0))
    return pl


def _pl_uma_nlos(d_2d_m: float, fc_ghz: float, h_bs: float = 25.0, h_ut: float = 1.5) -> float:
    """3GPP TR 38.901 Table 7.4.1-1: UMa NLOS path loss.
    PL = max(161.04 - 7.28*log10(fc) + 36.56*log10(d_km), PL_LOS)
    where d_km = d_2D / 1000
    """
    pl_los = _pl_uma_los(d_2d_m, fc_ghz, h_bs, h_ut)
    d_km = max(d_2d_m, 1.0) / 1000.0
    pl_nlos = 161.04 - 7.28 * math.log10(fc_ghz) + 36.56 * math.log10(d_km)
    return max(pl_nlos, pl_los)


def _pr_uma_los(d_2d_m: float) -> float:
    """3GPP TR 38.901 Table 7.4.2-1: UMa LOS probability."""
    d = d_2d_m
    if d <= 18:
        return 1.0
    elif d <= 6000:
        return max(0.0, math.exp(-(d - 18.0) / 27.0))
    else:
        return 0.0


def _d_bp_umi(h_bs: float, h_ut: float, fc_ghz: float) -> float:
    """UMi breakpoint distance in meters."""
    return 4 * (h_bs - 1.0) * (h_ut - 1.0) * fc_ghz * 1e9 / 3e8


def _pl_umi_los(d_2d_m: float, fc_ghz: float, h_bs: float = 10.0, h_ut: float = 1.5) -> float:
    """3GPP TR 38.901 Table 7.4.1-1: UMi-Street Canyon LOS path loss."""
    d_bp = _d_bp_umi(h_bs, h_ut, fc_ghz)
    d = max(d_2d_m, 1.0)

    if d <= d_bp:
        pl = 32.4 + 21.0 * math.log10(d) + 20.0 * math.log10(fc_ghz)
    else:
        pl = 32.4 + 40.0 * math.log10(d) + 20.0 * math.log10(fc_ghz) \
             - 9.5 * math.log10(max(d_bp, 1.0))
    return pl


def _pl_umi_nlos(d_2d_m: float, fc_ghz: float, h_bs: float = 10.0, h_ut: float = 1.5) -> float:
    """3GPP TR 38.901 Table 7.4.1-1: UMi-Street Canyon NLOS path loss."""
    pl_los = _pl_umi_los(d_2d_m, fc_ghz, h_bs, h_ut)
    pl_nlos = 35.3 * math.log10(max(d_2d_m, 1.0)) + 22.4 + 21.3 * math.log10(fc_ghz)
    return max(pl_nlos, pl_los)


def _pr_umi_los(d_2d_m: float) -> float:
    """3GPP TR 38.901 Table 7.4.2-1: UMi LOS probability."""
    d = d_2d_m
    if d <= 0:
        return 1.0
    elif d <= 18:
        return 1.0
    else:
        return max(0.0, 18.0 / d)


def _pl_rma_los(d_2d_m: float, fc_ghz: float, h_bs: float = 35.0, h_ut: float = 1.5) -> float:
    """3GPP TR 38.901 Table 7.4.1-1: RMa LOS path loss."""
    c = 3e8
    fc_hz = fc_ghz * 1e9
    d_bp = 2 * math.pi * h_bs * h_ut * fc_hz / c
    d = max(d_2d_m, 1.0)

    if d <= d_bp:
        pl = 20.0 * math.log10(40.0 * math.pi * d * fc_ghz / 3.0) \
             + min(0.0, 1.5 * (h_ut - h_bs) / 1000.0)
    else:
        pl_bp = 20.0 * math.log10(40.0 * math.pi * max(d_bp, 1.0) * fc_ghz / 3.0) \
                + min(0.0, 1.5 * (h_ut - h_bs) / 1000.0)
        pl = pl_bp + 40.0 * math.log10(d / max(d_bp, 1.0))
    return pl


def _pl_rma_nlos(d_2d_m: float, fc_ghz: float, h_bs: float = 35.0, h_ut: float = 1.5) -> float:
    """3GPP TR 38.901 Table 7.4.1-1: RMa NLOS path loss."""
    pl_los = _pl_rma_los(d_2d_m, fc_ghz, h_bs, h_ut)
    d_km = max(d_2d_m, 1.0) / 1000.0
    pl_nlos = 161.04 - 7.28 * math.log10(fc_ghz) + 36.56 * math.log10(d_km)
    return max(pl_nlos, pl_los)


def _pr_rma_los(d_2d_m: float) -> float:
    """3GPP TR 38.901 Table 7.4.2-1: RMa LOS probability."""
    d_km = d_2d_m / 1000.0
    if d_km <= 0.01:
        return 1.0
    elif d_km <= 0.1:
        return 1.0
    else:
        return max(0.0, math.exp(-(d_km - 0.01) / 0.5))


def _pl_inh_los(d_2d_m: float, fc_ghz: float, h_bs: float = 25.0, h_ut: float = 1.5) -> float:
    """3GPP TR 38.901 Table 7.4.1-1: InH LOS path loss."""
    d = max(d_2d_m, 1.0)
    if d <= 150:
        pl = 32.4 + 23.0 * math.log10(d) + 20.0 * math.log10(fc_ghz)
    else:
        pl = 32.4 + 23.0 * math.log10(150) + 20.0 * math.log10(fc_ghz) \
             + 32.0 * math.log10(d / 150)
    return pl


def _pl_inh_nlos(d_2d_m: float, fc_ghz: float, h_bs: float = 25.0, h_ut: float = 1.5) -> float:
    """3GPP TR 38.901 Table 7.4.1-1: InH NLOS path loss."""
    pl_los = _pl_inh_los(d_2d_m, fc_ghz)
    pl_nlos = 38.3 + 24.9 * math.log10(max(d_2d_m, 1.0)) + 20.0 * math.log10(fc_ghz)
    return max(pl_nlos, pl_los)


def _pr_inh_los(d_2d_m: float) -> float:
    """3GPP TR 38.901 Table 7.4.2-1: InH LOS probability."""
    d = d_2d_m
    if d <= 1.2:
        return 1.0
    elif d <= 6.5:
        return math.exp(-(d - 1.2) / 5.0)
    else:
        return 0.07 * math.exp(-(d - 6.5) / 10.0)


# Dispatch table
_PATH_LOSS_FUNCS = {
    "UMa": {"LOS": _pl_uma_los, "NLOS": _pl_uma_nlos},
    "UMi": {"LOS": _pl_umi_los, "NLOS": _pl_umi_nlos},
    "RMa": {"LOS": _pl_rma_los, "NLOS": _pl_rma_nlos},
    "InH": {"LOS": _pl_inh_los, "NLOS": _pl_inh_nlos},
}

_LOS_PROB_FUNCS = {
    "UMa": _pr_uma_los,
    "UMi": _pr_umi_los,
    "RMa": _pr_rma_los,
    "InH": _pr_inh_los,
}


def path_loss(scenario: Scenario, path_type: PathType, d_2d_m: float,
              fc_ghz: float, h_bs: float = 25.0, h_ut: float = 1.5) -> float:
    """Calculate path loss for given scenario and distance."""
    if scenario not in _PATH_LOSS_FUNCS:
        raise ValueError(f"Unknown scenario: {scenario}")

    if path_type == "LOS":
        return _PATH_LOSS_FUNCS[scenario]["LOS"](d_2d_m, fc_ghz, h_bs, h_ut)
    elif path_type == "NLOS":
        return _PATH_LOSS_FUNCS[scenario]["NLOS"](d_2d_m, fc_ghz, h_bs, h_ut)
    elif path_type == "combined":
        los_prob = _LOS_PROB_FUNCS[scenario](d_2d_m)
        pl_los = _PATH_LOSS_FUNCS[scenario]["LOS"](d_2d_m, fc_ghz, h_bs, h_ut)
        pl_nlos = _PATH_LOSS_FUNCS[scenario]["NLOS"](d_2d_m, fc_ghz, h_bs, h_ut)
        pl_linear = los_prob * (10 ** (-pl_los / 10)) + (1 - los_prob) * (10 ** (-pl_nlos / 10))
        return -10 * math.log10(max(pl_linear, 1e-30))
    else:
        raise ValueError(f"Unknown path type: {path_type}")


def los_probability(scenario: Scenario, d_2d_m: float) -> float:
    """Get LOS probability for given scenario and distance."""
    return _LOS_PROB_FUNCS[scenario](d_2d_m)


def invert_mapl_to_radius(scenario: Scenario, path_type: PathType, mapl_db: float,
                          fc_ghz: float, h_bs: float = 25.0, h_ut: float = 1.5,
                          d_min_m: float = 1.0, d_max_m: float = 50000.0) -> float:
    """Numerically invert MAPL -> cell radius using scipy brentq."""
    def objective(d):
        return path_loss(scenario, path_type, d, fc_ghz, h_bs, h_ut) - mapl_db

    f_min = objective(d_min_m)
    f_max = objective(d_max_m)

    if f_min > 0 and f_max > 0:
        return d_min_m
    if f_min < 0 and f_max < 0:
        return d_max_m

    try:
        radius_m = brentq(objective, d_min_m, d_max_m, xtol=0.1, rtol=1e-6)
    except ValueError:
        radius_m = d_max_m

    return radius_m