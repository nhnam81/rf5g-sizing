# 5G RF Coverage Sizing Tool — Comprehensive R&D Report

> **Final Report** | 2026-06-20
> Combines: Phase 1 (RF Factors) + Phase 2 (Tool Design) + Phase 3 (QoS & Capacity)
> Author: OpenClaw Agent Orchestrator

---

## EXECUTIVE SUMMARY

Báo cáo này trình bày thiết kế hoàn chỉnh cho công cụ **5G RF Coverage Sizing** — tính toán vùng phủ sóng, số trạm cần thiết, và kiểm tra QoS (Voice/Video/Data) dựa trên thông số đầu vào.

**3deliverables:**
1. `phase1-rf-factors.md` (13.6 KB) — Yếu tố kỹ thuật RF ảnh hưởng vùng phủ
2. `phase2-tool-design.md` (36.6 KB) — Khảo sát tools có sẵn + thiết kế architecture
3. `phase3-qos-capacity.md` (21.0 KB) — QoS requirements + capacity dimensioning

**Tổng cộng: ~71 KB tài liệu kỹ thuật.**

---

## 1. VẤN ĐỀ

Thiết kế công cụ giúp kỹ sư RF/Planning:
- Tính vùng phủ sóng 5G từ các thông số đầu vào
- Ước lượng số trạm phát (gNB) cần thiết
- Đảm bảo chất lượng dịch vụ (Voice, Video, Data)
- Hỗ trợ quyết chọn config (32T32R/8T8R, band, power...)

## 2. INPUT PARAMETERS

### 2.1 Coverage Parameters

| Parameter | Values | Source |
|-----------|--------|--------|
| Area (km²) | User input | Project |
| Environment | Dense urban / Urban / Suburban / Rural / Indoor | 3GPP TR 38.901 |
| BS antenna config | 32T32R, 16T16R, 8T8R, 4T4R, 2T2R | TS 38.104 |
| BS TX power/channel | 1W, 2W, 5W, 10W, 20W, 40W, 200W | TS 38.104 |
| Frequency band | n8, n28, n3, n41, n77, n78, n79, custom | TS 38.104 |
| BS antenna gain | 9–21 dBi (auto from config) | Lookup table |
| BS height | 10m (UMi), 25m (UMa), 35m (RMa) | Scenario default |
| UE Power Class | PC1, PC1.5, PC2, PC3, PC4 | TS 38.101 |
| UE antenna gain | 0 dBi (handset), 3–8 dBi (FWA/CPE) | Device spec |
| UE height | 1.5m default | Standard |
| Obstacle density | None / Light / Medium / Heavy | User input |

### 2.2 QoS Parameters (NEW — Phase 3)

| Parameter | Example Values | Impact |
|-----------|---------------|--------|
| Primary service | Voice / Video SD/HD/4K / Data / Gaming / Mixed | SINR target |
| Target DL per user | 1–300 Mbps | Capacity check |
| Target UL per user | 0.024–50 Mbps | Capacity check (UL bottleneck) |
| Max latency | 5–300 ms | Service viability |
| User density | 10–10,000 users/km² | Site count |
| Concurrent ratio | 5–30% | Active users |
| Coverage reliability | 90–99% | Shadow fading margin |
| Indoor coverage | Yes/No | Penetration loss |
| URLLC required | Yes/No | Special config |

## 3. CALCULATION METHODOLOGY

### 3.1 Coverage (Link Budget → Cell Radius)

```
Step 1: Calculate MAPL
  MAPL_DL = EIRP_BS + G_UE - RxSens_UE - Σ Margins
  MAPL_UL = EIRP_UE + G_BS - RxSens_BS - Σ Margins
  MAPL = min(MAPL_DL, MAPL_UL) = MAPL_UL  (UL-limited)

Step 2: Invert propagation model for cell radius
  PL(d) = MAPL → solve for d

Step 3: Site count
  N = Area / (2.598 × d²) × (1 + overlap)
```

### 3.2 Service Quality (SINR → MCS → Throughput)

```
Step 4: SINR at cell edge
  SINR_edge = Signal - Interference - Noise

Step 5: Map SINR → CQI → MCS → Spectral Efficiency
  (3GPP TS 38.214 Table 5.2.2.1-2)

Step 6: Throughput per cell
  TPUT = BW × SE × layers × (1-OH) × TDD_share

Step 7: QoS Check
  Voice: SINR ≥ -3 dB? → Pass/Fail
  Video HD: SINR ≥ 5 dB? → Service zone %
  Data: Cell capacity ≥ demand? → Pass/Fail
```

### 3.3 Capacity (Users → Additional Sites)

```
Step 8: Demand = N_users × TPUT_per_user × concurrent_ratio
Step 9: Supply = N_sites × sectors × cell_capacity
Step 10: If Demand > Supply → Add sites (capacity-limited)
```

## 4. KEY FINDINGS

### 4.1 UL luôn giới hạn
- UE TX power (23 dBm) vs BS TX power (53 dBm) → chênh 30 dB
- Cell radius = UL cell radius trong mọi trường hợp
- **Nâng cấp UE lên PC2 (+3 dB) → tăng radius 15–20%**

### 4.2 Antenna Config quan trọng hơn TX Power
- 32T32R vs 2T2R: +3.5 dB BF gain → radius +58%
- 200W vs 20W: +10 dB → radius +35% (UMa NLOS)
- **Đầu tư Massive MIMO mang lại ROI cao hơn là tăng công suất**

### 4.3 Capacity thường là bottleneck ở urban
- Dense urban: coverage → 121 sites, capacity → 144 sites (+19%)
- Nguyên nhân: nhiều users + throughput/user cao
- **Giải pháp: carrier aggregation, small cells, sector splitting**

### 4.4 Cell edge SERVICE ≠ CELL EDGE COVERAGE
- Coverage (min SINR = -6 dB): 100% area
- VoNR (SINR ≥ -3 dB): ~87% area
- Video HD (SINR ≥ 5 dB): ~47% area
- **Tool phải báo cả 2: coverage radius + service zones**

### 4.5 Tần số quyết định mọi thứ
| Band | Cell Radius (urban) | Sites/km² |
|------|--------------------|-----------| 
| n8 (900 MHz) | 1.5–2.5 km | 0.08–0.22 |
| n41 (2.6 GHz) | 0.8–1.5 km | 0.22–0.78 |
| n78 (3.5 GHz) | 0.3–0.7 km | 1.0–5.9 |
| mmWave (28 GHz) | 0.1–0.3 km | 5.4–48 |

→ **n78 cần gấp ~10 lần số site so với n8**

## 5. TOOL ARCHITECTURE (Khuyến nghị)

### 5.1 Technology Stack
- **Core**: Python 3.11+ (numpy, scipy)
- **Propagation models**: 3GPP TR 38.901 (UMa/UMi/RMa/InH/InF), FSPL, COST-231
- **CLI**: Typer
- **API**: FastAPI
- **Visualization**: Folium (Leaflet maps), Matplotlib (charts)
- **Templates**: Jinja2 (Markdown/HTML reports)

### 5.2 File Structure
```
rf_sizing_tool/
├── rf_sizing/
│   ├── models/
│   │   ├── propagation.py      # 3GPP 38.901 PL models
│   │   ├── link_budget.py      # DL/UL MAPL
│   │   ├── capacity.py          # Throughput, user count
│   │   ├── qos.py              # SINR→MCS→SE, service zones
│   │   └── site_count.py       # Hexagonal grid
│   ├── data/
│   │   ├── bands.py            # 5G NR band table
│   │   ├── ue_power.py         # Power Class table
│   │   ├── antenna_config.py   # Config → gain mapping
│   │   ├── mcs_table.py        # MCS/CQI/SINR tables
│   │   └── qos_profiles.py     # Service → KPI mapping
│   ├── core.py                 # Main pipeline
│   └── schema.py               # Pydantic I/O schemas
├── tests/
├── examples/
├── cli.py
└── pyproject.toml
```

### 5.3 Calculation Pipeline
```
Input JSON → Validate → Link Budget → Propagation Model → Cell Radius
                                                          ↓
                                                    SINR at Edge
                                                          ↓
                                                    MCS / CQI / SE
                                                          ↓
                                                    Cell Capacity
                                                          ↓
                                                    QoS Check
                                                          ↓
                                                    Capacity Check
                                                          ↓
                                              Output JSON + Map + Report
```

### 5.4 Example Output
```json
{
  "coverage": {
    "cell_radius_km": 0.446,
    "limiting_link": "UL",
    "n_sites_coverage": 121
  },
  "qos": {
    "voice": {"pass": true, "sinr_edge_db": -2.0},
    "video_hd": {"pass": false, "service_area_pct": 47},
    "data_50mbps": {"pass": false, "deficit_pct": 16}
  },
  "capacity": {
    "n_sites_required": 144,
    "limiting_factor": "capacity_dl"
  },
  "recommendations": [
    "Increase to 144 sites for DL capacity",
    "Carrier aggregation recommended",
    "Upgrade UEs to Power Class 2"
  ]
}
```

## 6. IMPLEMENTATION ROADMAP

| Phase | Duration | Deliverables |
|-------|----------|-------------|
| **MVP Core** | 2–3 weeks | Propagation models, link budget, site count, CLI |
| **QoS + Capacity** | 1–2 weeks | SINR→MCS mapping, throughput, QoS check, capacity dimensioning |
| **Visualization** | 2 weeks | Folium coverage map, service zone overlay, charts |
| **Web API** | 2–3 weeks | FastAPI backend, web form UI, interactive map |
| **Advanced** | Ongoing | InH/InF models, terrain (SRTM), capacity simulation, export |

**Total MVP: 4–5 weeks** (coverage + QoS + capacity + CLI)

## 7. COMPETITIVE ANALYSIS

| Tool | Type | Coverage | QoS | Capacity | Open-source | Vietnam-use |
|------|------|----------|-----|----------|-------------|-------------|
| **This tool** | Open | ✅ | ✅ | ✅ | ✅ | ✅ |
| Atoll | Commercial | ✅ | ✅ | ✅ | ❌ | Some operators |
| CelPlanner | Commercial | ✅ | Partial | ✅ | ❌ | Rare |
| 5g-tools.com | Web free | ✅ | ❌ | ❌ | ❌ | Reference |
| srsRAN | Open | ❌ | ❌ | ❌ | ✅ | Research only |

**Gap**: Không có open-source tool nào làm đầy đủ workflow Coverage → QoS → Capacity → Recommendation.

## 8. CONCLUSION

Tool 5G RF Coverage Sizing được thiết kế với:

1. **Coverage engine**: Link budget + 3GPP TR 38.901 propagation models → cell radius → site count
2. **QoS engine** (MỚI): SINR → MCS → throughput mapping, kiểm tra Voice/Video/Data/Gaming requirements
3. **Capacity engine** (MỚI): User density × throughput demand → capacity check → additional sites if needed
4. **Recommendation engine**: Rule-based suggestions cho config changes

**Key insight**: Coverage alone là không đủ. Tool phải tính cả **capacity** và **QoS** để đảm bảo trải nghiệm người dùng thực tế. Một vùng phủ sóng "đủ" về signal có thể không đủ throughput cho Video HD hoặc Cloud Gaming.

---

*Report date: 2026-06-20*
*Total research: 71 KB across 3 phase documents*
*Standards: 3GPP Release 16 (TR 38.901, TS 38.104/214/306/23.501), ITU-R M.2410-0*
