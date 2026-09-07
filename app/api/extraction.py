from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.extraction import ExtractionApplicationService
from app.infrastructure.database import get_session
from app.infrastructure.extraction import MySQLExtractionRepository
from app.models.common import CursorPage
from app.models.extraction import (
    CandidateReviewRequest,
    CandidateReviewResponse,
    ExtractionCandidateCreateRequest,
    ExtractionCandidateCreateResponse,
    ExtractionCandidateRead,
    ExtractionRunRead,
    ExtractionStart,
)

router = APIRouter(prefix="/v1", tags=["extraction"])


def _not_implemented():
    raise NotImplementedError("Contract-only endpoint: connect application service")


async def get_extraction_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExtractionApplicationService:
    repository = MySQLExtractionRepository(session)
    return ExtractionApplicationService(repository)


ExtractionService = Annotated[ExtractionApplicationService, Depends(get_extraction_service)]


@router.post(
    "/extractions/candidates",
    response_model=ExtractionCandidateCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="暂存 AI 提取候选数据（只写入 ext_* 暂存区，严禁直写正式 Observation）",
)
async def stage_candidate(
    request: Request,
    body: ExtractionCandidateCreateRequest,
    service: ExtractionService,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ExtractionCandidateCreateResponse:
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
    return await service.stage_candidate(
        body=body,
        idempotency_key=idempotency_key,
        request_path=request.url.path,
        request_id=request_id,
    )


@router.get(
    "/extraction-candidates/{candidate_id}",
    response_model=ExtractionCandidateRead,
    summary="获取指定 AI 提取候选详情与原始载荷",
)
async def get_candidate(
    candidate_id: UUID,
    service: ExtractionService,
) -> ExtractionCandidateRead:
    return await service.get_candidate(candidate_id)


@router.post(
    "/extraction-candidates/{candidate_id}/review",
    response_model=CandidateReviewResponse,
    summary="人工审核并晋升提取候选（ACCEPT晋升为 HUMAN_REVIEWED / REJECT拒绝）",
)
async def review_candidate(
    request: Request,
    candidate_id: UUID,
    body: CandidateReviewRequest,
    service: ExtractionService,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> CandidateReviewResponse:
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
    return await service.review_candidate(
        candidate_id=candidate_id,
        body=body,
        if_match_header=if_match,
        auth_header=authorization,
        request_id=request_id,
    )


@router.post(
    "/documents/{document_id}/extractions",
    response_model=ExtractionRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_extraction(document_id: UUID, body: ExtractionStart) -> ExtractionRunRead:
    _not_implemented()


@router.get("/extractions/{run_id}", response_model=ExtractionRunRead)
async def get_extraction(run_id: UUID) -> ExtractionRunRead:
    _not_implemented()


@router.get("/extractions/{run_id}/candidates", response_model=CursorPage[ExtractionCandidateRead])
async def list_candidates(
    run_id: UUID,
    status_filter: str | None = Query(default=None, alias="status"),
    cursor: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> CursorPage[ExtractionCandidateRead]:
    _not_implemented()
