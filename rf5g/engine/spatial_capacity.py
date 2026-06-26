"""Spatial demand and capacity evaluation for geometry-aware placement planning."""
from __future__ import annotations

from ..models.input_schema import RFSizingInput
from ..models.output_schema import SelectedSiteResult, SpatialCapacityResult
from .geometry import bearing_deg, haversine_km, point_in_polygon


def build_demand_tiles(sample_points: list[tuple[float, float]], inp: RFSizingInput, area_km2: float) -> list[dict]:
    total_users = inp.qos.users_per_km2 * area_km2 * inp.qos.concurrent_ratio
    total_dl_mbps = total_users * inp.qos.dl_per_user_mbps
    total_ul_mbps = total_users * inp.qos.ul_per_user_mbps

    weights = []
    for lat, lon in sample_points:
        dl_weight = 1.0
        ul_weight = 1.0
        for zone in (inp.spatial_capacity.demand_zones if inp.spatial_capacity else []):
            if point_in_polygon(lat, lon, zone.polygon):
                dl_weight *= zone.weight
                ul_weight *= zone.weight
                if zone.users_per_km2 and inp.qos.users_per_km2 > 0:
                    ratio = zone.users_per_km2 / inp.qos.users_per_km2
                    dl_weight *= ratio
                    ul_weight *= ratio
                if zone.dl_per_user_mbps and inp.qos.dl_per_user_mbps > 0:
                    dl_weight *= zone.dl_per_user_mbps / inp.qos.dl_per_user_mbps
                if zone.ul_per_user_mbps and inp.qos.ul_per_user_mbps > 0:
                    ul_weight *= zone.ul_per_user_mbps / inp.qos.ul_per_user_mbps
                if zone.concurrent_ratio and inp.qos.concurrent_ratio > 0:
                    ratio = zone.concurrent_ratio / inp.qos.concurrent_ratio
                    dl_weight *= ratio
                    ul_weight *= ratio
        weights.append((dl_weight, ul_weight))

    total_dl_weight = sum(weight[0] for weight in weights) or 1.0
    total_ul_weight = sum(weight[1] for weight in weights) or 1.0

    tiles = []
    for idx, (lat, lon) in enumerate(sample_points):
        dl_weight, ul_weight = weights[idx]
        tiles.append(
            {
                "lat": lat,
                "lon": lon,
                "dl_demand_mbps": total_dl_mbps * dl_weight / total_dl_weight,
                "ul_demand_mbps": total_ul_mbps * ul_weight / total_ul_weight,
                "dl_weight": dl_weight,
                "ul_weight": ul_weight,
            }
        )
    return tiles


def evaluate_spatial_capacity(
    demand_tiles: list[dict],
    selected_sites: list[SelectedSiteResult],
    cell_radius_km: float,
    cell_dl_capacity_mbps: float,
    cell_ul_capacity_mbps: float,
) -> tuple[SpatialCapacityResult, list[dict], list[float], list[float]]:
    site_loads = [
        {"dl_mbps": 0.0, "ul_mbps": 0.0, "tile_indices": [], "sector_loads": []}
        for _ in selected_sites
    ]
    sectors = _build_sector_entities(selected_sites, cell_dl_capacity_mbps, cell_ul_capacity_mbps)
    unmet_dl_weights = [0.0 for _ in demand_tiles]
    unmet_ul_weights = [0.0 for _ in demand_tiles]

    tile_order = sorted(
        range(len(demand_tiles)),
        key=lambda idx: demand_tiles[idx]["dl_demand_mbps"] + demand_tiles[idx]["ul_demand_mbps"],
        reverse=True,
    )

    for idx in tile_order:
        tile = demand_tiles[idx]
        covering = []
        for sector in sectors:
            if not _sector_covers_point(sector, tile["lat"], tile["lon"], cell_radius_km):
                continue
            distance_km = haversine_km(tile["lat"], tile["lon"], sector["site"].lat, sector["site"].lon)
            load_ratio = max(
                sector["dl_mbps"] / max(sector["dl_capacity_mbps"], 1e-9),
                sector["ul_mbps"] / max(sector["ul_capacity_mbps"], 1e-9),
            )
            covering.append((sector, load_ratio, distance_km))
        if not covering:
            unmet_dl_weights[idx] = tile["dl_demand_mbps"]
            unmet_ul_weights[idx] = tile["ul_demand_mbps"]
            continue

        chosen_sector, _, _ = min(covering, key=lambda item: (item[1], item[2]))
        chosen_sector["dl_mbps"] += tile["dl_demand_mbps"]
        chosen_sector["ul_mbps"] += tile["ul_demand_mbps"]
        chosen_sector["tile_indices"].append(idx)
        site_loads[chosen_sector["site_idx"]]["dl_mbps"] += tile["dl_demand_mbps"]
        site_loads[chosen_sector["site_idx"]]["ul_mbps"] += tile["ul_demand_mbps"]
        site_loads[chosen_sector["site_idx"]]["tile_indices"].append(idx)

    served_dl_mbps = 0.0
    served_ul_mbps = 0.0
    hotspot_tiles = 0
    overloaded_site_ids = set()

    for sector in sectors:
        dl_load = sector["dl_mbps"]
        ul_load = sector["ul_mbps"]
        dl_scale = min(1.0, sector["dl_capacity_mbps"] / dl_load) if dl_load > 0 else 1.0
        ul_scale = min(1.0, sector["ul_capacity_mbps"] / ul_load) if ul_load > 0 else 1.0
        served_dl_mbps += dl_load * dl_scale
        served_ul_mbps += ul_load * ul_scale
        sector["dl_scale"] = dl_scale
        sector["ul_scale"] = ul_scale
        if dl_scale < 1.0 or ul_scale < 1.0:
            overloaded_site_ids.add(sector["site_idx"])
            for tile_idx in sector["tile_indices"]:
                tile = demand_tiles[tile_idx]
                unmet_dl_weights[tile_idx] += tile["dl_demand_mbps"] * (1.0 - dl_scale)
                unmet_ul_weights[tile_idx] += tile["ul_demand_mbps"] * (1.0 - ul_scale)

    for site_idx, load in enumerate(site_loads):
        load["sector_loads"] = [sector for sector in sectors if sector["site_idx"] == site_idx]

    for dl_unmet, ul_unmet in zip(unmet_dl_weights, unmet_ul_weights):
        if dl_unmet > 0 or ul_unmet > 0:
            hotspot_tiles += 1

    demand_dl_mbps = sum(tile["dl_demand_mbps"] for tile in demand_tiles)
    demand_ul_mbps = sum(tile["ul_demand_mbps"] for tile in demand_tiles)
    unserved_dl_mbps = sum(unmet_dl_weights)
    unserved_ul_mbps = sum(unmet_ul_weights)

    result = SpatialCapacityResult(
        demand_dl_gbps=round(demand_dl_mbps / 1000.0, 3),
        served_dl_gbps=round(served_dl_mbps / 1000.0, 3),
        unserved_dl_gbps=round(unserved_dl_mbps / 1000.0, 3),
        demand_ul_gbps=round(demand_ul_mbps / 1000.0, 3),
        served_ul_gbps=round(served_ul_mbps / 1000.0, 3),
        unserved_ul_gbps=round(unserved_ul_mbps / 1000.0, 3),
        hotspot_tiles=hotspot_tiles,
        overloaded_sites=len(overloaded_site_ids),
        capacity_sufficient_spatial=hotspot_tiles == 0,
    )
    return result, site_loads, unmet_dl_weights, unmet_ul_weights


def _build_sector_entities(
    selected_sites: list[SelectedSiteResult],
    cell_dl_capacity_mbps: float,
    cell_ul_capacity_mbps: float,
) -> list[dict]:
    sectors = []
    for site_idx, site in enumerate(selected_sites):
        azimuths = site.azimuths_deg or [0.0]
        sector_count = max(1, len(azimuths))
        dl_capacity = cell_dl_capacity_mbps / sector_count if sector_count > 1 else cell_dl_capacity_mbps
        ul_capacity = cell_ul_capacity_mbps / sector_count if sector_count > 1 else cell_ul_capacity_mbps
        beamwidth = site.beamwidth_deg or 360.0
        for sector_idx, azimuth in enumerate(azimuths):
            sectors.append(
                {
                    "site_idx": site_idx,
                    "site": site,
                    "sector_idx": sector_idx,
                    "azimuth_deg": azimuth,
                    "beamwidth_deg": beamwidth,
                    "dl_capacity_mbps": dl_capacity,
                    "ul_capacity_mbps": ul_capacity,
                    "dl_mbps": 0.0,
                    "ul_mbps": 0.0,
                    "tile_indices": [],
                }
            )
    return sectors


def _sector_covers_point(sector: dict, lat: float, lon: float, cell_radius_km: float) -> bool:
    distance_km = haversine_km(lat, lon, sector["site"].lat, sector["site"].lon)
    if distance_km <= 1e-6:
        return True
    if distance_km > cell_radius_km:
        return False
    beamwidth = sector["beamwidth_deg"]
    if beamwidth >= 359.0:
        return True
    point_bearing = bearing_deg(sector["site"].lat, sector["site"].lon, lat, lon)
    return _angular_distance_deg(point_bearing, sector["azimuth_deg"]) <= beamwidth / 2.0


def _angular_distance_deg(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)
