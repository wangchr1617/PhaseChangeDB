import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_get_property_comparison_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 默认获取 crystallization_temperature 对比数据
        resp = await client.get("/v1/analytics/property-comparison?property_code=crystallization_temperature")
        assert resp.status_code == 200
        data = resp.json()

        assert data["property_code"] == "crystallization_temperature"
        assert "data_points" in data
        assert "box_plot_stats" in data
        assert "available_materials" in data
        assert "available_heating_rates" in data
        assert len(data["available_properties"]) > 0

        # 如果有观测数据，校验字段结构与数值合理性
        if data["total_count"] > 0:
            dp = data["data_points"][0]
            assert "observation_id" in dp
            assert "value" in dp
            assert dp["unit"] in ("°C", "K")
            assert "base_material" in dp
            assert "sample_formula" in dp

        # 2. 升温速率过滤
        resp_hr = await client.get("/v1/analytics/property-comparison?heating_rate=20")
        assert resp_hr.status_code == 200
        data_hr = resp_hr.json()
        for dp in data_hr["data_points"]:
            if dp["heating_rate_k_per_min"] is not None:
                assert abs(dp["heating_rate_k_per_min"] - 20.0) < 0.1

        # 3. 温度单位切换为 kelvin
        resp_k = await client.get("/v1/analytics/property-comparison?display_unit=kelvin")
        assert resp_k.status_code == 200
        assert resp_k.json()["display_unit"] == "K"


@pytest.mark.asyncio
async def test_fine_grained_evidence_graph_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/knowledge-graph/graph?subgraph=fine_grained&limit=50")
        assert resp.status_code == 200
        data = resp.json()

        assert "nodes" in data
        assert "edges" in data
        assert "summary" in data
        assert data["summary"]["total_nodes"] == len(data["nodes"])
        assert data["summary"]["total_edges"] == len(data["edges"])

        node_types = {n["node_type"] for n in data["nodes"]}
        # 验证是否生成细粒度的 observation 或 dopant 或 material 节点
        assert "material" in node_types or len(data["nodes"]) == 0
