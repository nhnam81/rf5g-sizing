"""Streamlit frontend for rf5g — 5G NR RF Coverage Sizing Tool."""
from __future__ import annotations
import json
import sys
import os
from pathlib import Path

# Add project root to path so rf5g package imports work when running standalone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from rf5g.models.input_schema import RFSizingInput, ProjectConfig, EnvironmentConfig, BaseStationConfig, FrequencyConfig, UEConfig, MarginsConfig, QoSConfig
from rf5g.models.output_schema import SizingOutput
from rf5g.models.lookup_tables import BandLookup
from rf5g.models.antenna_pattern import antenna_pattern_from_catalog, resolve_catalog_radio_total_tx_power_w
from rf5g.cli import _run_sizing
from rf5g.viz.coverage_map import generate_coverage_map, generate_interactive_map
from rf5g.viz.charts import plot_link_budget, plot_sinr_heatmap, plot_service_zones, plot_capacity_comparison
from rf5g.viz.report import generate_html_report, generate_markdown_report
from streamlit_folium import st_folium


@st.cache_data
def _load_catalog() -> dict:
    """Load radio/antenna product catalog."""
    from rf5g.models.lookup_tables import BandLookup
    import json
    catalog_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "radio_antenna_catalog.json")
    with open(catalog_path, encoding="utf-8") as f:
        return json.load(f)

st.set_page_config(
    page_title="5G NR RF Sizing",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📡 5G NR RF Coverage Sizing Tool")
st.caption("3GPP TR 38.901 | TS 38.104, 38.214, 38.306 | Open-source RF planning")
st.info("🧭 Với workflow planning nâng cao (service polygon, exclusion zones, alignments, traffic zones, objective mode), nên dùng **Guided Mode**. Compact mode này phù hợp sizing nhanh và expert users.")

# --- Sidebar: Input Parameters ---
with st.sidebar:
    st.header("⚙️ Input Parameters")

    st.subheader("📋 Project")
    project_name = st.text_input("Project Name", value="Dense Urban n78",
        help="Tên dự án — dùng cho báo cáo và xuất file")
    area_km2 = st.number_input("Coverage Area (km²)", min_value=0.1, value=50.0, step=1.0,
        help="Diện tích vùng phủ sóng cần tính toán (km²)")
    center_lat = st.number_input("Center Latitude", value=10.780000, step=0.000001, format="%.6f",
        help="Vĩ độ tâm vùng phủ (ví dụ: 10.780000 cho TP.HCM)")
    center_lon = st.number_input("Center Longitude", value=106.700000, step=0.000001, format="%.6f",
        help="Kinh độ tâm vùng phủ (ví dụ: 106.700000 cho TP.HCM)")

    st.subheader("🏙️ Environment")
    scenario = st.selectbox("Scenario", ["UMa", "UMi", "RMa", "InH"], index=0,
        help="3GPP TR 38.901 mô hình truyền sóng: UMa (Urban Macro), UMi (Urban Micro), RMa (Rural Macro), InH (Indoor Hotspot)")
    obstacle_density = st.selectbox("Obstacle Density", ["heavy", "medium", "light"], index=0,
        help="Mật độ vật cản: heavy (đô thị dày), medium (ngoại ô), light (nông thôn)")
    coverage_prob = st.slider("Coverage Probability", min_value=0.80, max_value=0.99, value=0.95, step=0.01,
        help="Xác suất phủ sóng ở cell edge — 95% = 95% vị trí cell edge đạt SINR yêu cầu")

    st.subheader("📡 Base Station")
    antenna_config = st.selectbox("Antenna Config", ["32T32R", "64T64R", "8T8R", "4T4R", "2T2R"], index=0,
        help="Cấu hình MIMO antenna: 64T64R (Massive MIMO), 32T32R, 8T8R (beamforming), 4T4R, 2T2R")

    # --- Radio catalog selection ---
    _catalog = _load_catalog()
    _radio_options = [""] + [f"{r['vendor']} {r['model']}" for r in _catalog["radios"]]
    _radio_sel = st.selectbox("📻 Radio", _radio_options, index=0,
        help="Select a radio from the product catalog, or leave blank for manual config")
    _radio_match = None
    _radio_total_tx_power_w = None
    if _radio_sel:
        _radio_match = next(r for r in _catalog["radios"] if f"{r['vendor']} {r['model']}" == _radio_sel)
        _radio_total_tx_power_w = resolve_catalog_radio_total_tx_power_w(_radio_match)
        if _radio_match.get("max_total_power_w") is not None and _radio_match.get("max_tx_power_w") is not None and _radio_match.get("tx_ports"):
            _power_caption = f"{_radio_match['max_tx_power_w']}W/port × {_radio_match['tx_ports']} = {_radio_total_tx_power_w:g}W total"
        elif _radio_total_tx_power_w is not None:
            _power_caption = f"{_radio_total_tx_power_w:g}W total"
        else:
            _power_caption = "TX power unavailable"
        st.caption(f"{_radio_match['description']} — {_power_caption}, {_radio_match.get('mimo_config', '?')}")
        # Auto-fill antenna_config from MIMO config
        _mimo_map = {"2T2R": "2T2R", "4T4R": "4T4R", "8T8R": "8T8R", "32T32R": "32T32R", "64T64R": "64T64R"}
        _radio_mimo = _radio_match.get("mimo_config", "")
        if _radio_mimo in _mimo_map:
            st.info(f"Auto-detected MIMO config: {_radio_mimo}")

    # --- Antenna catalog selection ---
    _ant_options = [""] + [f"{a['vendor']} {a['model']}" for a in _catalog["antennas"]]
    _ant_sel = st.selectbox("📡 Antenna", _ant_options, index=0,
        help="Select an antenna from the product catalog, or leave blank for manual config")
    _ant_match = None
    if _ant_sel:
        _ant_match = next(a for a in _catalog["antennas"] if f"{a['vendor']} {a['model']}" == _ant_sel)
        st.caption(f"{_ant_match['description']} — {_ant_match.get('gain_dbi', '?')} dBi, {_ant_match.get('h_beamwidth_deg', '?')}° azimuth")

    st.caption("Advanced: có thể upload custom antenna pattern để override catalog/built-in pattern cho map/planning.")
    _custom_pattern_upload = st.file_uploader("Custom pattern", type=["ant", "csv", "json", "msi", "txt"], key="compact_custom_pattern")
    _custom_pattern_format = st.selectbox("Pattern format", ["auto", "ant", "csv", "json", "msi", "atoll_txt"], index=0)
    _custom_pattern_name = st.text_input("Pattern row/name (optional)", value="")
    _custom_pattern_freq_mhz = st.number_input("Pattern frequency hint (MHz)", min_value=0.0, value=0.0, step=10.0)
    _custom_pattern_file = None
    if _custom_pattern_upload is not None:
        upload_dir = Path('/Users/namnguyen/rf5g-sizing/.tmp_import/custom_patterns')
        upload_dir.mkdir(parents=True, exist_ok=True)
        upload_path = upload_dir / _custom_pattern_upload.name
        upload_path.write_bytes(_custom_pattern_upload.getvalue())
        _custom_pattern_file = str(upload_path)
        st.caption(f"Using custom pattern: {upload_path.name}")

    tx_power_w = st.number_input("TX Power (W)", min_value=1.0, value=float(_radio_total_tx_power_w) if _radio_sel and _radio_total_tx_power_w is not None else 200.0, step=10.0,
        help="Tổng công suất phát mỗi sector/radio (Watt), cộng trên tất cả TX ports — tự động điền từ catalog Radio nếu chọn")
    bs_height_m = st.number_input("BS Height (m)", min_value=5.0, value=25.0, step=1.0,
        help="Chiều cao anten trạm gốc so mặt đất (mét)")
    sectors = st.selectbox("Sectors", [1, 3, 6], index=1,
        help="Số sector mỗi trạm: 1 (omni), 3 (tri-sector phổ biến), 6 (hex-sector)")

    st.subheader("📶 Frequency")
    band = st.selectbox("NR Band", ["n78", "n77", "n41", "n1", "n3", "n8", "n28", "n25", "n71", "n257", "n258", "n261"], index=0,
        help="3GPP NR band: n78/n77 (3.5GHz C-Band), n41 (2.5GHz), n1/n3 (FDD 2.1/1.8GHz), n257/n258/n261 (mmWave 28/39/28GHz)")
    bandwidth_mhz = st.number_input("Bandwidth (MHz)", min_value=5.0, value=100.0, step=5.0,
        help="Băng thông kênh — n78: 100MHz, n77: 100MHz, n41: up to 100MHz, mmWave: 50-400MHz")
    scs_khz = st.selectbox("SCS (kHz)", [15, 30, 60, 120], index=1,
        help="Subcarrier Spacing — 30kHz phổ biến n78/n77, 15kHz cho FDD low-band, 120kHz cho mmWave")

    # Auto-detect duplex from band data
    _bl_info = BandLookup()
    _band_duplex = _bl_info.get_band(band).get("duplex", "TDD")
    st.info(f"{_band_duplex} mode" + (" — TDD DL Ratio applies" if _band_duplex == "TDD" else " — Full duplex, DL ratio = 1.0"))
    tdd_dl_ratio = st.slider("TDD DL Ratio", min_value=0.5, max_value=0.9, value=0.70, step=0.05, disabled=(_band_duplex == "FDD"))

    st.subheader("📱 UE")
    power_class = st.selectbox("Power Class", ["PC1", "PC2", "PC3", "PC4"], index=2,
        help="3GPP UE Power Class: PC1 (31dBm macro), PC2 (26dBm), PC3 (23dBm phổ biến), PC4 (20dBm)")
    ue_height_m = st.number_input("UE Height (m)", min_value=1.0, value=1.5, step=0.1,
        help="Chiều cao thiết bị di động so mặt đất (mét)")
    ue_noise_figure = st.number_input("UE Noise Figure (dB)", min_value=0.0, value=7.0, step=0.5,
        help="Hệ số nhiễu nhiệt UE — 7dB là giá trị điển hình cho smartphone")

    st.subheader("📊 Margins")
    interference_db = st.number_input("Interference Margin (dB)", min_value=0.0, value=3.0, step=0.5,
        help="Dự trù nhiễu đồng kênh — 3-6dB cho mạng đô thị dày, 1-2dB nông thôn")
    penetration_db = st.number_input("Penetration Loss (dB)", min_value=0.0, value=10.0, step=1.0,
        help="Suy hao xuyên tường — 10-15dB (thấp/ttrung), 20-30dB (dày)")
    rain_db = st.number_input("Rain Attenuation (dB)", min_value=0.0, value=1.0, step=0.5,
        help="Suy hao mưa — chỉ đáng kể ở tần số >10GHz (mmWave), gần như 0 ở 3.5GHz")
    overlap_factor = st.number_input("Overlap Factor", min_value=0.0, max_value=0.5, value=0.25, step=0.05,
        help="Hệ số chồng lấp giữa các sector — 0.25 = 25% vùng phủ chồng nhau")

    st.subheader("🎯 QoS")
    primary_service = st.selectbox("Primary Service", ["mixed", "vonr", "video_hd", "video_4k", "data", "gaming", "iot"], index=0,
        help="Dịch vụ chính: mixed (tổng hợp), vonr (Voice over NR), video_hd/4k, data (eMBB), gaming (URLLC), iot (mMTC)")
    users_per_km2 = st.number_input("Users per km²", min_value=1.0, value=300.0, step=10.0,
        help="Mật độ người dùng trên km² — 300 điển hình đô thị, 50-100 nông thôn")
    dl_per_user_mbps = st.number_input("DL per User (Mbps)", min_value=0.5, value=20.0, step=1.0,
        help="Tốc độ downlink yêu cầu mỗi user — 5-10Mbps (VoNR), 20Mbps (HD), 50+Mbps (4K)")
    ul_per_user_mbps = st.number_input("UL per User (Mbps)", min_value=0.1, value=5.0, step=0.5,
        help="Tốc độ uplink yêu cầu mỗi user — 1-3Mbps (VoNR), 5Mbps (video call)")
    concurrent_ratio = st.number_input("Concurrent Ratio", min_value=0.01, max_value=0.99, value=0.10, step=0.01,
        help="Tỷ lệ user đồng thời hoạt động — 0.1 = 10% user đang truyền dữ liệu cùng lúc")

    st.divider()
    run_button = st.button("🚀 Calculate", width="stretch", type="primary")

    # Load config file
    st.subheader("📁 Load Config")
    st.caption("Tip: config có `placement` / `spatial_capacity` sẽ được backend hiểu, nhưng Guided Mode hiển thị planning workflow tốt hơn.")
    uploaded = st.file_uploader("Upload JSON config", type=["json"])
    if uploaded:
        try:
            config_data = json.loads(uploaded.read().decode())
            st.session_state["loaded_config"] = config_data
            st.success(f"Loaded: {config_data.get('project', {}).get('name', 'unnamed')}")
        except Exception as e:
            st.error(f"Invalid JSON: {e}")

# --- Build input ---
def build_input() -> RFSizingInput:
    if "loaded_config" in st.session_state:
        return RFSizingInput(**st.session_state["loaded_config"])
    # Auto-detect duplex from band data
    _bl = BandLookup()
    _band_info = _bl.get_band(band)
    _duplex = _band_info.get("duplex", "TDD")
    # For FDD bands, hide TDD DL ratio and set to 1.0 (full duplex)
    if _duplex == "FDD":
        tdd_dl_ratio_final = 1.0
    else:
        tdd_dl_ratio_final = tdd_dl_ratio
    # Resolve radio/antenna catalog selections
    _radio_vendor = None
    _radio_model = None
    _antenna_vendor = None
    _antenna_model = None
    if _radio_sel:
        _rm = next(r for r in _load_catalog()["radios"] if f"{r['vendor']} {r['model']}" == _radio_sel)
        _radio_vendor = _rm["vendor"]
        _radio_model = _rm["model"]
    if _ant_sel:
        _am = next(a for a in _load_catalog()["antennas"] if f"{a['vendor']} {a['model']}" == _ant_sel)
        _antenna_vendor = _am["vendor"]
        _antenna_model = _am["model"]

    base_station = BaseStationConfig(
            antenna_config=antenna_config,
            radio_vendor=_radio_vendor,
            radio_model=_radio_model,
            antenna_vendor=_antenna_vendor,
            antenna_model=_antenna_model,
            tx_power_w=tx_power_w,
            height_m=bs_height_m,
            sectors=sectors,
            cable_loss_db=1.0,
            noise_figure_db=3.5,
        )
    if _custom_pattern_file:
        base_station.antenna_pattern_source = 'file'
        base_station.antenna_pattern_file = _custom_pattern_file
        base_station.antenna_pattern_format = None if _custom_pattern_format == 'auto' else _custom_pattern_format
        base_station.antenna_pattern_name = _custom_pattern_name or None
        base_station.antenna_pattern_freq_mhz = _custom_pattern_freq_mhz or None

    return RFSizingInput(
        project=ProjectConfig(
            name=project_name,
            area_km2=area_km2,
            center_lat=center_lat,
            center_lon=center_lon,
        ),
        environment=EnvironmentConfig(
            scenario=scenario,
            obstacle_density=obstacle_density,
            coverage_probability=coverage_prob,
        ),
        base_station=base_station,
        frequency=FrequencyConfig(
            band=band,
            bandwidth_mhz=bandwidth_mhz,
            scs_khz=scs_khz,
            tdd_dl_ratio=tdd_dl_ratio_final,
            duplex=_duplex,
        ),
        user_equipment=UEConfig(
            power_class=power_class,
            height_m=ue_height_m,
            noise_figure=ue_noise_figure,
        ),
        margins=MarginsConfig(
            interference_db=interference_db,
            penetration_db=penetration_db,
            rain_attenuation_db=rain_db,
            overlap_factor=overlap_factor,
        ),
        qos=QoSConfig(
            primary_service=primary_service,
            users_per_km2=users_per_km2,
            dl_per_user_mbps=dl_per_user_mbps,
            ul_per_user_mbps=ul_per_user_mbps,
            concurrent_ratio=concurrent_ratio,
        ),
    )

# --- Run calculation ---
if run_button or "result" in st.session_state:
    with st.spinner("Calculating..."):
        try:
            inp = build_input()
            result = _run_sizing(inp)
            st.session_state["result"] = result
            st.session_state["input"] = inp
        except Exception as e:
            st.error(f"Calculation error: {e}")
            st.stop()

if "result" not in st.session_state:
    st.info("Configure parameters in the sidebar and click **Calculate** to see results.")
    st.stop()

result: SizingOutput = st.session_state["result"]
input_state: RFSizingInput = st.session_state["input"]

# --- Results Display ---
tab_overview, tab_link_budget, tab_coverage, tab_sinr, tab_capacity, tab_qos, tab_recs, tab_map, tab_charts = st.tabs([
    "📊 Overview", "📡 Link Budget", "🗺️ Coverage", "📶 SINR", "📦 Capacity", "✅ QoS", "💡 Recommendations", "🗺️ Map", "📈 Charts"
])

# --- Overview ---
with tab_overview:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Cell Radius", f"{result.propagation.cell_radius_m:.0f} m")
    col2.metric("Coverage Sites", f"{result.site_estimate.coverage_sites}")
    col3.metric("Limiting Link", result.site_estimate.limiting_link)
    col4.metric("Cell Edge SINR", f"{result.sinr.sinr_db:.1f} dB")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("DL MAPL", f"{result.link_budget_dl.mapl_db:.1f} dB")
    col6.metric("UL MAPL", f"{result.link_budget_ul.mapl_db:.1f} dB")
    if result.capacity:
        cap_color = "🟢" if result.capacity.capacity_sufficient else "🔴"
        col7.metric("Capacity", f"{cap_color} {'Sufficient' if result.capacity.capacity_sufficient else 'Insufficient'}")
        col8.metric("Total Sites", f"{result.capacity.total_sites}")

    st.divider()
    st.subheader("📋 Summary")
    st.write(f"**Project:** {result.project_name} | **Scenario:** {result.environment} | **Band:** {result.band} {result.bandwidth_mhz:.0f}MHz")
    st.write(f"**TX Power:** {result.tx_power_w}W | **Antenna:** {result.antenna_config} | **Propagation:** {result.propagation.model}")
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

    # JSON export
    col_dl, col_rpt = st.columns(2)
    with col_dl:
        json_str = result.model_dump_json(indent=2)
        st.download_button("📥 Download JSON", data=json_str, file_name=f"rf5g_{result.project_name.replace(' ', '_')}.json", mime="application/json")
    with col_rpt:
        html_path = generate_html_report(result)
        html_content = open(html_path, encoding="utf-8").read()
        st.download_button("📄 Download HTML Report", data=html_content, file_name=f"rf5g_{result.project_name.replace(' ', '_')}.html", mime="text/html")

# --- Link Budget ---
with tab_link_budget:
    st.subheader("Link Budget")
    lb_data = {
        "Parameter": ["EIRP", "Rx Sensitivity", "MAPL", "Shadow Fading", "Penetration Loss", "Interference"],
        "DL (dBm/dB)": [
            f"{result.link_budget_dl.eirp_dbm:.1f}",
            f"{result.link_budget_dl.rx_sensitivity_dbm:.1f}",
            f"{result.link_budget_dl.mapl_db:.1f}",
            f"{result.link_budget_dl.shadow_fading_margin_db:.1f}",
            f"{result.link_budget_dl.penetration_loss_db:.1f}",
            f"{result.link_budget_dl.interference_margin_db:.1f}",
        ],
        "UL (dBm/dB)": [
            f"{result.link_budget_ul.eirp_dbm:.1f}",
            f"{result.link_budget_ul.rx_sensitivity_dbm:.1f}",
            f"{result.link_budget_ul.mapl_db:.1f}",
            f"{result.link_budget_ul.shadow_fading_margin_db:.1f}",
            f"{result.link_budget_ul.penetration_loss_db:.1f}",
            f"{result.link_budget_ul.interference_margin_db:.1f}",
        ],
    }
    st.dataframe(lb_data, width="stretch")

# --- Coverage ---
with tab_coverage:
    st.subheader("Coverage Estimate")
    cov_data = {
        "Parameter": ["Propagation Model", "Path Loss", "Cell Radius", "LOS Probability", "ISD", "Coverage Sites"],
        "Value": [
            result.propagation.model,
            f"{result.propagation.path_loss_db:.1f} dB",
            f"{result.propagation.cell_radius_m:.0f} m ({result.propagation.cell_radius_km:.3f} km)",
            f"{result.propagation.los_probability:.1%}" if result.propagation.los_probability else "N/A",
            f"{result.site_estimate.isd_km * 1000:.0f} m",
            f"{result.site_estimate.coverage_sites}",
        ],
    }
    st.dataframe(cov_data, width="stretch")

# --- SINR ---
with tab_sinr:
    st.subheader("SINR & Modulation")
    sinr_data = {
        "Parameter": ["Cell Edge SINR", "CQI", "Modulation", "Spectral Efficiency", "Code Rate"],
        "Value": [
            f"{result.sinr.sinr_db:.1f} dB",
            str(result.sinr.cqi),
            result.sinr.modulation,
            f"{result.sinr.spectral_efficiency_bps_hz:.4f} bps/Hz",
            f"{result.sinr.code_rate:.4f}",
        ],
    }
    st.dataframe(sinr_data, width="stretch")

# --- Capacity ---
with tab_capacity:
    if result.capacity:
        st.subheader("Capacity Dimensioning")
        cap_data = {
            "Parameter": [
                "Cell DL Throughput", "Cell UL Throughput", "Total DL Capacity",
                "Total DL Demand", "Capacity Sufficient", "Total Sites (cov+cap)",
            ],
            "Value": [
                f"{result.capacity.cell_throughput_dl_mbps:.1f} Mbps",
                f"{result.capacity.cell_throughput_ul_mbps:.1f} Mbps",
                f"{result.capacity.total_capacity_dl_gbps:.2f} Gbps",
                f"{result.capacity.total_demand_dl_gbps:.2f} Gbps",
                "✅ YES" if result.capacity.capacity_sufficient else "❌ NO",
                str(result.capacity.total_sites),
            ],
        }
        st.dataframe(cap_data, width="stretch")
        if result.capacity.additional_sites_needed > 0:
            st.warning(f"⚠️ Additional {result.capacity.additional_sites_needed} sites needed for capacity.")
    else:
        st.info("Capacity calculation not available.")

# --- QoS ---
with tab_qos:
    if result.qos_verification:
        st.subheader("QoS Verification")
        qos_rows = []
        for q in result.qos_verification:
            qos_rows.append({
                "Service": q.service,
                "SINR Required": f"{q.sinr_required_db:.0f} dB",
                "SINR Available": f"{q.sinr_available_db:.1f} dB",
                "Area %": f"{q.area_percentage:.0f}%",
                "Status": "✅ PASS" if q.passed else "❌ FAIL",
            })
        st.dataframe(qos_rows, width="stretch")
    else:
        st.info("QoS verification not available.")

# --- Recommendations ---
with tab_recs:
    if result.recommendations:
        st.subheader("Recommendations")
        for i, rec in enumerate(result.recommendations, 1):
            st.write(f"{i}. {rec}")
    else:
        st.info("No specific recommendations.")

# --- Map ---
with tab_map:
    st.subheader("📡 Coverage Map")

    # Map mode selector
    map_mode = st.radio(
        "Map overlay",
        ["Coverage", "Capacity"],
        horizontal=True,
        key="map_mode",
    )

    # Manual station editor
    st.markdown("**Add manual sites** (optional): comma-separated `lat, lon, azimuth°, beamwidth°`")
    manual_input = st.text_area(
        "Manual sites",
        placeholder="10.782, 106.695, 0, 65\n10.785, 106.700, 120, 65",
        key="manual_sites",
    )

    site_meta = None
    custom_sites = None
    if manual_input.strip():
        try:
            parsed = []
            meta = []
            for line in manual_input.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                lat = float(parts[0])
                lon = float(parts[1])
                azimuth = float(parts[2]) if len(parts) > 2 else 0
                beamwidth = float(parts[3]) if len(parts) > 3 else 65
                parsed.append((lat, lon))
                meta.append({"azimuth": azimuth, "beamwidth": beamwidth})
            custom_sites = parsed
            site_meta = meta
            st.success(f"Parsed {len(parsed)} manual site(s)")
        except Exception as e:
            st.warning(f"Could not parse manual sites: {e}")

    # Coverage vs Capacity color
    n_cov = result.site_estimate.coverage_sites
    n_cap = getattr(result.site_estimate, "capacity_sites", None) or n_cov
    is_capacity = map_mode == "Capacity"
    n_sites = max(n_cov, n_cap) if is_capacity else n_cov
    center_lat_map = result.project_name and center_lat or 10.8231
    center_lon_map = result.project_name and center_lon or 106.6297

    antenna_pattern_override = None
    if input_state.base_station.antenna_vendor and input_state.base_station.antenna_model:
        try:
            freq_mhz = BandLookup().get_fc(result.band)
            antenna_pattern_override = antenna_pattern_from_catalog(
                input_state.base_station.antenna_vendor,
                input_state.base_station.antenna_model,
                freq_mhz=freq_mhz,
            )
        except Exception:
            antenna_pattern_override = None

    with st.spinner("Generating map..."):
        try:
            folium_map = generate_interactive_map(
                result,
                center_lat=center_lat_map,
                center_lon=center_lon_map,
                custom_sites=custom_sites,
                antenna_pattern_override=antenna_pattern_override,
                site_meta=site_meta,
                return_map=True,
            )
            st_folium(folium_map, width="stretch", height=600)
        except Exception as e:
            st.error(f"Map generation error: {e}")

# --- Charts ---
with tab_charts:
    st.subheader("Charts")
    import tempfile
    import matplotlib.pyplot as plt

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.write("**Link Budget**")
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                lb_path = plot_link_budget(result, output_path=f.name)
                st.image(lb_path)
        except Exception as e:
            st.error(f"Chart error: {e}")

        st.write("**Service Zones**")
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                sz_path = plot_service_zones(result, output_path=f.name)
                st.image(sz_path)
        except Exception as e:
            st.error(f"Chart error: {e}")

    with chart_col2:
        st.write("**SINR Heatmap**")
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                sh_path = plot_sinr_heatmap(result, output_path=f.name)
                st.image(sh_path)
        except Exception as e:
            st.error(f"Chart error: {e}")

        if result.capacity:
            st.write("**Capacity**")
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    cap_path = plot_capacity_comparison(result, output_path=f.name)
                    if cap_path:
                        st.image(cap_path)
            except Exception as e:
                st.error(f"Chart error: {e}")