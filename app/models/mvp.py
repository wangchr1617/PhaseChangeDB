from datetime import datetime
from uuid import UUID

from pydantic import Field

from .common import APIModel, VerificationStatus


class DashboardRead(APIModel):
    materials: int = Field(ge=0)
    papers: int = Field(ge=0)
    observations: int = Field(ge=0)
    verified_observations: int = Field(ge=0)
    pending_outbox_events: int = Field(ge=0)


class PropertyOption(APIModel):
    id: UUID
    code: str
    name: str
    canonical_unit: str | None = None


class ObservationListItem(APIModel):
    id: UUID
    material_id: UUID | None = None
    material_formula: str | None = None
    property_code: str
    property_name: str
    value: float | str | bool | None = None
    unit: str | None = None
    verification_status: VerificationStatus
    quality_score: float | None = None
    created_at: datetime
