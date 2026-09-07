from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from .common import APIModel


class DeviceLayerIn(APIModel):
    sequence_number: int = Field(ge=1, le=65535)
    role_term_id: UUID
    material_id: UUID | None = None
    material_text: str | None = None
    thickness_value: float | None = Field(default=None, ge=0)
    thickness_unit: str | None = None


class DeviceCreate(APIModel):
    source_paper_id: UUID | None = None
    device_type_term_id: UUID
    active_material_sample_id: UUID
    geometry: dict | None = None
    electrode_materials: dict | None = None
    device_dimensions: dict | None = None
    fabrication_description: str | None = None
    evidence_id: UUID | None = None
    layers: list[DeviceLayerIn] = Field(default_factory=list)


class DeviceRead(DeviceCreate):
    id: UUID
    row_version: int
    created_at: datetime
    updated_at: datetime


class DeviceTestCreate(APIModel):
    test_type_term_id: UUID
    pulse_width_value: float | None = Field(default=None, ge=0)
    pulse_width_unit: str | None = None
    pulse_voltage_value: float | None = None
    pulse_voltage_unit: str | None = None
    pulse_current_value: float | None = None
    pulse_current_unit: str | None = None
    ambient_temperature_value: float | None = None
    ambient_temperature_unit: str | None = None
    parameters: dict | None = None
    evidence_id: UUID | None = None


class DeviceTestRead(DeviceTestCreate):
    id: UUID
    device_id: UUID
    created_at: datetime
