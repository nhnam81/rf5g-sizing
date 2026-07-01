# rf5g-sizing — Canonical Workflow

> This document defines the official user journey through the rf5g-sizing tool.
> All documentation, UI, and CLI should follow this workflow.

## Overview

rf5g-sizing supports two main workflows:

1. **Quick Sizing** — Fast coverage/capacity estimation with minimal inputs
2. **Planning** — Geometry-aware site placement with advanced constraints

---

## Quick Sizing Workflow

For users who need fast answers: *"How many sites do I need?"*

### Step 1: Choose Starting Point

| Option | Description |
|--------|-------------|
| **Preset** | Select from curated scenario library (recommended for new users) |
| **Config file** | Load existing JSON configuration |
| **Manual input** | Enter parameters directly |

### Step 2: Configure Basic Parameters

**Required:**
- Coverage area (km²)
- Scenario (UMa/UMi/RMa/InH)
- Band (n78, n77, n41, n8, etc.)
- TX power (W)

**Optional with sensible defaults:**
- Antenna config (default: 32T32R)
- Bandwidth (default: 100 MHz)
- Users per km²
- Per-user throughput requirements

### Step 3: Run Sizing

Click **Calculate** or run:
```bash
rf5g size --config my_config.json
```

### Step 4: Review Results

**Key outputs:**
- Cell radius (m)
- Coverage sites needed
- Limiting link (UL/DL)
- Cell-edge SINR and CQI
- Capacity vs demand

**Warnings** appear for:
- Extreme parameter combinations
- Approximation-sensitive scenarios
- Equipment mismatch issues

### Step 5: Export (Optional)

- **Report**: HTML or Markdown summary
- **Map**: Interactive coverage map
- **Sites**: JSON/CSV site positions

---

## Planning Workflow

For users who need site placement: *"Where should I put my sites?"*

### Step 1: Complete Quick Sizing First

Planning requires sizing results as input. Complete Steps 1-4 of Quick Sizing.

### Step 2: Define Planning Constraints

**Geometry inputs:**
- Service area polygon (required)
- Exclusion zones (optional)
- Alignment corridors (optional)
- Existing/locked sites (optional)

**Capacity inputs:**
- Traffic demand zones
- Maximum load per site

### Step 3: Run Planning

Click **Calculate** or run:
```bash
rf5g plan --config planning_config.json
```

### Step 4: Review Planning Results

**Key outputs:**
- Selected site positions
- Coverage ratio
- Unserved demand
- Overloaded sites
- Planning scorecard

### Step 5: Iterate (Optional)

- Lock/unlock sites
- Adjust constraints
- Re-run planning
- Compare plans

### Step 6: Export

- **Sites**: JSON/CSV with coordinates
- **Map**: Interactive map with site markers
- **Report**: Full planning summary

---

## CLI Quick Reference

```bash
# Quick sizing from preset
rf5g size --area 50 --scenario UMa --band n78 --power 200

# Quick sizing from config
rf5g size --config examples/dense_urban_n78.json --output results.json

# Generate report
rf5g report --config examples/dense_urban_n78.json --format html

# Generate map
rf5g map --config examples/dense_urban_n78.json --output coverage.html

# Planning
rf5g plan --config planning_config.json

# Export sites
rf5g sites export-json --config my_config.json --output sites.json
```

---

## UI Quick Reference

### Guided Mode (Recommended)

1. **Select preset** from dropdown
2. **Adjust parameters** in expandable sections
3. Click **🚀 Tính toán**
4. Review results in tabs:
   - **Results**: Key metrics
   - **Planning**: Site placement (if enabled)
   - **Map**: Coverage visualization
   - **Export**: Download options

### Quick Mode

Direct parameter input without preset guidance.

---

## Decision Tree

```
┌─────────────────────────────────────────────────────────────┐
│                    What do you need?                         │
└─────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
    "How many sites?"                 "Where to put sites?"
            │                               │
            ▼                               ▼
    ┌───────────────┐               ┌───────────────┐
    │  Quick Sizing │               │   Planning    │
    └───────────────┘               └───────────────┘
            │                               │
            ▼                               ▼
    • Choose preset            • Complete sizing first
    • Adjust params            • Define service area
    • Calculate                • Add constraints
    • Review results           • Run planner
    • Export report/map        • Iterate & export
```

---

## Surface Alignment

All entry points should follow this workflow:

| Surface | Entry Point | Workflow Support |
|---------|-------------|------------------|
| **CLI** | `rf5g size` | Quick Sizing |
| **CLI** | `rf5g plan` | Planning |
| **API** | `POST /size` | Quick Sizing |
| **API** | `POST /placement/plan` | Planning |
| **UI** | Guided Mode | Both (tabbed) |
| **Docs** | USER_GUIDE.md | Both (sections) |

---

## Next Steps

After completing a workflow:

1. **Review assumptions** in the report
2. **Check warnings** for edge cases
3. **Validate** against real-world constraints
4. **Iterate** with adjusted parameters
5. **Export** for downstream tools (Atoll, planning tools, etc.)