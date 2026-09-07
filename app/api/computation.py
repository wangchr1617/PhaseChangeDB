from uuid import UUID

from fastapi import APIRouter, status

from app.models.computation import CalculationCreate, CalculationRead, StructureCreate, StructureRead

router = APIRouter(prefix="/v1", tags=["computation"])


def _not_implemented():
    raise NotImplementedError("Contract-only endpoint: connect application service")


@router.post("/structures", response_model=StructureRead, status_code=status.HTTP_201_CREATED)
async def create_structure(body: StructureCreate) -> StructureRead:
    _not_implemented()


@router.post("/calculations", response_model=CalculationRead, status_code=status.HTTP_202_ACCEPTED)
async def create_calculation(body: CalculationCreate) -> CalculationRead:
    _not_implemented()


@router.get("/calculations/{calculation_id}", response_model=CalculationRead)
async def get_calculation(calculation_id: UUID) -> CalculationRead:
    _not_implemented()
