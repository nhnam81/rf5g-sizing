"""Input schema for rf5g — Pydantic v2 models."""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class GeoPoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class GeoPolygon(BaseModel):
    outer: list[GeoPoint]
    holes: list[list[GeoPoint]] = Field(default_factory=list)
    name: Optional[str] = None
    id: Optional[str] = None

    @model_validator(mode="after")
    def validate_rings(self):
        if len(self.outer) < 3:
            raise ValueError("Service area polygon outer ring must have at least 3 points")
        for hole in self.holes:
            if len(hole) < 3:
                raise ValueError("Polygon holes must have at least 3 points")
        return self


class LinearAlignment(BaseModel):
    points: list[GeoPoint]
    alignment_type: Literal["road", "tunnel", "rail", "custom"] = "custom"
    buffer_m: Optional[float] = Field(None, ge=0)
    preferred_spacing_m: Optional[float] = Field(None, gt=0)
    name: Optional[str] = None

    @model_validator(mode="after")
    def validate_points(self):
        if len(self.points) < 2:
            raise ValueError("Alignment must contain at least 2 points")
        return self


class ExclusionZone(BaseModel):
    polygon: GeoPolygon
    reason: Literal["no_build", "water", "heritage", "private", "hazard", "custom"] = "no_build"
    hard: bool = True
    setback_m: float = Field(0.0, ge=0)


class TrafficZone(BaseModel):
    polygon: GeoPolygon
    weight: float = Field(1.0, gt=0)
    users_per_km2: Optional[float] = Field(None, gt=0)
    dl_per_user_mbps: Optional[float] = Field(None, gt=0)
    ul_per_user_mbps: Optional[float] = Field(None, gt=0)
    concurrent_ratio: Optional[float] = Field(None, gt=0, lt=1)
    name: Optional[str] = None


class PlannedSiteInput(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    status: Literal["candidate", "planned", "locked", "existing"] = "planned"
    id: Optional[str] = None
    azimuth_deg: Optional[float] = Field(None, ge=0, lt=360)
    beamwidth_deg: Optional[float] = Field(None, gt=0, le=360)
    sectors: Optional[int] = Field(None, ge=1, le=6)
    site_type: Optional[Literal["macro", "small_cell", "das", "repeater", "custom"]] = None
    notes: Optional[str] = None


class PlacementConstraints(BaseModel):
    service_area: Optional[GeoPolygon] = None
    exclusion_zones: list[ExclusionZone] = Field(default_factory=list)
    alignments: list[LinearAlignment] = Field(default_factory=list)
    planned_sites: list[PlannedSiteInput] = Field(default_factory=list)
    min_site_spacing_m: Optional[float] = Field(None, gt=0)
    edge_setback_m: float = Field(0.0, ge=0)
    allow_outside_service_area_buffer_m: float = Field(0.0, ge=0)
    placement_mode: Literal["polygon_fill", "alignment_biased", "alignment_only", "hybrid"] = "polygon_fill"
    objective: Literal["coverage_first", "balanced", "capacity_first"] = "balanced"


class SpatialCapacityConfig(BaseModel):
    enabled: bool = False
    grid_resolution_m: float = Field(100.0, gt=0)
    hotspot_search_radius_m: Optional[float] = Field(None, gt=0)
    demand_zones: list[TrafficZone] = Field(default_factory=list)
    max_load_per_site_mbps_dl: Optional[float] = Field(None, gt=0)
    max_load_per_site_mbps_ul: Optional[float] = Field(None, gt=0)


class ProjectConfig(BaseModel):
    name: str = "untitled"
    area_km2: float = Field(50.0, gt=0, description="Coverage area in km²")
    center_lat: float = Field(10.78, ge=-90, le=90, description="Center latitude")
    center_lon: float = Field(106.70, ge=-180, le=180, description="Center longitude")


class EnvironmentConfig(BaseModel):
    scenario: Literal["UMa", "UMi", "RMa", "InH"] = "UMa"
    obstacle_density: Literal["heavy", "medium", "light"] = "heavy"
    coverage_probability: float = Field(0.95, gt=0, lt=1, description="Target coverage probability")


class BaseStationConfig(BaseModel):
    antenna_config: str = "32T32R"
    radio_vendor: Optional[str] = Field(None, description="Radio vendor from catalog (e.g. 'Ericsson', 'Rapid.Space')")
    radio_model: Optional[str] = Field(None, description="Radio model from catalog (e.g. 'Radio 8883', 'ORS')")
    antenna_vendor: Optional[str] = Field(None, description="Antenna vendor from catalog (e.g. 'Prose Technologies', 'Ericsson')")
    antenna_model: Optional[str] = Field(None, description="Antenna model from catalog (e.g. '2TB-21U-SR', 'KRE 101 2677/1')")
    antenna_pattern_source: Optional[Literal['catalog', 'file']] = Field(None, description="Where the antenna pattern should be resolved from")
    antenna_pattern_file: Optional[str] = Field(None, description="Path to a custom antenna pattern asset (.ant, .csv, .json, .msi, .txt)")
    antenna_pattern_format: Optional[Literal['auto', 'ant', 'csv', 'json', 'msi', 'atoll_txt']] = Field(None, description="Explicit format for a custom antenna pattern file")
    antenna_pattern_name: Optional[str] = Field(None, description="Optional antenna/pattern row name for multi-row Atoll text files")
    antenna_pattern_freq_mhz: Optional[float] = Field(None, gt=0, description="Optional frequency hint for custom pattern resolution")
    tx_power_w: float = Field(200.0, gt=0, description="Total TX power per sector/radio in watts across all TX ports")
    height_m: float = Field(25.0, gt=0, description="BS antenna height in meters")
    sectors: Literal[1, 3, 6] = 3
    cable_loss_db: float = Field(1.0, ge=0, description="Feeder/cable loss in dB")
    noise_figure_db: float = Field(3.5, ge=0, description="BS receiver noise figure in dB")


class FrequencyConfig(BaseModel):
    band: str = "n78"
    bandwidth_mhz: float = Field(100.0, gt=0, description="Channel bandwidth in MHz")
    scs_khz: Literal[15, 30, 60, 120] = 30
    duplex: Literal["TDD", "FDD"] = "TDD"
    tdd_dl_ratio: float = Field(0.70, gt=0, le=1, description="TDD DL ratio (0.70 for DDDSU, 1.0 for FDD)")


class UEConfig(BaseModel):
    power_class: Literal["PC1", "PC2", "PC3", "PC4"] = "PC3"
    height_m: float = Field(1.5, gt=0, description="UE height in meters")
    antenna_gain_dbi: float = 0.0
    body_loss_db: float = Field(0.0, ge=0, description="Body loss in dB")
    noise_figure_db: float = Field(7.0, ge=0, description="UE noise figure in dB")


class MarginsConfig(BaseModel):
    interference_db: float = Field(3.0, ge=0, description="Interference margin in dB")
    shadow_fading_db: Optional[float] = Field(None, ge=0, description="Shadow fading margin (auto if None)")
    rain_attenuation_db: float = Field(1.0, ge=0, description="Rain attenuation in dB")
    penetration_db: float = Field(10.0, ge=0, description="Building penetration loss in dB")
    vegetation_db: float = Field(0.0, ge=0, description="Vegetation loss in dB")
    overlap_factor: float = Field(0.25, ge=0, le=0.5, description="Cell overlap factor")


class QoSConfig(BaseModel):
    primary_service: Literal["mixed", "vonr", "video_hd", "video_4k", "data", "gaming", "iot"] = "mixed"
    dl_per_user_mbps: float = Field(50.0, gt=0)
    ul_per_user_mbps: float = Field(10.0, gt=0)
    users_per_km2: float = Field(500.0, gt=0)
    concurrent_ratio: float = Field(0.20, gt=0, lt=1, description="Concurrent user ratio")


class RFSizingInput(BaseModel):
    """Complete input for 5G RF sizing calculation."""
    project: ProjectConfig = ProjectConfig()
    environment: EnvironmentConfig = EnvironmentConfig()
    base_station: BaseStationConfig = BaseStationConfig()
    frequency: FrequencyConfig = FrequencyConfig()
    user_equipment: UEConfig = UEConfig()
    margins: MarginsConfig = MarginsConfig()
    qos: QoSConfig = QoSConfig()
    placement: Optional[PlacementConstraints] = None
    spatial_capacity: Optional[SpatialCapacityConfig] = None
