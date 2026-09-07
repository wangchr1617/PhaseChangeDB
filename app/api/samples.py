from uuid import UUID

from fastapi import APIRouter, Header, status

from app.models.sample import MeasurementCreate, ProcessRunCreate, SampleCreate, SamplePatch, SampleRead

router = APIRouter(prefix="/v1", tags=["samples"])


def _not_implemented():
    raise NotImplementedError("Contract-only endpoint: connect application service")


@router.post("/samples", response_model=SampleRead, status_code=status.HTTP_201_CREATED)
async def create_sample(body: SampleCreate) -> SampleRead:
    _not_implemented()


@router.get("/samples/{sample_id}", response_model=SampleRead)
async def get_sample(sample_id: UUID) -> SampleRead:
    _not_implemented()


@router.patch("/samples/{sample_id}", response_model=SampleRead)
async def patch_sample(
    sample_id: UUID,
    body: SamplePatch,
    if_match: str = Header(alias="If-Match"),
) -> SampleRead:
    _not_implemented()


@router.post("/process-runs", status_code=status.HTTP_201_CREATED)
async def create_process_run(body: ProcessRunCreate) -> dict:
    _not_implemented()


@router.post("/measurements", status_code=status.HTTP_201_CREATED)
async def create_measurement(body: MeasurementCreate) -> dict:
    _not_implemented()
