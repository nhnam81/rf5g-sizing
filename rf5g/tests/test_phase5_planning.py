"""Tests for Phase A/B/C/D geometry-aware placement planning."""
import os
import tempfile

from fastapi.testclient import TestClient

from rf5g.api.app import app
from rf5g.cli import _run_sizing
from rf5g.engine.geometry import haversine_km, point_in_exclusion_zones, point_in_polygon
from rf5g.engine.placement_planner import _sample_service_points
from rf5g.engine.site_estimator import estimate_sites
from rf5g.models.antenna_pattern import antenna_pattern_from_catalog, pattern_for_config
from rf5g.models.input_schema import RFSizingInput
from rf5g.viz.coverage_map import generate_coverage_map


client = TestClient(app)


def planning_input() -> RFSizingInput:
    return RFSizingInput(
        project={"name": "Polygon Plan", "area_km2": 1.0, "center_lat": 10.78, "center_lon": 106.70},
        base_station={"antenna_config": "4T4R", "sectors": 3},
        placement={
            "service_area": {
                "outer": [
                    {"lat": 10.775, "lon": 106.695},
                    {"lat": 10.775, "lon": 106.705},
                    {"lat": 10.785, "lon": 106.705},
                    {"lat": 10.785, "lon": 106.695},
                ],
                "name": "Target area",
            },
            "exclusion_zones": [
                {
                    "polygon": {
                        "outer": [
                            {"lat": 10.779, "lon": 106.699},
                            {"lat": 10.779, "lon": 106.701},
                            {"lat": 10.781, "lon": 106.701},
                            {"lat": 10.781, "lon": 106.699},
                        ]
                    },
                    "reason": "no_build",
                }
            ],
            "planned_sites": [
                {
                    "id": "locked-1",
                    "lat": 10.776,
                    "lon": 106.696,
                    "status": "locked",
                }
            ],
        },
    )


def alignment_input() -> RFSizingInput:
    return RFSizingInput(
        project={"name": "Alignment Plan", "area_km2": 1.0, "center_lat": 10.78, "center_lon": 106.70},
        base_station={"antenna_config": "4T4R", "sectors": 1},
        placement={
            "service_area": {
                "outer": [
                    {"lat": 10.775, "lon": 106.694},
                    {"lat": 10.775, "lon": 106.706},
                    {"lat": 10.785, "lon": 106.706},
                    {"lat": 10.785, "lon": 106.694},
                ],
                "name": "Alignment target",
            },
            "alignments": [
                {
                    "name": "Tunnel axis",
                    "alignment_type": "tunnel",
                    "preferred_spacing_m": 120,
                    "points": [
                        {"lat": 10.780, "lon": 106.695},
                        {"lat": 10.780, "lon": 106.705},
                    ],
                }
            ],
            "placement_mode": "alignment_only",
        },
    )


def directional_polygon_input() -> RFSizingInput:
    return RFSizingInput(
        project={"name": "Directional Polygon", "area_km2": 0.51, "center_lat": 10.78, "center_lon": 106.70},
        environment={"scenario": "RMa", "obstacle_density": "medium", "coverage_probability": 0.95},
        base_station={
            "antenna_config": "2T2R",
            "antenna_vendor": "Prose Technologies",
            "antenna_model": "S-Wave 40D-65-9D-64K-B2",
            "tx_power_w": 20.0,
            "sectors": 1,
        },
        frequency={"band": "n77", "bandwidth_mhz": 50.0, "scs_khz": 30, "tdd_dl_ratio": 0.7},
        placement={
            "service_area": {
                "outer": [
                    {"lat": 10.7792, "lon": 106.6991},
                    {"lat": 10.7797, "lon": 106.7017},
                    {"lat": 10.7784, "lon": 106.7031},
                    {"lat": 10.7760, "lon": 106.7010},
                ],
                "name": "Directional polygon",
            },
            "placement_mode": "polygon_fill",
            "objective": "coverage_first",
        },
    )


def large_polygon_input() -> RFSizingInput:
    return RFSizingInput(
        project={"name": "Large Polygon", "area_km2": 12.0, "center_lat": 10.78, "center_lon": 106.70},
        base_station={"antenna_config": "4T4R", "sectors": 3},
        placement={
            "service_area": {
                "outer": [
                    {"lat": 10.760, "lon": 106.680},
                    {"lat": 10.760, "lon": 106.720},
                    {"lat": 10.775, "lon": 106.730},
                    {"lat": 10.795, "lon": 106.728},
                    {"lat": 10.805, "lon": 106.710},
                    {"lat": 10.800, "lon": 106.688},
                    {"lat": 10.785, "lon": 106.676},
                ],
                "name": "Large polygon",
            },
            "exclusion_zones": [
                {
                    "reason": "water",
                    "polygon": {
                        "outer": [
                            {"lat": 10.782, "lon": 106.699},
                            {"lat": 10.782, "lon": 106.707},
                            {"lat": 10.788, "lon": 106.707},
                            {"lat": 10.788, "lon": 106.699},
                        ]
                    },
                }
            ],
        },
        spatial_capacity={"enabled": True, "grid_resolution_m": 80},
    )


def capacity_input(objective: str) -> RFSizingInput:
    return RFSizingInput(
        project={"name": f"Capacity {objective}", "area_km2": 1.0, "center_lat": 10.78, "center_lon": 106.70},
        base_station={"antenna_config": "4T4R", "sectors": 3},
        qos={"users_per_km2": 1200, "dl_per_user_mbps": 40, "ul_per_user_mbps": 8, "concurrent_ratio": 0.25},
        placement={
            "service_area": {
                "outer": [
                    {"lat": 10.775, "lon": 106.695},
                    {"lat": 10.775, "lon": 106.705},
                    {"lat": 10.785, "lon": 106.705},
                    {"lat": 10.785, "lon": 106.695},
                ],
                "name": "Target area",
            },
            "objective": objective,
        },
        spatial_capacity={
            "enabled": True,
            "grid_resolution_m": 80,
            "demand_zones": [
                {
                    "name": "Hotspot",
                    "weight": 8.0,
                    "polygon": {
                        "outer": [
                            {"lat": 10.782, "lon": 106.702},
                            {"lat": 10.782, "lon": 106.705},
                            {"lat": 10.785, "lon": 106.705},
                            {"lat": 10.785, "lon": 106.702},
                        ]
                    },
                }
            ],
        },
    )


class TestPlanningIntegration:
    def test_run_sizing_returns_placement_plan(self):
        inp = planning_input()
        result = _run_sizing(inp)

        assert result.placement_plan is not None
        assert result.placement_plan.metrics.service_area_km2 > 0
        assert result.site_estimate.coverage_sites == result.placement_plan.metrics.selected_sites
        assert result.placement_plan.metrics.coverage_ratio >= inp.environment.coverage_probability
        assert result.placement_plan.metrics.candidate_sites > result.placement_plan.metrics.selected_sites
        assert result.placement_plan.metrics.rejected_candidates > 0
        assert any(site.id == "locked-1" and site.status == "locked" for site in result.placement_plan.selected_sites)

        service_area = inp.placement.service_area
        exclusions = inp.placement.exclusion_zones
        for site in result.placement_plan.selected_sites:
            if site.status == "locked":
                continue
            assert point_in_polygon(site.lat, site.lon, service_area)
            assert not point_in_exclusion_zones(site.lat, site.lon, exclusions)

    def test_generate_coverage_map_renders_planning_overlays(self):
        result = _run_sizing(planning_input())
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = generate_coverage_map(result, output_path=f.name)
            assert os.path.exists(path)
            content = open(path, encoding="utf-8").read()
            assert "Service area" in content
            assert "Exclusion zone: no_build" in content
            assert "locked-1" in content
            try:
                os.unlink(path)
            except PermissionError:
                pass

    def test_alignment_only_uses_alignment_candidates_and_azimuths(self):
        result = _run_sizing(alignment_input())
        assert result.placement_plan is not None
        assert result.placement_plan.mode == "alignment_only"
        auto_sites = [site for site in result.placement_plan.selected_sites if site.source == "alignment"]
        assert auto_sites, "Expected alignment-derived selected sites"
        first_site = auto_sites[0]
        assert first_site.azimuths_deg, "Expected inferred azimuths"
        assert abs(((first_site.azimuths_deg[0] - 90.0 + 180.0) % 360.0) - 180.0) < 20.0

    def test_polygon_fill_single_sector_directional_does_not_return_zero_sites(self):
        result = _run_sizing(directional_polygon_input())
        assert result.placement_plan is not None
        assert result.placement_plan.mode == "polygon_fill"
        assert result.placement_plan.metrics.selected_sites > 0
        assert result.placement_plan.metrics.coverage_ratio > 0
        assert any(site.azimuths_deg for site in result.placement_plan.selected_sites)

    def test_capacity_map_renders_traffic_zone_overlay(self):
        result = _run_sizing(capacity_input("capacity_first"))
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = generate_coverage_map(result, output_path=f.name)
            assert os.path.exists(path)
            content = open(path, encoding="utf-8").read()
            assert "Traffic zone" in content
            try:
                os.unlink(path)
            except PermissionError:
                pass

    def test_adaptive_sampling_increases_resolution_for_large_polygon(self):
        inp = large_polygon_input()
        service_area = inp.placement.service_area
        exclusions = inp.placement.exclusion_zones
        samples = _sample_service_points(service_area, exclusions, inp.placement.alignments, inp, 0.53)
        assert len(samples) > 784
        for lat, lon in samples[:100]:
            assert point_in_polygon(lat, lon, service_area)
            assert not point_in_exclusion_zones(lat, lon, exclusions)

    def test_site_estimator_distinguishes_omni_directional_and_multisector_modes(self):
        cell_radius_km = 0.53
        area_km2 = 4.30
        omni = estimate_sites(area_km2, cell_radius_km, sectors=1, antenna_pattern=pattern_for_config("2T2R"))
        directional = estimate_sites(
            area_km2,
            cell_radius_km,
            sectors=1,
            antenna_pattern=antenna_pattern_from_catalog("Prose Technologies", "S-Wave 40D-65-9D-64K-B2", freq_mhz=3700),
        )
        tri = estimate_sites(area_km2, cell_radius_km, sectors=3, antenna_pattern=pattern_for_config("4T4R"))
        six = estimate_sites(area_km2, cell_radius_km, sectors=6, antenna_pattern=pattern_for_config("16T16R"))

        assert omni.isd_km > directional.isd_km
        assert omni.coverage_sites < directional.coverage_sites
        assert six.isd_km < tri.isd_km < omni.isd_km

    def test_capacity_first_improves_hotspot_relief(self):
        coverage_result = _run_sizing(capacity_input("coverage_first"))
        capacity_result = _run_sizing(capacity_input("capacity_first"))
        assert coverage_result.placement_plan is not None
        assert capacity_result.placement_plan is not None
        assert coverage_result.placement_plan.spatial_capacity is not None
        assert capacity_result.placement_plan.spatial_capacity is not None

        coverage_spatial = coverage_result.placement_plan.spatial_capacity
        capacity_spatial = capacity_result.placement_plan.spatial_capacity
        assert capacity_result.placement_plan.metrics.coverage_ratio >= 0.95
        assert capacity_spatial.unserved_dl_gbps <= coverage_spatial.unserved_dl_gbps
        assert capacity_spatial.hotspot_tiles <= coverage_spatial.hotspot_tiles

    def test_spatial_capacity_marks_overloaded_selected_sites(self):
        result = _run_sizing(capacity_input("capacity_first"))
        assert result.placement_plan is not None
        assert result.placement_plan.spatial_capacity is not None
        overloaded = [site for site in result.placement_plan.selected_sites if site.overloaded]
        assert len(overloaded) == result.placement_plan.spatial_capacity.overloaded_sites
        assert all(site.estimated_dl_load_mbps is not None for site in overloaded)


class TestPlanningAPI:
    def test_geometry_validate_endpoint(self):
        resp = client.post("/geometry/validate", json=planning_input().model_dump())
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["service_area_km2"] > 0
        assert data["exclusion_zones"] == 1
        assert data["planned_sites"] == 1

    def test_placement_plan_endpoint(self):
        resp = client.post("/placement/plan", json=planning_input().model_dump())
        assert resp.status_code == 200
        data = resp.json()
        assert data["placement_plan"] is not None
        assert data["placement_plan"]["metrics"]["selected_sites"] > 0
        assert data["placement_plan"]["metrics"]["candidate_sites"] > data["placement_plan"]["metrics"]["selected_sites"]
        assert data["placement_plan"]["metrics"]["coverage_ratio"] >= planning_input().environment.coverage_probability

    def test_geometry_validate_reports_spatial_capacity(self):
        resp = client.post("/geometry/validate", json=capacity_input("capacity_first").model_dump())
        assert resp.status_code == 200
        data = resp.json()
        assert data["spatial_capacity_enabled"] is True
        assert data["traffic_zones"] == 1
