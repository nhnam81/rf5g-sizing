# 5G RF Coverage Sizing — Phase 1: Yếu tố kỹ thuật ảnh hưởng vùng phủ sóng

> Nghiên cứu kỹ thuật | 2026-06-20
> Standards: 3GPP TR 38.901, TS 38.104, TS 38.101, ITU-R P.1411

---

## 1. THÔNG SỐ TRẠM PHÁT (gNB)

### 1.1 Cấu hình Anten (T×R)

| Config | Số phần tử | Gain điển hình (dBi) | BF Gain (dB) | MIMO layers | Ứng dụng |
|--------|-----------|----------------------|--------------|-------------|----------|
| **32T32R** | 32 TX × 32 RX | 18–21 | 3–4 | 4 (DL MU-MIMO) | Macro cell (UMa), high-capacity |
| **16T16R** | 16×16 | 16–18 | 2–3 | 4 | Macro/micro |
| **8T8R** | 8×8 | 14–16 | 1.5–2 | 2–4 | Micro (UMi), small cell |
| **4T4R** | 4×4 | 12–14 | 1–1.5 | 2–4 | Small cell, indoor |
| **2T2R** | 2×2 | 9–11 | 0–0.5 | 1–2 | Indoor, femtocell |

**Impact lên coverage:**
- Beamforming gain (32T32R vs 2T2R): thêm ~3 dB → tăng bán kính ~15-20%
- Massive MIMO (32T32R): tập trung năng lượng vào hướng UE → giảm nhiễu, tăng SINR
- **Diminishing returns**: 64T64R không tăng đáng kể so với 32T32R ở sub-6GHz

### 1.2 Công suất phát (TX Power)

| Công suất/kênh | dBm | Loại trạm | Bán kính điển hình |
|----------------|-----|-----------|-------------------|
| 1W (30 dBm) | 30 | Femtocell/indoor | 50–200 m |
| 2W (33 dBm) | 33 | Small cell | 100–300 m |
| 5W (37 dBm) | 37 | Micro cell | 200–500 m |
| 10W (40 dBm) | 40 | Small macro | 300–800 m |
| 20W (43 dBm) | 43 | Macro | 500–1500 m |
| 40W (46 dBm) | 46 | Macro | 700–2000 m |
| 200W (53 dBm) | 53 | Macro (high-power) | 1000–3000 m |

**Lưu ý:** Tổng công suất = công suất/kênh × số kênh (RB). 200W = ~53 dBm cho 100 MHz BW tại n78.

### 1.3 Anten Gain

| Loại | Gain (dBi) | Bán kính tác động |
|------|-----------|-------------------|
| Macro sector (65° H-plane) | 15–21 | Vùng phủ chính + lobes phụ |
| Small cell omni | 2–5 | Phủ tròn, công suất thấp |
| Indoor ceiling mount | 2–4 | Phủ 1 tầng |
| Directional panel | 8–14 | Phủ hướng |

### 1.4 Băng tần số (3GPP TS 38.104)

| Band | Tần số (MHz) | Duplex | λ (bước sóng) | Đặc tính truyền lan |
|------|-------------|--------|--------------|---------------------|
| **n8** | 880–960 | FDD | ~32 cm | Phủ xa tốt, xuyên vật cản tốt, BW hạn chế (≤20 MHz) |
| **n28** | 703–803 | FDD | ~38 cm | Phủ rất xa, thấp tần,穿透 tốt |
| **n3** | 1710–1880 | FDD | ~16 cm | Phủ trung bình, cân bằng phủ/dung lượng |
| **n41** | 2496–2690 | TDD | ~12 cm | Cân bằng, BW lớn (100 MHz), phổ biến (Sprint/T-Mobile US) |
| **n77** | 3300–4200 | TDD | ~8 cm | C-band, phổ 5G chính toàn cầu, BW 100 MHz |
| **n78** | 3300–3800 | TDD | ~8.5 cm | Phổ 5G EU/VN/Á, phủ trung bình |
| **n79** | 4400–5000 | TDD | ~6.5 cm | Nhật/Trung, BW lớn |
| **FR2 (mmWave)** | 24250–52000 | TDD | <1.2 cm | Phủ rất gần (100–500m), BW cực lớn (400 MHz) |

**Quy luật vật lý:** Tần số cao hơn → path loss lớn hơn → cell radius nhỏ hơn.
```
FSPL = 20·log10(d_km) + 20·log10(fc_GHz) + 92.45
```
n78 (3.5 GHz) có FSPL cao hơn n8 (925 MHz) khoảng **11.6 dB** cùng khoảng cách.

---

## 2. THIẾT BỊ ĐẦU CUỐI (UE)

### 2.1 Power Class (3GPP TS 38.101)

| Power Class | FR | Max TX Power (dBm) | Max TX (mW) | Ứng dụng |
|-------------|-----|-------------------|-------------|----------|
| **PC1** | FR2 | 35 | 3162 | FWA (Fixed Wireless Access) |
| **PC1.5** | FR1 | 31 | 1259 | High-power UE / FWA (n77/n78) |
| **PC2** | FR1 | 26 | 398 | High-power handset (n41, n77, n78) |
| **PC2** | FR2 | 23 | 200 | Vehicular |
| **PC3** | FR1 | 23 | 200 | Standard handset (mọi băng FR1) |
| **PC3** | FR2 | 23 | 200 | Handheld mmWave |
| **PC4** | FR2 | 23 | 200 | High-power non-handheld |

**Impact:** PC2 (26 dBm) vs PC3 (23 dBm) = **+3 dB** → tăng UL cell radius ~15-20%.

### 2.2 UE Antenna

| Loại UE | Antenna Gain (dBi) | Body Loss (dB) |
|---------|-------------------|----------------|
| Smartphone (PC3) | 0 (omni) | 1–4 (head), 0–2 (hand) |
| FWA/CPE (PC1/1.5) | 3–8 (directional panel) | 0 |
| Vehicle (PC2) | 2–5 (roof mount) | 0 |
| IoT sensor | -2 đến +2 | 0–2 |

### 2.3 Noise Figure (NF)

| Loại UE | NF điển hình (dB) |
|---------|-------------------|
| Smartphone | 7–10 |
| FWA/CPE | 5–7 |
| IoT device | 10–15 |

---

## 3. MÔI TRƯỜNG TRUYỀN LAN

### 3.1户外 LOS vs NLOS

| Tình trạng | Đặc điểm | Path Loss |
|-----------|-----------|-----------|
| **LOS** (Line of Sight) | Không vật cản giữa BS-UE | Thấp nhất, FSPL + nhỏ |
| **NLOS** (Non-LOS) | Có vật cản (tòa nhà, cây, địa hình) | Cao hơn LOS 10–30 dB |
| **O2I** (Outdoor-to-Indoor) | UE trong nhà, BS ngoài trời | Thêm 10–20 dB penetration loss |

### 3.2 Building Penetration Loss (3GPP TR 38.901 O2I)

| Loại vật liệu | Loss (dB) | Ghi chú |
|---------------|-----------|---------|
| kính nhiệt tiết (Low-E) | 20–40 | Rất phổ biến tòa nhà văn phòng |
| kính thường | 2–6 | Nhà cũ, cửa sổ thường |
| tường gạch | 10–15 | Nhà phố |
| tường bê tông | 15–30 | Tòa nhà hiện đại |
| tường đá/c granite | 20–40 | Công trình đặc biệt |
| gỗ | 5–10 | Nhà gỗ |
| kim loại (lift shaft, HVAC) | 30–60 | Cấm hoàn toàn |

**3GPP O2I Loss model (TR 38.901 §7.4.3.1):**
```
PL_O2I = PL_3GPP(d) + PL_tw + PL_in + N(0, σ_P)    [dB]

PL_tw = 5 – 10·log10(7.37·10^(-3)·f_GHz² + 0.16)   (Low-E glass)
PL_in = 0.5·N(0, σ_P)                                (interior loss)
σ_P = 4.4 – 5.3 dB (depending on frequency)
```

### 3.3 Clutter Models

| Môi trường | 3GPP Scenario | Shadow Fading σ (dB) | Đặc điểm |
|-----------|---------------|----------------------|----------|
| Dense urban | UMa NLOS | 6–10 | Nhiều tòa nhà cao, street canyon |
| Urban | UMi NLOS | 7–8 | Tòa nhà trung bình, mật độ cao |
| Suburban | UMa/UMi | 4–6 | Nhà thấp tầng, cây xanh |
| Rural | RMa | 4–8 | Đất nông nghiệp, ít vật cản |
| Indoor office | InH-Office | 3–5 | Vách ngăn, trần, sàn |
| Indoor factory | InF-SL/DL/SH/DH | 4–6 | Dây chuyền, máy móc |

### 3.4 Địa hình (Terrain)

| Loại | Impact | Mô hình |
|------|--------|---------|
| Phẳng | Tầm thẳng xa | FSPL, Hata |
| Đồi/núi | Diffraction loss | ITU-R P.526 (knife-edge) |
| Thung lũng | Reflection, shadowing | Ray-tracing hoặc measurements |
| Mặt nước | Reflection đa đường | Two-ray model |

---

## 4. MÔ HÌNH TRUYỀN LAN RF (Propagation Models)

### 4.1 3GPP TR 38.901 V16.1.0 — Công thức chính

#### UMa (Urban Macro), BS height 25m

**LOS:**
```
PL_UMa_LOS = 28.0 + 22·log10(d_3D) + 20·log10(fc)     [dB]
Valid: 10m ≤ d ≤ 5km, 0.5–100 GHz, hBS = 25m
```

**NLOS:**
```
PL_UMa_NLOS = 13.54 + 39.08·log10(d_3D) + 20·log10(fc) - 0.6·(hUT - 1.5)    [dB]
```

**LOS Probability:**
```
P_LOS = min(18/d_2D + 0.0216, 1) · (1 - exp(-d_2D/36)) + exp(-d_2D/36)
```

#### UMi (Urban Micro), BS height 10m

**LOS:**
```
PL_UMi_LOS = 32.4 + 21·log10(d_3D) + 20·log10(fc)     [dB]
```

**NLOS:**
```
PL_UMi_NLOS = 32.4 + 31.9·log10(d_3D) + 20·log10(fc)    [dB]
```

#### RMa (Rural Macro)

**LOS:**
```
PL_RMa_LOS = 20·log10(40π·d·fc/3) + min(0.03·h^1.72, 10)·log10(d)
             - min(0.044·h^1.72, 14.77) + 0.002·log10(h)·d     [dB]
```

**NLOS:**
```
PL_RMa_NLOS = 161.04 - 7.1·log10(W) + 7.5·log10(h)
              - (24.37 - 3.7·(h/hBS)²)·log10(hBS)
              + (43.42 - 3.1·log10(hBS))·(log10(d) - 3)
              + 20·log10(fc) - (3.2·(log10(11.75·hUT))² - 4.97)     [dB]
```
Default: W=20m (street width), h=5m (building height)

#### InH-Office (Indoor Hotspot)

**LOS:**
```
PL_InH_LOS = 32.4 + 17.3·log10(d_3D) + 20·log10(fc)    [dB]
Valid: 1m ≤ d ≤ 150m
```

**NLOS:**
```
PL_InH_NLOS = max(PL_InH_LOS, 17.3 + 38.3·log10(d_3D) + 24.9·log10(fc))    [dB]
```

### 4.2 Khi nào dùng mô hình nào?

| Mô hình | Scenario | Tần số | Khoảng cách | Khi nào dùng |
|---------|----------|--------|-------------|--------------|
| UMa | Urban macro, hBS=25m | 0.5–100 GHz | 10m–5km | Thành phố, macro cell |
| UMi | Urban micro, hBS=10m | 0.5–100 GHz | 10m–5km | Thành phố, small cell |
| RMa | Rural macro | 0.5–7 GHz | 10m–10km | Nông thôn, đường cao tốc |
| InH-Office | Indoor | 0.5–100 GHz | 1–150m | Trong tòa nhà |
| InF (Factory) | Nhà máy | 0.5–100 GHz | 1–150m | Môi trường công nghiệp |
| FSPL | Lý tưởng (LOS) | Any | Any | Baseline, kiểm tra |
| COST-231 Hata | Legacy | 1500–2600 MHz | 1–20km | So sánh với 4G |
| ITU-R P.1411 | Short-range outdoor | 0.3–100 GHz | <1km | Small cell, DAS |

### 4.3 Free Space Path Loss (FSPL)

```
FSPL(dB) = 20·log10(d_m) + 20·log10(fc_Hz) - 147.55
         = 20·log10(d_km) + 20·log10(fc_GHz) + 92.45
```

**Quick reference:** Tại d=1km, fc=3.5 GHz → FSPL = 103.3 dB

---

## 5. PHƯƠNG PHÁP TÍNH VÙNG PHỦ

### 5.1 Link Budget (Cơ bản)

#### Downlink (DL):
```
Rx_DL = EIRP_BS - PL - margins + Gain_UE

Trong đó:
  EIRP_BS = P_TX_BS(dBm) - Feeder_loss + Antenna_gain_BS + BF_gain
  PL = Path Loss (từ propagation model)
  Margins = Interference + Shadow_fading + Rain + Penetration + Vegetation
```

#### Uplink (UL):
```
Rx_UL = EIRP_UE - PL - margins + Gain_BS

Trong đó:
  EIRP_UE = P_TX_UE(dBm) - Body_loss + Antenna_gain_UE
```

### 5.2 MAPL → Cell Radius

```
MAPL = EIRP - Rx_Sensitivity - Σ Margins    [dB]

Rx_Sensitivity = -174 + 10·log10(BW_Hz) + NF + SINR_target    [dBm]

Cell radius: giải PL(d) = MAPL cho d    [km hoặc m]
```

**Ví dụ UMa NLOS (n78, 3500 MHz):**
```
MAPL = 13.54 + 39.08·log10(d) + 20·log10(3.5)
→ d = 10^((MAPL - 13.54 - 20·log10(3.5)) / 39.08)
```

### 5.3 Uplink hay Downlink giới hạn?

**Luôn UL giới hạn** trong 5G NR vì:
- UE TX power (23–26 dBm) << BS TX power (43–53 dBm)
- UE antenna gain (0 dBi) < BS antenna gain (15–21 dBi)
- UE NF (7–10 dB) > BS NF (3–5 dB)

→ Cell radius = cell radius UL (trong đa số trường hợp)

### 5.4 Margins Tổng hợp

| Margin | Giá trị điển hình (dB) | Khi nào tăng |
|--------|----------------------|-------------|
| Interference margin | 2–6 | Mật độ cell cao, tải cao |
| Shadow fading | 4–16 | Mật độ vật cản cao |
| Body loss | 0–4 | UE cầm tay, sát đầu |
| Penetration loss (O2I) | 0–20 | UE trong nhà |
| Vegetation loss | 0–4 | Nhiều cây xanh |
| Rain fade | 0–2 | Vùng mưa nhiều (nhiệt đới) |
| Atmospheric | 0–0.5 | Chỉ ảnh hưởng >10 GHz |
| Implementation margin | 1–3 | Dự phòng thực tế |

### 5.5 Cell Radius → Site Count

```
Diện tích/site (hexagonal, 3-sector):
  A_site = 2.598 × R²    [km²]

Số site cần:
  N = ceil(Area / A_site) × (1 + overlap_factor)

  overlap_factor: 0.15 (planned), 0.25 (typical), 0.35 (conservative)

Inter-site distance (ISD):
  ISD = √3 × R ≈ 1.732 × R
```

---

## 6. CELL RADIUS THỰC TẾ

### 6.1 Bảng tham chiếu (3-sector macro, 32T32R, 200W, PC3 UE)

| Band | fc (MHz) | Dense Urban (km) | Urban (km) | Suburban (km) | Rural (km) |
|------|----------|-----------------|-----------|--------------|-----------|
| n8 | 925 | 0.8–1.5 | 1.5–2.5 | 2.5–5.0 | 5.0–10.0 |
| n28 | 780 | 1.0–1.8 | 1.8–3.0 | 3.0–6.0 | 6.0–12.0 |
| n3 | 1800 | 0.5–1.0 | 1.0–1.8 | 1.8–3.5 | 3.5–7.0 |
| n41 | 2595 | 0.4–0.8 | 0.8–1.5 | 1.5–3.0 | 3.0–5.0 |
| n77 | 3700 | 0.3–0.6 | 0.6–1.2 | 1.2–2.5 | 2.5–4.5 |
| n78 | 3500 | 0.3–0.7 | 0.7–1.3 | 1.3–2.8 | 2.8–5.0 |
| n79 | 4700 | 0.25–0.5 | 0.5–1.0 | 1.0–2.0 | 2.0–4.0 |
| FR2 (28GHz) | 28000 | 0.1–0.3 | 0.2–0.4 | 0.3–0.5 | 0.5–1.0 |

### 6.2 Indoor Coverage (InH model)

| Band | Office LOS (m) | Office NLOS (m) | Factory (m) |
|------|---------------|----------------|-------------|
| n77/n78 | 50–100 | 30–60 | 20–50 |
| n41 | 60–120 | 40–80 | 30–60 |
| n8 | 80–150 | 60–100 | 50–80 |

### 6.3 Impact của Antenna Config

| Config | BF Gain (dB) | Cell Radius (n78, urban) | So với 2T2R |
|--------|-------------|--------------------------|-------------|
| 2T2R | 0 | 0.50 km | baseline |
| 4T4R | 1.0 | 0.58 km | +16% |
| 8T8R | 2.0 | 0.66 km | +32% |
| 16T16R | 2.5 | 0.71 km | +42% |
| 32T32R | 3.5 | 0.79 km | +58% |
| 64T64R | 4.0 | 0.83 km | +66% |

> Tính với MAPL_UL = 130 dB, UMa NLOS, fc=3500 MHz

---

## 7. TÀI LIỆU THAM KHẢO

| Tài liệu | Mô tả |
|----------|-------|
| **3GPP TR 38.901** V16.1.0 | Channel model cho 0.5–100 GHz (UMa/UMi/RMa/InH/InF) |
| **3GPP TS 38.104** | NR BS radio transmission and reception |
| **3GPP TS 38.101-1** | NR UE radio transmission and reception (FR1) |
| **3GPP TS 38.101-2** | NR UE (FR2) |
| **3GPP TR 38.812** | NR MIMO_OVERALL (massive MIMO) |
| **ITU-R P.1411-10** | Short-range outdoor propagation |
| **ITU-R P.525-3** | Free-space attenuation |
| **ITU-R P.526-15** | Diffraction |
| **ITU-R P.2108** | Statistical building entry loss |
| **ITU-R P.2109** | Building entry loss (frequency 80-100 GHz) |
| **COST-231** | Urban transmission loss (extended Hata) |
| **5G-tools.com** | Web-based 5G NR link budget calculator (reference) |

---

## 8. CÁC YẾU TỐ ĐẦU VÀO CHO TOOL SIZING

Tổng hợp các input cần thiết cho công cụ sizing vùng phủ:

### 8.1 Input bắt buộc
1. **Diện tích vùng phủ** (km²)
2. **Loại môi trường** (dense urban / urban / suburban / rural / indoor)
3. **Băng tần** (n77, n78, n41, n8, hoặc custom MHz)
4. **Cấu hình anten BS** (32T32R, 8T8R, 4T4R, 2T2R)
5. **Công suất TX BS** (W/kênh)
6. **UE Power Class** (1, 1.5, 2, 3)

### 8.2 Input tùy chọn (có default)
7. Anten gain BS (dBi) — default từ config table
8. Chiều cao BS (m) — default 25m macro, 10m micro
9. Chiều cao UE (m) — default 1.5m
10. UE antenna gain (dBi) — default 0
11. Body loss (dB) — default 0
12. Interference margin (dB) — default 3
13. Shadow fading margin (dB) — auto từ obstacle density
14. Penetration loss (dB) — default 0 (outdoor), 10 (indoor)
15. Rain margin (dB) — default 1
16. SINR target DL/UL (dB) — default -3/-6
17. Bandwidth (MHz) — default 100 (n77/n78), 20 (n8)
18. Cell edge reliability (%) — default 95
19. Coverage overlap factor — default 0.25
20. Sectors per site — default 3

---

*Document generated: 2026-06-20*
*Phase 2 (tool design) available at: phase2-tool-design.md*
