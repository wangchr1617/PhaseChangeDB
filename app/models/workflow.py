from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.domain.workflow import validate_storage_uri
from app.models.common import APIModel, ValueKind, VerificationStatus
from app.models.literature import PaperCreate
from app.models.material import MaterialCreate


class DocumentIntake(APIModel):
    storage_uri: str = Field(min_length=5, max_length=1024)
    sha256: str = Field(min_length=64, max_length=64)
    document_type: str = Field(default="main_article", max_length=32)

    @field_validator("storage_uri")
    @classmethod
    def check_storage_uri(cls, v: str) -> str:
        try:
            return validate_storage_uri(v)
        except Exception as e:
            raise ValueError(str(e)) from e


class SampleIntake(APIModel):
    sample_label: str = Field(min_length=1, max_length=255)
    sample_type_term_id: UUID
    thickness_value: float | None = Field(default=None, ge=0)
    thickness_unit: str | None = Field(default=None, max_length=32)
    substrate_material: str | None = Field(default=None, max_length=255)
    description: str | None = None


class EvidenceIntake(APIModel):
    page_number: int = Field(ge=1)
    section: str | None = Field(default=None, max_length=512)
    figure_number: str | None = Field(default=None, max_length=64)
    table_number: str | None = Field(default=None, max_length=64)
    text_snippet: str = Field(min_length=1)
    fragment_type: str = Field(default="paragraph", max_length=32)


class MeasurementIntake(APIModel):
    measurement_type_term_id: UUID
    instrument: str | None = Field(default=None, max_length=255)
    temperature_value: float | None = None
    temperature_unit: str | None = Field(default=None, max_length=32)
    heating_rate_value: float | None = None
    heating_rate_unit: str | None = Field(default=None, max_length=32)


class ObservationIntake(APIModel):
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
    verification_status: VerificationStatus = VerificationStatus.HUMAN_REVIEWED

    @field_validator("verification_status")
    @classmethod
    def validate_intake_status(cls, v: VerificationStatus) -> VerificationStatus:
        if v in (VerificationStatus.AI_EXTRACTED, VerificationStatus.AI_VALIDATED):
            raise ValueError(
                f"人工登记接口不允许直接录入 {v.value} 状态。"
                "AI 提取结果必须先进入暂存区 (/v1/extractions/candidates) 经审核后晋升"
            )
        if v != VerificationStatus.HUMAN_REVIEWED:
            raise ValueError("人工登记接口初始状态必须为 HUMAN_REVIEWED")
        return v

    @model_validator(mode="after")
    def validate_normalization_fields(self) -> ObservationIntake:
        if self.normalized_value is not None and self.normalized_unit_term_id is None:
            raise ValueError("提供 normalized_value 时必须同时提供 normalized_unit_term_id")
        if self.normalized_unit_term_id is not None and self.normalized_value is None:
            raise ValueError("提供 normalized_unit_term_id 时必须同时提供 normalized_value")
        return self

    @model_validator(mode="after")
    def validate_value(self) -> ObservationIntake:
        if self.value_kind == ValueKind.SCALAR:
            if self.value_numeric is None and self.normalized_value is None:
                raise ValueError("标量观测必须提供 value_numeric 或 normalized_value")
        elif self.value_kind == ValueKind.RANGE:
            if self.value_min is None or self.value_max is None:
                raise ValueError("范围观测必须提供 value_min 与 value_max")
            if self.value_min > self.value_max:
                raise ValueError("value_min 不能大于 value_max")
        elif self.value_kind in (ValueKind.TEXT, ValueKind.CATEGORICAL):
            if not self.value_text:
                raise ValueError("文本/分类型观测必须提供 value_text")
        elif self.value_kind == ValueKind.BOOLEAN:
            if self.value_boolean is None:
                raise ValueError("布尔型观测必须提供 value_boolean")
        return self


class WorkflowIntakeRequest(APIModel):
    # 文献：严格二选一（paper_id 与 paper 必须且只能提供其中之一）
    paper_id: UUID | None = None
    paper: PaperCreate | None = None

    # 文档元数据
    document: DocumentIntake

    # 材料：严格二选一（material_id 与 material 必须且只能提供其中之一）
    material_id: UUID | None = None
    material: MaterialCreate | None = None

    # 实体样品
    sample: SampleIntake

    # 证据片段
    evidence: EvidenceIntake

    # 实验测量
    measurement: MeasurementIntake

    # 科学观测
    observation: ObservationIntake

    @model_validator(mode="after")
    def validate_entities(self) -> WorkflowIntakeRequest:
        if (self.paper_id is None and self.paper is None) or (
            self.paper_id is not None and self.paper is not None
        ):
            raise ValueError("paper_id 与 paper 必须二选一（不能同时提供或同时为空）")
        if (self.material_id is None and self.material is None) or (
            self.material_id is not None and self.material is not None
        ):
            raise ValueError("material_id 与 material 必须二选一（不能同时提供或同时为空）")
        return self


class WorkflowIntakeResponse(APIModel):
    observation_id: UUID
    paper_id: UUID
    document_id: UUID
    artifact_id: UUID
    material_id: UUID
    sample_id: UUID
    measurement_id: UUID
    evidence_id: UUID
    verification_status: VerificationStatus
    row_version: int
    created_at: datetime


class ObservationDetailRead(APIModel):
    id: UUID
    verification_status: VerificationStatus
    row_version: int
    created_at: datetime
    updated_at: datetime

    value_kind: str
    value_numeric: float | None = None
    value_min: float | None = None
    value_max: float | None = None
    value_text: str | None = None
    value_boolean: bool | None = None
    original_value_text: str | None = None
    original_unit_text: str | None = None
    normalized_value: float | None = None
    normalized_unit: str | None = None

    uncertainty_lower: float | None = None
    uncertainty_upper: float | None = None
    condition_temperature_value: float | None = None
    condition_temperature_unit: str | None = None
    quality_score: float | None = None

    property: dict
    material: dict
    sample: dict
    measurement: dict | None = None
    evidence: list[dict] = Field(default_factory=list)


class ObservationReviewRequest(APIModel):
    decision: VerificationStatus
    comment: str | None = Field(default=None, max_length=2000)
    reviewer: str = Field(min_length=1, max_length=255)


class ObservationReviewResponse(APIModel):
    observation_id: UUID
    previous_status: VerificationStatus
    new_status: VerificationStatus
    row_version: int
    reviewer: str
    decision: VerificationStatus
    comment: str | None = None
    reviewed_at: datetime
