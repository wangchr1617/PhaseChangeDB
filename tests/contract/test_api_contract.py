import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_health_reports_liveness() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_ready_reports_readiness() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.status_code in {200, 503}
    assert response.headers["X-Request-ID"]
    assert "status" in response.json()


def test_mvp_and_workflow_routes_are_present_in_openapi() -> None:
    paths = app.openapi()["paths"]
    assert "/v1/dashboard" in paths
    assert "/v1/materials" in paths
    assert "/v1/papers" in paths
    assert "/v1/observations" in paths
    assert "/v1/search" in paths

    # v0.2.0 Workflow routes
    assert "/v1/workflow/intake" in paths
    assert "/v1/workflow/observations/{observation_id}" in paths
    assert "/v1/workflow/observations/{observation_id}/review" in paths
    assert "/v1/workflow/terms" in paths
