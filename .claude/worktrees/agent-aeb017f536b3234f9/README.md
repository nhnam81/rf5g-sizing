# rf5g-sizing — 5G NR RF Coverage Sizing Tool

3GPP TR 38.901 propagation models, link budget analysis, site estimation, and QoS verification for 5G NR network planning.

## Quick Start (Windows)

1. Double-click `rf5g-sizing-1.0.0-setup.exe`
2. Follow the installer wizard
3. Launch from Desktop shortcut or Start Menu
4. Browser opens automatically at `http://localhost:8501`

## Features

- **Propagation Models**: 3GPP TR 38.901 (UMa, UMi, RMa, InH) with LOS/NLOS
- **Link Budget**: DL/UL with 3GPP TS 38.104/38.214 parameters
- **Site Estimation**: Hexagonal grid with MAPL-based radius calculation
- **QoS Verification**: Per-service (VoNR, Video HD, Data, IoT, URLLC, Video 4K)
- **Capacity Analysis**: Throughput estimation and demand verification
- **Coverage Maps**: Interactive Folium maps with hexagonal grid overlay
- **Guided UI**: Step-by-step parameter explanation in Streamlit

## System Requirements

- Windows 10/11 (64-bit)
- ~500 MB disk space
- No Python installation required (embedded)

## Documentation

- [Install Guide](INSTALL_GUIDE.md) — Detailed installation instructions
- [User Guide](USER_GUIDE.md) — How to use the tool

## Manual Installation (Developers)

```bash
git clone https://github.com/nhnam/rf5g-sizing.git
cd rf5g-sizing
pip install -e ".[web,viz]"
streamlit run rf5g/web/app.py
```

## License

MIT License — see [LICENSE](LICENSE) for details.