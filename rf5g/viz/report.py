"""Jinja2 Report Generator — Markdown/HTML report from sizing results."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from jinja2 import Template

from ..engine.summary import generate_executive_summary

REPORT_TEMPLATE = """# 5G NR RF Coverage Sizing Report

**Project:** {{ result.project_name }}
**Date:** {{ timestamp }}
**Scenario:** {{ result.environment }} | **Band:** {{ result.band }} {{ result.bandwidth_mhz | int }}MHz
**Effective TX:** {{ result.tx_power_w }}W {{ result.antenna_config }}
{% if result.input_tx_power_w != result.tx_power_w or result.input_antenna_config != result.antenna_config %}**Requested TX:** {{ result.input_tx_power_w }}W {{ result.input_antenna_config }}
{% endif %}{% if result.effective_antenna_gain_dbi is not none %}**Effective Antenna Gain:** {{ "%.1f" | format(result.effective_antenna_gain_dbi) }} dBi
{% endif %}{% if result.radio_details %}**Radio Source:** {{ result.radio_details.vendor or 'unknown' }} {{ result.radio_details.model or '' }}{% if result.radio_details.source_pdf %} — {{ result.radio_details.source_pdf }}{% endif %}
{% endif %}{% if result.antenna_details %}**Antenna Source:** {{ result.antenna_details.vendor or 'custom' }} {{ result.antenna_details.model or '' }}{% if result.antenna_details.source_pdf %} — {{ result.antenna_details.source_pdf }}{% endif %}
{% if result.antenna_details.pattern_asset %}**Pattern Asset:** {{ result.antenna_details.pattern_asset }}
{% endif %}{% endif %}{% if result.effective_pattern_source %}**Pattern Source:** {{ result.effective_pattern_source }}
{% endif %}
---

## Executive Summary

| Metric | Value |
|---|---|
| **Limiting Factor** | {{ summary.limiting_factor }} |
| **Estimated Sites** | {{ summary.estimated_sites }} |
| **Main Bottleneck** | {{ summary.main_bottleneck }} |
| **Cell Radius** | {{ "%.0f" | format(summary.cell_radius_m) }} m |
{% if summary.coverage_ratio %}| **Coverage Ratio** | {{ "%.1f" | format(summary.coverage_ratio * 100) }}% |
{% endif %}{% if summary.capacity_status %}| **Capacity** | {{ summary.capacity_status }} |
{% endif %}{% if summary.warnings_count > 0 %}| **Warnings** | {{ summary.warnings_count }} |
{% endif %}
**Next Action:** {{ summary.recommended_action }}

---

## 0. Equipment Provenance

| Parameter | Value |
|---|---|
| **Equipment Source** | {{ "Catalog (overrides applied)" if result.catalog_overrides_applied else "Built-in defaults" }} |
| **TX Power** | {{ result.tx_power_w }}W{% if result.input_tx_power_w != result.tx_power_w %} (input: {{ result.input_tx_power_w }}W → catalog: {{ result.tx_power_w }}W){% endif %} |
| **Antenna Config** | {{ result.antenna_config }}{% if result.input_antenna_config != result.antenna_config %} (input: {{ result.input_antenna_config }} → catalog: {{ result.antenna_config }}){% endif %} |
{% if result.effective_antenna_gain_dbi %}| **Effective Antenna Gain** | {{ "%.1f" | format(result.effective_antenna_gain_dbi) }} dBi |{% endif %}
{% if result.effective_pattern_source %}| **Pattern Source** | {{ result.effective_pattern_source }} |{% endif %}
{% if result.radio_details %}| **Radio** | {{ result.radio_details.vendor or "" }} {{ result.radio_details.model or "" }}{% if result.radio_details.source_pdf %} ({{ result.radio_details.source_pdf }}){% endif %} |{% endif %}
{% if result.antenna_details %}| **Antenna** | {{ result.antenna_details.vendor or "" }} {{ result.antenna_details.model or "" }}{% if result.antenna_details.source_pdf %} ({{ result.antenna_details.source_pdf }}){% endif %} |{% endif %}

---

## 1. Link Budget

| Parameter | DL | UL |
|---|---|---|
| EIRP (dBm) | {{ "%.1f" | format(result.link_budget_dl.eirp_dbm) }} | {{ "%.1f" | format(result.link_budget_ul.eirp_dbm) }} |
| Rx Sensitivity (dBm) | {{ "%.1f" | format(result.link_budget_dl.rx_sensitivity_dbm) }} | {{ "%.1f" | format(result.link_budget_ul.rx_sensitivity_dbm) }} |
| **MAPL (dB)** | **{{ "%.1f" | format(result.link_budget_dl.mapl_db) }}** | **{{ "%.1f" | format(result.link_budget_ul.mapl_db) }}** |
| Shadow Fading (dB) | {{ "%.1f" | format(result.link_budget_dl.shadow_fading_margin_db) }} | {{ "%.1f" | format(result.link_budget_ul.shadow_fading_margin_db) }} |
| Penetration Loss (dB) | {{ "%.1f" | format(result.link_budget_dl.penetration_loss_db) }} | {{ "%.1f" | format(result.link_budget_ul.penetration_loss_db) }} |
| Interference (dB) | {{ "%.1f" | format(result.link_budget_dl.interference_margin_db) }} | {{ "%.1f" | format(result.link_budget_ul.interference_margin_db) }} |

**Limiting Link:** {{ result.site_estimate.limiting_link }}

---

## 2. Coverage Estimate

| Parameter | Value |
|---|---|
| Propagation Model | {{ result.propagation.model }} |
| Path Loss | {{ "%.1f" | format(result.propagation.path_loss_db) }} dB |
| **Cell Radius** | **{{ "%.0f" | format(result.propagation.cell_radius_m) }} m** ({{ "%.3f" | format(result.propagation.cell_radius_km) }} km) |
| LOS Probability | {{ "%.1f" | format(result.propagation.los_probability * 100) }}% |
| ISD | {{ "%.0f" | format(result.site_estimate.isd_km * 1000) }} m |
| **Coverage Sites** | **{{ result.site_estimate.coverage_sites }}** |

---

## 3. SINR & Modulation

| Parameter | Value |
|---|---|
| Cell Edge SINR | {{ "%.1f" | format(result.sinr.sinr_db) }} dB |
| CQI | {{ result.sinr.cqi }} |
| Modulation | {{ result.sinr.modulation }} |
| Spectral Efficiency | {{ "%.4f" | format(result.sinr.spectral_efficiency_bps_hz) }} bps/Hz |
| Code Rate | {{ "%.4f" | format(result.sinr.code_rate) }} |

---

## 4. Capacity

| Parameter | Value |
|---|---|
| Cell DL Throughput | {{ "%.1f" | format(result.capacity.cell_throughput_dl_mbps) }} Mbps |
| Cell UL Throughput | {{ "%.1f" | format(result.capacity.cell_throughput_ul_mbps) }} Mbps |
| Total DL Capacity | {{ "%.2f" | format(result.capacity.total_capacity_dl_gbps) }} Gbps |
| Total DL Demand | {{ "%.2f" | format(result.capacity.total_demand_dl_gbps) }} Gbps |
| **Capacity Sufficient** | **{{ "YES" if result.capacity.capacity_sufficient else "NO" }}** |
| Total Sites (cov+cap) | {{ result.capacity.total_sites }} |
{% if result.capacity.additional_sites_needed > 0 %}| Additional Sites Needed | {{ result.capacity.additional_sites_needed }} |{% endif %}

---

## 5. QoS Verification

| Service | SINR Req | SINR Avail | Area % | Pass |
|---|---|---|---|---|
{% for q in result.qos_verification %}| {{ q.service }} | {{ q.sinr_required_db }} dB | {{ "%.1f" | format(q.sinr_available_db) }} dB | {{ "%.0f" | format(q.area_percentage) }}% | {{ "PASS" if q.passed else "FAIL" }} |
{% endfor %}
---

## 6. Recommendations

{% for i, rec in enumerate(result.recommendations, 1) %}{{ i }}. {{ rec }}
{% endfor %}

---

## 7. Assumptions & Limitations

### Propagation Model
- Based on **3GPP TR 38.901** statistical models (UMa, UMi, RMa, InH)
- LOS/NLOS probability is scenario-dependent; "combined" mode uses weighted average
- Does not account for specific terrain, clutter, or building data

### Link Budget
- **Penetration loss**: O2I model per 3GPP TR 38.901 (building type dependent)
- **Shadow fading**: Log-normal with scenario-dependent standard deviation
- **Interference margin**: User-specified; assumes uniform interference

### SINR & Throughput
- Cell-edge SINR assumes interference at user-specified margin
- CQI-to-SINR mapping based on 3GPP TS 38.214 Table 5.2.2.1-4
- **TDD throughput**: Approximated from peak using TDD ratio and overhead
- **FDD throughput**: Approximated (full duplex assumed, no HARQ/modeling)

### Capacity
- Per-cell throughput estimated from spectral efficiency at cell edge
- Demand is user-specified; no traffic modeling or time variation
- Assumes uniform user distribution

### Site Estimation
- Hexagonal cell layout with user-specified overlap factor
- Coverage-limited sizing (capacity check is secondary)
- No automatic cell splitting for capacity relief

### Equipment Defaults
- Antenna gain: Based on MIMO config (e.g., 32T32R = 20 dBi + 12 dB BF)
- TX power: User-specified or catalog default
- **Pattern source**: Default cosine pattern if no catalog/import provided

### Planning Limitations
- Geometry-aware planning uses simplified coverage model
- No 3D ray-tracing or building-aware propagation
- FR2/mmWave not supported in current version

---

*Report generated by rf5g — 5G NR RF Coverage Sizing Tool (3GPP TR 38.901)*
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>5G NR RF Coverage Report — {{ result.project_name }}</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
h1 { color: #1976D2; border-bottom: 3px solid #1976D2; padding-bottom: 10px; }
h2 { color: #333; margin-top: 30px; }
table { border-collapse: collapse; width: 100%; margin: 10px 0; }
th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
th { background: #1976D2; color: white; }
tr:nth-child(even) { background: #f9f9f9; }
.pass { color: #4CAF50; font-weight: bold; }
.fail { color: #F44336; font-weight: bold; }
.metric { font-size: 24px; font-weight: bold; color: #1976D2; }
.card { background: white; border-radius: 8px; padding: 20px; margin: 10px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.rec { padding: 8px 12px; margin: 5px 0; border-left: 3px solid #FF9800; background: #FFF8E1; }
.highlight { background: #E3F2FD; padding: 2px 6px; border-radius: 3px; }
h3 { color: #555; margin-top: 15px; margin-bottom: 5px; font-size: 14px; }
ul { margin: 5px 0 15px 20px; padding: 0; }
li { margin: 3px 0; color: #666; font-size: 13px; }
</style>
</head>
<body>
<h1>5G NR RF Coverage Report</h1>

<div class="card">
<p><strong>Project:</strong> {{ result.project_name }} |
<strong>Scenario:</strong> {{ result.environment }} |
<strong>Band:</strong> {{ result.band }} {{ result.bandwidth_mhz | int }}MHz |
<strong>Effective TX:</strong> {{ result.tx_power_w }}W {{ result.antenna_config }}
{% if result.input_tx_power_w != result.tx_power_w or result.input_antenna_config != result.antenna_config %}<br><strong>Requested TX:</strong> {{ result.input_tx_power_w }}W {{ result.input_antenna_config }}
{% endif %}{% if result.effective_antenna_gain_dbi is not none %}<br><strong>Effective Antenna Gain:</strong> {{ "%.1f" | format(result.effective_antenna_gain_dbi) }} dBi
{% endif %}{% if result.radio_details %}<br><strong>Radio Source:</strong> {{ result.radio_details.vendor or 'unknown' }} {{ result.radio_details.model or '' }}{% if result.radio_details.source_pdf %} — {{ result.radio_details.source_pdf }}{% endif %}
{% endif %}{% if result.antenna_details %}<br><strong>Antenna Source:</strong> {{ result.antenna_details.vendor or 'custom' }} {{ result.antenna_details.model or '' }}{% if result.antenna_details.source_pdf %} — {{ result.antenna_details.source_pdf }}{% endif %}
{% if result.antenna_details.pattern_asset %}<br><strong>Pattern Asset:</strong> {{ result.antenna_details.pattern_asset }}{% endif %}
{% endif %}{% if result.effective_pattern_source %}<br><strong>Pattern Source:</strong> {{ result.effective_pattern_source }}
{% endif %}</p>
</div>

<div class="card" style="background: #E3F2FD; border-left: 4px solid #1976D2;">
<h2 style="margin-top: 0; color: #1976D2;">📊 Executive Summary</h2>
<table style="background: white;">
<tr><td><strong>Limiting Factor</strong></td><td>{{ summary.limiting_factor }}</td></tr>
<tr><td><strong>Estimated Sites</strong></td><td class="metric">{{ summary.estimated_sites }}</td></tr>
<tr><td><strong>Main Bottleneck</strong></td><td>{{ summary.main_bottleneck }}</td></tr>
<tr><td><strong>Cell Radius</strong></td><td>{{ "%.0f" | format(summary.cell_radius_m) }} m</td></tr>
{% if summary.coverage_ratio %}<tr><td><strong>Coverage Ratio</strong></td><td>{{ "%.1f" | format(summary.coverage_ratio * 100) }}%</td></tr>
{% endif %}{% if summary.capacity_status %}<tr><td><strong>Capacity</strong></td><td>{{ summary.capacity_status }}</td></tr>
{% endif %}{% if summary.warnings_count > 0 %}<tr><td><strong>Warnings</strong></td><td>{{ summary.warnings_count }}</td></tr>
{% endif %}
</table>
<p style="margin-top: 10px; margin-bottom: 0;"><strong>Next Action:</strong> {{ summary.recommended_action }}</p>
</div>

<h2>0. Equipment Provenance</h2>
<div class="card">
<table>
<tr><td><strong>Equipment Source</strong></td><td>{{ "Catalog (overrides applied)" if result.catalog_overrides_applied else "Built-in defaults" }}</td></tr>
<tr><td><strong>TX Power</strong></td><td>{{ result.tx_power_w }}W{% if result.input_tx_power_w != result.tx_power_w %} <em>(input: {{ result.input_tx_power_w }}W → catalog: {{ result.tx_power_w }}W)</em>{% endif %}</td></tr>
<tr><td><strong>Antenna Config</strong></td><td>{{ result.antenna_config }}{% if result.input_antenna_config != result.antenna_config %} <em>(input: {{ result.input_antenna_config }} → catalog: {{ result.antenna_config }})</em>{% endif %}</td></tr>
{% if result.effective_antenna_gain_dbi %}<tr><td><strong>Effective Antenna Gain</strong></td><td>{{ "%.1f" | format(result.effective_antenna_gain_dbi) }} dBi</td></tr>{% endif %}
{% if result.effective_pattern_source %}<tr><td><strong>Pattern Source</strong></td><td>{{ result.effective_pattern_source }}</td></tr>{% endif %}
{% if result.radio_details %}<tr><td><strong>Radio</strong></td><td>{{ result.radio_details.vendor or "" }} {{ result.radio_details.model or "" }}{% if result.radio_details.source_pdf %} <em>({{ result.radio_details.source_pdf }})</em>{% endif %}</td></tr>{% endif %}
{% if result.antenna_details %}<tr><td><strong>Antenna</strong></td><td>{{ result.antenna_details.vendor or "" }} {{ result.antenna_details.model or "" }}{% if result.antenna_details.source_pdf %} <em>({{ result.antenna_details.source_pdf }})</em>{% endif %}</td></tr>{% endif %}
</table>
</div>

<h2>1. Link Budget</h2>
<div class="card">
<table>
<tr><th>Parameter</th><th>DL</th><th>UL</th></tr>
<tr><td>EIRP (dBm)</td><td>{{ "%.1f" | format(result.link_budget_dl.eirp_dbm) }}</td><td>{{ "%.1f" | format(result.link_budget_ul.eirp_dbm) }}</td></tr>
<tr><td>Rx Sensitivity (dBm)</td><td>{{ "%.1f" | format(result.link_budget_dl.rx_sensitivity_dbm) }}</td><td>{{ "%.1f" | format(result.link_budget_ul.rx_sensitivity_dbm) }}</td></tr>
<tr><td><strong>MAPL (dB)</strong></td><td class="metric">{{ "%.1f" | format(result.link_budget_dl.mapl_db) }}</td><td class="metric">{{ "%.1f" | format(result.link_budget_ul.mapl_db) }}</td></tr>
<tr><td>Shadow Fading (dB)</td><td>{{ "%.1f" | format(result.link_budget_dl.shadow_fading_margin_db) }}</td><td>{{ "%.1f" | format(result.link_budget_ul.shadow_fading_margin_db) }}</td></tr>
<tr><td>Penetration Loss (dB)</td><td>{{ "%.1f" | format(result.link_budget_dl.penetration_loss_db) }}</td><td>{{ "%.1f" | format(result.link_budget_ul.penetration_loss_db) }}</td></tr>
</table>
<p><strong>Limiting Link:</strong> <span class="highlight">{{ result.site_estimate.limiting_link }}</span></p>
</div>

<h2>2. Coverage</h2>
<div class="card">
<table>
<tr><th>Parameter</th><th>Value</th></tr>
<tr><td>Propagation Model</td><td>{{ result.propagation.model }}</td></tr>
<tr><td>Path Loss</td><td>{{ "%.1f" | format(result.propagation.path_loss_db) }} dB</td></tr>
<tr><td><strong>Cell Radius</strong></td><td class="metric">{{ "%.0f" | format(result.propagation.cell_radius_m) }} m ({{ "%.3f" | format(result.propagation.cell_radius_km) }} km)</td></tr>
<tr><td>LOS Probability</td><td>{{ "%.1f" | format(result.propagation.los_probability * 100) }}%</td></tr>
<tr><td>ISD</td><td>{{ "%.0f" | format(result.site_estimate.isd_km * 1000) }} m</td></tr>
<tr><td><strong>Coverage Sites</strong></td><td class="metric">{{ result.site_estimate.coverage_sites }}</td></tr>
</table>
</div>

<h2>3. SINR & Modulation</h2>
<div class="card">
<table>
<tr><th>Parameter</th><th>Value</th></tr>
<tr><td>Cell Edge SINR</td><td>{{ "%.1f" | format(result.sinr.sinr_db) }} dB</td></tr>
<tr><td>CQI</td><td>{{ result.sinr.cqi }}</td></tr>
<tr><td>Modulation</td><td>{{ result.sinr.modulation }}</td></tr>
<tr><td>Spectral Efficiency</td><td>{{ "%.4f" | format(result.sinr.spectral_efficiency_bps_hz) }} bps/Hz</td></tr>
</table>
</div>

<h2>4. Capacity</h2>
<div class="card">
<table>
<tr><th>Parameter</th><th>Value</th></tr>
<tr><td>Cell DL Throughput</td><td>{{ "%.1f" | format(result.capacity.cell_throughput_dl_mbps) }} Mbps</td></tr>
<tr><td>Cell UL Throughput</td><td>{{ "%.1f" | format(result.capacity.cell_throughput_ul_mbps) }} Mbps</td></tr>
<tr><td>Total DL Capacity</td><td>{{ "%.2f" | format(result.capacity.total_capacity_dl_gbps) }} Gbps</td></tr>
<tr><td>Total DL Demand</td><td>{{ "%.2f" | format(result.capacity.total_demand_dl_gbps) }} Gbps</td></tr>
<tr><td><strong>Capacity Sufficient</strong></td><td class="{{ 'pass' if result.capacity.capacity_sufficient else 'fail' }}">{{ "YES" if result.capacity.capacity_sufficient else "NO" }}</td></tr>
<tr><td>Total Sites (cov+cap)</td><td>{{ result.capacity.total_sites }}</td></tr>
{% if result.capacity.additional_sites_needed > 0 %}<tr><td>Additional Sites Needed</td><td class="fail">{{ result.capacity.additional_sites_needed }}</td></tr>{% endif %}
</table>
</div>

<h2>5. QoS Verification</h2>
<div class="card">
<table>
<tr><th>Service</th><th>SINR Req</th><th>SINR Avail</th><th>Area %</th><th>Status</th></tr>
{% for q in result.qos_verification %}<tr>
<td>{{ q.service }}</td>
<td>{{ q.sinr_required_db }} dB</td>
<td>{{ "%.1f" | format(q.sinr_available_db) }} dB</td>
<td>{{ "%.0f" | format(q.area_percentage) }}%</td>
<td class="{{ 'pass' if q.passed else 'fail' }}">{{ "PASS" if q.passed else "FAIL" }}</td>
</tr>{% endfor %}
</table>
</div>

<h2>6. Recommendations</h2>
<div class="card">
{% for rec in result.recommendations %}<div class="rec">{{ rec }}</div>{% endfor %}
</div>

<h2>7. Assumptions & Limitations</h2>
<div class="card">
<h3>Propagation Model</h3>
<ul>
<li>Based on <strong>3GPP TR 38.901</strong> statistical models (UMa, UMi, RMa, InH)</li>
<li>LOS/NLOS probability is scenario-dependent; "combined" mode uses weighted average</li>
<li>Does not account for specific terrain, clutter, or building data</li>
</ul>

<h3>Link Budget</h3>
<ul>
<li><strong>Penetration loss</strong>: O2I model per 3GPP TR 38.901 (building type dependent)</li>
<li><strong>Shadow fading</strong>: Log-normal with scenario-dependent standard deviation</li>
<li><strong>Interference margin</strong>: User-specified; assumes uniform interference</li>
</ul>

<h3>SINR & Throughput</h3>
<ul>
<li>Cell-edge SINR assumes interference at user-specified margin</li>
<li>CQI-to-SINR mapping based on 3GPP TS 38.214 Table 5.2.2.1-4</li>
<li><strong>TDD throughput</strong>: Approximated from peak using TDD ratio and overhead</li>
<li><strong>FDD throughput</strong>: Approximated (full duplex assumed, no HARQ modeling)</li>
</ul>

<h3>Capacity</h3>
<ul>
<li>Per-cell throughput estimated from spectral efficiency at cell edge</li>
<li>Demand is user-specified; no traffic modeling or time variation</li>
<li>Assumes uniform user distribution</li>
</ul>

<h3>Site Estimation</h3>
<ul>
<li>Hexagonal cell layout with user-specified overlap factor</li>
<li>Coverage-limited sizing (capacity check is secondary)</li>
<li>No automatic cell splitting for capacity relief</li>
</ul>

<h3>Equipment Defaults</h3>
<ul>
<li>Antenna gain: Based on MIMO config (e.g., 32T32R = 20 dBi + 12 dB BF)</li>
<li>TX power: User-specified or catalog default</li>
<li><strong>Pattern source</strong>: Default cosine pattern if no catalog/import provided</li>
</ul>

<h3>Planning Limitations</h3>
<ul>
<li>Geometry-aware planning uses simplified coverage model</li>
<li>No 3D ray-tracing or building-aware propagation</li>
<li>FR2/mmWave not supported in current version</li>
</ul>
</div>

<footer style="margin-top: 30px; padding-top: 10px; border-top: 1px solid #ddd; color: #888; font-size: 12px;">
Generated by <strong>rf5g</strong> — 5G NR RF Coverage Sizing Tool (3GPP TR 38.901) | {{ timestamp }}
</footer>
</body>
</html>
"""


def generate_markdown_report(result: SizingOutput, output_path: str | None = None) -> str:
    """Generate Markdown report from sizing results."""
    summary = generate_executive_summary(result)
    template = Template(REPORT_TEMPLATE)
    content = template.render(
        result=result,
        summary=summary,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        enumerate=enumerate,
    )

    if output_path is None:
        output_path = f"rf5g_report_{result.project_name.replace(' ', '_')}.md"

    Path(output_path).write_text(content, encoding="utf-8")
    return output_path


def generate_html_report(result: SizingOutput, output_path: str | None = None) -> str:
    """Generate HTML report from sizing results."""
    summary = generate_executive_summary(result)
    template = Template(HTML_TEMPLATE)
    content = template.render(
        result=result,
        summary=summary,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    if output_path is None:
        output_path = f"rf5g_report_{result.project_name.replace(' ', '_')}.html"

    Path(output_path).write_text(content, encoding="utf-8")
    return output_path