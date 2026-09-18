"""测试批量文献入库与材料观测冲突检测集成用例。"""

import os

import pytest
from uuid6 import uuid7

from app.infrastructure.database import session_factory
from app.infrastructure.mysql_catalog import MySQLCatalogRepository
from app.models.batch_upload import BatchIngestItem, BatchIngestRequest

pytestmark = pytest.mark.skipif(
    os.environ.get("PCM_INTEGRATION") != "1",
    reason="需要真实 MySQL 实例，设置 PCM_INTEGRATION=1 运行",
)


@pytest.mark.asyncio
async def test_batch_ingest_and_deduplication():
    async with session_factory() as session:
        repo = MySQLCatalogRepository(session)
        doi_unique = f"10.1016/j.pcm.{uuid7().hex}"
        title_unique = f"Novel Fast Phase Change Material {uuid7().hex}"


        req = BatchIngestRequest(
            items=[
                BatchIngestItem(
                    title=title_unique,
                    doi=doi_unique,
                    journal="Acta Materialia",
                    publication_year=2024,
                    first_author="Chao Peng",
                    corresponding_author="Zhitang Song",
                    abstract="Ultrafast crystallization kinetics in Ge-Sb alloys.",
                ),
                # 相同 DOI 的重复项
                BatchIngestItem(
                    title=f"{title_unique} (Duplicate)",
                    doi=doi_unique,
                    journal="Acta Materialia",
                    publication_year=2024,
                ),
            ]
        )


        res = await repo.batch_ingest_papers(req)
        assert res.total == 2
        assert res.succeeded == 1
        assert res.skipped == 1
        assert len(res.papers) == 1
        assert res.papers[0].doi == doi_unique
        assert res.papers[0].first_author == "Chao Peng"
        assert res.papers[0].corresponding_author == "Zhitang Song"



@pytest.mark.asyncio
async def test_material_conflicts_query():
    async with session_factory() as session:
        repo = MySQLCatalogRepository(session)
        # 获取一个材料（如 GeTe 或 GST）
        materials = await repo.list_materials(query=None, limit=10)

        assert len(materials) > 0
        mat_id = str(materials[0].id)

        conflicts = await repo.get_material_conflicts(mat_id)
        assert isinstance(conflicts, list)
        for c in conflicts:
            assert c.material_id == materials[0].id
            assert c.property_code
            assert len(c.items) >= 2
            for item in c.items:
                assert item.observation_id
                assert item.display_value
