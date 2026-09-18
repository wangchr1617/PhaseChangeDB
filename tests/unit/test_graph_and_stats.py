from app.models.batch_upload import (
    AuthorCountItem,
    GraphEdge,
    GraphNode,
    GraphSummary,
    JournalCountItem,
    KnowledgeGraphResponse,
    LiteratureStatsResponse,
    YearCountItem,
)


def test_literature_stats_response_model():
    resp = LiteratureStatsResponse(
        total_papers=10,
        year_distribution=[YearCountItem(year=2020, count=5), YearCountItem(year=2021, count=5)],
        journal_distribution=[JournalCountItem(journal="Nature Materials", count=8)],
        author_distribution=[AuthorCountItem(author="Matthias Wuttig", count=4)],
    )
    assert resp.total_papers == 10
    assert len(resp.year_distribution) == 2
    assert resp.journal_distribution[0].journal == "Nature Materials"


def test_knowledge_graph_response_model():
    node1 = GraphNode(id="mat_1", label="Ge2Sb2Te5", node_type="material", properties={"formula": "Ge2Sb2Te5"})
    node2 = GraphNode(id="elem_Ge", label="Ge", node_type="element")
    edge1 = GraphEdge(id="e1", source="mat_1", target="elem_Ge", edge_type="CONTAINS_ELEMENT", label="包含元素")

    resp = KnowledgeGraphResponse(
        nodes=[node1, node2],
        edges=[edge1],
        summary=GraphSummary(
            total_nodes=2,
            total_edges=1,
            material_count=1,
            paper_count=0,
            element_count=1,
            property_count=0,
        ),
    )
    assert resp.summary.total_nodes == 2
    assert resp.edges[0].edge_type == "CONTAINS_ELEMENT"
