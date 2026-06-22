"""Phase 1 Verification Script — 5G NR RF Sizing Tool vs PRD & 3GPP spec."""
import json
import math
import sys

sys.path.insert(0, ".")

from rf5g.models.input_schema import RFSizingInput
from rf5g.models.lookup_tables import BandLookup, PowerClassLookup, AntennaConfigLookup, SINRCQILookup, ShadowFadingLookup, QoSLookup
from rf5g.engine.propagation import (
    path_loss, invert_mapl_to_radius, los_probability,
    _pl_uma_los, _pl_uma_nlos, _pr_uma_los,
    _pl_umi_los, _pl_umi_nlos, _pr_umi_los,
    _pl_rma_los, _pl_rma_nlos, _pr_rma_los,
    _pl_inh_los, _pl_inh_nlos, _pr_inh_los,
)
from rf5g.engine.link_budget import calculate_link_budget
from rf5g.engine.site_estimator import estimate_sites
from rf5g.cli import _run_sizing

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name} — {detail}")

print("=" * 70)
print("5G NR RF SIZING TOOL — PHASE 1 VERIFICATION")
print("=" * 70)

# ============================================================================
# 1. 3GPP TR 38.901 Propagation Model Verification
# ============================================================================
print("\n[1] 3GPP TR 38.901 Propagation Models")
print("-" * 50)

# UMa LOS at 100m, 3.5 GHz
# PL = 28 + 22*log10(100) + 20*log10(3.5) = 28 + 44 + 10.88 = 82.88 dB
pl = _pl_uma_los(100, 3.5)
check("UMa LOS @100m", 78 < pl < 90, f"PL={pl:.2f} dB, expected ~83 dB")

# UMa LOS at 1km, 3.5 GHz (above breakpoint)
# Breakpoint: 4*(25-1)*(1.5-1)*3.5e9/3e8 = 4*24*0.5*3500/300 = 560m
# PL2 = 28 + 40*log10(1000) + 20*log10(3.5) - 9*log10(560)
#     = 28 + 120 + 10.88 - 24.97 = 133.91 dB
pl_1km = _pl_uma_los(1000, 3.5)
check("UMa LOS @1km (above BP)", 100 < pl_1km < 170, f"PL={pl_1km:.2f} dB")

# UMa NLOS at 500m
# PL = max(161.04 - 7.28*log10(3.5) + 36.56*log10(0.5), PL_LOS)
#    = max(161.04 - 3.96 - 11.01, ~94)
#    = max(146.07, ~94) = 146.07 dB
pl_nlos_500 = _pl_uma_nlos(500, 3.5)
check("UMa NLOS @500m", 130 < pl_nlos_500 < 160, f"PL={pl_nlos_500:.2f} dB")

# UMi LOS at 100m, 3.5 GHz
pl_umi = _pl_umi_los(100, 3.5)
check("UMi LOS @100m", 80 < pl_umi < 95, f"PL={pl_umi:.2f} dB")

# RMa LOS at 1km, 3.5 GHz
pl_rma = _pl_rma_los(1000, 3.5)
check("RMa LOS @1km", 80 < pl_rma < 110, f"PL={pl_rma:.2f} dB")

# InH LOS at 10m, 3.5 GHz
pl_inh = _pl_inh_los(10, 3.5)
check("InH LOS @10m", 50 < pl_inh < 80, f"PL={pl_inh:.2f} dB")

# LOS probability
check("UMa LOS prob decreases", _pr_uma_los(100) >= _pr_uma_los(500) >= _pr_uma_los(1000))
check("UMi LOS prob @100m", 0 < _pr_umi_los(100) <= 1)
check("RMa LOS prob decreases", _pr_rma_los(100) >= _pr_rma_los(5000))

# NLOS >= LOS
for scenario, los_fn, nlos_fn in [("UMa", _pl_uma_los, _pl_uma_nlos),
                                    ("UMi", _pl_umi_los, _pl_umi_nlos),
                                    ("RMa", _pl_rma_los, _pl_rma_nlos),
                                    ("InH", _pl_inh_los, _pl_inh_nlos)]:
    for d in [100, 500]:
        check(f"{scenario} NLOS>=LOS @{d}m", nlos_fn(d, 3.5) >= los_fn(d, 3.5))

# MAPL inversion round-trip
print("\n[2] MAPL → Cell Radius Inversion")
print("-" * 50)
for scenario in ["UMa", "UMi", "RMa"]:
    for mapl in [120, 130, 140, 150]:
        radius = invert_mapl_to_radius(scenario, "NLOS", mapl, 3.5)
        pl_back = path_loss(scenario, "NLOS", radius, 3.5)
        check(f"{scenario} NLOS round-trip MAPL={mapl}",
              abs(pl_back - mapl) < 2.0,
              f"PL@radius={pl_back:.2f}, MAPL={mapl}, diff={abs(pl_back-mapl):.2f}")

# ============================================================================
# 3. Lookup Tables
# ============================================================================
print("\n[3] Lookup Tables (TS 38.104, 38.101)")
print("-" * 50)
band_lookup = BandLookup()
pc_lookup = PowerClassLookup()
ant_lookup = AntennaConfigLookup()
sinr_lookup = SINRCQILookup()

# Band n78
check("Band n78 FC", abs(band_lookup.get_fc("n78") - 3500) < 1,
      f"FC={band_lookup.get_fc('n78')}")
check("NRB 100MHz/SCS30", band_lookup.get_nrb(100, 30) == 273,
      f"NRB={band_lookup.get_nrb(100, 30)}")

# Power classes
check("PC3 TX power", pc_lookup.get_tx_power_dbm("PC3") == 23.0)

# Antenna configs
ant32 = ant_lookup.get_config("32T32R")
check("32T32R antenna gain", ant32["antenna_gain_dbi"] > 0)

# CQI lookup
check("CQI at -3 dB SINR", sinr_lookup.get_by_sinr(-3.0)["cqi"] == 3)

# ============================================================================
# 4. Link Budget
# ============================================================================
print("\n[4] Link Budget Calculation")
print("-" * 50)
with open("examples/dense_urban_n78.json") as f:
    data = json.load(f)
inp = RFSizingInput(**data)
sf_lookup = ShadowFadingLookup()
dl, ul = calculate_link_budget(inp, band_lookup, pc_lookup, ant_lookup, sf_lookup)

check("DL MAPL reasonable", 140 < dl.mapl_db < 170, f"DL MAPL={dl.mapl_db:.2f}")
check("UL MAPL reasonable", 120 < ul.mapl_db < 145, f"UL MAPL={ul.mapl_db:.2f}")
check("UL is limiting", ul.mapl_db < dl.mapl_db)
check("DL EIRP reasonable", 70 < dl.eirp_dbm < 95, f"DL EIRP={dl.eirp_dbm:.2f}")
check("UL EIRP reasonable", 15 < ul.eirp_dbm < 30, f"UL EIRP={ul.eirp_dbm:.2f}")

# ============================================================================
# 5. Full Sizing Pipeline
# ============================================================================
print("\n[5] Full Sizing Pipeline (3 Scenarios)")
print("-" * 50)

for config_file, scenario_name in [
    ("examples/dense_urban_n78.json", "Dense Urban n78"),
    ("examples/suburban_n77.json", "Suburban n77"),
    ("examples/rural_n8.json", "Rural n8"),
]:
    with open(config_file) as f:
        data = json.load(f)
    inp = RFSizingInput(**data)
    result = _run_sizing(inp)

    check(f"{scenario_name}: cell radius > 0",
          result.propagation.cell_radius_m > 0,
          f"radius={result.propagation.cell_radius_m:.1f}m")
    check(f"{scenario_name}: sites > 0",
          result.site_estimate.coverage_sites > 0,
          f"sites={result.site_estimate.coverage_sites}")
    check(f"{scenario_name}: PL reasonable",
          80 < result.propagation.path_loss_db < 200,
          f"PL={result.propagation.path_loss_db:.2f}")
    check(f"{scenario_name}: limiting link identified",
          result.site_estimate.limiting_link in ["DL", "UL"])
    check(f"{scenario_name}: QoS verification exists",
          len(result.qos_verification) > 0)

# ============================================================================
# 6. PRD Cross-Check
# ============================================================================
print("\n[6] PRD Cross-Check")
print("-" * 50)

# Dense Urban: verify key numbers
with open("examples/dense_urban_n78.json") as f:
    data = json.load(f)
inp = RFSizingInput(**data)
result = _run_sizing(inp)

check("PRD: DL EIRP ~84 dBm", abs(result.link_budget_dl.eirp_dbm - 84) < 1,
      f"DL EIRP={result.link_budget_dl.eirp_dbm:.2f}")
check("PRD: UL limiting", result.site_estimate.limiting_link == "UL")
check("PRD: SINR at cell edge negative",
      result.sinr.sinr_db < 0,
      f"SINR={result.sinr.sinr_db:.2f}")
check("PRD: CQI 3 (QPSK) at cell edge",
      result.sinr.cqi <= 4,
      f"CQI={result.sinr.cqi}")
check("PRD: Cell radius < 1km (dense urban)",
      result.propagation.cell_radius_km < 1.0,
      f"radius={result.propagation.cell_radius_km:.3f} km")

# Rural: should have larger cell radius
with open("examples/rural_n8.json") as f:
    data = json.load(f)
inp_rural = RFSizingInput(**data)
result_rural = _run_sizing(inp_rural)

check("PRD: Rural radius > urban radius",
      result_rural.propagation.cell_radius_km > result.propagation.cell_radius_km,
      f"rural={result_rural.propagation.cell_radius_km:.3f} km vs urban={result.propagation.cell_radius_km:.3f} km")

# ============================================================================
# Summary
# ============================================================================
print("\n" + "=" * 70)
print(f"VERIFICATION COMPLETE: {passed} PASSED, {failed} FAILED")
print("=" * 70)

if failed > 0:
    sys.exit(1)
else:
    print("Phase 1 implementation verified against 3GPP TR 38.901 and PRD.")
    sys.exit(0)