from __future__ import annotations

from datetime import datetime
from uuid import UUID

from .common import APIModel


class OntologyTermRead(APIModel):
    id: UUID
    namespace: str
    code: str
    label: str
    definition: str | None = None
    parent_id: UUID | None = None
    aliases: list[str] = []
    ontology_version: str
    deprecated: bool


class PropertyDefinitionRead(APIModel):
    id: UUID
    code: str
    name: str
    category_term_id: UUID | None = None
    symbol: str | None = None
    description: str | None = None
    dimension: str | None = None
    canonical_unit_term_id: UUID | None = None
    value_kind: str
    created_at: datetime
    updated_at: datetime
