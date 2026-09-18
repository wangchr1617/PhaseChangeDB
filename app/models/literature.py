from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from .common import APIModel


class PaperCreate(APIModel):
    doi: str | None = Field(default=None, max_length=255)
    title: str = Field(min_length=1)
    journal: str | None = Field(default=None, max_length=255)
    publication_year: int | None = Field(default=None, ge=1600, le=2200)
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    publisher: str | None = None
    abstract: str | None = None
    metadata: dict | None = None
    first_author: str | None = None
    corresponding_author: str | None = None
    authors: list[str] = Field(default_factory=list)


class PaperPatch(APIModel):
    doi: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, min_length=1)
    journal: str | None = Field(default=None, max_length=255)
    publication_year: int | None = Field(default=None, ge=1600, le=2200)
    abstract: str | None = None
    metadata: dict | None = None
    first_author: str | None = None
    corresponding_author: str | None = None
    authors: list[str] | None = None


class PaperRead(APIModel):
    id: UUID
    doi: str | None = None
    title: str
    journal: str | None = None
    publication_year: int | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    publisher: str | None = None
    abstract: str | None = None
    metadata: dict | None = None
    first_author: str | None = None
    corresponding_author: str | None = None
    authors: list[str] = Field(default_factory=list)
    row_version: int
    created_at: datetime
    updated_at: datetime


class DocumentCreate(APIModel):
    document_type: str
    artifact_id: UUID


class DocumentRead(APIModel):
    id: UUID
    paper_id: UUID
    document_type: str
    artifact_id: UUID
    parser_version: str | None = None
    parse_status: str
    created_at: datetime
    updated_at: datetime


class EvidenceRead(APIModel):
    id: UUID
    paper_id: UUID
    document_id: UUID
    fragment_type: str
    page_number: int | None = None
    section: str | None = None
    figure_number: str | None = None
    table_number: str | None = None
    text_snippet: str | None = None
    artifact_id: UUID | None = None
    created_at: datetime
