# 📡 5G NR RF Coverage Sizing Tool — Hướng dẫn sử dụng

> Phiên bản 1.2 | 3GPP TR 38.901 V16.1.0 | TS 38.104, 38.214, 38.306
>
> **v1.2 cập nhật:** streamlit-folium rendering, Manual sector input (lat,lon,azimuth,beamwidth), Radio/Antenna catalog dropdown, Capacity sites map, Area verification, Sector directionality warning

---

## 📑 Mục lục

1. [Cài đặt](#1-cài-đặt)
2. [Sử dụng CLI](#2-sử-dụng-cli)
3. [File cấu hình JSON](#3-file-cấu-hình-json)
4. [Sử dụng FastAPI Server](#4-sử-dụng-fastapi-server)
5. [Sử dụng Streamlit Web UI](#5-sử-dụng-streamlit-web-ui)
6. [Giải thích kết quả](#6-giải-thích-kết-quả)
7. [Các kịch bản mẫu](#7-các-kịch-bản-mẫu)
8. [Tham số kỹ thuật](#8-tham-số-kỹ-thuật)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Cài đặt

### Yêu cầu
- Python 3.10+
- pip

### Cài đặt dependencies

```bash
cd research/5g-rf-sizing
pip install -e .
```

Hoặc cài đặt thủ công:

```bash
pip install pydantic scipy numpy matplotlib folium jinja2 typer rich fastapi uvicorn streamlit
```

### Kiểm tra cài đặt

```bash
python -m rf5g.cli tables
```

Nếu thấy bảng NR bands → cài đặt OK.

---

## 2. Sử dụng CLI

### 2.1 Tính toán sizing (lệnh chính)

```bash
# Sử dụng config file (khuyến nghị)
python -m rf5g.cli size --config examples/dense_urban_n78.json

# Quick sizing với tham số tùy chỉnh
python -m rf5g.cli size --area 50 --scenario UMa --band n78 --bandwidth 100 --power 200

# Xuất kết quả JSON
python -m rf5g.cli size --config examples/dense_urban_n78.json --output result.json
```

**Kết quả hiển thị:**
- Link Budget (DL/UL MAPL, EIRP, Sensitivity)
- Coverage Estimate (Cell Radius, Sites, ISD)
- SINR & Modulation (CQI, MCS, Spectral Efficiency)
- Capacity (Throughput, Demand vs Supply)
- QoS Verification (6 service types pass/fail)
- Recommendations (hàng động đề xuất)

### 2.2 Tạo coverage map (interactive, drag-and-drop)

```bash
# Map mặc định (HCMC center) — interactive với drag-and-drop sites
python -m rf5g.cli map --config examples/dense_urban_n78.json --output coverage.html

# Tùy chỉnh vị trí bản đồ
python -m rf5g.cli map --config examples/dense_urban_n78.json --lat 21.03 --lon 105.85 --zoom 11

# Import custom sites (JSON hoặc CSV, WGS84)
python -m rf5g.cli map --config examples/dense_urban_n78.json --sites my_sites.json --output custom_map.html

# Quick map
python -m rf5g.cli map --area 50 --scenario UMa --band n78 --output my_map.html
```

**Kết quả:** File HTML interactive với Leaflet/Folium, có thể:
- **Kéo thả site markers** để đổi vị trí → tự vẽ lại coverage hex
- **Xóa site** qua popup "Delete Site"
- **Xem chi tiết** mỗi site (lat/lon, radius, SINR, path loss)
- **Export sites** từ browser (JSON hoặc CSV, WGS84)
- **Sidebar** hiển thị danh sách sites
- **Hệ tọa độ:** WGS84 (EPSG:4326) — tương thích Google Maps, KML, GeoJSON
- **Haversine** cho distance calculation chính xác ở mọi vĩ độ
- **Directional antenna patterns** — Omni, Panel 120°/65°/90°, BF 30°/60°
- **Per-sector coverage** — 3-sector (120°), 6-sector (60°), omni
- **Atoll/CSV/JSON antenna import** — dùng datasheet thực tế thay vì built-in

### 2.2.1 Antenna Patterns (Mẫu phát sóng anten)

**Built-in patterns (tự động map theo antenna config):**

| Antenna Config | Pattern | Beamwidth | Gain | Mô tả |
|---|---|---|---|---|
| 2T2R | Omni | 360° | 2 dBi | Đẳng hướng (repeater/small cell) |
| 4T4R | Panel 120° | 120° | 17 dBi | 3-sector macro |
| 8T8R | Panel 120° | 120° | 17 dBi | 3-sector macro |
| 16T16R | Panel 65° | 65° | 20 dBi | 6-sector / high-gain |
| 32T32R | BF 60° | 60° | 22 dBi | SU-MIMO |
| 64T64R | BF 30° | 30° | 25 dBi | MU-MIMO |

**Import custom antenna pattern:**
```bash
# Atoll .ant file
rf5g map --config scenario.json --antenna-pattern /path/to/Kathrein_80010554.ant

# CSV (azimuth,gain_db columns)
rf5g map --config scenario.json --antenna-pattern /path/to/pattern.csv

# JSON (full pattern definition)
rf5g map --config scenario.json --antenna-pattern /path/to/pattern.json
```

**JSON pattern format:**
```json
{
    "name": "Custom_5G",
    "frequency_mhz": 3500,
    "gain_max_dbi": 18.5,
    "beamwidth_h_deg": 65,
    "beamwidth_v_deg": 10,
    "front_to_back_db": 30,
    "tilt_deg": 6,
    "horizontal_pattern": {"0": 0.0, "1": -0.1, ...},
    "vertical_pattern": {"-10": -3.0, ...}
}
```

### 2.2.1 Quản lý sites (CLI)

```bash
# Xuất sites ra JSON (WGS84)
python -m rf5g.cli sites export-json --config examples/dense_urban_n78.json --output sites.json

# Xuất sites ra CSV
python -m rf5g.cli sites export-csv --config examples/dense_urban_n78.json --output sites.csv

# Import sites từ file
python -m rf5g.cli sites import --sites-file sites.json

# Xem số sites ước tính
python -m rf5g.cli sites count --config examples/dense_urban_n78.json
```

**Định dạng sites.json:**
```json
{
  "coordinate_system": "WGS84 (EPSG:4326)",
  "total_sites": 200,
  "metadata": { "project": "Dense Urban n78", "cell_radius_m": 119 },
  "sites": [
    {"site_id": 1, "latitude": 10.780000, "longitude": 106.700000},
    {"site_id": 2, "latitude": 10.780000, "longitude": 106.701893}
  ]
}
```

### 2.3 Tạo báo cáo

```bash
# HTML report (có styling, bảng biểu)
python -m rf5g.cli report --config examples/dense_urban_n78.json --format html

# Markdown report (plain text)
python -m rf5g.cli report --config examples/dense_urban_n78.json --format md

# Tùy chỉnh output path
python -m rf5g.cli report --config examples/dense_urban_n78.json --format html --output my_report.html
```

### 2.4 Tạo biểu đồ

```bash
python -m rf5g.cli charts --config examples/dense_urban_n78.json

# Tùy chỉnh thư mục output
python -m rf5g.cli charts --config examples/dense_urban_n78.json --output-dir ./reports/
```

**4 biểu đồ được tạo:**
1. `link_budget_*.png` — DL/UL waterfall chart
2. `sinr_heatmap_*.png` — SINR vs distance
3. `service_zones_*.png` — QoS pie + coverage bar
4. `capacity_*.png` — Capacity vs demand bar

### 2.5 Xem bảng tham chiếu

```bash
python -m rf5g.cli tables
```

Hiển thị: NR Bands, NRB values, Power Classes, Antenna Configs, SINR-CQI table.

---

## 3. File cấu hình JSON

### 3.1 Cấu trúc đầy đủ

```json
{
  "project": {
    "name": "Dense Urban n78",
    "area_km2": 50.0,
    "center_lat": 10.8231,
    "center_lon": 106.6297
  },
  "environment": {
    "scenario": "UMa",
    "obstacle_density": "heavy",
    "coverage_probability": 0.95
  },
  "base_station": {
    "tx_power_w": 200.0,
    "antenna_config": "32T32R",
    "height_m": 25.0,
    "sectors": 3,
    "cable_loss_db": 1.0,
    "noise_figure_db": 3.5
  },
  "frequency": {
    "band": "n78",
    "bandwidth_mhz": 100.0,
    "scs_khz": 30,
    "tdd_dl_ratio": 0.70
  },
  "user_equipment": {
    "power_class": "PC3",
    "height_m": 1.5,
    "noise_figure_db": 7.0
  },
  "margins": {
    "interference_db": 3.0,
    "penetration_db": 10.0,
    "rain_attenuation_db": 1.0,
    "overlap_factor": 0.25
  },
  "qos": {
    "primary_service": "mixed",
    "users_per_km2": 300.0,
    "dl_per_user_mbps": 20.0,
    "ul_per_user_mbps": 5.0,
    "concurrent_ratio": 0.10
  }
}
```

### 3.2 Tham số quan trọng

| Tham số | Mặc định | Giải thích |
|---|---|---|
| `scenario` | "UMa" | UMa (Urban Macro), UMi (Urban Micro), RMa (Rural Macro), InH (Indoor) |
| `obstacle_density` | "heavy" | heavy (dense urban), medium (suburban), light (rural) |
| `band` | "n78" | NR band: n78, n77, n41, n1, n3, n8, n28, n25, n71 |
| `bandwidth_mhz` | 100.0 | Channel bandwidth (5-400 MHz tùy band) |
| `tx_power_w` | 200.0 | BS TX power (W) |
| `antenna_config` | "32T32R" | 2T2R, 4T4R, 8T8R, 16T16R, 32T32R, 64T64R |
| `primary_service` | "mixed" | vonr, video_hd, video_4k, data, gaming, iot, mixed |
| `tdd_dl_ratio` | 0.70 | TDD DL ratio (0.5-0.9) |

### 3.3 Quick override

Không cần JSON file, có thể dùng CLI parameters:

```bash
python -m rf5g.cli size --area 100 --scenario RMa --band n8 --bandwidth 10 --power 40
```

---

## 4. Sử dụng FastAPI Server

### 4.1 Khởi động server

```bash
cd research/5g-rf-sizing
uvicorn rf5g.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Mở Swagger UI: `http://localhost:8000/docs`

### 4.2 API Endpoints

#### POST /size — Full sizing

```bash
curl -X POST http://localhost:8000/size \
  -H "Content-Type: application/json" \
  -d '{"project": {"name": "Test", "area_km2": 50}, "environment": {"scenario": "UMa"}, "frequency": {"band": "n78", "bandwidth_mhz": 100}}'
```

#### POST /size/quick — Quick sizing

```bash
curl -X POST "http://localhost:8000/size/quick?area_km2=50&scenario=UMa&band=n78&bandwidth_mhz=100&tx_power_w=200"
```

#### POST /compare — So sánh nhiều kịch bản

```bash
curl -X POST http://localhost:8000/compare \
  -H "Content-Type: application/json" \
  -d '{
    "scenarios": [
      {"project": {"name": "Urban", "area_km2": 50}, "environment": {"scenario": "UMa"}},
      {"project": {"name": "Rural", "area_km2": 500}, "environment": {"scenario": "RMa"}}
    ]
  }'
```

#### POST /map — Tạo coverage map

```bash
curl -X POST http://localhost:8000/map \
  -H "Content-Type: application/json" \
  -d '{"project": {"area_km2": 50}, "environment": {"scenario": "UMa"}}' \
  --output coverage.html
```

#### POST /report/html — HTML report

```bash
curl -X POST http://localhost:8000/report/html \
  -H "Content-Type: application/json" \
  -d '{"project": {"area_km2": 50}}' \
  --output report.html
```

#### GET /tables/bands — Danh sách NR bands

```bash
curl http://localhost:8000/tables/bands
```

#### GET /tables/bands/n78 — Chi tiết band n78

```bash
curl http://localhost:8000/tables/bands/n78
```

### 4.3 Response Format

Mọi `/size` response đều trả về `SizingOutput` JSON đầy đủ:

```json
{
  "project_name": "Dense Urban n78",
  "environment": "UMa",
  "band": "n78",
  "bandwidth_mhz": 100.0,
  "tx_power_w": 200.0,
  "antenna_config": "32T32R",
  "link_budget_dl": { "eirp_dbm": 84.0, "rx_sensitivity_dbm": -93.0, "mapl_db": 158.7, ... },
  "link_budget_ul": { "eirp_dbm": 23.0, "rx_sensitivity_dbm": -96.5, "mapl_db": 133.2, ... },
  "propagation": { "model": "UMa_NLOS", "path_loss_db": 133.2, "cell_radius_m": 222.3, "cell_radius_km": 0.222, ... },
  "site_estimate": { "coverage_sites": 488, "isd_km": 0.385, "limiting_link": "UL", ... },
  "sinr": { "sinr_db": -3.0, "cqi": 3, "modulation": "QPSK", "spectral_efficiency_bps_hz": 0.49, ... },
  "capacity": { "cell_throughput_dl_mbps": 160.2, "total_capacity_dl_gbps": 78.2, "capacity_sufficient": true, ... },
  "qos_verification": [ { "service": "VoNR", "sinr_required_db": -3, "sinr_available_db": -3.0, "area_percentage": 50.0, "passed": true }, ... ],
  "recommendations": ["UL is limiting...", "Consider upgrading UE to PC2...", ...]
}
```

---

## 5. Sử dụng Streamlit Web UI

### 5.1 Khởi động

```bash
cd research/5g-rf-sizing
streamlit run rf5g/web/app.py
```

Mở trình duyệt: `http://localhost:8501`

### 5.2 Cách sử dụng

1. **Sidebar trái**: Cấu hình tham số
   - Project: tên, diện tích, tọa độ
   - Environment: scenario, obstacle density, coverage probability
   - Base Station: TX power, antenna config, height, sectors
   - Frequency: band, bandwidth, SCS, TDD ratio
   - UE: power class, height, noise figure
   - Margins: interference, penetration, rain, overlap
   - QoS: primary service, users/km², per-user throughput

2. **Nhấn "🚀 Calculate"** → kết quả hiện ở 9 tabs:

| Tab | Nội dung |
|---|---|
| **Overview** | Tóm tắt chính: Cell Radius, Sites, MAPL, SINR, Capacity |
| **Link Budget** | Bảng DL/UL chi tiết |
| **Coverage** | Cell radius, ISD, LOS probability, sites |
| **SINR** | CQI, modulation, spectral efficiency |
| **Capacity** | Throughput, demand vs supply |
| **QoS** | 6 service types pass/fail |
| **Recommendations** | Hành động đề xuất |
| **Map** | Folium interactive map |
| **Charts** | 4 biểu đồ (link budget, SINR, service zones, capacity) |

3. **Upload JSON config**: Nút upload ở sidebar để load file config có sẵn

4. **Download**: 
   - JSON result (nút trong tab Overview)
   - HTML report (nút trong tab Overview)

---

## 6. Giải thích kết quả

### 6.1 Link Budget

| Metric | Ý nghĩa |
|---|---|
| **EIRP** | Effective Isotropic Radiated Power — tổng công suất phát + antenna gain |
| **Rx Sensitivity** | Ngưỡng nhạy thu — công suất tối thiểu UE/gNB có thể nhận |
| **MAPL** | Maximum Allowable Path Loss — path loss tối đa để duy trì kết nối |
| **UL limiting** | UL MAPL < DL MAPL → uplink là bottleneck |

**MAPL cao hơn = cell radius lớn hơn = ít sites hơn.** UL thường limiting vì UE power (23 dBm) << BS power (43 dBm).

### 6.2 Cell Radius & Sites

- **Cell Radius**: Khoảng cách từ BS đến cell edge, tính bằng MAPL inversion (scipy brentq)
- **ISD**: Inter-Site Distance = √3 × R (hexagonal grid)
- **Sites**: Diện tích / cell_area × sectors, làm tròn lên

### 6.3 SINR & Modulation

| SINR Range | CQI | Modulation | SE (bps/Hz) |
|---|---|---|---|
| < -6.9 dB | 1 | QPSK | 0.15 |
| -3.0 dB | 3 | QPSK | 0.49 |
| 5.0 dB | 7 | 16QAM | 1.48 |
| 10.0 dB | 10 | 64QAM | 2.73 |
| 15.0 dB | 13 | 256QAM | 4.52 |
| > 20 dB | 15 | 256QAM | 5.55 |

### 6.4 Capacity

- **Cell Throughput**: Bandwidth × SE × layers × TDD ratio × overhead
- **Total Capacity**: Cell throughput × total sites
- **Total Demand**: users/km² × area × concurrent_ratio × per_user_mbps
- **Capacity Sufficient**: YES nếu Total Capacity ≥ Total Demand

### 6.5 QoS Verification

6 service types được kiểm tra:

| Service | SINR Threshold | Bài toán |
|---|---|---|
| **VoNR** | -3 dB | Voice over NR — thấp nhất, dễ pass nhất |
| **IoT** | -5 dB | IoT sensors — dễ nhất |
| **Data** | 0 dB | Basic data |
| **Video HD** | 5 dB | HD video streaming |
| **Gaming** | 8 dB | Low-latency gaming |
| **Video 4K** | 10 dB | 4K video — cao nhất, khó nhất |

### 6.6 Recommendations

Hệ thống tự động đề xuất dựa trên:
- UL limiting → nâng UE power class (PC2), UL CA
- Dense urban → small cells, 8T8R/16T16R
- SINR thấp → nâng antenna, thêm sites
- Capacity thiếu → thêm sites, mở bandwidth
- Band-specific (n8 narrowband, n78 wideband)

---

## 7. Các kịch bản mẫu

### 7.1 Dense Urban n78 ( Thành phố )

```bash
python -m rf5g.cli size --config examples/dense_urban_n78.json
```

**Kết quả dự kiến:**
- Cell radius: ~222m, 488 sites
- SINR: -3.0 dB (CQI 3, QPSK)
- Capacity: SUFFICIENT (78.2 Gbps vs 30.0 Gbps demand)
- UL limiting, VoNR ✅, Data ❌

### 7.2 Suburban n77 ( Ngoại ô )

```bash
python -m rf5g.cli size --config examples/suburban_n77.json
```

**Kết quả dự kiến:**
- Cell radius: ~255m, 1,424 sites
- Capacity: SUFFICIENT (111.2 Gbps vs 24.0 Gbps)

### 7.3 Rural n8 ( Nông thôn )

```bash
python -m rf5g.cli size --config examples/rural_n8.json
```

**Kết quả dự kiến:**
- Cell radius: ~14.6km, 2 sites (coverage)
- Capacity: INSUFFICIENT (0.03 Gbps vs 5.0 Gbps)
- → Nhiều sites hơn cần cho capacity

---

## 8. Tham số kỹ thuật

### 8.1 Propagation Models (3GPP TR 38.901)

| Scenario | LOS | NLOS | Combined |
|---|---|---|---|
| **UMa** (Urban Macro) | Table 7.4.1-1 | Table 7.4.1-1 | P_LOS weighted |
| **UMi** (Urban Micro) | Table 7.4.1-1 | Table 7.4.1-1 | P_LOS weighted |
| **RMa** (Rural Macro) | Table 7.4.1-1 | Table 7.4.1-1 | P_LOS weighted |
| **InH** (Indoor) | Table 7.4.1-1 | Table 7.4.1-1 | P_LOS weighted |

**LOS Probability**: Per Table 7.4.2-1 (3GPP TR 38.901 V16.1.0)

**Breakpoint Distance**: UMa `4 * h_BS * h_UT * fc / c`, UMi `4 * h_BS * h_UT * fc / c`, RMa `2 * pi * h_BS * h_UT * fc / c`

### 8.2 NR Bands Supported

| Band | fc (MHz) | Max BW (MHz) | Common Use |
|---|---|---|---|
| n1 | 2120 | 20 | Low-band urban |
| n3 | 1815 | 30 | Low-band urban |
| n8 | 900 | 10 | Rural coverage |
| n25 | 1850 | 20 | US low-band |
| n28 | 710 | 20 | Low-band coverage |
| n41 | 2595 | 100 | TDD mid-band |
| n77 | 3300 | 100 | TDD mid-band |
| n78 | 3500 | 100 | TDD mid-band |
| n71 | 625 | 20 | US low-band |

### 8.3 SINR-CQI Mapping (3GPP TS 38.214)

Linear interpolation giữa 15 CQI entries. CQI 1 = QPSK (SE 0.15), CQI 15 = 256QAM (SE 5.55).

### 8.4 QoS Service Types

| Service | SINR Threshold | Latency | Use Case |
|---|---|---|---|
| VoNR | -3 dB | <100ms | Voice calls |
| IoT | -5 dB | <1s | Sensor data |
| Data | 0 dB | <50ms | Basic internet |
| Video HD | 5 dB | <30ms | HD streaming |
| Gaming | 8 dB | <10ms | Real-time gaming |
| Video 4K | 10 dB | <20ms | 4K streaming |

---

## 9. Troubleshooting

### Lỗi "ModuleNotFoundError"

```bash
# Đảm bảo cài đặt package
cd research/5g-rf-sizing
pip install -e .
```

### Lỗi "Band nXX not found"

Band phải là string: `"n78"` (không phải `78`). Kiểm tra bands.json cho supported bands.

### Lỗi "Scenario must be UMa/UMi/RMa/InH"

Scenario chỉ chấp nhận 4 giá trị: `UMa`, `UMi`, `RMa`, `InH` (case-sensitive).

### Kết quả không hợp lý

1. **Sites quá nhiều**: UL limiting → tăng UE power class hoặc giảm area
2. **Capacity insufficient**: Tăng bandwidth hoặc thêm sites
3. **SINR rất thấp**: Thay antenna config cao hơn (64T64R) hoặc giảm ISD
4. **Cell radius quá lớn/nhỏ**: Kiểm tra obstacle_density (heavy cho urban, light cho rural)

### FastAPI không start

```bash
# Kiểm tra port 8000 có bị占用
netstat -an | findstr 8000

# Hoặc dùng port khác
uvicorn rf5g.api.app:app --host 0.0.0.0 --port 8001
```

### Streamlit không start

```bash
# Đảm bảo PYTHONPATH đúng
cd research/5g-rf-sizing
streamlit run rf5g/web/app.py

# Hoặc set PYTHONPATH
$env:PYTHONPATH="."; streamlit run rf5g/web/app.py
```

---

## 📁 Cấu trúc thư mục

```
5g-rf-sizing/
├── PRD.md                          # Product Requirements Document
├── pyproject.toml                  # Package config
├── examples/                       # 3 sample configs
│   ├── dense_urban_n78.json
│   ├── suburban_n77.json
│   └── rural_n8.json
├── rf5g/
│   ├── __init__.py
│   ├── cli.py                      # CLI (6 commands: size, map, report, charts, tables, sites)
│   ├── api/
│   │   ├── __init__.py
│   │   └── app.py                  # FastAPI (16 endpoints + sites/map + sites/export)
│   ├── web/
│   │   ├── __init__.py
│   │   ├── app.py                  # Streamlit Basic Mode
│   │   └── guided.py               # Streamlit Guided Mode (Vietnamese)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── input_schema.py         # Pydantic input model
│   │   ├── output_schema.py        # Pydantic output model
│   │   └── lookup_tables.py        # 6 lookup tables
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── propagation.py          # 3GPP TR 38.901
│   │   ├── link_budget.py          # DL/UL MAPL
│   │   ├── site_estimator.py       # Hexagonal grid
│   │   ├── sinr_mapper.py          # SINR→CQI→MCS→SE
│   │   ├── capacity.py             # Cell throughput
│   │   ├── qos_verifier.py         # QoS verification
│   │   └── recommender.py          # Recommendations
│   ├── viz/
│   │   ├── __init__.py
│   │   ├── coverage_map.py         # Folium map (drag-and-drop, WGS84, haversine)
│   │   ├── charts.py               # 4 Matplotlib charts
│   │   └── report.py               # HTML + Markdown reports
│   ├── data/                        # 6 JSON lookup tables
│   │   ├── bands.json
│   │   ├── power_classes.json
│   │   ├── antenna_configs.json
│   │   ├── sinr_cqi_table.json
│   │   ├── qos_requirements.json
│   │   └── shadow_fading.json
│   └── tests/                        # 84 unit tests
│       ├── test_propagation.py      # Phase 1 (30 tests)
│       ├── test_phase2.py           # Phase 2 (28 tests)
│       ├── test_phase3.py           # Phase 3 (10 tests)
│       ├── test_phase4.py           # Phase 4 (16 tests)
│       └── test_integration.py      # Integration (9 tests)
├── verify_prd_full.py              # PRD verification (102 checks)
└── verify_phase4.py                # Phase 4 verification (35 checks)
```

---

### 5.2 Guided Mode (Giao diện hướng dẫn)

```bash
streamlit run rf5g/web/guided.py
```

**Khác biệt so với Web UI cơ bản:**
- 5 kịch bản mẫu có mô tả chi tiết (Dense Urban, Suburban, Rural, Indoor, n41)
- Mỗi tham số có giải thích tiếng Việt đầy đủ (hover `help=`)
- 4 bước rõ ràng: Chọn → Tùy chỉnh → Tính toán → Xem kết quả
- Giải thích ý nghĩa kết quả (MAPL, SINR, QoS, Recommendations)
- Export: JSON, HTML Report, Markdown, Config JSON

**5 Kịch bản mẫu:**

| Kịch bản | Mô tả |
|---|---|
| 🏙️ Dense Urban n78 | Thành phố mật độ cao, 100 MHz, 32T32R |
| 🏘️ Suburban n77 | Ngoại ô/khu đô thị mới, 50 MHz, 8T8R |
| 🌾 Rural n8 | Nông thôn/ĐBSCL, 10 MHz, 4T4R |
| 🏢 Indoor InH n78 | Tòa nhà/trung tâm thương mại |
| 📶 Urban n41 | TDD mid-band (Mỹ), 80 MHz, 64T64R |

### 5.3 Tính năng nâng cao (v1.2)

#### Radio/Antenna Catalog Dropdown

Sidebar có dropdown chọn Radio và Antenna từ catalog (5 radios, 9 antennas):
- **Radio**: Ericsson Radio 4415/8883, Prose 2TR, 2W2TC, SWave 0640
- **Antenna**: Ericsson KRE 2405/9011, Prose SWave 40D/0640, v.v.
- Khi chọn catalog → tự động override TX power, antenna gain, beamwidth, MIMO config

#### Nhập site thủ công (Manual Site Input)

Trong tab Map, ô text cho phép nhập site thủ công:

```
# Chỉ lat, lon (dùng config chung cho sector)
10.782000, 106.700000

# Đầy đủ: lat, lon, azimuth, beamwidth
10.782000, 106.700000, 0, 65
10.785000, 106.705000, 120, 65
10.780000, 106.695000, 240, 65
```

- **Azimuth**: hướng góc phủ (0°=Bắc, 90°=Đông, 180°=Nam)
- **Beamwidth**: độ rộng tia (65° cho antenna 65°, 90° cho antenna 90°)
- Site có azimuth+beamwidth → vẽ sector wedge (tím)
- Site không có azimuth → dùng config chung (omni/3-sector)
- Độ chính xác: 6 chữ số thập phân (~0.1m)

#### Map views

3 chế độ xem bản đồ:
1. **Coverage Sites** — sites phủ sóng (hex grid hoặc thủ công)
2. **Capacity Sites** — sites theo dung lượng
3. **Comparison** — so sánh coverage vs capacity overlay

#### Sector directionality warning

Khi chọn antenna sector (beamwidth < 360°) và sectors=1:
- Tool cảnh báo: "Mỗi site chỉ phủ {beamwidth}° — KHÔNG phải 360°"
- Vẽ sector wedge màu tím cho directional coverage

### 5.4 Khắc phục sự cố

| Lỗi | Nguyên nhân | Khắc phục |
|---|---|---|
| Bản đồ trắng/blank | streamlit-folium chưa cài | `pip install streamlit-folium` |
| Map không full-width | width parameter | Dùng `st_folium(fmap, width=None, height=600)` |
| Sector vẽ thành hình tròn | horizontal_pattern rỗng | Dùng `_cosine_pattern(beamwidth, gain)` |
| AntennaPattern error | thiếu `name` argument | Truyền `name="manual"` vào constructor |

---

*Hướng dẫn này dành cho rf5g v1.2.0 — 5G NR RF Coverage Sizing Tool (3GPP TR 38.901 V16.1.0)*