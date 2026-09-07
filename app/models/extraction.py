from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from .common import APIModel, CandidateStatus, ValueKind
from .literature import PaperCreate
from .material import MaterialCreate
from .workflow import DocumentIntake, EvidenceIntake, MeasurementIntake, SampleIntake


class ExtractionStart(APIModel):
    model_name: str
    model_version: str | None = None
    prompt_version: str | None = None
    ontology_version: str = "0.1"


class ExtractionRunRead(APIModel):
    id: UUID
    document_id: UUID
    model_name: str
    model_version: str | None = None
    prompt_version: str | None = None
    ontology_version: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None


class CandidateObservationData(APIModel):
    # 材料与样品上下文（material_id 与 material 二选一）
    material_id: UUID | None = None
    material: MaterialCreate | None = None
    sample: SampleIntake
    measurement: MeasurementIntake

    # 证据定位与文本
    evidence: EvidenceIntake

    # 观测数据（原始值绝对保留）
    property_definition_id: UUID
    value_kind: ValueKind = ValueKind.SCALAR
    value_numeric: Decimal | float | None = None
    value_min: Decimal | float | None = None
    value_max: Decimal | float | None = None
    value_text: str | None = None
    value_boolean: bool | None = None

    original_value_text: str = Field(min_length=1, max_length=255)
    original_unit_text: str = Field(min_length=1, max_length=64)
    normalized_value: Decimal | float | None = None
    normalized_unit_term_id: UUID | None = None

    uncertainty_lower: Decimal | float | None = None
    uncertainty_upper: Decimal | float | None = None
    condition_temperature_value: Decimal | float | None = None
    condition_temperature_unit: str | None = Field(default=None, max_length=32)
    quality_score: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_candidate_fields(self) -> CandidateObservationData:
        if (self.material_id is None and self.material is None) or (
            self.material_id is not None and self.material is not None
        ):
            raise ValueError("material_id 与 material 必须二选一（不能同时提供或同时为空）")
        if self.normalized_value is not None and self.normalized_unit_term_id is None:
            raise ValueError("提供 normalized_value 时必须同时提供 normalized_unit_term_id")
        if self.normalized_unit_term_id is not None and self.normalized_value is None:
            raise ValueError("提供 normalized_unit_term_id 时必须同时提供 normalized_value")
        return self


class ExtractionCandidateCreateRequest(APIModel):
    # 提取运行元数据
    model_name: str = Field(min_length=1, max_length=255)
    model_version: str | None = Field(default=None, max_length=128)
    prompt_version: str | None = Field(default=None, max_length=64)
    ontology_version: str = Field(default="0.1", max_length=32)

    # 文献与文档引用（paper_id 与 paper 二选一）
    paper_id: UUID | None = None
    paper: PaperCreate | None = None
    document: DocumentIntake

    # 候选类型与置信度
    candidate_type: str = Field(default="observation", max_length=64)
    confidence: float | None = Field(default=None, ge=0, le=1)

    # 结构化候选载荷
    candidate_data: CandidateObservationData

    @model_validator(mode="after")
    def validate_paper(self) -> ExtractionCandidateCreateRequest:
        if (self.paper_id is None and self.paper is None) or (
            self.paper_id is not None and self.paper is not None
        ):
            raise ValueError("paper_id 与 paper 必须二选一（不能同时提供或同时为空）")
        return self


class ExtractionCandidateCreateResponse(APIModel):
    candidate_id: UUID
    extraction_run_id: UUID
    candidate_type: str
    status: str
    row_version: int
    created_at: datetime


class ExtractionCandidateRead(APIModel):
    id: UUID
    extraction_run_id: UUID
    candidate_type: str
    candidate_payload: dict[str, Any]
    confidence: float | None = None
    evidence_fragment_id: UUID | None = None
    status: CandidateStatus | str
    promoted_entity_type: str | None = None
    promoted_entity_id: UUID | None = None
    row_version: int = 1
    created_at: datetime


class CandidateReviewRequest(APIModel):
    decision: Literal["accept", "reject"]
    reviewer: str = Field(min_length=1, max_length=255)
    comment: str | None = Field(default=None, max_length=2000)
    corrected_payload: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_decision_payload(self) -> CandidateReviewRequest:
        if self.decision == "reject" and self.corrected_payload is not None:
            raise ValueError("reject 决策不允许携带 corrected_payload")
        return self


# 兼容既有命名
CandidateReview = CandidateReviewRequest


class CandidateReviewResponse(APIModel):
    candidate_id: UUID
    extraction_run_id: UUID
    status: str
    decision: str
    reviewer: str
    row_version: int
    promoted_observation_id: UUID | None = None
    reviewed_at: datetime
