# Geometry-Aware Planning Guide

> This guide explains how to use the geometry-aware site placement planning feature in rf5g-sizing.

## Overview

The planning module enables **geometry-aware site placement** within a defined service area, considering:
- Service area boundaries (polygon)
- Exclusion zones (areas where sites cannot be placed)
- Alignment corridors (linear features like roads, railways)
- Existing/locked sites (sites to preserve)
- Capacity demand (traffic zones with specific throughput requirements)

## When to Use Planning

| Use Case | Recommended Approach |
|----------|----------------------|
| Quick site count estimate | Use **Quick Sizing** workflow |
| Site placement along a corridor | Use **Planning** with alignments |
| Coverage within specific boundaries | Use **Planning** with service area polygon |
| Avoiding restricted areas | Use **Planning** with exclusion zones |
| Preserving existing sites | Use **Planning** with locked sites |

## Planning Workflow

### Step 1: Define Service Area

The service area is a polygon that defines the coverage boundary.

**Coordinate System:** WGS84 (EPSG:4326)

**Format:**
```json
{
  "coordinates": [
    [lon1, lat1],
    [lon2, lat2],
    [lon3, lat3],
    ...
    [lon1, lat1]  // Close the polygon
  ]
}
```

**Example:**
```json
{
  "placement": {
    "service_area": {
      "coordinates": [
        [106.70, 10.75],
        [106.80, 10.75],
        [106.80, 10.85],
        [106.70, 10.85],
        [106.70, 10.75]
      ]
    }
  }
}
```

### Step 2: Define Exclusion Zones (Optional)

Exclusion zones are areas where sites cannot be placed (water bodies, protected areas, etc.).

```json
{
  "placement": {
    "exclusion_zones": [
      {
        "name": "Lake Area",
        "polygon": {
          "coordinates": [[106.72, 10.77], [106.74, 10.77], [106.74, 10.79], [106.72, 10.79], [106.72, 10.77]]
        }
      }
    ]
  }
}
```

### Step 3: Define Alignments (Optional)

Alignments are linear corridors for site placement (roads, railways, utility lines).

```json
{
  "placement": {
    "alignments": [
      {
        "points": [
          {"lat": 10.76, "lon": 106.71},
          {"lat": 10.84, "lon": 106.79}
        ],
        "width_m": 500
      }
    ]
  }
}
```

### Step 4: Lock Existing Sites (Optional)

Preserve existing or planned sites during planning.

```json
{
  "placement": {
    "planned_sites": [
      {
        "id": "site-001",
        "lat": 10.78,
        "lon": 106.75,
        "status": "locked",
        "azimuth_deg": 0
      }
    ]
  }
}
```

**Status options:**
- `locked` — Site must be included, cannot be moved
- `existing` — Existing site to preserve
- `candidate` — Proposed site for evaluation

### Step 5: Configure Planning Parameters

```json
{
  "placement": {
    "placement_mode": "auto",
    "objective": "coverage_first",
    "min_site_spacing_m": 300,
    "edge_setback_m": 50
  }
}
```

**Placement modes:**
| Mode | Description |
|------|-------------|
| `auto` | Automatic site placement within service area |
| `alignment_only` | Sites only along defined alignments |
| `manual` | Use only manually defined sites |

**Planning objectives:**
| Objective | Description |
|-----------|-------------|
| `coverage_first` | Maximize coverage area first |
| `capacity_first` | Prioritize high-demand areas |
| `balanced` | Balance coverage and capacity |

### Step 6: Add Capacity Demand (Optional)

Define traffic demand zones for capacity-aware planning.

```json
{
  "spatial_capacity": {
    "enabled": true,
    "grid_resolution_m": 100,
    "demand_zones": [
      {
        "polygon": {"coordinates": [...]},
        "demand_dl_mbps": 500,
        "demand_ul_mbps": 100
      }
    ],
    "max_load_per_site_mbps_dl": 500,
    "max_load_per_site_mbps_ul": 100
  }
}
```

### Step 7: Run Planning

**CLI:**
```bash
rf5g plan --config planning_config.json --output plan_results.json
```

**UI:**
1. Select "Geometry-aware planning" mode
2. Configure service area and constraints
3. Click Calculate
4. Review planning results

## Planning Results

### Selected Sites

Each selected site includes:
- `id` — Unique identifier
- `lat`, `lon` — WGS84 coordinates
- `source` — How site was selected (auto, locked, alignment, etc.)
- `azimuths_deg` — Sector directions
- `status` — Site status (selected, locked)
- `coverage_area_km2` — Estimated coverage area
- `estimated_dl_load_mbps` — Estimated DL load (if capacity enabled)
- `overloaded` — Whether site exceeds load limits

### Planning Metrics (Scorecard)

| Metric | Description |
|--------|-------------|
| `service_area_km2` | Total service area |
| `covered_area_km2` | Area covered by selected sites |
| `coverage_ratio` | Percentage of service area covered |
| `selected_sites` | Number of sites in plan |
| `locked_sites` | Number of preserved sites |
| `alignment_length_km` | Total alignment length |
| `excluded_area_km2` | Area excluded from planning |

### Spatial Capacity Results

When capacity planning is enabled:

| Metric | Description |
|--------|-------------|
| `demand_dl_gbps` | Total DL demand |
| `served_dl_gbps` | DL demand served by selected sites |
| `unserved_dl_gbps` | DL demand not served |
| `hotspot_tiles` | High-demand grid tiles |
| `overloaded_sites` | Sites exceeding load limits |

## Complete Example

```json
{
  "project": {
    "name": "Corridor Planning n78",
    "area_km2": 50,
    "center_lat": 10.78,
    "center_lon": 106.75
  },
  "environment": {
    "scenario": "UMa",
    "obstacle_density": "medium"
  },
  "base_station": {
    "antenna_config": "32T32R",
    "tx_power_w": 200,
    "height_m": 25,
    "sectors": 3
  },
  "frequency": {
    "band": "n78",
    "bandwidth_mhz": 100
  },
  "placement": {
    "service_area": {
      "coordinates": [
        [106.70, 10.75],
        [106.80, 10.75],
        [106.80, 10.85],
        [106.70, 10.85],
        [106.70, 10.75]
      ]
    },
    "exclusion_zones": [
      {
        "name": "River",
        "polygon": {
          "coordinates": [[106.72, 10.77], [106.74, 10.77], [106.74, 10.79], [106.72, 10.79], [106.72, 10.77]]
        }
      }
    ],
    "alignments": [
      {
        "points": [{"lat": 10.76, "lon": 106.71}, {"lat": 10.84, "lon": 106.79}],
        "width_m": 500
      }
    ],
    "planned_sites": [
      {
        "id": "existing-001",
        "lat": 10.78,
        "lon": 106.73,
        "status": "locked"
      }
    ],
    "placement_mode": "auto",
    "objective": "coverage_first",
    "min_site_spacing_m": 300,
    "edge_setback_m": 50
  },
  "spatial_capacity": {
    "enabled": true,
    "grid_resolution_m": 100,
    "demand_zones": [
      {
        "polygon": {"coordinates": [[106.73, 10.78], [106.77, 10.78], [106.77, 10.82], [106.73, 10.82], [106.73, 10.78]]},
        "demand_dl_mbps": 1000,
        "demand_ul_mbps": 200
      }
    ],
    "max_load_per_site_mbps_dl": 500
  }
}
```

## Tips

1. **Start simple** — Begin with service area only, add constraints incrementally
2. **Lock good sites** — Preserve manually optimized positions
3. **Check coverage ratio** — Aim for >90% coverage in planning results
4. **Review overloaded sites** — May indicate need for more sites or capacity optimization
5. **Use alignments** — For corridor coverage (highways, railways, coastlines)
6. **Export and iterate** — Export sites, adjust in GIS tools, re-import

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Low coverage ratio | Add more sites or reduce exclusion zones |
| Sites outside service area | Check polygon coordinates and coordinate system |
| Too many sites | Increase `min_site_spacing_m` |
| Overloaded sites | Add more sites in high-demand zones |
| No sites along alignment | Check alignment points and width |

## API Endpoints

```bash
# Validate geometry inputs
POST /geometry/validate

# Run placement planning
POST /placement/plan

# Export sites
POST /sites/export
```