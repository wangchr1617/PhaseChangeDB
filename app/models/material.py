from typing import Any
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


class VariantObservationRead(APIModel):
    id: UUID
    property_code: str
    property_name: str
    value: float | str | bool | None = None
    unit: str | None = None
    display_value: str | None = None
    verification_status: str = "HUMAN_REVIEWED"


class MaterialVariantRead(APIModel):
    sample_id: UUID
    sample_label: str | None = None
    nominal_formula: str
    original_name: str | None = None
    doping_element: str | None = None
    doping_concentration: float | None = None
    preparation_method: str | None = None
    annealing_temperature: str | None = None
    pressure: str | None = None
    test_method: str | None = None
    crystal_phase: str | None = None
    atmosphere: str | None = None
    cooling_rate: str | None = None
    paper_id: UUID | None = None
    paper_title: str | None = None
    paper_doi: str | None = None
    first_author: str | None = None
    corresponding_author: str | None = None
    journal: str | None = None
    publication_year: int | None = None
    observations: list[VariantObservationRead] = Field(default_factory=list)


class MaterialRead(RecordMeta):
    canonical_formula: str
    reduced_formula: str | None = None
    chemical_system: str
    material_family_term_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)
    components: list[CompositionComponentIn] = Field(default_factory=list)
    is_low_toxicity: bool = True
    is_cost_effective: bool = True
    variant_count: int = 0
    paper_count: int = 0
    typical_properties: dict[str, Any] = Field(default_factory=dict)
    variants: list[MaterialVariantRead] = Field(default_factory=list)

