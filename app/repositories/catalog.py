from typing import Protocol

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
from app.models.mvp import DashboardRead, ObservationListItem, PropertyOption
from app.models.observation import ObservationCreate, ObservationRead
from app.models.search import SearchHit


class CatalogRepository(Protocol):
    async def dashboard(self) -> DashboardRead: ...

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
    ) -> list[MaterialRead]: ...

    async def get_existing_elements(self) -> list[str]: ...

    async def get_material(self, material_id: str) -> MaterialRead | None: ...

    async def create_material(self, body: MaterialCreate) -> MaterialRead: ...

    async def list_papers(self, query: str | None, limit: int) -> list[PaperRead]: ...

    async def get_paper(self, paper_id: str) -> PaperRead | None: ...

    async def create_paper(self, body: PaperCreate) -> PaperRead: ...

    async def batch_ingest_papers(
        self, request: BatchIngestRequest | list[BatchIngestItem]
    ) -> BatchIngestResponse: ...


    async def list_observations(self, limit: int) -> list[ObservationListItem]: ...

    async def create_observation(self, body: ObservationCreate) -> ObservationRead: ...

    async def list_properties(self) -> list[PropertyOption]: ...

    async def search(self, query: str, limit: int) -> list[SearchHit]: ...

    async def get_config(self) -> AppConfigRead: ...

    async def update_config(self, body: AppConfigUpdate) -> AppConfigRead: ...

    async def get_material_conflicts(self, material_id: str) -> list[ObservationConflictGroup]: ...

    async def get_literature_stats(self) -> LiteratureStatsResponse: ...

    async def get_knowledge_graph(
        self,
        element: str | None = None,
        material_id: str | None = None,
        include_papers: bool = False,
        subgraph: str | None = None,
        limit: int = 60,
    ) -> KnowledgeGraphResponse: ...
