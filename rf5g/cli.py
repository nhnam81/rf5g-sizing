"""CLI for rf5g — 5G NR RF Coverage Sizing Tool."""
from __future__ import annotations
import json
import sys
import math
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .models.input_schema import RFSizingInput
from .models.lookup_tables import BandLookup, PowerClassLookup, AntennaConfigLookup, SINRCQILookup, QoSLookup, ShadowFadingLookup
from .models.output_schema import SizingOutput
from .engine.propagation import path_loss, invert_mapl_to_radius, los_probability
from .engine.link_budget import calculate_link_budget, resolve_effective_base_station
from .engine.site_estimator import estimate_sites
from .engine.sinr_mapper import map_sinr_to_cqi, calculate_cell_throughput, coverage_percentage
from .engine.capacity import calculate_capacity
from .engine.qos_verifier import verify_qos
from .engine.recommender import generate_recommendations
from .engine.warnings import generate_warnings
from .engine.summary import generate_executive_summary, format_summary_text, generate_planning_scorecard, format_scorecard_text
from .engine.placement_planner import build_placement_plan, effective_planning_area_km2
from .viz.coverage_map import (
    generate_coverage_map, generate_interactive_map,
    export_sites_json, export_sites_csv, import_sites_json, import_sites_csv,
    recalculate_from_sites,
)
from .viz.charts import plot_link_budget, plot_sinr_heatmap, plot_service_zones, plot_capacity_comparison
from .viz.report import generate_markdown_report, generate_html_report

app = typer.Typer(
    name="rf5g",
    help="5G NR RF Coverage Sizing Tool — 3GPP TR 38.901",
    no_args_is_help=True,
)
console = Console()


def _resolve_equipment_provenance(inp: RFSizingInput, effective_bs: dict) -> tuple[dict | None, dict | None]:
    radio_details = None
    antenna_details = None

    if inp.base_station.radio_vendor and inp.base_station.radio_model:
        try:
            from .models.antenna_pattern import get_catalog_radio
            radio = get_catalog_radio(inp.base_station.radio_vendor, inp.base_station.radio_model)
            radio_details = {
                'vendor': radio.get('vendor'),
                'model': radio.get('model'),
                'source_pdf': radio.get('source_pdf'),
                'import_confidence': radio.get('import_confidence'),
            }
        except Exception:
            radio_details = {
                'vendor': inp.base_station.radio_vendor,
                'model': inp.base_station.radio_model,
            }

    if inp.base_station.antenna_pattern_file:
        antenna_details = {
            'vendor': inp.base_station.antenna_vendor,
            'model': inp.base_station.antenna_model,
            'pattern_source': effective_bs.get('pattern_source'),
            'pattern_source_type': inp.base_station.antenna_pattern_format or 'auto',
            'pattern_asset': inp.base_station.antenna_pattern_file,
        }
    elif inp.base_station.antenna_vendor and inp.base_station.antenna_model:
        try:
            from .models.antenna_pattern import get_catalog_antenna
            ant = get_catalog_antenna(inp.base_station.antenna_vendor, inp.base_station.antenna_model)
            antenna_details = {
                'vendor': ant.get('vendor'),
                'model': ant.get('model'),
                'source_pdf': ant.get('source_pdf'),
                'import_confidence': ant.get('import_confidence'),
                'pattern_source_type': ant.get('pattern_source_type') or ant.get('pattern_type'),
                'pattern_asset': ant.get('pattern_asset') or ant.get('atoll_file') or ant.get('pattern_file'),
                'pattern_source': effective_bs.get('pattern_source'),
            }
        except Exception:
            antenna_details = {
                'vendor': inp.base_station.antenna_vendor,
                'model': inp.base_station.antenna_model,
                'pattern_source': effective_bs.get('pattern_source'),
            }
    elif effective_bs.get('pattern_source'):
        antenna_details = {
            'pattern_source': effective_bs.get('pattern_source'),
        }

    return radio_details, antenna_details


def _run_sizing(inp: RFSizingInput) -> SizingOutput:
    """Run complete sizing calculation from input."""
    # Initialize lookups
    band_lookup = BandLookup()
    pc_lookup = PowerClassLookup()
    ant_lookup = AntennaConfigLookup()
    sinr_lookup = SINRCQILookup()
    qos_lookup = QoSLookup()
    sf_lookup = ShadowFadingLookup()

    effective_bs = resolve_effective_base_station(inp, ant_lookup)

    # Calculate link budget
    dl_result, ul_result = calculate_link_budget(inp, band_lookup, pc_lookup, ant_lookup, sf_lookup)

    # Determine limiting link
    mapl = min(dl_result.mapl_db, ul_result.mapl_db)
    limiting_link = "UL" if ul_result.mapl_db <= dl_result.mapl_db else "DL"

    # Get carrier frequency
    fc_mhz = band_lookup.get_fc(inp.frequency.band)
    fc_ghz = fc_mhz / 1000.0

    # Propagation model
    scenario = inp.environment.scenario
    h_bs = inp.base_station.height_m
    h_ut = inp.user_equipment.height_m

    # Choose path type based on environment
    if inp.environment.obstacle_density == "heavy":
        path_type = "NLOS"
    elif inp.environment.obstacle_density == "light":
        path_type = "LOS"
    else:
        path_type = "combined"

    # Invert MAPL → cell radius
    cell_radius_m = invert_mapl_to_radius(
        scenario=scenario,
        path_type=path_type,
        mapl_db=mapl,
        fc_ghz=fc_ghz,
        h_bs=h_bs,
        h_ut=h_ut,
    )
    cell_radius_km = cell_radius_m / 1000.0

    # Propagation result
    pl_at_radius = path_loss(scenario, path_type, cell_radius_m, fc_ghz, h_bs, h_ut)
    pr_los = los_probability(scenario, cell_radius_m)

    from .models.output_schema import PropagationResult
    prop = PropagationResult(
        model=f"{scenario}_{path_type}",
        path_loss_db=round(pl_at_radius, 2),
        cell_radius_km=round(cell_radius_km, 4),
        cell_radius_m=round(cell_radius_m, 1),
        los_probability=round(pr_los, 4),
        combined_path_loss_db=None if path_type != "combined" else round(pl_at_radius, 2),
    )

    planning_area_km2 = effective_planning_area_km2(inp)

    # Site estimation
    site = estimate_sites(
        area_km2=planning_area_km2,
        cell_radius_km=cell_radius_km,
        sectors=inp.base_station.sectors,
        overlap_factor=inp.margins.overlap_factor,
        limiting_link=limiting_link,
        antenna_pattern=effective_bs["pattern"],
    )

    # SINR at cell edge
    sinr_db = mapl - pl_at_radius - inp.margins.interference_db

    # Get CQI/SE from SINR
    cqi_entry = map_sinr_to_cqi(sinr_db, sinr_lookup)

    from .models.output_schema import SINRResult
    sinr_result = SINRResult(
        sinr_db=round(sinr_db, 2),
        cqi=cqi_entry["cqi"],
        modulation=cqi_entry["modulation"],
        spectral_efficiency_bps_hz=round(cqi_entry["spectral_efficiency"], 4),
        code_rate=round(cqi_entry["code_rate_x1024"] / 1024, 4),
    )

    # QoS verification
    qos_results = verify_qos(inp, sinr_db, cell_radius_km, qos_lookup)

    capacity_probe = calculate_capacity(inp, sinr_db, max(1, site.coverage_sites), band_lookup, sinr_lookup, area_km2=planning_area_km2)
    placement_plan = build_placement_plan(
        inp,
        site,
        effective_bs["pattern"],
        cell_dl_capacity_mbps=capacity_probe.cell_throughput_dl_mbps,
        cell_ul_capacity_mbps=capacity_probe.cell_throughput_ul_mbps,
    )
    if placement_plan is not None:
        site.coverage_sites = placement_plan.metrics.selected_sites

    # Capacity dimensioning
    capacity = calculate_capacity(inp, sinr_db, site.coverage_sites, band_lookup, sinr_lookup, area_km2=planning_area_km2)

    radio_details, antenna_details = _resolve_equipment_provenance(inp, effective_bs)

    # Recommendations
    # Build partial output for recommender
    from .models.output_schema import SizingOutput as SO
    result = SO(
        project_name=inp.project.name,
        environment=inp.environment.scenario,
        band=inp.frequency.band,
        bandwidth_mhz=inp.frequency.bandwidth_mhz,
        antenna_config=effective_bs["antenna_config"],
        tx_power_w=effective_bs["tx_power_w"],
        input_antenna_config=inp.base_station.antenna_config,
        input_tx_power_w=inp.base_station.tx_power_w,
        effective_antenna_gain_dbi=effective_bs["antenna_gain_dbi"],
        effective_pattern_source=effective_bs.get("pattern_source"),
        radio_details=radio_details,
        antenna_details=antenna_details,
        catalog_overrides_applied=effective_bs["catalog_overrides_applied"],
        placement_plan=placement_plan,
        link_budget_dl=dl_result,
        link_budget_ul=ul_result,
        propagation=prop,
        site_estimate=site,
        sinr=sinr_result,
        qos_verification=qos_results,
        capacity=capacity,
        recommendations=[],  # Will be filled below
    )

    # Generate recommendations
    recs = generate_recommendations(result)

    result.recommendations = recs

    # Generate warnings
    from .models.output_schema import ScenarioWarning
    warnings_result = generate_warnings(inp, result)
    result.warnings = [
        ScenarioWarning(
            code=w.code,
            severity=w.severity,
            category=w.category,
            message=w.message,
            detail=w.detail,
            recommendation=w.recommendation,
        )
        for w in warnings_result.warnings
    ]

    return result

@app.command()
def size(
    config: Path = typer.Option(None, "--config", "-c", help="Path to JSON config file"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file path"),
    area: Optional[float] = typer.Option(None, "--area", help="Coverage area in km2"),
    scenario: Optional[str] = typer.Option(None, "--scenario", help="UMa/UMi/RMa/InH"),
    band: Optional[str] = typer.Option(None, "--band", help="NR band (n78, n41, etc.)"),
    power: Optional[float] = typer.Option(None, "--power", help="BS TX power in watts"),
    config_name: Optional[str] = typer.Option("untitled", "--name", help="Project name"),
):
    """Calculate 5G NR RF coverage sizing."""
    if config:
        with open(config) as f:
            data = json.load(f)
        inp = RFSizingInput(**data)
    else:
        inp = RFSizingInput()
        if area:
            inp.project.area_km2 = area
        if scenario:
            inp.environment.scenario = scenario
        if band:
            inp.frequency.band = band
        if power:
            inp.base_station.tx_power_w = power

    result = _run_sizing(inp)

    # Display results
    console.print(Panel(f"[bold blue]5G NR RF Sizing -- {result.project_name}[/bold blue]", expand=False))

    # Executive Summary
    summary = generate_executive_summary(result)
    console.print(Panel(
        f"[bold]Limiting Factor:[/bold] {summary.limiting_factor.upper()}\n"
        f"[bold]Estimated Sites:[/bold] {summary.estimated_sites}\n"
        f"[bold]Main Bottleneck:[/bold] {summary.main_bottleneck}\n"
        f"[bold]Cell Radius:[/bold] {summary.cell_radius_m:.0f} m" +
        (f"\n[bold]Coverage Ratio:[/bold] {summary.coverage_ratio:.1%}" if summary.coverage_ratio else "") +
        (f"\n[bold]Capacity:[/bold] {summary.capacity_status}" if summary.capacity_status else "") +
        (f"\n[bold yellow]Next Action:[/bold yellow] {summary.recommended_action}" if summary.recommended_action else ""),
        title="📊 Executive Summary",
        expand=False,
    ))

    # Link budget table
    lb_table = Table(title="Link Budget", show_header=True, header_style="bold")
    lb_table.add_column("Parameter", style="cyan")
    lb_table.add_column("DL", justify="right")
    lb_table.add_column("UL", justify="right")

    lb_table.add_row("EIRP (dBm)", f"{result.link_budget_dl.eirp_dbm:.1f}", f"{result.link_budget_ul.eirp_dbm:.1f}")
    lb_table.add_row("Rx Sensitivity (dBm)", f"{result.link_budget_dl.rx_sensitivity_dbm:.1f}", f"{result.link_budget_ul.rx_sensitivity_dbm:.1f}")
    lb_table.add_row("[bold]MAPL (dB)[/bold]", f"[bold]{result.link_budget_dl.mapl_db:.1f}[/bold]", f"[bold]{result.link_budget_ul.mapl_db:.1f}[/bold]")
    lb_table.add_row("Shadow Fading (dB)", f"{result.link_budget_dl.shadow_fading_margin_db:.1f}", f"{result.link_budget_ul.shadow_fading_margin_db:.1f}")
    lb_table.add_row("Penetration Loss (dB)", f"{result.link_budget_dl.penetration_loss_db:.1f}", f"{result.link_budget_ul.penetration_loss_db:.1f}")

    console.print(lb_table)

    # Coverage table
    cov_table = Table(title="Coverage Estimate", show_header=True, header_style="bold")
    cov_table.add_column("Parameter", style="cyan")
    cov_table.add_column("Value", justify="right")

    cov_table.add_row("Propagation Model", result.propagation.model)
    cov_table.add_row("Path Loss (dB)", f"{result.propagation.path_loss_db:.1f}")
    cov_table.add_row("[bold]Cell Radius (km)[/bold]", f"[bold]{result.propagation.cell_radius_km:.3f}[/bold]")
    cov_table.add_row("Cell Radius (m)", f"{result.propagation.cell_radius_m:.0f}")
    cov_table.add_row("LOS Probability", f"{result.propagation.los_probability:.2%}" if result.propagation.los_probability else "N/A")
    cov_table.add_row("Limiting Link", result.site_estimate.limiting_link)
    cov_table.add_row("ISD (km)", f"{result.site_estimate.isd_km:.3f}")
    cov_table.add_row("[bold]Coverage Sites[/bold]", f"[bold]{result.site_estimate.coverage_sites}[/bold]")

    console.print(cov_table)

    # SINR
    console.print(f"\n[bold]Cell Edge SINR:[/bold] {result.sinr.sinr_db:.1f} dB -> CQI {result.sinr.cqi} ({result.sinr.modulation}, SE={result.sinr.spectral_efficiency_bps_hz:.2f} bps/Hz)")

    # Capacity
    if result.capacity:
        cap_table = Table(title="Capacity", show_header=True, header_style="bold")
        cap_table.add_column("Parameter", style="cyan")
        cap_table.add_column("Value", justify="right")

        cap_table.add_row("Cell DL Throughput", f"{result.capacity.cell_throughput_dl_mbps:.1f} Mbps")
        cap_table.add_row("Cell UL Throughput", f"{result.capacity.cell_throughput_ul_mbps:.1f} Mbps")
        cap_table.add_row("Total DL Capacity", f"{result.capacity.total_capacity_dl_gbps:.2f} Gbps")
        cap_table.add_row("Total DL Demand", f"{result.capacity.total_demand_dl_gbps:.2f} Gbps")
        cap_table.add_row("Capacity Sufficient", "[green]YES[/green]" if result.capacity.capacity_sufficient else "[red]NO[/red]")
        cap_table.add_row("[bold]Total Sites (coverage+capacity)[/bold]", f"[bold]{result.capacity.total_sites}[/bold]")
        if result.capacity.additional_sites_needed > 0:
            cap_table.add_row("Additional Sites Needed", f"[red]{result.capacity.additional_sites_needed}[/red]")

        console.print(cap_table)

    # Equipment Provenance
    provenance_lines = []
    if result.catalog_overrides_applied:
        provenance_lines.append("[bold]Equipment Source:[/bold] Catalog (overrides applied)")
    else:
        provenance_lines.append("[bold]Equipment Source:[/bold] Built-in defaults")

    if result.effective_antenna_gain_dbi is not None:
        provenance_lines.append(f"[bold]Effective Antenna Gain:[/bold] {result.effective_antenna_gain_dbi:.1f} dBi")

    if result.effective_pattern_source:
        provenance_lines.append(f"[bold]Pattern Source:[/bold] {result.effective_pattern_source}")

    if result.radio_details:
        radio_info = []
        if result.radio_details.vendor:
            radio_info.append(result.radio_details.vendor)
        if result.radio_details.model:
            radio_info.append(result.radio_details.model)
        if result.radio_details.source_pdf:
            radio_info.append(f"({result.radio_details.source_pdf})")
        if radio_info:
            provenance_lines.append(f"[bold]Radio:[/bold] {' '.join(radio_info)}")

    if result.antenna_details:
        ant_info = []
        if result.antenna_details.vendor:
            ant_info.append(result.antenna_details.vendor)
        if result.antenna_details.model:
            ant_info.append(result.antenna_details.model)
        if result.antenna_details.source_pdf:
            ant_info.append(f"({result.antenna_details.source_pdf})")
        if result.antenna_details.pattern_asset:
            ant_info.append(f"[{result.antenna_details.pattern_asset}]")
        if ant_info:
            provenance_lines.append(f"[bold]Antenna:[/bold] {' '.join(ant_info)}")

    # Check for input vs effective differences
    if result.input_tx_power_w != result.tx_power_w:
        provenance_lines.append(f"[bold]TX Power:[/bold] {result.input_tx_power_w}W → {result.tx_power_w}W (catalog override)")
    else:
        provenance_lines.append(f"[bold]TX Power:[/bold] {result.tx_power_w}W")

    if result.input_antenna_config != result.antenna_config:
        provenance_lines.append(f"[bold]Antenna Config:[/bold] {result.input_antenna_config} → {result.antenna_config} (catalog override)")

    if provenance_lines:
        console.print(Panel(
            "\n".join(provenance_lines),
            title="🔧 Equipment Provenance",
            expand=False,
        ))

    # QoS
    if result.qos_verification:
        qos_table = Table(title="QoS Verification", show_header=True, header_style="bold")
        qos_table.add_column("Service", style="cyan")
        qos_table.add_column("SINR Req", justify="right")
        qos_table.add_column("SINR Avail", justify="right")
        qos_table.add_column("Area %", justify="right")
        qos_table.add_column("Pass", justify="center")

        for q in result.qos_verification:
            status = "[green]PASS[/green]" if q.passed else "[red]FAIL[/red]"
            qos_table.add_row(q.service, f"{q.sinr_required_db:.0f} dB", f"{q.sinr_available_db:.1f} dB", f"{q.area_percentage:.0f}%", status)

        console.print(qos_table)

    # Recommendations
    if result.recommendations:
        console.print("\n[bold yellow]Recommendations:[/bold yellow]")
        for i, rec in enumerate(result.recommendations, 1):
            console.print(f"  {i}. {rec}")

    # Warnings
    warnings_result = generate_warnings(inp, result)
    if warnings_result.has_warnings:
        console.print("\n[bold magenta]⚠️  Scenario Warnings:[/bold magenta]")
        for w in warnings_result.warnings:
            severity_style = {
                "critical": "red",
                "warning": "yellow",
                "info": "dim",
            }.get(w.severity, "white")
            console.print(f"  [{severity_style}][{w.code}] {w.message}[/{severity_style}]")

    # Planning scorecard (if planning result exists)
    if result.placement_plan:
        try:
            scorecard = generate_planning_scorecard(result)
            console.print(Panel(
                f"[bold]Coverage Quality:[/bold] {scorecard.coverage_quality.upper()}\n"
                f"[bold]Service Area:[/bold] {scorecard.service_area_km2:.2f} km²\n"
                f"[bold]Coverage Ratio:[/bold] {scorecard.coverage_ratio:.1%}\n"
                f"[bold]Sites:[/bold] {scorecard.total_sites} (locked: {scorecard.locked_sites}, auto: {scorecard.auto_selected_sites})" +
                (f"\n[bold]DL Unserved:[/bold] {scorecard.unserved_dl_gbps:.2f} Gbps" if scorecard.unserved_dl_gbps else "") +
                (f"\n[bold]Overloaded:[/bold] {scorecard.overloaded_sites}" if scorecard.overloaded_sites else ""),
                title="📊 Planning Scorecard",
                expand=False,
            ))
        except Exception:
            pass  # Skip scorecard if planning result is incomplete

    # Save output
    if output:
        with open(output, "w") as f:
            f.write(result.model_dump_json(indent=2))
        console.print(f"\n[green]Results saved to {output}[/green]")

    return result

@app.command()
def plan(
    config: Path = typer.Option(..., "--config", "-c", help="Path to JSON planning config file"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file path"),
):
    """Run geometry-aware placement planning from a JSON config."""
    with open(config) as f:
        data = json.load(f)
    inp = RFSizingInput(**data)
    result = _run_sizing(inp)
    if result.placement_plan is None:
        raise typer.BadParameter("Config does not include placement.service_area for planning")

    metrics = result.placement_plan.metrics
    table = Table(title="Placement Plan", show_header=True, header_style="bold")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    table.add_row("Mode", result.placement_plan.mode)
    table.add_row("Service Area", f"{metrics.service_area_km2:.2f} km²")
    table.add_row("Covered Area", f"{metrics.covered_area_km2:.2f} km²")
    table.add_row("Coverage Ratio", f"{metrics.coverage_ratio:.1%}")
    table.add_row("Selected Sites", str(metrics.selected_sites))
    table.add_row("Locked Sites", str(metrics.locked_sites))
    table.add_row("Alignment Length", f"{metrics.alignment_length_km:.2f} km")
    if result.placement_plan.spatial_capacity:
        sc = result.placement_plan.spatial_capacity
        table.add_row("Demand DL", f"{sc.demand_dl_gbps:.3f} Gbps")
        table.add_row("Unserved DL", f"{sc.unserved_dl_gbps:.3f} Gbps")
        table.add_row("Hotspot Tiles", str(sc.hotspot_tiles))
        table.add_row("Overloaded Sites", str(sc.overloaded_sites))
    console.print(table)

    if output:
        with open(output, "w") as f:
            f.write(result.model_dump_json(indent=2))
        console.print(f"[green]Planning results saved to {output}[/green]")

    return result

@app.command()
def tables(
    band: Optional[str] = typer.Option(None, "--band", help="Show info for specific band"),
    config_name: Optional[str] = typer.Option(None, "--config", help="Show antenna config"),
):
    """Display lookup tables (bands, antenna configs, etc.)."""
    band_lookup = BandLookup()
    ant_lookup = AntennaConfigLookup()

    if band:
        info = band_lookup.get_band(band)
        console.print(Panel(f"[bold]Band {band}[/bold]", expand=False))
        for k, v in info.items():
            if not k.startswith("_"):
                console.print(f"  {k}: {v}")
    else:
        console.print("[bold]Available bands:[/bold]")
        for b in band_lookup.list_bands():
            info = band_lookup.get_band(b)
            console.print(f"  {b}: {info.get('name', 'N/A')} -- fc={info.get('fc_mhz', '?')} MHz")

    console.print(f"\n[bold]Antenna configs:[/bold] {ant_lookup.list_configs()}")

@app.command()
def map(
    config: Path = typer.Option(None, "--config", "-c", help="Path to JSON config file"),
    output: Optional[str] = typer.Option("coverage_map.html", "--output", "-o", help="Output HTML file"),
    lat: float = typer.Option(10.8231, "--lat", help="Map center latitude"),
    lon: float = typer.Option(106.6297, "--lon", help="Map center longitude"),
    zoom: int = typer.Option(12, "--zoom", help="Zoom level"),
    sites_file: Optional[Path] = typer.Option(None, "--sites", "-s", help="Import custom sites (JSON or CSV, WGS84)"),
    area: Optional[float] = typer.Option(None, "--area", help="Coverage area km2"),
    scenario: Optional[str] = typer.Option(None, "--scenario", help="UMa/UMi/RMa/InH"),
    band: Optional[str] = typer.Option(None, "--band", help="NR band"),
    power: Optional[float] = typer.Option(None, "--power", help="BS TX power W"),
):
    """Generate interactive Folium coverage map with drag-and-drop sites.

    Features:
    - Drag markers to reposition sites
    - Popup shows site details (lat/lon, SINR, PL)
    - Delete site via popup button
    - Export sites as JSON/CSV from browser
    - Import custom sites via --sites (JSON or CSV, WGS84)

    Coordinate system: WGS84 (EPSG:4326)
    """
    if config:
        with open(config) as f:
            data = json.load(f)
        inp = RFSizingInput(**data)
        if lat == 10.8231 and inp.project.center_lat:
            lat = inp.project.center_lat
        if lon == 106.6297 and inp.project.center_lon:
            lon = inp.project.center_lon
    else:
        inp = RFSizingInput()
        if area: inp.project.area_km2 = area
        if scenario: inp.environment.scenario = scenario
        if band: inp.frequency.band = band
        if power: inp.base_station.tx_power_w = power

    result = _run_sizing(inp)

    # Import custom sites if provided
    custom_sites = None
    if sites_file:
        path_str = str(sites_file)
        if path_str.endswith(".json"):
            custom_sites = import_sites_json(path_str)
        elif path_str.endswith(".csv"):
            custom_sites = import_sites_csv(path_str)
        console.print(f"[green]Loaded {len(custom_sites)} custom sites from {sites_file}[/green]")

    path = generate_interactive_map(
        result, center_lat=lat, center_lon=lon, zoom_start=zoom,
        output_path=output, custom_sites=custom_sites,
    )
    console.print(f"[green]Interactive coverage map saved to {path}[/green]")
    console.print(f"  [cyan]Features: Drag-and-drop sites, export JSON/CSV from browser[/cyan]")
    console.print(f"  [cyan]Coordinate system: WGS84 (EPSG:4326)[/cyan]")

@app.command()
def report(
    config: Path = typer.Option(None, "--config", "-c", help="Path to JSON config file"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output path"),
    format: str = typer.Option("html", "--format", "-f", help="Report format: html, md, executive, technical"),
    area: Optional[float] = typer.Option(None, "--area", help="Coverage area km2"),
    scenario: Optional[str] = typer.Option(None, "--scenario", help="UMa/UMi/RMa/InH"),
    band: Optional[str] = typer.Option(None, "--band", help="NR band"),
    power: Optional[float] = typer.Option(None, "--power", help="BS TX power W"),
):
    """Generate sizing report.

    Formats:
    - html: Full HTML report (default)
    - md: Full Markdown report
    - executive: Executive summary for non-technical stakeholders
    - technical: Technical appendix with full engineering details
    """
    if config:
        with open(config) as f:
            data = json.load(f)
        inp = RFSizingInput(**data)
    else:
        inp = RFSizingInput()
        if area: inp.project.area_km2 = area
        if scenario: inp.environment.scenario = scenario
        if band: inp.frequency.band = band
        if power: inp.base_station.tx_power_w = power

    result = _run_sizing(inp)
    name = result.project_name.replace(" ", "_")

    if format == "md":
        path = generate_markdown_report(result, output or f"rf5g_report_{name}.md")
    elif format == "executive":
        from .viz.report import generate_executive_report
        path = generate_executive_report(result, output or f"rf5g_executive_{name}.md")
    elif format == "technical":
        from .viz.report import generate_technical_appendix
        path = generate_technical_appendix(result, output or f"rf5g_technical_{name}.md")
    else:
        path = generate_html_report(result, output or f"rf5g_report_{name}.html")
    console.print(f"[green]Report saved to {path}[/green]")

@app.command()
def charts(
    config: Path = typer.Option(None, "--config", "-c", help="Path to JSON config file"),
    output_dir: Optional[str] = typer.Option(".", "--output-dir", "-o", help="Output directory"),
    area: Optional[float] = typer.Option(None, "--area", help="Coverage area km2"),
    scenario: Optional[str] = typer.Option(None, "--scenario", help="UMa/UMi/RMa/InH"),
    band: Optional[str] = typer.Option(None, "--band", help="NR band"),
    power: Optional[float] = typer.Option(None, "--power", help="BS TX power W"),
):
    """Generate charts (link budget, SINR heatmap, service zones, capacity)."""
    if config:
        with open(config) as f:
            data = json.load(f)
        inp = RFSizingInput(**data)
    else:
        inp = RFSizingInput()
        if area: inp.project.area_km2 = area
        if scenario: inp.environment.scenario = scenario
        if band: inp.frequency.band = band
        if power: inp.base_station.tx_power_w = power

    result = _run_sizing(inp)
    name = result.project_name.replace(" ", "_")
    out = output_dir

    lb_path = plot_link_budget(result, f"{out}/link_budget_{name}.png")
    console.print(f"  [green]Link budget chart: {lb_path}[/green]")

    sinr_path = plot_sinr_heatmap(result, f"{out}/sinr_heatmap_{name}.png")
    console.print(f"  [green]SINR heatmap: {sinr_path}[/green]")

    svc_path = plot_service_zones(result, f"{out}/service_zones_{name}.png")
    console.print(f"  [green]Service zones: {svc_path}[/green]")

    cap_path = plot_capacity_comparison(result, f"{out}/capacity_{name}.png")
    if cap_path:
        console.print(f"  [green]Capacity chart: {cap_path}[/green]")

@app.command()
def sites(
    action: str = typer.Argument(..., help="Action: export-json, export-csv, import, count"),
    config: Path = typer.Option(None, "--config", "-c", help="Path to JSON config file"),
    sites_file: Optional[Path] = typer.Option(None, "--sites-file", "-s", help="Sites file (JSON or CSV)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    area: Optional[float] = typer.Option(None, "--area", help="Coverage area km2"),
    scenario: Optional[str] = typer.Option(None, "--scenario", help="UMa/UMi/RMa/InH"),
    band: Optional[str] = typer.Option(None, "--band", help="NR band"),
    power: Optional[float] = typer.Option(None, "--power", help="BS TX power W"),
):
    """Export/import custom site positions (WGS84 coordinates)."""
    if config:
        with open(config) as f:
            data = json.load(f)
        inp = RFSizingInput(**data)
    else:
        inp = RFSizingInput()
        if area: inp.project.area_km2 = area
        if scenario: inp.environment.scenario = scenario
        if band: inp.frequency.band = band
        if power: inp.base_station.tx_power_w = power

    result = _run_sizing(inp)
    name = result.project_name.replace(" ", "_")

    if action == "count":
        console.print(f"[bold]Estimated sites:[/bold] {result.site_estimate.coverage_sites}")
        console.print(f"[bold]Cell radius:[/bold] {result.propagation.cell_radius_m:.0f}m")
        console.print(f"[bold]ISD:[/bold] {result.site_estimate.isd_km * 1000:.0f}m")

    elif action == "export-json":
        from .viz.coverage_map import generate_hex_grid
        sites = generate_hex_grid(
            inp.project.center_lat, inp.project.center_lon,
            result.site_estimate.isd_km, result.site_estimate.coverage_sites
        )
        out_path = output or f"rf5g_sites_{name}.json"
        metadata = {
            "project": result.project_name,
            "band": result.band,
            "cell_radius_m": result.propagation.cell_radius_m,
            "isd_km": result.site_estimate.isd_km,
            "total_sites": len(sites),
        }
        export_sites_json(sites, out_path, metadata)
        console.print(f"[green]Exported {len(sites)} sites to {out_path} (WGS84)[/green]")

    elif action == "export-csv":
        from .viz.coverage_map import generate_hex_grid
        sites = generate_hex_grid(
            inp.project.center_lat, inp.project.center_lon,
            result.site_estimate.isd_km, result.site_estimate.coverage_sites
        )
        out_path = output or f"rf5g_sites_{name}.csv"
        export_sites_csv(sites, out_path)
        console.print(f"[green]Exported {len(sites)} sites to {out_path} (WGS84)[/green]")

    elif action == "import":
        if not sites_file:
            console.print("[red]Error: --sites-file required for import[/red]")
            raise typer.Exit(1)
        path_str = str(sites_file)
        if path_str.endswith(".json"):
            custom_sites = import_sites_json(path_str)
        elif path_str.endswith(".csv"):
            custom_sites = import_sites_csv(path_str)
        else:
            console.print("[red]Error: sites file must be .json or .csv[/red]")
            raise typer.Exit(1)
        console.print(f"[green]Imported {len(custom_sites)} sites from {sites_file}[/green]")
        for i, (lat, lon) in enumerate(custom_sites[:10]):
            console.print(f"  Site #{i + 1}: {lat:.6f}, {lon:.6f}")
        if len(custom_sites) > 10:
            console.print(f"  ... and {len(custom_sites) - 10} more")
    else:
        console.print(f"[red]Unknown action: {action}. Use: export-json, export-csv, import, count[/red]")


if __name__ == "__main__":
    app()