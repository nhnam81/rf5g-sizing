# rf5g-sizing — 5G NR RF Coverage Sizing Tool

3GPP TR 38.901 propagation models, link budget analysis, site estimation, and QoS verification for 5G NR network planning.

## Quick Start (Windows)

1. Double-click `rf5g-sizing-1.4.0-setup.exe`
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
- [ROADMAP.md](ROADMAP.md) — Milestone direction and sequencing
- [BACKLOG.md](BACKLOG.md) — Issue catalog for future implementation work
- [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md) — Session/sprint progress log and next actions

## Planning and issue tracking

Use the repo planning files together:
- `ROADMAP.md` defines milestone direction and sequencing
- `BACKLOG.md` holds issue-ready work items grouped by milestone
- `.github/ISSUE_TEMPLATE/` holds the GitHub Issue Forms used to create execution/tracking issues from backlog items
- `.github/tracking-issues/` holds copy/paste-ready milestone tracking issue bodies
- `IMPLEMENTATION_LOG.md` records session/sprint progress, blockers, and next actions

When opening a new implementation issue, preserve the backlog structure:
- **Why**
- **Scope**
- **Acceptance criteria**

## Manual Installation (Developers)

```bash
git clone https://github.com/nhnam/rf5g-sizing.git
cd rf5g-sizing
pip install -e ".[web,viz]"
streamlit run rf5g/web/app.py
```

## CLI Usage

```bash
# Calculate sizing from config file
rf5g size --config examples/dense_urban_n78.json --output results.json

# Quick sizing with command-line options
rf5g size --area 50 --scenario UMa --band n78 --power 200

# Generate HTML report
rf5g report --config examples/dense_urban_n78.json --format html

# Generate interactive coverage map
rf5g map --config examples/dense_urban_n78.json --output coverage.html

# Export site positions
rf5g sites export-json --config examples/dense_urban_n78.json --output sites.json

# Run geometry-aware planning
rf5g plan --config planning_config.json
```

## License

MIT License — see [LICENSE](LICENSE) for details.