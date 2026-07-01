# rf5g-sizing — User Guide

## Overview

rf5g-sizing is a 5G NR RF Coverage Sizing Tool based on 3GPP standards. It helps radio planners estimate the number of base stations needed, verify QoS targets, and generate coverage maps.

**Standards referenced:**
- 3GPP TR 38.901 — Propagation models
- 3GPP TS 38.104 — Base station RF requirements
- 3GPP TS 38.214 — Physical layer measurements
- 3GPP TS 38.306 — UE capabilities

## Getting Started

1. Launch rf5g-sizing (Desktop shortcut or Start Menu)
2. Browser opens at `http://localhost:8501`
3. Configure parameters in the sidebar
4. Click **🚀 Calculate**
5. Review results in the main panel

## Interface Guide

### Sidebar — Input Parameters

#### 📍 Project
- **Project Name**: Label for your project
- **Coverage Area (km²)**: Total area to cover
- **Center Latitude/Longitude**: Center point for coverage map

#### 🏙️ Environment
- **Scenario**: 
  - `UMa` — Urban Macro (outdoor, high BS)
  - `UMi` — Urban Micro (outdoor, low BS)
  - `RMa` — Rural Macro
  - `InH` — Indoor Hotspot
- **Obstacle Density**: heavy / medium / light — affects penetration loss
- **Coverage Probability**: Target probability (0.80–0.99)

#### 📡 Base Station
- **Antenna Config**: 32T32R, 64T64R, 8T8R, 4T4R, 2T2R
- **TX Power (W)**: Base station transmit power
- **BS Height (m)**: Antenna height above ground
- **Sectors**: 1 (omni), 3 (standard), or 6 (high capacity)

#### 📻 Frequency
- **NR Band**: n78 (3.5 GHz), n77 (3.3–4.2 GHz), n41 (2.5 GHz), n1/n3/n8/n28/n25/n71
- **Bandwidth (MHz)**: Channel bandwidth (5–100 MHz)
- **SCS (kHz)**: Subcarrier spacing — 15/30/60/120 kHz
- **TDD DL Ratio**: Downlink ratio in TDD config (0.5–0.9)

#### 📱 UE (User Equipment)
- **Power Class**: PC1–PC4 (PC3 = typical smartphone)
- **UE Height (m)**: Usually 1.5m
- **UE Noise Figure (dB)**: Receiver noise figure

#### 📊 Margins
- **Interference Margin (dB)**: Uplink interference margin
- **Penetration Loss (dB)**: Indoor penetration loss
- **Rain Attenuation (dB)**: Rain margin
- **Overlap Factor**: Cell overlap factor (0–0.5)

#### 🎯 QoS
- **Primary Service**: mixed, vonr, video_hd, video_4k, data, gaming, iot
- **Users per km²**: User density
- **DL/UL per User (Mbps)**: Per-user throughput requirement
- **Concurrent Ratio**: Fraction of active users

### Main Panel — Results

After clicking **Calculate**, you'll see:

1. **Link Budget Table** — Detailed DL/UL path budget
2. **Site Count** — Number of sites needed for coverage
3. **SINR Heatmap** — Signal quality distribution
4. **Service Zones** — Coverage by service type
5. **Coverage Map** — Interactive Folium map with hex grid
6. **Capacity Analysis** — Throughput vs demand

### Guided Mode

Switch to **Guided Mode** using the sidebar toggle for step-by-step explanations of each parameter.

### Export Results

- **📊 Export Report** — Download HTML or Markdown report
- **🗺️ Export Map** — Download interactive coverage map (HTML)
- **📋 Export Sites** — Download site list (CSV/JSON)

## Configuration Files

You can save and load configurations as JSON:

1. Configure all parameters in the sidebar
2. Click **💾 Save Config** to download JSON
3. Later, use **📁 Load Config** to restore

Example config:
```json
{
  "project": {"name": "Dense Urban n78", "area_km2": 50, "center_lat": 10.78, "center_lon": 106.70},
  "environment": {"scenario": "UMa", "obstacle_density": "heavy", "coverage_prob": 0.95},
  "base_station": {"antenna_config": "32T32R", "tx_power_w": 200, "bs_height_m": 25, "sectors": 3},
  "frequency": {"band": "n78", "bandwidth_mhz": 100, "scs_khz": 30, "tdd_dl_ratio": 0.70},
  "ue": {"power_class": "PC3", "ue_height_m": 1.5, "ue_noise_figure": 7.0},
  "margins": {"interference_db": 3.0, "penetration_db": 10.0, "rain_db": 1.0, "overlap_factor": 0.25},
  "qos": {"primary_service": "mixed", "users_per_km2": 300, "dl_per_user_mbps": 20, "ul_per_user_mbps": 5, "concurrent_ratio": 0.10}
}
```

## CLI Mode (Advanced)

For automation and scripting, use the `rf5g` CLI:

### Calculate Sizing

```cmd
rf5g size --config my_config.json --output results.json
rf5g size --area 50 --scenario UMa --band n78 --power 200
```

### Generate Reports

```cmd
rf5g report --config my_config.json --format html
rf5g report --config my_config.json --format md
```

### Generate Coverage Map

```cmd
rf5g map --config my_config.json --output coverage_map.html
rf5g map --area 50 --scenario UMa --band n78 --lat 10.78 --lon 106.70
```

### Generate Charts

```cmd
rf5g charts --config my_config.json --output-dir ./output
```

### Export Sites

```cmd
rf5g sites count --config my_config.json
rf5g sites export-json --config my_config.json --output sites.json
rf5g sites export-csv --config my_config.json --output sites.csv
```

### Run Geometry-Aware Planning

```cmd
rf5g plan --config planning_config.json --output plan_results.json
```

### Display Lookup Tables

```cmd
rf5g tables
rf5g tables --band n78
```

### Example Config Files

See `examples/` directory for sample configurations:
- `dense_urban_n78.json` — Urban macro, n78, 100MHz, 32T32R
- `suburban_n77.json` — Suburban, n77, 50MHz, 8T8R
- `rural_n8.json` — Rural macro, n8, 10MHz, 4T4R

## Tips

- **Start with presets** and customize from there
- **Penetration loss** is the most sensitive parameter — adjust carefully
- **Coverage probability** 0.95 vs 0.90 can mean 20–30% more sites
- **Check capacity** — sometimes you need more sites for capacity than coverage
- **Use the coverage map** to visualize site placement before deployment

## Stopping the Server

- Press **Ctrl+C** in the command window, or
- Close the browser tab and the command window

## Support

- GitHub: https://github.com/nhnam/rf5g-sizing
- License: MIT