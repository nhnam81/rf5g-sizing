"""Geometry helpers for geometry-aware placement planning."""
from __future__ import annotations

import math

from ..models.input_schema import ExclusionZone, GeoPoint, GeoPolygon, LinearAlignment


def centroid_from_points(points: list[GeoPoint]) -> GeoPoint:
    lat = sum(p.lat for p in points) / len(points)
    lon = sum(p.lon for p in points) / len(points)
    return GeoPoint(lat=lat, lon=lon)


def polygon_centroid(polygon: GeoPolygon) -> GeoPoint:
    return centroid_from_points(polygon.outer)


def latlon_to_xy_km(lat: float, lon: float, ref_lat: float, ref_lon: float) -> tuple[float, float]:
    x = (lon - ref_lon) * 111.320 * math.cos(math.radians(ref_lat))
    y = (lat - ref_lat) * 111.0
    return x, y


def xy_km_to_latlon(x_km: float, y_km: float, ref_lat: float, ref_lon: float) -> tuple[float, float]:
    lat = ref_lat + y_km / 111.0
    lon = ref_lon + x_km / (111.320 * math.cos(math.radians(ref_lat)))
    return lat, lon


def _ring_area_xy(coords: list[tuple[float, float]]) -> float:
    area = 0.0
    for i in range(len(coords)):
        x1, y1 = coords[i]
        x2, y2 = coords[(i + 1) % len(coords)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def _project_ring_km(ring: list[GeoPoint], ref_lat: float, ref_lon: float) -> list[tuple[float, float]]:
    return [latlon_to_xy_km(point.lat, point.lon, ref_lat, ref_lon) for point in ring]


def polygon_area_km2(polygon: GeoPolygon) -> float:
    ref = polygon_centroid(polygon)
    outer_area = _ring_area_xy(_project_ring_km(polygon.outer, ref.lat, ref.lon))
    holes_area = sum(_ring_area_xy(_project_ring_km(hole, ref.lat, ref.lon)) for hole in polygon.holes)
    return max(0.0, outer_area - holes_area)


def line_length_km(alignment: LinearAlignment) -> float:
    total = 0.0
    for start, end in zip(alignment.points, alignment.points[1:]):
        total += haversine_km(start.lat, start.lon, end.lat, end.lon)
    return total


def polygon_bbox(polygon: GeoPolygon) -> tuple[float, float, float, float]:
    lats = [point.lat for point in polygon.outer]
    lons = [point.lon for point in polygon.outer]
    return min(lats), min(lons), max(lats), max(lons)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return radius * 2 * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlon_rad = math.radians(lon2 - lon1)
    y = math.sin(dlon_rad) * math.cos(lat2_rad)
    x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon_rad)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def sample_alignment_points(alignment: LinearAlignment, spacing_m: float) -> list[dict]:
    if spacing_m <= 0:
        raise ValueError("Alignment sampling spacing must be positive")

    ref = centroid_from_points(alignment.points)
    coords = [latlon_to_xy_km(point.lat, point.lon, ref.lat, ref.lon) for point in alignment.points]
    spacing_km = spacing_m / 1000.0

    samples: list[dict] = []
    distance_since_last = 0.0
    prev_x = prev_y = None

    for idx, ((x1, y1), (x2, y2)) in enumerate(zip(coords, coords[1:])):
        seg_dx = x2 - x1
        seg_dy = y2 - y1
        seg_len = math.hypot(seg_dx, seg_dy)
        if seg_len == 0:
            continue
        seg_bearing = bearing_deg(alignment.points[idx].lat, alignment.points[idx].lon, alignment.points[idx + 1].lat, alignment.points[idx + 1].lon)

        distance = 0.0 if prev_x is None else spacing_km - distance_since_last
        if prev_x is None:
            lat, lon = xy_km_to_latlon(x1, y1, ref.lat, ref.lon)
            samples.append({"lat": lat, "lon": lon, "bearing_deg": seg_bearing})
            distance = spacing_km

        while distance <= seg_len + 1e-9:
            ratio = distance / seg_len
            x = x1 + seg_dx * ratio
            y = y1 + seg_dy * ratio
            lat, lon = xy_km_to_latlon(x, y, ref.lat, ref.lon)
            samples.append({"lat": lat, "lon": lon, "bearing_deg": seg_bearing})
            distance += spacing_km

        distance_since_last = seg_len - (distance - spacing_km)
        prev_x, prev_y = x2, y2

    if not samples and alignment.points:
        samples.append({"lat": alignment.points[0].lat, "lon": alignment.points[0].lon, "bearing_deg": 0.0})
    return samples


def _point_in_ring(lat: float, lon: float, ring: list[GeoPoint]) -> bool:
    inside = False
    j = len(ring) - 1
    for i, point in enumerate(ring):
        pi_lat, pi_lon = point.lat, point.lon
        pj_lat, pj_lon = ring[j].lat, ring[j].lon
        intersects = ((pi_lat > lat) != (pj_lat > lat)) and (
            lon < (pj_lon - pi_lon) * (lat - pi_lat) / ((pj_lat - pi_lat) or 1e-12) + pi_lon
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def point_in_polygon(lat: float, lon: float, polygon: GeoPolygon) -> bool:
    if not _point_in_ring(lat, lon, polygon.outer):
        return False
    for hole in polygon.holes:
        if _point_in_ring(lat, lon, hole):
            return False
    return True


def point_in_exclusion_zones(lat: float, lon: float, exclusions: list[ExclusionZone]) -> bool:
    return any(point_in_polygon(lat, lon, exclusion.polygon) for exclusion in exclusions)


def _point_to_segment_distance_km(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    nearest_x = ax + t * dx
    nearest_y = ay + t * dy
    return math.hypot(px - nearest_x, py - nearest_y)


def point_to_polygon_boundary_distance_km(lat: float, lon: float, polygon: GeoPolygon) -> float:
    ref = polygon_centroid(polygon)
    px, py = latlon_to_xy_km(lat, lon, ref.lat, ref.lon)
    distances = []
    for ring in [polygon.outer, *polygon.holes]:
        coords = _project_ring_km(ring, ref.lat, ref.lon)
        for i in range(len(coords)):
            ax, ay = coords[i]
            bx, by = coords[(i + 1) % len(coords)]
            distances.append(_point_to_segment_distance_km(px, py, ax, ay, bx, by))
    return min(distances) if distances else 0.0


def point_to_alignment_distance_km(lat: float, lon: float, alignment: LinearAlignment) -> float:
    ref = centroid_from_points(alignment.points)
    px, py = latlon_to_xy_km(lat, lon, ref.lat, ref.lon)
    coords = [latlon_to_xy_km(point.lat, point.lon, ref.lat, ref.lon) for point in alignment.points]
    distances = []
    for (ax, ay), (bx, by) in zip(coords, coords[1:]):
        distances.append(_point_to_segment_distance_km(px, py, ax, ay, bx, by))
    return min(distances) if distances else 0.0


def point_near_alignment(lat: float, lon: float, alignment: LinearAlignment, buffer_m: float | None) -> bool:
    if not buffer_m or buffer_m <= 0:
        return True
    return point_to_alignment_distance_km(lat, lon, alignment) * 1000.0 <= buffer_m


def point_respects_setback(lat: float, lon: float, polygon: GeoPolygon, setback_m: float) -> bool:
    if setback_m <= 0:
        return True
    if not point_in_polygon(lat, lon, polygon):
        return False
    return point_to_polygon_boundary_distance_km(lat, lon, polygon) * 1000.0 >= setback_m
