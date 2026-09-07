from uuid import UUID

from fastapi import APIRouter, status

from app.models.device import DeviceCreate, DeviceRead, DeviceTestCreate, DeviceTestRead

router = APIRouter(prefix="/v1/devices", tags=["devices"])


def _not_implemented():
    raise NotImplementedError("Contract-only endpoint: connect application service")


@router.post("", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
async def create_device(body: DeviceCreate) -> DeviceRead:
    _not_implemented()


@router.get("/{device_id}", response_model=DeviceRead)
async def get_device(device_id: UUID) -> DeviceRead:
    _not_implemented()


@router.post("/{device_id}/tests", response_model=DeviceTestRead, status_code=status.HTTP_201_CREATED)
async def create_device_test(device_id: UUID, body: DeviceTestCreate) -> DeviceTestRead:
    _not_implemented()
