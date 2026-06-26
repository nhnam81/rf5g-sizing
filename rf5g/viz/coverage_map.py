# ── 5G NR RF Coverage Map Module ──
"""Coverage map generation with drag-and-drop site placement.

Uses Folium for interactive maps with WGS84 (EPSG:4326) coordinates.
Haversine distance for all map calculations.
"""

import math
import json
import tempfile
from pathlib import Path

import folium

from rf5g.models.output_schema import SizingOutput
from rf5g.models.antenna_pattern import (
    AntennaPattern,
    pattern_for_config,
    antenna_pattern_from_catalog,
    coverage_polygon,
)


# ── Helper: km to lat/lon conversion ──

def km_to_lat(km: float) -> float:
    """Convert km offset to latitude degrees (WGS84)."""
    return km / 111.0


def km_to_lon(km: float, lat: float) -> float:
    """Convert km offset to longitude degrees at given latitude (WGS84)."""
    return km / (111.0 * math.cos(math.radians(lat)))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km between two WGS84 points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


# ── Hex Grid Generation ──

def generate_hex_grid(
    center_lat: float,
    center_lon: float,
    isd_km: float,
    n_sites: int,
    max_sites: int = 200,
) -> list[tuple[float, float]]:
    """Generate hex grid site positions in WGS84 lat/lon.

    Uses axial hex coordinates with ISD spacing.
    First site is always at the center point.
    Sites expand outward in concentric rings.
    Returns list of (lat, lon) tuples.
    """
    if n_sites <= 0 or isd_km <= 0:
        return [(center_lat, center_lon)]

    sites = [(center_lat, center_lon)]
    if n_sites == 1:
        return sites

    seen = {(round(center_lat, 8), round(center_lon, 8))}

    def _add(lat: float, lon: float) -> bool:
        key = (round(lat, 8), round(lon, 8))
        if key not in seen and len(sites) < n_sites:
            seen.add(key)
            sites.append((lat, lon))
            return True
        return False

    # Cube coordinate ring traversal
    # Hex size (circumradius) = ISD / sqrt(3) so that adjacent sites are ISD apart
    hex_size = isd_km / math.sqrt(3)
    directions = [
        (0, -1, 1), (1, -1, 0), (1, 0, -1),
        (0, 1, -1), (-1, 1, 0), (-1, 0, 1),
    ]

    for ring in range(1, max(20, n_sites) + 1):
        # Start corner of ring N: cube (ring, -ring, 0)
        cx, cy, cz = ring, -ring, 0

        for side_idx in range(6):
            dx, dy, dz = directions[side_idx]
            for _ in range(ring):
                # Axial: q = cx, r = cz
                q, r = cx, cz
                # Pointy-top hex: x = s*(sqrt(3)*q + sqrt(3)/2*r), y = s*3/2*r
                x_km = hex_size * (math.sqrt(3) * q + math.sqrt(3) / 2 * r)
                y_km = hex_size * (3 / 2 * r)
                lat = center_lat + km_to_lat(y_km)
                lon = center_lon + km_to_lon(x_km, center_lat)
                _add(lat, lon)
                # Walk to next position along this side
                cx += dx
                cy += dy
                cz += dz

        if len(sites) >= n_sites:
            break

    return sites[:min(n_sites, max_sites)]


# ── Export Functions ──

def export_sites_json(
    sites: list[tuple[float, float]],
    isd_km: float,
    project_name: str = "5G_NR_Sites",
) -> str:
    """Export sites as GeoJSON FeatureCollection."""
    import json as _json
    features = []
    for i, (lat, lon) in enumerate(sites):
        features.append({
            "type": "Feature",
            "properties": {
                "site_id": i + 1,
                "project": project_name,
                "isd_km": round(isd_km, 4),
            },
            "geometry": {
                "type": "Point",
                "coordinates": [round(lon, 6), round(lat, 6)],
            },
        })
    return _json.dumps({
        "type": "FeatureCollection",
        "features": features,
    }, indent=2, ensure_ascii=False)


def export_sites_csv(
    sites: list[tuple[float, float]],
    isd_km: float,
    project_name: str = "5G_NR_Sites",
) -> str:
    """Export sites as CSV string."""
    lines = ["site_id,latitude,longitude,isd_km,project"]
    for i, (lat, lon) in enumerate(sites):
        lines.append(f"{i+1},{lat:.6f},{lon:.6f},{isd_km:.4f},{project_name}")
    return "\n".join(lines)


def import_sites_json(path: str) -> list[tuple[float, float]]:
    """Import sites from GeoJSON file."""
    import json as _json
    with open(path, "r", encoding="utf-8") as f:
        data = _json.load(f)
    sites = []
    for feature in data.get("features", []):
        coords = feature["geometry"]["coordinates"]
        # GeoJSON: [lon, lat] -> convert to (lat, lon)
        sites.append((coords[1], coords[0]))
    return sites


def import_sites_csv(path: str) -> list[tuple[float, float]]:
    """Import sites from CSV file."""
    sites = []
    with open(path, "r", encoding="utf-8") as f:
        import csv
        reader = csv.DictReader(f)
        for row in reader:
            lat = float(row["latitude"])
            lon = float(row["longitude"])
            sites.append((lat, lon))
    return sites


def recalculate_from_sites(
    result: SizingOutput,
    sites: list[tuple[float, float]],
) -> SizingOutput:
    """Recalculate sizing output based on custom sites."""
    # Just return the same result; sites override is handled at map generation level
    return result


# ── Interactive Map with Drag-and-Drop ──

# JavaScript for drag-and-drop functionality
DRAG_DROP_JS = """
<script>

var rf5gMap = null;
var rf5gSites = {};
var rf5gMarkers = {};
var rf5gHexes = {};
var rf5gConfig;
var rf5gCounter = 0;
// rf5gConfig will be set by Python-generated script after map creation

function initRf5gMap(mapId) {
    // Find the Leaflet map instance by its container ID
    // Folium creates maps like: var map_xxx = L.map("map_xxx", {...});
    // We need to find the container element and get the map instance
    var container = document.getElementById(mapId);
    if (!container) {
        // Try finding any map container
        var containers = document.querySelectorAll('[id^="map_"]');
        if (containers.length > 0) {
            container = containers[0];
            mapId = container.id;
        } else {
            return;
        }
    }
    // Leaflet stores map instance on the container element
    rf5gMap = container._leaflet_map || L.DomUtil.get(mapId)._leaflet;
    // Alternative: iterate window to find L.map instance
    if (!rf5gMap) {
        for (var key in window) {
            try {
                if (window[key] && window[key].getContainer && typeof window[key].getContainer === 'function') {
                    rf5gMap = window[key];
                    break;
                }
            } catch(e) {}
        }
    }
    if (!rf5gMap) return;
    // Only bind click handler once
    if (!rf5gMap._rf5gClickBound) {
        rf5gMap._rf5gClickBound = true;
        rf5gMap.on('click', function(e) {
            addDraggableMarker(e.latlng.lat, e.latlng.lng);
        });
    }
}

function computeCoverageShape(lat, lon, radiusKm, antennaType, patternData, azimuth) {
    // Compute coverage polygon based on antenna pattern
    // Returns array of [lat, lon] for Leaflet polygon
    var cosLat = Math.cos(lat * Math.PI / 180);
    var nullRadius = radiusKm * 0.05; // 5% for null directions
    
    if (antennaType === 'omni') {
        // Circle for omnidirectional
        var vertices = [];
        for (var i = 0; i < 36; i++) {
            var angle = 2 * Math.PI * i / 36;
            var dlat = radiusKm * Math.cos(angle) / 111.0;
            var dlon = radiusKm * Math.sin(angle) / (111.0 * cosLat);
            vertices.push([lat + dlat, lon + dlon]);
        }
        return vertices;
    }
    
    if (patternData && patternData.length > 0) {
        // Use antenna pattern data [azimuth, relative_gain_dB]
        var vertices = [];
        var threshold = -10; // dB below peak
        
        for (var i = 0; i < 360; i++) {
            var bearing = i;
            var patternAz = ((bearing - azimuth) % 360 + 360) % 360;
            
            // Find gain at this azimuth (interpolate from pattern data)
            var gain = interpolateGain(patternData, patternAz);
            var relativeGain = gain;
            
            if (relativeGain < threshold) {
                effectiveRadius = nullRadius;
            } else {
                effectiveRadius = radiusKm * Math.pow(10, relativeGain / 70);
                effectiveRadius = Math.max(effectiveRadius, nullRadius);
            }
            
            var dlat = effectiveRadius * Math.cos(bearing * Math.PI / 180) / 111.0;
            var dlon = effectiveRadius * Math.sin(bearing * Math.PI / 180) / (111.0 * cosLat);
            vertices.push([lat + dlat, lon + dlon]);
        }
        return vertices;
    }
    
    // Built-in sector pattern (cosine approximation)
    var beamwidth = rf5gConfig.antenna_beamwidth || 65;
    var vertices = [];
    var halfBeam = beamwidth / 2;
    
    for (var i = 0; i < 360; i++) {
        var bearing = i;
        var patternAz = ((bearing - azimuth + 180) % 360) - 180;
        
        if (Math.abs(patternAz) <= halfBeam) {
            // Inside main beam: cosine taper
            var cosVal = Math.cos(patternAz * Math.PI / beamwidth);
            effectiveRadius = radiusKm * Math.pow(10, 3 * cosVal / 70); // ~3dB edge taper
            effectiveRadius = Math.max(effectiveRadius, nullRadius);
        } else {
            effectiveRadius = nullRadius;
        }
        
        var dlat = effectiveRadius * Math.cos(bearing * Math.PI / 180) / 111.0;
        var dlon = effectiveRadius * Math.sin(bearing * Math.PI / 180) / (111.0 * cosLat);
        vertices.push([lat + dlat, lon + dlon]);
    }
    return vertices;
}

function interpolateGain(patternData, az) {
    // Linear interpolation of gain from pattern data [azimuth, relative_gain_dB]
    var n = patternData.length;
    if (n === 0) return -25;
    if (n === 1) return patternData[0][1];
    
    for (var i = 0; i < n; i++) {
        if (patternData[i][0] >= az) {
            if (i === 0) {
                var prev = patternData[n-1][0] - 360;
                var t = (az - prev) / (patternData[i][0] - prev);
                return patternData[n-1][1] + t * (patternData[i][1] - patternData[n-1][1]);
            }
            var prevAz = patternData[i-1][0];
            var nextAz = patternData[i][0];
            var t = (az - prevAz) / (nextAz - prevAz);
            return patternData[i-1][1] + t * (patternData[i][1] - patternData[i-1][1]);
        }
    }
    // Wrap around
    var prevAz = patternData[n-1][0];
    var nextAz = patternData[0][0] + 360;
    var t = (az - prevAz) / (nextAz - prevAz);
    return patternData[n-1][1] + t * (patternData[0][1] - patternData[n-1][1]);
}

function getSiteShape(lat, lon) {
    // Get coverage shape for a site based on antenna config
    var antType = rf5gConfig.antenna_type || 'sector';
    var sectors = rf5gConfig.sectors || 3;
    var azimuths = rf5gConfig.sector_azimuths || [0, 120, 240];
    var patternData = rf5gConfig.antenna_pattern || null;
    var radiusKm = rf5gConfig.cell_radius_km;
    
    if (antType === 'omni' || sectors === 1) {
        if (antType === 'omni') {
            return computeCoverageShape(lat, lon, radiusKm, 'omni', null, 0);
        }
        // Single sector directional: one wedge
        return computeCoverageShape(lat, lon, radiusKm, 'sector', patternData, azimuths[0] || 0);
    }
    
    // Multi-sector: return array of shapes
    var shapes = [];
    for (var s = 0; s < sectors; s++) {
        shapes.push(computeCoverageShape(lat, lon, radiusKm, 'sector', patternData, azimuths[s]));
    }
    return shapes;
}

function computeHexVertices(lat, lon, radiusKm) {
    // Legacy: still used for omni fallback
    var vertices = [];
    for (var i = 0; i < 6; i++) {
        var angle = Math.PI / 3 * i + Math.PI / 6;
        var dlatKm = radiusKm * Math.cos(angle);
        var dlonKm = radiusKm * Math.sin(angle);
        var dlat = dlatKm / 111.0;
        var dlon = dlonKm / (111.0 * Math.cos(lat * Math.PI / 180));
        vertices.push([lat + dlat, lon + dlon]);
    }
    return vertices;
}

function addDraggableMarker(lat, lon) {
    var id = 'site_' + (++rf5gCounter);
    rf5gSites[id] = [lat.toFixed(6), lon.toFixed(6)];

    var marker = L.marker([lat, lon], {draggable: true}).addTo(rf5gMap);
    marker.bindTooltip('Site #' + rf5gCounter + ': ' + lat.toFixed(6) + ', ' + lon.toFixed(6));
    marker.on('dragend', function(e) {
        var pos = e.target.getLatLng();
        rf5gSites[id] = [pos.lat.toFixed(6), pos.lng.toFixed(6)];
        marker.setTooltipContent('Site #' + id.split('_')[1] + ': ' + pos.lat.toFixed(6) + ', ' + pos.lng.toFixed(6));

        // Update coverage shapes
        var antType = rf5gConfig.antenna_type || 'sector';
        var sectors = rf5gConfig.sectors || 3;
        var azimuths = rf5gConfig.sector_azimuths || [0, 120, 240];
        var patternData = rf5gConfig.antenna_pattern || null;
        var shapes = rf5gHexes[id];
        if (antType === 'omni') {
            shapes[0].setLatLngs(computeCoverageShape(pos.lat, pos.lng, rf5gConfig.cell_radius_km, 'omni', null, 0));
        } else if (sectors === 1) {
            shapes[0].setLatLngs(computeCoverageShape(pos.lat, pos.lng, rf5gConfig.cell_radius_km, 'sector', patternData, azimuths[0]));
        } else {
            for (var s = 0; s < sectors; s++) {
                shapes[s].setLatLngs(computeCoverageShape(pos.lat, pos.lng, rf5gConfig.cell_radius_km, 'sector', patternData, azimuths[s]));
            }
        }
    });

    // Draw coverage shape (sector-aware)
    var antType = rf5gConfig.antenna_type || 'sector';
    var sectors = rf5gConfig.sectors || 3;
    var azimuths = rf5gConfig.sector_azimuths || [0, 120, 240];
    var patternData = rf5gConfig.antenna_pattern || null;

    if (antType === 'omni') {
        var shapeCoords = computeCoverageShape(lat, lon, rf5gConfig.cell_radius_km, 'omni', null, 0);
        var hex = L.polygon(shapeCoords, {
            color: rf5gConfig.sinr_color,
            fillColor: rf5gConfig.sinr_color,
            fillOpacity: 0.15,
            weight: 1
        }).addTo(rf5gMap);
        rf5gHexes[id] = [hex];
    } else if (sectors === 1) {
        var shapeCoords = computeCoverageShape(lat, lon, rf5gConfig.cell_radius_km, 'sector', patternData, azimuths[0]);
        var hex = L.polygon(shapeCoords, {
            color: '#9C27B0',
            fillColor: '#9C27B0',
            fillOpacity: 0.12,
            weight: 1
        }).addTo(rf5gMap);
        rf5gHexes[id] = [hex];
    } else {
        var sectorColors = ['#2196F3', '#4CAF50', '#FF9800', '#9C27B0', '#FF5722', '#009688'];
        var hexes = [];
        for (var s = 0; s < sectors; s++) {
            var shapeCoords = computeCoverageShape(lat, lon, rf5gConfig.cell_radius_km, 'sector', patternData, azimuths[s]);
            var hex = L.polygon(shapeCoords, {
                color: sectorColors[s % sectorColors.length],
                fillColor: sectorColors[s % sectorColors.length],
                fillOpacity: 0.08,
                weight: 1
            }).addTo(rf5gMap);
            hexes.push(hex);
        }
        rf5gHexes[id] = hexes;
    }

    rf5gMarkers[id] = marker;
    updateSiteList();
}

function removeSite(id) {
    if (rf5gMarkers[id]) {
        rf5gMap.removeLayer(rf5gMarkers[id]);
        delete rf5gMarkers[id];
    }
    if (rf5gHexes[id]) {
        rf5gHexes[id].forEach(function(hex) {
            rf5gMap.removeLayer(hex);
        });
        delete rf5gHexes[id];
    }
    rf5gSites[id] = null;
    updateSiteList();
}

function updateSiteList() {
    var list = document.getElementById('rf5g-site-list');
    if (!list) return;
    var html = '<b>Sites:</b><br>';
    var count = 0;
    for (var id in rf5gSites) {
        if (rf5gSites[id]) {
            html += '<span style="margin-right:8px;">📍 ' + rf5gSites[id][0] + ', ' + rf5gSites[id][1] +
                    ' <button onclick="removeSite(\\'' + id + '\\')" style="background:#f44336;color:white;border:none;padding:1px 6px;border-radius:3px;cursor:pointer;font-size:11px;">✕</button></span>';
            count++;
        }
    }
    html += '<br><small>📍 Click map to add sites</small>';
    list.innerHTML = html;
}
</script>
"""


def generate_interactive_map(
    result: SizingOutput,
    center_lat: float = 10.8231,
    center_lon: float = 106.6297,
    zoom_start: int = 12,
    output_path: str | None = None,
    custom_sites: list[tuple[float, float]] | None = None,
    antenna_pattern_override: AntennaPattern | None = None,
    return_map: bool = False,
    site_meta: list[dict] | None = None,
) -> str | folium.Map:
    """Generate interactive coverage map with drag-and-drop site placement.

    Uses Folium with WGS84 (EPSG:4326) coordinates and haversine distances.
    Supports sector-specific coverage shapes for directional antennas.
    site_meta: optional per-site dict with 'azimuth' and 'beamwidth' keys.
    """
    # ── Determine antenna pattern ──
    if antenna_pattern_override:
        antenna_pattern = antenna_pattern_override
    else:
        antenna_pattern = pattern_for_config(result.antenna_config)

    # ── Calculate grid parameters ──
    cell_radius_km = result.site_estimate.cell_radius_km
    isd_km = result.site_estimate.isd_km
    n_cov = result.site_estimate.coverage_sites
    n_cap = getattr(result.site_estimate, 'capacity_sites', n_cov)
    if n_cap is None:
        n_cap = n_cov
    n_sites = max(n_cov, n_cap)

    sectors = result.site_estimate.sectors if hasattr(result.site_estimate, 'sectors') else 3
    sector_azimuths = {
        1: [0],
        2: [0, 180],
        3: [0, 120, 240],
        4: [0, 90, 180, 270],
        6: [0, 60, 120, 180, 240, 300],
    }.get(sectors, [0, 120, 240])

    # ── Antenna pattern config for JS ──
    config = {
        "cell_radius_km": cell_radius_km,
        "isd_km": isd_km,
        "n_sites": n_sites,
        "sinr_color": "#4CAF50",
    }

    if antenna_pattern_override:
        ant_p = antenna_pattern_override
    else:
        ant_p = pattern_for_config(result.antenna_config)

    # ── Title bar ──
    is_single_directional = sectors == 1 and ant_p.pattern_type != "omni"

    # ── Determine coverage color ──
    if n_cap > n_cov:
        sinr_color = "#FF9800"  # Capacity-limited
    else:
        sinr_color = "#4CAF50"  # Coverage-limited

    config["sinr_color"] = sinr_color
    config["antenna_type"] = ant_p.pattern_type
    config["antenna_beamwidth"] = ant_p.beamwidth_h_deg
    config["sectors"] = sectors
    config["sector_azimuths"] = sector_azimuths
    if ant_p.pattern_type == "custom" and ant_p.horizontal_pattern:
        config["antenna_pattern"] = [[az, round(gain - ant_p.gain_max_dbi, 1)] for az, gain in sorted(ant_p.horizontal_pattern.items())]
    else:
        config["antenna_pattern"] = None

    is_single_directional = sectors == 1 and ant_p.pattern_type != "omni"

    # ── Build Folium map ──
    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_start, tiles="OpenStreetMap", width="100%", height=600)

    # ── Draw planning overlays ──
    if result.placement_plan and result.placement_plan.overlays:
        overlays = result.placement_plan.overlays
        if overlays.service_area:
            service_coords = [(point.lat, point.lon) for point in overlays.service_area.outer]
            folium.Polygon(
                locations=service_coords,
                color="#1E88E5",
                fill=False,
                weight=3,
                popup="Service area",
            ).add_to(m)
            for hole in overlays.service_area.holes:
                folium.Polygon(
                    locations=[(point.lat, point.lon) for point in hole],
                    color="#1E88E5",
                    dash_array="5,5",
                    fill=False,
                    weight=2,
                    popup="Service area hole",
                ).add_to(m)
        for exclusion in overlays.exclusion_zones:
            folium.Polygon(
                locations=[(point.lat, point.lon) for point in exclusion.polygon.outer],
                color="#E53935",
                fill=True,
                fill_color="#E53935",
                fill_opacity=0.12,
                weight=2,
                popup=f"Exclusion zone: {exclusion.reason}",
            ).add_to(m)
        for alignment in overlays.alignments:
            folium.PolyLine(
                locations=[(point.lat, point.lon) for point in alignment.points],
                color="#6D4C41",
                weight=3,
                dash_array="6,4",
                popup=f"Alignment: {alignment.alignment_type}",
            ).add_to(m)
        for traffic_zone in overlays.traffic_zones:
            folium.Polygon(
                locations=[(point.lat, point.lon) for point in traffic_zone.polygon.outer],
                color="#FB8C00",
                fill=True,
                fill_color="#FB8C00",
                fill_opacity=0.10,
                weight=2,
                popup=f"Traffic zone: {traffic_zone.name or 'weighted demand'} (x{traffic_zone.weight})",
            ).add_to(m)

    # ── Generate sites ──
    planned_site_meta = None
    if custom_sites:
        sites = custom_sites
    elif result.placement_plan and result.placement_plan.selected_sites:
        sites = [(site.lat, site.lon) for site in result.placement_plan.selected_sites]
        planned_site_meta = [
            {
                "label": site.id,
                "status": site.status,
                "source": site.source,
                "azimuths": list(site.azimuths_deg),
                "beamwidth": site.beamwidth_deg,
                "overloaded": site.overloaded,
            }
            for site in result.placement_plan.selected_sites
        ]
    else:
        sites = generate_hex_grid(center_lat, center_lon, isd_km, n_sites)

    # ── Color mapping for sectors ──
    sector_colors = ["#2196F3", "#4CAF50", "#FF9800", "#9C27B0", "#FF5722", "#009688"]

    # ── Draw each site ──
    for idx, (lat, lon) in enumerate(sites):
        site_color = sinr_color

        # Per-site override from site_meta or placement plan
        site_azimuths = sector_azimuths  # default
        site_beamwidth = ant_p.beamwidth_h_deg  # default
        site_ant = ant_p  # default
        manual_sector = False
        site_label = f"Site #{idx + 1}"
        site_status = None
        site_overloaded = False

        if planned_site_meta and idx < len(planned_site_meta):
            pm = planned_site_meta[idx]
            site_label = pm.get("label") or site_label
            site_status = pm.get("status")
            site_overloaded = bool(pm.get("overloaded"))
            site_azimuths = pm.get("azimuths") or site_azimuths
            if pm.get("beamwidth") is not None:
                site_beamwidth = pm["beamwidth"]
            if site_beamwidth < 359:
                from rf5g.models.antenna_pattern import _cosine_pattern
                site_ant = AntennaPattern(
                    name=f"Planned-{site_beamwidth:.0f}deg",
                    pattern_type="sector",
                    beamwidth_h_deg=site_beamwidth,
                    gain_max_dbi=ant_p.gain_max_dbi,
                    horizontal_pattern=_cosine_pattern(site_beamwidth, ant_p.gain_max_dbi),
                )
        elif site_meta and idx < len(site_meta):
            sm = site_meta[idx]
            if sm.get("azimuth") is not None and sm.get("beamwidth") is not None:
                # Manual sector: override azimuth and beamwidth for this site
                site_azimuths = [sm["azimuth"]]
                site_beamwidth = sm["beamwidth"]
                from rf5g.models.antenna_pattern import _cosine_pattern
                site_ant = AntennaPattern(
                    name=f"Manual-{site_beamwidth:.0f}deg",
                    pattern_type="sector",
                    beamwidth_h_deg=site_beamwidth,
                    gain_max_dbi=ant_p.gain_max_dbi,
                    horizontal_pattern=_cosine_pattern(site_beamwidth, ant_p.gain_max_dbi),
                )
                manual_sector = True

        # Draw coverage polygon per site
        if site_ant.pattern_type == "omni" and not manual_sector:
            # Omni: circle
            coords = coverage_polygon(lat, lon, cell_radius_km, site_ant, azimuth_deg=0)
            folium.Polygon(
                locations=coords,
                color=sinr_color,
                fill_color=sinr_color,
                fill_opacity=0.15,
                weight=1,
                popup=f"{site_label}<br>{site_status + '<br>' if site_status else ''}Omni coverage<br>R={cell_radius_km * 1000:.0f}m",
            ).add_to(m)
        elif manual_sector:
            # Manual sector: purple wedge
            coords = coverage_polygon(lat, lon, cell_radius_km, site_ant, azimuth_deg=site_azimuths[0])
            folium.Polygon(
                locations=coords,
                color="#9C27B0",
                fill_color="#9C27B0",
                fill_opacity=0.12,
                weight=1,
                popup=f"{site_label}<br>{site_status + '<br>' if site_status else ''}Manual {site_beamwidth:.0f}° @ Az {site_azimuths[0]:.0f}°<br>R={cell_radius_km * 1000:.0f}m",
            ).add_to(m)
        elif len(site_azimuths) == 1:
            # Single sector directional: purple wedge
            coords = coverage_polygon(lat, lon, cell_radius_km, site_ant, azimuth_deg=site_azimuths[0])
            folium.Polygon(
                locations=coords,
                color="#9C27B0",
                fill_color="#9C27B0",
                fill_opacity=0.12,
                weight=1,
                popup=f"{site_label}<br>{site_status + '<br>' if site_status else ''}1-Sector {site_ant.beamwidth_h_deg:.0f}°<br>R={cell_radius_km * 1000:.0f}m",
            ).add_to(m)
        else:
            # Multi-sector: draw per-sector polygons
            for s_idx, az in enumerate(site_azimuths):
                coords = coverage_polygon(lat, lon, cell_radius_km, site_ant, azimuth_deg=az)
                color = sector_colors[s_idx % len(sector_colors)]
                folium.Polygon(
                    locations=coords,
                    color=color,
                    fill_color=color,
                    fill_opacity=0.08,
                    weight=1,
                    popup=f"{site_label} Sector {s_idx + 1}<br>{site_status + '<br>' if site_status else ''}Azimuth {az}°<br>R={cell_radius_km * 1000:.0f}m",
                ).add_to(m)

        # Site marker (static fallback)
        marker_color = "#D32F2F" if site_overloaded else site_color
        folium.CircleMarker(
            location=[lat, lon],
            radius=4,
            color=marker_color,
            fill=True,
            fill_color=marker_color,
            fill_opacity=0.8,
            tooltip=f"{site_label}: {lat:.6f}, {lon:.6f}" + (" [OVERLOADED]" if site_overloaded else ""),
        ).add_to(m)

    # ── Inject config and JS ──
    config_js = f"rf5gConfig = {json.dumps(config)};"
    sites_js = f"rf5gSites = {json.dumps([[f'{lat:.6f}', f'{lon:.6f}'] for lat, lon in sites])};"

    # Initialize sites from Python
    # Use setTimeout to ensure Leaflet map is ready before adding markers
    init_js = DRAG_DROP_JS + f"""
<script>
{config_js}
{sites_js}
rf5gCounter = rf5gSites.length;
// Wait for Leaflet map to be initialized, then add markers
function rf5gInit() {{
    // Find any Leaflet map on the page
    var mapId = null;
    var containers = document.querySelectorAll('[id^="map_"]');
    if (containers.length > 0) {{
        mapId = containers[0].id;
    }}
    if (!mapId) {{
        setTimeout(rf5gInit, 100);
        return;
    }}
    initRf5gMap(mapId);
    // Try to find the map variable
    if (!rf5gMap) {{
        // Search window for Leaflet map instance
        for (var key in window) {{
            try {{
                if (window[key] && window[key].getContainer) {{
                    rf5gMap = window[key];
                    break;
                }}
            }} catch(e) {{}}
        }}
    }}
    if (!rf5gMap) {{
        setTimeout(rf5gInit, 100);
        return;
    }}
    for (var i = 0; i < rf5gSites.length; i++) {{
        addDraggableMarker(parseFloat(rf5gSites[i][0]), parseFloat(rf5gSites[i][1]));
    }}
}}
setTimeout(rf5gInit, 200);
</script>
"""

    # Inject JS AFTER map creation using script.add_child
    # This ensures config and init code run after the Leaflet map is ready
    m.get_root().script.add_child(folium.Element(init_js))

    # ── Return map object or save to file ──
    if return_map:
        return m

    if output_path is None:
        output_path = str(Path(tempfile.mkdtemp()) / "coverage_map.html")

    m.save(output_path)
    return output_path


def generate_coverage_map(
    result: SizingOutput,
    center_lat: float = 10.8231,
    center_lon: float = 106.6297,
    zoom_start: int = 12,
    output_path: str | None = None,
    antenna_pattern_override: AntennaPattern | None = None,
    return_map: bool = False,
) -> str | folium.Map:
    """Generate interactive coverage map (backward-compatible wrapper).

    This calls generate_interactive_map() with drag-and-drop support.
    """
    return generate_interactive_map(
        result=result,
        center_lat=center_lat,
        center_lon=center_lon,
        zoom_start=zoom_start,
        output_path=output_path,
        antenna_pattern_override=antenna_pattern_override,
        return_map=return_map,
    )