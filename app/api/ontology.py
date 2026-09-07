from fastapi import APIRouter, Query

from app.models.common import CursorPage
from app.models.ontology import OntologyTermRead, PropertyDefinitionRead

router = APIRouter(prefix="/v1", tags=["ontology"])


def _not_implemented():
    raise NotImplementedError("Contract-only endpoint: connect application service")


@router.get("/ontology/terms", response_model=CursorPage[OntologyTermRead])
async def list_terms(
    namespace: str | None = None,
    q: str | None = None,
    include_deprecated: bool = False,
    cursor: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> CursorPage[OntologyTermRead]:
    _not_implemented()


@router.get("/properties", response_model=CursorPage[PropertyDefinitionRead])
async def list_properties(
    category_code: str | None = None,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> CursorPage[PropertyDefinitionRead]:
    _not_implemented()
