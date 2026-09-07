from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

from .common import APIModel, EvidenceRole, ValueKind, VerificationStatus


class ObservationCreate(APIModel):
    sample_id: UUID | None = None
    device_id: UUID | None = None
    calculation_id: UUID | None = None

    property_definition_id: UUID
    measurement_id: UUID | None = None
    device_test_id: UUID | None = None
    phase_assignment_id: UUID | None = None

    value_kind: ValueKind = ValueKind.SCALAR
    value_numeric: float | None = None
    value_min: float | None = None
    value_max: float | None = None
    value_text: str | None = None
    value_boolean: bool | None = None

    original_value_text: str | None = None
    original_unit_text: str | None = None
    normalized_value: float | None = None
    normalized_unit_term_id: UUID | None = None
    uncertainty_lower: float | None = None
    uncertainty_upper: float | None = None

    condition_temperature_value: float | None = None
    condition_temperature_unit: str | None = None
    condition_pressure_value: float | None = Field(default=None, ge=0)
    condition_pressure_unit: str | None = None

    quality_score: float | None = Field(default=None, ge=0, le=1)
    verification_status: VerificationStatus = VerificationStatus.AI_EXTRACTED

    @model_validator(mode="after")
    def validate_subject_and_value(self) -> ObservationCreate:
        subjects = [self.sample_id, self.device_id, self.calculation_id]
        if sum(value is not None for value in subjects) != 1:
            raise ValueError("exactly one of sample_id, device_id, calculation_id is required")

        if self.measurement_id is not None and self.sample_id is None:
            raise ValueError("measurement_id requires sample_id")
        if self.device_test_id is not None and self.device_id is None:
            raise ValueError("device_test_id requires device_id")

        if self.value_kind == ValueKind.SCALAR:
            if self.value_numeric is None and self.normalized_value is None:
                raise ValueError("scalar observation requires value_numeric or normalized_value")
        elif self.value_kind == ValueKind.RANGE:
            if self.value_min is None or self.value_max is None:
                raise ValueError("range observation requires value_min and value_max")
            if self.value_min > self.value_max:
                raise ValueError("value_min must not exceed value_max")
        elif self.value_kind in (ValueKind.TEXT, ValueKind.CATEGORICAL):
            if not self.value_text:
                raise ValueError("text/categorical observation requires value_text")
        elif self.value_kind == ValueKind.BOOLEAN:
            if self.value_boolean is None:
                raise ValueError("boolean observation requires value_boolean")
        return self


class ObservationPatch(APIModel):
    phase_assignment_id: UUID | None = None
    value_numeric: float | None = None
    value_min: float | None = None
    value_max: float | None = None
    value_text: str | None = None
    value_boolean: bool | None = None
    original_value_text: str | None = None
    original_unit_text: str | None = None
    normalized_value: float | None = None
    normalized_unit_term_id: UUID | None = None
    uncertainty_lower: float | None = None
    uncertainty_upper: float | None = None
    quality_score: float | None = Field(default=None, ge=0, le=1)
    verification_status: VerificationStatus | None = None


class EvidenceLinkCreate(APIModel):
    evidence_fragment_id: UUID
    evidence_role: EvidenceRole = EvidenceRole.PRIMARY
    confidence: float | None = Field(default=None, ge=0, le=1)


class ObservationRead(ObservationCreate):
    id: UUID
    row_version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    evidence: list[EvidenceLinkCreate] = Field(default_factory=list)
