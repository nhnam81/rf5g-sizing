"""Input schema for rf5g — Pydantic v2 models."""
from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator


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
    tx_power_w: float = Field(200.0, gt=0, description="Total TX power in watts")
    height_m: float = Field(25.0, gt=0, description="BS antenna height in meters")
    sectors: Literal[1, 3, 6] = 3
    cable_loss_db: float = Field(1.0, ge=0, description="Feeder/cable loss in dB")
    noise_figure_db: float = Field(3.5, ge=0, description="BS receiver noise figure in dB")


class FrequencyConfig(BaseModel):
    band: str = "n78"
    bandwidth_mhz: float = Field(100.0, gt=0, description="Channel bandwidth in MHz")
    scs_khz: Literal[15, 30, 60, 120] = 30
    duplex: Literal["TDD", "FDD"] = "TDD"
    tdd_dl_ratio: float = Field(0.70, gt=0, lt=1, description="TDD DL ratio (e.g. 0.70 for DDDSU)")


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