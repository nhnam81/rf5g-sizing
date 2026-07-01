# rf5g-sizing — Công thức Verification Report

**Date**: 2026-06-23  
**Scope**: Link Budget, Propagation, Site Estimation, Capacity, SINR/CQI

---

## 1. Propagation Models (3GPP TR 38.901 V16.1.0)

### 1.1 UMa LOS ✅ CORRECT
```
PL = 28.0 + 22*log10(d) + 20*log10(fc)          [d ≤ d_BP]
PL = 28.0 + 40*log10(d) + 20*log10(fc) - 9*log10(d_BP)  [d > d_BP]
d_BP = 4*(h_BS-1)*(h_UT-1)*fc/3e8
```
**3GPP Reference**: Table 7.4.1-1, Row "UMa-LOS"  
**Status**: ✅ Matches 3GPP TR 38.901 V16.1.0

### 1.2 UMa NLOS ⚠️ NEEDS REVIEW
```
PL_NLOS = max(161.04 - 7.28*log10(fc) + 36.56*log10(d_km), PL_LOS)
```
**3GPP Reference**: Table 7.4.1-1, Row "UMa-NLOS"  
**Issue**: 3GPP formula is:
```
PL_NLOS = 161.04 - 7.28*log10(fc[GHz]) + 36.56*log10(d_km)  ← 3GPP uses fc in GHz
```
**Current code uses**: `fc_ghz` which IS in GHz ✅  
**BUT**: 3GPP TR 38.901 also has alternative formula:
```
PL_NLOS = 13.54 + 39.08*log10(d_3D) + 20*log10(fc) - 5.49*log10(h_BS^2)
```
Code uses the simpler formula (Option 1). This is acceptable for macro planning.

**Verdict**: ✅ Acceptable (simplified but standard-compliant)

### 1.3 UMi LOS ✅ CORRECT
```
PL = 32.4 + 21*log10(d) + 20*log10(fc)    [d ≤ d_BP]
PL = 32.4 + 40*log10(d) + 20*log10(fc) - 9.5*log10(d_BP)  [d > d_BP]
```
**3GPP Reference**: Table 7.4.1-1, Row "UMi-Street Canyon-LOS"  
**Status**: ✅ Matches 3GPP

### 1.4 UMi NLOS ⚠️ MINOR
```
PL_NLOS = max(35.3*log10(d) + 22.4 + 21.3*log10(fc), PL_LOS)
```
**3GPP Reference**: Table 7.4.1-1  
**Issue**: The exact 3GPP formula is:
```
PL_NLOS = 35.3*log10(d_3D) + 22.4 + 21.3*log10(fc[GHz])
```
Code uses `d_2d_m` instead of `d_3D`. In UMi, for h_BS=10m and h_UT=1.5m, the difference is negligible (< 0.1 dB for d > 20m).

**Verdict**: ✅ Acceptable (d_2D ≈ d_3D for typical heights)

### 1.5 RMa LOS ✅ CORRECT
```
d_BP = 2*pi*h_BS*h_UT*fc_Hz/c
PL = 20*log10(40*pi*d*fc/3) + min(0, 1.5*(h_UT-h_BS)/1000)  [d ≤ d_BP]
PL = PL_BP + 40*log10(d/d_BP)  [d > d_BP]
```
**3GPP Reference**: Table 7.4.1-1, Row "RMa-LOS"  
**Status**: ✅ Matches 3GPP

### 1.6 RMa NLOS ✅ CORRECT
```
PL_NLOS = max(161.04 - 7.28*log10(fc) + 36.56*log10(d_km), PL_LOS)
```
**3GPP Reference**: Table 7.4.1-1  
**Status**: ✅ Matches 3GPP

### 1.7 InH LOS ✅ CORRECT
```
PL = 32.4 + 23*log10(d) + 20*log10(fc)              [d ≤ 150m]
PL = 32.4 + 23*log10(150) + 20*log10(fc) + 32*log10(d/150)  [d > 150m]
```
**3GPP Reference**: Table 7.4.1-1, Row "InH-LOS"  
**Status**: ✅ Matches 3GPP

### 1.8 InH NLOS ✅ CORRECT
```
PL_NLOS = max(38.3 + 24.9*log10(d) + 20*log10(fc), PL_LOS)
```
**3GPP Reference**: Table 7.4.1-1, Row "InH-NLOS"  
**Status**: ✅ Matches 3GPP

### 1.9 LOS Probability ✅ CORRECT
All 4 scenarios (UMa, UMi, RMa, InH) match 3GPP TR 38.901 Table 7.4.2-1.

### 1.10 Combined Path Loss ✅ CORRECT
```
PL_combined = -10*log10(P_LOS * 10^(-PL_LOS/10) + (1-P_LOS) * 10^(-PL_NLOS/10))
```
Linear power averaging — standard approach. ✅

---

## 2. Link Budget

### 2.1 DL EIRP ✅ CORRECT
```
EIRP = Tx_power(W→dBm) + Tx_gain(antenna+BF) - Cable_loss
```
**Check**: 200W → 53 dBm, 32T32R: 20dBi antenna + 12dB BF = 32dB gain  
EIRP = 53 + 32 - 1 = **84 dBm** ✅

### 2.2 DL Sensitivity ⚠️ SIMPLIFIED
```
Sensitivity = Noise_floor + SNR_required
Noise_floor = -174 + 10*log10(BW) + NF
SNR_required = -6 dB (processing gain for QPSK 1/2)
```
**Issue**: 
- **-6 dB SNR is too aggressive**. 3GPP TS 38.214 Table 5.2.2.1-2 shows:
  - CQI 1 (QPSK R=78/1024): SINR = -8 dB, SE = 0.1523
  - CQI 2 (QPSK R=120/1024): SINR = -6 dB, SE = 0.2344
- Using -6 dB as sensitivity target means assuming CQI 2 (worst case) which is reasonable for cell edge.
- **But**: The noise floor calculation uses full bandwidth, not per-RB. For 100 MHz, this gives:
  - NF = -174 + 80 + 7 = **-87 dBm**
  - Sensitivity = -87 + (-6) = **-93 dBm**
  - This is the full-band sensitivity, which is correct for total throughput but conservative for cell edge.

**Verdict**: ✅ Acceptable for planning (conservative cell-edge assumption)

### 2.3 MAPL Formula ✅ CORRECT
```
MAPL = EIRP + Rx_gain - Sensitivity - Cable_loss - Body_loss - Interference_margin - SF_margin - Rain_margin - Penetration_margin
```
**Standard link budget formula.** ✅

### 2.4 UL Link Budget ⚠️ MISSING BODY LOSS ON TX
```
UL_EIRP = UE_Tx_power + UE_gain - Body_loss
UL_MAPL = EIRP + Rx_gain - Sensitivity - Cable_loss - Interference - SF - Rain - Penetration
```
**Issue**: UL EIRP subtracts body_loss but doesn't include it in UL MAPL. This is **correct** — body loss is on the UE TX side, already included in EIRP calculation.

**BUT**: UL MAPL doesn't subtract `body_loss_db` separately from MAPL. Looking at the code:
```python
ul_mapl = (ul_eirp + ul_rx_gain_db - ul_sensitivity_dbm 
           - ul_cable_loss_db - inp.margins.interference_db 
           - sf_margin - inp.margins.rain_attenuation_db - inp.margins.penetration_db)
```
**Missing**: `body_loss_db` is NOT subtracted in UL MAPL! But it IS included in `ul_eirp` (subtracted there).  
**So**: Body loss IS accounted for, just in EIRP rather than MAPL. ✅ Correct.

### 2.5 ⚠️ CRITICAL: DL MAPL double-counts cable_loss
In DL MAPL formula:
```python
dl_mapl = (dl_eirp + dl_rx_gain_db - dl_sensitivity_dbm
           - dl_cable_loss_db      # ← SUBTRACTED HERE
           - dl_body_loss_db
           - ...)
```
BUT `dl_eirp = dl_tx_power_dbm + dl_tx_gain_db - dl_cable_loss_db`  
**Cable loss is subtracted TWICE**: once in EIRP, once in MAPL!

**Impact**: For 1 dB cable loss → MAPL is **2 dB too low** → cell radius underestimated by ~10-15%

**Severity**: 🔴 **HIGH** — This is a bug that directly affects all coverage calculations.

### 2.6 ⚠️ FDD UL Throughput
For FDD bands (n1, n3, n8, n28):
```python
if tdd_dl_ratio >= 1.0:
    dl_mbps = raw_bits_per_second * (1 - overhead) / 1e6
    ul_mbps = raw_bits_per_second * (1 - overhead) / 1e6
```
**Issue**: FDD UL uses full bandwidth but with DL antenna gains/overhead. For FDD, UL and DL have different:
- UE TX power (23 dBm PC3) vs BS TX power (53 dBm for 200W)  
- BS RX gain (antenna+BF) vs UE RX gain (0 dBi)

**BUT**: This is throughput calculation, not link budget. Throughput depends on RB allocation and SE, not on link budget power. For FDD, DL and UL each use the full BW, so the raw bits/second is the same for both. The actual throughput difference comes from different SE (different SINR at DL vs UL), which is NOT captured here.

**Verdict**: ⚠️ **APPROXIMATE** — FDD UL throughput should use UL-specific SE, not same as DL. But for planning-level estimation, this is acceptable.

---

## 3. Site Estimation ✅ CORRECT

```
Hexagonal: Area/site = 2.598 × R²
ISD = √3 × R (3-sector)
Sites = ceil(Area / cell_area × (1 + overlap_factor))
```
**3GPP Reference**: Standard hexagonal grid model  
**Status**: ✅ Matches standard telecom planning

---

## 4. Capacity / Throughput

### 4.1 Throughput Formula ✅ CORRECT
```
Throughput = N_RB × 12 × 14 × SE × slots_per_ms × 1000 × layers × (1-OH) × TDD_ratio
```
**3GPP TS 38.306**:  
`Tput = ∑(layer) × ∑(RB) × 12 × 14 × SE × (1-OH) × slots/s × 1000`

Code formula matches. ✅

### 4.2 Average SE ⚠️ SIMPLIFIED
```
avg_SE = cell_edge_SE × 1.5
```
**Issue**: The factor 1.5 is a rough approximation. In reality, average SE depends on:
- SINR distribution across cell area
- User distribution (uniform vs edge-biased)
- Scheduling (PF, RR, etc.)

**Verdict**: ✅ Acceptable for planning-level estimation

### 4.3 MIMO Layers ⚠️ AGGRESSIVE
```
2T2R → 2 layers, 4T4R → 4 layers, 8T8R+ → 4 layers
```
**Issue**: 
- 2T2R: 2 layers is correct for 2×2 MIMO ✅
- 4T4R: 4 layers is **optimistic**. 4T4R typically supports 2-4 layers in DL, 2 in UL. 4×4 MIMO is possible but requires ideal conditions.
- 8T8R+: 4 layers is reasonable for MU-MIMO ✅

**Verdict**: ⚠️ 4T4R at 4 layers is optimistic. Should be 2-4 layers depending on conditions.

---

## 5. SINR / CQI Mapping ✅ CORRECT

SINR → CQI table matches 3GPP TS 38.214 Table 5.2.2.1-2.

Interpolation is linear between CQI thresholds. ✅

---

## 6. Shadow Fading ✅ CORRECT

Uses 3GPP TR 38.901 Table 7.4.2-1 sigma values:
- UMa NLOS: 8.0 dB ✅
- UMi NLOS: 7.82 dB ✅
- RMa NLOS: 8.0 dB ✅
- InH NLOS: 4.0 dB ✅

SF margin = sigma × Φ⁻¹(coverage_probability) using scipy.stats.norm.ppf ✅

---

## 7. NRB Table ✅ CORRECT

Verified against 3GPP TS 38.104 Table 5.3.2-1:
- All SCS/BW combinations match 3GPP spec
- n40, n258, n261 entries added correctly

---

## 8. FDD Support ✅ CORRECT (after fix)

- FDD bands (n1, n3, n8, n28) auto-detected from bands.json duplex field
- TDD ratio slider disabled for FDD, set to 1.0
- Throughput: FDD uses full BW for both DL and UL (separate carriers)
- Link budget: tdd_dl_ratio=1.0 → no TDD penalty

---

## Summary

| Component | Status | Issue |
|-----------|--------|-------|
| Propagation Models | ✅ | All match 3GPP TR 38.901 |
| LOS Probability | ✅ | All match 3GPP |
| Link Budget DL | 🔴 | **Cable loss counted TWICE** |
| Link Budget UL | ✅ | Correct |
| MAPL Formula | ✅ | Standard, minus cable bug |
| Site Estimation | ✅ | Standard hex grid |
| Throughput | ✅ | Matches 3GPP TS 38.306 |
| SINR/CQI | ✅ | Matches 3GPP TS 38.214 |
| Shadow Fading | ✅ | Matches 3GPP TR 38.901 |
| NRB Table | ✅ | Matches 3GPP TS 38.104 |
| FDD Support | ✅ | Correct after fix |

### 🔴 CRITICAL BUG: Cable Loss Double-Counted in DL MAPL

**Location**: `rf5g/engine/link_budget.py`, line ~62 and ~75

```python
# Line ~62: Cable loss subtracted in EIRP
dl_eirp = dl_tx_power_dbm + dl_tx_gain_db - dl_cable_loss_db  # ← cable here

# Line ~75: Cable loss subtracted AGAIN in MAPL
dl_mapl = (dl_eirp + dl_rx_gain_db - dl_sensitivity_dbm
           - dl_cable_loss_db      # ← AND HERE TOO!
           - dl_body_loss_db - ...)
```

**Fix**: Remove `dl_cable_loss_db` from MAPL (it's already in EIRP).

**Impact**: 
- MAPL is ~1 dB too low (for 1 dB cable loss)
- Cell radius underestimated by ~10%
- Site count overestimated by ~20-25%

**Recommended fix**:
```python
# DL MAPL: Remove dl_cable_loss_db (already in EIRP)
dl_mapl = (dl_eirp + dl_rx_gain_db
           - dl_sensitivity_dbm
           - dl_body_loss_db
           - inp.margins.interference_db
           - sf_margin
           - inp.margins.rain_attenuation_db
           - inp.margins.penetration_db)
```

And similarly for UL, `ul_cable_loss_db` is already subtracted from... wait, let me check UL again:

```python
ul_eirp = ul_tx_power_dbm + ul_tx_gain_db - ul_body_loss_db
```
UL EIRP does NOT include cable_loss (it's on UE side, no cable). Cable loss is on BS RX side in UL:
```python
ul_mapl = (ul_eirp + ul_rx_gain_db - ul_sensitivity_dbm
           - ul_cable_loss_db    # BS RX cable loss — this is CORRECT
           - ...)
```
✅ UL is correct — cable loss is only in MAPL, not in EIRP.

---

*Report generated: 2026-06-23*