"""Enhanced Streamlit UI — Guided 5G NR RF Sizing with parameter explanations."""
from __future__ import annotations
import json
import math
import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from rf5g.models.input_schema import (
    RFSizingInput, ProjectConfig, EnvironmentConfig, BaseStationConfig,
    FrequencyConfig, UEConfig, MarginsConfig, QoSConfig,
    GeoPoint, GeoPolygon, ExclusionZone, LinearAlignment, PlannedSiteInput,
    PlacementConstraints, TrafficZone, SpatialCapacityConfig,
)
from rf5g.cli import _run_sizing
from rf5g.viz.coverage_map import generate_coverage_map, generate_interactive_map, generate_hex_grid, export_sites_json, export_sites_csv, haversine_km, pattern_for_config
from rf5g.viz.charts import plot_link_budget, plot_sinr_heatmap, plot_service_zones, plot_capacity_comparison
from rf5g.viz.report import generate_html_report, generate_markdown_report
from rf5g.engine.geometry import line_length_km, polygon_area_km2
from rf5g.engine.placement_planner import effective_planning_area_km2

# ── Load Product Catalog ──
try:
    from rf5g.models.antenna_pattern import load_catalog
    _CATALOG = load_catalog()
    _RADIO_VENDORS = sorted(set(r["vendor"] for r in _CATALOG["radios"]))
    _ANTENNA_VENDORS = sorted(set(a["vendor"] for a in _CATALOG["antennas"]))
    _RADIO_MODELS = {}
    for r in _CATALOG["radios"]:
        _RADIO_MODELS.setdefault(r["vendor"], []).append(r["model"])
    _ANTENNA_MODELS = {}
    for a in _CATALOG["antennas"]:
        _ANTENNA_MODELS.setdefault(a["vendor"], []).append(a["model"])
except Exception:
    _RADIO_VENDORS = []
    _ANTENNA_VENDORS = []
    _RADIO_MODELS = {}
    _ANTENNA_MODELS = {}
    _CATALOG = None

# ── Page Config ──
st.set_page_config(
    page_title="5G NR RF Sizing — Guided Mode",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Example Configs with Descriptions ──
EXAMPLES = {
    "🏙️ Dense Urban n78 (Thành phố)": {
        "desc": "Kịch bản mạng đô thị mật độ cao, băng tần n78 (3.5 GHz), 100 MHz bandwidth. "
                "Phù hợp quy hoạch mạng 5G tại trung tâm thành phố (Q1, Q3, Q7 HCM). "
                "UL limiting do UE power thấp → cần nhiều站点, small cells.",
        "config": {
            "project": {"name": "Dense Urban n78", "area_km2": 50.0, "center_lat": 10.78, "center_lon": 106.70},
            "environment": {"scenario": "UMa", "obstacle_density": "heavy", "coverage_probability": 0.95},
            "base_station": {"tx_power_w": 200.0, "antenna_config": "32T32R", "height_m": 25.0, "sectors": 3, "cable_loss_db": 1.0, "noise_figure_db": 3.5},
            "frequency": {"band": "n78", "bandwidth_mhz": 100.0, "scs_khz": 30, "tdd_dl_ratio": 0.70},
            "user_equipment": {"power_class": "PC3", "height_m": 1.5, "noise_figure_db": 7.0},
            "margins": {"interference_db": 3.0, "penetration_db": 10.0, "rain_attenuation_db": 1.0, "overlap_factor": 0.25},
            "qos": {"primary_service": "mixed", "users_per_km2": 300.0, "dl_per_user_mbps": 20.0, "ul_per_user_mbps": 5.0, "concurrent_ratio": 0.10},
        },
    },
    "🏘️ Suburban n77 (Ngoại ô)": {
        "desc": "Kịch bản mạng ngoại ô / khu dân cư, băng tần n77 (3.3 GHz), 50 MHz bandwidth. "
                "Phù hợp quy hoạch 5G tại các khu đô thị mới (Thủ Đức, Bình Dương). "
                "Obstacle density medium, 8T8R antenna.",
        "config": {
            "project": {"name": "Suburban n77", "area_km2": 200.0, "center_lat": 10.85, "center_lon": 106.75},
            "environment": {"scenario": "UMi", "obstacle_density": "medium", "coverage_probability": 0.95},
            "base_station": {"tx_power_w": 200.0, "antenna_config": "8T8R", "height_m": 20.0, "sectors": 3, "cable_loss_db": 1.0, "noise_figure_db": 3.5},
            "frequency": {"band": "n77", "bandwidth_mhz": 50.0, "scs_khz": 30, "tdd_dl_ratio": 0.70},
            "user_equipment": {"power_class": "PC3", "height_m": 1.5, "noise_figure_db": 7.0},
            "margins": {"interference_db": 2.0, "penetration_db": 7.0, "rain_attenuation_db": 0.5, "overlap_factor": 0.20},
            "qos": {"primary_service": "mixed", "users_per_km2": 80.0, "dl_per_user_mbps": 15.0, "ul_per_user_mbps": 3.0, "concurrent_ratio": 0.10},
        },
    },
    "🌾 Rural n8 (Nông thôn)": {
        "desc": "Kịch bản mạng nông thôn / vùng sâu vùng xa, băng tần n8 (900 MHz), 10 MHz bandwidth. "
                "Phù hợp phủ sóng rộng tại ĐBSCL, Tây Nguyên. "
                "RMa propagation, wide coverage nhưng throughput thấp (narrowband).",
        "config": {
            "project": {"name": "Rural n8", "area_km2": 500.0, "center_lat": 10.03, "center_lon": 105.77},
            "environment": {"scenario": "RMa", "obstacle_density": "light", "coverage_probability": 0.90},
            "base_station": {"tx_power_w": 40.0, "antenna_config": "4T4R", "height_m": 35.0, "sectors": 3, "cable_loss_db": 2.0, "noise_figure_db": 3.0},
            "frequency": {"band": "n8", "bandwidth_mhz": 10.0, "scs_khz": 15, "duplex": "FDD", "tdd_dl_ratio": 1.0},
            "user_equipment": {"power_class": "PC3", "height_m": 1.5, "noise_figure_db": 9.0},
            "margins": {"interference_db": 1.0, "penetration_db": 5.0, "rain_attenuation_db": 0.3, "overlap_factor": 0.15},
            "qos": {"primary_service": "data", "users_per_km2": 20.0, "dl_per_user_mbps": 5.0, "ul_per_user_mbps": 1.0, "concurrent_ratio": 0.10},
        },
    },
    "🏢 Indoor InH n78 (Tòa nhà)": {
        "desc": "Kịch bản phủ sóng trong nhà (Indoor Hotspot), băng tần n78, 100 MHz bandwidth. "
                "Phù hợp quy hoạch mạng trong nhà tại trung tâm thương mại, sân bay, nhà ga. "
                "Cell radius rất nhỏ, throughput rất cao.",
        "config": {
            "project": {"name": "Indoor InH n78", "area_km2": 0.05, "center_lat": 10.78, "center_lon": 106.70},
            "environment": {"scenario": "InH", "obstacle_density": "heavy", "coverage_probability": 0.99},
            "base_station": {"tx_power_w": 5.0, "antenna_config": "4T4R", "height_m": 3.0, "sectors": 1, "cable_loss_db": 0.5, "noise_figure_db": 5.0},
            "frequency": {"band": "n78", "bandwidth_mhz": 100.0, "scs_khz": 30, "tdd_dl_ratio": 0.80},
            "user_equipment": {"power_class": "PC3", "height_m": 1.5, "noise_figure_db": 9.0},
            "margins": {"interference_db": 5.0, "penetration_db": 0.0, "rain_attenuation_db": 0.0, "overlap_factor": 0.30},
            "qos": {"primary_service": "video_4k", "users_per_km2": 5000.0, "dl_per_user_mbps": 50.0, "ul_per_user_mbps": 10.0, "concurrent_ratio": 0.20},
        },
    },
    "\U0001f3e0 Rural n28 (700MHz FDD)": {
        "desc": "Kịch bản phủ sóng rộng nông thôn, băng tần n28 (700 MHz), FDD 10 MHz bandwidth. Phù hợp phủ sóng 5G vùng sâu vùng xa (ĐBSCL, Tây Nguyên). FDD mode — full duplex, UL throughput bằng DL.",
        "config": {
            "project": {"name": "Rural n28", "area_km2": 500.0, "center_lat": 10.03, "center_lon": 105.77},
            "environment": {"scenario": "RMa", "obstacle_density": "light", "coverage_probability": 0.90},
            "base_station": {"tx_power_w": 40.0, "antenna_config": "4T4R", "height_m": 35.0, "sectors": 3, "cable_loss_db": 2.0, "noise_figure_db": 3.0},
            "frequency": {"band": "n28", "bandwidth_mhz": 10.0, "scs_khz": 15, "duplex": "FDD", "tdd_dl_ratio": 1.0},
            "user_equipment": {"power_class": "PC3", "height_m": 1.5, "noise_figure_db": 9.0},
            "margins": {"interference_db": 1.0, "penetration_db": 5.0, "rain_attenuation_db": 0.3, "overlap_factor": 0.15},
            "qos": {"primary_service": "data", "users_per_km2": 20.0, "dl_per_user_mbps": 5.0, "ul_per_user_mbps": 1.0, "concurrent_ratio": 0.10},
        },
    },
    "\U0001f310 Urban n40 (2.3GHz TDD)": {
        "desc": "Kịch bản đô thị băng tần n40 (2.3 GHz), TDD 20 MHz bandwidth. Phù hợp quy hoạch 5G tại khu đô thị Việt Nam (Viettel n40 2300-2310 MHz). TDD mid-band, cân bằng coverage và capacity.",
        "config": {
            "project": {"name": "Urban n40", "area_km2": 50.0, "center_lat": 10.78, "center_lon": 106.70},
            "environment": {"scenario": "UMa", "obstacle_density": "heavy", "coverage_probability": 0.95},
            "base_station": {"tx_power_w": 100.0, "antenna_config": "32T32R", "height_m": 25.0, "sectors": 3, "cable_loss_db": 1.0, "noise_figure_db": 3.5},
            "frequency": {"band": "n40", "bandwidth_mhz": 20.0, "scs_khz": 30, "duplex": "TDD", "tdd_dl_ratio": 0.70},
            "user_equipment": {"power_class": "PC3", "height_m": 1.5, "noise_figure_db": 7.0},
            "margins": {"interference_db": 3.0, "penetration_db": 10.0, "rain_attenuation_db": 1.0, "overlap_factor": 0.25},
            "qos": {"primary_service": "data", "users_per_km2": 300.0, "dl_per_user_mbps": 20.0, "ul_per_user_mbps": 5.0, "concurrent_ratio": 0.10},
        },
    },
    "\U0001f4e1 mmWave n258 (26GHz)": {
        "desc": "Kịch bản mmWave băng tần n258 (24.25-27.5 GHz), 100 MHz bandwidth. Phù hợp hotspot density cao (quận 1, khu thương mại). Coverage rất ngắn nhưng throughput rất cao (Gbps). Viettel n258 24250-26500 MHz, VNPT n258 26500-27500 MHz.",
        "config": {
            "project": {"name": "Hotspot n258 mmWave", "area_km2": 5.0, "center_lat": 10.78, "center_lon": 106.70},
            "environment": {"scenario": "UMi", "obstacle_density": "heavy", "coverage_probability": 0.90},
            "base_station": {"tx_power_w": 10.0, "antenna_config": "4T4R", "height_m": 6.0, "sectors": 1, "cable_loss_db": 0.5, "noise_figure_db": 5.0},
            "frequency": {"band": "n258", "bandwidth_mhz": 100.0, "scs_khz": 120, "duplex": "TDD", "tdd_dl_ratio": 0.70},
            "user_equipment": {"power_class": "PC3", "height_m": 1.5, "noise_figure_db": 10.0},
            "margins": {"interference_db": 5.0, "penetration_db": 20.0, "rain_attenuation_db": 5.0, "overlap_factor": 0.30},
            "qos": {"primary_service": "video_4k", "users_per_km2": 1000.0, "dl_per_user_mbps": 100.0, "ul_per_user_mbps": 20.0, "concurrent_ratio": 0.15},
        },
    },
    "\U0001f682 FRMCS n101 (1.9GHz Railway)": {
        "desc": "Kịch bản FRMCS (Future Railway Mobile Communication System) băng tần n101 (1900-1910 MHz TDD). "
                "Dành riêng cho thông tin liên lạc đường sắt (ETCS/TCMS voice & data). "
                "BW tối đa 10 MHz, SCS 15/30 kHz. Phù hợp phủ sóng dọc tuyến đường sắt.",
        "config": {
            "project": {"name": "FRMCS n101 Railway", "area_km2": 200.0, "center_lat": 10.78, "center_lon": 106.70},
            "environment": {"scenario": "RMa", "obstacle_density": "light", "coverage_probability": 0.99},
            "base_station": {"tx_power_w": 40.0, "antenna_config": "4T4R", "height_m": 25.0, "sectors": 3, "cable_loss_db": 1.0, "noise_figure_db": 3.5},
            "frequency": {"band": "n101", "bandwidth_mhz": 10.0, "scs_khz": 30, "duplex": "TDD", "tdd_dl_ratio": 0.70},
            "user_equipment": {"power_class": "PC3", "height_m": 3.0, "noise_figure_db": 7.0},
            "margins": {"interference_db": 3.0, "penetration_db": 5.0, "rain_attenuation_db": 0.5, "overlap_factor": 0.20},
            "qos": {"primary_service": "vonr", "users_per_km2": 20.0, "dl_per_user_mbps": 10.0, "ul_per_user_mbps": 5.0, "concurrent_ratio": 0.30},
        },
    },
    "📶 Sub6 GHz n41 (TDD Mid-band)": {
        "desc": "Kịch bản băng tần n41 (2.5 GHz), phổ biến tại Mỹ và một số thị trường. "
                "TDD mid-band, phù hợp quy hoạch mạng đô thị vừa. "
                "Cân bằng giữa coverage và capacity.",
        "config": {
            "project": {"name": "Urban n41", "area_km2": 100.0, "center_lat": 10.78, "center_lon": 106.70},
            "environment": {"scenario": "UMa", "obstacle_density": "medium", "coverage_probability": 0.95},
            "base_station": {"tx_power_w": 160.0, "antenna_config": "64T64R", "height_m": 30.0, "sectors": 3, "cable_loss_db": 1.0, "noise_figure_db": 3.5},
            "frequency": {"band": "n41", "bandwidth_mhz": 80.0, "scs_khz": 30, "tdd_dl_ratio": 0.70},
            "user_equipment": {"power_class": "PC3", "height_m": 1.5, "noise_figure_db": 7.0},
            "margins": {"interference_db": 3.0, "penetration_db": 8.0, "rain_attenuation_db": 0.8, "overlap_factor": 0.25},
            "qos": {"primary_service": "mixed", "users_per_km2": 150.0, "dl_per_user_mbps": 25.0, "ul_per_user_mbps": 5.0, "concurrent_ratio": 0.12},
        },
    },
}

# ── Parameter Explanations ──
PARAM_HELP = {
    # Project
    "project.name": "🏗️ **Tên dự án** — Tên gợi nhớ cho kịch bản sizing (VD: 'HCMC Q1 5G Plan')",
    "project.area_km2": "📐 **Diện tích phủ sóng** (km²) — Tổng diện tích cần phủ sóng. "
                        "Cell radius × số cells phải đủ phủ diện tích này.\n\n"
                        "• Nội thành HCM Q1: ~5-10 km²\n• Quận trung tâm: ~20-50 km²\n• Tỉnh: ~500-5000 km²",
    "project.center_lat": "📍 **Vĩ độ tâm** — Vị trí trung tâm vùng phủ sóng, dùng cho bản đồ.",
    "project.center_lon": "📍 **Kinh độ tâm** — Vị trí trung tâm vùng phủ sóng, dùng cho bản đồ.",
    # Environment
    "environment.scenario": "🏙️ **Kịch bản truyền sóng** (3GPP TR 38.901)\n\n"
                           "• **UMa** (Urban Macro): BS cao 25m+, cell lớn, đô thị. Phù hợp macrocell phủ sóng thành phố.\n"
                           "• **UMi** (Urban Micro): BS thấp 10m, cell nhỏ, đô thị dày. Phù hợp small cell, hotzone.\n"
                           "• **RMa** (Rural Macro): Vùng nông thôn, cell rất lớn (km). Phù hợp phủ sóng rộng.\n"
                           "• **InH** (Indoor Hotspot): Trong nhà, cell rất nhỏ (10-50m). Phù hợp mall, airport.",
    "environment.obstacle_density": "🏢 **Mật độ vật cản** — Ảnh hưởng shadow fading margin.\n\n"
                                    "• **heavy**: Dense urban, nhiều tòa nhà cao → SF margin cao (8-10 dB)\n"
                                    "• **medium**: Suburban, nhà thấp, cây xanh → SF vừa (4-6 dB)\n"
                                    "• **light**: Rural, đồng bằng, ít vật cản → SF thấp (2-4 dB)",
    "environment.coverage_probability": "📊 **Xác suất phủ sóng** — Tỷ lệ cell edge user đạt throughput tối thiểu.\n\n"
                                      "• 0.90 (90%): Rural, yêu cầu thấp\n• 0.95 (95%): Tiêu chuẩn đô thị\n• 0.99 (99%): Indoor, mission-critical",
    # Base Station
    "base_station.tx_power_w": "📡 **Công suất phát BS** (Watt tổng / sector) — tổng công suất trên tất cả TX ports, dùng trực tiếp trong EIRP = 10·log10(P) + antenna_gain.\n\n"
                               "• 5W: Small cell, indoor\n• 40W: Rural macro\n• 100W: Urban macro\n• 200W: Dense urban, 32T32R+\n• 320W: 64T64R MU-MIMO",
    "base_station.antenna_config": "📶 **Cấu hình antenna** — Số TX/RX chains, ảnh hưởng gain và MIMO layers.\n\n"
                                  "• **2T2R**: Small cell, rural repeater. Gain thấp.\n• **4T4R**: Rural macro, low-cost. Gain ~11 dBi.\n• **8T8R**: Suburban, small cell. Gain ~14 dBi.\n• **16T16R**: Urban, mid-range. Gain ~17 dBi.\n• **32T32R**: Dense urban, MU-MIMO. Gain ~20 dBi.\n• **64T64R**: High-capacity urban. Gain ~23 dBi.",
    "base_station.height_m": "🏗️ **Chiều cao BS** (m) — Ảnh hưởng breakpoint distance và LOS probability.\n\n"
                            "• UMa: 25m (tiêu chuẩn)\n• UMi: 10m (lamppost)\n• RMa: 35m (tháp)\n• InH: 3m (trần nhà)",
    "base_station.sectors": "🔄 **Số sector** — Số sector/cell site.\n\n"
                           "• 1: Omni-directional (360°)\n• 3: Tri-sectored (120° mỗi sector) — phổ biến nhất\n• 6: Hex-sectored (60° mỗi sector) — high capacity",
    "base_station.cable_loss_db": "🔌 **Cable loss** (dB) — Suy hao cáp từ BS đến antenna. Thường 0.5-3 dB.",
    "base_station.noise_figure_db": "🔇 **Noise figure BS** (dB) — Nhiễu nội bộ receiver. Thường 2.5-5 dB.",
    # Frequency
    "frequency.band": "📻 **NR Band** — Băng tần 5G.\n\n"
                      "• **n78** (3.5 GHz): TDD mid-band, phổ biến nhất VN. BW: 10-100 MHz.\n"
                      "• **n77** (3.3 GHz): TDD mid-band, tương tự n78. BW: 10-100 MHz.\n"
                      "• **n41** (2.5 GHz): TDD mid-band, Mỹ. BW: 5-100 MHz.\n"
                      "• **n8** (900 MHz): FDD low-band, phủ sóng nông thôn. BW: 5-10 MHz.\n"
                      "• **n28** (700 MHz): FDD low-band, phủ sóng rộng. BW: 5-20 MHz.\n"
                      "• **n1** (2.1 GHz): FDD mid-band. BW: 5-20 MHz.\n"
                      "• **n3** (1.8 GHz): FDD mid-band. BW: 5-30 MHz.",
    "frequency.bandwidth_mhz": "📊 **Bandwidth** (MHz) — Độ rộng kênh. Càng lớn → throughput càng cao nhưng cần nhiều spectrum.\n\n"
                              "• n78: 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 100 MHz\n"
                              "• n8: 5, 10 MHz\n"
                              "• n41: 5-100 MHz",
    "frequency.scs_khz": "📈 **SCS** (kHz) — Sub-Carrier Spacing.\n\n"
                         "• 15 kHz: Low-band (n8, n28), FDD\n• 30 kHz: Mid-band (n78, n77), TDD — phổ biến nhất\n• 60 kHz: mmWave, high-mobility\n• 120 kHz: mmWave chỉ",
    "frequency.tdd_dl_ratio": "⬇️ **TDD DL Ratio** — Tỷ lệ tài nguyên downlink.\n\n"
                             "• 0.50: Balanced (50/50 UL/DL)\n• 0.70: Standard TDD (70/30) — phổ biến nhất\n• 0.80: DL-heavy (80/20) — streaming/video\n• 0.90: Maximum DL (90/10)",
    # UE
    "user_equipment.power_class": "📱 **UE Power Class** — Công suất phát tối đa của thiết bị đầu cuối.\n\n"
                                  "• **PC1** (31 dBm / ~1.3W): Vehicle-mounted, fixed CPE\n• **PC2** (26 dBm / ~400mW): High-power UE\n• **PC3** (23 dBm / ~200mW): Standard smartphone — phổ biến nhất\n• **PC4** (20 dBm / ~100mW): Low-power IoT",
    "user_equipment.height_m": "📏 **Chiều cao UE** (m) — Thường 1.5m (người đứng). Ảnh hưởng LOS probability.",
    "user_equipment.noise_figure_db": "🔇 **UE Noise Figure** (dB) — Nhiễu nội bộ UE. Smartphone: 7-9 dB, CPE: 5-7 dB.",
    # Margins
    "margins.interference_db": "⚡ **Interference Margin** (dB) — Dự trừ cho nhiễu đồng kênh.\n\n"
                               "• 1-2 dB: Rural, ít site\n• 3 dB: Tiêu chuẩn đô thị\n• 5-6 dB: Dense urban, nhiều site",
    "margins.penetration_db": "🏠 **Penetration Loss** (dB) — Suy hao xuyên qua tường nhà.\n\n"
                              "• 0 dB: Outdoor only\n• 5-7 dB: Wood/drywall (suburban)\n• 10-12 dB: Brick/concrete (urban)\n• 15-20 dB: Thick concrete, basement",
    "margins.rain_attenuation_db": "🌧️ **Rain Attenuation** (dB) — Suy hao mưa.\n\n"
                                   "• 0-0.5 dB: Tần số thấp (n8, n28)\n• 0.5-1 dB: Mid-band (n78, n77)\n• 2-5 dB: mmWave (n257+)",
    "margins.overlap_factor": "🔄 **Overlap Factor** — Tỷ lệ overlap giữa các cell.\n\n"
                              "• 0.10: Rural, ít overlap\n• 0.25: Tiêu chuẩn\n• 0.35: Dense urban, nhiều handover",
    # QoS
    "qos.primary_service": "🎯 **Primary Service** — Dịch vụ chính cần tối ưu.\n\n"
                           "• **mixed**: Kiểm tra tất cả 6 dịch vụ\n• **vonr**: Voice over NR (SINR ≥ -3 dB)\n• **video_hd**: HD video streaming (SINR ≥ 5 dB)\n• **video_4k**: 4K video (SINR ≥ 10 dB)\n• **data**: Basic data (SINR ≥ 0 dB)\n• **gaming**: Low-latency gaming (SINR ≥ 8 dB)\n• **iot**: IoT sensors (SINR ≥ -5 dB)",
    "qos.users_per_km2": "👥 **Users per km²** — Mật độ user trong vùng phủ sóng.\n\n"
                         "• 20: Rural, ít user\n• 80: Suburban\n• 300: Dense urban\n• 500-1000: Stadium, mall\n• 5000: Indoor hotspot",
    "qos.dl_per_user_mbps": "⬇️ **DL per User** (Mbps) — Throughput downlink mỗi user active.\n\n"
                            "• 5 Mbps: Basic data, rural\n• 10-20 Mbps: Standard urban\n• 50 Mbps: Premium/video\n• 100 Mbps: High-speed",
    "qos.ul_per_user_mbps": "⬆️ **UL per User** (Mbps) — Throughput uplink mỗi user active.\n\n"
                            "• 1 Mbps: IoT, basic\n• 3-5 Mbps: Standard\n• 10 Mbps: Video call, streaming",
    "qos.concurrent_ratio": "📊 **Concurrent Ratio** — Tỷ lệ user active cùng lúc.\n\n"
                            "• 0.05 (5%): Rural, ít user\n• 0.10 (10%): Tiêu chuẩn\n• 0.20 (20%): Peak hour\n• 0.50 (50%): Stadium, event",
}

# ── Helper: Get param help ──
def get_help(key: str) -> str:
    return PARAM_HELP.get(key, "")

# ── Session State ──
def init_state():
    defaults = {
        "selected_example": None,
        "result": None,
        "input": None,
        "calculated": False,
        "compare_runs": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _approximate_service_area_polygon(center_lat: float, center_lon: float, area_km2: float, vertices: int = 16) -> dict:
    radius_km = math.sqrt(area_km2 / math.pi)
    points = []
    for idx in range(vertices):
        angle = 2 * math.pi * idx / vertices
        lat = center_lat + radius_km * math.cos(angle) / 111.0
        lon = center_lon + radius_km * math.sin(angle) / (111.320 * math.cos(math.radians(center_lat)))
        points.append({"lat": round(lat, 6), "lon": round(lon, 6)})
    return {"outer": points, "name": "Approximate service area"}


def _parse_json_text(raw: str, expected_type: type, field_label: str):
    if not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_label}: JSON không hợp lệ ({exc})") from exc
    if not isinstance(parsed, expected_type):
        type_name = "object" if expected_type is dict else "array"
        raise ValueError(f"{field_label}: phải là JSON {type_name}")
    return parsed


def _polygon_points_to_text(service_area: dict | None) -> str:
    if not service_area or not service_area.get("outer"):
        return ""
    return "\n".join(f"{point['lat']:.6f}, {point['lon']:.6f}" for point in service_area["outer"])


def _parse_polygon_points_text(raw: str, field_label: str) -> dict:
    points = []
    for line_no, raw_line in enumerate(raw.strip().splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.replace(";", ",").split(",") if part.strip()]
        if len(parts) == 1:
            parts = line.split()
        if len(parts) < 2:
            raise ValueError(f"{field_label}: dòng {line_no} phải có định dạng `lat, lon`")
        try:
            lat = float(parts[0])
            lon = float(parts[1])
        except ValueError as exc:
            raise ValueError(f"{field_label}: dòng {line_no} có lat/lon không hợp lệ") from exc
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError(f"{field_label}: dòng {line_no} có lat/lon ngoài phạm vi")
        points.append({"lat": round(lat, 6), "lon": round(lon, 6)})
    if len(points) < 3:
        raise ValueError(f"{field_label}: cần ít nhất 3 điểm để tạo polygon")
    return {"outer": points, "name": "Ordered points polygon"}


def _catalog_override_preview(radio_vendor: str | None, radio_model: str | None, ant_vendor: str | None, ant_model: str | None, manual_tx_power_w: float, manual_antenna_config: str) -> dict:
    preview = {
        "radio": None,
        "antenna": None,
        "effective_tx_power_w": manual_tx_power_w,
        "effective_antenna_config": manual_antenna_config,
        "notes": [],
    }
    if radio_vendor and radio_model:
        try:
            from rf5g.models.antenna_pattern import get_catalog_radio, resolve_catalog_radio_total_tx_power_w
            radio = get_catalog_radio(radio_vendor, radio_model)
            preview["radio"] = f"{radio['vendor']} {radio['model']}"
            total_tx_power_w = resolve_catalog_radio_total_tx_power_w(radio)
            if total_tx_power_w is not None and abs(total_tx_power_w - manual_tx_power_w) > 1e-6:
                preview["effective_tx_power_w"] = total_tx_power_w
                preview["notes"].append(f"Catalog radio override TX power → {total_tx_power_w:g}W")
            mimo_config = radio.get("mimo_config")
            if mimo_config and mimo_config != manual_antenna_config:
                preview["effective_antenna_config"] = mimo_config
                preview["notes"].append(f"Catalog radio suggests antenna config {mimo_config}")
        except Exception:
            pass
    if ant_vendor and ant_model:
        preview["antenna"] = f"{ant_vendor} {ant_model}"
    return preview


init_state()

# ── Header ──
st.title("📡 5G NR RF Coverage Sizing Tool")
st.caption("**3GPP TR 38.901** | TS 38.104, 38.214, 38.306 | Guided Mode — Giải thích từng tham số")

# ══════════════════════════════════════════════
# STEP 1: Chọn kịch bản mẫu
# ══════════════════════════════════════════════
st.header("📋 Bước 1: Chọn kịch bản mẫu")

st.markdown("Chọn một kịch bản mẫu để bắt đầu, sau đó tùy chỉnh các tham số. "
            "Mỗi kịch bản có mô tả chi tiết và tham số phù hợp.")

example_cols = st.columns(len(EXAMPLES))
selected_key = None

for i, (key, val) in enumerate(EXAMPLES.items()):
    with example_cols[i]:
        if st.button(key, key=f"ex_{i}"):
            st.session_state["selected_example"] = key
            st.session_state["calculated"] = False
            st.session_state["result"] = None
        if st.session_state.get("selected_example") == key:
            st.markdown(f"✅ **Đã chọn**")

# Show description of selected example
selected = st.session_state.get("selected_example")
if selected and selected in EXAMPLES:
    st.info(EXAMPLES[selected]["desc"])

planning_shell = st.radio(
    "Chế độ làm việc",
    ["Standard sizing", "Geometry-aware planning"],
    horizontal=True,
    index=1,
    help="Standard sizing phù hợp sizing RF nhanh. Geometry-aware planning mở khóa polygon, exclusion, alignment, traffic zone và planning objective.",
)
if planning_shell == "Geometry-aware planning":
    st.caption("🧭 Guided Mode đang hoạt động như một planning workflow cho Phase C/D.")
else:
    st.caption("⚡ Standard sizing giữ trải nghiệm cấu hình nhanh. Với planning nâng cao, nên dùng Geometry-aware planning.")

st.divider()

# ══════════════════════════════════════════════
# STEP 2: Cấu hình tham số (with explanations)
# ══════════════════════════════════════════════
st.header("⚙️ Bước 2: Tùy chỉnh tham số")

st.markdown("Mỗi tham số có giải thích chi tiết. Click vào ℹ️ hoặc hover để xem.")

# Load defaults from selected example or blank
if selected and selected in EXAMPLES:
    cfg = EXAMPLES[selected]["config"]
    defaults = {
        "project_name": cfg["project"]["name"],
        "area_km2": cfg["project"]["area_km2"],
        "center_lat": cfg["project"].get("center_lat", 10.8231),
        "center_lon": cfg["project"].get("center_lon", 106.6297),
        "scenario": cfg["environment"]["scenario"],
        "obstacle_density": cfg["environment"]["obstacle_density"],
        "coverage_probability": cfg["environment"]["coverage_probability"],
        "tx_power_w": cfg["base_station"]["tx_power_w"],
        "antenna_config": cfg["base_station"]["antenna_config"],
        "bs_height_m": cfg["base_station"]["height_m"],
        "sectors": cfg["base_station"]["sectors"],
        "cable_loss_db": cfg["base_station"]["cable_loss_db"],
        "bs_noise_figure_db": cfg["base_station"]["noise_figure_db"],
        "band": cfg["frequency"]["band"],
        "bandwidth_mhz": cfg["frequency"]["bandwidth_mhz"],
        "scs_khz": cfg["frequency"]["scs_khz"],
        "tdd_dl_ratio": cfg["frequency"]["tdd_dl_ratio"],
        "power_class": cfg["user_equipment"]["power_class"],
        "ue_height_m": cfg["user_equipment"]["height_m"],
        "ue_noise_figure_db": cfg["user_equipment"]["noise_figure_db"],
        "interference_db": cfg["margins"]["interference_db"],
        "penetration_db": cfg["margins"]["penetration_db"],
        "rain_attenuation_db": cfg["margins"]["rain_attenuation_db"],
        "overlap_factor": cfg["margins"]["overlap_factor"],
        "primary_service": cfg["qos"]["primary_service"],
        "users_per_km2": cfg["qos"]["users_per_km2"],
        "dl_per_user_mbps": cfg["qos"]["dl_per_user_mbps"],
        "ul_per_user_mbps": cfg["qos"]["ul_per_user_mbps"],
        "concurrent_ratio": cfg["qos"]["concurrent_ratio"],
    }
else:
    defaults = {
        "project_name": "Dense Urban n78", "area_km2": 50.0, "center_lat": 10.8231, "center_lon": 106.6297,
        "scenario": "UMa", "obstacle_density": "heavy", "coverage_probability": 0.95,
        "tx_power_w": 200.0, "antenna_config": "32T32R", "bs_height_m": 25.0, "sectors": 3,
        "cable_loss_db": 1.0, "bs_noise_figure_db": 3.5,
        "band": "n78", "bandwidth_mhz": 100.0, "scs_khz": 30, "tdd_dl_ratio": 0.70,
        "power_class": "PC3", "ue_height_m": 1.5, "ue_noise_figure_db": 7.0,
        "interference_db": 3.0, "penetration_db": 10.0, "rain_attenuation_db": 1.0, "overlap_factor": 0.25,
        "primary_service": "mixed", "users_per_km2": 300.0,
        "dl_per_user_mbps": 20.0, "ul_per_user_mbps": 5.0, "concurrent_ratio": 0.10,
    }

loaded_config = st.session_state.get("loaded_config", {})
loaded_placement = loaded_config.get("placement", {}) if isinstance(loaded_config, dict) else {}
loaded_spatial = loaded_config.get("spatial_capacity", {}) if isinstance(loaded_config, dict) else {}

# ── Project ──
with st.expander("📍 Project — Thông tin dự án", expanded=True):
    c1, c2, c3 = st.columns(3)
    project_name = c1.text_input("Tên dự án", value=defaults["project_name"], help=get_help("project.name"))
    area_km2 = c2.number_input("Diện tích (km²)", min_value=0.1, value=defaults["area_km2"], step=1.0, help=get_help("project.area_km2"))
    center_lat = c3.number_input("Vĩ độ tâm", value=float(defaults["center_lat"]), step=0.000001, format="%.6f", help=get_help("project.center_lat"))
    center_lon = st.number_input("Kinh độ tâm", value=float(defaults["center_lon"]), step=0.000001, format="%.6f", help=get_help("project.center_lon"))

# ── Environment ──
with st.expander("🏙️ Environment — Môi trường truyền sóng", expanded=True):
    c1, c2, c3 = st.columns(3)
    scenario = c1.selectbox("Scenario", ["UMa", "UMi", "RMa", "InH"], index=["UMa", "UMi", "RMa", "InH"].index(defaults["scenario"]), help=get_help("environment.scenario"))
    obstacle_density = c2.selectbox("Mật độ vật cản", ["heavy", "medium", "light"], index=["heavy", "medium", "light"].index(defaults["obstacle_density"]), help=get_help("environment.obstacle_density"))
    coverage_probability = c3.slider("Xác suất phủ sóng", min_value=0.80, max_value=0.99, value=defaults["coverage_probability"], step=0.01, help=get_help("environment.coverage_probability"))

# ── Base Station ──
with st.expander("📡 Base Station — Trạm phát", expanded=True):
    c1, c2, c3 = st.columns(3)
    tx_power_w = c1.number_input("Công suất phát (W)", min_value=1.0, value=defaults["tx_power_w"], step=10.0, help=get_help("base_station.tx_power_w"))
    antenna_config = c2.selectbox("Antenna Config", ["2T2R", "4T4R", "8T8R", "16T16R", "32T32R", "64T64R"], index=["2T2R", "4T4R", "8T8R", "16T16R", "32T32R", "64T64R"].index(defaults["antenna_config"]), help=get_help("base_station.antenna_config"))
    bs_height_m = c3.number_input("Chiều cao BS (m)", min_value=1.0, value=defaults["bs_height_m"], step=1.0, help=get_help("base_station.height_m"))
    c4, c5, c6 = st.columns(3)
    sectors = c4.selectbox("Sectors", [1, 3, 6], index=[1, 3, 6].index(defaults["sectors"]), help=get_help("base_station.sectors"))
    cable_loss_db = c5.number_input("Cable loss (dB)", min_value=0.0, value=defaults["cable_loss_db"], step=0.1, help=get_help("base_station.cable_loss_db"))
    bs_noise_figure_db = c6.number_input("BS Noise Figure (dB)", min_value=0.0, value=defaults["bs_noise_figure_db"], step=0.5, help=get_help("base_station.noise_figure_db"))

    # ── Product Catalog Selection ──
    if _CATALOG:
        st.markdown("---")
        st.markdown("**🔧 Chọn Radio & Antenna từ Catalog** (thông số tự động override)")
        radio_vendor = st.selectbox(
            "Radio Vendor",
            ["— None —"] + _RADIO_VENDORS,
            index=0,
            help="Chọn nhà sản xuất Radio. TX power, MIMO config sẽ tự động cập nhật từ datasheet.",
        )
        if radio_vendor != "— None —" and radio_vendor in _RADIO_MODELS:
            r_models = _RADIO_MODELS[radio_vendor]
            radio_model = st.selectbox(
                "Radio Model",
                ["— Select —"] + r_models,
                index=0,
                help=f"{radio_vendor} radio models từ catalog.",
            )
            if radio_model != "— Select —":
                # Show radio specs
                from rf5g.models.antenna_pattern import get_catalog_radio, resolve_catalog_radio_total_tx_power_w
                try:
                    r_spec = get_catalog_radio(radio_vendor, radio_model)
                    total_tx_power_w = resolve_catalog_radio_total_tx_power_w(r_spec)
                    if r_spec.get("max_total_power_w") is not None and r_spec.get("max_tx_power_w") is not None and r_spec.get("tx_ports"):
                        power_caption = f"{r_spec['max_tx_power_w']}W/port × {r_spec['tx_ports']} = {total_tx_power_w:g}W total"
                    elif total_tx_power_w is not None:
                        power_caption = f"{total_tx_power_w:g}W total"
                    else:
                        power_caption = "TX power unavailable"
                    st.caption(f"📡 {r_spec['vendor']} {r_spec['model']}: {r_spec['mimo_config']}, "
                              f"{power_caption}, {r_spec['frequency_bands']}, {r_spec['weight_kg']}kg")
                    # Auto-set tx_power_w and antenna_config from radio spec
                    if total_tx_power_w is not None:
                        tx_power_w = total_tx_power_w
                    if r_spec.get("mimo_config"):
                        mimo_map = {"2T2R": "2T2R", "4T4R": "4T4R", "8T8R": "8T8R",
                                    "16T16R": "16T16R", "32T32R": "32T32R", "64T64R": "64T64R"}
                        ac = mimo_map.get(r_spec["mimo_config"], antenna_config)
                        if ac in ["2T2R", "4T4R", "8T8R", "16T16R", "32T32R", "64T64R"]:
                            antenna_config = ac
                except Exception:
                    pass
        else:
            radio_model = None

        ant_vendor = st.selectbox(
            "Antenna Vendor",
            ["— None —"] + _ANTENNA_VENDORS,
            index=0,
            help="Chọn nhà sản xuất Antenna. Gain, beamwidth sẽ tự động cập nhật từ datasheet.",
        )
        if ant_vendor != "— None —" and ant_vendor in _ANTENNA_MODELS:
            a_models = _ANTENNA_MODELS[ant_vendor]
            antenna_model = st.selectbox(
                "Antenna Model",
                ["— Select —"] + a_models,
                index=0,
                help=f"{ant_vendor} antenna models từ catalog.",
            )
            if antenna_model != "— Select —":
                from rf5g.models.antenna_pattern import get_catalog_antenna
                try:
                    a_spec = get_catalog_antenna(ant_vendor, antenna_model)
                    gain_str = f"{a_spec['gain_dbi']} dBi" if a_spec.get('gain_dbi') else 'N/A'
                    bw_str = f"H:{a_spec.get('h_beamwidth_deg', '?')}° V:{a_spec.get('v_beamwidth_deg', '?')}°" if a_spec.get('h_beamwidth_deg') else ''
                    subband_str = ''
                    if a_spec.get('subbands'):
                        bands = [f"{s['range_mhz'][0]}-{s['range_mhz'][1]} MHz ({s.get('gain_dbi','?')} dBi)" for s in a_spec['subbands']]
                        subband_str = f" | Bands: {', '.join(bands)}"
                    st.caption(f"📶 {a_spec['vendor']} {a_spec['model']}: {a_spec['type']} {gain_str} {bw_str}{subband_str}")
                except Exception:
                    pass
        else:
            antenna_model = None
    else:
        radio_vendor = None
        radio_model = None
        ant_vendor = None
        antenna_model = None

    st.markdown("---")
    st.markdown("**🧪 Custom antenna pattern (optional)**")
    custom_pattern_upload = st.file_uploader(
        "Upload antenna pattern (.ant, .csv, .json, .msi, .txt)",
        type=["ant", "csv", "json", "msi", "txt"],
        key="guided_custom_pattern_upload",
        help="Ưu tiên cao nhất: nếu upload custom pattern, runtime sẽ dùng pattern này thay vì catalog antenna pattern. Hữu ích cho antenna có radiation pattern đặc thù.",
    )
    custom_pattern_format = st.selectbox(
        "Custom pattern format",
        ["auto", "ant", "csv", "json", "msi", "atoll_txt"],
        index=0,
        help="Chọn format nếu muốn override auto-detection. `.txt` có thể là MSI-like hoặc Atoll text.",
    )
    custom_pattern_name = st.text_input(
        "Custom pattern row/name (optional)",
        value="",
        help="Dùng khi file Atoll text có nhiều row/pattern và bạn muốn chỉ rõ row name.",
    )
    custom_pattern_freq_mhz = st.number_input(
        "Custom pattern frequency hint (MHz)",
        min_value=0.0,
        value=0.0,
        step=10.0,
        help="Dùng để chọn row gần tần số nhất khi file pattern có nhiều frequency entries.",
    )

    _custom_pattern_file = None
    if custom_pattern_upload is not None:
        upload_dir = Path('/Users/namnguyen/rf5g-sizing/.tmp_import/custom_patterns')
        upload_dir.mkdir(parents=True, exist_ok=True)
        upload_path = upload_dir / custom_pattern_upload.name
        upload_path.write_bytes(custom_pattern_upload.getvalue())
        _custom_pattern_file = str(upload_path)
        st.caption(f"Loaded custom pattern asset: {upload_path.name}")

    # Collect catalog selections for build_input
    _catalog_radio_vendor = radio_vendor if (radio_vendor and radio_vendor != "— None —") else None
    _catalog_radio_model = radio_model if (radio_model and radio_model != "— Select —") else None
    _catalog_ant_vendor = ant_vendor if (ant_vendor and ant_vendor != "— None —") else None
    _catalog_ant_model = antenna_model if (antenna_model and antenna_model != "— Select —") else None

# ── Frequency ──
with st.expander("📻 Frequency — Băng tần & Cấu hình", expanded=True):
    c1, c2, c3 = st.columns(3)
    band = c1.selectbox("NR Band", ["n78", "n77", "n41", "n1", "n3", "n8", "n28", "n40", "n101", "n257", "n258", "n261"], index=["n78", "n77", "n41", "n1", "n3", "n8", "n28", "n40", "n101", "n257", "n258", "n261"].index(defaults["band"]), help=get_help("frequency.band"))
    bandwidth_mhz = c2.number_input("Bandwidth (MHz)", min_value=5.0, value=defaults["bandwidth_mhz"], step=5.0, help=get_help("frequency.bandwidth_mhz"))
    scs_khz = c3.selectbox("SCS (kHz)", [15, 30, 60, 120], index=[15, 30, 60, 120].index(defaults["scs_khz"]), help=get_help("frequency.scs_khz"))
    tdd_dl_ratio = st.slider("TDD DL Ratio", min_value=0.50, max_value=0.90, value=defaults["tdd_dl_ratio"], step=0.05, help=get_help("frequency.tdd_dl_ratio"))

# ── UE ──
with st.expander("📱 User Equipment — Thiết bị đầu cuối", expanded=True):
    c1, c2, c3 = st.columns(3)
    power_class = c1.selectbox("Power Class", ["PC1", "PC2", "PC3", "PC4"], index=["PC1", "PC2", "PC3", "PC4"].index(defaults["power_class"]), help=get_help("user_equipment.power_class"))
    ue_height_m = c2.number_input("Chiều cao UE (m)", min_value=1.0, value=defaults["ue_height_m"], step=0.1, help=get_help("user_equipment.height_m"))
    ue_noise_figure_db = c3.number_input("UE Noise Figure (dB)", min_value=0.0, value=defaults["ue_noise_figure_db"], step=0.5, help=get_help("user_equipment.noise_figure_db"))

# ── Margins ──
with st.expander("📊 Margins — Dự trù suy hao", expanded=True):
    c1, c2 = st.columns(2)
    interference_db = c1.number_input("Interference Margin (dB)", min_value=0.0, value=defaults["interference_db"], step=0.5, help=get_help("margins.interference_db"))
    penetration_db = c2.number_input("Penetration Loss (dB)", min_value=0.0, value=defaults["penetration_db"], step=1.0, help=get_help("margins.penetration_db"))
    c3, c4, c5 = st.columns(3)
    rain_attenuation_db = c3.number_input("Rain Attenuation (dB)", min_value=0.0, value=defaults["rain_attenuation_db"], step=0.1, help=get_help("margins.rain_attenuation_db"))
    overlap_factor = c4.number_input("Overlap Factor", min_value=0.0, max_value=0.5, value=defaults["overlap_factor"], step=0.05, help=get_help("margins.overlap_factor"))

# ── QoS ──
with st.expander("🎯 QoS — Chất lượng dịch vụ", expanded=True):
    c1, c2 = st.columns(2)
    primary_service = c1.selectbox("Primary Service", ["mixed", "vonr", "video_hd", "video_4k", "data", "gaming", "iot"], index=["mixed", "vonr", "video_hd", "video_4k", "data", "gaming", "iot"].index(defaults["primary_service"]), help=get_help("qos.primary_service"))
    users_per_km2 = c2.number_input("Users per km²", min_value=1.0, value=defaults["users_per_km2"], step=10.0, help=get_help("qos.users_per_km2"))
    c3, c4, c5 = st.columns(3)
    dl_per_user_mbps = c3.number_input("DL per User (Mbps)", min_value=0.5, value=defaults["dl_per_user_mbps"], step=1.0, help=get_help("qos.dl_per_user_mbps"))
    ul_per_user_mbps = c4.number_input("UL per User (Mbps)", min_value=0.1, value=defaults["ul_per_user_mbps"], step=0.5, help=get_help("qos.ul_per_user_mbps"))
    concurrent_ratio = c5.number_input("Concurrent Ratio", min_value=0.01, max_value=0.99, value=defaults["concurrent_ratio"], step=0.01, help=get_help("qos.concurrent_ratio"))

if planning_shell == "Geometry-aware planning":
    st.markdown("### 🧭 Planning Inputs — Geometry & Strategy")
    service_area_source = st.radio(
        "Service area source",
        ["Approximate circle from area + center", "Ordered points", "Paste polygon JSON"],
        horizontal=True,
        index=0 if not loaded_placement.get("service_area") else 2,
        help="Approximate circle tạo polygon từ area + center. Ordered points cho phép nhập các điểm theo thứ tự. Paste polygon JSON dùng trực tiếp `GeoPolygon` từ planning schema.",
    )
    default_service_area_json = json.dumps(loaded_placement.get("service_area", {}), indent=2, ensure_ascii=False) if loaded_placement.get("service_area") else ""
    default_service_area_points = _polygon_points_to_text(loaded_placement.get("service_area"))
    if service_area_source == "Paste polygon JSON":
        service_area_json = st.text_area(
            "Service area polygon JSON",
            value=default_service_area_json,
            height=160,
            placeholder='{"outer": [{"lat": 10.775, "lon": 106.695}, {"lat": 10.775, "lon": 106.705}, {"lat": 10.785, "lon": 106.705}, {"lat": 10.785, "lon": 106.695}], "name": "Target area"}',
            help="Paste một `GeoPolygon` hợp lệ. Dùng khi bạn muốn planning theo hình học thực tế thay vì area+center approximation.",
        )
        service_area_points_text = ""
    elif service_area_source == "Ordered points":
        service_area_points_text = st.text_area(
            "Service area points (lat, lon theo thứ tự)",
            value=default_service_area_points,
            height=160,
            placeholder="10.517860, 107.014418\n10.507658, 107.034188\n10.498606, 107.009709\n10.495440, 107.001274\n10.502635, 107.001886",
            help="Nhập mỗi dòng theo format `lat, lon`. Hệ thống sẽ giữ nguyên thứ tự các điểm để tạo polygon. Không cần lặp lại điểm đầu ở cuối.",
        )
        service_area_json = ""
        st.caption("Ordered points phù hợp hơn cho người dùng nhập tay polygon nhanh mà không cần viết JSON.")
    else:
        service_area_json = ""
        service_area_points_text = ""
        st.caption("Service area sẽ được nội suy thành polygon hình tròn từ `area_km2` + `center_lat/lon`.")

    with st.expander("🚧 Constraints — Exclusions, Alignments, Spacing", expanded=False):
        exclusion_zones_json = st.text_area(
            "Exclusion zones JSON",
            value=json.dumps(loaded_placement.get("exclusion_zones", []), indent=2, ensure_ascii=False) if loaded_placement.get("exclusion_zones") else "",
            height=140,
            placeholder='[{"reason": "no_build", "polygon": {"outer": [{"lat": 10.779, "lon": 106.699}, {"lat": 10.779, "lon": 106.701}, {"lat": 10.781, "lon": 106.701}, {"lat": 10.781, "lon": 106.699}]}}]',
        )
        alignments_json = st.text_area(
            "Alignments JSON",
            value=json.dumps(loaded_placement.get("alignments", []), indent=2, ensure_ascii=False) if loaded_placement.get("alignments") else "",
            height=140,
            placeholder='[{"name": "Tunnel axis", "alignment_type": "tunnel", "preferred_spacing_m": 120, "points": [{"lat": 10.780, "lon": 106.695}, {"lat": 10.780, "lon": 106.705}]}]',
        )
        c1, c2, c3 = st.columns(3)
        min_site_spacing_m = c1.number_input("Min site spacing (m)", min_value=0.0, value=float(loaded_placement.get("min_site_spacing_m") or 0.0), step=10.0)
        edge_setback_m = c2.number_input("Edge setback (m)", min_value=0.0, value=float(loaded_placement.get("edge_setback_m") or 0.0), step=10.0)
        outside_buffer_m = c3.number_input("Outside service area buffer (m)", min_value=0.0, value=float(loaded_placement.get("allow_outside_service_area_buffer_m") or 0.0), step=10.0)

    with st.expander("📈 Demand shaping — Traffic zones & spatial capacity", expanded=False):
        spatial_capacity_enabled = st.checkbox("Enable spatial capacity", value=bool(loaded_spatial.get("enabled", False)))
        c1, c2, c3 = st.columns(3)
        grid_resolution_m = c1.number_input("Grid resolution (m)", min_value=10.0, value=float(loaded_spatial.get("grid_resolution_m") or 100.0), step=10.0, disabled=not spatial_capacity_enabled)
        hotspot_search_radius_m = c2.number_input("Hotspot search radius (m)", min_value=0.0, value=float(loaded_spatial.get("hotspot_search_radius_m") or 0.0), step=10.0, disabled=not spatial_capacity_enabled)
        traffic_zones_json = st.text_area(
            "Traffic zones JSON",
            value=json.dumps(loaded_spatial.get("demand_zones", []), indent=2, ensure_ascii=False) if loaded_spatial.get("demand_zones") else "",
            height=140,
            placeholder='[{"name": "Hotspot", "weight": 8.0, "polygon": {"outer": [{"lat": 10.782, "lon": 106.702}, {"lat": 10.782, "lon": 106.705}, {"lat": 10.785, "lon": 106.705}, {"lat": 10.785, "lon": 106.702}]}}]',
            disabled=not spatial_capacity_enabled,
        )
        c4, c5 = st.columns(2)
        max_load_per_site_mbps_dl = c4.number_input("Max DL load per site (Mbps)", min_value=0.0, value=float(loaded_spatial.get("max_load_per_site_mbps_dl") or 0.0), step=10.0, disabled=not spatial_capacity_enabled)
        max_load_per_site_mbps_ul = c5.number_input("Max UL load per site (Mbps)", min_value=0.0, value=float(loaded_spatial.get("max_load_per_site_mbps_ul") or 0.0), step=10.0, disabled=not spatial_capacity_enabled)

    with st.expander("🎛️ Planning strategy — Objective & placement mode", expanded=True):
        c1, c2 = st.columns(2)
        placement_mode = c1.radio(
            "Placement mode",
            ["polygon_fill", "alignment_biased", "alignment_only", "hybrid"],
            horizontal=False,
            index=["polygon_fill", "alignment_biased", "alignment_only", "hybrid"].index(loaded_placement.get("placement_mode", "polygon_fill")),
            help="polygon_fill phủ theo polygon; alignment_only bám tuyến; alignment_biased ưu tiên tuyến; hybrid trộn cả hai.",
        )
        planning_objective = c2.radio(
            "Planning objective",
            ["coverage_first", "balanced", "capacity_first"],
            horizontal=False,
            index=["coverage_first", "balanced", "capacity_first"].index(loaded_placement.get("objective", "balanced")),
            help="coverage_first ưu tiên phủ sóng, capacity_first ưu tiên hotspot/capacity, balanced cân bằng cả hai.",
        )

    with st.expander("📍 Existing / planned sites", expanded=False):
        planned_sites_json = st.text_area(
            "Planned / locked / existing sites JSON",
            value=json.dumps(loaded_placement.get("planned_sites", []), indent=2, ensure_ascii=False) if loaded_placement.get("planned_sites") else "",
            height=140,
            placeholder='[{"id": "locked-1", "lat": 10.776, "lon": 106.696, "status": "locked", "azimuth_deg": 90, "beamwidth_deg": 120}]',
        )
else:
    service_area_source = "Approximate circle from area + center"
    service_area_json = ""
    exclusion_zones_json = ""
    alignments_json = ""
    min_site_spacing_m = 0.0
    edge_setback_m = 0.0
    outside_buffer_m = 0.0
    spatial_capacity_enabled = False
    grid_resolution_m = 100.0
    hotspot_search_radius_m = 0.0
    traffic_zones_json = ""
    max_load_per_site_mbps_dl = 0.0
    max_load_per_site_mbps_ul = 0.0
    placement_mode = "polygon_fill"
    planning_objective = "balanced"
    planned_sites_json = ""

st.divider()

# ══════════════════════════════════════════════
# STEP 3: Calculate
# ══════════════════════════════════════════════
st.header("🚀 Bước 3: Tính toán")

col_run, col_export = st.columns([1, 1])
with col_run:
    run_button = st.button("▶️ Tính toán RF Sizing", type="primary", use_container_width=True)
with col_export:
    uploaded = st.file_uploader("📁 Hoặc upload JSON config", type=["json"])

if uploaded:
    try:
        config_data = json.loads(uploaded.read().decode())
        st.session_state["loaded_config"] = config_data
        st.success(f"Đã load config: {config_data.get('project', {}).get('name', 'unnamed')}")
    except Exception as e:
        st.error(f"Lỗi JSON: {e}")

# ── Build Input ──
def build_input_from_ui() -> RFSizingInput:
    base_station_kw = dict(
        tx_power_w=tx_power_w, antenna_config=antenna_config, height_m=bs_height_m,
        sectors=sectors, cable_loss_db=cable_loss_db, noise_figure_db=bs_noise_figure_db,
    )
    if _catalog_radio_vendor:
        base_station_kw["radio_vendor"] = _catalog_radio_vendor
    if _catalog_radio_model:
        base_station_kw["radio_model"] = _catalog_radio_model
    if _catalog_ant_vendor:
        base_station_kw["antenna_vendor"] = _catalog_ant_vendor
    if _catalog_ant_model:
        base_station_kw["antenna_model"] = _catalog_ant_model
    if _custom_pattern_file:
        base_station_kw["antenna_pattern_source"] = "file"
        base_station_kw["antenna_pattern_file"] = _custom_pattern_file
        base_station_kw["antenna_pattern_format"] = None if custom_pattern_format == "auto" else custom_pattern_format
        base_station_kw["antenna_pattern_name"] = custom_pattern_name or None
        base_station_kw["antenna_pattern_freq_mhz"] = custom_pattern_freq_mhz or None

    placement_obj = None
    spatial_capacity_obj = None
    if planning_shell == "Geometry-aware planning":
        if service_area_source == "Paste polygon JSON":
            service_area_data = _parse_json_text(service_area_json, dict, "Service area")
        elif service_area_source == "Ordered points":
            service_area_data = _parse_polygon_points_text(service_area_points_text, "Service area points")
        else:
            service_area_data = _approximate_service_area_polygon(center_lat, center_lon, area_km2)
        exclusion_data = _parse_json_text(exclusion_zones_json, list, "Exclusion zones") or []
        alignment_data = _parse_json_text(alignments_json, list, "Alignments") or []
        planned_site_data = _parse_json_text(planned_sites_json, list, "Planned sites") or []
        placement_obj = PlacementConstraints(
            service_area=GeoPolygon(**service_area_data),
            exclusion_zones=[ExclusionZone(**item) for item in exclusion_data],
            alignments=[LinearAlignment(**item) for item in alignment_data],
            planned_sites=[PlannedSiteInput(**item) for item in planned_site_data],
            min_site_spacing_m=min_site_spacing_m or None,
            edge_setback_m=edge_setback_m,
            allow_outside_service_area_buffer_m=outside_buffer_m,
            placement_mode=placement_mode,
            objective=planning_objective,
        )
        if spatial_capacity_enabled:
            traffic_zone_data = _parse_json_text(traffic_zones_json, list, "Traffic zones") or []
            spatial_capacity_obj = SpatialCapacityConfig(
                enabled=True,
                grid_resolution_m=grid_resolution_m,
                hotspot_search_radius_m=hotspot_search_radius_m or None,
                demand_zones=[TrafficZone(**item) for item in traffic_zone_data],
                max_load_per_site_mbps_dl=max_load_per_site_mbps_dl or None,
                max_load_per_site_mbps_ul=max_load_per_site_mbps_ul or None,
            )

    return RFSizingInput(
        project=ProjectConfig(name=project_name, area_km2=area_km2, center_lat=center_lat, center_lon=center_lon),
        environment=EnvironmentConfig(scenario=scenario, obstacle_density=obstacle_density, coverage_probability=coverage_probability),
        base_station=BaseStationConfig(**base_station_kw),
        frequency=FrequencyConfig(band=band, bandwidth_mhz=bandwidth_mhz, scs_khz=scs_khz, tdd_dl_ratio=tdd_dl_ratio),
        user_equipment=UEConfig(power_class=power_class, height_m=ue_height_m, noise_figure_db=ue_noise_figure_db),
        margins=MarginsConfig(
            interference_db=interference_db, penetration_db=penetration_db,
            rain_attenuation_db=rain_attenuation_db, overlap_factor=overlap_factor,
        ),
        qos=QoSConfig(
            primary_service=primary_service, users_per_km2=users_per_km2,
            dl_per_user_mbps=dl_per_user_mbps, ul_per_user_mbps=ul_per_user_mbps,
            concurrent_ratio=concurrent_ratio,
        ),
        placement=placement_obj,
        spatial_capacity=spatial_capacity_obj,
    )

preview_error = None
preview_input = None
if "loaded_config" in st.session_state:
    try:
        preview_input = RFSizingInput(**st.session_state["loaded_config"])
    except Exception as exc:
        preview_error = f"Config đã load không hợp lệ: {exc}"
else:
    try:
        preview_input = build_input_from_ui()
    except Exception as exc:
        preview_error = str(exc)

st.markdown("#### 🧾 Pre-run assumptions summary")
if preview_error:
    st.error(preview_error)
else:
    summary_cols = st.columns(3)
    summary_cols[0].markdown(
        f"**Scope**\n\n"
        f"- Project: `{preview_input.project.name}`\n"
        f"- Scenario: `{preview_input.environment.scenario}` / `{preview_input.environment.obstacle_density}`\n"
        f"- Band: `{preview_input.frequency.band}` {preview_input.frequency.bandwidth_mhz:.0f} MHz\n"
        f"- Duplex/TDD ratio: `{preview_input.frequency.duplex}` / `{preview_input.frequency.tdd_dl_ratio:.2f}`"
    )
    catalog_preview = _catalog_override_preview(_catalog_radio_vendor, _catalog_radio_model, _catalog_ant_vendor, _catalog_ant_model, tx_power_w, antenna_config)
    pattern_source_label = f"custom file ({Path(_custom_pattern_file).name})" if _custom_pattern_file else 'catalog/builtin'
    summary_cols[1].markdown(
        f"**Equipment**\n\n"
        f"- TX power: `{catalog_preview['effective_tx_power_w']:.1f} W`\n"
        f"- Antenna config: `{catalog_preview['effective_antenna_config']}`\n"
        f"- Radio: `{catalog_preview['radio'] or 'manual'}`\n"
        f"- Antenna: `{catalog_preview['antenna'] or 'manual'}`\n"
        f"- Pattern source: `{pattern_source_label}`"
    )
    placement = preview_input.placement
    spatial_capacity = preview_input.spatial_capacity
    if planning_shell == "Geometry-aware planning" and placement:
        service_area_km2 = polygon_area_km2(placement.service_area)
        excluded_area_km2 = sum(polygon_area_km2(zone.polygon) for zone in placement.exclusion_zones)
        alignment_length = sum(line_length_km(alignment) for alignment in placement.alignments)
        summary_cols[2].markdown(
            f"**Planning**\n\n"
            f"- Service area: `{service_area_km2:.3f} km²`\n"
            f"- Exclusions: `{len(placement.exclusion_zones)}` (`{excluded_area_km2:.3f} km²`)\n"
            f"- Alignments: `{len(placement.alignments)}` (`{alignment_length:.3f} km`)\n"
            f"- Objective / mode: `{placement.objective}` / `{placement.placement_mode}`\n"
            f"- Traffic zones: `{len(spatial_capacity.demand_zones) if spatial_capacity else 0}`"
        )
    else:
        summary_cols[2].markdown(
            f"**Planning**\n\n"
            f"- Workflow: `{planning_shell}`\n"
            f"- Service polygon: `disabled`\n"
            f"- Objective: `n/a`\n"
            f"- Traffic zones: `0`"
        )

    validation_msgs = []
    if planning_shell == "Geometry-aware planning" and placement:
        if placement.placement_mode == "alignment_only" and not placement.alignments:
            validation_msgs.append(("error", "`alignment_only` cần ít nhất một alignment."))
        if placement.objective == "capacity_first" and (not spatial_capacity or not spatial_capacity.enabled or not spatial_capacity.demand_zones):
            validation_msgs.append(("warning", "`capacity_first` đang bật nhưng chưa có traffic zone — planner sẽ khó thể hiện hotspot-aware behavior."))
        if abs(preview_input.project.area_km2 - service_area_km2) / max(service_area_km2, 1e-6) > 0.5:
            validation_msgs.append(("warning", f"`area_km2` ({preview_input.project.area_km2:.2f}) lệch đáng kể so với polygon area ({service_area_km2:.2f})."))
    for note in catalog_preview["notes"]:
        validation_msgs.append(("info", note))
    if validation_msgs:
        for level, msg in validation_msgs:
            getattr(st, level)(msg)
    else:
        st.success("Ready — assumptions hợp lệ để chạy planning/sizing.")

    current_input = st.session_state.get("input")
    if current_input is not None and current_input.model_dump() != preview_input.model_dump():
        st.warning("Inputs đã thay đổi kể từ lần calculate gần nhất — hãy chạy lại để đồng bộ kết quả và các tab summary/map.")

if run_button or st.session_state.get("calculated"):
    with st.spinner("Đang tính toán..."):
        try:
            if "loaded_config" in st.session_state:
                inp = RFSizingInput(**st.session_state["loaded_config"])
            else:
                inp = build_input_from_ui()
            result = _run_sizing(inp)
            st.session_state["result"] = result
            st.session_state["input"] = inp
            st.session_state["calculated"] = True
        except Exception as e:
            st.error(f"Lỗi tính toán: {e}")
            st.stop()

if not st.session_state.get("result"):
    st.info("👆 Chọn kịch bản mẫu ở trên, tùy chỉnh tham số, rồi nhấn **Tính toán**.")
    st.stop()

result = st.session_state["result"]

# ══════════════════════════════════════════════
# STEP 4: Results
# ══════════════════════════════════════════════
st.header("📊 Bước 4: Kết quả")

# ── Key Metrics ──
st.subheader("📈 Chỉ số chính")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Cell Radius", f"{result.propagation.cell_radius_m:.0f} m", help="Bán kính cell từ MAPL inversion (3GPP TR 38.901)")
m2.metric("Coverage Sites", f"{result.site_estimate.coverage_sites}", help="Số site cần thiết để phủ sóng diện tích yêu cầu")
m3.metric("Limiting Link", result.site_estimate.limiting_link, help="UL hoặc DL limiting — UL thường là bottleneck do UE power thấp hơn BS")
m4.metric("Cell Edge SINR", f"{result.sinr.sinr_db:.1f} dB", help="SINR tại cell edge → CQI → Modulation → Spectral Efficiency")

m5, m6, m7, m8 = st.columns(4)
m5.metric("DL MAPL", f"{result.link_budget_dl.mapl_db:.1f} dB", help="Maximum Allowable Path Loss Downlink — tổng suy hao cho phép đường xuống")
m6.metric("UL MAPL", f"{result.link_budget_ul.mapl_db:.1f} dB", help="Maximum Allowable Path Loss Uplink — tổng suy hao cho phép đường lên")
if result.capacity:
    cap_ok = result.capacity.capacity_sufficient
    m7.metric("Capacity", "✅ Đủ" if cap_ok else "❌ Thiếu", help=f"{result.capacity.total_capacity_dl_gbps:.1f} Gbps supply vs {result.capacity.total_demand_dl_gbps:.1f} Gbps demand")
    m8.metric("Total Sites", f"{result.capacity.total_sites}", help="Tổng sites = max(coverage_sites, capacity_sites)")

if result.placement_plan:
    st.markdown("#### 🧭 Executive planning summary")
    plan = result.placement_plan
    exec_cols = st.columns(4)
    exec_cols[0].metric("Selected sites", f"{plan.metrics.selected_sites}")
    exec_cols[1].metric("Coverage ratio", f"{plan.metrics.coverage_ratio:.1%}")
    exec_cols[2].metric("Effective planning area", f"{plan.metrics.service_area_km2:.2f} km²")
    if plan.spatial_capacity:
        exec_cols[3].metric("Unserved DL", f"{plan.spatial_capacity.unserved_dl_gbps:.3f} Gbps")
    else:
        exec_cols[3].metric("Rejected candidates", f"{plan.metrics.rejected_candidates}")
    summary_lines = [
        f"Planner mode: **{plan.mode}**",
        f"Coverage target achieved: **{plan.metrics.coverage_ratio:.1%}** over **{plan.metrics.service_area_km2:.2f} km²** usable area.",
        f"Selected **{plan.metrics.selected_sites}** sites with **{plan.metrics.locked_sites}** locked/existing preserved.",
    ]
    if plan.metrics.excluded_area_km2 > 0:
        summary_lines.append(f"Exclusion zones removed **{plan.metrics.excluded_area_km2:.2f} km²** from the usable area.")
    if plan.metrics.alignment_length_km > 0:
        summary_lines.append(f"Alignment input contributed **{plan.metrics.alignment_length_km:.2f} km** corridor guidance.")
    if plan.spatial_capacity:
        summary_lines.append(
            f"Spatial capacity: **{plan.spatial_capacity.unserved_dl_gbps:.3f} Gbps DL** unserved across **{plan.spatial_capacity.hotspot_tiles}** hotspot tiles, overloaded sites = **{plan.spatial_capacity.overloaded_sites}**."
        )
    if result.catalog_overrides_applied:
        summary_lines.append(
            f"Catalog overrides applied — effective TX **{result.tx_power_w:.1f} W**, input TX **{result.input_tx_power_w:.1f} W**, antenna gain **{result.effective_antenna_gain_dbi or 0:.1f} dBi**."
        )
    if getattr(result, 'effective_pattern_source', None):
        summary_lines.append(f"Pattern source: **{result.effective_pattern_source}**")
    st.markdown("\n\n".join(f"- {line}" for line in summary_lines))

# ── Detailed Tabs ──
tab_exec, tab_lb, tab_cov, tab_sinr, tab_cap, tab_qos, tab_rec, tab_plan, tab_map, tab_chart, tab_compare, tab_export = st.tabs([
    "🧭 Executive Summary", "📡 Link Budget", "🗺️ Coverage", "📶 SINR", "📦 Capacity", "✅ QoS", "💡 Recommendations", "📍 Placement Plan", "🗺️ Map & Geometry", "📈 Charts", "🔀 Comparison", "📥 Export",
])

with tab_exec:
    st.markdown("### Executive Summary")
    st.write(f"**Project:** {result.project_name} | **Scenario:** {result.environment} | **Band:** {result.band} {result.bandwidth_mhz:.0f} MHz")
    st.write(f"**Effective TX:** {result.tx_power_w:.1f} W | **Antenna Config:** {result.antenna_config} | **Limiting Link:** {result.site_estimate.limiting_link}")
    if result.catalog_overrides_applied:
        st.info(
            f"Catalog override đang hoạt động — Input TX {result.input_tx_power_w:.1f} W / Input antenna {result.input_antenna_config} → Effective TX {result.tx_power_w:.1f} W / Gain {result.effective_antenna_gain_dbi or 0:.1f} dBi"
        )
    radio_details = getattr(result, 'radio_details', None)
    antenna_details = getattr(result, 'antenna_details', None)
    if radio_details:
        st.caption(f"Radio source: {radio_details.vendor or 'unknown'} {radio_details.model or ''}{' — ' + radio_details.source_pdf if radio_details.source_pdf else ''}")
    if antenna_details:
        st.caption(f"Antenna source: {antenna_details.vendor or 'custom'} {antenna_details.model or ''}{' — ' + antenna_details.source_pdf if antenna_details.source_pdf else ''}")
        if antenna_details.pattern_asset:
            st.caption(f"Pattern asset: {antenna_details.pattern_asset}")
    if getattr(result, 'effective_pattern_source', None):
        st.caption(f"Pattern source: {result.effective_pattern_source}")
    if result.placement_plan:
        metric_rows = [
            {"Metric": "Placement mode", "Value": result.placement_plan.mode},
            {"Metric": "Selected sites", "Value": result.placement_plan.metrics.selected_sites},
            {"Metric": "Coverage ratio", "Value": f"{result.placement_plan.metrics.coverage_ratio:.1%}"},
            {"Metric": "Alignment length", "Value": f"{result.placement_plan.metrics.alignment_length_km:.2f} km"},
            {"Metric": "Rejected candidates", "Value": result.placement_plan.metrics.rejected_candidates},
        ]
        if result.placement_plan.spatial_capacity:
            metric_rows.extend([
                {"Metric": "Unserved DL", "Value": f"{result.placement_plan.spatial_capacity.unserved_dl_gbps:.3f} Gbps"},
                {"Metric": "Hotspot tiles", "Value": result.placement_plan.spatial_capacity.hotspot_tiles},
                {"Metric": "Overloaded sites", "Value": result.placement_plan.spatial_capacity.overloaded_sites},
            ])
        st.dataframe(metric_rows, use_container_width=True, hide_index=True)

with tab_lb:
    st.markdown("### Link Budget — Suy hao cho phép tối đa")
    st.markdown("**MAPL (Maximum Allowable Path Loss)** = EIRP − Rx Sensitivity − Margins. "
                "MAPL càng cao → cell radius càng lớn → ít site hơn.")
    lb_data = {
        "Tham số": ["EIRP (dBm)", "Rx Sensitivity (dBm)", "MAPL (dB)", "Shadow Fading (dB)", "Penetration Loss (dB)", "Interference (dB)"],
        "DL (Downlink)": [
            f"{result.link_budget_dl.eirp_dbm:.1f}",
            f"{result.link_budget_dl.rx_sensitivity_dbm:.1f}",
            f"**{result.link_budget_dl.mapl_db:.1f}**",
            f"{result.link_budget_dl.shadow_fading_margin_db:.1f}",
            f"{result.link_budget_dl.penetration_loss_db:.1f}",
            f"{result.link_budget_dl.interference_margin_db:.1f}",
        ],
        "UL (Uplink)": [
            f"{result.link_budget_ul.eirp_dbm:.1f}",
            f"{result.link_budget_ul.rx_sensitivity_dbm:.1f}",
            f"**{result.link_budget_ul.mapl_db:.1f}**",
            f"{result.link_budget_ul.shadow_fading_margin_db:.1f}",
            f"{result.link_budget_ul.penetration_loss_db:.1f}",
            f"{result.link_budget_ul.interference_margin_db:.1f}",
        ],
    }
    st.dataframe(lb_data, use_container_width=True, hide_index=True)
    if result.site_estimate.limiting_link == "UL":
        st.warning(f"⚠️ **UL limiting**: UL MAPL ({result.link_budget_ul.mapl_db:.1f} dB) thấp hơn DL ({result.link_budget_dl.mapl_db:.1f} dB) "
                   f"→ Cell radius bị giới hạn bởi uplink. Cân nhắc nâng UE Power Class hoặc UL CA.")

with tab_cov:
    st.markdown("### Coverage Estimate — Ước tính phủ sóng")
    cov_data = {
        "Tham số": ["Propagation Model", "Path Loss (dB)", "Cell Radius (m)", "Cell Radius (km)", "LOS Probability", "ISD (m)", "Coverage Sites"],
        "Giá trị": [
            result.propagation.model,
            f"{result.propagation.path_loss_db:.1f}",
            f"{result.propagation.cell_radius_m:.0f}",
            f"{result.propagation.cell_radius_km:.3f}",
            f"{result.propagation.los_probability:.1%}" if result.propagation.los_probability else "N/A",
            f"{result.site_estimate.isd_km * 1000:.0f}",
            f"{result.site_estimate.coverage_sites}",
        ],
    }
    st.dataframe(cov_data, use_container_width=True, hide_index=True)
    st.info(f"ISD (Inter-Site Distance) = √3 × R = √3 × {result.propagation.cell_radius_m:.0f}m = {result.site_estimate.isd_km * 1000:.0f}m")

with tab_sinr:
    st.markdown("### SINR & Modulation — Chất lượng sóng tại cell edge")
    sinr_data = {
        "Tham số": ["SINR (dB)", "CQI", "Modulation", "Spectral Efficiency (bps/Hz)", "Code Rate"],
        "Giá trị": [
            f"{result.sinr.sinr_db:.1f}",
            str(result.sinr.cqi),
            result.sinr.modulation,
            f"{result.sinr.spectral_efficiency_bps_hz:.4f}",
            f"{result.sinr.code_rate:.4f}",
        ],
    }
    st.dataframe(sinr_data, use_container_width=True, hide_index=True)
    if result.sinr.cqi <= 3:
        st.warning("⚠️ CQI thấp (≤3, QPSK) → throughput cell edge kém. Cân nhắc thêm sites hoặc nâng antenna.")
    elif result.sinr.cqi >= 10:
        st.success("✅ CQI cao (≥10, 64QAM+) → throughput cell edge tốt.")

with tab_cap:
    if result.capacity:
        st.markdown("### Capacity — Khả năng thông qua")
        st.markdown(f"**Cell DL:** {result.capacity.cell_throughput_dl_mbps:.1f} Mbps | "
                    f"**Cell UL:** {result.capacity.cell_throughput_ul_mbps:.1f} Mbps")
        cap_data = {
            "Tham số": ["Cell DL Throughput", "Cell UL Throughput", "Total DL Capacity", "Total DL Demand",
                         "Capacity Sufficient", "Total Sites (cov+cap)", "Additional Sites"],
            "Giá trị": [
                f"{result.capacity.cell_throughput_dl_mbps:.1f} Mbps",
                f"{result.capacity.cell_throughput_ul_mbps:.1f} Mbps",
                f"{result.capacity.total_capacity_dl_gbps:.2f} Gbps",
                f"{result.capacity.total_demand_dl_gbps:.2f} Gbps",
                "✅ Đủ" if result.capacity.capacity_sufficient else "❌ Thiếu",
                str(result.capacity.total_sites),
                str(result.capacity.additional_sites_needed),
            ],
        }
        st.dataframe(cap_data, use_container_width=True, hide_index=True)
        if result.placement_plan and result.placement_plan.metrics.selected_sites == 0:
            st.warning("Planner hiện chưa chọn được site nào. Capacity summary bên dưới chỉ phản ánh phép tính RF/capacity nền, không phải một placement plan hợp lệ.")
        if not result.capacity.capacity_sufficient:
            st.error(f"❌ **Capacity không đủ**: Cần thêm {result.capacity.additional_sites_needed} sites "
                     f"({result.capacity.total_capacity_dl_gbps:.1f} Gbps supply < {result.capacity.total_demand_dl_gbps:.1f} Gbps demand)")
        if result.placement_plan and result.placement_plan.spatial_capacity:
            st.markdown("#### Spatial capacity")
            sc = result.placement_plan.spatial_capacity
            st.dataframe([
                {"Tham số": "Demand DL", "Giá trị": f"{sc.demand_dl_gbps:.3f} Gbps"},
                {"Tham số": "Served DL", "Giá trị": f"{sc.served_dl_gbps:.3f} Gbps"},
                {"Tham số": "Unserved DL", "Giá trị": f"{sc.unserved_dl_gbps:.3f} Gbps"},
                {"Tham số": "Demand UL", "Giá trị": f"{sc.demand_ul_gbps:.3f} Gbps"},
                {"Tham số": "Served UL", "Giá trị": f"{sc.served_ul_gbps:.3f} Gbps"},
                {"Tham số": "Unserved UL", "Giá trị": f"{sc.unserved_ul_gbps:.3f} Gbps"},
                {"Tham số": "Hotspot Tiles", "Giá trị": sc.hotspot_tiles},
                {"Tham số": "Overloaded Sites", "Giá trị": sc.overloaded_sites},
            ], use_container_width=True, hide_index=True)
    else:
        st.info("Capacity calculation không khả dụng.")

with tab_qos:
    if result.qos_verification:
        st.markdown("### QoS Verification — Kiểm tra chất lượng dịch vụ")
        qos_rows = []
        for q in result.qos_verification:
            qos_rows.append({
                "Dịch vụ": q.service,
                "SINR Yêu cầu": f"{q.sinr_required_db} dB",
                "SINR Có": f"{q.sinr_available_db:.1f} dB",
                "Phủ sóng %": f"{q.area_percentage:.0f}%",
                "Kết quả": "✅ PASS" if q.passed else "❌ FAIL",
            })
        st.dataframe(qos_rows, use_container_width=True, hide_index=True)
    else:
        st.info("QoS verification không khả dụng.")

with tab_rec:
    if result.recommendations:
        st.markdown("### Recommendations — Đề xuất hành động")
        for i, rec in enumerate(result.recommendations, 1):
            st.write(f"{i}. {rec}")
    else:
        st.info("Không có đề xuất đặc biệt.")

with tab_plan:
    st.markdown("### Placement Plan — Kế hoạch đặt site")
    if result.placement_plan:
        metrics_rows = [
            {"Metric": "Service area", "Value": f"{result.placement_plan.metrics.service_area_km2:.3f} km²"},
            {"Metric": "Covered area", "Value": f"{result.placement_plan.metrics.covered_area_km2:.3f} km²"},
            {"Metric": "Coverage ratio", "Value": f"{result.placement_plan.metrics.coverage_ratio:.1%}"},
            {"Metric": "Excluded area", "Value": f"{result.placement_plan.metrics.excluded_area_km2:.3f} km²"},
            {"Metric": "Candidate sites", "Value": result.placement_plan.metrics.candidate_sites},
            {"Metric": "Selected sites", "Value": result.placement_plan.metrics.selected_sites},
            {"Metric": "Locked sites", "Value": result.placement_plan.metrics.locked_sites},
            {"Metric": "Rejected candidates", "Value": result.placement_plan.metrics.rejected_candidates},
        ]
        st.dataframe(metrics_rows, use_container_width=True, hide_index=True)

        if result.placement_plan.metrics.selected_sites == 0:
            st.error("Planner không chọn được site nào với cấu hình hiện tại.")
            top_reasons = [candidate for candidate in result.placement_plan.candidates if not candidate.accepted][:3]
            if top_reasons:
                st.caption("Top rejection reasons:")
                for candidate in top_reasons:
                    st.write(f"- **{candidate.id}**: {' | '.join(candidate.reasons)}")
            st.info("Gợi ý: giảm `min_site_spacing_m`, đổi `placement_mode`, tăng service area, hoặc dùng manual preview để kiểm tra geometry/site assumptions.")

        st.markdown("#### ✅ Selected sites")
        selected_rows = []
        for site in result.placement_plan.selected_sites:
            selected_rows.append({
                "ID": site.id,
                "Source": site.source,
                "Status": site.status,
                "Lat": round(site.lat, 6),
                "Lon": round(site.lon, 6),
                "Azimuths": ", ".join(f"{az:.0f}°" for az in site.azimuths_deg) if site.azimuths_deg else "-",
                "Beamwidth": f"{site.beamwidth_deg:.0f}°" if site.beamwidth_deg else "-",
                "DL load": f"{site.estimated_dl_load_mbps:.1f} Mbps" if site.estimated_dl_load_mbps is not None else "-",
                "UL load": f"{site.estimated_ul_load_mbps:.1f} Mbps" if site.estimated_ul_load_mbps is not None else "-",
                "Overloaded": "⚠️" if site.overloaded else "",
            })
        st.dataframe(selected_rows, use_container_width=True, hide_index=True)

        rejected = [candidate for candidate in result.placement_plan.candidates if not candidate.accepted]
        if rejected:
            st.markdown("#### ❌ Rejected candidates")
            rejected_rows = []
            for candidate in rejected[:100]:
                rejected_rows.append({
                    "ID": candidate.id,
                    "Source": candidate.source,
                    "Score": f"{candidate.score:.2f}" if candidate.score is not None else "-",
                    "Reasons": " | ".join(candidate.reasons),
                })
            st.dataframe(rejected_rows, use_container_width=True, hide_index=True)
    else:
        st.info("Planning output chưa khả dụng cho scenario hiện tại.")

with tab_map:
    st.markdown("### Map & Geometry — Bản đồ planning")
    if result.placement_plan:
        map_summary_cols = st.columns(4)
        map_summary_cols[0].metric("Usable area", f"{result.placement_plan.metrics.service_area_km2:.2f} km²")
        map_summary_cols[1].metric("Excluded area", f"{result.placement_plan.metrics.excluded_area_km2:.2f} km²")
        map_summary_cols[2].metric("Alignment length", f"{result.placement_plan.metrics.alignment_length_km:.2f} km")
        overload_count = result.placement_plan.spatial_capacity.overloaded_sites if result.placement_plan.spatial_capacity else 0
        map_summary_cols[3].metric("Overloaded sites", f"{overload_count}")
        st.caption("Map sẽ overlay service area, exclusion zones, alignments, traffic zones và selected sites từ planner. Bạn vẫn có thể override tạm thời bằng manual sites bên dưới để review nhanh.")

    map_source = st.radio(
        "Map source",
        ["Planner result", "Manual site preview"],
        horizontal=True,
        help="Planner result hiển thị selected sites từ placement plan. Manual site preview chỉ dùng để review thủ công và KHÔNG thay đổi selected_sites trong planner.",
    )
    if map_source == "Planner result" and result.placement_plan and result.placement_plan.metrics.selected_sites == 0:
        st.warning("Planner result hiện có 0 selected sites. Nếu muốn review hình học thủ công, chuyển sang Manual site preview.")
    elif map_source == "Manual site preview":
        st.info("Bạn đang xem manual preview. Các số liệu selected sites / coverage ratio ở trên vẫn thuộc planner result, không đổi theo manual sites bên dưới.")

    # ── Custom site input ──
    st.markdown("**📍 Nhập site thủ công** — format: `lat, lon` hoặc `lat, lon, azimuth, beamwidth` — 6 chữ số thập phân:")
    custom_sites_text = st.text_area(
        "Sites (lat, lon[, azimuth, beamwidth])",
        value="",
        placeholder="10.782000, 106.700000\n10.785000, 106.705000, 0, 65\n10.780000, 106.695000, 120, 65",
        height=100,
        help="Nhập từng site mỗi dòng. Format:\n• lat, lon (omni hoặc dùng config chung)\n• lat, lon, azimuth°, beamwidth° (sector thủ công)\nAzimuth: hướng góc phủ (0°=Bắc, 90°=Đông). Beamwidth: độ rộng tia.\nVí dụ sector 1 hướng Bắc 65°: 10.782, 106.700, 0, 65",
        key="custom_sites_input",
    )

    # Parse custom sites with azimuth/beamwidth support
    custom_sites = None
    custom_site_meta = None  # list of {azimuth, beamwidth} per site
    if map_source == "Manual site preview" and custom_sites_text.strip():
        parsed = []
        meta = []
        for line in custom_sites_text.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.replace(",", " ").split()
            try:
                lat = round(float(parts[0]), 6)
                lon = round(float(parts[1]), 6)
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    continue
                azi = float(parts[2]) if len(parts) > 2 else None
                bw = float(parts[3]) if len(parts) > 3 else None
                parsed.append((lat, lon))
                meta.append({"azimuth": azi, "beamwidth": bw})
            except (ValueError, IndexError):
                pass
        if parsed:
            custom_sites = parsed
            custom_site_meta = meta
            n_manual = len(parsed)
            n_sector_manual = sum(1 for m in meta if m["azimuth"] is not None)
            if n_sector_manual > 0:
                st.caption(f"✅ **{n_manual}** site — {n_sector_manual} sector thủ công (azimuth+beamwidth)")
            else:
                st.caption(f"✅ Đã nhập **{n_manual}** site thủ công")

    # Map view options
    map_view = st.radio(
        "Chế độ xem",
        ["Coverage Sites (phủ sóng)", "Capacity Sites (theo dung lượng)", "So sánh Coverage vs Capacity"],
        horizontal=True,
        help="Coverage Sites: số site phủ sóng toàn diện tích. Capacity Sites: số site cần thiết cho throughput yêu cầu."
    )

    n_cov = result.site_estimate.coverage_sites
    n_cap = result.capacity.total_sites if result.capacity else n_cov
    n_total = max(n_cov, n_cap)

    if "Capacity Sites" in map_view and n_cap > n_cov:
        st.info(f"📡 Coverage: **{n_cov}** sites | 📦 Capacity: **{n_cap}** sites → Cần **{n_cap - n_cov}** site thêm cho capacity.")
    elif "So sánh" in map_view:
        st.info(f"📡 Coverage: **{n_cov}** sites | 📦 Capacity: **{n_cap}** sites | Tổng: **{n_total}** sites")
    else:
        st.info(f"📡 Cần **{n_cov}** sites để phủ sóng {result.project_name}")

    # ── Sector configuration warning ──
    n_sectors = result.site_estimate.sectors if hasattr(result.site_estimate, 'sectors') else 3
    isd_km = result.site_estimate.isd_km
    # Use catalog antenna pattern if selected, otherwise default
    if _catalog_ant_vendor and _catalog_ant_model:
        try:
            from rf5g.models.antenna_pattern import antenna_pattern_from_catalog
            freq_mhz = 3500.0
            try:
                from rf5g.models.lookup_tables import BandLookup
                freq_mhz = BandLookup().get_fc(result.band)
            except Exception:
                pass
            ant_pattern = antenna_pattern_from_catalog(_catalog_ant_vendor, _catalog_ant_model, freq_mhz=freq_mhz)
        except Exception:
            ant_pattern = pattern_for_config(result.antenna_config)
    else:
        ant_pattern = pattern_for_config(result.antenna_config)
    if n_sectors == 1 and ant_pattern.pattern_type != "omni":
        st.warning(f"⚠️ **1 Sector + Antenna {ant_pattern.pattern_type} ({ant_pattern.beamwidth_h_deg}°):** "
                  f"Mỗi site chỉ phủ **{ant_pattern.beamwidth_h_deg}°** — KHÔNG phải 360°. "
                  f"Để phủ toàn diện tích, cần xoay site hoặc dùng 3 sector. "
                  f"Đang tính {n_total} site với mỗi site phủ {ant_pattern.beamwidth_h_deg}°.")
    elif n_sectors == 3:
        st.success(f"✅ **3 Sector ({ant_pattern.beamwidth_h_deg}° mỗi sector)** — "
                  f"Phủ 360° hoàn chỉnh. ISD = {isd_km*1000:.0f}m.")
    elif n_sectors == 1 and ant_pattern.pattern_type == "omni":
        st.success(f"✅ **1 Sector Omni (360°)** — Phủ vòng tròn hoàn chỉnh. ISD = {isd_km*1000:.0f}m.")

    # ── Area verification ──
    isd_km = result.site_estimate.isd_km
    cell_radius_km = result.propagation.cell_radius_km
    n_display = n_cap if "Capacity" in map_view or "So sánh" in map_view else n_cov
    if custom_sites:
        n_display = len(custom_sites)
        # Compute actual area from custom sites (convex hull)
        try:
            if len(custom_sites) >= 3:
                # Approximate area using bounding box
                lats = [s[0] for s in custom_sites]
                lons = [s[1] for s in custom_sites]
                max_d = 0
                for i in range(len(custom_sites)):
                    for j in range(i+1, len(custom_sites)):
                        d = haversine_km(custom_sites[i][0], custom_sites[i][1], custom_sites[j][0], custom_sites[j][1])
                        if d > max_d:
                            max_d = d
                # Approx area as circle with radius = max_d/2
                custom_area_km2 = math.pi * (max_d / 2) ** 2
                input_area_km2 = area_km2
                st.markdown(f"**📐 Kiểm tra diện tích:**")
                st.caption(f"Diện tích input: **{input_area_km2}** km² | Diện tích sites thủ công (≈): **{custom_area_km2:.1f}** km²")
        except Exception:
            pass
    else:
        # Verify: hex grid area vs input area
        hex_cell_area_km2 = result.site_estimate.cell_area_km2
        hex_total_area_km2 = hex_cell_area_km2 * n_display
        input_area_km2 = area_km2
        # Also compute convex hull area of hex grid
        grid_sites = generate_hex_grid(center_lat, center_lon, isd_km, n_display)
        if len(grid_sites) >= 3:
            max_d = 0
            for i in range(len(grid_sites)):
                for j in range(i+1, min(len(grid_sites), i+20)):  # Sample for speed
                    d = haversine_km(grid_sites[i][0], grid_sites[i][1], grid_sites[j][0], grid_sites[j][1])
                    if d > max_d:
                        max_d = d
            grid_diameter_km = max_d
            grid_area_approx = math.pi * (max_d / 2) ** 2
        else:
            grid_diameter_km = isd_km
            grid_area_approx = hex_total_area_km2

        st.markdown("**📐 Kiểm tra diện tích:**")
        st.caption(
            f"Diện tích input: **{input_area_km2}** km² | "
            f"Hex grid ({n_display} sites): **{hex_total_area_km2:.1f}** km² | "
            f"Đường kính grid: **{grid_diameter_km:.2f}** km | "
            f"ISD: **{isd_km*1000:.0f}**m | Cell R: **{cell_radius_km*1000:.0f}**m"
        )
        if hex_total_area_km2 < input_area_km2 * 0.8:
            st.warning(f"⚠️ Diện tích hex grid ({hex_total_area_km2:.1f} km²) nhỏ hơn input ({input_area_km2} km²). Cần thêm sites hoặc tăng ISD.")
        elif hex_total_area_km2 > input_area_km2 * 1.5:
            st.info(f"ℹ️ Hex grid phủ **{hex_total_area_km2/input_area_km2:.1f}x** diện tích input — đủ dư phủ sóng.")

    with st.spinner("Đang tạo bản đồ..."):
        try:
            if map_source == "Manual site preview" and custom_sites:
                fmap = generate_interactive_map(result, center_lat=center_lat, center_lon=center_lon, custom_sites=custom_sites, antenna_pattern_override=ant_pattern, return_map=True, site_meta=custom_site_meta)
            elif map_source == "Manual site preview" and not custom_sites:
                st.info("Chưa có manual sites hợp lệ. Đang fallback về planner result.")
                fmap = generate_coverage_map(result, center_lat=center_lat, center_lon=center_lon, antenna_pattern_override=ant_pattern, return_map=True)
            elif "Capacity Sites" in map_view and n_cap > n_cov:
                cap_sites = generate_hex_grid(center_lat, center_lon, isd_km, n_cap)
                fmap = generate_interactive_map(result, center_lat=center_lat, center_lon=center_lon, custom_sites=cap_sites, antenna_pattern_override=ant_pattern, return_map=True)
            elif "So sánh" in map_view:
                cap_sites = generate_hex_grid(center_lat, center_lon, isd_km, n_cap)
                fmap = generate_interactive_map(result, center_lat=center_lat, center_lon=center_lon, custom_sites=cap_sites, antenna_pattern_override=ant_pattern, return_map=True)
            else:
                fmap = generate_coverage_map(result, center_lat=center_lat, center_lon=center_lon, antenna_pattern_override=ant_pattern, return_map=True)
            # Use streamlit-folium for proper rendering
            from streamlit_folium import st_folium
            st_folium(fmap, width=None, height=600, returned_objects=[])
        except Exception as e:
            st.error(f"Lỗi tạo map: {e}")

    # Export sites
    st.markdown("#### 📥 Xuất danh sách Site")
    exp_col1, exp_col2 = st.columns(2)
    with exp_col1:
        if st.button("📥 Export Sites JSON", key="export_json"):
            export_sites = custom_sites if custom_sites else generate_hex_grid(center_lat, center_lon, isd_km, n_total)
            out_path = export_sites_json(export_sites, f"{result.project_name}_sites.json", metadata={
                "band": result.band,
                "isd_km": isd_km,
                "cell_radius_km": result.propagation.cell_radius_km,
                "total_sites": len(export_sites),
            })
            with open(out_path, encoding="utf-8") as f:
                st.download_button("⬇️ Download JSON", f.read(), file_name=out_path, mime="application/json")
    with exp_col2:
        if st.button("📥 Export Sites CSV", key="export_csv"):
            export_sites = custom_sites if custom_sites else generate_hex_grid(center_lat, center_lon, isd_km, n_total)
            out_path = export_sites_csv(export_sites, f"{result.project_name}_sites.csv")
            with open(out_path, encoding="utf-8") as f:
                st.download_button("⬇️ Download CSV", f.read(), file_name=out_path, mime="text/csv")

with tab_chart:
    st.markdown("### Charts — Biểu đồ")
    import tempfile
    import matplotlib
    matplotlib.use("Agg")

    chart_c1, chart_c2 = st.columns(2)
    with chart_c1:
        st.write("**📡 Link Budget**")
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                lb_path = plot_link_budget(result, output_path=f.name)
                st.image(lb_path)
        except Exception as e:
            st.error(f"Lỗi: {e}")

        st.write("**🎯 Service Zones**")
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                sz_path = plot_service_zones(result, output_path=f.name)
                st.image(sz_path)
        except Exception as e:
            st.error(f"Lỗi: {e}")

    with chart_c2:
        st.write("**📶 SINR Heatmap**")
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                sh_path = plot_sinr_heatmap(result, output_path=f.name)
                st.image(sh_path)
        except Exception as e:
            st.error(f"Lỗi: {e}")

        if result.capacity:
            st.write("**📦 Capacity**")
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    cap_path = plot_capacity_comparison(result, output_path=f.name)
                    if cap_path:
                        st.image(cap_path)
            except Exception as e:
                st.error(f"Lỗi: {e}")

with tab_compare:
    st.markdown("### Comparison — So sánh scenario")
    compare_col1, compare_col2, compare_col3 = st.columns(3)
    if compare_col1.button("➕ Add current run to comparison", use_container_width=True):
        current_input = st.session_state.get("input")
        objective_label = current_input.placement.objective if current_input and current_input.placement else "legacy"
        mode_label = current_input.placement.placement_mode if current_input and current_input.placement else "legacy"
        st.session_state["compare_runs"].append({
            "name": result.project_name,
            "objective": objective_label,
            "placement_mode": mode_label,
            "coverage_ratio": result.placement_plan.metrics.coverage_ratio if result.placement_plan else None,
            "selected_sites": result.placement_plan.metrics.selected_sites if result.placement_plan else result.site_estimate.coverage_sites,
            "unserved_dl_gbps": result.placement_plan.spatial_capacity.unserved_dl_gbps if result.placement_plan and result.placement_plan.spatial_capacity else None,
            "hotspot_tiles": result.placement_plan.spatial_capacity.hotspot_tiles if result.placement_plan and result.placement_plan.spatial_capacity else None,
            "overloaded_sites": result.placement_plan.spatial_capacity.overloaded_sites if result.placement_plan and result.placement_plan.spatial_capacity else None,
            "limiting_link": result.site_estimate.limiting_link,
        })
    if compare_col2.button("🧬 Duplicate current scenario snapshot", use_container_width=True):
        snapshot = st.session_state.get("input", build_input_from_ui()).model_dump()
        st.session_state["compare_runs"].append({"name": f"{result.project_name} (snapshot)", "snapshot": snapshot})
    if compare_col3.button("🗑️ Clear comparison", use_container_width=True):
        st.session_state["compare_runs"] = []

    compare_runs = st.session_state.get("compare_runs", [])
    if compare_runs:
        st.dataframe(compare_runs, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có scenario nào trong comparison set. Hãy add current run hoặc duplicate snapshot để so sánh objective / placement mode.")

with tab_export:
    st.markdown("### Export — Xuất planning package")
    json_str = result.model_dump_json(indent=2)
    col_j, col_h, col_m = st.columns(3)

    with col_j:
        st.download_button(
            "📥 Planning Summary JSON",
            data=json_str,
            file_name=f"{result.project_name.replace(' ', '_')}_summary.json",
            mime="application/json",
        )

    with col_h:
        html_path = generate_html_report(result)
        html_content = open(html_path, encoding="utf-8").read()
        st.download_button(
            "📄 HTML Report",
            data=html_content,
            file_name=f"rf5g_{result.project_name.replace(' ', '_')}.html",
            mime="text/html",
        )

    with col_m:
        md_path = generate_markdown_report(result)
        md_content = open(md_path, encoding="utf-8").read()
        st.download_button(
            "📝 Markdown Report",
            data=md_content,
            file_name=f"rf5g_{result.project_name.replace(' ', '_')}.md",
            mime="text/markdown",
        )

    st.divider()
    st.markdown("#### 💾 Scenario & planning inputs")
    current_config = st.session_state.get("input", build_input_from_ui()).model_dump()
    config_json = json.dumps(current_config, indent=2, ensure_ascii=False)
    st.code(config_json, language="json")
    st.download_button(
        "💾 Download Scenario JSON",
        data=config_json,
        file_name=f"{result.project_name.replace(' ', '_')}_scenario.json",
        mime="application/json",
    )

    if result.placement_plan:
        st.markdown("#### 📍 Selected sites package")
        selected_sites_json = json.dumps([site.model_dump() for site in result.placement_plan.selected_sites], indent=2, ensure_ascii=False)
        st.download_button(
            "📥 Selected Sites JSON",
            data=selected_sites_json,
            file_name=f"{result.project_name.replace(' ', '_')}_selected-sites.json",
            mime="application/json",
        )

    compare_runs = st.session_state.get("compare_runs", [])
    if compare_runs:
        st.markdown("#### 🔀 Comparison export")
        compare_json = json.dumps(compare_runs, indent=2, ensure_ascii=False)
        st.download_button(
            "📤 Download Comparison JSON",
            data=compare_json,
            file_name=f"{result.project_name.replace(' ', '_')}_comparison.json",
            mime="application/json",
        )
