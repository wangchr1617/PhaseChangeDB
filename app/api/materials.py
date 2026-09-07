from uuid import UUID

from fastapi import APIRouter, Header, Query, status

from app.models.common import CursorPage
from app.models.material import MaterialCreate, MaterialPatch, MaterialRead
from app.models.observation import ObservationRead

router = APIRouter(prefix="/v1/materials", tags=["materials"])


def _not_implemented():
    raise NotImplementedError("Contract-only endpoint: connect application service")


@router.post("", response_model=MaterialRead, status_code=status.HTTP_201_CREATED)
async def create_material(body: MaterialCreate) -> MaterialRead:
    _not_implemented()


@router.get("", response_model=CursorPage[MaterialRead])
async def list_materials(
    q: str | None = None,
    chemical_system: str | None = None,
    family_code: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> CursorPage[MaterialRead]:
    _not_implemented()


@router.get("/{material_id}", response_model=MaterialRead)
async def get_material(material_id: UUID) -> MaterialRead:
    _not_implemented()


@router.patch("/{material_id}", response_model=MaterialRead)
async def patch_material(
    material_id: UUID,
    body: MaterialPatch,
    if_match: str = Header(alias="If-Match"),
) -> MaterialRead:
    """If-Match is the current row_version ETag, e.g. W/"7"."""
    _not_implemented()


@router.get("/{material_id}/observations", response_model=CursorPage[ObservationRead])
async def list_material_observations(
    material_id: UUID,
    property_code: str | None = None,
    verification_status: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> CursorPage[ObservationRead]:
    _not_implemented()
