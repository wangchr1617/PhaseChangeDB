from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.common import ValueKind, VerificationStatus
from app.models.extraction import (
    CandidateObservationData,
    ExtractionCandidateCreateRequest,
)
from app.models.literature import PaperCreate
from app.models.material import MaterialCreate
from app.models.workflow import (
    DocumentIntake,
    EvidenceIntake,
    MeasurementIntake,
    ObservationIntake,
    SampleIntake,
    WorkflowIntakeRequest,
)


def _valid_doc() -> DocumentIntake:
    return DocumentIntake(
        storage_uri="s3://phasechangedb/articles/test.pdf",
        sha256="a" * 64,
        document_type="main_article",
    )


def _valid_sample() -> SampleIntake:
    return SampleIntake(
        sample_label="S-001",
        sample_type_term_id=uuid4(),
    )


def _valid_evidence() -> EvidenceIntake:
    return EvidenceIntake(
        page_number=1,
        text_snippet="Ge2Sb2Te5 thin film phase change observed at 430 K.",
    )


def _valid_measurement() -> MeasurementIntake:
    return MeasurementIntake(
        measurement_type_term_id=uuid4(),
    )


def _valid_obs() -> ObservationIntake:
    return ObservationIntake(
        property_definition_id=uuid4(),
        value_kind=ValueKind.SCALAR,
        value_numeric=Decimal("430.0"),
        original_value_text="430",
        original_unit_text="K",
        verification_status=VerificationStatus.HUMAN_REVIEWED,
    )


def test_paper_xor_validation() -> None:
    # 1. paper_id 与 paper 同时缺失 -> 422 校验失败
    with pytest.raises(ValidationError, match="paper_id 与 paper 必须二选一"):
        WorkflowIntakeRequest(
            paper_id=None,
            paper=None,
            document=_valid_doc(),
            material_id=uuid4(),
            material=None,
            sample=_valid_sample(),
            evidence=_valid_evidence(),
            measurement=_valid_measurement(),
            observation=_valid_obs(),
        )

    # 2. paper_id 与 paper 同时提供 -> 422 校验失败
    with pytest.raises(ValidationError, match="paper_id 与 paper 必须二选一"):
        WorkflowIntakeRequest(
            paper_id=uuid4(),
            paper=PaperCreate(title="Test Paper"),
            document=_valid_doc(),
            material_id=uuid4(),
            material=None,
            sample=_valid_sample(),
            evidence=_valid_evidence(),
            measurement=_valid_measurement(),
            observation=_valid_obs(),
        )

    # 3. 仅提供 paper_id -> 成功
    req1 = WorkflowIntakeRequest(
        paper_id=uuid4(),
        paper=None,
        document=_valid_doc(),
        material_id=uuid4(),
        material=None,
        sample=_valid_sample(),
        evidence=_valid_evidence(),
        measurement=_valid_measurement(),
        observation=_valid_obs(),
    )
    assert req1.paper_id is not None
    assert req1.paper is None

    # 4. 仅提供 paper -> 成功
    req2 = WorkflowIntakeRequest(
        paper_id=None,
        paper=PaperCreate(title="Test Paper"),
        document=_valid_doc(),
        material_id=uuid4(),
        material=None,
        sample=_valid_sample(),
        evidence=_valid_evidence(),
        measurement=_valid_measurement(),
        observation=_valid_obs(),
    )
    assert req2.paper is not None
    assert req2.paper_id is None


def test_material_xor_validation() -> None:
    # 1. material_id 与 material 同时缺失 -> 422 校验失败
    with pytest.raises(ValidationError, match="material_id 与 material 必须二选一"):
        WorkflowIntakeRequest(
            paper_id=uuid4(),
            paper=None,
            document=_valid_doc(),
            material_id=None,
            material=None,
            sample=_valid_sample(),
            evidence=_valid_evidence(),
            measurement=_valid_measurement(),
            observation=_valid_obs(),
        )

    # 2. material_id 与 material 同时提供 -> 422 校验失败
    with pytest.raises(ValidationError, match="material_id 与 material 必须二选一"):
        WorkflowIntakeRequest(
            paper_id=uuid4(),
            paper=None,
            document=_valid_doc(),
            material_id=uuid4(),
            material=MaterialCreate(canonical_formula="Ge2Sb2Te5", chemical_system="Ge-Sb-Te"),
            sample=_valid_sample(),
            evidence=_valid_evidence(),
            measurement=_valid_measurement(),
            observation=_valid_obs(),
        )


def test_manual_intake_rejects_ai_status() -> None:
    # 人工登记接口禁止传入 AI_EXTRACTED
    with pytest.raises(ValidationError, match="人工登记接口不允许直接录入 AI_EXTRACTED"):
        ObservationIntake(
            property_definition_id=uuid4(),
            value_kind=ValueKind.SCALAR,
            value_numeric=Decimal("430.0"),
            original_value_text="430",
            original_unit_text="K",
            verification_status=VerificationStatus.AI_EXTRACTED,
        )

    # 人工登记接口禁止传入 AI_VALIDATED
    with pytest.raises(ValidationError, match="人工登记接口不允许直接录入 AI_VALIDATED"):
        ObservationIntake(
            property_definition_id=uuid4(),
            value_kind=ValueKind.SCALAR,
            value_numeric=Decimal("430.0"),
            original_value_text="430",
            original_unit_text="K",
            verification_status=VerificationStatus.AI_VALIDATED,
        )


def test_document_rejects_http_and_demo_uri() -> None:
    # 公共 DocumentIntake 严禁使用 http:// 与 demo://
    with pytest.raises(ValidationError, match="非法的 storage_uri 协议"):
        DocumentIntake(
            storage_uri="http://example.com/paper.pdf",
            sha256="b" * 64,
        )

    with pytest.raises(ValidationError, match="非法的 storage_uri 协议"):
        DocumentIntake(
            storage_uri="demo://articles/paper.pdf",
            sha256="b" * 64,
        )

    # s3:// 与 https:// 合法
    doc_s3 = DocumentIntake(storage_uri="s3://bucket/paper.pdf", sha256="b" * 64)
    assert doc_s3.storage_uri.startswith("s3://")

    doc_https = DocumentIntake(storage_uri="https://domain.org/paper.pdf", sha256="b" * 64)
    assert doc_https.storage_uri.startswith("https://")


def test_extraction_candidate_request_model() -> None:
    cand_data = CandidateObservationData(
        material_id=uuid4(),
        sample=_valid_sample(),
        measurement=_valid_measurement(),
        evidence=_valid_evidence(),
        property_definition_id=uuid4(),
        value_numeric=Decimal("150.5"),
        original_value_text="150.5",
        original_unit_text="C",
    )

    # 正常候选请求
    req = ExtractionCandidateCreateRequest(
        model_name="PcmLlmExtractor",
        model_version="v1.2",
        prompt_version="pcm-ner-v2",
        paper_id=uuid4(),
        document=_valid_doc(),
        candidate_data=cand_data,
        confidence=0.92,
    )
    assert req.model_name == "PcmLlmExtractor"
    assert req.confidence == 0.92
    assert req.candidate_type == "observation"

    # candidate_data material XOR 校验
    with pytest.raises(ValidationError, match="material_id 与 material 必须二选一"):
        CandidateObservationData(
            material_id=None,
            material=None,
            sample=_valid_sample(),
            measurement=_valid_measurement(),
            evidence=_valid_evidence(),
            property_definition_id=uuid4(),
            value_numeric=Decimal("150.5"),
            original_value_text="150.5",
            original_unit_text="C",
        )
