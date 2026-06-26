"""Tests for Phase 3: Visualization (map, charts, report)."""
import json
import os
import tempfile
import pytest
from rf5g.models.input_schema import RFSizingInput
from rf5g.models.lookup_tables import BandLookup
from rf5g.models.antenna_pattern import antenna_pattern_from_catalog
from rf5g.cli import _run_sizing
from rf5g.viz.coverage_map import generate_coverage_map, generate_interactive_map
from rf5g.viz.charts import plot_link_budget, plot_sinr_heatmap, plot_service_zones, plot_capacity_comparison
from rf5g.viz.report import generate_markdown_report, generate_html_report


class TestCoverageMap:
    """Test Folium coverage map generation."""

    def test_map_generates_html(self):
        """Coverage map should generate valid HTML file."""
        inp = RFSizingInput()
        result = _run_sizing(inp)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = generate_coverage_map(result, output_path=f.name)
            assert os.path.exists(path)
            content = open(path, encoding="utf-8").read()
            assert "folium" in content.lower() or "leaflet" in content.lower()
            assert "Site" in content or "cell" in content.lower()
            # Windows: close file before unlink
            import gc; gc.collect()
            try:
                os.unlink(path)
            except PermissionError:
                pass

    def test_map_with_custom_center(self):
        """Coverage map should accept custom lat/lon."""
        inp = RFSizingInput()
        result = _run_sizing(inp)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = generate_coverage_map(result, center_lat=21.0, center_lon=105.8, output_path=f.name)
            assert os.path.exists(path)
            content = open(path, encoding="utf-8").read()
            assert "21.0" in content or "105.8" in content
            import gc; gc.collect()
            try:
                os.unlink(path)
            except PermissionError:
                pass

    def test_single_sector_catalog_panel_uses_directional_wedge(self):
        """Single-sector catalog panel antennas should render directional coverage, not omni."""
        inp = RFSizingInput(
            base_station={
                "antenna_config": "2T2R",
                "antenna_vendor": "Prose Technologies",
                "antenna_model": "S-Wave 40D-65-9D-64K-B2",
                "sectors": 1,
            },
            frequency={"band": "n78", "bandwidth_mhz": 100.0, "scs_khz": 30},
        )
        result = _run_sizing(inp)
        ant_pattern = antenna_pattern_from_catalog(
            "Prose Technologies",
            "S-Wave 40D-65-9D-64K-B2",
            freq_mhz=BandLookup().get_fc(result.band),
        )
        assert ant_pattern.source == "catalog:atoll"
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = generate_interactive_map(result, output_path=f.name, antenna_pattern_override=ant_pattern)
            assert os.path.exists(path)
            content = open(path, encoding="utf-8").read()
            assert "1-Sector 65°" in content
            assert "Omni coverage" not in content
            import gc; gc.collect()
            try:
                os.unlink(path)
            except PermissionError:
                pass

    def test_catalog_msi_pattern_uses_real_asset(self):
        ant_pattern = antenna_pattern_from_catalog(
            "Ericsson",
            "KRE 101 2571/1 (Antenna 9011)",
            freq_mhz=3500,
        )
        assert ant_pattern.source == "catalog:msi"
        assert ant_pattern.horizontal_pattern
        assert ant_pattern.beamwidth_h_deg > 0

    def test_catalog_atoll_pattern_uses_real_asset(self):
        ant_pattern = antenna_pattern_from_catalog(
            "Prose Technologies",
            "2W2TC-21VMSR",
            freq_mhz=3500,
        )
        assert ant_pattern.source == "catalog:atoll"
        assert ant_pattern.horizontal_pattern
        assert ant_pattern.beamwidth_h_deg > 0

    def test_custom_pattern_source_is_reported(self):
        inp = RFSizingInput(
            base_station={
                "antenna_config": "2T2R",
                "antenna_pattern_source": "file",
                "antenna_pattern_file": "/Users/namnguyen/Downloads/42. Radio and Antenna/Antenna Products/Prose Panel Antenna Outdoor S-Wave 40D-65-9D-64K-B2 Atoll.txt",
                "antenna_pattern_format": "atoll_txt",
            },
            frequency={"band": "n78", "bandwidth_mhz": 100.0, "scs_khz": 30},
        )
        result = _run_sizing(inp)
        html = generate_html_report(result)
        content = open(html, encoding="utf-8").read()
        assert "Pattern Source" in content
        assert "custom:atoll_txt" in content
        import gc; gc.collect()
        try:
            os.unlink(html)
        except PermissionError:
            pass


class TestCharts:
    """Test Matplotlib chart generation."""

    def test_link_budget_chart(self):
        """Link budget chart should generate PNG file."""
        inp = RFSizingInput()
        result = _run_sizing(inp)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = plot_link_budget(result, output_path=f.name)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 1000  # Non-trivial image
            import gc; gc.collect()
            try:
                os.unlink(path)
            except PermissionError:
                pass

    def test_sinr_heatmap(self):
        """SINR heatmap should generate PNG file."""
        inp = RFSizingInput()
        result = _run_sizing(inp)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = plot_sinr_heatmap(result, output_path=f.name)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 1000
            import gc; gc.collect()
            try:
                os.unlink(path)
            except PermissionError:
                pass

    def test_service_zones_chart(self):
        """Service zones chart should generate PNG file."""
        inp = RFSizingInput()
        result = _run_sizing(inp)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = plot_service_zones(result, output_path=f.name)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 1000
            import gc; gc.collect()
            try:
                os.unlink(path)
            except PermissionError:
                pass

    def test_capacity_chart(self):
        """Capacity chart should generate PNG file."""
        inp = RFSizingInput()
        result = _run_sizing(inp)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = plot_capacity_comparison(result, output_path=f.name)
            assert os.path.exists(path)
            assert len(path) > 0
            import gc; gc.collect()
            try:
                os.unlink(path)
            except PermissionError:
                pass


class TestReport:
    """Test report generation (Markdown and HTML)."""

    def test_markdown_report(self):
        """Markdown report should contain key sections."""
        inp = RFSizingInput()
        result = _run_sizing(inp)
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            path = generate_markdown_report(result, output_path=f.name)
            assert os.path.exists(path)
            content = open(path, encoding="utf-8").read()
            assert "Link Budget" in content
            assert "MAPL" in content
            assert "Cell Radius" in content
            assert "Capacity" in content
            assert "QoS" in content or "QoS Verification" in content
            import gc; gc.collect()
            try:
                os.unlink(path)
            except PermissionError:
                pass

    def test_html_report(self):
        """HTML report should be valid HTML with key sections."""
        inp = RFSizingInput()
        result = _run_sizing(inp)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = generate_html_report(result, output_path=f.name)
            assert os.path.exists(path)
            content = open(path, encoding="utf-8").read()
            assert "<html" in content
            assert "Link Budget" in content
            assert "MAPL" in content
            assert "Capacity" in content
            assert "QoS" in content or "qos" in content.lower()
            import gc; gc.collect()
            try:
                os.unlink(path)
            except PermissionError:
                pass

    def test_report_contains_recommendations(self):
        """Report should include recommendations section."""
        inp = RFSizingInput()
        result = _run_sizing(inp)
        md = generate_markdown_report(result)
        content = open(md, encoding="utf-8").read()
        assert "Recommendations" in content or "recommendations" in content.lower()
        import gc; gc.collect()
        try:
            os.unlink(md)
        except PermissionError:
            pass

    def test_report_dense_urban(self):
        """Report for dense urban should mention n78 and sites."""
        with open("examples/dense_urban_n78.json") as f:
            data = json.load(f)
        inp = RFSizingInput(**data)
        result = _run_sizing(inp)
        html = generate_html_report(result)
        content = open(html, encoding="utf-8").read()
        assert "n78" in content
        assert "Sites" in content or "sites" in content
        import gc; gc.collect()
        try:
            os.unlink(html)
        except PermissionError:
            pass