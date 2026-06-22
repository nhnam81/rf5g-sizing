# 5G RF Coverage Sizing Tool — PRD (Product Requirements Document)

> **Version:** 1.1 | **Date:** 2026-06-22
> **Status:** Updated — Drag-and-drop sites, Shadow fading fix, WGS84 haversine
> **Author:** OpenClaw Agent | **Owner:** nhnam
>
> **v1.1 changes:**
> - FR-09: Added drag-and-drop site placement with WGS84 (EPSG:4326) haversine conversion
> - FR-09: Added site import/export (JSON/CSV) CLI and API endpoints
> - 6.3: Shadow fading now uses 3GPP TR 38.901 Table 7.4.2-1 sigma × z-score (was fixed table)
> - 6.4: Added drag-and-drop map validation test cases
> - Architecture: Added web/ (Guided + Basic Streamlit), sites CLI, /sites/export + /sites/map API

---

## 1. VISION & PROBLEM

### 1.1 Problem Statement

RF/Planning engineers cần tính nhanh vùng phủ 5G, số trạm cần thiết, và kiểm tra QoS (Voice/Video/Data) — nhưng:

- **Commercial tools** (Atoll, Planet, iBwave): $15K–$50K/license, Windows-only, cần GIS data, setup mất tuần
- **Open-source tools**: chỉ tính link budget cơ bản (5g-tools.com), không có Coverage → QoS → Capacity → Recommendation workflow
- **Excel/Excel**: chậm, dễ sai, không visualize, không mở rộng được

**Gap**: Không có tool open-source nào cung cấp **end-to-end sizing** từ input parameters → link budget → cell radius → site count → SINR mapping → QoS verification → capacity check → recommendations.

### 1.2 Vision

Công cụ **5G RF Sizing** open-source, nhanh, chính xác, giúp kỹ sư RF:
1. Nhập thông số → biết ngay bao nhiêu trạm, bán kính, vùng phủ
2. Kiểm tra QoS: VoNR, Video HD/4K, Data, Gaming có đạt không
3. So sánh scenarios: n78 vs n41, 32T32R vs 8T8R, urban vs suburban
4. Xuất báo cáo, map, recommendation tự động
5. Mở rộng: API để tích hợp, Web UI cho non-technical users

### 1.3 Target Users

| User | Use Case |
|------|----------|
| RF Engineer | Quick site count estimate, link budget validation |
| Network Planner | Scenario comparison, budget planning |
| Sales/Pre-sales | Customer proposal: "50 km² coverage = X sites" |
| Researcher | Benchmark 3GPP models, sensitivity analysis |
| Student | Learn 5G RF planning concepts |

### 1.4 Non-Goals (Phase 1)

- ❌ Không thay thế Atoll/Planet (no GIS terrain, no ray-tracing)
- ❌ Không tính interference coordination (ICIC) chi tiết
- ❌ Không cần DEM/clutter data
- ❌ Không có 3D visualization
- ❌ Không hỗ trợ FR2 (mmWave) trong Phase 1

---

## 2. FUNCTIONAL REQUIREMENTS

### FR-01: Input Parameter Management

**Priority:** P0 (MVP)

- JSON/YAML input file với schema validation (Pydantic)
- Predefined lookup tables (band → frequency, Power Class → TX power, antenna config → gain)
- Sensible defaults cho từng environment (urban/suburban/rural)
- Override bất kỳ parameter nào

**Input schema:**
```json
{
  "project": { "name": "...", "area_km2": 50, "center_lat": 10.78, "center_lon": 106.70 },
  "environment": { "scenario": "UMa", "obstacle_density": "heavy" },
  "base_station": { "antenna_config": "32T32R", "tx_power_w": 200, "height_m": 25, "sectors": 3 },
  "frequency": { "band": "n78", "bandwidth_mhz": 100, "scs_khz": 30, "duplex": "TDD" },
  "user_equipment": { "power_class": 3, "height_m": 1.5 },
  "margins": { "interference_db": 3, "shadow_fading_db": "auto", "penetration_db": 10 },
  "qos": { "primary_service": "mixed", "dl_per_user_mbps": 50, "ul_per_user_mbps": 10, "users_per_km2": 500 }
}
```

### FR-02: Link Budget Calculator (DL/UL)

**Priority:** P0 (MVP)

- Tính EIRP, Rx sensitivity, MAPL cho cả DL và UL
- Hỗ trợ đầy đủ margins: interference, shadow fading, rain, penetration, vegetation, body loss
- Auto-compute shadow fading từ obstacle density + reliability target
- Auto-resolve UE TX power từ Power Class
- Auto-resolve antenna gain từ config (32T32R → 18–21 dBi)

**Output per link:**
```
EIRP, Rx Sensitivity, MAPL, limiting link identification
```

### FR-03: Propagation Models (3GPP TR 38.901)

**Priority:** P0 (MVP)

Implement đầy đủ 4 scenario path loss models:

| Scenario | LOS | NLOS | LOS Probability |
|----------|-----|------|-----------------|
| UMa (Urban Macro) | ✅ | ✅ | ✅ |
| UMi (Urban Micro) | ✅ | ✅ | ✅ |
| RMa (Rural Macro) | ✅ | ✅ | ✅ |
| InH (Indoor Hotspot) | ✅ | ✅ | ✅ |

**Additional models:**
- FSPL (Free Space Path Loss) — baseline comparison
- COST-231 Hata (Extended) — legacy comparison

**MAPL → Cell Radius inversion:**
- Numerical solve cho 3GPP models (non-invertible analytically)
- Analytical solve cho FSPL
- Support both LOS, NLOS, and combined (expected value)

### FR-04: Site Count Estimation

**Priority:** P0 (MVP)

- Hexagonal grid (3-sector): `Area = 2.598 × R²`
- Omnidirectional: `Area = π × R²`
- Overlap factor: configurable (0.15 planned, 0.25 typical, 0.35 conservative)
- Cell radius = min(DL radius, UL radius) — UL typically limiting
- ISD (Inter-Site Distance) calculation

### FR-05: SINR Mapping & QoS Verification

**Priority:** P1 (Phase 2)

- SINR at cell edge calculation: `SINR = RSRP - Interference - Noise`
- SINR → CQI → MCS → Spectral Efficiency mapping (3GPP TS 38.214)
- Service zone mapping: % cell area đạt VoNR, Video HD, Data
- QoS verification table: pass/fail cho từng service type

| Service | SINR min | Cell Radius | % Area | Pass? |
|---------|----------|-------------|--------|-------|
| VoNR | -3 dB | 0.68 km | 87% | ✅ |
| Video HD | 5 dB | 0.38 km | 47% | ❌ |
| Data 50Mbps | 0 dB | 0.55 km | 70% | ⚠️ |

### FR-06: Capacity Dimensioning

**Priority:** P1 (Phase 2)

- Cell throughput calculation: `BW × SE × layers × (1-OH) × TDD_share`
- TDD duplex ratio support (7:3, 8:2, custom)
- User capacity per service type
- Overprovisioning ratio (concurrent users %)
- **Capacity check**: nếu capacity-limited → calculate additional sites needed
- Final site count = max(coverage sites, capacity sites)

### FR-07: Recommendation Engine

**Priority:** P1 (Phase 2)

Rule-based recommendations:

| Condition | Recommendation |
|-----------|---------------|
| UL limiting & UE PC3 | "Upgrade to Power Class 2 (+3 dB UL)" |
| Shadow fading > 12 dB | "Heavy clutter. Consider more sites or lower reliability" |
| Cell radius < 200m | "Small cell deployment. Consider 4T4R/2T2R" |
| Cell radius > 5km | "Verify RMa model. Terrain may limit coverage" |
| ISD < 500m | "Ultra-dense. ICIC recommended" |
| Capacity insufficient | "Add carrier, increase BW, or deploy small cells" |
| SINR too low for VoNR | "Increase TX power, upgrade antenna, add sites" |

### FR-08: Scenario Comparison

**Priority:** P1 (Phase 2)

- Chạy nhiều scenarios cùng lúc (e.g., n78 vs n41, 32T32R vs 8T8R)
- Side-by-side comparison table
- Export comparison report (Markdown)

### FR-08: Antenna Pattern Support

**Priority:** P1 (Phase 1 core)

- **Built-in patterns**: Omni, Panel 120°, Panel 65°, Panel 90°, BF 30°, BF 60°
- **Auto-mapping**: Antenna config → pattern (e.g., 32T32R → BF 60°, 64T64R → BF 30°)
- **Atoll .ant import**: Parse Atoll antenna pattern files
- **CSV import**: azimuth,gain_db columns
- **JSON import**: Full pattern definition with metadata
- **Directional coverage**: Per-sector coverage polygon based on antenna pattern
- **Sector visualization**: 3-sector (0°/120°/240°), 6-sector (0°/60°/120°/180°/240°/300°), omni
- **Gain pattern**: Cosine-shaped main lobe, side lobes, front-to-back ratio
- **Path-loss-aware radius**: coverage radius scales by gain (10^(gain/70))
- **WGS84 haversine**: Accurate lat/lon conversion at all latitudes

**Mapping:**
- 2T2R → Omni (360°, 2 dBi)
- 4T4R → Panel 120° (17 dBi)
- 8T8R → Panel 120° (17 dBi)
- 16T16R → Panel 65° (20 dBi)
- 32T32R → BF 60° (22 dBi)
- 64T64R → BF 30° (25 dBi)

**CLI commands:**
```bash
# Use built-in pattern
rf5g map --config scenario.json --antenna-pattern panel_120

# Import Atoll .ant file
rf5g map --config scenario.json --antenna-pattern /path/to/Kathrein_80010554.ant

# Import CSV pattern
rf5g map --config scenario.json --antenna-pattern /path/to/pattern.csv

# Import JSON pattern
rf5g map --config scenario.json --antenna-pattern /path/to/pattern.json
```

**Priority:** P2 (Phase 3)

- **Folium map** (HTML interactive): coverage rings, hex grid, site markers
- **Drag-and-drop site placement**: draggable markers, add/delete sites, recalculate coverage
- **Per-site hex visualization**: coverage area per site, SINR color coding
- **Site import/export**: JSON/CSV format, WGS84 (EPSG:4326) coordinates
- **Haversine distance**: accurate km↔lat/lon conversion at all latitudes
- **Matplotlib charts**: link budget bar chart, SINR heatmap, service zone pie
- **Jinja2 report template**: Markdown/HTML report

**Drag-and-drop capabilities:**
- Drag site markers to reposition → auto-update coverage hex
- Delete site via popup button
- Export sites as JSON/CSV from browser sidebar
- Import custom sites via CLI `--sites` flag or API `/sites/map`
- Coordinate system: WGS84 (EPSG:4326) with haversine-based km↔deg conversion
- Per-site popup: site ID, lat/lon, cell radius, SINR, path loss

**Site management CLI commands:**
```bash
rf5g sites export-json --config scenario.json --output sites.json
rf5g sites export-csv --config scenario.json --output sites.csv
rf5g sites import --sites-file sites.json
rf5g sites count --config scenario.json
rf5g map --config scenario.json --sites custom_sites.json
```

### FR-10: Web UI

**Priority:** P3 (Phase 4)

- FastAPI backend (reuse calculation engine)
- Streamlit frontend (quick MVP) hoặc React (polished)
- Interactive parameter sliders
- Real-time calculation (sub-second response)
- Export PDF/Excel

### FR-11: CLI Interface

**Priority:** P0 (MVP)

```bash
# Single scenario
rf5g size --config scenario.json --output result.json

# Quick estimate
rf5g size --area 50 --scenario UMa --band n78 --power 200 --config 32T32R

# Scenario comparison
rf5g compare --configs urban.json suburban.json rural.json

# Generate map
rf5g map --config scenario.json --output coverage.html

# Show lookup tables
rf5g tables --band n78 --config 32T32R
```

---

## 3. NON-FUNCTIONAL REQUIREMENTS

### NFR-01: Accuracy

- Propagation models: ±3 dB so với 3GPP TR 38.901 reference implementation
- Link budget: ±0.5 dB vs manual calculation
- Site count: ±10% vs commercial tools (Atoll, Planet)
- SINR estimation: ±2 dB vs simulation
- **Validation**: unit tests cho từng model với known values từ 3GPP spec

### NFR-02: Performance

- Single scenario calculation: < 1 second (CLI)
- Batch 100 scenarios: < 10 seconds
- Map generation: < 5 seconds
- Web API response: < 500ms (p95)

### NFR-03: Usability

- CLI: sensible defaults, `--help` đầy đủ, JSON input/output
- Zero-config start: `rf5g size --area 50 --band n78` chạy được với defaults
- Error messages rõ ràng, suggest fix
- Vietnamese + English error messages

### NFR-04: Extensibility

- Plugin architecture cho propagation models (dễ thêm model mới)
- Schema-based input/output (Pydantic)
- API-first design (Web UI gọi API, CLI gọi API)

### NFR-05: Documentation

- README với quick start
- API reference (auto-generated từ docstrings)
- Worked examples cho từng scenario
- Validation test cases vs 3GPP spec

---

## 4. ARCHITECTURE

### 4.1 Module Structure

```
rf5g/
├── __init__.py
├── cli.py                    # Typer CLI entry point (size, map, report, charts, tables, sites)
├── models/
│   ├── __init__.py
│   ├── input_schema.py       # Pydantic input model
│   ├── output_schema.py      # Pydantic output model
│   ├── lookup_tables.py      # Band, Power Class, Antenna Config, SF (3GPP TR 38.901)
│   ├── antenna_pattern.py   # Antenna radiation patterns (built-in + Atoll/CSV/JSON import)
├── engine/
│   ├── __init__.py
│   ├── propagation.py        # 3GPP TR 38.901 path loss models
│   ├── link_budget.py        # DL/UL link budget calculator
│   ├── site_estimator.py     # Cell radius → site count
│   ├── sinr_mapper.py       # SINR → CQI → MCS → SE
│   ├── capacity.py            # Cell capacity, user capacity
│   ├── qos_verifier.py       # QoS pass/fail verification
│   └── recommender.py        # Rule-based recommendations
├── api/
│   ├── __init__.py
│   └── app.py                # FastAPI app (14 endpoints + sites/map + sites/export)
├── viz/
│   ├── __init__.py
│   ├── coverage_map.py       # Folium map generator (drag-and-drop, WGS84, haversine)
│   ├── charts.py             # Matplotlib charts
│   └── report.py             # Jinja2 report generator
├── data/
│   ├── bands.json            # 3GPP TS 38.104 frequency bands
│   ├── power_classes.json     # 3GPP TS 38.101 UE power classes
│   ├── antenna_configs.json  # Antenna config → gain/BF mapping
│   ├── sinr_cqi_table.json   # SINR → CQI → MCS → SE
│   ├── qos_requirements.json # Service → SINR/throughput/latency
│   └── shadow_fading.json    # Scenario-based SF margin (3GPP TR 38.901 Table 7.4.2-1)
├── web/
│   ├── __init__.py
│   ├── app.py                # Streamlit Basic Mode
│   └── guided.py            # Streamlit Guided Mode (Vietnamese)
└── tests/
    ├── test_propagation.py    # vs 3GPP spec values
    ├── test_link_budget.py    # vs manual calculations
    ├── test_capacity.py
    ├── test_qos.py
    ├── test_integration.py   # End-to-end scenarios
    ├── test_phase2.py
    ├── test_phase3.py
    └── test_phase4.py
```

### 4.2 Data Flow

```
┌─────────────────┐
│   INPUT (JSON)   │
│  project, env,   │
│  BS, freq, UE,   │
│  margins, QoS    │
└────────┬──────────┘
         │
         ▼
┌─────────────────┐
│ PARAM RESOLVER   │  band→fc, PC→TX, config→gain, density→SF
└────────┬──────────┘
         │
         ▼
┌─────────────────┐
│ LINK BUDGET      │  DL/UL EIRP, sensitivity, MAPL
└────────┬──────────┘
         │
         ▼
┌─────────────────┐
│ PROPAGATION      │  3GPP 38.901 models → cell radius
└────────┬──────────┘
         │
         ▼
┌─────────────────┐
│ SITE ESTIMATOR   │  hex grid → site count, ISD
└────────┬──────────┘
         │
         ▼
┌─────────────────┐
│ SINR MAPPER      │  cell edge SINR → CQI → MCS → SE
└────────┬──────────┘
         │
         ▼
┌─────────────────┐
│ CAPACITY CHECK   │  cell throughput vs user demand
└────────┬──────────┘
         │
         ▼
┌─────────────────┐
│ QoS VERIFIER     │  pass/fail per service type
└────────┬──────────┘
         │
         ▼
┌─────────────────┐
│ RECOMMENDER      │  rule-based suggestions
└────────┬──────────┘
         │
         ▼
┌─────────────────┐
│ OUTPUT (JSON)    │
│  coverage, QoS,  │
│  capacity, recs  │
└──────────────────┘
```

### 4.3 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python 3.11+ | RF domain, numpy/scipy, py3gppchannels |
| CLI framework | Typer | Type-safe, auto-docs, modern |
| Schema validation | Pydantic v2 | Fast, type-safe, JSON Schema generation |
| Propagation models | Custom + py3gppchannels | Direct 3GPP formulas, cross-validated |
| Map visualization | Folium | Interactive HTML, no GIS needed |
| Web framework | FastAPI | Async, auto OpenAPI docs, Pydantic |
| Testing | pytest + hypothesis | Unit + property-based for edge cases |
| Package distribution | pip (PyPI) | Easy install, standard |

---

## 5. IMPLEMENTATION PLAN

### Phase 1 — MVP Core (Week 1-3)

**Goal:** CLI tool tính link budget → cell radius → site count

| Day | Task | Deliverable |
|-----|------|-------------|
| 1-2 | Project setup, input schema, lookup tables | `models/input_schema.py`, `models/lookup_tables.py` |
| 3-5 | Propagation models (UMa, UMi, RMa, InH, FSPL) | `engine/propagation.py` + tests |
| 6-8 | Link budget calculator (DL/UL) | `engine/link_budget.py` + tests |
| 9-10 | Site estimator (hex/omni) | `engine/site_estimator.py` + tests |
| 11-13 | CLI (Typer), JSON input/output | `cli.py` |
| 14 | Validation against 3GPP spec values | Test report |
| 15 | Example configs + README | `examples/` |

**Exit criteria:**
```bash
rf5g size --config examples/dense_urban_n78.json --output result.json
# → cell_radius_km, mapl_dl, mapl_ul, n_sites, isd_km
```

### Phase 2 — QoS & Capacity (Week 4-5)

**Goal:** SINR mapping, QoS verification, capacity check

| Day | Task | Deliverable |
|-----|------|-------------|
| 16-17 | SINR → CQI → MCS → SE tables | `engine/sinr_mapper.py` |
| 18-19 | QoS verifier (Voice/Video/Data/Gaming) | `engine/qos_verifier.py` |
| 20-22 | Capacity dimensioning | `engine/capacity.py` |
| 23-24 | Recommendation engine | `engine/recommender.py` |
| 25 | Integration + CLI update | Updated `cli.py` |
| 26-28 | Scenario comparison | `rf5g compare` command |

**Exit criteria:**
```bash
rf5g size --config examples/dense_urban_n78.json --output result.json
# → + qos_verification, capacity_check, recommendations
```

### Phase 3 — Visualization (Week 6-7)

**Goal:** Coverage map, charts, reports

| Day | Task | Deliverable |
|-----|------|-------------|
| 29-31 | Folium coverage map | `viz/coverage_map.py` |
| 32-34 | Matplotlib charts | `viz/charts.py` |
| 35-37 | Jinja2 report templates | `viz/report.py` |
| 38-39 | CLI map/report commands | `rf5g map`, `rf5g report` |

**Exit criteria:**
```bash
rf5g map --config examples/dense_urban_n78.json --output coverage.html
# → Interactive HTML map with coverage rings + hex grid
```

### Phase 4 — Web UI (Week 8-10)

**Goal:** FastAPI + Streamlit web interface

| Day | Task | Deliverable |
|-----|------|-------------|
| 40-42 | FastAPI backend (endpoints: /size, /compare, /map) | `api/app.py` |
| 43-47 | Streamlit frontend | Input form, results display, map |
| 48-49 | PDF/Excel export | Report generation |
| 50 | Deployment docs | Docker, cloud deploy |

**Exit criteria:**
```
http://localhost:8501 → Input form → Results + Map + Report
```

---

## 6. VALIDATION PLAN

### 6.1 Unit Tests vs 3GPP Spec

| Model | Test Source | Tolerance |
|-------|-----------|-----------|
| UMa LOS | TR 38.901 Table 7.4.1-1 | ±0.5 dB |
| UMa NLOS | TR 38.901 Table 7.4.1-1 | ±0.5 dB |
| UMi LOS | TR 38.901 Table 7.4.1-1 | ±0.5 dB |
| UMi NLOS | TR 38.901 Table 7.4.1-1 | ±0.5 dB |
| RMa LOS | TR 38.901 Table 7.4.1-1 | ±0.5 dB |
| RMa NLOS | TR 38.901 Table 7.4.1-1 | ±0.5 dB |
| InH LOS | TR 38.901 Table 7.4.1-1 | ±0.5 dB |
| InH NLOS | TR 38.901 Table 7.4.1-1 | ±0.5 dB |
| FSPL | Analytical | ±0.01 dB |
| LOS Probability | TR 38.901 §7.4.2 | ±0.01 |

### 6.2 Integration Tests

| Scenario | Expected Result | Source |
|----------|----------------|--------|
| Dense urban n78 (50 km²) | ~121-224 sites | Phase 2 worked example |
| Suburban n77 (200 km²) | ~458-573 sites | Phase 2 worked example |
| Rural n8 (500 km²) | ~40-60 sites | Phase 2 worked example |
| Link budget DL/UL | MAPL ±0.5 dB | Manual calculation |

### 6.3 Cross-Validation

- Compare results với **5g-tools.com** calculator (same inputs)
- Compare results với **py3gppchannels** library (same models)
- Spot-check với **Atoll** nếu có access
- **Shadow Fading**: verified against 3GPP TR 38.901 Table 7.4.2-1 sigma values × norm.ppf(coverage_probability)
  - UMa NLOS 95%: 13.2 dB (8.0 × 1.645)
  - UMi NLOS 95%: 12.9 dB (7.82 × 1.645)
  - RMa NLOS 95%: 13.2 dB (8.0 × 1.645)
  - InH NLOS 95%: 6.6 dB (4.0 × 1.645)
- **O2I Penetration**: currently fixed value (user input), 5g-tools.com uses frequency-dependent model (3GPP TR 38.901 §7.4.3)
- **EIRP**: rf5g includes beamforming gain (32T32R: +12 dB), 5g-tools.com does not — both valid approaches

### 6.4 Drag-and-Drop Map Validation

| Test | Expected Result | Status |
|------|----------------|--------|
| Generate interactive map with hex grid | Map loads, hexes visible | ✅ |
| Export sites as JSON (WGS84) | Valid JSON with lat/lon | ✅ |
| Export sites as CSV | Valid CSV with headers | ✅ |
| Import sites from JSON | Correct site count and positions | ✅ |
| Import sites from CSV | Correct site count and positions | ✅ |
| CLI sites count command | Correct site count | ✅ |
| CLI map --sites flag | Map with custom site positions | ✅ |
| API /sites/export endpoint | JSON response with WGS84 coords | ✅ |
| API /sites/map endpoint | HTML map with custom sites | ✅ |
| Haversine km↔lat/lon conversion | < 0.5% error at lat 10.8° | ✅ |

---

## 7. RISKS & MITIGATIONS

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| 3GPP model implementation bugs | Medium | High | Validate từng model vs spec values |
| Numerical inversion errors | Low | High | Use scipy.optimize.brentq, add fallback |
| py3gppchannels dependency breaks | Low | Medium | Vendor-copy critical models |
| Performance (large area, many scenarios) | Low | Medium | Cache propagation results, vectorize numpy |
| Web UI complexity | Medium | Low | Phase 3, use Streamlit (simple) |
| Accuracy vs commercial tools | High | Medium | Document ±10% disclaimer, add sensitivity analysis |

---

## 8. SUCCESS METRICS

| Metric | Target | Measurement |
|--------|--------|-------------|
| Accuracy vs 3GPP spec | ±0.5 dB path loss | Unit tests |
| Accuracy vs manual calculation | ±0.5 dB MAPL | Worked examples |
| Site count vs commercial tools | ±10% | Scenario comparison |
| Single scenario calculation time | < 1 second | Benchmark |
| CLI ease of use | 0-config quick start | User testing |
| Code coverage | ≥ 90% | pytest-cov |
| Documentation completeness | All functions documented | Review |

---

## 9. REFERENCES

| Document | Location |
|----------|----------|
| Phase 1 — RF Factors | `research/5g-rf-sizing/phase1-rf-factors.md` |
| Phase 2 — Tool Design | `research/5g-rf-sizing/phase2-tool-design.md` |
| Phase 3 — QoS & Capacity | `research/5g-rf-sizing/phase3-qos-capacity.md` |
| Final Report | `research/5g-rf-sizing/FINAL-REPORT.md` |
| 3GPP TR 38.901 | Propagation models |
| 3GPP TS 38.104 | BS radio transmission, band tables |
| 3GPP TS 38.101 | UE power classes |
| 3GPP TS 38.214 | MCS, CQI, TBS |
| 3GPP TS 38.306 | Throughput formula |
| 3GPP TS 23.501 | 5QI QoS mapping |
| ITU-R M.2410-0 | IMT-2020 requirements |

---

*PRD v1.0 — 2026-06-22 — Ready for review and implementation*