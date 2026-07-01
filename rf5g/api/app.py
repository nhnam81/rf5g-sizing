"""FastAPI backend for rf5g — 5G NR RF Coverage Sizing Tool."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

# Import version from package
from .. import __version__

from ..models.input_schema import RFSizingInput, ProjectConfig, EnvironmentConfig, BaseStationConfig, FrequencyConfig, UEConfig, MarginsConfig, QoSConfig
from ..models.output_schema import SizingOutput
from ..models.lookup_tables import BandLookup, AntennaConfigLookup, SINRCQILookup, QoSLookup, ShadowFadingLookup, PowerClassLookup
from ..engine.propagation import path_loss, invert_mapl_to_radius, los_probability
from ..engine.link_budget import calculate_link_budget
from ..engine.site_estimator import estimate_sites
from ..engine.sinr_mapper import map_sinr_to_cqi, calculate_cell_throughput, coverage_percentage
from ..engine.capacity import calculate_capacity
from ..engine.qos_verifier import verify_qos
from ..engine.recommender import generate_recommendations
from ..viz.coverage_map import (
    generate_coverage_map, generate_interactive_map,
    export_sites_json, export_sites_csv, import_sites_json, import_sites_csv,
    generate_hex_grid,
)
from ..viz.charts import plot_link_budget, plot_sinr_heatmap, plot_service_zones, plot_capacity_comparison
from ..viz.report import generate_markdown_report, generate_html_report
from ..cli import _run_sizing
from ..engine.geometry import line_length_km, polygon_area_km2
from ..engine.placement_planner import effective_planning_area_km2

app = FastAPI(
    title="5G NR RF Coverage Sizing Tool",
    description="API for 5G NR RF coverage sizing — 3GPP TR 38.901",
    version=__version__,
)

# CORS for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(__file__).parent.parent / "data"


# --- Helper: run sizing from input ---
def _sizing_from_params(
    project: Optional[ProjectConfig] = None,
    environment: Optional[EnvironmentConfig] = None,
    base_station: Optional[BaseStationConfig] = None,
    frequency: Optional[FrequencyConfig] = None,
    user_equipment: Optional[UEConfig] = None,
    margins: Optional[MarginsConfig] = None,
    qos: Optional[QoSConfig] = None,
) -> SizingOutput:
    inp = RFSizingInput(
        project=project or ProjectConfig(),
        environment=environment or EnvironmentConfig(),
        base_station=base_station or BaseStationConfig(),
        frequency=frequency or FrequencyConfig(),
        user_equipment=user_equipment or UEConfig(),
        margins=margins or MarginsConfig(),
        qos=qos or QoSConfig(),
    )
    return _run_sizing(inp)


# --- Endpoints ---

@app.get("/", tags=["info"])
async def root():
    """API info."""
    return {
        "name": "5G NR RF Coverage Sizing Tool",
        "version": __version__,
        "docs": "/docs",
        "endpoints": ["/size", "/placement/plan", "/geometry/validate", "/compare", "/map", "/report", "/charts", "/tables"],
    }


@app.post("/size", response_model=SizingOutput, tags=["sizing"])
async def size(input_data: RFSizingInput):
    """Run complete 5G NR RF sizing calculation."""
    try:
        result = _run_sizing(input_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/placement/plan", response_model=SizingOutput, tags=["planning"])
async def placement_plan(input_data: RFSizingInput):
    """Run geometry-aware placement planning when placement inputs are provided."""
    try:
        return _run_sizing(input_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/geometry/validate", tags=["planning"])
async def validate_geometry(input_data: RFSizingInput):
    """Validate planning geometry inputs and summarize derived metrics."""
    try:
        placement = input_data.placement
        if not placement or not placement.service_area:
            return {
                "valid": False,
                "message": "No placement.service_area provided",
            }
        spatial_capacity = input_data.spatial_capacity
        return {
            "valid": True,
            "service_area_km2": round(polygon_area_km2(placement.service_area), 3),
            "effective_planning_area_km2": round(effective_planning_area_km2(input_data), 3),
            "exclusion_zones": len(placement.exclusion_zones),
            "excluded_area_km2": round(sum(polygon_area_km2(zone.polygon) for zone in placement.exclusion_zones), 3),
            "alignments": len(placement.alignments),
            "alignment_length_km": round(sum(line_length_km(alignment) for alignment in placement.alignments), 3),
            "planned_sites": len(placement.planned_sites),
            "spatial_capacity_enabled": bool(spatial_capacity and spatial_capacity.enabled),
            "traffic_zones": len(spatial_capacity.demand_zones) if spatial_capacity else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/size/quick", response_model=SizingOutput, tags=["sizing"])
async def size_quick(
    area_km2: float = Query(50.0, gt=0),
    scenario: str = Query("UMa"),
    band: str = Query("n78"),
    bandwidth_mhz: float = Query(100.0, gt=0),
    tx_power_w: float = Query(200.0, gt=0),
    antenna_config: str = Query("32T32R"),
    obstacle_density: str = Query("heavy"),
    users_per_km2: float = Query(300.0, gt=0),
    dl_per_user_mbps: float = Query(20.0, gt=0),
):
    """Quick sizing with minimal parameters — uses sensible defaults."""
    try:
        inp = RFSizingInput(
            project=ProjectConfig(area_km2=area_km2),
            environment=EnvironmentConfig(scenario=scenario, obstacle_density=obstacle_density),
            base_station=BaseStationConfig(tx_power_w=tx_power_w, antenna_config=antenna_config),
            frequency=FrequencyConfig(band=band, bandwidth_mhz=bandwidth_mhz),
            qos=QoSConfig(users_per_km2=users_per_km2, dl_per_user_mbps=dl_per_user_mbps),
        )
        result = _run_sizing(inp)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class CompareRequest(BaseModel):
    """Compare multiple scenarios."""
    scenarios: List[RFSizingInput]


@app.post("/compare", tags=["sizing"])
async def compare(request: CompareRequest):
    """Compare multiple sizing scenarios side by side."""
    if len(request.scenarios) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 scenarios to compare")
    if len(request.scenarios) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 scenarios")

    results = []
    for i, scenario in enumerate(request.scenarios):
        try:
            result = _run_sizing(scenario)
            results.append(result)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Scenario {i} error: {e}")

    # Build comparison summary
    comparison = []
    for r in results:
        comparison.append({
            "project_name": r.project_name,
            "environment": r.environment,
            "band": r.band,
            "bandwidth_mhz": r.bandwidth_mhz,
            "tx_power_w": r.tx_power_w,
            "cell_radius_m": r.propagation.cell_radius_m,
            "coverage_sites": r.site_estimate.coverage_sites,
            "limiting_link": r.site_estimate.limiting_link,
            "sinr_db": r.sinr.sinr_db,
            "cqi": r.sinr.cqi,
            "modulation": r.sinr.modulation,
            "capacity_sufficient": r.capacity.capacity_sufficient if r.capacity else None,
            "total_sites": r.capacity.total_sites if r.capacity else None,
            "total_capacity_dl_gbps": r.capacity.total_capacity_dl_gbps if r.capacity else None,
            "total_demand_dl_gbps": r.capacity.total_demand_dl_gbps if r.capacity else None,
        })

    # Generate comparison highlights
    highlights = _generate_comparison_highlights(results)

    return {"comparison": comparison, "highlights": highlights, "results": results}


def _generate_comparison_highlights(results: list) -> dict:
    """Generate comparison highlights for decision support.

    Returns:
        Dictionary with:
        - winner: scenario name with best overall metrics
        - tradeoffs: list of tradeoff observations
        - recommendations: list of recommendations based on comparison
    """
    if len(results) < 2:
        return {"winner": None, "tradeoffs": [], "recommendations": []}

    # Find best scenario by coverage sites (fewer is better)
    best_coverage = min(results, key=lambda r: r.site_estimate.coverage_sites)

    # Find best scenario by capacity (if applicable)
    best_capacity = None
    capacity_scenarios = [r for r in results if r.capacity and r.capacity.capacity_sufficient]
    if capacity_scenarios:
        best_capacity = min(capacity_scenarios, key=lambda r: r.capacity.total_sites)

    # Find best SINR
    best_sinr = max(results, key=lambda r: r.sinr.sinr_db)

    # Generate tradeoffs
    tradeoffs = []

    # Coverage vs sites tradeoff
    if len(results) >= 2:
        r1, r2 = results[0], results[1]
        site_diff = abs(r1.site_estimate.coverage_sites - r2.site_estimate.coverage_sites)
        if site_diff > 100:
            tradeoffs.append(
                f"Site count varies significantly: {r1.project_name} needs {r1.site_estimate.coverage_sites} sites vs {r2.project_name} needs {r2.site_estimate.coverage_sites} sites"
            )

    # Band/throughput tradeoff
    bandwidths = [r.bandwidth_mhz for r in results]
    if max(bandwidths) != min(bandwidths):
        tradeoffs.append(
            f"Bandwidth varies: {min(bandwidths)} MHz to {max(bandwidths)} MHz — higher bandwidth provides more capacity but may have reduced coverage"
        )

    # Limiting link comparison
    limiting_links = [r.site_estimate.limiting_link for r in results]
    if "UL" in limiting_links and "DL" in limiting_links:
        tradeoffs.append(
            "Different limiting links across scenarios — some are UL-limited, others DL-limited"
        )

    # Capacity vs coverage
    if best_coverage and best_capacity and best_coverage.project_name != best_capacity.project_name:
        tradeoffs.append(
            f"Coverage-optimal ({best_coverage.project_name}) differs from capacity-optimal ({best_capacity.project_name})"
        )

    # Generate recommendations
    recommendations = []

    if best_coverage.site_estimate.coverage_sites < best_sinr.site_estimate.coverage_sites:
        recommendations.append(
            f"{best_coverage.project_name} needs fewer sites but has lower SINR — consider if coverage or signal quality is priority"
        )

    if best_sinr.sinr_db > best_coverage.sinr.sinr_db + 3:
        recommendations.append(
            f"{best_sinr.project_name} has significantly better SINR (+{best_sinr.sinr_db - best_coverage.sinr.sinr_db:.1f} dB) — better for high-throughput services"
        )

    # Check for capacity constraints
    capacity_insufficient = [r for r in results if r.capacity and not r.capacity.capacity_sufficient]
    if capacity_insufficient:
        recommendations.append(
            f"{len(capacity_insufficient)} scenario(s) have insufficient capacity — consider adding sites or reducing demand"
        )

    # Determine overall winner
    # Score: minimize sites, maximize SINR, ensure capacity
    def score(r):
        score = 0
        # Fewer sites is better
        score -= r.site_estimate.coverage_sites
        # Higher SINR is better
        score += r.sinr.sinr_db
        # Capacity sufficient is better
        if r.capacity and r.capacity.capacity_sufficient:
            score += 100
        return score

    winner = max(results, key=score)

    return {
        "winner": winner.project_name,
        "winner_reason": f"Best overall score based on sites ({winner.site_estimate.coverage_sites}), SINR ({winner.sinr.sinr_db:.1f} dB), and capacity",
        "tradeoffs": tradeoffs,
        "recommendations": recommendations,
        "best_coverage": best_coverage.project_name,
        "best_capacity": best_capacity.project_name if best_capacity else None,
        "best_sinr": best_sinr.project_name,
    }


@app.post("/map", tags=["visualization"])
async def create_map(
    input_data: RFSizingInput,
    lat: float = Query(10.8231),
    lon: float = Query(106.6297),
    zoom: int = Query(12),
):
    """Generate interactive Folium coverage map."""
    try:
        result = _run_sizing(input_data)
        path = generate_coverage_map(result, center_lat=lat, center_lon=lon, zoom_start=zoom)
        return HTMLResponse(content=open(path, encoding="utf-8").read(), status_code=200)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/report/html", tags=["visualization"])
async def html_report(input_data: RFSizingInput):
    """Generate HTML sizing report."""
    try:
        result = _run_sizing(input_data)
        path = generate_html_report(result)
        content = open(path, encoding="utf-8").read()
        return HTMLResponse(content=content, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/report/markdown", tags=["visualization"])
async def markdown_report(input_data: RFSizingInput):
    """Generate Markdown sizing report."""
    try:
        result = _run_sizing(input_data)
        path = generate_markdown_report(result)
        content = open(path, encoding="utf-8").read()
        return {"report": content, "project_name": result.project_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/tables/bands", tags=["lookup"])
async def list_bands():
    """List all available NR bands."""
    lookup = BandLookup()
    bands = []
    for b in lookup.list_bands():
        bands.append(lookup.get_band(b))
    return {"bands": bands}


@app.get("/tables/bands/{band_id}", tags=["lookup"])
async def get_band(band_id: str):
    """Get details for a specific NR band."""
    lookup = BandLookup()
    try:
        return lookup.get_band(band_id)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=404, detail=f"Band {band_id} not found")


@app.get("/tables/antenna_configs", tags=["lookup"])
async def list_antenna_configs():
    """List available antenna configurations."""
    lookup = AntennaConfigLookup()
    return {"configs": lookup.list_configs()}


@app.get("/tables/qos", tags=["lookup"])
async def list_qos():
    """List QoS service types and requirements."""
    lookup = QoSLookup()
    services = []
    for svc in ["vonr", "video_hd", "video_4k", "data", "gaming", "iot"]:
        try:
            services.append(lookup.get_service(svc))
        except Exception:
            pass
    return {"services": services}

# ── Sites Export/Import Endpoints ──

class SitesExportRequest(BaseModel):
    """Request to export hex-grid sites."""
    input_data: RFSizingInput
    format: str = "json"  # json or csv

class SitesImportRequest(BaseModel):
    """Request to generate map with custom sites."""
    input_data: RFSizingInput
    sites: List[List[float]]  # [[lat, lon], ...]
    lat: float = 10.8231
    lon: float = 106.6297
    zoom: int = 12

@app.post("/sites/export", tags=["sites"])
async def export_sites(request: SitesExportRequest):
    """Export hex-grid site positions (WGS84 coordinates)."""
    try:
        result = _run_sizing(request.input_data)
        sites = generate_hex_grid(
            request.input_data.project.center_lat,
            request.input_data.project.center_lon,
            result.site_estimate.isd_km,
            result.site_estimate.coverage_sites,
        )
        return {
            "coordinate_system": "WGS84 (EPSG:4326)",
            "total_sites": len(sites),
            "sites": [
                {"site_id": i + 1, "latitude": round(lat, 6), "longitude": round(lon, 6)}
                for i, (lat, lon) in enumerate(sites)
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/sites/map", tags=["sites"])
async def map_with_sites(request: SitesImportRequest):
    """Generate interactive coverage map with custom site positions."""
    try:
        result = _run_sizing(request.input_data)
        custom_sites = [(s[0], s[1]) for s in request.sites]
        path = generate_interactive_map(
            result,
            center_lat=request.lat,
            center_lon=request.lon,
            zoom_start=request.zoom,
            custom_sites=custom_sites,
        )
        content = open(path, encoding="utf-8").read()
        return HTMLResponse(content=content, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))