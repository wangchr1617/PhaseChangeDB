from __future__ import annotations

from uuid import UUID

from pydantic import Field

from .common import APIModel, RecordMeta


class CompositionComponentIn(APIModel):
    element_symbol: str = Field(min_length=1, max_length=3)
    amount: float | None = Field(default=None, ge=0)
    atomic_fraction: float | None = Field(default=None, ge=0, le=1)
    role_term_id: UUID | None = None
    concentration_value: float | None = Field(default=None, ge=0)
    concentration_unit: str | None = Field(default=None, max_length=32)


class MaterialCreate(APIModel):
    canonical_formula: str = Field(min_length=1, max_length=255)
    reduced_formula: str | None = Field(default=None, max_length=255)
    chemical_system: str = Field(min_length=1, max_length=255)
    material_family_term_id: UUID | None = None
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)
    components: list[CompositionComponentIn] = Field(default_factory=list)


class MaterialPatch(APIModel):
    canonical_formula: str | None = Field(default=None, min_length=1, max_length=255)
    reduced_formula: str | None = Field(default=None, max_length=255)
    chemical_system: str | None = Field(default=None, min_length=1, max_length=255)
    material_family_term_id: UUID | None = None
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None


class MaterialRead(RecordMeta):
    canonical_formula: str
    reduced_formula: str | None = None
    chemical_system: str
    material_family_term_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)
    components: list[CompositionComponentIn] = Field(default_factory=list)
