from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from .common import APIModel, ClaimStance, VerificationStatus


class ClaimEvidenceIn(APIModel):
    evidence_fragment_id: UUID
    stance: ClaimStance
    confidence: float | None = Field(default=None, ge=0, le=1)


class ClaimCreate(APIModel):
    claim_type_term_id: UUID
    claim_text: str = Field(min_length=1)
    structured_claim: dict | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    verification_status: VerificationStatus = VerificationStatus.AI_EXTRACTED
    source_type: str = "human"
    material_ids: list[UUID] = Field(default_factory=list)
    property_definition_ids: list[UUID] = Field(default_factory=list)
    evidence: list[ClaimEvidenceIn] = Field(default_factory=list)


class ClaimPatch(APIModel):
    claim_text: str | None = Field(default=None, min_length=1)
    structured_claim: dict | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    verification_status: VerificationStatus | None = None


class ClaimRead(ClaimCreate):
    id: UUID
    row_version: int
    created_at: datetime
    updated_at: datetime


class KnowledgeGapRead(APIModel):
    id: UUID
    material_id: UUID
    property_definition_id: UUID
    gap_type: str
    gap_score: float
    evidence_count: int
    observation_count: int
    paper_count: int
    condition_coverage_score: float | None = None
    conflict_score: float | None = None
    status: str
    algorithm_version: str
    generated_at: datetime
