# rf5g-sizing — User Guide

## Overview

rf5g-sizing is a 5G NR RF Coverage Sizing Tool based on 3GPP standards. It helps radio planners estimate the number of base stations needed, verify QoS targets, and generate coverage maps.

**Two Workflows:**

| Workflow | Purpose | Complexity | Time |
|----------|---------|------------|------|
| **Quick Sizing** | Estimate site count and coverage | Simple | ~1 min |
| **Planning** | Geometry-aware site placement | Advanced | ~5 min |

> 💡 **Recommendation:** Start with Quick Sizing. Use Planning when you need actual site positions.

---

## Quick Sizing Workflow

### Step 1: Launch

1. Start rf5g-sizing (Desktop shortcut or `streamlit run rf5g/web/guided.py`)
2. Browser opens at `http://localhost:8501`

### Step 2: Choose Starting Point

**Option A: Select a Preset (Recommended)**

Choose from curated scenarios:
- 🏙️ **Dense Urban n78** — High-density urban, 3.5 GHz
- 🏘️ **Suburban n77** — Suburban residential, 3.3 GHz
- 🌾 **Rural n8** — Rural wide-area, 900 MHz

**Option B: Load Config File**

Click **📁 Load Config** to restore a saved JSON configuration.

**Option C: Manual Input**

Enter parameters directly (see Parameter Reference below).

### Step 3: Adjust Parameters (Optional)

Modify key parameters in the expandable sections:

| Parameter | Typical Range | Impact |
|-----------|---------------|--------|
| Coverage Area | 1–1000 km² | Site count scales linearly |
| Scenario | UMa/UMi/RMa/InH | Propagation model |
| Band | n78, n77, n41, n8 | Frequency, coverage |
| TX Power | 40–320 W | Cell radius |
| Penetration Loss | 5–20 dB | Indoor coverage depth |

### Step 4: Calculate

Click **🚀 Tính toán** (Calculate)

### Step 5: Review Results

**Key Metrics:**
- **Cell Radius** — Coverage range per site
- **Coverage Sites** — Sites needed for coverage
- **Limiting Link** — UL or DL bottleneck
- **Cell Edge SINR** — Signal quality at cell edge
- **Capacity** — Supply vs demand

**Warnings** appear for:
- Extreme parameter combinations
- Approximation-sensitive scenarios
- Equipment mismatches

### Step 6: Export (Optional)

| Export | Format | Use Case |
|--------|--------|----------|
| 📊 Report | HTML, MD | Documentation, sharing |
| 🗺️ Map | HTML | Coverage visualization |
| 📋 Sites | JSON, CSV | Site list for planning tools |

---

## Planning Workflow

Planning adds geometry-aware site placement on top of Quick Sizing.

### Prerequisites

Complete Quick Sizing first (Steps 1–5) to establish baseline coverage parameters.

### Step 1: Enable Planning Mode

In the UI, select **"Geometry-aware planning"** in the Planning section.

### Step 2: Define Service Area

Provide a polygon defining the area to cover:

```json
{
  "coordinates": [
    [106.70, 10.75],
    [106.75, 10.75],
    [106.75, 10.80],
    [106.70, 10.80],
    [106.70, 10.75]
  ]
}
```

### Step 3: Add Constraints (Optional)

**Exclusion Zones** — Areas where sites cannot be placed:
- Water bodies
- Protected areas
- Existing buildings

**Alignment Corridors** — Linear features for site placement:
- Roads
- Railways
- Utility corridors

**Locked Sites** — Existing sites to preserve:
- Current cell towers
- Planned site locations

### Step 4: Configure Capacity (Optional)

**Traffic Zones** — Areas with specific demand:
```json
{
  "polygon": {"coordinates": [...]},
  "demand_dl_mbps": 500,
  "demand_ul_mbps": 100
}
```

### Step 5: Run Planning

Click **🚀 Tính toán** (Calculate)

### Step 6: Review Planning Results

**Key Outputs:**
- **Selected Sites** — Site positions (lat/lon)
- **Coverage Ratio** — % of service area covered
- **Unserved Demand** — Capacity gaps
- **Overloaded Sites** — Sites exceeding load limits

### Step 7: Iterate

- **Lock** good sites
- **Adjust** constraints
- **Re-run** planning
- **Compare** results

### Step 8: Export

Export site positions for use in:
- Radio planning tools (Atoll, Planet)
- GIS applications
- Field surveys

---

## Parameter Reference

### Project

| Parameter | Description | Default |
|-----------|-------------|---------|
| Name | Project label | "untitled" |
| Area (km²) | Total coverage area | 50 |
| Center Lat/Lon | Map center | 10.82, 106.63 |

### Environment

| Scenario | Description | Use Case |
|----------|-------------|----------|
| UMa | Urban Macro | High BS (25m+), outdoor |
| UMi | Urban Micro | Low BS (<25m), outdoor |
| RMa | Rural Macro | Wide area, low density |
| InH | Indoor Hotspot | Shopping malls, stadiums |

| Obstacle Density | Penetration Loss |
|------------------|------------------|
| heavy | 15–20 dB (dense urban) |
| medium | 8–12 dB (suburban) |
| light | 3–6 dB (rural) |

### Base Station

| Antenna Config | Gain | Beamforming | Use Case |
|----------------|------|-------------|----------|
| 64T64R | 23 dBi | 15 dB | High capacity urban |
| 32T32R | 20 dBi | 12 dB | Standard urban |
| 16T16R | 18 dBi | 9 dB | Suburban |
| 8T8R | 15 dBi | 6 dB | Rural |
| 4T4R | 12 dBi | 3 dB | Low capacity |
| 2T2R | 9 dBi | 0 dB | Small cell |

### Frequency

| Band | Frequency | Typical Use |
|------|-----------|-------------|
| n78 | 3.5 GHz | 5G mid-band (TDD) |
| n77 | 3.3–4.2 GHz | 5G mid-band (TDD) |
| n41 | 2.5 GHz | 5G low-band (TDD) |
| n8 | 900 MHz | 5G low-band (FDD) |
| n28 | 700 MHz | 5G low-band (FDD) |
| n71 | 600 MHz | 5G low-band (FDD) |

### QoS

| Service | SINR Req | Use Case |
|---------|----------|----------|
| VoNR | -3 dB | Voice calls |
| Video HD | 5 dB | 1080p streaming |
| Video 4K | 10 dB | 4K streaming |
| Data | 0 dB | General data |
| Gaming | 8 dB | Low latency gaming |
| IoT | -5 dB | IoT sensors |

---

## CLI Reference

### Quick Sizing

```bash
# From config file
rf5g size --config examples/dense_urban_n78.json --output results.json

# With command-line options
rf5g size --area 50 --scenario UMa --band n78 --power 200

# Generate report
rf5g report --config my_config.json --format html

# Generate map
rf5g map --config my_config.json --output coverage.html
```

### Planning

```bash
# Run geometry-aware planning
rf5g plan --config planning_config.json --output plan_results.json
```

### Sites Export

```bash
# Count sites
rf5g sites count --config my_config.json

# Export as JSON
rf5g sites export-json --config my_config.json --output sites.json

# Export as CSV
rf5g sites export-csv --config my_config.json --output sites.csv
```

### Lookup Tables

```bash
# List all bands
rf5g tables

# Show specific band
rf5g tables --band n78
```

---

## Tips

1. **Start with presets** — They have sensible defaults for common scenarios
2. **Penetration loss** is the most sensitive parameter — adjust carefully
3. **Coverage probability** 0.95 vs 0.90 can mean 20–30% more sites
4. **Check capacity** — Sometimes you need more sites for capacity than coverage
5. **Use warnings** — They highlight potential issues before deployment
6. **Review assumptions** — Check Section 7 in reports for model limitations

---

## Standards Referenced

- **3GPP TR 38.901** — Propagation models
- **3GPP TS 38.104** — Base station RF requirements
- **3GPP TS 38.214** — Physical layer measurements
- **3GPP TS 38.306** — UE capabilities

---

## Support

- **GitHub:** https://github.com/nhnam/rf5g-sizing
- **License:** MIT