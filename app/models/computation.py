from __future__ import annotations

from datetime import datetime
from uuid import UUID

from .common import APIModel


class StructureCreate(APIModel):
    material_id: UUID
    sample_id: UUID | None = None
    structure_type: str
    space_group: str | None = None
    artifact_id: UUID
    structure_hash: str
    source: str | None = None
    metadata: dict | None = None


class StructureRead(StructureCreate):
    id: UUID
    created_at: datetime


class CalculationCreate(APIModel):
    structure_id: UUID
    calculation_type_term_id: UUID
    method: str
    code: str
    code_version: str | None = None
    functional: str | None = None
    pseudopotential: str | None = None
    parameters: dict | None = None


class CalculationRead(CalculationCreate):
    id: UUID
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
