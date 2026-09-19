import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def demo_client(monkeypatch):
    monkeypatch.setenv("PCM_DEMO_MODE", "1")
    from app.main import app
    return TestClient(app)

def test_demo_mode_health_and_ready(demo_client):
    r_health = demo_client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json() == {"status": "ok"}

    r_ready = demo_client.get("/ready")
    assert r_ready.status_code == 200
    assert r_ready.json() == {"status": "ready", "database": "demo_mode"}

def test_demo_mode_dashboard_and_api_prefix(demo_client):
    r1 = demo_client.get("/v1/dashboard")
    assert r1.status_code == 200
    assert r1.json()["materials"] >= 1

    # 验证 /api/v1 前缀别名
    r2 = demo_client.get("/api/v1/dashboard")
    assert r2.status_code == 200
    assert r2.json() == r1.json()

def test_demo_mode_materials_and_elements(demo_client):
    r = demo_client.get("/v1/materials")
    assert r.status_code == 200
    assert len(r.json()["items"]) > 0

    r_elem = demo_client.get("/v1/materials/elements")
    assert r_elem.status_code == 200
    assert "Ge" in r_elem.json()

def test_demo_mode_property_comparison(demo_client):
    r = demo_client.get("/v1/analytics/property-comparison?property_code=crystallization_temperature")
    assert r.status_code == 200
    data = r.json()
    assert len(data["data_points"]) > 0
    assert len(data["box_plot_stats"]) > 0

def test_demo_mode_knowledge_graph(demo_client):
    r = demo_client.get("/v1/knowledge-graph/graph?subgraph=fine_grained")
    assert r.status_code == 200
    data = r.json()
    assert len(data["nodes"]) > 0
    assert len(data["edges"]) > 0

def test_demo_mode_static_html(demo_client):
    r = demo_client.get("/")
    assert r.status_code == 200
    assert "PhaseChangeDB" in r.text or "html" in r.text
