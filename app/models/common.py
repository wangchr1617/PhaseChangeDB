from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    """Strict external contract. Unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class VerificationStatus(StrEnum):
    AI_EXTRACTED = "AI_EXTRACTED"
    AI_VALIDATED = "AI_VALIDATED"
    HUMAN_REVIEWED = "HUMAN_REVIEWED"
    VERIFIED = "VERIFIED"
    DISPUTED = "DISPUTED"
    RETRACTED = "RETRACTED"


class ValueKind(StrEnum):
    SCALAR = "scalar"
    RANGE = "range"
    TEXT = "text"
    BOOLEAN = "boolean"
    CATEGORICAL = "categorical"
    CURVE = "curve"


class EvidenceRole(StrEnum):
    PRIMARY = "primary"
    SUPPORTING = "supporting"
    DERIVED = "derived"
    CONTEXT = "context"


class ClaimStance(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    QUALIFIES = "qualifies"


class CandidateStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    MODIFIED = "modified"
    REJECTED = "rejected"


class RecordMeta(APIModel):
    id: UUID
    row_version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime


T = TypeVar("T")


class CursorPage(APIModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
    has_more: bool


class ProblemDetail(APIModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    request_id: str | None = None
    errors: list[dict] | None = None
