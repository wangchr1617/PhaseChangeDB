from __future__ import annotations

import re
from urllib.parse import urlparse

from app.domain.exceptions import (
    DomainConflictError,
    DomainValidationError,
    EntityNotFoundError,
    PreconditionFailedError,
    ServiceUnavailableError,
    UnauthorizedError,
    WorkflowDomainError,
)
from app.domain.normalization import (
    resolve_and_validate_normalization,
    try_same_unit_normalization,
)
from app.models.common import VerificationStatus

ALLOWED_PUBLIC_STORAGE_SCHEMES = {"s3", "https"}
ALLOWED_STORAGE_SCHEMES = ALLOWED_PUBLIC_STORAGE_SCHEMES  # 保持既有常量兼容
SHA256_REGEX = re.compile(r"^[0-9a-f]{64}$")

# 允许的状态流转矩阵
ALLOWED_TRANSITIONS: dict[VerificationStatus, set[VerificationStatus]] = {
    VerificationStatus.AI_EXTRACTED: {
        VerificationStatus.HUMAN_REVIEWED,
        VerificationStatus.DISPUTED,
        VerificationStatus.RETRACTED,
    },
    VerificationStatus.AI_VALIDATED: {
        VerificationStatus.HUMAN_REVIEWED,
        VerificationStatus.DISPUTED,
        VerificationStatus.RETRACTED,
    },
    VerificationStatus.HUMAN_REVIEWED: {
        VerificationStatus.VERIFIED,
        VerificationStatus.DISPUTED,
        VerificationStatus.RETRACTED,
    },
    VerificationStatus.VERIFIED: {
        VerificationStatus.DISPUTED,
        VerificationStatus.RETRACTED,
    },
    VerificationStatus.DISPUTED: {
        VerificationStatus.HUMAN_REVIEWED,
        VerificationStatus.RETRACTED,
    },
    VerificationStatus.RETRACTED: set(),  # 已撤回记录为终态，不可逆
}


def validate_storage_uri(uri: str, allowed_schemes: set[str] | None = None) -> str:
    """验证文档制品存储 URI 协议。公共接口只允许 s3:// 与 https://。"""
    schemes = allowed_schemes or ALLOWED_PUBLIC_STORAGE_SCHEMES
    parsed = urlparse(uri)
    if not parsed.scheme or parsed.scheme.lower() not in schemes:
        raise DomainValidationError(
            f"非法的 storage_uri 协议: '{parsed.scheme}'。公共录入只允许: {', '.join(sorted(schemes))}"
        )
    return uri


def validate_sha256_hex(sha256: str) -> str:
    """验证 SHA-256 为 64 位小写十六进制。"""
    if not SHA256_REGEX.match(sha256):
        raise DomainValidationError("sha256 必须为 64 位小写十六进制字符串")
    return sha256


def validate_manual_intake_verification_status(status: VerificationStatus) -> None:
    """人工直接登记时初始状态只能为 HUMAN_REVIEWED，禁止客户端直接录入 AI 提取状态或直接设为 VERIFIED。"""
    if status in (VerificationStatus.AI_EXTRACTED, VerificationStatus.AI_VALIDATED):
        raise DomainValidationError(
            f"人工登记接口不允许直接录入 {status.value} 状态。"
            "AI 提取结果必须先进入暂存区 (/v1/extractions/candidates) 经审核后晋升"
        )
    if status != VerificationStatus.HUMAN_REVIEWED:
        raise DomainValidationError(
            f"人工登记接口初始状态必须为 HUMAN_REVIEWED，禁止直接设为 {status.value}"
        )


def validate_initial_verification_status(status: VerificationStatus) -> None:
    """兼容旧校验函数，仅在显式支持未审核初始状态时使用。"""
    if status == VerificationStatus.VERIFIED:
        raise DomainValidationError("观测创建时禁止直接设为 VERIFIED 状态，必须经由人工审核流转")
    if status not in {VerificationStatus.AI_EXTRACTED, VerificationStatus.AI_VALIDATED}:
        raise DomainValidationError(f"初始状态只能为 AI_EXTRACTED 或 AI_VALIDATED，不可为 {status}")


def validate_review_transition(
    current_status: VerificationStatus,
    target_status: VerificationStatus,
    has_evidence: bool,
) -> None:
    """验证人工审核状态流转的合法性。"""
    if current_status == VerificationStatus.RETRACTED:
        raise DomainConflictError("已撤回记录为终态，不可逆，禁止恢复为其他状态")

    if current_status == target_status:
        raise DomainConflictError(f"观测已处于 {target_status} 状态，无需重复流转")

    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        if current_status == VerificationStatus.AI_EXTRACTED and target_status == VerificationStatus.VERIFIED:
            raise DomainConflictError("不能跳过 HUMAN_REVIEWED 直接将 AI_EXTRACTED 晋升为 VERIFIED")
        raise DomainConflictError(f"非法的状态流转: 从 {current_status} 到 {target_status}")

    if target_status == VerificationStatus.VERIFIED and not has_evidence:
        raise DomainConflictError("晋升为 VERIFIED 必须已有可定位的关联证据（Evidence）")


def validate_candidate_review(
    current_status: str,
    decision: str,
    has_evidence: bool,
) -> None:
    """验证提取候选审核决定的合法性。"""
    decision_lower = decision.lower()
    if decision_lower not in {"accept", "promote", "reject", "modify"}:
        raise DomainValidationError(f"非法的审核决定: '{decision}'，只允许: accept, promote, reject, modify")

    if current_status != "pending":
        raise DomainConflictError(f"候选记录当前状态为 '{current_status}'，已被处理，不可重复审核")

    if decision_lower in {"accept", "promote"} and not has_evidence:
        raise DomainConflictError("晋升为正式 Observation 必须有关联的证据片段（Evidence）")


__all__ = [
    "ALLOWED_PUBLIC_STORAGE_SCHEMES",
    "ALLOWED_STORAGE_SCHEMES",
    "ALLOWED_TRANSITIONS",
    "DomainConflictError",
    "DomainValidationError",
    "EntityNotFoundError",
    "PreconditionFailedError",
    "ServiceUnavailableError",
    "UnauthorizedError",
    "WorkflowDomainError",
    "resolve_and_validate_normalization",
    "try_same_unit_normalization",
    "validate_candidate_review",
    "validate_initial_verification_status",
    "validate_manual_intake_verification_status",
    "validate_review_transition",
    "validate_sha256_hex",
    "validate_storage_uri",
]
