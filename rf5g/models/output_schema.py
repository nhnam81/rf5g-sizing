"""Output schema for rf5g — Pydantic v2 models."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field

from .input_schema import ExclusionZone, GeoPolygon, LinearAlignment, TrafficZone


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


class CandidateSiteResult(BaseModel):
    id: str
    lat: float
    lon: float
    source: str
    accepted: bool
    reasons: list[str] = Field(default_factory=list)
    score: Optional[float] = None
    azimuths_deg: list[float] = Field(default_factory=list)
    beamwidth_deg: Optional[float] = None
    status: Optional[str] = None


class EquipmentSourceResult(BaseModel):
    vendor: Optional[str] = None
    model: Optional[str] = None
    source_pdf: Optional[str] = None
    import_confidence: Optional[str] = None
    pattern_source_type: Optional[str] = None
    pattern_asset: Optional[str] = None
    pattern_source: Optional[str] = None


class SelectedSiteResult(BaseModel):
    id: str
    lat: float
    lon: float
    source: str
    azimuths_deg: list[float] = Field(default_factory=list)
    beamwidth_deg: Optional[float] = None
    status: str = "selected"
    coverage_area_km2: Optional[float] = None
    estimated_dl_load_mbps: Optional[float] = None
    estimated_ul_load_mbps: Optional[float] = None
    overloaded: bool = False


class PlacementMetrics(BaseModel):
    service_area_km2: float
    covered_area_km2: float
    coverage_ratio: float
    excluded_area_km2: float = 0.0
    candidate_sites: int = 0
    selected_sites: int = 0
    locked_sites: int = 0
    rejected_candidates: int = 0
    alignment_length_km: float = 0.0


class SpatialCapacityResult(BaseModel):
    demand_dl_gbps: float
    served_dl_gbps: float
    unserved_dl_gbps: float
    demand_ul_gbps: float
    served_ul_gbps: float
    unserved_ul_gbps: float
    hotspot_tiles: int = 0
    overloaded_sites: int = 0
    capacity_sufficient_spatial: bool = True


class GeometryOverlay(BaseModel):
    service_area: Optional[GeoPolygon] = None
    exclusion_zones: list[ExclusionZone] = Field(default_factory=list)
    alignments: list[LinearAlignment] = Field(default_factory=list)
    traffic_zones: list[TrafficZone] = Field(default_factory=list)


class PlacementPlanResult(BaseModel):
    mode: str
    metrics: PlacementMetrics
    selected_sites: list[SelectedSiteResult] = Field(default_factory=list)
    candidates: list[CandidateSiteResult] = Field(default_factory=list)
    overlays: Optional[GeometryOverlay] = None
    spatial_capacity: Optional[SpatialCapacityResult] = None


class SizingOutput(BaseModel):
    """Complete output of 5G RF sizing calculation."""
    project_name: str
    environment: str
    band: str
    bandwidth_mhz: float
    antenna_config: str
    tx_power_w: float
    input_antenna_config: str
    input_tx_power_w: float
    effective_antenna_gain_dbi: Optional[float] = None
    effective_pattern_source: Optional[str] = None
    radio_details: Optional[EquipmentSourceResult] = None
    antenna_details: Optional[EquipmentSourceResult] = None
    catalog_overrides_applied: bool = False
    link_budget_dl: LinkBudgetResult
    link_budget_ul: LinkBudgetResult
    propagation: PropagationResult
    site_estimate: SiteEstimateResult
    sinr: SINRResult
    qos_verification: list[QoSVerificationResult] = Field(default_factory=list)
    capacity: Optional[CapacityResult] = None
    recommendations: list[str] = Field(default_factory=list)
    placement_plan: Optional[PlacementPlanResult] = None
