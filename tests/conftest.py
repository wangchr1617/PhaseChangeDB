import pytest

from app.infrastructure.database import engine


@pytest.fixture(autouse=True)
async def dispose_db_engine():
    yield
    await engine.dispose()
