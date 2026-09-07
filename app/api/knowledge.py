from uuid import UUID

from fastapi import APIRouter, Header, Query, status

from app.models.claim import ClaimCreate, ClaimPatch, ClaimRead, KnowledgeGapRead
from app.models.common import CursorPage

router = APIRouter(prefix="/v1", tags=["knowledge"])


def _not_implemented():
    raise NotImplementedError("Contract-only endpoint: connect application service")


@router.post("/claims", response_model=ClaimRead, status_code=status.HTTP_201_CREATED)
async def create_claim(body: ClaimCreate) -> ClaimRead:
    _not_implemented()


@router.get("/claims", response_model=CursorPage[ClaimRead])
async def list_claims(
    material_id: UUID | None = None,
    property_code: str | None = None,
    verification_status: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> CursorPage[ClaimRead]:
    _not_implemented()


@router.patch("/claims/{claim_id}", response_model=ClaimRead)
async def patch_claim(
    claim_id: UUID,
    body: ClaimPatch,
    if_match: str = Header(alias="If-Match"),
) -> ClaimRead:
    _not_implemented()


@router.get("/knowledge-gaps", response_model=CursorPage[KnowledgeGapRead])
async def list_knowledge_gaps(
    material_id: UUID | None = None,
    property_code: str | None = None,
    gap_type: str | None = None,
    min_score: float | None = Query(default=None, ge=0, le=1),
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> CursorPage[KnowledgeGapRead]:
    _not_implemented()
