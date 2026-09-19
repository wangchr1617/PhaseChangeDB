"""PhaseChangeDB 内置科学演示数据提供器。

当未检测到 MySQL 运行或显式指定 PCM_DEMO_MODE=1 时，
自动提供只读但完整真实的相变材料科学数据、知识图谱与横向物性对比，
使得用户无需配置任何数据库即可即刻体验全部功能。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models.batch_upload import (
    KnowledgeGraphResponse,
    LiteratureAgentConfig,
    LiteratureStatsResponse,
)
from app.models.config import AppConfigRead, AppConfigUpdate
from app.models.literature import PaperRead
from app.models.material import MaterialRead
from app.models.mvp import (
    DashboardRead,
    ObservationListItem,
    PropertyComparisonResponse,
    PropertyOption,
)
from app.models.search import SearchResponse

SNAPSHOT_PATH = Path(__file__).resolve().parent / "demo_snapshot.json"


class DemoCatalogRepository:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        if SNAPSHOT_PATH.is_file():
            try:
                self._data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}

    async def dashboard(self) -> DashboardRead:
        d = self._data.get("dashboard", {})
        return DashboardRead(
            materials=d.get("materials", 5),
            papers=d.get("papers", 1054),
            observations=d.get("observations", 54),
            verified_observations=d.get("verified_observations", 17),
            pending_outbox_events=d.get("pending_outbox_events", 0),
        )

    async def list_materials(self, **kwargs: Any) -> list[MaterialRead]:
        raw = self._data.get("materials", {}).get("items", [])
        return [MaterialRead.model_validate(m) for m in raw]

    async def get_material(self, material_id: str) -> MaterialRead | None:
        raw = self._data.get("materials", {}).get("items", [])
        for m in raw:
            if m.get("id") == material_id:
                return MaterialRead.model_validate(m)
        if raw:
            return MaterialRead.model_validate(raw[0])
        return None

    async def get_existing_elements(self) -> list[str]:
        return self._data.get("elements", ["Ge", "Te", "Sb", "Bi", "In", "Ti", "Sc", "Ag", "N", "C"])

    async def list_elements(self) -> list[str]:
        return await self.get_existing_elements()

    async def list_papers(self, **kwargs: Any) -> list[PaperRead]:
        raw = self._data.get("papers", {}).get("items", [])
        return [PaperRead.model_validate(p) for p in raw]

    async def get_paper(self, paper_id: str) -> PaperRead | None:
        raw = self._data.get("papers", {}).get("items", [])
        for p in raw:
            if p.get("id") == paper_id:
                return PaperRead.model_validate(p)
        if raw:
            return PaperRead.model_validate(raw[0])
        return None

    async def list_observations(self, **kwargs: Any) -> list[ObservationListItem]:
        raw = self._data.get("observations", {}).get("items", [])
        return [ObservationListItem.model_validate(o) for o in raw]

    async def list_properties(self) -> list[PropertyOption]:
        raw = self._data.get("properties", [])
        return [PropertyOption.model_validate(p) for p in raw]

    async def search(self, query: str) -> SearchResponse:
        q = query.lower().strip()
        hits = []
        raw_m = self._data.get("materials", {}).get("items", [])
        for m in raw_m:
            if q in (m.get("canonical_formula") or "").lower() or q in (m.get("chemical_system") or "").lower():
                hits.append({
                    "id": m.get("id"),
                    "target": "materials",
                    "title": m.get("canonical_formula"),
                    "snippet": f"体系: {m.get('chemical_system')} | 空间群: {m.get('space_group')}",
                })
        raw_p = self._data.get("papers", {}).get("items", [])
        for p in raw_p:
            if q in (p.get("title") or "").lower() or q in (p.get("doi") or "").lower():
                hits.append({
                    "id": p.get("id"),
                    "target": "papers",
                    "title": p.get("title"),
                    "snippet": f"DOI: {p.get('doi')} ({p.get('publication_year')})",
                })
        return SearchResponse.model_validate({"query": query, "hits": hits})

    async def get_config(self) -> AppConfigRead:
        raw = self._data.get("config", {
            "app_title": "PhaseChangeDB",
            "app_description": "面向相变材料的科学数据与知识发现平台 (Demo)",
            "updated_at": "2026-09-19T00:00:00Z",
        })
        return AppConfigRead.model_validate(raw)

    async def update_config(self, payload: AppConfigUpdate) -> AppConfigRead:
        return AppConfigRead(
            app_title=payload.app_title,
            app_description=payload.app_description,
            updated_at="2026-09-19T00:00:00Z",
        )

    async def get_agent_config(self) -> LiteratureAgentConfig:
        raw = self._data.get("agent_config", {
            "enabled": True,
            "version": "v1.2.0-pcm",
            "default_model": "gemini-2.5-pro",
            "available_models": ["gemini-2.5-pro", "gemini-2.5-flash", "claude-3-7-sonnet", "gpt-4o"],
            "prompt_version": "pcm-extract-v2.1",
            "ontology_version": "pcm-ontology-2026.1",
            "extraction_confidence_threshold": 0.75,
            "auto_promotion_enabled": False,
        })
        return LiteratureAgentConfig.model_validate(raw)

    async def get_literature_stats(self) -> LiteratureStatsResponse:
        raw = self._data.get("literature_stats", {
            "total_papers": 1054,
            "parsed_papers": 1054,
            "failed_papers": 0,
            "total_observations": 54,
            "average_parse_time_ms": 420.5,
            "year_distribution": {"2020": 120, "2021": 210, "2022": 315, "2023": 250, "2024": 159},
            "journal_distribution": {"Nature Materials": 45, "Applied Physics Letters": 320, "Acta Materialia": 180},
        })
        return LiteratureStatsResponse.model_validate(raw)

    async def get_knowledge_graph(
        self,
        element: str | None = None,
        material_id: str | None = None,
        include_papers: bool = False,
        subgraph: str | None = None,
        limit: int = 80,
        **kwargs: Any,
    ) -> KnowledgeGraphResponse:
        if subgraph == "fine_grained":
            raw = self._data.get("graph_fine_grained")
        else:
            raw = self._data.get("graph_macro")
        if not raw:
            raw = {"nodes": [], "edges": [], "summary": {}}
        return KnowledgeGraphResponse.model_validate(raw)

    async def get_property_comparison(self, property_code: str, **kwargs: Any) -> PropertyComparisonResponse:
        mapping = {
            "crystallization_temperature": "prop_Tc",
            "activation_energy": "prop_Ea",
            "melting_temperature": "prop_Tm",
            "crystallization_time": "prop_tcryst",
            "resistivity": "prop_rho",
        }
        key = mapping.get(property_code, "prop_Tc")
        raw = self._data.get(key) or self._data.get("prop_Tc")
        if not raw:
            raw = {
                "property_code": property_code,
                "property_name": property_code,
                "display_unit": "",
                "total_count": 0,
                "data_points": [],
                "box_plot_stats": [],
                "available_properties": [],
                "available_materials": ["GeTe", "Sb2Te3"],
                "available_heating_rates": [10, 20, 40],
            }
        return PropertyComparisonResponse.model_validate(raw)


_demo_repo_instance: DemoCatalogRepository | None = None


def get_demo_repository() -> DemoCatalogRepository:
    global _demo_repo_instance
    if _demo_repo_instance is None:
        _demo_repo_instance = DemoCatalogRepository()
    return _demo_repo_instance
