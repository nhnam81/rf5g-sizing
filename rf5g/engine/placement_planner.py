"""Geometry-aware placement planning for polygon-constrained site layouts."""
from __future__ import annotations

import math

from ..models.antenna_pattern import AntennaPattern, derive_site_geometry_mode
from ..models.input_schema import LinearAlignment, RFSizingInput
from ..models.output_schema import (
    CandidateSiteResult,
    GeometryOverlay,
    PlacementMetrics,
    PlacementPlanResult,
    SelectedSiteResult,
    SiteEstimateResult,
)
from .geometry import (
    bearing_deg,
    centroid_from_points,
    haversine_km,
    latlon_to_xy_km,
    line_length_km,
    point_in_exclusion_zones,
    point_in_polygon,
    point_near_alignment,
    point_respects_setback,
    point_to_polygon_boundary_distance_km,
    polygon_area_km2,
    polygon_bbox,
    sample_alignment_points,
    xy_km_to_latlon,
)
from .spatial_capacity import build_demand_tiles, evaluate_spatial_capacity


def effective_planning_area_km2(inp: RFSizingInput) -> float:
    placement = inp.placement
    if placement and placement.service_area:
        return polygon_area_km2(placement.service_area)
    return inp.project.area_km2


def build_placement_plan(
    inp: RFSizingInput,
    site_estimate: SiteEstimateResult,
    antenna_pattern: AntennaPattern,
    cell_dl_capacity_mbps: float | None = None,
    cell_ul_capacity_mbps: float | None = None,
) -> PlacementPlanResult | None:
    placement = inp.placement
    if not placement or not placement.service_area:
        return None

    service_area = placement.service_area
    exclusions = placement.exclusion_zones
    alignments = placement.alignments
    usable_area_km2 = effective_planning_area_km2(inp)
    excluded_area_km2 = sum(polygon_area_km2(zone.polygon) for zone in exclusions)
    alignment_length_km = sum(line_length_km(alignment) for alignment in alignments)
    mode = placement.placement_mode
    objective = placement.objective

    geometry_mode = derive_site_geometry_mode(inp.base_station.sectors, antenna_pattern)
    default_azimuths = _default_sector_azimuths(inp.base_station.sectors)
    default_beamwidth = 360.0 if geometry_mode == "omni_360" else antenna_pattern.beamwidth_h_deg

    selected_sites: list[SelectedSiteResult] = []
    selected_positions: list[tuple[float, float]] = []
    candidate_records: list[dict] = []
    min_spacing_m = placement.min_site_spacing_m or 0.0

    for idx, planned in enumerate(placement.planned_sites, start=1):
        accepted = _candidate_allowed(
            planned.lat,
            planned.lon,
            service_area,
            exclusions,
            placement.edge_setback_m,
            placement.allow_outside_service_area_buffer_m,
        )
        if planned.status in {"locked", "existing"}:
            accepted = True
        reasons = []
        if accepted:
            reasons.append("seed site")
        else:
            if not point_in_polygon(planned.lat, planned.lon, service_area):
                reasons.append("outside service area")
            if point_in_exclusion_zones(planned.lat, planned.lon, exclusions):
                reasons.append("inside exclusion zone")
            if not point_respects_setback(planned.lat, planned.lon, service_area, placement.edge_setback_m):
                reasons.append("violates edge setback")
        azimuths = [planned.azimuth_deg] if planned.azimuth_deg is not None else list(default_azimuths)
        beamwidth = planned.beamwidth_deg if planned.beamwidth_deg is not None else default_beamwidth
        candidate_records.append(
            {
                "id": planned.id or f"planned-{idx}",
                "lat": planned.lat,
                "lon": planned.lon,
                "source": "manual",
                "accepted": accepted,
                "reasons": reasons,
                "azimuths_deg": azimuths,
                "beamwidth_deg": beamwidth,
                "status": planned.status,
                "score": None,
            }
        )
        if accepted:
            selected_sites.append(
                SelectedSiteResult(
                    id=planned.id or f"planned-{idx}",
                    lat=planned.lat,
                    lon=planned.lon,
                    source="manual",
                    azimuths_deg=azimuths,
                    beamwidth_deg=beamwidth,
                    status=planned.status,
                    explanations=[f"{planned.status} site preserved"] if planned.status in {"locked", "existing"} else ["manual seed site"],
                )
            )
            selected_positions.append((planned.lat, planned.lon))

    sample_points = _sample_service_points(service_area, exclusions, alignments, inp, site_estimate.cell_radius_km)
    covered_indices = _covered_point_indices(sample_points, selected_sites, site_estimate.cell_radius_km)
    demand_tiles = None
    if inp.spatial_capacity and inp.spatial_capacity.enabled:
        demand_tiles = build_demand_tiles(sample_points, inp, usable_area_km2)

    for candidate in _generate_auto_candidates(
        inp,
        site_estimate,
        service_area,
        exclusions,
        alignments,
        selected_positions,
        default_azimuths,
        default_beamwidth,
        geometry_mode,
    ):
        candidate["coverage_indices"] = _coverage_indices_for_site(
            sample_points,
            candidate["lat"],
            candidate["lon"],
            candidate["azimuths_deg"],
            candidate["beamwidth_deg"],
            site_estimate.cell_radius_km,
        )
        candidate_records.append(candidate)

    auto_candidates = [candidate for candidate in candidate_records if candidate["source"] != "manual"]
    target_coverage_ratio = _target_coverage_ratio(inp)
    target_covered = math.ceil(target_coverage_ratio * len(sample_points)) if sample_points else 0
    alignment_bonus = 0.5 if mode == "alignment_biased" else 0.0

    while auto_candidates:
        unmet_dl_weights = [0.0 for _ in sample_points]
        unmet_ul_weights = [0.0 for _ in sample_points]
        capacity_goal_met = True
        if demand_tiles:
            spatial_result, _, unmet_dl_weights, unmet_ul_weights = evaluate_spatial_capacity(
                demand_tiles,
                selected_sites,
                site_estimate.cell_radius_km,
                cell_dl_capacity_mbps or 0.0,
                cell_ul_capacity_mbps or 0.0,
            )
            if objective == "capacity_first":
                capacity_goal_met = (
                    spatial_result.unserved_dl_gbps <= max(0.05 * spatial_result.demand_dl_gbps, 0.01)
                    and spatial_result.unserved_ul_gbps <= max(0.05 * spatial_result.demand_ul_gbps, 0.005)
                )
        else:
            spatial_result = None

        if len(covered_indices) >= target_covered and capacity_goal_met:
            break

        best = None
        best_score = -1.0
        best_gain = set()
        best_demand_gain = 0.0
        for candidate in auto_candidates:
            gain = candidate["coverage_indices"] - covered_indices
            coverage_gain = float(len(gain))
            demand_gain = 0.0
            if demand_tiles:
                demand_gain = float(
                    sum(unmet_dl_weights[idx] + 0.5 * unmet_ul_weights[idx] for idx in candidate["coverage_indices"])
                )
            source_bonus = alignment_bonus if candidate["source"] == "alignment" else 0.0
            score = _candidate_score(objective, coverage_gain, demand_gain, source_bonus)
            candidate["score"] = score
            candidate["demand_gain"] = demand_gain
            if score > best_score:
                best = candidate
                best_score = score
                best_gain = gain
                best_demand_gain = demand_gain
        if best is None or best_score <= 0:
            break
        if demand_tiles and objective == "capacity_first" and len(covered_indices) >= target_covered and best_demand_gain <= 0.01:
            break

        best["accepted"] = True
        best["reasons"] = [
            f"selected by {objective} score {best_score:.2f}",
            f"coverage gain {len(best_gain)} tiles",
        ]
        if demand_tiles:
            best["reasons"].append(f"demand relief {best_demand_gain:.2f} Mbps")
        if best["source"] == "alignment":
            best["reasons"].append("sampled along alignment")
        selected_sites.append(
            SelectedSiteResult(
                id=best["id"],
                lat=best["lat"],
                lon=best["lon"],
                source=best["source"],
                azimuths_deg=best["azimuths_deg"],
                beamwidth_deg=best["beamwidth_deg"],
                status="selected",
                explanations=best["reasons"],
            )
        )
        selected_positions.append((best["lat"], best["lon"]))
        covered_indices |= best_gain
        auto_candidates.remove(best)

    for candidate in auto_candidates:
        if not candidate.get("accepted"):
            candidate["accepted"] = False
            candidate["reasons"] = ["not selected after greedy planning"]

    coverage_ratio = len(covered_indices) / len(sample_points) if sample_points else 0.0
    covered_area_km2 = usable_area_km2 * coverage_ratio
    locked_sites = sum(1 for site in selected_sites if site.status in {"locked", "existing"})

    spatial_capacity = None
    if demand_tiles:
        spatial_capacity, site_loads, _, _ = evaluate_spatial_capacity(
            demand_tiles,
            selected_sites,
            site_estimate.cell_radius_km,
            cell_dl_capacity_mbps or 0.0,
            cell_ul_capacity_mbps or 0.0,
        )
        for site, load in zip(selected_sites, site_loads):
            site.estimated_dl_load_mbps = round(load["dl_mbps"], 2)
            site.estimated_ul_load_mbps = round(load["ul_mbps"], 2)
            if any(sector.get("dl_scale", 1.0) < 1.0 or sector.get("ul_scale", 1.0) < 1.0 for sector in load.get("sector_loads", [])):
                site.overloaded = True
            if cell_dl_capacity_mbps and load["dl_mbps"] > cell_dl_capacity_mbps:
                site.overloaded = True
            if cell_ul_capacity_mbps and load["ul_mbps"] > cell_ul_capacity_mbps:
                site.overloaded = True

    candidates = [
        CandidateSiteResult(
            id=candidate["id"],
            lat=candidate["lat"],
            lon=candidate["lon"],
            source=candidate["source"],
            accepted=candidate["accepted"],
            reasons=candidate["reasons"],
            score=candidate.get("score"),
            azimuths_deg=candidate["azimuths_deg"],
            beamwidth_deg=candidate["beamwidth_deg"],
            status=candidate["status"],
        )
        for candidate in candidate_records
    ]

    return PlacementPlanResult(
        mode=mode,
        metrics=PlacementMetrics(
            service_area_km2=round(usable_area_km2, 3),
            covered_area_km2=round(covered_area_km2, 3),
            coverage_ratio=round(coverage_ratio, 4),
            excluded_area_km2=round(excluded_area_km2, 3),
            candidate_sites=len(candidates),
            selected_sites=len(selected_sites),
            locked_sites=locked_sites,
            rejected_candidates=sum(1 for candidate in candidates if not candidate.accepted),
            alignment_length_km=round(alignment_length_km, 3),
        ),
        selected_sites=selected_sites,
        candidates=candidates,
        overlays=GeometryOverlay(
            service_area=service_area,
            exclusion_zones=exclusions,
            alignments=alignments,
            traffic_zones=inp.spatial_capacity.demand_zones if inp.spatial_capacity else [],
        ),
        spatial_capacity=spatial_capacity,
    )


def _candidate_allowed(
    lat: float,
    lon: float,
    service_area,
    exclusions,
    edge_setback_m: float,
    outside_buffer_m: float,
) -> bool:
    inside = point_in_polygon(lat, lon, service_area)
    if not inside:
        if outside_buffer_m <= 0:
            return False
        if point_to_polygon_boundary_distance_km(lat, lon, service_area) * 1000.0 > outside_buffer_m:
            return False
    if point_in_exclusion_zones(lat, lon, exclusions):
        return False
    if inside and not point_respects_setback(lat, lon, service_area, edge_setback_m):
        return False
    return True


def _generate_auto_candidates(
    inp: RFSizingInput,
    site_estimate: SiteEstimateResult,
    service_area,
    exclusions,
    alignments: list[LinearAlignment],
    selected_positions: list[tuple[float, float]],
    default_azimuths: list[float],
    default_beamwidth: float,
    geometry_mode: str,
) -> list[dict]:
    placement = inp.placement
    mode = placement.placement_mode
    min_spacing_m = placement.min_site_spacing_m or 0.0
    candidates = []
    seen = set()

    if mode in {"polygon_fill", "alignment_biased", "hybrid"} or not alignments:
        ref = centroid_from_points(service_area.outer)
        projected_outer = [latlon_to_xy_km(point.lat, point.lon, ref.lat, ref.lon) for point in service_area.outer]
        min_x = min(x for x, _ in projected_outer)
        max_x = max(x for x, _ in projected_outer)
        min_y = min(y for _, y in projected_outer)
        max_y = max(y for _, y in projected_outer)

        spacing_scale = 1.0
        if geometry_mode == "omni_360":
            spacing_scale *= 1.1
        elif geometry_mode == "directional_1_sector":
            spacing_scale *= 0.7
        elif geometry_mode == "sector_6":
            spacing_scale *= 0.85
        if mode == "alignment_biased":
            spacing_scale *= 1.35
        dx = (site_estimate.isd_km if site_estimate.isd_km > 0 else max(0.1, site_estimate.cell_radius_km)) * spacing_scale
        dy = math.sqrt(3) * dx / 2.0
        auto_index = 0
        row = 0
        y = min_y
        while y <= max_y + 1e-9:
            x = min_x + (dx / 2.0 if row % 2 else 0.0)
            while x <= max_x + 1e-9:
                lat, lon = xy_km_to_latlon(x, y, ref.lat, ref.lon)
                x += dx
                if not _candidate_allowed(lat, lon, service_area, exclusions, placement.edge_setback_m, placement.allow_outside_service_area_buffer_m):
                    continue
                if not _respects_min_spacing(lat, lon, selected_positions, min_spacing_m):
                    continue
                if (round(lat, 6), round(lon, 6)) in seen:
                    continue
                _append_candidate_variants(
                    candidates,
                    seen,
                    lat,
                    lon,
                    "auto",
                    auto_index,
                    inp.base_station.sectors,
                    default_azimuths,
                    default_beamwidth,
                )
                auto_index = len([c for c in candidates if c["source"] == "auto"])
            row += 1
            y += dy

        if not any(candidate["source"] == "auto" for candidate in candidates):
            fallback_point = centroid_from_points(service_area.outer)
            lat = fallback_point.lat
            lon = fallback_point.lon
            if _candidate_allowed(lat, lon, service_area, exclusions, placement.edge_setback_m, placement.allow_outside_service_area_buffer_m):
                if _respects_min_spacing(lat, lon, selected_positions, min_spacing_m):
                    _append_candidate_variants(
                        candidates,
                        seen,
                        lat,
                        lon,
                        "auto",
                        auto_index,
                        inp.base_station.sectors,
                        default_azimuths,
                        default_beamwidth,
                    )

    if alignments and mode in {"alignment_only", "alignment_biased", "hybrid"}:
        alignment_index = 0
        for alignment in alignments:
            spacing_m = alignment.preferred_spacing_m or site_estimate.isd_km * 1000.0
            for sample in sample_alignment_points(alignment, spacing_m):
                lat = sample["lat"]
                lon = sample["lon"]
                if not _candidate_allowed(lat, lon, service_area, exclusions, placement.edge_setback_m, placement.allow_outside_service_area_buffer_m):
                    continue
                if not point_near_alignment(lat, lon, alignment, alignment.buffer_m):
                    continue
                if not _respects_min_spacing(lat, lon, selected_positions, min_spacing_m):
                    continue
                key = (round(lat, 6), round(lon, 6))
                if key in seen:
                    continue
                seen.add(key)
                alignment_index += 1
                candidates.append(
                    {
                        "id": f"alignment-{alignment_index}",
                        "lat": lat,
                        "lon": lon,
                        "source": "alignment",
                        "accepted": False,
                        "reasons": [],
                        "azimuths_deg": _alignment_azimuths(inp.base_station.sectors, sample["bearing_deg"]),
                        "beamwidth_deg": default_beamwidth,
                        "status": "candidate",
                    }
                )

    if inp.spatial_capacity and inp.spatial_capacity.enabled and inp.spatial_capacity.demand_zones:
        hotspot_index = 0
        hotspot_spacing_km = max(0.02, inp.spatial_capacity.grid_resolution_m / 1000.0)
        for zone in inp.spatial_capacity.demand_zones:
            min_lat, min_lon, max_lat, max_lon = polygon_bbox(zone.polygon)
            ref = centroid_from_points(zone.polygon.outer)
            min_x, min_y = latlon_to_xy_km(min_lat, min_lon, ref.lat, ref.lon)
            max_x, max_y = latlon_to_xy_km(max_lat, max_lon, ref.lat, ref.lon)
            y = min(min_y, max_y)
            max_y_val = max(min_y, max_y)
            while y <= max_y_val + 1e-9:
                x = min(min_x, max_x)
                max_x_val = max(min_x, max_x)
                while x <= max_x_val + 1e-9:
                    lat, lon = xy_km_to_latlon(x, y, ref.lat, ref.lon)
                    x += hotspot_spacing_km
                    if not point_in_polygon(lat, lon, zone.polygon):
                        continue
                    if not _candidate_allowed(lat, lon, service_area, exclusions, placement.edge_setback_m, placement.allow_outside_service_area_buffer_m):
                        continue
                    if not _respects_min_spacing(lat, lon, selected_positions, min_spacing_m):
                        continue
                    key = (round(lat, 6), round(lon, 6))
                    if key in seen:
                        continue
                    seen.add(key)
                    hotspot_index += 1
                    candidates.append(
                        {
                            "id": f"hotspot-{hotspot_index}",
                            "lat": lat,
                            "lon": lon,
                            "source": "hotspot",
                            "accepted": False,
                            "reasons": [],
                            "azimuths_deg": list(default_azimuths),
                            "beamwidth_deg": default_beamwidth,
                            "status": "candidate",
                        }
                    )
                y += hotspot_spacing_km
    return candidates


def _candidate_azimuth_variants(sectors: int, default_azimuths: list[float], beamwidth_deg: float) -> list[list[float]]:
    if sectors != 1 or beamwidth_deg >= 359.0:
        return [list(default_azimuths)]

    step_deg = 30.0 if beamwidth_deg <= 90.0 else 45.0
    variants = []
    azimuth = 0.0
    while azimuth < 360.0 - 1e-6:
        variants.append([round(azimuth, 2)])
        azimuth += step_deg
    return variants


def _append_candidate_variants(
    candidates: list[dict],
    seen: set,
    lat: float,
    lon: float,
    source: str,
    current_index: int,
    sectors: int,
    default_azimuths: list[float],
    default_beamwidth: float,
) -> None:
    azimuth_variants = _candidate_azimuth_variants(sectors, default_azimuths, default_beamwidth)
    next_index = current_index
    for variant_idx, azimuths in enumerate(azimuth_variants, start=1):
        variant_key = (round(lat, 6), round(lon, 6), tuple(round(az, 2) for az in azimuths))
        if variant_key in seen:
            continue
        seen.add(variant_key)
        next_index += 1
        variant_suffix = f"-az{variant_idx}" if len(azimuth_variants) > 1 else ""
        candidates.append(
            {
                "id": f"{source}-{next_index}{variant_suffix}",
                "lat": lat,
                "lon": lon,
                "source": source,
                "accepted": False,
                "reasons": [],
                "azimuths_deg": list(azimuths),
                "beamwidth_deg": default_beamwidth,
                "status": "candidate",
            }
        )


def _alignment_azimuths(sectors: int, bearing_deg: float) -> list[float]:
    if sectors == 1:
        return [round(bearing_deg % 360.0, 2)]
    if sectors == 2:
        return [round(bearing_deg % 360.0, 2), round((bearing_deg + 180.0) % 360.0, 2)]
    base = _default_sector_azimuths(sectors)
    anchor = base[0] if base else 0.0
    return [round((bearing_deg + (az - anchor)) % 360.0, 2) for az in base]


def _target_coverage_ratio(inp: RFSizingInput) -> float:
    placement = inp.placement
    objective = placement.objective if placement else "balanced"
    base = inp.environment.coverage_probability
    if objective == "coverage_first":
        return min(0.99, max(base, 0.98))
    if objective == "capacity_first":
        return min(0.99, max(base, 0.95))
    return max(0.92, min(0.99, base))


def _candidate_score(objective: str, coverage_gain: float, demand_gain: float, source_bonus: float) -> float:
    if objective == "coverage_first":
        return coverage_gain + 0.05 * demand_gain + source_bonus
    if objective == "capacity_first":
        return demand_gain + 0.1 * coverage_gain + source_bonus
    return coverage_gain + demand_gain + source_bonus


def _default_sector_azimuths(sectors: int) -> list[float]:
    return {
        1: [0.0],
        2: [0.0, 180.0],
        3: [0.0, 120.0, 240.0],
        4: [0.0, 90.0, 180.0, 270.0],
        6: [0.0, 60.0, 120.0, 180.0, 240.0, 300.0],
    }.get(sectors, [0.0, 120.0, 240.0])


def _sample_service_points(service_area, exclusions, alignments, inp: RFSizingInput, cell_radius_km: float) -> list[tuple[float, float]]:
    if inp.placement and inp.placement.placement_mode == "alignment_only" and alignments:
        points = []
        seen = set()
        spacing_m = inp.spatial_capacity.grid_resolution_m if inp.spatial_capacity and inp.spatial_capacity.enabled else max(25.0, inp.base_station.height_m * 2)
        for alignment in alignments:
            for sample in sample_alignment_points(alignment, alignment.preferred_spacing_m or spacing_m):
                key = (round(sample["lat"], 6), round(sample["lon"], 6))
                if key not in seen:
                    seen.add(key)
                    points.append((sample["lat"], sample["lon"]))
        return points

    ref = centroid_from_points(service_area.outer)
    projected_outer = [latlon_to_xy_km(point.lat, point.lon, ref.lat, ref.lon) for point in service_area.outer]
    min_x = min(x for x, _ in projected_outer)
    max_x = max(x for x, _ in projected_outer)
    min_y = min(y for _, y in projected_outer)
    max_y = max(y for _, y in projected_outer)
    spacing_km = _adaptive_sample_spacing_km(service_area, inp, cell_radius_km, max_x - min_x, max_y - min_y)

    points = []
    y = min_y
    while y <= max_y + 1e-9:
        x = min_x
        while x <= max_x + 1e-9:
            lat, lon = xy_km_to_latlon(x + spacing_km / 2.0, y + spacing_km / 2.0, ref.lat, ref.lon)
            x += spacing_km
            if not point_in_polygon(lat, lon, service_area):
                continue
            if point_in_exclusion_zones(lat, lon, exclusions):
                continue
            points.append((lat, lon))
        y += spacing_km
    return points


def _adaptive_sample_spacing_km(service_area, inp: RFSizingInput, cell_radius_km: float, width_km: float, height_km: float) -> float:
    area_km2 = max(0.001, polygon_area_km2(service_area))
    target_samples = min(1200, max(220, int(area_km2 * 200)))
    bbox_area_km2 = max(0.001, width_km * height_km)
    bbox_spacing_km = math.sqrt(bbox_area_km2 / target_samples)

    rf_spacing_km = max(0.03, min(0.35, cell_radius_km / 2.5))
    spacing_km = min(bbox_spacing_km, rf_spacing_km)

    if inp.spatial_capacity and inp.spatial_capacity.enabled:
        spacing_km = min(spacing_km, max(0.03, inp.spatial_capacity.grid_resolution_m / 1000.0))

    return max(0.02, spacing_km)


def _covered_point_indices(sample_points, selected_sites, cell_radius_km: float) -> set[int]:
    covered = set()
    for idx, (lat, lon) in enumerate(sample_points):
        if _point_is_covered(lat, lon, selected_sites, cell_radius_km):
            covered.add(idx)
    return covered


def _coverage_indices_for_site(
    sample_points: list[tuple[float, float]],
    site_lat: float,
    site_lon: float,
    azimuths_deg: list[float],
    beamwidth_deg: float,
    cell_radius_km: float,
) -> set[int]:
    covered = set()
    site = SelectedSiteResult(
        id="candidate",
        lat=site_lat,
        lon=site_lon,
        source="auto",
        azimuths_deg=list(azimuths_deg),
        beamwidth_deg=beamwidth_deg,
        status="candidate",
    )
    for idx, (lat, lon) in enumerate(sample_points):
        if _point_is_covered(lat, lon, [site], cell_radius_km):
            covered.add(idx)
    return covered


def _respects_min_spacing(lat: float, lon: float, selected_positions: list[tuple[float, float]], min_spacing_m: float) -> bool:
    if min_spacing_m <= 0:
        return True
    return all(haversine_km(lat, lon, sel_lat, sel_lon) * 1000.0 >= min_spacing_m for sel_lat, sel_lon in selected_positions)


def _point_is_covered(lat: float, lon: float, selected_sites: list[SelectedSiteResult], cell_radius_km: float) -> bool:
    for site in selected_sites:
        distance_km = haversine_km(lat, lon, site.lat, site.lon)
        if distance_km <= 1e-6:
            return True
        if distance_km > cell_radius_km:
            continue
        azimuths = site.azimuths_deg or [0.0]
        beamwidth = site.beamwidth_deg or 360.0
        if beamwidth >= 359.0:
            return True
        point_bearing = bearing_deg(site.lat, site.lon, lat, lon)
        for azimuth in azimuths:
            if _angular_distance_deg(point_bearing, azimuth) <= beamwidth / 2.0:
                return True
    return False


def _angular_distance_deg(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)
