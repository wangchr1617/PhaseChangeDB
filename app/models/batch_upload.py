from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field

from .common import APIModel, VerificationStatus
from .literature import PaperRead


class ParsedPaperPreview(APIModel):
    file_id: str
    filename: str
    file_size: int
    title: str
    journal: str | None = None
    publication_year: int | None = None
    first_author: str | None = None
    corresponding_author: str | None = None
    doi: str | None = None
    abstract: str | None = None
    status: str = "parsed"  # "parsed" | "failed"
    error_message: str | None = None


class BatchUploadResponse(APIModel):
    total_files: int
    parsed_count: int
    failed_count: int
    items: list[ParsedPaperPreview]


class BatchIngestItem(APIModel):
    title: str = Field(min_length=1)
    journal: str | None = None
    publication_year: int | None = None
    first_author: str | None = None
    corresponding_author: str | None = None
    doi: str | None = None
    abstract: str | None = None
    metadata: dict[str, Any] | None = None


class BatchIngestRequest(APIModel):
    items: list[BatchIngestItem] = Field(min_length=1)


class BatchIngestResponse(APIModel):
    total: int
    succeeded: int
    skipped: int
    failed: int
    papers: list[PaperRead]


class ConflictObservationItem(APIModel):
    observation_id: UUID
    property_code: str
    property_name: str
    value: float | str | bool | None = None
    display_value: str
    normalized_value: float | None = None
    normalized_unit: str | None = None
    condition_temperature: str | None = None
    condition_pressure: str | None = None
    measurement_instrument: str | None = None
    paper_id: UUID | None = None
    paper_title: str | None = None
    paper_doi: str | None = None
    first_author: str | None = None
    corresponding_author: str | None = None
    journal: str | None = None
    publication_year: int | None = None
    verification_status: VerificationStatus
    quality_score: float | None = None


class ObservationConflictGroup(APIModel):
    material_id: UUID
    material_formula: str
    property_code: str
    property_name: str
    conflict_type: str = "condition_discrepancy"  # "condition_discrepancy" | "explicit_dispute"
    discrepancy_description: str
    items: list[ConflictObservationItem]


class LiteratureAgentConfig(APIModel):
    agent_name: str = "PhaseChangeLiteratureAgent"
    version: str = "v1.0-alpha"
    enabled: bool = True
    available_models: list[str] = [
        "gemini-2.5-pro",
    ]
    default_model: str = "gemini-2.5-pro"
    prompt_version: str = "pcm-extract-v2.1"
    ontology_version: str = "0.3.0"
    auto_staging_enabled: bool = True
    require_human_review: bool = True


class YearCountItem(APIModel):
    year: int
    count: int


class JournalCountItem(APIModel):
    journal: str
    count: int


class AuthorCountItem(APIModel):
    author: str
    count: int


class SystemCountItem(APIModel):
    chemical_system: str
    count: int


class LiteratureStatsResponse(APIModel):
    total_papers: int
    year_distribution: list[YearCountItem]
    journal_distribution: list[JournalCountItem]
    author_distribution: list[AuthorCountItem]
    system_distribution: list[SystemCountItem] = Field(default_factory=list)


class GraphNode(APIModel):
    id: str
    label: str
    node_type: str  # "material" | "element" | "paper" | "property"
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(APIModel):
    id: str
    source: str
    target: str
    edge_type: str  # "CONTAINS_ELEMENT" | "MENTIONS" | "HAS_PROPERTY" | "AUTHORED"
    label: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphSummary(APIModel):
    total_nodes: int
    total_edges: int
    material_count: int
    paper_count: int
    element_count: int
    property_count: int
    system_count: int = 0
    author_count: int = 0
    journal_count: int = 0
    dopant_count: int = 0
    observation_count: int = 0


class KnowledgeGraphResponse(APIModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    summary: GraphSummary
