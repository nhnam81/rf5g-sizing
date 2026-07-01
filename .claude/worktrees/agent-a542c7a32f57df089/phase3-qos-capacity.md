# 5G RF Coverage Sizing — Phase 3: Capacity Dimensioning & QoS

> Bổ sung throughput, QoS requirements cho Voice/Video/Data
> Standards: 3GPP TS 38.306, TS 38.214, TS 23.501, ITU-R M.2410-0 (IMT-2020)
> Date: 2026-06-20

---

## 1. CÔNG THỨC TÍNH THROUGHPUT 5G NR

### 1.1 Công thức chính (3GPP TS 38.306 §4.1.2)

```
Throughput = N_RB × 12 × Qm × f0 × R × (1 − OH) × Symbols_per_slot × Slots_per_second × N_layers    [bps]
```

**Trong đó:**

| Thông số | Ý nghĩa | Giá trị điển hình |
|----------|---------|-------------------|
| N_RB | Số Resource Blocks | Phụ thuộc BW + SCS (xem §1.2) |
| 12 | Số subcarriers/RB | 12 (cố định) |
| Qm | Modulation order (bits/symbol) | 2 (QPSK), 4 (16QAM), 6 (64QAM), 8 (256QAM) |
| f0 | Scaling factor | 1 (full buffer), 0.8 (typical) |
| R | Code rate | 0.12–0.93 (phụ thuộc MCS) |
| OH | Overhead (control/reference signals) | DL: 0.14, UL: 0.08 |
| Symbols_per_slot | 12–14 (14 bình thường, giảm nếu DMRS) | 12 (có DMRS), 14 (không) |
| Slots_per_second | Phụ thuộc SCS | 1000 (15kHz), 2000 (30kHz), 4000 (60kHz) |
| N_layers | MIMO layers | 1–4 (DL), 1–2 (UL) |

### 1.2 Bandwidth → N_RB Mapping (3GPP TS 38.104)

| BW (MHz) | SCS 15kHz | SCS 30kHz | SCS 60kHz |
|----------|-----------|-----------|-----------|
| 5 | 25 | 11 | — |
| 10 | 52 | 24 | 11 |
| 15 | 79 | 36 | 18 |
| 20 | 106 | 51 | 24 |
| 40 | 216 | 106 | 51 |
| 50 | 270 | 133 | 65 |
| **100** | **273** | — | — |

> Lưu ý: 100 MHz chỉ dùng được ở n77/n78/n41 (TDD) với SCS 30kHz → N_RB = 273

### 1.3 TDD Duplex Share

| TDD Pattern | DL:UL | DL share | UL share |
|-------------|-------|----------|----------|
| DDDSUDDSUU | 7:3 | 70% | 30% |
| DDDSU | 8:2 | 80% | 20% |
| DSU | 2:1 | 67% | 33% |
| DDDSUDDDSD | 8:1:1 | 80% | 10% |

**TDD throughput thực tế:**
```
Throughput_DL_actual = Throughput_DL × DL_share
Throughput_UL_actual = Throughput_UL × UL_share
```

### 1.4 Ví dụ tính throughput

**n78, 100 MHz, SCS 30kHz, 256QAM DL, 4 layers, code rate 0.8, OH=0.14:**
```
N_RB = 273
Symbols = 12 (with DMRS)
Slots/s = 2000 (30kHz)

DL_max = 273 × 12 × 8 × 1 × 0.8 × (1-0.14) × 12 × 2000 × 4
       = 273 × 12 × 8 × 0.8 × 0.86 × 12 × 2000 × 4
       = 273 × 12 × 8 × 0.8 × 0.86 × 12 × 8000
       = 1,717,858,304 bps ≈ 1.72 Gbps (TDD full-dl)

Với TDD 7:3: 1.72 × 0.7 ≈ 1.20 Gbps
```

**n78, 100 MHz, UL, 64QAM, 2 layers, code rate 0.6, OH=0.08:**
```
UL_max = 273 × 12 × 6 × 1 × 0.6 × (1-0.08) × 12 × 2000 × 2
       = 273 × 12 × 6 × 0.6 × 0.92 × 12 × 4000
       = 522,048,000 bps ≈ 522 Mbps (TDD full-ul)

Với TDD 7:3: 522 × 0.3 ≈ 157 Mbps
```

---

## 2. SINR → MCS → SPECTRAL EFFICIENCY MAPPING

### 2.1 SINR Threshold → Modulation (3GPP TS 38.214)

| SINR Range (dB) | Modulation | MCS Index | Code Rate | Spectral Eff (bps/Hz) | MIMO Layers |
|-----------------|-----------|-----------|-----------|----------------------|-------------|
| < -6 | — | No connection | — | 0 | — |
| -6 đến -3 | QPSK | 0–5 | 0.12–0.25 | 0.25–0.50 | 1 |
| -3 đến 1 | QPSK | 6–10 | 0.30–0.44 | 0.50–0.88 | 1–2 |
| 1 đến 5 | QPSK→16QAM | 11–15 | 0.44–0.60 | 0.88–1.50 | 2 |
| 5 đến 10 | 16QAM | 16–19 | 0.55–0.70 | 1.50–2.40 | 2–3 |
| 10 đến 15 | 16QAM→64QAM | 20–24 | 0.60–0.75 | 2.40–4.00 | 3 |
| 15 đến 20 | 64QAM | 25–27 | 0.70–0.85 | 4.00–5.50 | 3–4 |
| 20 đến 25 | 64QAM→256QAM | 28 | 0.85–0.93 | 5.50–7.40 | 4 |
| > 25 | 256QAM | 28+ | 0.93 | 7.40+ | 4 |

### 2.2 CQI → Spectral Efficiency (3GPP TS 38.214 Table 5.2.2.1-2)

| CQI | Modulation | Code Rate × 1024 | Spectral Eff (bps/Hz) | SINR approx (dB) |
|-----|-----------|-----------------|----------------------|------------------|
| 0 | — | out of range | 0 | < -6 |
| 1 | QPSK | 78 | 0.1523 | -6 |
| 2 | QPSK | 120 | 0.2344 | -4 |
| 3 | QPSK | 193 | 0.3770 | -2 |
| 4 | QPSK | 308 | 0.6016 | 0 |
| 5 | QPSK | 449 | 0.8770 | 2 |
| 6 | QPSK | 602 | 1.1758 | 4 |
| 7 | 16QAM | 378 | 1.4766 | 6 |
| 8 | 16QAM | 490 | 1.9141 | 8 |
| 9 | 16QAM | 616 | 2.4063 | 10 |
| 10 | 64QAM | 466 | 2.7305 | 12 |
| 11 | 64QAM | 567 | 3.3223 | 14 |
| 12 | 64QAM | 666 | 3.9023 | 16 |
| 13 | 64QAM | 772 | 4.5234 | 18 |
| 14 | 256QAM | 711 | 5.5547 | 21 |
| 15 | 256QAM | 797 | 6.2266 | 23+ |

### 2.3 Throughput = f(SINR, BW, Layers)

```
Throughput_cell = BW_Hz × SE(SINR) × N_layers × (1 − OH) × TDD_share    [bps]
```

**Ví dụ tại cell edge (SINR = 0 dB, CQI=4, SE=0.60):**
```
n78, 100 MHz, 1 layer, DL TDD 70%:
TP = 100×10⁶ × 0.60 × 1 × 0.86 × 0.70 = 36.1 Mbps
```

**Tại SINR = 15 dB (CQI=11, SE=3.32):**
```
n78, 100 MHz, 3 layers, DL TDD 70%:
TP = 100×10⁶ × 3.32 × 3 × 0.86 × 0.70 = 600 Mbps
```

---

## 3. QoS REQUIREMENTS THEO LOẠI DỊCH VỤ

### 3.1 5G Service Categories (ITU-R M.2410-0 / IMT-2020)

| Service | Tên đầy đủ | Đặc điểm | KPI chính |
|---------|-----------|-----------|-----------|
| **eMBB** | Enhanced Mobile Broadband | Throughput cao, dữ liệu lớn | DL ≥ 10 Gbps peak, UE ≥ 100 Mbps |
| **URLLC** | Ultra-Reliable Low Latency Comm | Độ trễ cực thấp, tin cậy cao | <1ms RTT, 99.999% reliability |
| **mMTC** | Massive Machine-Type Comm | Số lượng thiết bị lớn, low power | 10⁶ devices/km², battery 10+ năm |

### 3.2 QoS Requirements theo Service Type

#### Voice (VoNR / VoIP)

| Thông số | Yêu cầu | Ghi chú |
|----------|---------|---------|
| DL/UL throughput/user | **≥ 24 kbps** (AMR-WB) | Codec adaptive multi-rate wideband |
| Latency (user plane) | ≤ 50 ms (target), ≤ 100 ms (max) | End-to-end one-way |
| Jitter | ≤ 30 ms | Variation |
| Packet Loss Rate | ≤ 1% | BLER target |
| SINR minimum | ≥ **-3 dB** | Đảm bảo QPSK, MCS 5–6 |
| 5QI | **1** (Conversational Voice) | 3GPP TS 23.501 |
| Priority | **Highest** (scheduling) | Pre-emption over data |

#### Video Streaming (SD/HD/4K)

| Thông số | SD (480p) | HD (1080p) | 4K (2160p) | 8K |
|----------|-----------|-----------|-----------|-----|
| DL throughput | **1–2 Mbps** | **5–8 Mbps** | **25–50 Mbps** | 100+ Mbps |
| UL throughput | 0.5 Mbps | 1–2 Mbps | 5–10 Mbps | — |
| Latency | ≤ 150 ms | ≤ 100 ms | ≤ 50 ms (interactive) | — |
| Jitter | ≤ 50 ms | ≤ 30 ms | ≤ 20 ms | — |
| Packet Loss | ≤ 2% | ≤ 1% | ≤ 0.1% | — |
| SINR minimum | ≥ **0 dB** | ≥ **5 dB** | ≥ **12 dB** | ≥ 20 dB |
| Modulation | QPSK–16QAM | 16QAM | 64QAM | 256QAM |
| 5QI | **2** (Conversational Video) | **4** (Streaming) | **4** | — |

#### Video Call / Conferencing (2-way)

| Thông số | Yêu cầu |
|----------|---------|
| DL throughput | 2–10 Mbps (HD) |
| UL throughput | 2–10 Mbps (HD) — **bottleneck!** |
| Latency | ≤ 50 ms (one-way) |
| Jitter | ≤ 30 ms |
| SINR (DL+UL) | ≥ **5 dB** both ways |
| Symmetric | UL ≈ DL → **cần TDD balanced** hoặc UL-heavy |

#### Data (Web, Email, File Download)

| Thông số | Best-effort | Guaranteed |
|----------|-------------|------------|
| DL throughput | ≥ **1 Mbps** (usable web) | 10–100+ Mbps |
| UL throughput | ≥ **0.5 Mbps** | 5–50 Mbps |
| Latency | ≤ 100 ms (web), ≤ 300 ms (email) |
| SINR | ≥ **-6 dB** (min connectivity) |
| 5QI | **9** (Default: web, file share) |

#### Gaming / Cloud Gaming

| Thông số | Cloud Gaming | Online Gaming |
|----------|--------------|---------------|
| DL throughput | 20–50 Mbps | 1–5 Mbps |
| UL throughput | 5–10 Mbps | 0.5–2 Mbps |
| Latency | ≤ **20 ms** (RTT) | ≤ **30 ms** |
| Jitter | ≤ **5 ms** | ≤ 10 ms |
| SINR | ≥ **15 dB** | ≥ 5 dB |

#### IoT / mMTC

| Thông số | Smart Meter | Industrial IoT |
|----------|------------|----------------|
| Throughput | 10–100 kbps | 100 kbps–1 Mbps |
| Latency | ≤ 1s | ≤ 10 ms (URLLC) |
| Devices/km² | 10,000–100,000 | 1,000–10,000 |
| Battery | 10+ years | Wired |
| SINR | ≥ -6 dB | ≥ 0 dB |

### 3.3 5QI → QoS Mapping (3GPP TS 23.501)

| 5QI | Resource Type | Priority | Packet Delay Budget | Packet Error Rate | Example Service |
|-----|--------------|----------|--------------------|-------------------|-----------------|
| **1** | GBR | 2 | 100ms | 10⁻² | Conversational Voice |
| **2** | GBR | 4 | 150ms | 10⁻³ | Conversational Video |
| **3** | GBR | 3 | 50ms | 10⁻³ | Real-time gaming |
| **4** | GBR | 5 | 300ms | 10⁻⁶ | Non-conversational video streaming |
| **5** | Non-GBR | 1 | 100ms | 10⁻⁶ | IMS signalling |
| **6** | Non-GBR | 6 | 300ms | 10⁻⁶ | Video TCP (buffered) |
| **7** | Non-GBR | 7 | 100ms | 10⁻³ | Voice, Video, interactive |
| **8** | Non-GBR | 8 | 300ms | 10⁻⁶ | TCP web, email |
| **9** | Non-GBR | 9 | 300ms | 10⁻⁶ | Web, file sharing |
| **69** | GBR | 0.5 | 5ms | 10⁻⁵ | URLLC: factory automation |
| **80** | Non-GBR | 5.5 | 10ms | 10⁻⁵ | URLLC: low latency |

---

## 4. SINR → COVERAGE ZONE → SERVICE ZONE

### 4.1 Service Zones theo SINR

```
                    Cell Center          Cell Edge
                    ─────────────────────────────────
                    │  256QAM  │  64QAM  │ 16QAM │ QPSK │ No svc
SINR (dB):          │  >20     │  10-20  │ 3-10  │ -6-3  │ < -6
                    ─────────────────────────────────
Service available:
  VoNR (≥-3dB)     │██████████│█████████│███████│██████│
  Video SD (≥0dB)  │██████████│█████████│███████│      │
  Video HD (≥5dB)  │██████████│█████████│       │      │
  Video 4K (≥12dB) │██████████│         │       │      │
  Gaming (≥15dB)   │██████████│         │       │      │
  Cloud Gaming     │████      │         │       │      │
```

### 4.2 Cell Radius theo Service Level

**Ví dụ: n78, 100MHz, 32T32R, 200W, UMa NLOS, urban**

| Service | SINR min (dB) | Cell Radius (km) | % Cell Area | Users/cell (20Hz, 50% load) |
|---------|--------------|-----------------|-------------|------------------------------|
| Basic connectivity | -6 | 0.79 | 100% | — |
| VoNR | -3 | 0.68 | 87% | ~2000 |
| Video SD (480p) | 0 | 0.55 | 70% | ~1500 |
| Video HD (1080p) | 5 | 0.38 | 47% | ~800 |
| Video 4K | 12 | 0.22 | 20% | ~300 |
| Gaming/Cloud | 15 | 0.17 | 12% | ~150 |

> Cell radius giảm nhanh khi yêu cầu SINR cao — do đường cong PL dốc ở NLOS

### 4.3 Coverage vs Capacity Trade-off

```
┌─────────────────────────────────────────────────────────┐
│  COVERAGE-CAPACITY TRADE-OFF                            │
│                                                         │
│  ┌────────────┐         ┌──────────────┐                │
│  │ COVERAGE   │ ←───── │ CAPACITY      │                │
│  │ (Cell edge │ trade- │ (Cell center  │                │
│  │  SINR ≥    │  off   │  throughput)  │                │
│  │  target)   │         │               │                │
│  └────────────┘         └──────────────┘                │
│                                                         │
│  Muốn cell edge tốt → giảm throughput/cell (mất công    │
│  suất cho coverage, dùng low MCS)                       │
│                                                         │
│  Muốn throughput cao → chấp nhận cell edge kém (chỉ      │
│  phục vụ users gần BS)                                  │
└─────────────────────────────────────────────────────────┘
```

**2 chiến lược:**
1. **Coverage-limited**: Thiết kế cho SINR_min thấp nhất (VoNR = -3dB) → radius lớn, but throughput thấp ở edge
2. **Capacity-limited**: Thiết kế cho SINR_min cao (HD video = 5dB) → radius nhỏ, throughput cao everywhere

---

## 5. CAPACITY DIMENSIONING

### 5.1 Cell Capacity

```
Cell_Throughput_DL = BW × SE_avg(SINR_avg) × N_layers × (1−OH) × TDD_DL_share    [bps]

Cell_Throughput_UL = BW × SE_avg(SINR_avg) × N_layers_UL × (1−OH) × TDD_UL_share    [bps]
```

**Ví dụ: n78, 100MHz, 32T32R (4 layers DL, 2 UL), avg SINR=10dB, SE=2.4:**
```
DL_capacity = 100×10⁶ × 2.4 × 4 × 0.86 × 0.70 = 578 Mbps per cell
UL_capacity = 100×10⁶ × 2.4 × 2 × 0.92 × 0.30 = 133 Mbps per cell
```

### 5.2 User Capacity (per Service)

```
N_users = Cell_Throughput / (Throughput_per_user × Overprovisioning_ratio)
```

**Overprovisioning ratio** (x% active cùng lúc):
- Voice: 0.5–1% active (concurrent) → ratio 100–200×
- Video streaming: 10–20% active → ratio 5–10×
- Data/Best-effort: 5–10% active → ratio 10–20×

**Ví dụ: Cell với 578 Mbps DL capacity**
| Service | Per-user (Mbps) | Overprov. | Max Users |
|---------|----------------|-----------|-----------|
| VoNR | 0.024 | 200× | ∞ ( không giới hạn ) |
| Video HD | 8 | 5× | 578/(8×0.2) = **360** |
| Video 4K | 50 | 5× | 578/(50×0.2) = **57** |
| Web/Data | 10 | 10× | 578/(10×0.1) = **578** |
| Mixed (50% HD, 30% data, 20% VoNR) | — | — | **~280** |

### 5.3 Site Count với Capacity Constraint

```
N_sites_capacity = max(
    N_sites_coverage,                              // từ link budget
    Total_Users × Throughput_per_user / Cell_capacity / Overprov_factor
)
```

**Khi nào capacity dominate?**
- Dense urban, nhiều users, throughput/user cao
- Venues (stadium, mall, airport)
- FWA (Fixed Wireless Access) với UL throughput cao

---

## 6. QOS-AWARE SIZING — WORKFLOW CHO TOOL

### 6.1 Input bổ sung cho Tool

```json
{
  "qos_requirements": {
    "primary_service": "mixed",        // "voice" | "video_sd" | "video_hd" | "video_4k" | "data" | "gaming" | "mixed"
    "target_dl_per_user_mbps": 50,     // Mbps, minimum guaranteed
    "target_ul_per_user_mbps": 10,     // Mbps
    "max_latency_ms": 50,             // one-way user plane
    "target_users_per_km2": 500,       // user density
    "concurrent_ratio": 0.20,          // % users active simultaneously
    "coverage_reliability": 95,        // % cell edge reliability
    "indoor_coverage": true,           // có yêu cầu phủ trong nhà?
    "voice_quality": "AMR-WB",         // voice codec
    "video_resolution": "1080p",
    "urllc_required": false            // URLLC: <1ms, 99.999%
  }
}
```

### 6.2 Calculation Flow (Coverage + Capacity)

```
Step 1: LINK BUDGET (Coverage)
  ├─ Calculate MAPL_DL, MAPL_UL
  ├─ Cell radius = min(R_DL, R_UL) = R_UL  (UL-limited)
  └─ N_sites_coverage = Area / (2.598 × R²) × (1 + overlap)

Step 2: SINR MAPPING (Service Quality)
  ├─ Calculate SINR at cell edge (R)
  │   SINR_edge = EIRP - PL(R) - Interference - Noise
  ├─ Map SINR → CQI → MCS → SE
  └─ Determine service availability at cell edge

Step 3: THROUGHPUT (Capacity)
  ├─ Cell capacity = BW × SE × layers × (1-OH) × TDD_share
  ├─ User capacity = Cell_capacity / (per_user_TPUT × concurrent)
  └─ Area capacity = User_capacity × N_sites_coverage

Step 4: CAPACITY CHECK
  ├─ If Area_capacity < required_users × per_user_TPUT:
  │   → Need MORE sites (capacity-limited)
  │   → Recalculate N_sites_capacity
  └─ Final N_sites = max(N_coverage, N_capacity)

Step 5: QOS VERIFICATION
  ├─ Voice: SINR ≥ -3 dB at cell edge? ✓/✗
  ├─ Video: SINR ≥ service_threshold at cell edge? ✓/✗
  ├— Latency: propagation_delay + processing ≤ target? ✓/✗
  └─ Reliability: shadow_fading_margin adequate for reliability%? ✓/✗

Step 6: RECOMMENDATIONS
  ├─ If SINR too low: increase TX power, upgrade antenna (32T32R), add sites
  ├─ If capacity too low: more BW, more sectors, carrier aggregation, small cells
  ├─ If UL bottleneck: upgrade UE Power Class, UL MIMO, TDD rebalance
  └─ If indoor: add indoor small cells / DAS
```

### 6.3 Example: Dense Urban n78, Mixed Service

**Inputs:**
```
Area: 50 km², dense urban (UMa NLOS)
BS: 32T32R, 200W, 18 dBi, 25m, 3 sectors
Band: n78 (3500 MHz), 100 MHz BW, SCS 30kHz, TDD DDDSU (70:30)
UE: PC3 (23 dBm), 0 dBi, 1.5m, NF=7dB
Margins: IF=3, SF=9.4, rain=1, OH=0.14(DL)/0.08(UL)
QoS: 50 Mbps DL, 10 Mbps UL per user, 500 users/km², 20% concurrent
```

**Step 1: Coverage**
```
MAPL_UL = 23 + 0 - 0 - (-104.8 + 3.5 + (-6)) - 3 - 9.4 - 1 + 18 + 3.5 - 0.5
        = 23 + 97.3 - 3 - 9.4 - 1 + 18 + 3.5 - 0.5 = 127.9 dB

Cell radius (UMa NLOS):
127.9 = 13.54 + 39.08·log10(d) + 20·log10(3.5)
d = 10^((127.9 - 24.42) / 39.08) = 10^2.649 = 446 m = 0.446 km

N_sites_coverage = 50 / (2.598 × 0.446²) × 1.25 = 50 / 0.516 × 1.25 = 121 sites
```

**Step 2: SINR at cell edge**
```
SINR_edge_UL: UE Tx → BS Rx
RSRP = 23 - 0 - PL(446m) = 23 - 127.9 = -104.9 dBm
Noise = -174 + 10·log10(100e6) + 3.5 = -90.5 dBm
SINR = -104.9 - (-90.5) = -14.4 dB → too low for any service!
```

→ **Wait** — MAPL includes interference margin (3dB) + shadow fading (9.4dB) → median SINR is higher:
```
SINR_median = SINR_edge + IF_margin + SF_margin = -14.4 + 3 + 9.4 = -2.0 dB
```

→ **At 95% reliability**: SINR ≈ -2 dB → **QPSK, CQI 3–4, SE ≈ 0.4–0.6**

**Step 3: Cell Capacity**
```
DL: 100×10⁶ × 2.4(avg SE @10dB) × 4 × 0.86 × 0.70 = 578 Mbps
UL: 100×10⁶ × 1.0(avg SE @5dB UL) × 2 × 0.92 × 0.30 = 55.2 Mbps
```

**Step 4: Capacity Check**
```
Required: 500 users/km² × 50 km² = 25,000 users
Active: 25,000 × 0.20 = 5,000 concurrent
DL demand: 5,000 × 50 Mbps = 250,000 Mbps = 250 Gbps
DL supply (121 sites × 3 sectors × 578 Mbps): 121 × 3 × 578 = 209, 814 Mbps ≈ 210 Gbps

→ Capacity INSUFFICIENT! (250 > 210)
→ Capacity-limited: need ~144 sites (additional 23)
```

**Step 5: QoS Verification**
```
Voice (VoNR): SINR ≥ -3 dB at edge → ✓ (SINR_median = -2 dB)
Video HD: SINR ≥ 5 dB at edge → ✗ (only near center)
Data 50 Mbps/user: Cell capacity insufficient → ✗ at full load
```

**Step 6: Recommendations**
```
1. Increase sites from 121 → 144 (capacity)
2. Or reduce per-user target to 35 Mbps DL → 175 Gbps demand < 210 Gbps
3. Or add carrier aggregation (second 100MHz carrier) → doubles capacity
4. Or deploy small cells (4T4R, indoor) for capacity offload
5. Upgrade UE to PC2 (+3 dB UL) for better cell-edge SINR
```

---

## 7. QOS REQUIREMENT LOOKUP TABLES (cho Tool)

### 7.1 Service → SINR/Throughput Mapping

| Service | Min SINR (dB) | Min DL (Mbps) | Min UL (Mbps) | Max Latency (ms) | 5QI |
|---------|--------------|---------------|---------------|-----------------|-----|
| Emergency Call | -3 | 0.024 | 0.024 | 50 | 1 |
| VoNR (Voice) | -3 | 0.024 | 0.024 | 50 | 1 |
| Video Call (HD) | 5 | 8 | 8 | 50 | 2 |
| Video Streaming SD | 0 | 2 | 0.5 | 150 | 4 |
| Video Streaming HD | 5 | 8 | 1 | 100 | 4 |
| Video Streaming 4K | 12 | 50 | 5 | 50 | 4 |
| Web Browsing | -6 | 1 | 0.5 | 100 | 9 |
| Email/Social | -6 | 0.5 | 0.2 | 300 | 9 |
| File Download | 0 | 10 | 1 | 300 | 6 |
| Online Gaming | 5 | 5 | 1 | 30 | 3 |
| Cloud Gaming | 15 | 50 | 10 | 20 | 3 |
| AR/VR | 15 | 100 | 20 | 10 | 3 |
| Smart Meter (IoT) | -6 | 0.01 | 0.01 | 1000 | 9 |
| Industrial IoT | 0 | 1 | 1 | 10 | 69/80 |
| FWA Basic | -3 | 50 | 10 | 100 | 6 |
| FWA Premium | 10 | 300 | 50 | 50 | 4 |
| Telemedicine | 5 | 10 | 10 | 20 | 2 |
| Autonomous Vehicle | 10 | 50 | 10 | 5 | 69 |

### 7.2 Environment → SINR Adjustment

| Environment | SINR adjustment (dB) | Ghi chú |
|-------------|---------------------|---------|
| Dense urban (UMa) | 0 | Baseline |
| Urban (UMi) | +1 | Ít vật cản hơn UMa |
| Suburban | +3 | Clutter thấp |
| Rural | +5 | Gần như LOS |
| Indoor (InH) | -3 đến -8 | Penetration + clutter |
| Factory (InF) | -5 đến -10 | Metallic clutter, máy móc |
| Vehicle (V2X) | -3 | Doppler + handover |
| High speed train | -5 | Doppler cao, handover nhanh |

---

## 8. TÍCH HỢP VÀO TOOL SIZING

### 8.1 Workflow cập nhật

```
INPUT: User chỉ định:
  - Vùng phủ (km²)
  - Môi trường (outdoor/indoor)
  - BS config (32T32R, 8T8R, ...)
  - TX power
  - Băng tần (n77, n78, n41, n8)
  - UE Power Class
  - QoS targets:
    * Loại dịch vụ chính (voice/video/data/mixed)
    * Tốc độ DL/UL mục tiêu (Mbps)
    * Số users/km²
    * Độ trễ tối đa
    * Độ tin cậy yêu cầu (%)

OUTPUT:
  1. Coverage map (cell radius, # sites)
  2. Service zone map (có bao nhiêu % vùng đủ cho mỗi service)
  3. Capacity check (đủ hay thiếu, bao nhiêu site thêm)
  4. QoS verification table (pass/fail từng service)
  5. Recommendations (config changes, thêm sites, carrier aggregation)
```

### 8.2 Output Example (JSON)

```json
{
  "coverage": {
    "cell_radius_km": 0.446,
    "n_sites_coverage": 121,
    "limiting_link": "UL",
    "mapl_ul_db": 127.9,
    "mapl_dl_db": 134.3
  },
  "qos": {
    "voice_vonr": {"sinr_edge_db": -2.0, "required_db": -3, "pass": true},
    "video_hd": {"sinr_edge_db": -2.0, "required_db": 5, "pass": false, "service_area_pct": 47},
    "data_50mbps": {"per_user_dl_mbps": 50, "capacity_ok": false, "deficit_pct": 16}
  },
  "capacity": {
    "cell_dl_mbps": 578,
    "cell_ul_mbps": 55,
    "n_sites_required_capacity": 144,
    "limiting_factor": "capacity_dl"
  },
  "final": {
    "n_sites": 144,
    "isd_km": 0.50,
    "recommendations": [
      "Increase sites by 23 for DL capacity",
      "Consider carrier aggregation (2nd 100MHz)",
      "Upgrade cell-edge UEs to Power Class 2",
      "Deploy small cells in high-traffic clusters"
    ]
  }
}
```

---

## 9. TÀI LIỆU THAM KHẢO

| Tài liệu | Mô tả |
|----------|-------|
| **3GPP TS 38.306** | NR UE radio access capabilities (throughput formula) |
| **3GPP TS 38.214** | NR Physical layer procedures (MCS, CQI, TBS) |
| **3GPP TS 38.104** | NR BS radio transmission (BW → N_RB table) |
| **3GPP TS 23.501** | System architecture (5QI QoS mapping) |
| **ITU-R M.2410-0** | IMT-2020 minimum requirements (eMBB, URLLC, mMTC) |
| **3GPP TR 38.913** | Study on NR NextGen (service requirements) |
| **3GPP TS 38.300** | NR Overall description (architecture, QoS flow) |

---

*Document generated: 2026-06-20*
*Depends on: phase1-rf-factors.md, phase2-tool-design.md*
