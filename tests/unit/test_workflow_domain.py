from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.workflow import WorkflowApplicationService
from app.domain.workflow import (
    DomainConflictError,
    DomainValidationError,
    resolve_and_validate_normalization,
    try_same_unit_normalization,
    validate_candidate_review,
    validate_manual_intake_verification_status,
    validate_review_transition,
    validate_sha256_hex,
    validate_storage_uri,
)
from app.models.common import VerificationStatus


def test_validate_storage_uri_allowed_schemes() -> None:
    # 公共录入只允许 s3:// 和 https://
    assert validate_storage_uri("s3://bucket/key.pdf") == "s3://bucket/key.pdf"
    assert validate_storage_uri("https://example.com/paper.pdf") == "https://example.com/paper.pdf"

    # http:// 和公共 demo:// 必须被拒绝
    with pytest.raises(DomainValidationError, match="非法的 storage_uri 协议"):
        validate_storage_uri("http://example.com/paper.pdf")

    with pytest.raises(DomainValidationError, match="非法的 storage_uri 协议"):
        validate_storage_uri("demo://paper/nmat2009")

    with pytest.raises(DomainValidationError, match="非法的 storage_uri 协议"):
        validate_storage_uri("ftp://example.com/paper.pdf")

    with pytest.raises(DomainValidationError, match="非法的 storage_uri 协议"):
        validate_storage_uri("file:///etc/passwd")


def test_validate_sha256_hex() -> None:
    valid_sha = "93a44bbbb96c751ca06b526fe571763aa6113791b97777227b0998b8f1f5d8c3"
    assert validate_sha256_hex(valid_sha) == valid_sha

    # 大写字符拒绝（必须为规范小写）
    with pytest.raises(DomainValidationError, match="sha256 必须为 64 位小写十六进制字符串"):
        validate_sha256_hex(valid_sha.upper())

    # 长度不足
    with pytest.raises(DomainValidationError, match="sha256 必须为 64 位小写十六进制字符串"):
        validate_sha256_hex("123456")


def test_validate_manual_intake_verification_status() -> None:
    # 人工直接登记只能为 HUMAN_REVIEWED
    validate_manual_intake_verification_status(VerificationStatus.HUMAN_REVIEWED)

    # 严禁直接传入 AI 提取状态
    with pytest.raises(DomainValidationError, match="不允许直接录入 AI_EXTRACTED"):
        validate_manual_intake_verification_status(VerificationStatus.AI_EXTRACTED)

    with pytest.raises(DomainValidationError, match="不允许直接录入 AI_VALIDATED"):
        validate_manual_intake_verification_status(VerificationStatus.AI_VALIDATED)

    # 严禁直接设为 VERIFIED
    with pytest.raises(DomainValidationError, match="初始状态必须为 HUMAN_REVIEWED"):
        validate_manual_intake_verification_status(VerificationStatus.VERIFIED)


def test_review_transitions_valid_flow() -> None:
    # 正常完整流转: AI_EXTRACTED -> HUMAN_REVIEWED -> VERIFIED
    validate_review_transition(
        current_status=VerificationStatus.AI_EXTRACTED,
        target_status=VerificationStatus.HUMAN_REVIEWED,
        has_evidence=True,
    )
    validate_review_transition(
        current_status=VerificationStatus.HUMAN_REVIEWED,
        target_status=VerificationStatus.VERIFIED,
        has_evidence=True,
    )

    # 存疑流转: VERIFIED -> DISPUTED -> HUMAN_REVIEWED
    validate_review_transition(
        current_status=VerificationStatus.VERIFIED,
        target_status=VerificationStatus.DISPUTED,
        has_evidence=True,
    )
    validate_review_transition(
        current_status=VerificationStatus.DISPUTED,
        target_status=VerificationStatus.HUMAN_REVIEWED,
        has_evidence=True,
    )

    # 撤回: 任何合法状态 -> RETRACTED
    validate_review_transition(
        current_status=VerificationStatus.HUMAN_REVIEWED,
        target_status=VerificationStatus.RETRACTED,
        has_evidence=True,
    )


def test_cannot_skip_human_reviewed_to_verified() -> None:
    with pytest.raises(DomainConflictError, match="不能跳过 HUMAN_REVIEWED"):
        validate_review_transition(
            current_status=VerificationStatus.AI_EXTRACTED,
            target_status=VerificationStatus.VERIFIED,
            has_evidence=True,
        )


def test_verified_requires_evidence() -> None:
    with pytest.raises(DomainConflictError, match="必须已有可定位的关联证据"):
        validate_review_transition(
            current_status=VerificationStatus.HUMAN_REVIEWED,
            target_status=VerificationStatus.VERIFIED,
            has_evidence=False,
        )


def test_retracted_is_terminal_state() -> None:
    with pytest.raises(DomainConflictError, match="已撤回记录为终态，不可逆"):
        validate_review_transition(
            current_status=VerificationStatus.RETRACTED,
            target_status=VerificationStatus.HUMAN_REVIEWED,
            has_evidence=True,
        )


def test_same_status_transition_rejected() -> None:
    with pytest.raises(DomainConflictError, match="无需重复流转"):
        validate_review_transition(
            current_status=VerificationStatus.VERIFIED,
            target_status=VerificationStatus.VERIFIED,
            has_evidence=True,
        )


def test_normalization_rules() -> None:
    canonical_unit_id = uuid4()
    other_unit_id = uuid4()

    # 1. 未提供归一化值时，两者均返回 None
    val, unit_id = resolve_and_validate_normalization(
        original_value_text="430",
        original_unit_text="K",
        value_numeric=430.0,
        normalized_value=None,
        normalized_unit_term_id=None,
        canonical_unit_term_id=canonical_unit_id,
        canonical_unit_symbol="K",
    )
    assert val is None
    assert unit_id is None

    # 2. 只提供 normalized_value 但缺失 normalized_unit_term_id 拒绝
    with pytest.raises(DomainValidationError, match="必须同时提供 normalized_unit_term_id"):
        resolve_and_validate_normalization(
            original_value_text="430",
            original_unit_text="K",
            value_numeric=430.0,
            normalized_value=430.0,
            normalized_unit_term_id=None,
            canonical_unit_term_id=canonical_unit_id,
            canonical_unit_symbol="K",
        )

    # 3. 只提供 normalized_unit_term_id 但缺失 normalized_value 拒绝
    with pytest.raises(DomainValidationError, match="必须同时提供 normalized_value"):
        resolve_and_validate_normalization(
            original_value_text="430",
            original_unit_text="K",
            value_numeric=430.0,
            normalized_value=None,
            normalized_unit_term_id=canonical_unit_id,
            canonical_unit_term_id=canonical_unit_id,
            canonical_unit_symbol="K",
        )

    # 4. 单位不匹配时拒绝
    with pytest.raises(DomainValidationError, match="与属性规范单位.*不匹配"):
        resolve_and_validate_normalization(
            original_value_text="430",
            original_unit_text="C",
            value_numeric=430.0,
            normalized_value=703.15,
            normalized_unit_term_id=other_unit_id,
            canonical_unit_term_id=canonical_unit_id,
            canonical_unit_symbol="K",
        )

    # 5. 同单位等值归一化成功
    val, unit_id = resolve_and_validate_normalization(
        original_value_text="430",
        original_unit_text="K",
        value_numeric=430.0,
        normalized_value=430.0,
        normalized_unit_term_id=canonical_unit_id,
        canonical_unit_term_id=canonical_unit_id,
        canonical_unit_symbol="K",
    )
    assert val == Decimal("430.0")
    assert unit_id == canonical_unit_id

    # 6. 原单位与规范单位一致，但 normalized_value 发生虚假窜改，拒绝
    with pytest.raises(DomainValidationError, match="必须与原始数值.*一致"):
        resolve_and_validate_normalization(
            original_value_text="430",
            original_unit_text="K",
            value_numeric=430.0,
            normalized_value=500.0,
            normalized_unit_term_id=canonical_unit_id,
            canonical_unit_term_id=canonical_unit_id,
            canonical_unit_symbol="K",
        )


def test_try_same_unit_normalization() -> None:
    canonical_unit_id = uuid4()
    # 严格匹配时返回 Decimal 数值和规范单位 ID
    val, unit = try_same_unit_normalization(
        original_unit_text="K",
        value_numeric=430.5,
        canonical_unit_term_id=canonical_unit_id,
        canonical_unit_symbol="K",
    )
    assert val == Decimal("430.5")
    assert unit == canonical_unit_id

    # 不匹配时返回 (None, None)
    val2, unit2 = try_same_unit_normalization(
        original_unit_text="degC",
        value_numeric=150.0,
        canonical_unit_term_id=canonical_unit_id,
        canonical_unit_symbol="K",
    )
    assert val2 is None
    assert unit2 is None


def test_if_match_strict_etag_parsing() -> None:
    # 严格接受 W/"<row_version>"
    assert WorkflowApplicationService.parse_if_match('W/"1"') == 1
    assert WorkflowApplicationService.parse_if_match('W/"42"') == 42

    # 拒绝缺少 W/ 前缀或引号的非法形式
    with pytest.raises(DomainValidationError, match="必须严格为弱 ETag 格式"):
        WorkflowApplicationService.parse_if_match('"1"')

    with pytest.raises(DomainValidationError, match="必须严格为弱 ETag 格式"):
        WorkflowApplicationService.parse_if_match("1")

    with pytest.raises(DomainValidationError, match="必须严格为弱 ETag 格式"):
        WorkflowApplicationService.parse_if_match("W/1")

    with pytest.raises(DomainValidationError, match="缺少必需的 If-Match"):
        WorkflowApplicationService.parse_if_match(None)


def test_candidate_review_domain_validation() -> None:
    # pending 状态下 accept 且有证据：合法
    validate_candidate_review(current_status="pending", decision="accept", has_evidence=True)
    validate_candidate_review(current_status="pending", decision="promote", has_evidence=True)

    # pending 状态下 accept 但无证据：非法
    with pytest.raises(DomainConflictError, match="必须有关联的证据片段"):
        validate_candidate_review(current_status="pending", decision="accept", has_evidence=False)

    # pending 状态下 reject：合法（无论有无证据）
    validate_candidate_review(current_status="pending", decision="reject", has_evidence=False)

    # 非 pending 状态下（已被处理）：冲突
    with pytest.raises(DomainConflictError, match="已被处理，不可重复审核"):
        validate_candidate_review(current_status="accepted", decision="accept", has_evidence=True)

    with pytest.raises(DomainConflictError, match="已被处理，不可重复审核"):
        validate_candidate_review(current_status="rejected", decision="accept", has_evidence=True)

    # 非法决定字面值
    with pytest.raises(DomainValidationError, match="非法的审核决定"):
        validate_candidate_review(current_status="pending", decision="invalid_action", has_evidence=True)
