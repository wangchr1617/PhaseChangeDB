"""PhaseChangeDB MySQL 聚合仓储门面 (Facade)。

为了治理原 2242 行上帝类带来的架构负债，各领域具体 SQL 与映射逻辑已全面解耦下沉至
`app/infrastructure/repositories/` 细分子仓储中：
- MySQLMaterialRepository (材料、变体、元素周期表、冲突检测)
- MySQLLiteratureRepository (论文目录、作者关联、批量录入、统计分布)
- MySQLObservationRepository (物性定义、观测记录、跨文献横向对比看板)
- MySQLGraphRepository (科学知识图谱多级关联子图)
- MySQLConfigRepository (系统配置、全局概览看板、基础检索)

本类作为向后兼容的轻量聚合门面（Facade），保留全部原有公共方法契约，确保既有 API 路由、
用例编排与集成测试 100% 零破坏性平滑运行。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.repositories.config_repository import MySQLConfigRepository
from app.infrastructure.repositories.graph_repository import MySQLGraphRepository
from app.infrastructure.repositories.literature_repository import MySQLLiteratureRepository
from app.infrastructure.repositories.material_repository import MySQLMaterialRepository
from app.infrastructure.repositories.observation_repository import MySQLObservationRepository
from app.models.batch_upload import (
    BatchIngestItem,
    BatchIngestRequest,
    BatchIngestResponse,
    KnowledgeGraphResponse,
    LiteratureStatsResponse,
    ObservationConflictGroup,
)
from app.models.config import AppConfigRead, AppConfigUpdate
from app.models.literature import PaperCreate, PaperRead
from app.models.material import MaterialCreate, MaterialRead
from app.models.mvp import (
    DashboardRead,
    ObservationListItem,
    PropertyComparisonResponse,
    PropertyOption,
)
from app.models.observation import ObservationCreate, ObservationRead
from app.models.search import SearchHit


class MySQLCatalogRepository:
    """MySQL 仓储聚合门面。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.material_repo = MySQLMaterialRepository(session)
        self.literature_repo = MySQLLiteratureRepository(session)
        self.observation_repo = MySQLObservationRepository(session)
        self.graph_repo = MySQLGraphRepository(session)
        self.config_repo = MySQLConfigRepository(session)

    # ----------------- Dashboard & Config & Search -----------------
    async def dashboard(self) -> DashboardRead:
        return await self.config_repo.dashboard()

    async def get_config(self) -> AppConfigRead:
        return await self.config_repo.get_config()

    async def update_config(self, body: AppConfigUpdate) -> AppConfigRead:
        return await self.config_repo.update_config(body)

    async def search(self, query: str, limit: int) -> list[SearchHit]:
        return await self.config_repo.search(query, limit)

    # ----------------- Materials -----------------
    async def list_materials(
        self,
        query: str | None = None,
        limit: int = 50,
        elements: list[str] | None = None,
        min_tc: float | None = None,
        max_tc: float | None = None,
        min_latent_heat: float | None = None,
        max_latent_heat: float | None = None,
        low_toxicity: bool | None = None,
        cost_effective: bool | None = None,
    ) -> list[MaterialRead]:
        return await self.material_repo.list_materials(
            query=query,
            limit=limit,
            elements=elements,
            min_tc=min_tc,
            max_tc=max_tc,
            min_latent_heat=min_latent_heat,
            max_latent_heat=max_latent_heat,
            low_toxicity=low_toxicity,
            cost_effective=cost_effective,
        )

    async def get_existing_elements(self) -> list[str]:
        return await self.material_repo.get_existing_elements()

    async def get_material(self, material_id: str) -> MaterialRead | None:
        return await self.material_repo.get_material(material_id)

    async def create_material(self, body: MaterialCreate) -> MaterialRead:
        return await self.material_repo.create_material(body)

    async def get_material_conflicts(self, material_id: str) -> list[ObservationConflictGroup]:
        return await self.material_repo.get_material_conflicts(material_id)

    # ----------------- Literature -----------------
    async def list_papers(self, query: str | None = None, limit: int = 50) -> list[PaperRead]:
        return await self.literature_repo.list_papers(query, limit)

    async def get_paper(self, paper_id: str) -> PaperRead | None:
        return await self.literature_repo.get_paper(paper_id)

    async def create_paper(self, body: PaperCreate) -> PaperRead:
        return await self.literature_repo.create_paper(body)

    async def batch_ingest_papers(
        self, request: BatchIngestRequest | list[BatchIngestItem]
    ) -> BatchIngestResponse:
        return await self.literature_repo.batch_ingest_papers(request)

    async def get_literature_stats(self) -> LiteratureStatsResponse:
        return await self.literature_repo.get_literature_stats()

    # ----------------- Observations & Analytics -----------------
    async def list_observations(self, limit: int = 50) -> list[ObservationListItem]:
        return await self.observation_repo.list_observations(limit)

    async def create_observation(self, body: ObservationCreate) -> ObservationRead:
        return await self.observation_repo.create_observation(body)

    async def list_properties(self) -> list[PropertyOption]:
        return await self.observation_repo.list_properties()

    async def get_property_comparison(
        self,
        property_code: str = "crystallization_temperature",
        base_material: str | None = None,
        heating_rate: float | None = None,
        display_unit: str = "celsius",
    ) -> PropertyComparisonResponse:
        return await self.observation_repo.get_property_comparison(
            property_code=property_code,
            base_material=base_material,
            heating_rate=heating_rate,
            display_unit=display_unit,
        )

    # ----------------- Knowledge Graph -----------------
    async def get_knowledge_graph(
        self,
        element: str | None = None,
        material_id: str | None = None,
        include_papers: bool = False,
        subgraph: str | None = None,
        limit: int = 60,
    ) -> KnowledgeGraphResponse:
        return await self.graph_repo.get_knowledge_graph(
            element=element,
            material_id=material_id,
            include_papers=include_papers,
            subgraph=subgraph,
            limit=limit,
        )

    # ----------------- 静态辅助转换适配方法 -----------------
    @staticmethod
    def _material(row: Any) -> MaterialRead:
        return MySQLMaterialRepository._material(row)

    @staticmethod
    def _paper(row: Any, authors_info: list[dict[str, Any]] | None = None) -> PaperRead:
        return MySQLLiteratureRepository._paper(row, authors_info)

    @staticmethod
    def _observation_value(row: Any) -> float | str | bool | None:
        return MySQLObservationRepository._observation_value(row)
