from uuid import UUID

from fastapi import APIRouter, Header, Query, status

from app.models.common import CursorPage
from app.models.literature import DocumentCreate, DocumentRead, EvidenceRead, PaperCreate, PaperPatch, PaperRead

router = APIRouter(prefix="/v1", tags=["literature"])


def _not_implemented():
    raise NotImplementedError("Contract-only endpoint: connect application service")


@router.post("/papers", response_model=PaperRead, status_code=status.HTTP_201_CREATED)
async def create_paper(body: PaperCreate) -> PaperRead:
    _not_implemented()


@router.get("/papers", response_model=CursorPage[PaperRead])
async def list_papers(
    q: str | None = None,
    publication_year: int | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> CursorPage[PaperRead]:
    _not_implemented()


@router.get("/papers/{paper_id}", response_model=PaperRead)
async def get_paper(paper_id: UUID) -> PaperRead:
    _not_implemented()


@router.patch("/papers/{paper_id}", response_model=PaperRead)
async def patch_paper(
    paper_id: UUID,
    body: PaperPatch,
    if_match: str = Header(alias="If-Match"),
) -> PaperRead:
    _not_implemented()


@router.post("/papers/{paper_id}/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def add_document(paper_id: UUID, body: DocumentCreate) -> DocumentRead:
    _not_implemented()


@router.get("/papers/{paper_id}/documents", response_model=list[DocumentRead])
async def list_documents(paper_id: UUID) -> list[DocumentRead]:
    _not_implemented()


@router.get("/evidence/{evidence_id}", response_model=EvidenceRead)
async def get_evidence(evidence_id: UUID) -> EvidenceRead:
    _not_implemented()
