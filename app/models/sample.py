from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from .common import APIModel, RecordMeta


class SampleCreate(APIModel):
    nominal_material_id: UUID
    source_paper_id: UUID | None = None
    sample_label: str | None = Field(default=None, max_length=255)
    sample_type_term_id: UUID
    thickness_value: float | None = Field(default=None, ge=0)
    thickness_unit: str | None = Field(default=None, max_length=32)
    substrate_material: str | None = Field(default=None, max_length=255)
    geometry: dict | None = None
    description: str | None = None


class SamplePatch(APIModel):
    sample_label: str | None = Field(default=None, max_length=255)
    sample_type_term_id: UUID | None = None
    thickness_value: float | None = Field(default=None, ge=0)
    thickness_unit: str | None = Field(default=None, max_length=32)
    substrate_material: str | None = Field(default=None, max_length=255)
    geometry: dict | None = None
    description: str | None = None


class SampleRead(RecordMeta):
    nominal_material_id: UUID
    source_paper_id: UUID | None = None
    sample_label: str | None = None
    sample_type_term_id: UUID
    thickness_value: float | None = None
    thickness_unit: str | None = None
    substrate_material: str | None = None
    geometry: dict | None = None
    description: str | None = None


class ProcessStepCreate(APIModel):
    sequence_number: int = Field(ge=1, le=65535)
    process_type_term_id: UUID
    temperature_value: float | None = None
    temperature_unit: str | None = None
    duration_value: float | None = Field(default=None, ge=0)
    duration_unit: str | None = None
    pressure_value: float | None = Field(default=None, ge=0)
    pressure_unit: str | None = None
    atmosphere: str | None = None
    heating_rate_value: float | None = None
    heating_rate_unit: str | None = None
    cooling_rate_value: float | None = None
    cooling_rate_unit: str | None = None
    parameters: dict | None = None
    evidence_id: UUID | None = None


class ProcessRunCreate(APIModel):
    sample_id: UUID
    process_name: str | None = None
    start_state: str | None = None
    end_state: str | None = None
    source_paper_id: UUID | None = None
    evidence_id: UUID | None = None
    steps: list[ProcessStepCreate] = Field(default_factory=list)


class MeasurementCreate(APIModel):
    sample_id: UUID
    measurement_type_term_id: UUID
    instrument: str | None = None
    temperature_value: float | None = None
    temperature_unit: str | None = None
    pressure_value: float | None = Field(default=None, ge=0)
    pressure_unit: str | None = None
    heating_rate_value: float | None = None
    heating_rate_unit: str | None = None
    frequency_value: float | None = None
    frequency_unit: str | None = None
    wavelength_value: float | None = None
    wavelength_unit: str | None = None
    parameters: dict | None = None
    source_paper_id: UUID | None = None
    evidence_id: UUID | None = None
    performed_at: datetime | None = None
