from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.workflow import WorkflowApplicationService
from app.infrastructure.database import get_session
from app.infrastructure.workflow import MySQLWorkflowRepository
from app.models.workflow import (
    ObservationDetailRead,
    ObservationReviewRequest,
    ObservationReviewResponse,
    WorkflowIntakeRequest,
    WorkflowIntakeResponse,
)

router = APIRouter(prefix="/v1/workflow", tags=["workflow"])


async def get_workflow_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorkflowApplicationService:
    repository = MySQLWorkflowRepository(session)
    return WorkflowApplicationService(repository)


WorkflowService = Annotated[WorkflowApplicationService, Depends(get_workflow_service)]


@router.post(
    "/intake",
    response_model=WorkflowIntakeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="完整科研记录录入（论文、制品、材料、样品、测量、证据与观测）",
)
async def intake(
    request: Request,
    body: WorkflowIntakeRequest,
    service: WorkflowService,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> WorkflowIntakeResponse:
    request_id = request.headers.get("X-Request-ID")
    return await service.intake(
        body=body,
        idempotency_key=idempotency_key,
        auth_header=authorization,
        request_path=request.url.path,
        request_id=request_id,
    )


@router.get(
    "/observations/{observation_id}",
    response_model=ObservationDetailRead,
    summary="获取观测详情与完整证据溯源上下文",
)
async def get_observation_detail(
    observation_id: UUID,
    service: WorkflowService,
) -> ObservationDetailRead:
    return await service.get_observation_detail(observation_id)


@router.post(
    "/observations/{observation_id}/review",
    response_model=ObservationReviewResponse,
    summary="人工审核观测（AI_EXTRACTED → HUMAN_REVIEWED → VERIFIED / DISPUTED / RETRACTED）",
)
async def review_observation(
    request: Request,
    observation_id: UUID,
    body: ObservationReviewRequest,
    service: WorkflowService,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> ObservationReviewResponse:
    request_id = request.headers.get("X-Request-ID")
    return await service.review_observation(
        observation_id=observation_id,
        body=body,
        if_match_header=if_match,
        auth_header=authorization,
        request_id=request_id,
    )


@router.get(
    "/terms",
    response_model=list[dict[str, Any]],
    summary="按命名空间获取本体术语选项（如 sample_type, measurement_type）",
)
async def list_terms(
    service: WorkflowService,
    namespace: str = Query(..., description="本体术语命名空间"),
) -> list[dict[str, Any]]:
    return await service.list_terms_by_namespace(namespace)
