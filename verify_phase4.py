"""Phase 4 verification: FastAPI + Streamlit endpoints."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from rf5g.api.app import app
from rf5g.models.input_schema import RFSizingInput
import json

client = TestClient(app)
passed = 0
failed = 0

def check(name, condition):
    global passed, failed
    if condition:
        print(f"  PASS  {name}")
        passed += 1
    else:
        print(f"  FAIL  {name}")
        failed += 1

print("=" * 70)
print("5G NR RF SIZING TOOL -- PHASE 4 VERIFICATION (API + Web UI)")
print("=" * 70)

# FR-10: Web UI (FastAPI backend)
print("\n[FR-10] FastAPI Backend")
print("-" * 50)

# API info
resp = client.get("/")
check("FR-10: Root endpoint returns API info", resp.status_code == 200)
data = resp.json()
check("FR-10: API has version", "version" in data)
check("FR-10: API lists endpoints", "endpoints" in data)

# OpenAPI docs
resp = client.get("/docs")
check("FR-10: OpenAPI docs accessible", resp.status_code == 200)

# /size endpoint
payload = RFSizingInput().model_dump()
resp = client.post("/size", json=payload)
check("FR-10: /size endpoint works", resp.status_code == 200)
size_data = resp.json()
check("FR-10: /size returns propagation", "propagation" in size_data)
check("FR-10: /size returns site_estimate", "site_estimate" in size_data)
check("FR-10: /size returns SINR", "sinr" in size_data)
check("FR-10: /size returns capacity", "capacity" in size_data)
check("FR-10: /size returns recommendations", "recommendations" in size_data)

# /size/quick
resp = client.post("/size/quick?area_km2=50&scenario=UMa&band=n78")
check("FR-10: /size/quick works", resp.status_code == 200)
quick_data = resp.json()
check("FR-10: Quick size returns cell radius", quick_data["propagation"]["cell_radius_m"] > 0)

# /compare
compare_payload = {
    "scenarios": [
        {"project": {"name": "Urban", "area_km2": 50}, "environment": {"scenario": "UMa"}},
        {"project": {"name": "Rural", "area_km2": 500}, "environment": {"scenario": "RMa"}},
    ]
}
resp = client.post("/compare", json=compare_payload)
check("FR-10: /compare endpoint works", resp.status_code == 200)
compare_data = resp.json()
check("FR-10: /compare returns comparison", "comparison" in compare_data)
check("FR-10: /compare returns 2 scenarios", len(compare_data["comparison"]) == 2)

# /map endpoint
resp = client.post("/map", json=payload)
check("FR-10: /map endpoint generates HTML", resp.status_code == 200)
check("FR-10: Map contains leaflet/folium", "leaflet" in resp.text.lower() or "folium" in resp.text.lower())

# /report/html
resp = client.post("/report/html", json=payload)
check("FR-10: /report/html generates HTML", resp.status_code == 200)
check("FR-10: HTML report contains MAPL", "MAPL" in resp.text)

# /report/markdown
resp = client.post("/report/markdown", json=payload)
check("FR-10: /report/markdown generates content", resp.status_code == 200)
md_data = resp.json()
check("FR-10: MD report contains sections", "MAPL" in md_data["report"])

# /tables endpoints
resp = client.get("/tables/bands")
check("FR-10: /tables/bands works", resp.status_code == 200)
check("FR-10: Bands list not empty", len(resp.json()["bands"]) > 0)

resp = client.get("/tables/bands/n78")
check("FR-10: /tables/bands/n78 works", resp.status_code == 200)
check("FR-10: Band n78 has fc_mhz", "fc_mhz" in resp.json())

resp = client.get("/tables/bands/n999")
check("FR-10: Unknown band returns 404", resp.status_code == 404)

resp = client.get("/tables/antenna_configs")
check("FR-10: /tables/antenna_configs works", resp.status_code == 200)

resp = client.get("/tables/qos")
check("FR-10: /tables/qos works", resp.status_code == 200)

# NFR-02: API response time
import time
start = time.time()
for _ in range(10):
    client.post("/size", json=payload)
elapsed = time.time() - start
check("NFR-02: API avg response < 500ms", elapsed / 10 < 0.5)

# NFR-04: Extensibility (API-first design)
check("NFR-04: API has /size endpoint", "/size" in str(app.routes))
check("NFR-04: API has /compare endpoint", "/compare" in str(app.routes))
check("NFR-04: API has /map endpoint", "/map" in str(app.routes))
check("NFR-04: API has /report endpoint", "/report" in str(app.routes))

# Module structure check
import os
base = os.path.join(os.path.dirname(__file__), "rf5g")
check("FR-10: api/app.py exists", os.path.exists(os.path.join(base, "api", "app.py")))
check("FR-10: web/app.py exists", os.path.exists(os.path.join(base, "web", "app.py")))

print("\n" + "=" * 70)
print(f"PHASE 4 VERIFICATION COMPLETE: {passed} PASSED, {failed} FAILED")
print("=" * 70)

if failed > 0:
    sys.exit(1)