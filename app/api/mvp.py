from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import get_session
from app.infrastructure.mysql_catalog import MySQLCatalogRepository
from app.models.common import CursorPage
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
    limit: int = Query(default=50, ge=1, le=200),
) -> CursorPage[MaterialRead]:
    items = await repository.list_materials(q, limit)
    return CursorPage(items=items, next_cursor=None, has_more=False)


@router.post("/materials", response_model=MaterialRead, status_code=status.HTTP_201_CREATED, tags=["materials"])
async def create_material(body: MaterialCreate, repository: Repository) -> MaterialRead:
    return await repository.create_material(body)


@router.get("/materials/{material_id}", response_model=MaterialRead, tags=["materials"])
async def get_material(material_id: UUID, repository: Repository) -> MaterialRead:
    material = await repository.get_material(str(material_id))
    if material is None:
        raise HTTPException(status_code=404, detail="材料不存在")
    return material


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
