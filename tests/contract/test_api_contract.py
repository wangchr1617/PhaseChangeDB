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

    # v0.3.0 Routes
    assert "/v1/materials/elements" in paths
    assert "/v1/config" in paths

    # v0.4.0 Batch upload, agent & conflict routes
    assert "/v1/materials/{material_id}/conflicts" in paths
    assert "/v1/literature/batch-upload" in paths
    assert "/v1/literature/batch-ingest" in paths
    assert "/v1/agents/literature-parser/config" in paths


@pytest.mark.asyncio
async def test_agent_config_endpoint() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/agents/literature-parser/config")
    assert response.status_code == 200
    data = response.json()
    assert data["agent_name"] == "PhaseChangeLiteratureAgent"
    assert data["enabled"] is True
    assert "gemini-2.5-pro" in data["available_models"]


@pytest.mark.asyncio
async def test_batch_upload_endpoint() -> None:
    transport = httpx.ASGITransport(app=app)
    sample_bib = b"@article{t1, title={Test GST Paper}, author={Zhang, Wei and Li, Ming}, year={2023}}"
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        files = [
            ("files", ("test.bib", sample_bib, "application/x-bibtex")),
        ]
        response = await client.post("/v1/literature/batch-upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["total_files"] == 1
    assert data["parsed_count"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Test GST Paper"
    assert data["items"][0]["first_author"] == "Zhang, Wei"


