from uuid import UUID

from fastapi import APIRouter, Header, Query, status

from app.models.common import CursorPage, VerificationStatus
from app.models.observation import EvidenceLinkCreate, ObservationCreate, ObservationPatch, ObservationRead

router = APIRouter(prefix="/v1/observations", tags=["observations"])


def _not_implemented():
    raise NotImplementedError("Contract-only endpoint: connect application service")


@router.post("", response_model=ObservationRead, status_code=status.HTTP_201_CREATED)
async def create_observation(body: ObservationCreate) -> ObservationRead:
    _not_implemented()


@router.get("", response_model=CursorPage[ObservationRead])
async def list_observations(
    material_id: UUID | None = None,
    sample_id: UUID | None = None,
    property_code: str | None = None,
    verification_status: VerificationStatus | None = None,
    value_min: float | None = None,
    value_max: float | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> CursorPage[ObservationRead]:
    _not_implemented()


@router.get("/{observation_id}", response_model=ObservationRead)
async def get_observation(observation_id: UUID) -> ObservationRead:
    _not_implemented()


@router.patch("/{observation_id}", response_model=ObservationRead)
async def patch_observation(
    observation_id: UUID,
    body: ObservationPatch,
    if_match: str = Header(alias="If-Match"),
) -> ObservationRead:
    _not_implemented()


@router.post("/{observation_id}/evidence", response_model=ObservationRead)
async def link_evidence(observation_id: UUID, body: EvidenceLinkCreate) -> ObservationRead:
    _not_implemented()
