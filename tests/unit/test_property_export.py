"""物性横向对比科研数据导出端点测试。"""

from __future__ import annotations

import codecs

from fastapi.testclient import TestClient

from app.main import app


def test_export_property_comparison_csv() -> None:
    client = TestClient(app)
    resp = client.get("/v1/analytics/property-comparison/export?property_code=crystallization_temperature&format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment; filename=" in resp.headers["content-disposition"]
    # 验证 UTF-8 BOM 存在
    assert resp.content.startswith(codecs.BOM_UTF8)
    text = resp.content.decode("utf-8")
    assert "observation_id,property_code,property_name" in text
    assert "crystallization_temperature" in text


def test_export_property_comparison_json() -> None:
    client = TestClient(app)
    resp = client.get("/v1/analytics/property-comparison/export?property_code=crystallization_temperature&format=json")
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]
    data = resp.json()
    assert data["property_code"] == "crystallization_temperature"
    assert "data_points" in data
