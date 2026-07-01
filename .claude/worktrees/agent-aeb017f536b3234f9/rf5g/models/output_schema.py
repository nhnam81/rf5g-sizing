"""Output schema for rf5g — Pydantic v2 models."""
from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field


class LinkBudgetResult(BaseModel):
    """Result of DL/UL link budget calculation."""
    direction: str  # "DL" or "UL"
    eirp_dbm: float
    rx_sensitivity_dbm: float
    mapl_db: float
    tx_power_dbm: float
    tx_gain_db: float
    rx_gain_db: float
    cable_loss_db: float
    body_loss_db: float
    interference_margin_db: float
    shadow_fading_margin_db: float
    rain_margin_db: float
    penetration_loss_db: float
    noise_floor_dbm: float
    noise_figure_db: float
    snr_required_db: float


class PropagationResult(BaseModel):
    """Result of propagation model calculation."""
    model: str  # e.g. "UMa_NLOS"
    path_loss_db: float
    cell_radius_km: float
    cell_radius_m: float
    los_probability: Optional[float] = None
    combined_path_loss_db: Optional[float] = None


class SiteEstimateResult(BaseModel):
    """Result of site count estimation."""
    coverage_sites: int
    cell_radius_km: float
    cell_area_km2: float
    isd_km: float  # Inter-site distance
    limiting_link: str  # "DL" or "UL"
    overlap_factor: float
    sectors: int = 3  # Number of sectors per site


class SINRResult(BaseModel):
    """SINR at cell edge and mapping to CQI/SE."""
    sinr_db: float
    cqi: int
    modulation: str
    spectral_efficiency_bps_hz: float
    code_rate: float


class QoSVerificationResult(BaseModel):
    """QoS pass/fail for each service type."""
    service: str
    sinr_required_db: float
    sinr_available_db: float
    radius_km: float
    area_percentage: float
    passed: bool


class CapacityResult(BaseModel):
    """Capacity dimensioning result."""
    cell_throughput_dl_mbps: float
    cell_throughput_ul_mbps: float
    total_sites: int
    total_capacity_dl_gbps: float
    total_demand_dl_gbps: float
    capacity_sufficient: bool
    additional_sites_needed: int


class SizingOutput(BaseModel):
    """Complete output of 5G RF sizing calculation."""
    project_name: str
    environment: str
    band: str
    bandwidth_mhz: float
    antenna_config: str
    tx_power_w: float
    link_budget_dl: LinkBudgetResult
    link_budget_ul: LinkBudgetResult
    propagation: PropagationResult
    site_estimate: SiteEstimateResult
    sinr: SINRResult
    qos_verification: List[QoSVerificationResult] = []
    capacity: Optional[CapacityResult] = None
    recommendations: List[str] = []