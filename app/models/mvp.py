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
    normalized_value: float | str | None = None
    normalized_unit: str | None = None
    display_value: str | None = None
    verification_status: VerificationStatus
    quality_score: float | None = None
    created_at: datetime


class PropertyComparisonDataPoint(APIModel):
    observation_id: UUID
    property_code: str
    property_name: str
    material_formula: str
    base_material: str
    dopant_element: str | None = None
    dopant_at_pct: float | None = None
    sample_formula: str
    value: float
    unit: str
    normalized_value: float | None = None
    normalized_unit: str | None = None
    heating_rate_k_per_min: float | None = None
    measurement_method: str | None = None
    film_thickness_nm: float | None = None
    substrate: str | None = None
    paper_id: UUID | None = None
    paper_title: str | None = None
    paper_doi: str | None = None
    paper_year: int | None = None
    first_author: str | None = None
    evidence_snippet: str | None = None
    figure_or_table: str | None = None
    page_number: int | None = None
    verification_status: str
    quality_score: float | None = None


class PropertyBoxPlotStat(APIModel):
    group_name: str
    count: int
    min_val: float
    q1: float
    median: float
    q3: float
    max_val: float


class PropertyComparisonResponse(APIModel):
    property_code: str
    property_name: str
    display_unit: str
    total_count: int
    data_points: list[PropertyComparisonDataPoint]
    box_plot_stats: list[PropertyBoxPlotStat]
    available_properties: list[dict[str, str]]
    available_materials: list[str]
    available_heating_rates: list[float]

