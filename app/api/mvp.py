from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from app.application.literature_parser import parse_uploaded_paper
from app.infrastructure.database import get_session
from app.infrastructure.mysql_catalog import MySQLCatalogRepository
from app.models.batch_upload import (
    BatchIngestRequest,
    BatchIngestResponse,
    BatchUploadResponse,
    LiteratureAgentConfig,
    ObservationConflictGroup,
    ParsedPaperPreview,
)
from app.models.common import CursorPage
from app.models.config import AppConfigRead, AppConfigUpdate
from app.models.literature import PaperCreate, PaperRead
from app.models.material import MaterialCreate, MaterialRead
from app.models.mvp import DashboardRead, ObservationListItem, PropertyOption
from app.models.observation import ObservationCreate, ObservationRead
from app.models.search import SearchRequest, SearchResponse

router = APIRouter(prefix="/v1")


async def get_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> MySQLCatalogRepository:
    return MySQLCatalogRepository(session)


Repository = Annotated[MySQLCatalogRepository, Depends(get_repository)]


@router.get("/dashboard", response_model=DashboardRead, tags=["dashboard"])
async def dashboard(repository: Repository) -> DashboardRead:
    return await repository.dashboard()


@router.get("/materials", response_model=CursorPage[MaterialRead], tags=["materials"])
async def list_materials(
    repository: Repository,
    q: str | None = None,
    elements: str | None = Query(default=None, description="逗号分隔的元素列表，如 Ge,Sb,Te"),
    limit: int = Query(default=50, ge=1, le=200),
) -> CursorPage[MaterialRead]:
    elem_list = [e.strip() for e in elements.split(",") if e.strip()] if elements else None
    items = await repository.list_materials(q, limit, elements=elem_list)
    return CursorPage(items=items, next_cursor=None, has_more=False)


@router.get("/materials/elements", response_model=list[str], tags=["materials"])
async def list_existing_elements(repository: Repository) -> list[str]:
    return await repository.get_existing_elements()


@router.post("/materials", response_model=MaterialRead, status_code=status.HTTP_201_CREATED, tags=["materials"])
async def create_material(body: MaterialCreate, repository: Repository) -> MaterialRead:
    return await repository.create_material(body)


@router.get("/materials/{material_id}", response_model=MaterialRead, tags=["materials"])
async def get_material(material_id: UUID, repository: Repository) -> MaterialRead:
    material = await repository.get_material(str(material_id))
    if material is None:
        raise HTTPException(status_code=404, detail="材料不存在")
    return material


@router.get("/materials/{material_id}/conflicts", response_model=list[ObservationConflictGroup], tags=["materials"])
async def get_material_conflicts(material_id: UUID, repository: Repository) -> list[ObservationConflictGroup]:
    return await repository.get_material_conflicts(str(material_id))



@router.get("/papers", response_model=CursorPage[PaperRead], tags=["literature"])
async def list_papers(
    repository: Repository,
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> CursorPage[PaperRead]:
    items = await repository.list_papers(q, limit)
    return CursorPage(items=items, next_cursor=None, has_more=False)


@router.post("/papers", response_model=PaperRead, status_code=status.HTTP_201_CREATED, tags=["literature"])
async def create_paper(body: PaperCreate, repository: Repository) -> PaperRead:
    return await repository.create_paper(body)


@router.get("/papers/{paper_id}", response_model=PaperRead, tags=["literature"])
async def get_paper(paper_id: UUID, repository: Repository) -> PaperRead:
    paper = await repository.get_paper(str(paper_id))
    if paper is None:
        raise HTTPException(status_code=404, detail="文献不存在")
    return paper


@router.post("/literature/batch-upload", response_model=BatchUploadResponse, tags=["literature"])
async def batch_upload_papers(
    files: Annotated[list[UploadFile], File(...)],
) -> BatchUploadResponse:

    items: list[ParsedPaperPreview] = []
    parsed_cnt = 0
    failed_cnt = 0

    for file in files:
        try:
            content = await file.read()
            preview = parse_uploaded_paper(file.filename or "unknown_paper", content)
            items.append(preview)
            if preview.status == "parsed":
                parsed_cnt += 1
            else:
                failed_cnt += 1
        except Exception as e:
            failed_cnt += 1
            items.append(
                ParsedPaperPreview(
                    file_id=str(uuid7()),
                    filename=file.filename or "unknown_paper",
                    file_size=0,
                    title=file.filename or "unknown_paper",
                    status="failed",
                    error_message=str(e),
                )
            )

    return BatchUploadResponse(
        total_files=len(files),
        parsed_count=parsed_cnt,
        failed_count=failed_cnt,
        items=items,
    )


@router.post("/literature/batch-ingest", response_model=BatchIngestResponse, tags=["literature"])
async def batch_ingest_papers(
    body: BatchIngestRequest,
    repository: Repository,
) -> BatchIngestResponse:
    return await repository.batch_ingest_papers(body)



@router.get("/observations", response_model=CursorPage[ObservationListItem], tags=["observations"])
async def list_observations(
    repository: Repository,
    limit: int = Query(default=50, ge=1, le=200),
) -> CursorPage[ObservationListItem]:
    items = await repository.list_observations(limit)
    return CursorPage(items=items, next_cursor=None, has_more=False)


@router.post(
    "/observations", response_model=ObservationRead, status_code=status.HTTP_201_CREATED, tags=["observations"]
)
async def create_observation(body: ObservationCreate, repository: Repository) -> ObservationRead:
    return await repository.create_observation(body)


@router.get("/properties", response_model=list[PropertyOption], tags=["ontology"])
async def list_properties(repository: Repository) -> list[PropertyOption]:
    return await repository.list_properties()


@router.post("/search", response_model=SearchResponse, tags=["search"])
async def search(body: SearchRequest, repository: Repository) -> SearchResponse:
    hits = await repository.search(body.query, body.limit)
    return SearchResponse(hits=hits, next_cursor=None, has_more=False)


@router.get("/config", response_model=AppConfigRead, tags=["config"])
async def get_config(repository: Repository) -> AppConfigRead:
    return await repository.get_config()


@router.put("/config", response_model=AppConfigRead, tags=["config"])
async def update_config(body: AppConfigUpdate, repository: Repository) -> AppConfigRead:
    return await repository.update_config(body)


@router.get("/agents/literature-parser/config", response_model=LiteratureAgentConfig, tags=["agent"])
async def get_literature_agent_config() -> LiteratureAgentConfig:
    return LiteratureAgentConfig()

