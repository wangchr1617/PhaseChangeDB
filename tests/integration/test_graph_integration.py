import pytest

from app.infrastructure.database import session_factory
from app.infrastructure.mysql_catalog import MySQLCatalogRepository


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mysql_literature_stats_integration():
    async with session_factory() as session:
        repo = MySQLCatalogRepository(session)
        stats = await repo.get_literature_stats()
        assert stats.total_papers >= 0
        assert isinstance(stats.year_distribution, list)
        assert isinstance(stats.journal_distribution, list)
        assert isinstance(stats.author_distribution, list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mysql_knowledge_graph_integration():
    async with session_factory() as session:
        repo = MySQLCatalogRepository(session)
        graph = await repo.get_knowledge_graph(limit=30)
        assert graph.summary.total_nodes >= 0
        assert graph.summary.total_edges >= 0
        assert isinstance(graph.nodes, list)
        assert isinstance(graph.edges, list)
        # 如果数据库有材料，检查是否能正常生成节点
        if graph.summary.material_count > 0:
            mat_nodes = [n for n in graph.nodes if n.node_type == "material"]
            assert len(mat_nodes) == graph.summary.material_count
