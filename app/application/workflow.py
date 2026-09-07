from __future__ import annotations

import re
import secrets
from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.domain.workflow import (
    DomainValidationError,
    ServiceUnavailableError,
    UnauthorizedError,
)
from app.infrastructure.workflow import MySQLWorkflowRepository
from app.models.workflow import (
    ObservationDetailRead,
    ObservationReviewRequest,
    ObservationReviewResponse,
    WorkflowIntakeRequest,
    WorkflowIntakeResponse,
)

IF_MATCH_REGEX = re.compile(r'^W/"(\d+)"$')


class WorkflowApplicationService:
    """编排录入与审核业务用例、权限校验与版本解析。"""

    def __init__(self, repository: MySQLWorkflowRepository):
        self.repository = repository
        self.settings = get_settings()

    def verify_reviewer_token(self, auth_header: str | None) -> None:
        """校验本地 Reviewer 权限 Token。"""
        configured_token = self.settings.reviewer_token
        if not configured_token:
            raise ServiceUnavailableError("审核功能未配置或 Reviewer Token 未设置，请配置 PCM_REVIEWER_TOKEN")

        if not auth_header or not auth_header.startswith("Bearer "):
            raise UnauthorizedError("审核凭据无效或缺失，必须携带 Authorization: Bearer <TOKEN>")

        token = auth_header.removeprefix("Bearer ").strip()
        if not secrets.compare_digest(token, configured_token):
            raise UnauthorizedError("审核凭据无效，Token 不匹配")

    @staticmethod
    def parse_if_match(if_match_header: str | None) -> int:
        """解析 If-Match: W/\"<row_version>\" 头并提取整型版本号。"""
        if not if_match_header:
            raise DomainValidationError("缺少必需的 If-Match 请求头，格式形如 W/\"1\"")

        match = IF_MATCH_REGEX.match(if_match_header.strip())
        if not match:
            raise DomainValidationError(
                f"非法的 If-Match 格式: '{if_match_header}'，必须严格为弱 ETag 格式形如 W/\"1\""
            )

        return int(match.group(1))

    @staticmethod
    def validate_idempotency_key(key: str | None) -> str:
        """校验 Idempotency-Key 请求头。"""
        if not key or not key.strip():
            raise DomainValidationError("缺少必需的 Idempotency-Key 请求头")
        clean = key.strip()
        if len(clean) > 255:
            raise DomainValidationError("Idempotency-Key 长度不能超过 255 字符")
        return clean

    async def intake(
        self,
        body: WorkflowIntakeRequest,
        idempotency_key: str | None,
        auth_header: str | None,
        request_path: str,
        request_id: str | None,
    ) -> WorkflowIntakeResponse:
        """完整科研记录录入用例（强制要求 Reviewer Token 与 Idempotency-Key）。"""
        self.verify_reviewer_token(auth_header)
        key = self.validate_idempotency_key(idempotency_key)
        return await self.repository.intake(
            body=body,
            idempotency_key=key,
            request_path=request_path,
            request_id=request_id,
        )

    async def get_observation_detail(self, observation_id: UUID) -> ObservationDetailRead:
        """获取观测完整上下文详情（公共只读）。"""
        return await self.repository.get_observation_detail(observation_id)

    async def review_observation(
        self,
        observation_id: UUID,
        body: ObservationReviewRequest,
        if_match_header: str | None,
        auth_header: str | None,
        request_id: str | None,
    ) -> ObservationReviewResponse:
        """人工审核用例（强制要求 Reviewer Token 与 If-Match）。"""
        self.verify_reviewer_token(auth_header)
        expected_version = self.parse_if_match(if_match_header)
        return await self.repository.review_observation(
            observation_id=observation_id,
            expected_version=expected_version,
            review=body,
            request_id=request_id,
        )

    async def list_terms_by_namespace(self, namespace: str) -> list[dict[str, Any]]:
        """获取指定命名空间的本体术语选项。"""
        return await self.repository.list_terms_by_namespace(namespace)
