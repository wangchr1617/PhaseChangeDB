"""PhaseChangeDB 科学知识图谱 MySQL 拓扑生成仓储实现。

负责宏观相变骨干网络、材料文献星丛、细粒度掺杂-物性-文献证据链多维拓扑子图构建与图摘要统计。
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.material_normalizer import VALID_ELEMENTS
from app.domain.normalization import format_display_value
from app.infrastructure.repositories.base import BaseMySQLRepository, to_json, to_number, to_uuid
from app.infrastructure.repositories.material_repository import MySQLMaterialRepository
from app.models.batch_upload import GraphEdge, GraphNode, GraphSummary, KnowledgeGraphResponse


class MySQLGraphRepository(BaseMySQLRepository):
    """科学知识图谱 MySQL 仓储。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.materials = MySQLMaterialRepository(session)

    async def get_knowledge_graph(
        self,
        element: str | None = None,
        material_id: str | None = None,
        include_papers: bool = False,
        subgraph: str | None = None,
        limit: int = 60,
    ) -> KnowledgeGraphResponse:
        """基于权威 MySQL 数据源构建宏观科学骨干图谱或材料文献证据子图谱。"""
        materials = await self.materials.list_materials(
            query=None, limit=limit, elements=[element] if element else None
        )
        if material_id:
            try:
                target_mid = UUID(material_id)
                materials = [m for m in materials if m.id == target_mid]
            except ValueError:
                pass

        material_map = {str(m.id): m for m in materials}
        if not materials:
            return KnowledgeGraphResponse(
                nodes=[],
                edges=[],
                summary=GraphSummary(
                    total_nodes=0,
                    total_edges=0,
                    material_count=0,
                    paper_count=0,
                    element_count=0,
                    property_count=0,
                    system_count=0,
                    author_count=0,
                    journal_count=0,
                ),
            )

        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        node_ids: set[str] = set()
        edge_keys: set[tuple[str, str, str]] = set()

        for m in materials:
            m_id = f"mat_{m.id}"
            if m_id not in node_ids:
                node_ids.add(m_id)
                nodes.append(
                    GraphNode(
                        id=m_id,
                        label=m.canonical_formula,
                        node_type="material",
                        properties={
                            "material_id": str(m.id),
                            "canonical_formula": m.canonical_formula,
                            "chemical_system": m.chemical_system,
                            "name": m.name or m.canonical_formula,
                        },
                    )
                )

        if subgraph in ("fine_grained", "evidence_chain"):
            obs_sql = """
                SELECT
                    o.id AS obs_id,
                    pdef.code AS property_code,
                    pdef.name AS property_name,
                    pdef.symbol AS property_symbol,
                    m.id AS material_id,
                    m.canonical_formula AS base_material,
                    s.sample_label,
                    s.thickness_value,
                    s.substrate_material,
                    meas.instrument,
                    meas.heating_rate_value,
                    meas.heating_rate_unit,
                    o.value_numeric,
                    o.original_value_text,
                    o.original_unit_text,
                    o.normalized_value,
                    o.verification_status,
                    p.id AS paper_id,
                    p.title AS paper_title,
                    p.doi AS paper_doi,
                    p.publication_year,
                    p.metadata_json AS paper_metadata,
                    ef.figure_number,
                    ef.text_snippet
                FROM obs_observation o
                JOIN obs_property_definition pdef ON o.property_definition_id = pdef.id
                JOIN sam_sample s ON o.sample_id = s.id
                JOIN mat_material m ON s.nominal_material_id = m.id
                LEFT JOIN exp_measurement meas ON o.measurement_id = meas.id
                LEFT JOIN lit_paper p ON s.source_paper_id = p.id
                LEFT JOIN evd_observation_link eol ON o.id = eol.observation_id
                LEFT JOIN evd_fragment ef ON (eol.evidence_fragment_id = ef.id OR meas.evidence_id = ef.id)
                WHERE o.verification_status != 'RETRACTED'
            """
            params: dict[str, Any] = {"limit": limit}
            if material_id:
                try:
                    params["mid"] = UUID(material_id).bytes
                    obs_sql += " AND m.id = :mid "
                except ValueError:
                    pass
            obs_sql += " ORDER BY o.created_at DESC LIMIT :limit"

            obs_rows = (await self.session.execute(text(obs_sql), params)).mappings().all()

            for r in obs_rows:
                m_guid = to_uuid(r["material_id"])
                m_node_id = f"mat_{m_guid}"
                if m_node_id not in node_ids:
                    node_ids.add(m_node_id)
                    nodes.append(
                        GraphNode(
                            id=m_node_id,
                            label=r["base_material"],
                            node_type="material",
                            properties={"material_id": str(m_guid), "formula": r["base_material"]},
                        )
                    )

                sample_lbl = r["sample_label"] or r["base_material"]
                dop_elem = None
                for cand_elem in ("Bi", "In", "Sb", "Ag", "N", "C", "Ti", "Sc", "Cr", "Cu", "Al", "Si"):
                    if r["base_material"] == "GeTe" and cand_elem in ("Ge", "Te"):
                        continue
                    if r["base_material"] == "Sb2Te3" and cand_elem in ("Sb", "Te"):
                        continue
                    if re.search(rf"\b{cand_elem}\b|{cand_elem}\d+", sample_lbl):
                        dop_elem = cand_elem
                        break

                parent_source_id = m_node_id
                if dop_elem:
                    dop_node_id = f"dopant_{dop_elem}"
                    if dop_node_id not in node_ids:
                        node_ids.add(dop_node_id)
                        nodes.append(
                            GraphNode(
                                id=dop_node_id,
                                label=f"掺杂: {dop_elem}",
                                node_type="dopant",
                                properties={"element": dop_elem},
                            )
                        )
                    edge_key = (m_node_id, dop_node_id, "DOPED_WITH")
                    if edge_key not in edge_keys:
                        edge_keys.add(edge_key)
                        edges.append(
                            GraphEdge(
                                id=f"e_{len(edges)}",
                                source=m_node_id,
                                target=dop_node_id,
                                edge_type="DOPED_WITH",
                                label="改性掺杂",
                            )
                        )
                    parent_source_id = dop_node_id

                obs_guid = to_uuid(r["obs_id"])
                obs_node_id = f"obs_{obs_guid}"
                val_txt = f"{r['original_value_text']}{r['original_unit_text'] or ''}"
                hr_txt = f" ({r['heating_rate_value']}K/min)" if r["heating_rate_value"] else ""
                obs_label = f"{r['property_symbol'] or r['property_code'][:2]}: {val_txt}{hr_txt}"

                if obs_node_id not in node_ids:
                    node_ids.add(obs_node_id)
                    nodes.append(
                        GraphNode(
                            id=obs_node_id,
                            label=obs_label,
                            node_type="observation",
                            properties={
                                "observation_id": str(obs_guid),
                                "property_code": r["property_code"],
                                "property_name": r["property_name"],
                                "value": str(r["value_numeric"]),
                                "unit": r["original_unit_text"],
                                "heating_rate": str(r["heating_rate_value"]) if r["heating_rate_value"] else None,
                                "status": r["verification_status"],
                                "sample_label": sample_lbl,
                                "snippet": r["text_snippet"],
                                "figure": r["figure_number"],
                            },
                        )
                    )

                edge_key = (parent_source_id, obs_node_id, "EXHIBITS_PROPERTY")
                if edge_key not in edge_keys:
                    edge_keys.add(edge_key)
                    edges.append(
                        GraphEdge(
                            id=f"e_{len(edges)}",
                            source=parent_source_id,
                            target=obs_node_id,
                            edge_type="EXHIBITS_PROPERTY",
                            label="测得物性",
                        )
                    )

                if r["paper_id"]:
                    p_guid = to_uuid(r["paper_id"])
                    p_node_id = f"paper_{p_guid}"
                    p_title = r["paper_title"] or "Academic Paper"
                    if p_node_id not in node_ids:
                        node_ids.add(p_node_id)
                        nodes.append(
                            GraphNode(
                                id=p_node_id,
                                label=p_title[:24] + "..." if len(p_title) > 26 else p_title,
                                node_type="paper",
                                properties={
                                    "paper_id": str(p_guid),
                                    "title": p_title,
                                    "doi": r["paper_doi"],
                                    "year": r["publication_year"],
                                },
                            )
                        )

                    edge_key = (obs_node_id, p_node_id, "REPORTED_IN")
                    if edge_key not in edge_keys:
                        edge_keys.add(edge_key)
                        edges.append(
                            GraphEdge(
                                id=f"e_{len(edges)}",
                                source=obs_node_id,
                                target=p_node_id,
                                edge_type="REPORTED_IN",
                                label="报道于文献",
                            )
                        )

                    p_meta = to_json(r["paper_metadata"]) or {}
                    author_name = p_meta.get("first_author")
                    if author_name:
                        a_node_id = f"auth_{author_name.replace(' ', '_')}"
                        if a_node_id not in node_ids:
                            node_ids.add(a_node_id)
                            nodes.append(
                                GraphNode(
                                    id=a_node_id,
                                    label=author_name,
                                    node_type="first_author",
                                    properties={"name": author_name},
                                )
                            )
                        edge_key = (p_node_id, a_node_id, "AUTHORED_BY")
                        if edge_key not in edge_keys:
                            edge_keys.add(edge_key)
                            edges.append(
                                GraphEdge(
                                    id=f"e_{len(edges)}",
                                    source=p_node_id,
                                    target=a_node_id,
                                    edge_type="AUTHORED_BY",
                                    label="学者发表",
                                )
                            )

        elif subgraph == "literature" or (material_id and subgraph != "macro"):
            max_papers_per_mat = min(limit, 35)
            for m in materials:
                m_node_id = f"mat_{m.id}"
                formula_clean = m.canonical_formula

                p_sql = """
                    SELECT DISTINCT p.id, p.doi, p.title, p.journal,
                           p.publication_year, p.abstract, p.metadata_json, p.created_at
                    FROM lit_paper p
                    WHERE EXISTS (
                        SELECT 1 FROM sam_sample s WHERE s.source_paper_id = p.id AND s.nominal_material_id = :mid
                    )
                    OR p.title LIKE :form_query
                    OR p.abstract LIKE :form_query
                    OR JSON_SEARCH(p.metadata_json, 'one', :formula, NULL, '$.related_materials') IS NOT NULL
                    ORDER BY p.publication_year DESC, p.created_at DESC
                    LIMIT :paper_limit
                """
                p_rows = (
                    await self.session.execute(
                        text(p_sql),
                        {
                            "mid": m.id.bytes,
                            "form_query": f"%{formula_clean}%",
                            "formula": formula_clean,
                            "paper_limit": max_papers_per_mat,
                        },
                    )
                ).mappings().all()

                for pr in p_rows:
                    p_guid = to_uuid(pr["id"])
                    p_node_id = f"paper_{p_guid}"
                    p_meta = to_json(pr["metadata_json"]) or {}
                    p_title = pr["title"]
                    p_first_author = p_meta.get("first_author")
                    p_corr_author = p_meta.get("corresponding_author")

                    if p_node_id not in node_ids:
                        node_ids.add(p_node_id)
                        nodes.append(
                            GraphNode(
                                id=p_node_id,
                                label=p_title[:26] + "..." if len(p_title) > 28 else p_title,
                                node_type="paper",
                                properties={
                                    "paper_id": str(p_guid),
                                    "title": p_title,
                                    "doi": pr["doi"],
                                    "journal": pr["journal"],
                                    "year": pr["publication_year"],
                                    "first_author": p_first_author,
                                    "corresponding_author": p_corr_author,
                                },
                            )
                        )

                    edge_key = (m_node_id, p_node_id, "EVIDENCED_BY")
                    if edge_key not in edge_keys:
                        edge_keys.add(edge_key)
                        edges.append(
                            GraphEdge(
                                id=f"e_{len(edges)}",
                                source=m_node_id,
                                target=p_node_id,
                                edge_type="EVIDENCED_BY",
                                label="文献证据",
                            )
                        )

                    if p_first_author and p_first_author.strip():
                        fa_name = p_first_author.strip()
                        fa_node_id = f"author_{re.sub(r'[^a-zA-Z0-9]', '_', fa_name)}"
                        if fa_node_id not in node_ids:
                            node_ids.add(fa_node_id)
                            nodes.append(
                                GraphNode(
                                    id=fa_node_id,
                                    label=fa_name,
                                    node_type="first_author",
                                    properties={"name": fa_name, "role": "第一作者"},
                                )
                            )
                        fa_edge_key = (p_node_id, fa_node_id, "FIRST_AUTHORED_BY")
                        if fa_edge_key not in edge_keys:
                            edge_keys.add(edge_key)
                            edges.append(
                                GraphEdge(
                                    id=f"e_{len(edges)}",
                                    source=p_node_id,
                                    target=fa_node_id,
                                    edge_type="FIRST_AUTHORED_BY",
                                    label="第一作者",
                                )
                            )

                    if p_corr_author and p_corr_author.strip():
                        ca_name = p_corr_author.strip()
                        if not p_first_author or ca_name != p_first_author.strip():
                            ca_node_id = f"author_{re.sub(r'[^a-zA-Z0-9]', '_', ca_name)}"
                            if ca_node_id not in node_ids:
                                node_ids.add(ca_node_id)
                                nodes.append(
                                    GraphNode(
                                        id=ca_node_id,
                                        label=ca_name,
                                        node_type="corresponding_author",
                                        properties={"name": ca_name, "role": "通讯作者"},
                                    )
                                )
                            ca_edge_key = (p_node_id, ca_node_id, "CORRESPONDING_AUTHORED_BY")
                            if ca_edge_key not in edge_keys:
                                edge_keys.add(ca_edge_key)
                                edges.append(
                                    GraphEdge(
                                        id=f"e_{len(edges)}",
                                        source=p_node_id,
                                        target=ca_node_id,
                                        edge_type="CORRESPONDING_AUTHORED_BY",
                                        label="通讯作者",
                                    )
                                )

                    if pr["journal"] and pr["journal"].strip():
                        j_name = pr["journal"].strip()
                        j_node_id = f"journal_{re.sub(r'[^a-zA-Z0-9]', '_', j_name)}"
                        if j_node_id not in node_ids:
                            node_ids.add(j_node_id)
                            nodes.append(
                                GraphNode(
                                    id=j_node_id,
                                    label=j_name[:24] + "..." if len(j_name) > 26 else j_name,
                                    node_type="journal",
                                    properties={"name": j_name},
                                )
                            )
                        j_edge_key = (p_node_id, j_node_id, "PUBLISHED_IN")
                        if j_edge_key not in edge_keys:
                            edge_keys.add(j_edge_key)
                            edges.append(
                                GraphEdge(
                                    id=f"e_{len(edges)}",
                                    source=p_node_id,
                                    target=j_node_id,
                                    edge_type="PUBLISHED_IN",
                                    label="发表于",
                                )
                            )

        else:
            for m in materials:
                m_node_id = f"mat_{m.id}"
                chem_sys = m.chemical_system or ""
                elements_in_mat = [el for el in chem_sys.split("-") if el in VALID_ELEMENTS]
                if not elements_in_mat:
                    elements_in_mat = [
                        el for el in re.findall(r"[A-Z][a-z]?", m.canonical_formula) if el in VALID_ELEMENTS
                    ]

                for el in set(elements_in_mat):
                    el_node_id = f"elem_{el}"
                    if el_node_id not in node_ids:
                        node_ids.add(el_node_id)
                        nodes.append(
                            GraphNode(
                                id=el_node_id,
                                label=el,
                                node_type="element",
                                properties={"symbol": el},
                            )
                        )
                    edge_key = (m_node_id, el_node_id, "CONTAINS_ELEMENT")
                    if edge_key not in edge_keys:
                        edge_keys.add(edge_key)
                        edges.append(
                            GraphEdge(
                                id=f"e_{len(edges)}",
                                source=m_node_id,
                                target=el_node_id,
                                edge_type="CONTAINS_ELEMENT",
                                label="包含元素",
                            )
                        )

                if chem_sys:
                    sys_node_id = f"sys_{chem_sys}"
                    if sys_node_id not in node_ids:
                        node_ids.add(sys_node_id)
                        nodes.append(
                            GraphNode(
                                id=sys_node_id,
                                label=chem_sys,
                                node_type="system",
                                properties={"chemical_system": chem_sys},
                            )
                        )
                    edge_key = (m_node_id, sys_node_id, "BELONGS_TO_SYSTEM")
                    if edge_key not in edge_keys:
                        edge_keys.add(edge_key)
                        edges.append(
                            GraphEdge(
                                id=f"e_{len(edges)}",
                                source=m_node_id,
                                target=sys_node_id,
                                edge_type="BELONGS_TO_SYSTEM",
                                label="所属体系",
                            )
                        )

            mat_ids_bytes = [m.id.bytes for m in materials]
            if mat_ids_bytes:
                placeholders = ", ".join([f":mid_{i}" for i in range(len(mat_ids_bytes))])
                params = {f"mid_{i}": mid for i, mid in enumerate(mat_ids_bytes)}
                obs_sql = f"""
                    SELECT
                        o.id AS obs_id,
                        s.nominal_material_id AS material_id,
                        pd.id AS prop_id,
                        pd.name AS property_name,
                        canon_u.code AS canonical_unit,
                        o.value_numeric,
                        o.value_kind,
                        o.normalized_value,
                        u.code AS normalized_unit,
                        o.value_text,
                        o.value_min,
                        o.value_max
                    FROM obs_observation o
                    JOIN sam_sample s ON s.id = o.sample_id
                    JOIN obs_property_definition pd ON pd.id = o.property_definition_id
                    LEFT JOIN ont_term canon_u ON canon_u.id = pd.canonical_unit_term_id
                    LEFT JOIN ont_term u ON u.id = o.normalized_unit_term_id
                    WHERE s.nominal_material_id IN ({placeholders})
                    LIMIT 50
                """
                obs_rows = (await self.session.execute(text(obs_sql), params)).mappings().all()
                for r in obs_rows:
                    mat_guid = to_uuid(r["material_id"])
                    if not mat_guid or str(mat_guid) not in material_map:
                        continue
                    m_node_id = f"mat_{mat_guid}"
                    prop_guid = to_uuid(r["prop_id"])
                    prop_node_id = f"prop_{prop_guid}"

                    raw_val = to_number(r["value_numeric"]) if r["value_numeric"] is not None else r["value_text"]
                    disp_val = format_display_value(
                        value=raw_val,
                        unit=r["normalized_unit"] or r["canonical_unit"],
                        canonical_unit=r["canonical_unit"],
                        normalized_value=to_number(r["normalized_value"]),
                    )

                    if prop_node_id not in node_ids:
                        node_ids.add(prop_node_id)
                        nodes.append(
                            GraphNode(
                                id=prop_node_id,
                                label=r["property_name"],
                                node_type="property",
                                properties={
                                    "property_name": r["property_name"],
                                    "canonical_unit": r["canonical_unit"],
                                    "sample_value": disp_val,
                                },
                            )
                        )

                    edge_key = (m_node_id, prop_node_id, "HAS_PROPERTY")
                    if edge_key not in edge_keys:
                        edge_keys.add(edge_key)
                        edges.append(
                            GraphEdge(
                                id=f"e_{len(edges)}",
                                source=m_node_id,
                                target=prop_node_id,
                                edge_type="HAS_PROPERTY",
                                label=f"{r['property_name']}: {disp_val}",
                                properties={"display_value": disp_val},
                            )
                        )

            if include_papers:
                for m in materials[:6]:
                    p_sql = """
                        SELECT DISTINCT p.id, p.doi, p.title, p.journal,
                               p.publication_year, p.metadata_json, p.created_at
                        FROM lit_paper p
                        WHERE EXISTS (
                            SELECT 1 FROM sam_sample s WHERE s.source_paper_id = p.id AND s.nominal_material_id = :mid
                        )
                        OR p.title LIKE :form_query
                        OR p.abstract LIKE :form_query
                        OR JSON_SEARCH(p.metadata_json, 'one', :formula, NULL, '$.related_materials') IS NOT NULL
                        ORDER BY p.publication_year DESC, p.created_at DESC
                        LIMIT 3
                    """
                    p_rows = (
                        await self.session.execute(
                            text(p_sql),
                            {
                                "mid": m.id.bytes,
                                "form_query": f"%{m.canonical_formula}%",
                                "formula": m.canonical_formula,
                            },
                        )
                    ).mappings().all()

                    for pr in p_rows:
                        p_guid = to_uuid(pr["id"])
                        p_node_id = f"paper_{p_guid}"
                        p_meta = to_json(pr["metadata_json"]) or {}
                        p_title = pr["title"]

                        if p_node_id not in node_ids:
                            node_ids.add(p_node_id)
                            nodes.append(
                                GraphNode(
                                    id=p_node_id,
                                    label=p_title[:24] + "..." if len(p_title) > 26 else p_title,
                                    node_type="paper",
                                    properties={
                                        "paper_id": str(p_guid),
                                        "title": p_title,
                                        "doi": pr["doi"],
                                        "journal": pr["journal"],
                                        "year": pr["publication_year"],
                                        "first_author": p_meta.get("first_author"),
                                        "corresponding_author": p_meta.get("corresponding_author"),
                                    },
                                )
                            )
                        edge_key = (f"mat_{m.id}", p_node_id, "EVIDENCED_BY")
                        if edge_key not in edge_keys:
                            edge_keys.add(edge_key)
                            edges.append(
                                GraphEdge(
                                    id=f"e_{len(edges)}",
                                    source=f"mat_{m.id}",
                                    target=p_node_id,
                                    edge_type="EVIDENCED_BY",
                                    label="文献证据",
                                )
                            )

        mat_cnt = sum(1 for n in nodes if n.node_type == "material")
        elem_cnt = sum(1 for n in nodes if n.node_type == "element")
        paper_cnt = sum(1 for n in nodes if n.node_type == "paper")
        prop_cnt = sum(1 for n in nodes if n.node_type == "property")
        sys_cnt = sum(1 for n in nodes if n.node_type == "system")
        author_cnt = sum(1 for n in nodes if n.node_type in ("author", "first_author", "corresponding_author"))
        journal_cnt = sum(1 for n in nodes if n.node_type == "journal")
        dopant_cnt = sum(1 for n in nodes if n.node_type == "dopant")
        obs_cnt = sum(1 for n in nodes if n.node_type == "observation")

        return KnowledgeGraphResponse(
            nodes=nodes,
            edges=edges,
            summary=GraphSummary(
                total_nodes=len(nodes),
                total_edges=len(edges),
                material_count=mat_cnt,
                paper_count=paper_cnt,
                element_count=elem_cnt,
                property_count=prop_cnt,
                system_count=sys_cnt,
                author_count=author_cnt,
                journal_count=journal_cnt,
                dopant_count=dopant_cnt,
                observation_count=obs_cnt,
            ),
        )
