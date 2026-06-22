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
)
from rf5g.cli import _run_sizing
from rf5g.viz.coverage_map import generate_coverage_map, generate_interactive_map, generate_hex_grid, export_sites_json, export_sites_csv, haversine_km, pattern_for_config
from rf5g.viz.charts import plot_link_budget, plot_sinr_heatmap, plot_service_zones, plot_capacity_comparison
from rf5g.viz.report import generate_html_report, generate_markdown_report

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
            "frequency": {"band": "n8", "bandwidth_mhz": 10.0, "scs_khz": 15, "tdd_dl_ratio": 0.60},
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
    "base_station.tx_power_w": "📡 **Công suất phát BS** (Watt) — EIRP = 10·log10(P) + antenna_gain.\n\n"
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
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

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
                from rf5g.models.antenna_pattern import get_catalog_radio
                try:
                    r_spec = get_catalog_radio(radio_vendor, radio_model)
                    st.caption(f"📡 {r_spec['vendor']} {r_spec['model']}: {r_spec['mimo_config']}, "
                              f"{r_spec['max_tx_power_w']}W/port ({r_spec['max_tx_power_dbm']} dBm), "
                              f"{r_spec['frequency_bands']}, {r_spec['weight_kg']}kg")
                    # Auto-set tx_power_w and antenna_config from radio spec
                    if r_spec.get("max_tx_power_w") and r_spec.get("tx_ports"):
                        total_w = r_spec["max_tx_power_w"] * r_spec["tx_ports"]
                        tx_power_w = total_w
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

    # Collect catalog selections for build_input
    _catalog_radio_vendor = radio_vendor if (radio_vendor and radio_vendor != "— None —") else None
    _catalog_radio_model = radio_model if (radio_model and radio_model != "— Select —") else None
    _catalog_ant_vendor = ant_vendor if (ant_vendor and ant_vendor != "— None —") else None
    _catalog_ant_model = antenna_model if (antenna_model and antenna_model != "— Select —") else None

# ── Frequency ──
with st.expander("📻 Frequency — Băng tần & Cấu hình", expanded=True):
    c1, c2, c3 = st.columns(3)
    band = c1.selectbox("NR Band", ["n78", "n77", "n41", "n1", "n3", "n8", "n28", "n25", "n71"], index=["n78", "n77", "n41", "n1", "n3", "n8", "n28", "n25", "n71"].index(defaults["band"]), help=get_help("frequency.band"))
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
    )

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

# ── Detailed Tabs ──
tab_lb, tab_cov, tab_sinr, tab_cap, tab_qos, tab_rec, tab_map, tab_chart, tab_export = st.tabs([
    "📡 Link Budget", "🗺️ Coverage", "📶 SINR", "📦 Capacity", "✅ QoS", "💡 Recommendations", "🗺️ Map", "📈 Charts", "📥 Export",
])

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
        if not result.capacity.capacity_sufficient:
            st.error(f"❌ **Capacity không đủ**: Cần thêm {result.capacity.additional_sites_needed} sites "
                     f"({result.capacity.total_capacity_dl_gbps:.1f} Gbps supply < {result.capacity.total_demand_dl_gbps:.1f} Gbps demand)")
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

with tab_map:
    st.markdown("### Coverage Map — Bản đồ phủ sóng")

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
    if custom_sites_text.strip():
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
            if custom_sites:
                fmap = generate_interactive_map(result, center_lat=center_lat, center_lon=center_lon, custom_sites=custom_sites, antenna_pattern_override=ant_pattern, return_map=True, site_meta=custom_site_meta)
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

with tab_export:
    st.markdown("### Export — Xuất kết quả")
    json_str = result.model_dump_json(indent=2)
    col_j, col_h, col_m = st.columns(3)

    with col_j:
        st.download_button(
            "📥 JSON Result",
            data=json_str,
            file_name=f"rf5g_{result.project_name.replace(' ', '_')}.json",
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

    # Also show current config for saving
    st.divider()
    st.markdown("#### 💾 Lưu cấu hình hiện tại")
    current_config = st.session_state.get("input", build_input_from_ui()).model_dump()
    config_json = json.dumps(current_config, indent=2, ensure_ascii=False)
    st.code(config_json, language="json")
    st.download_button(
        "💾 Download Config JSON",
        data=config_json,
        file_name=f"config_{result.project_name.replace(' ', '_')}.json",
        mime="application/json",
    )