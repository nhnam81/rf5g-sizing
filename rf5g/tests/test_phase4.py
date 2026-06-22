"""Tests for Phase 4: FastAPI + Streamlit (API endpoints)."""
import json
import pytest
from fastapi.testclient import TestClient
from rf5g.api.app import app
from rf5g.models.input_schema import RFSizingInput


@pytest.fixture
def client():
    return TestClient(app)


class TestAPIInfo:
    """Test root and info endpoints."""

    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert "version" in data
        assert "endpoints" in data

    def test_openapi_docs(self, client):
        resp = client.get("/docs")
        assert resp.status_code == 200


class TestSizeEndpoint:
    """Test /size endpoint."""

    def test_size_default(self, client):
        resp = client.post("/size", json=RFSizingInput().model_dump())
        assert resp.status_code == 200
        data = resp.json()
        assert "project_name" in data
        assert "propagation" in data
        assert "site_estimate" in data
        assert data["propagation"]["cell_radius_m"] > 0
        assert data["site_estimate"]["coverage_sites"] > 0

    def test_size_custom_params(self, client):
        payload = {
            "project": {"name": "Test Urban", "area_km2": 25.0},
            "environment": {"scenario": "UMi", "obstacle_density": "heavy"},
            "frequency": {"band": "n78", "bandwidth_mhz": 100},
            "base_station": {"tx_power_w": 200, "antenna_config": "32T32R"},
        }
        resp = client.post("/size", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_name"] == "Test Urban"
        assert data["environment"] == "UMi"
        assert data["band"] == "n78"

    def test_size_rural_n8(self, client):
        payload = {
            "project": {"name": "Rural n8", "area_km2": 500},
            "environment": {"scenario": "RMa", "obstacle_density": "light"},
            "frequency": {"band": "n8", "bandwidth_mhz": 10},
            "base_station": {"tx_power_w": 40, "antenna_config": "2T2R"},
        }
        resp = client.post("/size", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["band"] == "n8"
        assert data["propagation"]["cell_radius_m"] > 0


class TestQuickSize:
    """Test /size/quick endpoint."""

    def test_quick_default(self, client):
        resp = client.post("/size/quick")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_name"] == "untitled"
        assert data["propagation"]["cell_radius_m"] > 0

    def test_quick_with_params(self, client):
        resp = client.post("/size/quick?area_km2=100&scenario=RMa&band=n41&bandwidth_mhz=50")
        assert resp.status_code == 200
        data = resp.json()
        assert data["environment"] == "RMa"
        assert data["band"] == "n41"


class TestCompareEndpoint:
    """Test /compare endpoint."""

    def test_compare_two(self, client):
        payload = {
            "scenarios": [
                {"project": {"name": "Urban", "area_km2": 50}, "environment": {"scenario": "UMa"}},
                {"project": {"name": "Rural", "area_km2": 500}, "environment": {"scenario": "RMa"}},
            ]
        }
        resp = client.post("/compare", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "comparison" in data
        assert len(data["comparison"]) == 2
        assert data["comparison"][0]["project_name"] == "Urban"
        assert data["comparison"][1]["project_name"] == "Rural"

    def test_compare_too_few(self, client):
        payload = {"scenarios": [{"project": {"name": "Only one"}}]}
        resp = client.post("/compare", json=payload)
        assert resp.status_code == 400


class TestLookupEndpoints:
    """Test lookup table endpoints."""

    def test_list_bands(self, client):
        resp = client.get("/tables/bands")
        assert resp.status_code == 200
        data = resp.json()
        assert "bands" in data
        assert len(data["bands"]) > 0

    def test_get_band(self, client):
        resp = client.get("/tables/bands/n78")
        assert resp.status_code == 200
        data = resp.json()
        assert "fc_mhz" in data
        assert data["fc_mhz"] > 0

    def test_get_band_not_found(self, client):
        resp = client.get("/tables/bands/n999")
        assert resp.status_code == 404

    def test_antenna_configs(self, client):
        resp = client.get("/tables/antenna_configs")
        assert resp.status_code == 200
        data = resp.json()
        assert "configs" in data
        assert len(data["configs"]) > 0

    def test_qos_services(self, client):
        resp = client.get("/tables/qos")
        assert resp.status_code == 200
        data = resp.json()
        assert "services" in data


class TestReportEndpoints:
    """Test report endpoints."""

    def test_html_report(self, client):
        payload = RFSizingInput().model_dump()
        resp = client.post("/report/html", json=payload)
        assert resp.status_code == 200
        assert "<html" in resp.text
        assert "MAPL" in resp.text

    def test_markdown_report(self, client):
        payload = RFSizingInput().model_dump()
        resp = client.post("/report/markdown", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "report" in data
        assert "MAPL" in data["report"]