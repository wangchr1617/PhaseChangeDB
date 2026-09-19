"""Crossref REST API 客户端单元测试。"""

from __future__ import annotations

import httpx
import pytest

from app.infrastructure.parsers.crossref_client import CrossrefClient


def test_crossref_headers_and_mailto() -> None:
    client = CrossrefClient(mailto="test@example.org")
    headers = client.headers
    assert "PhaseChangeDB/1.0 (mailto:test@example.org)" in headers["User-Agent"]
    assert headers["Accept"] == "application/json"


def test_parse_crossref_message_full() -> None:
    sample_message = {
        "DOI": "10.1016/j.actamat.2020.08.001",
        "title": ["<jats:title>Crystallization kinetics</jats:title> in doped GeTe"],
        "container-title": ["Acta Materialia"],
        "published-print": {"date-parts": [[2020, 11, 1]]},
        "author": [
            {"given": "San", "family": "Zhang", "sequence": "first"},
            {"given": "Si", "family": "Li", "sequence": "additional"},
            {"given": "Wu", "family": "Wang", "sequence": "additional"},
        ],
        "abstract": "<jats:p>This study demonstrates high-speed phase transitions.</jats:p>",
    }

    parsed = CrossrefClient.parse_crossref_message(sample_message)
    assert parsed["doi"] == "10.1016/j.actamat.2020.08.001"
    assert parsed["title"] == "Crystallization kinetics in doped GeTe"
    assert parsed["journal"] == "Acta Materialia"
    assert parsed["publication_year"] == 2020
    assert parsed["first_author"] == "San Zhang"
    assert parsed["corresponding_author"] == "Wu Wang"
    assert parsed["authors"] == ["San Zhang", "Si Li", "Wu Wang"]
    assert parsed["abstract"] == "This study demonstrates high-speed phase transitions."
    assert parsed["source"] == "crossref_polite_api"


def test_parse_crossref_message_fallback_dates() -> None:
    # 仅有 published-online
    msg = {
        "doi": "10.1000/xyz123",
        "title": ["Single author work"],
        "published-online": {"date-parts": [[2023, 5]]},
        "author": [{"family": "Curie"}],
    }
    parsed = CrossrefClient.parse_crossref_message(msg)
    assert parsed["publication_year"] == 2023
    assert parsed["first_author"] == "Curie"
    assert parsed["corresponding_author"] == "Curie"
    assert parsed["authors"] == ["Curie"]


@pytest.mark.asyncio
async def test_lookup_doi_mock_success(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_payload = {
        "status": "ok",
        "message": {
            "DOI": "10.1038/s41563-021-01109-w",
            "title": ["Elemental electrical switch"],
            "container-title": ["Nature Materials"],
            "published-print": {"date-parts": [[2021]]},
            "author": [{"given": "Feng", "family": "Rao", "sequence": "first"}],
        },
    }

    class MockResponse:
        status_code = 200

        def json(self) -> dict:
            return mock_payload

        def raise_for_status(self) -> None:
            pass

    async def mock_get(self: httpx.AsyncClient, url: str, **kwargs) -> MockResponse:
        assert "10.1038/s41563-021-01109-w" in url
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    client = CrossrefClient()
    result = await client.lookup_doi("https://doi.org/10.1038/s41563-021-01109-w")
    assert result is not None
    assert result["title"] == "Elemental electrical switch"
    assert result["journal"] == "Nature Materials"
    assert result["publication_year"] == 2021
    assert result["first_author"] == "Feng Rao"


@pytest.mark.asyncio
async def test_lookup_doi_mock_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    class MockResponse404:
        status_code = 404

    async def mock_get_404(self: httpx.AsyncClient, url: str, **kwargs) -> MockResponse404:
        return MockResponse404()

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get_404)

    client = CrossrefClient()
    result = await client.lookup_doi("10.9999/non-existent-doi")
    assert result is None


def test_api_lookup_doi_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    async def mock_lookup(self: CrossrefClient, doi: str):
        if "10.1038" in doi:
            return {
                "doi": doi,
                "title": "Ultra-fast phase change material",
                "journal": "Nature",
                "publication_year": 2022,
                "first_author": "Alice Scientist",
                "corresponding_author": "Bob Professor",
                "authors": ["Alice Scientist", "Bob Professor"],
                "abstract": "Breakthrough in Ge-Sb-Te alloys.",
                "source": "crossref_polite_api",
            }
        return None

    monkeypatch.setattr(CrossrefClient, "lookup_doi", mock_lookup)

    client = TestClient(app)
    resp = client.get("/v1/literature/lookup-doi?doi=10.1038/example-doi")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Ultra-fast phase change material"
    assert data["journal"] == "Nature"
    assert data["publication_year"] == 2022
    assert data["status"] == "parsed"

    # 测试未找到 404
    resp_404 = client.get("/v1/literature/lookup-doi?doi=10.9999/not-found")
    assert resp_404.status_code == 404

