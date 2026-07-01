"""Lookup tables for rf5g — loads from JSON data files."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DATA_DIR = Path(__file__).parent.parent / "data"


def _load_json(filename: str) -> dict:
    with open(DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


class BandLookup:
    """3GPP TS 38.104 frequency band lookup."""

    def __init__(self):
        data = _load_json("bands.json")
        self._bands = {k: v for k, v in data.items() if not k.startswith("_")}
        self._nrb = {k: {int(bw): v for bw, v in bw_dict.items()} for k, bw_dict in data.get("nrb_table", {}).items()}

    def get_band(self, band: str) -> dict:
        if band not in self._bands:
            raise ValueError(f"Unknown band: {band}. Available: {list(self._bands.keys())}")
        return self._bands[band]

    def get_fc(self, band: str) -> float:
        return self.get_band(band)["fc_mhz"]

    def get_nrb(self, bandwidth_mhz: float, scs_khz: int) -> int:
        scs_key = str(int(scs_khz))
        if scs_key not in self._nrb:
            raise ValueError(f"Unknown SCS: {scs_khz} kHz. Available: {list(self._nrb.keys())} kHz")
        bw_table = self._nrb[scs_key]
        bw_key = int(bandwidth_mhz)
        if bw_key not in bw_table:
            raise ValueError(f"Unknown BW: {bandwidth_mhz} MHz for SCS {scs_khz} kHz. Available: {list(bw_table.keys())} MHz")
        return bw_table[bw_key]

    def list_bands(self) -> List[str]:
        return list(self._bands.keys())


class PowerClassLookup:
    """UE power class lookup per 3GPP TS 38.101."""

    def __init__(self):
        data = _load_json("power_classes.json")
        self._classes = {k: v for k, v in data.items() if not k.startswith("_")}

    def get_tx_power_dbm(self, power_class: str) -> float:
        if power_class not in self._classes:
            raise ValueError(f"Unknown power class: {power_class}")
        return self._classes[power_class]["tx_power_dbm"]


class AntennaConfigLookup:
    """Antenna configuration lookup."""

    def __init__(self):
        data = _load_json("antenna_configs.json")
        self._configs = {k: v for k, v in data.items() if not k.startswith("_")}
        self._ue = data.get("_ue_antenna", {})

    def get_config(self, config_name: str) -> dict:
        if config_name not in self._configs:
            available = list(self._configs.keys())
            raise ValueError(f"Unknown antenna config: {config_name}. Available: {available}")
        return self._configs[config_name]

    def get_ue_config(self) -> dict:
        return self._ue

    def list_configs(self) -> List[str]:
        return list(self._configs.keys())


class SINRCQILookup:
    """SINR → CQI → MCS → SE lookup per 3GPP TS 38.214."""

    def __init__(self):
        data = _load_json("sinr_cqi_table.json")
        self._table = data["table"]

    def get_by_cqi(self, cqi: int) -> dict:
        for row in self._table:
            if row["cqi"] == cqi:
                return row
        raise ValueError(f"Unknown CQI: {cqi}. Range: 1-15")

    def get_by_sinr(self, sinr_db: float) -> dict:
        """Find CQI for given SINR using linear interpolation."""
        sorted_table = sorted(self._table, key=lambda x: x["sinr_db"])
        if sinr_db <= sorted_table[0]["sinr_db"]:
            return sorted_table[0]
        if sinr_db >= sorted_table[-1]["sinr_db"]:
            return sorted_table[-1]
        for i in range(len(sorted_table) - 1):
            if sorted_table[i]["sinr_db"] <= sinr_db < sorted_table[i + 1]["sinr_db"]:
                return sorted_table[i]
        return sorted_table[-1]


class QoSLookup:
    """QoS requirements lookup."""

    def __init__(self):
        data = _load_json("qos_requirements.json")
        self._services = {k: v for k, v in data.items() if not k.startswith("_")}

    def get_service(self, service: str) -> dict:
        if service not in self._services:
            raise ValueError(f"Unknown service: {service}. Available: {list(self._services.keys())}")
        return self._services[service]

    def get_services_for_mixed(self) -> List[dict]:
        mixed = self._services.get("mixed", {})
        if "services" in mixed:
            return [self._services[s] for s in mixed["services"] if s in self._services]
        return list(self._services.values())


class ShadowFadingLookup:
    """Shadow fading margin lookup (3GPP TR 38.901 Table 7.4.2-1).

SF margin = sigma_SF * norm.ppf(coverage_probability)
where sigma_SF is the log-normal shadow fading std dev per scenario.

3GPP TR 38.901 V16.1.0 Table 7.4.2-1:
  UMa LOS: 4.0 dB, UMa NLOS: 8.0 dB
  UMi LOS: 4.0 dB, UMi NLOS: 7.82 dB (street canyon) / 6.0 dB
  RMa LOS: 4.0 dB, RMa NLOS: 8.0 dB
  InH LOS: 3.0 dB, InH NLOS: 4.0 dB
"""
    # 3GPP TR 38.901 Table 7.4.2-1 shadow fading std dev per scenario+LOS
    _3GPP_SF_SIGMA = {
        ("UMa", "LOS"): 4.0,
        ("UMa", "NLOS"): 8.0,
        ("UMi", "LOS"): 4.0,
        ("UMi", "NLOS"): 7.82,
        ("RMa", "LOS"): 4.0,
        ("RMa", "NLOS"): 8.0,
        ("InH", "LOS"): 3.0,
        ("InH", "NLOS"): 4.0,
    }

    def __init__(self):
        data = _load_json("shadow_fading.json")
        self._densities = {k: v for k, v in data.items() if not k.startswith("_")}

    def get_sf_sigma(self, scenario: str, los_condition: str = "NLOS") -> float:
        """Get 3GPP shadow fading std dev for scenario + LOS condition."""
        key = (scenario, los_condition)
        if key in self._3GPP_SF_SIGMA:
            return self._3GPP_SF_SIGMA[key]
        # Fallback: use density-based mapping
        density_map = {"heavy": "urban_heavy", "medium": "urban", "light": "urban_light"}
        json_key = density_map.get(scenario.lower(), scenario)
        if json_key in self._densities:
            return self._densities[json_key]["sf_db"]
        return 8.0  # Default: UMa NLOS

    def get_sf_margin(self, obstacle_density: str, coverage_probability: float = 0.95,
                      scenario: str = "UMa", los_condition: str = "NLOS") -> float:
        """Calculate shadow fading margin = sigma * norm.ppf(coverage_probability).

        Uses 3GPP TR 38.901 Table 7.4.2-1 sigma values per scenario.
        For combined LOS/NLOS, uses NLOS sigma (conservative).
        """
        try:
            from scipy.stats import norm
        except ImportError:
            import math
            # Approximate norm.ppf for common values
            z_approx = {0.85: 1.036, 0.90: 1.282, 0.95: 1.645, 0.98: 2.054, 0.99: 2.326, 0.999: 3.090}
            z = z_approx.get(coverage_probability, 1.645)
            sigma = self.get_sf_sigma(scenario, los_condition)
            return round(sigma * z, 1)

        sigma = self.get_sf_sigma(scenario, los_condition)
        z = norm.ppf(coverage_probability)
        return round(sigma * z, 1)

    def get_sigma(self, obstacle_density: str) -> float:
        density_map = {"heavy": "urban_heavy", "medium": "urban", "light": "urban_light"}
        json_key = density_map.get(obstacle_density, obstacle_density)
        if json_key not in self._densities:
            raise ValueError(f"Unknown density: {obstacle_density}")
        return self._densities[json_key]["sf_db"]