# Example Configurations

This directory contains preset configurations for common 5G NR planning scenarios.

## Available Presets

| Preset | Scenario | Band | Bandwidth | Antenna | Use Case |
|--------|----------|------|-----------|---------|----------|
| **dense_urban_n78.json** | UMa | n78 | 100 MHz | 32T32R | High-density urban areas (city centers, CBDs) |
| **suburban_n77.json** | UMa | n77 | 50 MHz | 8T8R | Suburban residential, urban fringe |
| **rural_n8.json** | RMa | n8 | 10 MHz | 4T4R | Rural wide-area coverage, low-density areas |
| **indoor_hotspot_n77.json** | InH | n77 | 100 MHz | 4T4R | Shopping malls, stadiums, convention centers |
| **capacity_hotspot_n78.json** | UMi | n78 | 100 MHz | 64T64R | High-capacity zones (venues, transit hubs) |

## When to Use Each Preset

### Dense Urban n78
- **Environment:** Urban macro, heavy clutter, tall buildings
- **Coverage area:** 50 km² typical
- **Characteristics:** Small cells, UL-limited, high site count
- **Typical sites:** 1000-2000 per 50 km²

### Suburban n77
- **Environment:** Urban/suburban macro, medium clutter
- **Coverage area:** 200 km² typical
- **Characteristics:** Moderate cell radius, balanced DL/UL
- **Typical sites:** 500-1500 per 200 km²

### Rural n8
- **Environment:** Rural macro, light clutter, open terrain
- **Coverage area:** 500 km² typical
- **Characteristics:** Wide coverage, low capacity, FDD
- **Typical sites:** 3-10 per 500 km²

### Indoor Hotspot n77
- **Environment:** Indoor, heavy obstacles, dense users
- **Coverage area:** 0.1 km² (single building/floor)
- **Characteristics:** Small cells, high capacity, low power
- **Typical sites:** 1-5 per floor

### Capacity Hotspot n78
- **Environment:** Urban micro, high interference, dense users
- **Coverage area:** 5 km²
- **Characteristics:** High capacity, 64T64R, small cells
- **Typical sites:** 100-300 per 5 km²

## How to Use

### CLI
```bash
rf5g size --config examples/dense_urban_n78.json --output results.json
```

### API
```bash
curl -X POST http://localhost:8000/size \
  -H "Content-Type: application/json" \
  -d @examples/dense_urban_n78.json
```

### UI
In the guided UI, select the preset from the dropdown in Step 1.

## Customizing Presets

1. Copy the preset JSON file
2. Modify parameters as needed
3. Run with `--config your_custom.json`

Key parameters to adjust:
- `project.area_km2` — Your coverage area
- `project.center_lat/center_lon` — Your location
- `margins.penetration_db` — Building penetration depth
- `qos.users_per_km2` — Your user density
- `qos.dl_per_user_mbps` — Your throughput targets

## Adding New Presets

To add a new preset:

1. Create a JSON file in this directory
2. Follow the schema in `rf5g/models/input_schema.py`
3. Include all required sections: project, environment, base_station, frequency, user_equipment, margins, qos
4. Add a brief description in this README