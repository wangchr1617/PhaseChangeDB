from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field

from .common import APIModel


class SearchFilters(APIModel):
    publication_year_min: int | None = None
    publication_year_max: int | None = None
    material_ids: list[UUID] = Field(default_factory=list)
    material_formulas: list[str] = Field(default_factory=list)
    property_codes: list[str] = Field(default_factory=list)
    verification_status: list[str] = Field(default_factory=list)
    fragment_types: list[str] = Field(default_factory=list)


class SearchRequest(APIModel):
    query: str = Field(min_length=1, max_length=2000)
    targets: list[Literal["papers", "evidence", "materials", "observations", "claims"]] = Field(
        default_factory=lambda: ["evidence"]
    )
    mode: Literal["lexical", "semantic", "hybrid"] = "hybrid"
    filters: SearchFilters = Field(default_factory=SearchFilters)
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = None


class SearchHit(APIModel):
    target: str
    id: UUID
    score: float | None = None
    title: str | None = None
    snippet: str | None = None
    metadata: dict = Field(default_factory=dict)


class SearchResponse(APIModel):
    hits: list[SearchHit]
    next_cursor: str | None = None
    has_more: bool


class AgentAskRequest(APIModel):
    question: str = Field(min_length=1, max_length=10000)
    material_ids: list[UUID] = Field(default_factory=list)
    require_verified: bool = True
    include_conflicting_evidence: bool = True


class AgentEvidence(APIModel):
    evidence_id: UUID
    paper_id: UUID
    page_number: int | None = None
    figure_number: str | None = None
    table_number: str | None = None
    snippet: str | None = None
    stance: str | None = None


class AgentAnswer(APIModel):
    answer: str
    confidence: float = Field(ge=0, le=1)
    limitations: list[str] = Field(default_factory=list)
    evidence: list[AgentEvidence] = Field(default_factory=list)
    tool_trace_id: UUID
