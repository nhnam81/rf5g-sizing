"""Antenna pattern module — import and manage directional antenna patterns.

Supports:
- Built-in patterns: Omni, Panel 120°, Panel 65°, Panel 90°, BF 30°, BF 60°
- Atoll .ant format import
- CSV format import (azimuth, gain_db columns)
- JSON format import

Coordinate system: WGS84 (EPSG:4326)
Azimuth: 0° = North, 90° = East, 180° = South, 270° = West
Elevation: 0° = Horizon, positive = up

Pattern types:
- Omnidirectional: equal gain all azimuths
- Sector (Panel): 120°, 65°, 90° beamwidth
- Beamforming: narrow 30° or 60° beam with high gain
- Custom: imported from datasheet/atoll file
"""
from __future__ import annotations
import json
import math
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class AntennaPattern:
    """Antenna radiation pattern.

    Attributes:
        name: Pattern name (e.g. "Panel_120deg", "Omni")
        pattern_type: "omni", "sector", "beamforming", "custom"
        frequency_mhz: Center frequency in MHz
        gain_max_dbi: Peak gain in dBi
        horizontal_pattern: Dict of azimuth_deg -> relative_gain_dB (0-360°, 1° resolution)
        vertical_pattern: Dict of elevation_deg -> relative_gain_dB (-90 to 90°, 1° resolution)
        beamwidth_h_deg: Horizontal 3dB beamwidth in degrees
        beamwidth_v_deg: Vertical 3dB beamwidth in degrees
        front_to_back_db: Front-to-back ratio in dB
        tilt_deg: Electrical downtilt in degrees
        source: "built-in", "atoll", "csv", "json"
    """
    name: str
    pattern_type: str  # "omni", "sector", "beamforming", "custom"
    frequency_mhz: float = 3500.0
    gain_max_dbi: float = 0.0
    horizontal_pattern: dict[int, float] = field(default_factory=dict)
    vertical_pattern: dict[int, float] = field(default_factory=dict)
    beamwidth_h_deg: float = 360.0
    beamwidth_v_deg: float = 90.0
    front_to_back_db: float = 0.0
    tilt_deg: float = 0.0
    source: str = "built-in"

    def gain_at_azimuth(self, azimuth_deg: float) -> float:
        """Get total gain (dBi) at given azimuth angle.

        Args:
            azimuth_deg: Azimuth in degrees (0=North, 90=East)

        Returns:
            Gain in dBi (gain_max + relative pattern gain)
        """
        if self.pattern_type == "omni":
            return self.gain_max_dbi

        az = int(azimuth_deg % 360)
        if az in self.horizontal_pattern:
            return self.gain_max_dbi + self.horizontal_pattern[az]
        # Interpolate
        az_low = az
        az_high = (az + 1) % 360
        gain_low = self.horizontal_pattern.get(az_low, -60.0)
        gain_high = self.horizontal_pattern.get(az_high, -60.0)
        frac = azimuth_deg - int(azimuth_deg)
        return self.gain_max_dbi + gain_low + frac * (gain_high - gain_low)

    def gain_at_elevation(self, elevation_deg: float) -> float:
        """Get relative gain at given elevation angle.

        Args:
            elevation_deg: Elevation in degrees (0=horizon, positive=up)

        Returns:
            Relative gain in dB (0 at peak)
        """
        el = int(elevation_deg)
        if el in self.vertical_pattern:
            return self.vertical_pattern[el]
        # Interpolate
        el_low = el
        el_high = el + 1
        gain_low = self.vertical_pattern.get(el_low, -30.0)
        gain_high = self.vertical_pattern.get(el_high, -30.0)
        frac = elevation_deg - int(elevation_deg)
        return gain_low + frac * (gain_high - gain_low)

    def gain_at(self, azimuth_deg: float, elevation_deg: float = 0.0) -> float:
        """Get total gain at given azimuth and elevation.

        Returns: Total gain in dBi = gain_max + h_pattern(az) + v_pattern(el)
        """
        return self.gain_at_azimuth(azimuth_deg) + self.gain_at_elevation(elevation_deg)

    def coverage_angles(self, threshold_db: float = -3.0) -> list[tuple[float, float]]:
        """Get azimuth angles where gain >= gain_max + threshold.

        Args:
            threshold_db: Threshold below max gain (default -3 dB for beamwidth)

        Returns:
            List of (start_angle, end_angle) tuples where gain is above threshold
        """
        if self.pattern_type == "omni":
            return [(0, 360)]

        angles = []
        in_coverage = False
        start = 0
        for az in range(361):
            az_mod = az % 360
            gain = self.horizontal_pattern.get(az_mod, -60.0)
            if gain >= threshold_db and not in_coverage:
                start = az_mod
                in_coverage = True
            elif gain < threshold_db and in_coverage:
                angles.append((start, az_mod))
                in_coverage = False
        if in_coverage:
            angles.append((start, 360))

        return angles if angles else [(0, 360)]


# ── Built-in Patterns ──

def _cosine_pattern(beamwidth_deg: float, front_to_back_db: float = 25.0,
                    resolution: int = 1) -> dict[int, float]:
    """Generate cosine-shaped horizontal pattern.

    Args:
        beamwidth_deg: 3dB beamwidth in degrees
        front_to_back_db: Front-to-back ratio in dB
        resolution: Degree resolution (1 = 1° steps)

    Returns:
        Dict of azimuth -> relative gain (dB), peak = 0 dB at 0°
    """
    pattern = {}
    half_bw = beamwidth_deg / 2

    for az in range(0, 360, resolution):
        angle = az
        if angle > 180:
            angle = 360 - angle

        if angle <= half_bw:
            # Main lobe: cosine shape
            # At half_bw, gain = -3 dB
            cos_val = math.cos(math.pi / 2 * angle / half_bw)
            gain = 20 * math.log10(max(cos_val, 1e-10))
            pattern[az] = round(max(gain, -60.0), 1)
        else:
            # Side/back lobes
            # Gradual roll-off to front-to-back ratio
            back_gain = -front_to_back_db
            # Add small side lobes
            side_lobe_level = min(-20.0, -front_to_back_db + 5)
            if 90 < angle < 150:
                pattern[az] = round(side_lobe_level + 3 * math.cos(math.radians(angle * 3)), 1)
            else:
                pattern[az] = round(back_gain, 1)

    return pattern


def _vertical_pattern(beamwidth_v_deg: float = 15.0, downtilt_deg: float = 0.0,
                      resolution: int = 1) -> dict[int, float]:
    """Generate vertical pattern (simplified).

    Args:
        beamwidth_v_deg: Vertical 3dB beamwidth in degrees
        downtilt_deg: Electrical downtilt in degrees
        resolution: Degree resolution

    Returns:
        Dict of elevation -> relative gain (dB)
    """
    pattern = {}
    half_bw = beamwidth_v_deg / 2

    for el in range(-90, 91, resolution):
        # Shift by downtilt
        shifted_el = el - downtilt_deg
        if abs(shifted_el) <= half_bw:
            cos_val = math.cos(math.pi / 2 * shifted_el / half_bw)
            gain = 20 * math.log10(max(cos_val, 1e-10))
            pattern[el] = round(max(gain, -30.0), 1)
        elif abs(shifted_el) <= 2 * half_bw:
            # First side lobe
            pattern[el] = round(-15.0, 1)
        else:
            pattern[el] = round(-30.0, 1)

    return pattern


# ── Built-in Pattern Library ──

BUILTIN_PATTERNS: dict[str, AntennaPattern] = {
    "omni": AntennaPattern(
        name="Omnidirectional",
        pattern_type="omni",
        gain_max_dbi=2.0,  # Typical omni dipole
        beamwidth_h_deg=360.0,
        beamwidth_v_deg=90.0,
        front_to_back_db=0.0,
        horizontal_pattern={az: 0.0 for az in range(360)},
        vertical_pattern={el: 0.0 for el in range(-90, 91)},
        source="built-in",
    ),
    "panel_120": AntennaPattern(
        name="Panel 120° (3-sector macro)",
        pattern_type="sector",
        gain_max_dbi=17.0,
        beamwidth_h_deg=120.0,
        beamwidth_v_deg=15.0,
        front_to_back_db=25.0,
        horizontal_pattern=_cosine_pattern(120, 25.0),
        vertical_pattern=_vertical_pattern(15.0),
        source="built-in",
    ),
    "panel_65": AntennaPattern(
        name="Panel 65° (6-sector / high-gain)",
        pattern_type="sector",
        gain_max_dbi=20.0,
        beamwidth_h_deg=65.0,
        beamwidth_v_deg=10.0,
        front_to_back_db=30.0,
        horizontal_pattern=_cosine_pattern(65, 30.0),
        vertical_pattern=_vertical_pattern(10.0),
        source="built-in",
    ),
    "panel_90": AntennaPattern(
        name="Panel 90° (4-sector)",
        pattern_type="sector",
        gain_max_dbi=18.0,
        beamwidth_h_deg=90.0,
        beamwidth_v_deg=12.0,
        front_to_back_db=28.0,
        horizontal_pattern=_cosine_pattern(90, 28.0),
        vertical_pattern=_vertical_pattern(12.0),
        source="built-in",
    ),
    "bf_30": AntennaPattern(
        name="Beamforming 30° (MU-MIMO)",
        pattern_type="beamforming",
        gain_max_dbi=25.0,
        beamwidth_h_deg=30.0,
        beamwidth_v_deg=8.0,
        front_to_back_db=35.0,
        horizontal_pattern=_cosine_pattern(30, 35.0),
        vertical_pattern=_vertical_pattern(8.0),
        source="built-in",
    ),
    "bf_60": AntennaPattern(
        name="Beamforming 60° (SU-MIMO)",
        pattern_type="beamforming",
        gain_max_dbi=22.0,
        beamwidth_h_deg=60.0,
        beamwidth_v_deg=10.0,
        front_to_back_db=30.0,
        horizontal_pattern=_cosine_pattern(60, 30.0),
        vertical_pattern=_vertical_pattern(10.0),
        source="built-in",
    ),
}

# Map antenna configs to built-in patterns
ANTENNA_CONFIG_PATTERN_MAP: dict[str, str] = {
    "2T2R": "omni",     # Basic MIMO → omni
    "4T4R": "panel_120",  # Standard macro → 120° sector
    "8T8R": "panel_120",  # High-gain macro → 120° sector
    "16T16R": "panel_65",  # Massive MIMO → 65° sector
    "32T32R": "bf_60",   # MU-MIMO → 60° BF
    "64T64R": "bf_30",   # Premium MU-MIMO → 30° BF
}


def derive_site_geometry_mode(sectors: int, pattern: AntennaPattern) -> str:
    """Classify the effective site geometry from sector count and pattern shape."""
    if sectors == 1:
        return "omni_360" if pattern.pattern_type == "omni" or pattern.beamwidth_h_deg >= 359 else "directional_1_sector"
    if sectors >= 6:
        return "sector_6"
    return "sector_3"


# ── Atoll .ant File Parser ──

def parse_atoll_ant(filepath: str) -> AntennaPattern:
    """Parse Atoll .ant antenna pattern file.

    Atoll .ant format:
    ```
    NAME AntennaName
    FREQUENCY 3500
    GAIN 17.0
    HORIZONTAL 0 0.0 1 -0.5 ... 359 -0.5
    VERTICAL -90 -30.0 -89 -29.5 ... 90 0.0
    TILT 0
    ```

    Args:
        filepath: Path to .ant file

    Returns:
        AntennaPattern with parsed data
    """
    name = os.path.basename(filepath).replace(".ant", "")
    freq_mhz = 3500.0
    gain_max = 0.0
    h_pattern = {}
    v_pattern = {}
    tilt = 0.0

    with open(filepath, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("NAME") or line.startswith("name"):
                name = line.split(None, 1)[1] if len(line.split()) > 1 else name
            elif line.startswith("FREQUENCY") or line.startswith("frequency"):
                try:
                    freq_mhz = float(line.split()[1])
                except (IndexError, ValueError):
                    pass
            elif line.startswith("GAIN") or line.startswith("gain"):
                try:
                    gain_max = float(line.split()[1])
                except (IndexError, ValueError):
                    pass
            elif line.startswith("HORIZONTAL") or line.startswith("horizontal"):
                parts = line.split()[1:]
                for i in range(0, len(parts) - 1, 2):
                    try:
                        az = int(parts[i]) % 360
                        gain = float(parts[i + 1])
                        h_pattern[az] = gain
                    except (ValueError, IndexError):
                        pass
            elif line.startswith("VERTICAL") or line.startswith("vertical"):
                parts = line.split()[1:]
                for i in range(0, len(parts) - 1, 2):
                    try:
                        el = int(parts[i])
                        gain = float(parts[i + 1])
                        v_pattern[el] = gain
                    except (ValueError, IndexError):
                        pass
            elif line.startswith("TILT") or line.startswith("tilt"):
                try:
                    tilt = float(line.split()[1])
                except (IndexError, ValueError):
                    pass

    # Determine beamwidth from pattern
    beamwidth_h = _calc_beamwidth(h_pattern)
    beamwidth_v = _calc_beamwidth(v_pattern, is_vertical=True)
    front_to_back = _calc_front_to_back(h_pattern)

    # Determine pattern type
    if beamwidth_h >= 350:
        ptype = "omni"
    elif beamwidth_h <= 45:
        ptype = "beamforming"
    else:
        ptype = "custom"

    return AntennaPattern(
        name=name,
        pattern_type=ptype,
        frequency_mhz=freq_mhz,
        gain_max_dbi=gain_max,
        horizontal_pattern=h_pattern,
        vertical_pattern=v_pattern,
        beamwidth_h_deg=beamwidth_h,
        beamwidth_v_deg=beamwidth_v,
        front_to_back_db=front_to_back,
        tilt_deg=tilt,
        source="atoll",
    )


# ── CSV Parser ──

def parse_csv_pattern(filepath: str) -> AntennaPattern:
    """Parse CSV antenna pattern file.

    Expected format:
    ```
    azimuth,gain_db
    0,0.0
    1,-0.1
    ...
    359,-0.5
    ```

    Or with vertical:
    ```
    azimuth,gain_db,elevation,vert_gain_db
    0,0.0,-90,-30.0
    ...
    ```

    Args:
        filepath: Path to CSV file

    Returns:
        AntennaPattern
    """
    import csv

    name = os.path.basename(filepath).replace(".csv", "")
    h_pattern = {}
    v_pattern = {}

    with open(filepath, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)

        has_vertical = len(header) >= 4 if header else False

        for row in reader:
            try:
                if len(row) >= 2:
                    az = int(float(row[0])) % 360
                    gain = float(row[1])
                    h_pattern[az] = gain
                if has_vertical and len(row) >= 4:
                    el = int(float(row[2]))
                    v_gain = float(row[3])
                    v_pattern[el] = v_gain
            except (ValueError, IndexError):
                pass

    beamwidth_h = _calc_beamwidth(h_pattern)
    beamwidth_v = _calc_beamwidth(v_pattern, is_vertical=True)
    front_to_back = _calc_front_to_back(h_pattern)

    if beamwidth_h >= 350:
        ptype = "omni"
    elif beamwidth_h <= 45:
        ptype = "beamforming"
    else:
        ptype = "custom"

    return AntennaPattern(
        name=name,
        pattern_type=ptype,
        gain_max_dbi=max(h_pattern.values()) if h_pattern else 0.0,
        horizontal_pattern=h_pattern,
        vertical_pattern=v_pattern,
        beamwidth_h_deg=beamwidth_h,
        beamwidth_v_deg=beamwidth_v,
        front_to_back_db=front_to_back,
        source="csv",
    )


# ── JSON Parser ──

def parse_json_pattern(filepath: str) -> AntennaPattern:
    """Parse JSON antenna pattern file.

    Expected format:
    ```json
    {
        "name": "Custom_5G",
        "frequency_mhz": 3500,
        "gain_max_dbi": 18.5,
        "beamwidth_h_deg": 65,
        "beamwidth_v_deg": 10,
        "front_to_back_db": 30,
        "tilt_deg": 6,
        "horizontal_pattern": {"0": 0.0, "1": -0.1, ...},
        "vertical_pattern": {"-10": -3.0, ...}
    }
    ```

    Args:
        filepath: Path to JSON file

    Returns:
        AntennaPattern
    """
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    h_pattern = {int(k): v for k, v in data.get("horizontal_pattern", {}).items()}
    v_pattern = {int(k): v for k, v in data.get("vertical_pattern", {}).items()}

    if not h_pattern:
        # Generate from beamwidth
        bw = data.get("beamwidth_h_deg", 120)
        ftb = data.get("front_to_back_db", 25)
        h_pattern = _cosine_pattern(bw, ftb)

    if not v_pattern:
        bw_v = data.get("beamwidth_v_deg", 15)
        tilt = data.get("tilt_deg", 0)
        v_pattern = _vertical_pattern(bw_v, tilt)

    return AntennaPattern(
        name=data.get("name", os.path.basename(filepath)),
        pattern_type=data.get("pattern_type", "custom"),
        frequency_mhz=data.get("frequency_mhz", 3500),
        gain_max_dbi=data.get("gain_max_dbi", 0.0),
        horizontal_pattern=h_pattern,
        vertical_pattern=v_pattern,
        beamwidth_h_deg=data.get("beamwidth_h_deg", _calc_beamwidth(h_pattern)),
        beamwidth_v_deg=data.get("beamwidth_v_deg", _calc_beamwidth(v_pattern, True)),
        front_to_back_db=data.get("front_to_back_db", _calc_front_to_back(h_pattern)),
        tilt_deg=data.get("tilt_deg", 0.0),
        source="json",
    )


# ── Helper Functions ──

def _calc_beamwidth(pattern: dict, is_vertical: bool = False) -> float:
    """Calculate 3dB beamwidth from pattern dict."""
    if not pattern:
        return 360.0 if not is_vertical else 90.0

    # Find peak
    peak_gain = max(pattern.values())
    threshold = peak_gain - 3.0

    # Find angles above threshold
    above = [az for az, gain in pattern.items() if gain >= threshold]
    if not above:
        return 360.0 if not is_vertical else 90.0

    return float(max(above) - min(above))


def _calc_front_to_back(pattern: dict) -> float:
    """Calculate front-to-back ratio from horizontal pattern."""
    if not pattern:
        return 0.0

    peak = max(pattern.values())
    back = pattern.get(180, -60.0)
    return round(peak - back, 1)


def get_pattern(pattern_name: str) -> AntennaPattern:
    """Get antenna pattern by name or file path.

    Args:
        pattern_name: Built-in name ("omni", "panel_120", etc.) or file path (.ant, .csv, .json, .msi, .txt)

    Returns:
        AntennaPattern
    """
    # Check built-in
    if pattern_name in BUILTIN_PATTERNS:
        return BUILTIN_PATTERNS[pattern_name]

    # Check file path
    if os.path.isfile(pattern_name):
        ext = os.path.splitext(pattern_name)[1].lower()
        if ext == ".ant":
            return parse_atoll_ant(pattern_name)
        elif ext == ".csv":
            return parse_csv_pattern(pattern_name)
        elif ext == ".json":
            return parse_json_pattern(pattern_name)
        elif ext == ".msi":
            return parse_msi_pattern(pattern_name)
        elif ext == ".txt":
            return parse_atoll_txt(pattern_name)
        else:
            raise ValueError(f"Unsupported file format: {ext}. Use .ant, .csv, .json, .msi, or .txt")

    # Check antenna config mapping
    if pattern_name in ANTENNA_CONFIG_PATTERN_MAP:
        return BUILTIN_PATTERNS[ANTENNA_CONFIG_PATTERN_MAP[pattern_name]]

    raise ValueError(
        f"Unknown pattern: {pattern_name}. "
        f"Built-in: {list(BUILTIN_PATTERNS.keys())}. "
        f"Or provide file path (.ant, .csv, .json, .msi, .txt)"
    )


def pattern_for_config(antenna_config: str) -> AntennaPattern:
    """Get the default antenna pattern for a given antenna config.

    Args:
        antenna_config: e.g. "32T32R", "64T64R", "4T4R"

    Returns:
        AntennaPattern
    """
    pattern_name = ANTENNA_CONFIG_PATTERN_MAP.get(antenna_config, "panel_120")
    return BUILTIN_PATTERNS[pattern_name]


# ── Coverage Shape Generation ──

def coverage_polygon(
    center_lat: float,
    center_lon: float,
    radius_km: float,
    pattern: AntennaPattern,
    azimuth_deg: float = 0.0,
    n_points: int = 360,
    gain_threshold_db: float = -10.0,
    null_radius_fraction: float = 0.05,
) -> list[tuple[float, float]]:
    """Generate coverage polygon based on antenna pattern.

    Creates a directional coverage shape where the radius varies by azimuth
    based on the antenna gain pattern. Uses haversine for accurate WGS84.

    For sector antennas, produces a wedge shape clipped at the -10dB beamwidth.
    Angles well outside the main beam use minimal radius to avoid circular
    artifacts from back/side lobes in the MSI pattern.

    Args:
        center_lat: Site latitude (WGS84)
        center_lon: Site longitude (WGS84)
        radius_km: Maximum coverage radius in km (at peak gain)
        pattern: AntennaPattern to apply
        azimuth_deg: Sector azimuth in degrees (0=North, 90=East)
        n_points: Number of polygon points
        gain_threshold_db: Minimum gain threshold for coverage (dB below peak)
        null_radius_fraction: Radius fraction for angles outside threshold

    Returns:
        List of (lat, lon) tuples forming coverage polygon (WGS84)
    """
    if pattern.pattern_type == "omni":
        # Circle for omnidirectional
        points = []
        for i in range(n_points):
            angle = 2 * math.pi * i / n_points
            dlat = radius_km * math.cos(angle) / 111.0
            dlon = radius_km * math.sin(angle) / (111.0 * math.cos(math.radians(center_lat)))
            points.append((center_lat + dlat, center_lon + dlon))
        return points

    # Directional: vary radius by azimuth
    points = []
    peak_gain = pattern.gain_max_dbi
    null_radius = radius_km * null_radius_fraction

    for i in range(n_points):
        bearing = 360.0 * i / n_points

        pattern_az = (bearing - azimuth_deg) % 360
        gain = pattern.gain_at_azimuth(pattern_az)
        relative_gain = gain - peak_gain

        if relative_gain < gain_threshold_db:
            # Well outside main beam: use minimal radius (near-zero)
            effective_radius = null_radius
        else:
            # Inside main beam: scale radius by gain
            effective_radius = radius_km * 10 ** (relative_gain / 70)
            effective_radius = max(effective_radius, null_radius)

        dlat = effective_radius * math.cos(math.radians(bearing)) / 111.0
        dlon = effective_radius * math.sin(math.radians(bearing)) / (111.0 * math.cos(math.radians(center_lat)))
        points.append((center_lat + dlat, center_lon + dlon))

    return points


def sector_coverage_polygon(
    center_lat: float,
    center_lon: float,
    radius_km: float,
    pattern: AntennaPattern,
    azimuth_deg: float = 0.0,
    n_points: int = 360,
) -> list[tuple[float, float]]:
    """Generate sector coverage polygon (simplified: wedge shape).

    For 3-sector sites, azimuths are 0°, 120°, 240°.
    For 6-sector sites, azimuths are 0°, 60°, 120°, 180°, 240°, 300°.
    """
    return coverage_polygon(
        center_lat, center_lon, radius_km, pattern, azimuth_deg, n_points,
        gain_threshold_db=-10.0,
    )


# ── MSI Pattern Parser ──

def parse_msi_pattern(filepath: str) -> AntennaPattern:
    """Parse MSI antenna pattern file (Kathrein/ERICSSON format).

    MSI format has header fields then HORIZONTAL 360 section:
    NAME AntennaName
    FREQUENCY 3500
    GAIN dBi 17.8
    HORIZONTAL 360
    0 0.0
    1 -0.1
    ...
    """
    name = os.path.basename(filepath).replace(".txt", "").replace(".msi", "")
    freq_mhz = 3500.0
    gain_max = 0.0
    h_pattern = {}
    h_bw = 360.0
    v_bw = 90.0
    tilt = 0.0
    ftb = 25.0
    in_horizontal = False

    with open(filepath, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.upper().startswith("HORIZONTAL"):
                in_horizontal = True
                continue
            elif line.upper().startswith("VERTICAL"):
                in_horizontal = False
                continue
            if in_horizontal:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        az = int(float(parts[0])) % 360
                        gain = float(parts[1])
                        h_pattern[az] = gain
                    except (ValueError, IndexError):
                        pass
                continue
            upper = line.upper()
            if upper.startswith("NAME"):
                rest = line.split(None, 1)
                if len(rest) > 1:
                    name = rest[1].strip()
            elif upper.startswith("FREQUENCY"):
                try:
                    freq_mhz = float(line.split()[1])
                except (IndexError, ValueError):
                    pass
            elif "GAIN" in upper and ("DBI" in upper or "DBD" in upper):
                # "GAIN dBi 17.8" / "GAIN 7.35 dBd"
                parts = line.split()
                for p in parts:
                    try:
                        val = float(p)
                        gain_max = val + 2.15 if "DBD" in upper else val
                        break
                    except ValueError:
                        continue
            elif "GAIN" in upper:
                # Fallback: any GAIN line with a number
                parts = line.split()
                if gain_max == 0.0:  # Only if not already parsed
                    for p in parts:
                        try:
                            gain_max = float(p)
                            break
                        except ValueError:
                            continue
            elif upper.startswith("H_WIDTH"):
                parts = line.split()
                if len(parts) > 1:
                    try:
                        h_bw = float(parts[1])
                    except ValueError:
                        pass  # Keep default, will calc from pattern
            elif upper.startswith("V_WIDTH"):
                parts = line.split()
                if len(parts) > 1:
                    try:
                        v_bw = float(parts[1])
                    except ValueError:
                        pass
            elif upper.startswith("TILT"):
                parts = line.split()
                if len(parts) > 1:
                    try:
                        tilt = float(parts[1])
                    except ValueError:
                        pass  # TILT might be "ELECTRICAL" or empty

    if h_pattern:
        # MSI patterns: 0 dB = boresight, values are relative gain
        # If max gain is far from 0, normalize so peak = 0 dB
        max_gain = max(h_pattern.values())
        if abs(max_gain) > 5:  # Likely absolute/offset pattern
            h_pattern = {az: gain - max_gain for az, gain in h_pattern.items()}
        calc_bw = _calc_beamwidth(h_pattern)
        # Use pattern-calculated BW if header H_WIDTH was empty/invalid
        # but keep header H_WIDTH if it was valid (e.g. 84.33 from MSI header)
        if calc_bw > 0:
            # Pattern gives valid BW — but only use if header didn't have one
            if h_bw <= 0 or h_bw == 360.0:
                h_bw = calc_bw
        elif h_bw <= 0:
            # Pattern BW calc failed, but header had no value — use 65° default
            h_bw = 65.0
        # If h_bw was set from header (e.g. 84.33), keep it
        ftb = _calc_front_to_back(h_pattern)

    ptype = "omni" if h_bw >= 350 else ("beamforming" if h_bw <= 45 else "custom")

    return AntennaPattern(
        name=name,
        pattern_type=ptype,
        frequency_mhz=freq_mhz,
        gain_max_dbi=gain_max,
        horizontal_pattern=h_pattern if h_pattern else _cosine_pattern(h_bw, ftb),
        vertical_pattern=_vertical_pattern(v_bw, tilt),
        beamwidth_h_deg=h_bw,
        beamwidth_v_deg=v_bw,
        front_to_back_db=ftb,
        tilt_deg=tilt,
        source="msi",
    )


# ── Atoll Tab-Separated Parser ──

def parse_atoll_txt(filepath: str, antenna_name: str = None, freq_mhz: float = None) -> AntennaPattern:
    """Parse Atoll tab-separated antenna file.

    Supports files where the main radiation pattern is stored inline in a
    dedicated `Pattern` column, together with beamwidth / tilt metadata.
    """
    rows = []
    fallback_name = antenna_name or os.path.basename(filepath).replace(".txt", "")

    with open(filepath, encoding="utf-8", errors="ignore") as f:
        header = f.readline().strip().split("\t")
        index_map = {col.lower().strip(): idx for idx, col in enumerate(header)}

        def _find_idx(*candidates: str):
            for idx, col in enumerate(header):
                cl = col.lower().strip()
                if any(candidate in cl for candidate in candidates):
                    return idx
            return None

        name_idx = _find_idx("name")
        gain_idx = _find_idx("gain")
        pattern_idx = _find_idx("pattern")
        beam_idx = _find_idx("beamwidth")
        h_idx = _find_idx("h_width")
        v_idx = _find_idx("v_width")
        freq_idx = _find_idx("frequency")
        ftb_idx = _find_idx("front_to_back")
        tilt_idx = _find_idx("tilt")

        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            cols = raw_line.rstrip("\n").split("\t")
            row_name = cols[name_idx].strip() if name_idx is not None and len(cols) > name_idx else fallback_name
            pattern_raw = cols[pattern_idx].strip() if pattern_idx is not None and len(cols) > pattern_idx else ""
            if antenna_name and antenna_name.lower() not in row_name.lower():
                continue
            row_freq = None
            if freq_idx is not None and len(cols) > freq_idx:
                try:
                    row_freq = float(cols[freq_idx])
                except ValueError:
                    row_freq = None
            row = {
                "name": row_name,
                "gain": None,
                "pattern": _parse_pattern_string(pattern_raw),
                "beamwidth": None,
                "h_bw": None,
                "v_bw": None,
                "freq_mhz": row_freq,
                "ftb": None,
                "tilt": None,
            }
            if gain_idx is not None and len(cols) > gain_idx:
                try:
                    row["gain"] = float(cols[gain_idx])
                except ValueError:
                    pass
            if beam_idx is not None and len(cols) > beam_idx:
                try:
                    row["beamwidth"] = float(cols[beam_idx])
                except ValueError:
                    pass
            if h_idx is not None and len(cols) > h_idx:
                try:
                    row["h_bw"] = float(cols[h_idx])
                except ValueError:
                    pass
            if v_idx is not None and len(cols) > v_idx:
                try:
                    row["v_bw"] = float(cols[v_idx])
                except ValueError:
                    pass
            if ftb_idx is not None and len(cols) > ftb_idx:
                try:
                    row["ftb"] = float(cols[ftb_idx])
                except ValueError:
                    pass
            if tilt_idx is not None and len(cols) > tilt_idx:
                try:
                    row["tilt"] = float(cols[tilt_idx])
                except ValueError:
                    pass
            rows.append(row)

    if not rows:
        raise ValueError(f"No antenna rows found in {filepath}")

    if freq_mhz is not None:
        selected = min(rows, key=lambda row: abs((row["freq_mhz"] or freq_mhz) - freq_mhz))
    else:
        selected = rows[0]

    name = selected["name"]
    gain_max = selected["gain"] or 0.0
    h_pattern = selected["pattern"]
    h_bw = selected["h_bw"] or selected["beamwidth"] or 65.0
    v_bw = selected["v_bw"] or 10.0
    ftb = selected["ftb"] or 25.0
    tilt = selected["tilt"] or 0.0
    resolved_freq = selected["freq_mhz"] or freq_mhz or 3500.0

    if h_pattern:
        calc_bw = _calc_beamwidth(h_pattern)
        if calc_bw and calc_bw < 350:
            h_bw = calc_bw
        ftb = _calc_front_to_back(h_pattern)

    ptype = "omni" if h_bw >= 350 else ("beamforming" if h_bw <= 45 else "custom")
    return AntennaPattern(
        name=name,
        pattern_type=ptype,
        frequency_mhz=resolved_freq,
        gain_max_dbi=gain_max,
        horizontal_pattern=h_pattern if h_pattern else _cosine_pattern(h_bw, ftb),
        vertical_pattern=_vertical_pattern(v_bw, tilt),
        beamwidth_h_deg=h_bw,
        beamwidth_v_deg=v_bw,
        front_to_back_db=ftb,
        tilt_deg=tilt,
        source="atoll",
    )


# ── Product Catalog Loader ──

CATALOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "radio_antenna_catalog.json"
)
PATTERN_ASSET_ROOTS = [
    Path(os.path.dirname(CATALOG_PATH)) / "patterns",
    Path.home() / "Downloads" / "42. Radio and Antenna" / "Antenna Products",
]


def _normalize_pattern_relpath(path_value: str) -> str:
    return path_value.replace("\\", "/").strip()


def _resolve_pattern_asset(path_value: str | None, expect_dir: bool = False) -> Optional[Path]:
    if not path_value:
        return None
    normalized = _normalize_pattern_relpath(path_value)
    raw_path = Path(normalized)
    candidate_paths = []
    if raw_path.is_absolute():
        candidate_paths.append(raw_path)
    else:
        candidate_paths.append(Path(normalized))
        for root in PATTERN_ASSET_ROOTS:
            candidate_paths.append(root / normalized)
            candidate_paths.append(root / Path(normalized).name)
    for candidate in candidate_paths:
        if expect_dir and candidate.is_dir():
            return candidate
        if not expect_dir and candidate.is_file():
            return candidate
    return None


def _pick_msi_file(directory: Path, freq_mhz: float | None = None) -> Optional[Path]:
    files = sorted(p for p in directory.rglob("*") if p.suffix.lower() in {".msi", ".txt"})
    if not files:
        return None
    if freq_mhz is None:
        return files[0]

    def score(path: Path) -> tuple[float, int, str]:
        nums = [int(token) for token in ''.join(ch if ch.isdigit() else ' ' for ch in path.stem).split() if token.isdigit()]
        freq_candidates = [num for num in nums if 500 <= num <= 7000]
        freq_score = min((abs(num - freq_mhz) for num in freq_candidates), default=10_000.0)
        ext_priority = 0 if path.suffix.lower() == ".msi" else 1
        return (freq_score, ext_priority, str(path))

    return min(files, key=score)


def _parse_pattern_string(raw: str) -> dict[int, float]:
    tokens = raw.replace(",", " ").split()
    if len(tokens) >= 6 and tokens[0] in {"2", "3"} and tokens[3] in {"360", "361"}:
        tokens = tokens[4:]
    pattern = {}
    idx = 0
    while idx + 1 < len(tokens):
        try:
            az = int(float(tokens[idx])) % 360
            gain = float(tokens[idx + 1])
            pattern[az] = gain
            idx += 2
        except ValueError:
            idx += 1
    return pattern


def _merge_catalog_pattern(pattern: AntennaPattern, ant: dict, freq_mhz: float | None, gain_dbi: float, h_bw: float, v_bw: float, ftb: float, tilt_deg: float) -> AntennaPattern:
    merged = AntennaPattern(
        name=f"{ant['vendor']} {ant['model']}",
        pattern_type=pattern.pattern_type,
        frequency_mhz=freq_mhz or pattern.frequency_mhz,
        gain_max_dbi=gain_dbi if gain_dbi is not None else pattern.gain_max_dbi,
        horizontal_pattern=pattern.horizontal_pattern or _cosine_pattern(h_bw, ftb),
        vertical_pattern=pattern.vertical_pattern or _vertical_pattern(v_bw, tilt_deg),
        beamwidth_h_deg=h_bw or pattern.beamwidth_h_deg,
        beamwidth_v_deg=v_bw or pattern.beamwidth_v_deg,
        front_to_back_db=ftb or pattern.front_to_back_db,
        tilt_deg=tilt_deg,
        source=f"catalog:{pattern.source}",
    )
    if merged.pattern_type == "omni" and merged.beamwidth_h_deg < 359:
        merged.pattern_type = "custom"
    return merged


def _load_catalog_pattern_asset(ant: dict, freq_mhz: float | None, gain_dbi: float, h_bw: float, v_bw: float, ftb: float, tilt_deg: float) -> Optional[AntennaPattern]:
    source_type = (ant.get("pattern_source_type") or ant.get("pattern_type") or "").lower()
    pattern_asset = ant.get("pattern_asset") or ant.get("atoll_file") or ant.get("pattern_file")

    if "atoll" in source_type and pattern_asset:
        asset = _resolve_pattern_asset(pattern_asset)
        if asset is not None:
            pattern = parse_atoll_txt(str(asset), freq_mhz=freq_mhz)
            return _merge_catalog_pattern(pattern, ant, freq_mhz, gain_dbi, h_bw, v_bw, ftb, tilt_deg)

    if source_type in {"msi", "msi_file"} and pattern_asset:
        asset = _resolve_pattern_asset(pattern_asset)
        if asset is not None:
            pattern = parse_msi_pattern(str(asset))
            return _merge_catalog_pattern(pattern, ant, freq_mhz, gain_dbi, h_bw, v_bw, ftb, tilt_deg)

    if source_type == "msi_dir" or ant.get("msi_dir"):
        asset_dir = _resolve_pattern_asset(ant.get("msi_dir") or pattern_asset, expect_dir=True)
        if asset_dir is not None:
            asset = _pick_msi_file(asset_dir, freq_mhz=freq_mhz)
            if asset is not None:
                pattern = parse_msi_pattern(str(asset))
                return _merge_catalog_pattern(pattern, ant, freq_mhz, gain_dbi, h_bw, v_bw, ftb, tilt_deg)

    if source_type == "atoll_ant" and pattern_asset:
        asset = _resolve_pattern_asset(pattern_asset)
        if asset is not None:
            pattern = parse_atoll_ant(str(asset))
            return _merge_catalog_pattern(pattern, ant, freq_mhz, gain_dbi, h_bw, v_bw, ftb, tilt_deg)

    if source_type == "csv" and pattern_asset:
        asset = _resolve_pattern_asset(pattern_asset)
        if asset is not None:
            pattern = parse_csv_pattern(str(asset))
            return _merge_catalog_pattern(pattern, ant, freq_mhz, gain_dbi, h_bw, v_bw, ftb, tilt_deg)

    if source_type == "json" and pattern_asset:
        asset = _resolve_pattern_asset(pattern_asset)
        if asset is not None:
            pattern = parse_json_pattern(str(asset))
            return _merge_catalog_pattern(pattern, ant, freq_mhz, gain_dbi, h_bw, v_bw, ftb, tilt_deg)

    return None


def load_catalog() -> dict:
    """Load the radio/antenna product catalog."""
    paths = [
        CATALOG_PATH,
        os.path.join(os.path.dirname(CATALOG_PATH), "..", "..", "radio_antenna_catalog.json"),
    ]
    for path in paths:
        path = os.path.normpath(path)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(f"Catalog not found. Searched: {paths}")


def catalog_antennas() -> list[dict]:
    """List all antennas in the product catalog."""
    return load_catalog()["antennas"]


def catalog_radios() -> list[dict]:
    """List all radios in the product catalog."""
    return load_catalog()["radios"]


def get_catalog_antenna(vendor: str, model: str) -> dict:
    """Get a specific antenna from the catalog (case-insensitive partial match)."""
    antennas = catalog_antennas()
    vl, ml = vendor.lower(), model.lower()
    for ant in antennas:
        if vl in ant["vendor"].lower() and ml in ant["model"].lower():
            return ant
    avail = [f"{a['vendor']} {a['model']}" for a in antennas]
    raise ValueError(f"Antenna not found: {vendor} {model}. Available: {avail}")


def get_catalog_radio(vendor: str, model: str) -> dict:
    """Get a specific radio from the catalog (case-insensitive partial match)."""
    radios = catalog_radios()
    vl, ml = vendor.lower(), model.lower()
    for radio in radios:
        if vl in radio["vendor"].lower() and ml in radio["model"].lower():
            return radio
    avail = [f"{r['vendor']} {r['model']}" for r in radios]
    raise ValueError(f"Radio not found: {vendor} {model}. Available: {avail}")


def resolve_catalog_radio_total_tx_power_w(radio: dict) -> Optional[float]:
    """Resolve total conducted TX power in watts from a catalog radio entry."""
    total_w = radio.get("max_total_power_w")
    if total_w is not None:
        return float(total_w)

    total_w = radio.get("max_power_whole_w")
    if total_w is not None:
        return float(total_w)

    total_w = radio.get("max_tx_power_w")
    if total_w is not None:
        return float(total_w)

    return None


def get_catalog_radio_total_tx_power_w(vendor: str, model: str) -> Optional[float]:
    """Get normalized total conducted TX power in watts for a catalog radio."""
    return resolve_catalog_radio_total_tx_power_w(get_catalog_radio(vendor, model))


def load_custom_pattern(
    pattern_file: str,
    pattern_format: str | None = None,
    antenna_name: str | None = None,
    freq_mhz: float | None = None,
) -> AntennaPattern:
    asset = _resolve_pattern_asset(pattern_file)
    if asset is None:
        raise FileNotFoundError(f"Pattern asset not found: {pattern_file}")

    fmt = (pattern_format or 'auto').lower()
    if fmt == 'auto':
        ext = asset.suffix.lower()
        if ext == '.ant':
            fmt = 'ant'
        elif ext == '.csv':
            fmt = 'csv'
        elif ext == '.json':
            fmt = 'json'
        elif ext == '.msi':
            fmt = 'msi'
        elif ext == '.txt':
            with asset.open(encoding='utf-8', errors='ignore') as f:
                head = ''.join(f.readline() for _ in range(3)).upper()
            fmt = 'msi' if 'HORIZONTAL' in head or head.startswith('NAME') else 'atoll_txt'
        else:
            raise ValueError(f"Unsupported custom pattern extension: {ext}")

    if fmt == 'ant':
        pattern = parse_atoll_ant(str(asset))
    elif fmt == 'csv':
        pattern = parse_csv_pattern(str(asset))
    elif fmt == 'json':
        pattern = parse_json_pattern(str(asset))
    elif fmt == 'msi':
        pattern = parse_msi_pattern(str(asset))
    elif fmt == 'atoll_txt':
        pattern = parse_atoll_txt(str(asset), antenna_name=antenna_name, freq_mhz=freq_mhz)
    else:
        raise ValueError(f"Unsupported custom pattern format: {fmt}")

    pattern.name = antenna_name or pattern.name
    pattern.frequency_mhz = freq_mhz or pattern.frequency_mhz
    pattern.source = f"custom:{fmt}"
    return pattern


def resolve_antenna_pattern(base_station, freq_mhz: float | None = None) -> AntennaPattern:
    if getattr(base_station, 'antenna_pattern_file', None):
        return load_custom_pattern(
            base_station.antenna_pattern_file,
            pattern_format=base_station.antenna_pattern_format,
            antenna_name=base_station.antenna_pattern_name,
            freq_mhz=base_station.antenna_pattern_freq_mhz or freq_mhz,
        )
    if getattr(base_station, 'antenna_vendor', None) and getattr(base_station, 'antenna_model', None):
        return antenna_pattern_from_catalog(base_station.antenna_vendor, base_station.antenna_model, freq_mhz=freq_mhz)
    return pattern_for_config(base_station.antenna_config)


def antenna_pattern_from_catalog(vendor: str, model: str, freq_mhz: float = None) -> AntennaPattern:
    """Create AntennaPattern from catalog antenna entry.

    Prefers a real imported pattern asset when catalog metadata points to one.
    Falls back to a synthesized cosine/vertical pattern when no asset exists
    or parsing fails.
    """
    ant = get_catalog_antenna(vendor, model)
    gain_dbi = ant.get("gain_dbi")
    h_bw = ant.get("h_beamwidth_deg")
    v_bw = ant.get("v_beamwidth_deg")
    ftb = ant.get("front_to_back_db", 25.0)
    tilt = ant.get("electrical_tilt_range_deg", [0, 0])
    tilt_deg = tilt[0] if isinstance(tilt, list) else 0

    # Multi-band: select subband by frequency
    subbands = ant.get("subbands", [])
    if subbands and freq_mhz:
        for sb in subbands:
            r = sb.get("range_mhz", [0, 0])
            if r[0] <= freq_mhz <= r[1]:
                gain_dbi = sb.get("gain_dbi", gain_dbi)
                h_bw = sb.get("h_beamwidth_deg", h_bw)
                v_bw = sb.get("v_beamwidth_deg", v_bw)
                ftb = sb.get("f2b_db", ftb)
                break

    # Fallback to first subband if still None
    if gain_dbi is None and subbands:
        gain_dbi = subbands[0].get("gain_dbi", 10.0)
    if h_bw is None and subbands:
        h_bw = subbands[0].get("h_beamwidth_deg", 65.0)
    if v_bw is None and subbands:
        v_bw = subbands[0].get("v_beamwidth_deg", 15.0)

    gain_dbi = gain_dbi or 10.0
    h_bw = h_bw or 65.0
    v_bw = v_bw or 15.0

    loaded = _load_catalog_pattern_asset(ant, freq_mhz, gain_dbi, h_bw, v_bw, ftb, tilt_deg)
    if loaded is not None:
        return loaded

    # Determine pattern type
    if h_bw <= 45:
        pattern_type = "beamforming"
    elif h_bw >= 350:
        pattern_type = "omni"
    else:
        pattern_type = "sector" if h_bw >= 90 else "custom"

    h_pattern = _cosine_pattern(h_bw, ftb)
    v_pattern = _vertical_pattern(v_bw, tilt_deg)

    return AntennaPattern(
        name=f"{ant['vendor']} {ant['model']}",
        pattern_type=pattern_type,
        frequency_mhz=freq_mhz or 3500.0,
        gain_max_dbi=gain_dbi,
        horizontal_pattern=h_pattern,
        vertical_pattern=v_pattern,
        beamwidth_h_deg=h_bw,
        beamwidth_v_deg=v_bw,
        front_to_back_db=ftb,
        tilt_deg=tilt_deg,
        source="catalog:synthetic",
    )


def list_catalog_models() -> dict:
    """List all available catalog models."""
    cat = load_catalog()
    return {
        "antennas": [(a["vendor"], a["model"]) for a in cat["antennas"]],
        "radios": [(r["vendor"], r["model"]) for r in cat["radios"]],
    }


@dataclass
class PatternValidationResult:
    """Result of antenna pattern validation."""
    valid: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)
    is_fallback: bool = False
    fallback_type: str = ""


def validate_antenna_pattern(pattern: AntennaPattern) -> PatternValidationResult:
    """Validate antenna pattern completeness and quality.

    Checks:
    - Pattern type consistency
    - Horizontal pattern coverage (0-360°)
    - Vertical pattern coverage (-90 to 90°)
    - Gain reasonableness
    - Beamwidth consistency
    - Front-to-back ratio

    Args:
        pattern: AntennaPattern to validate

    Returns:
        PatternValidationResult with validation status and messages
    """
    result = PatternValidationResult(valid=True)

    # Check pattern type
    valid_types = ["omni", "sector", "beamforming", "custom", "catalog:synthetic", "catalog:atoll"]
    if pattern.pattern_type not in valid_types:
        result.warnings.append(f"Unknown pattern type: {pattern.pattern_type}")

    # Check gain reasonableness
    if pattern.gain_max_dbi < -10 or pattern.gain_max_dbi > 50:
        result.warnings.append(f"Unusual gain value: {pattern.gain_max_dbi:.1f} dBi (expected -10 to 50 dBi)")

    # Check omnidirectional patterns
    if pattern.pattern_type == "omni":
        result.info.append("Omnidirectional pattern - equal gain all azimuths")
        if pattern.horizontal_pattern:
            result.warnings.append("Omnidirectional pattern should not have horizontal pattern data")
        return result

    # Check sector/beamforming patterns
    if pattern.pattern_type in ["sector", "beamforming", "custom", "catalog:synthetic", "catalog:atoll"]:
        # Check horizontal pattern coverage
        if not pattern.horizontal_pattern:
            result.errors.append("Missing horizontal pattern data")
            result.valid = False
            result.is_fallback = True
            result.fallback_type = "cosine"
            result.warnings.append("Using cosine fallback pattern - no horizontal pattern data")
        else:
            # Check azimuth coverage
            az_coverage = len(pattern.horizontal_pattern)
            if az_coverage < 360:
                result.warnings.append(f"Horizontal pattern covers only {az_coverage} azimuth values (expected 360)")

            # Check for gaps in coverage
            az_keys = sorted(pattern.horizontal_pattern.keys())
            if az_keys:
                gaps = []
                for i in range(len(az_keys) - 1):
                    if az_keys[i + 1] - az_keys[i] > 1:
                        gaps.append((az_keys[i], az_keys[i + 1]))
                if gaps:
                    result.warnings.append(f"Pattern has {len(gaps)} azimuth gaps, interpolation will be used")

            # Check for null values in main lobe
            main_lobe_gains = [pattern.horizontal_pattern.get(a, -60) for a in range(-60, 61)]
            if max(main_lobe_gains) < -10:
                result.warnings.append("Main lobe gain is very low (< -10 dB relative)")

        # Check vertical pattern
        if not pattern.vertical_pattern:
            result.info.append("No vertical pattern - using simplified vertical model")
        else:
            el_keys = sorted(pattern.vertical_pattern.keys())
            if el_keys:
                if min(el_keys) > -30 or max(el_keys) < 30:
                    result.warnings.append(f"Vertical pattern covers limited elevation range ({min(el_keys)}° to {max(el_keys)}°)")

        # Check beamwidth consistency
        if pattern.beamwidth_h_deg <= 0 or pattern.beamwidth_h_deg > 360:
            result.warnings.append(f"Invalid horizontal beamwidth: {pattern.beamwidth_h_deg}°")

        # Check front-to-back ratio
        if pattern.front_to_back_db < 0:
            result.warnings.append(f"Negative front-to-back ratio: {pattern.front_to_back_db:.1f} dB")
        elif pattern.front_to_back_db > 40:
            result.warnings.append(f"Very high front-to-back ratio: {pattern.front_to_back_db:.1f} dB (verify if realistic)")

    # Check source
    if pattern.source == "built-in":
        result.info.append(f"Built-in pattern: {pattern.name}")
    elif pattern.source == "catalog:atoll":
        result.info.append("Pattern from catalog (Atoll format)")
    elif pattern.source == "catalog:synthetic":
        result.info.append("Pattern derived from catalog specifications")
    elif pattern.source in ["atoll", "csv", "json", "atoll_txt", "msi"]:
        result.info.append(f"Imported pattern (source: {pattern.source})")

    return result


def pattern_preview_text(pattern: AntennaPattern) -> str:
    """Generate a text preview of antenna pattern characteristics.

    Args:
        pattern: AntennaPattern to preview

    Returns:
        Human-readable text summary
    """
    lines = [
        f"Pattern: {pattern.name}",
        f"Type: {pattern.pattern_type}",
        f"Source: {pattern.source}",
        f"Frequency: {pattern.frequency_mhz:.0f} MHz",
        f"Peak Gain: {pattern.gain_max_dbi:.1f} dBi",
    ]

    if pattern.pattern_type != "omni":
        lines.append(f"Horizontal Beamwidth: {pattern.beamwidth_h_deg:.1f}°")
        if pattern.beamwidth_v_deg:
            lines.append(f"Vertical Beamwidth: {pattern.beamwidth_v_deg:.1f}°")
        if pattern.front_to_back_db:
            lines.append(f"Front-to-Back Ratio: {pattern.front_to_back_db:.1f} dB")
        if pattern.tilt_deg:
            lines.append(f"Electrical Downtilt: {pattern.tilt_deg:.1f}°")

    # Validation summary
    validation = validate_antenna_pattern(pattern)
    if validation.warnings:
        lines.append("")
        lines.append("Warnings:")
        for w in validation.warnings:
            lines.append(f"  ⚠ {w}")

    if validation.info:
        lines.append("")
        lines.append("Info:")
        for i in validation.info:
            lines.append(f"  ℹ {i}")

    return "\n".join(lines)