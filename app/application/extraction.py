"""PhaseChangeDB AI 提取暂存与人工审核应用服务。"""

from __future__ import annotations

import re
import secrets
from uuid import UUID

from app.core.config import get_settings
from app.domain.workflow import (
    DomainValidationError,
    ServiceUnavailableError,
    UnauthorizedError,
)
from app.infrastructure.extraction import MySQLExtractionRepository
from app.models.extraction import (
    CandidateReviewRequest,
    CandidateReviewResponse,
    ExtractionCandidateCreateRequest,
    ExtractionCandidateCreateResponse,
    ExtractionCandidateRead,
)

IF_MATCH_REGEX = re.compile(r'^W/"(\d+)"$')


class ExtractionApplicationService:
    """编排 AI 提取结果暂存、候选详情查询与人工审核晋升用例。"""

    def __init__(self, repository: MySQLExtractionRepository):
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

    async def stage_candidate(
        self,
        body: ExtractionCandidateCreateRequest,
        idempotency_key: str | None,
        request_path: str,
        request_id: str | None,
    ) -> ExtractionCandidateCreateResponse:
        """AI 提取结果暂存用例（强制要求 Idempotency-Key）。"""
        key = self.validate_idempotency_key(idempotency_key)
        return await self.repository.stage_candidate(
            body=body,
            idempotency_key=key,
            request_path=request_path,
            request_id=request_id,
        )

    async def get_candidate(self, candidate_id: UUID) -> ExtractionCandidateRead:
        """获取提取候选详情。"""
        return await self.repository.get_candidate(candidate_id)

    async def review_candidate(
        self,
        candidate_id: UUID,
        body: CandidateReviewRequest,
        if_match_header: str | None,
        auth_header: str | None,
        request_id: str | None,
    ) -> CandidateReviewResponse:
        """人工审核与晋升提取候选用例（强制要求 Reviewer Token 与 If-Match）。"""
        self.verify_reviewer_token(auth_header)
        expected_version = self.parse_if_match(if_match_header)
        return await self.repository.review_candidate(
            candidate_id=candidate_id,
            expected_version=expected_version,
            review=body,
            request_id=request_id,
        )
