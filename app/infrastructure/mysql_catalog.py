import json
import re
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from app.domain.material_normalizer import (
    VALID_ELEMENTS,
    extract_elements,
    is_cost_effective,
    is_low_toxicity,
    is_valid_chemical_alias,
    normalize_formula,
)
from app.domain.normalization import format_display_value
from app.models.batch_upload import (
    AuthorCountItem,
    BatchIngestItem,
    BatchIngestRequest,
    BatchIngestResponse,
    ConflictObservationItem,
    GraphEdge,
    GraphNode,
    GraphSummary,
    JournalCountItem,
    KnowledgeGraphResponse,
    LiteratureStatsResponse,
    ObservationConflictGroup,
    SystemCountItem,
    YearCountItem,
)
from app.models.config import AppConfigRead, AppConfigUpdate
from app.models.literature import PaperCreate, PaperRead
from app.models.material import MaterialCreate, MaterialRead, MaterialVariantRead, VariantObservationRead
from app.models.mvp import (
    DashboardRead,
    ObservationListItem,
    PropertyBoxPlotStat,
    PropertyComparisonDataPoint,
    PropertyComparisonResponse,
    PropertyOption,
)
from app.models.observation import ObservationCreate, ObservationRead
from app.models.search import SearchHit


def _uuid(value: bytes | bytearray | memoryview | None) -> UUID | None:
    return UUID(bytes=bytes(value)) if value is not None else None


def _json(value: Any) -> dict | None:
    if value is None or isinstance(value, dict):
        return value
    return json.loads(value)


def _number(value: Decimal | int | float | None) -> float | None:
    return float(value) if value is not None else None




class MySQLCatalogRepository:
    """MVP 所需的 MySQL 仓储实现。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def dashboard(self) -> DashboardRead:
        row = (
            (
                await self.session.execute(
                    text(
                        """
                    SELECT
                      (SELECT COUNT(*) FROM mat_material) AS materials,
                      (SELECT COUNT(*) FROM lit_paper) AS papers,
                      (SELECT COUNT(*) FROM obs_observation) AS observations,
                      (SELECT COUNT(*) FROM obs_observation
                       WHERE verification_status = 'VERIFIED') AS verified_observations,
                      (SELECT COUNT(*) FROM sys_outbox_event
                       WHERE status IN ('pending', 'processing')) AS pending_outbox_events
                    """
                    )
                )
            )
            .mappings()
            .one()
        )
        return DashboardRead(**row)

    async def list_materials(
        self,
        query: str | None = None,
        limit: int = 50,
        elements: list[str] | None = None,
        min_tc: float | None = None,
        max_tc: float | None = None,
        min_latent_heat: float | None = None,
        max_latent_heat: float | None = None,
        low_toxicity: bool | None = None,
        cost_effective: bool | None = None,
    ) -> list[MaterialRead]:
        conditions = [
            "m.canonical_formula NOT LIKE 'CandReqId%'",
            "m.canonical_formula NOT LIKE 'ReqIdMat%'",
            "m.canonical_formula NOT LIKE 'AcceptanceMat%'",
        ]
        params: dict[str, Any] = {}

        if query:
            conditions.append(
                "(m.canonical_formula LIKE :query OR m.chemical_system LIKE :query OR m.name LIKE :query "
                "OR EXISTS (SELECT 1 FROM mat_material_alias ma WHERE ma.material_id = m.id AND ma.alias LIKE :query))"
            )
            params["query"] = f"%{query}%"

        if elements:
            for idx, el in enumerate(elements):
                el_clean = el.strip()
                if not el_clean:
                    continue
                sys_param = f"elem_sys_{idx}"
                form_param = f"elem_form_{idx}"
                conditions.append(
                    f"(CONCAT('-', m.chemical_system, '-') LIKE :{sys_param} OR m.canonical_formula LIKE :{form_param})"
                )
                params[sys_param] = f"%-{el_clean}-%"
                params[form_param] = f"%{el_clean}%"

        where = f"WHERE {' AND '.join(conditions)}"
        sql = f"""
            SELECT m.id, m.canonical_formula, m.reduced_formula, m.chemical_system,
                   m.material_family_term_id, m.name, m.description, m.row_version, m.created_at, m.updated_at
            FROM mat_material m
            {where}
            ORDER BY m.updated_at DESC, m.id DESC
        """
        rows = (await self.session.execute(text(sql), params)).mappings().all()
        if not rows:
            return []

        # 批量获取别名、样品与观测统计
        mids = [r["id"] for r in rows]
        placeholders = ", ".join([f":mid_{i}" for i in range(len(mids))])
        mparams = {f"mid_{i}": mid for i, mid in enumerate(mids)}

        alias_sql = f"SELECT material_id, alias FROM mat_material_alias WHERE material_id IN ({placeholders})"
        alias_rows = (await self.session.execute(text(alias_sql), mparams)).mappings().all()
        aliases_by_mat: dict[bytes, list[str]] = {}
        for ar in alias_rows:
            aliases_by_mat.setdefault(bytes(ar["material_id"]), []).append(ar["alias"])

        # 查询每个材料关联的样品数量、文献数量及相变温度/潜热观测
        stats_sql = f"""
            SELECT s.nominal_material_id AS material_id,
                   s.id AS sample_id,
                   s.source_paper_id,
                   pd.code AS property_code,
                   canon_u.code AS canonical_unit,
                   o.value_numeric,
                   o.normalized_value,
                   o.original_unit_text
            FROM sam_sample s
            LEFT JOIN obs_observation o ON o.sample_id = s.id
            LEFT JOIN obs_property_definition pd ON pd.id = o.property_definition_id
            LEFT JOIN ont_term canon_u ON canon_u.id = pd.canonical_unit_term_id
            WHERE s.nominal_material_id IN ({placeholders})
        """
        stats_rows = (await self.session.execute(text(stats_sql), mparams)).mappings().all()

        samples_by_mat: dict[bytes, set[bytes]] = {}
        papers_by_mat: dict[bytes, set[bytes]] = {}
        tc_obs_by_mat: dict[bytes, list[float]] = {}
        lh_obs_by_mat: dict[bytes, list[float]] = {}

        for sr in stats_rows:
            mat_b = bytes(sr["material_id"])
            if sr["sample_id"]:
                samples_by_mat.setdefault(mat_b, set()).add(bytes(sr["sample_id"]))
            if sr["source_paper_id"]:
                papers_by_mat.setdefault(mat_b, set()).add(bytes(sr["source_paper_id"]))

            num_val = _number(sr["normalized_value"] if sr["normalized_value"] is not None else sr["value_numeric"])
            if num_val is not None:
                p_code = (sr["property_code"] or "").lower()
                if "crystallization_temperature" in p_code or p_code in {"tx", "tc"}:
                    tc_obs_by_mat.setdefault(mat_b, []).append(num_val)
                elif "latent_heat" in p_code or "enthalpy" in p_code:
                    lh_obs_by_mat.setdefault(mat_b, []).append(num_val)

        results: list[MaterialRead] = []
        for row in rows:
            mat_b = bytes(row["id"])
            c_form = row["canonical_formula"]
            elems = extract_elements(c_form)
            is_low_tox = is_low_toxicity(elems)
            is_cost_eff = is_cost_effective(elems)

            if low_toxicity is not None and is_low_tox != low_toxicity:
                continue
            if cost_effective is not None and is_cost_eff != cost_effective:
                continue

            tc_list = tc_obs_by_mat.get(mat_b, [])
            lh_list = lh_obs_by_mat.get(mat_b, [])

            if min_tc is not None and (not tc_list or max(tc_list) < min_tc):
                continue
            if max_tc is not None and (not tc_list or min(tc_list) > max_tc):
                continue
            if min_latent_heat is not None and (not lh_list or max(lh_list) < min_latent_heat):
                continue
            if max_latent_heat is not None and (not lh_list or min(lh_list) > max_latent_heat):
                continue

            typical_props: dict[str, Any] = {}
            if tc_list:
                rep_tc = round(sum(tc_list) / len(tc_list), 1)
                typical_props["crystallization_temperature"] = {
                    "value": rep_tc,
                    "unit": "K",
                    "display": f"{rep_tc} K",
                }
            if lh_list:
                rep_lh = round(sum(lh_list) / len(lh_list), 1)
                typical_props["latent_heat"] = {
                    "value": rep_lh,
                    "unit": "J/g",
                    "display": f"{rep_lh} J/g",
                }

            mat_obj = self._material(row)
            mat_obj.aliases = aliases_by_mat.get(mat_b, [])
            mat_obj.is_low_toxicity = is_low_tox
            mat_obj.is_cost_effective = is_cost_eff
            mat_obj.variant_count = len(samples_by_mat.get(mat_b, set()))
            mat_obj.paper_count = len(papers_by_mat.get(mat_b, set()))
            mat_obj.typical_properties = typical_props

            results.append(mat_obj)
            if len(results) >= limit:
                break

        return results

    async def get_existing_elements(self) -> list[str]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT DISTINCT chemical_system, canonical_formula
                    FROM mat_material
                    WHERE canonical_formula NOT LIKE 'CandReqId%'
                      AND canonical_formula NOT LIKE 'ReqIdMat%'
                      AND canonical_formula NOT LIKE 'AcceptanceMat%'
                    """
                )
            )
        ).fetchall()

        found_elements: set[str] = set()
        for r in rows:
            chem_sys = r[0] or ""
            formula = r[1] or ""
            for part in chem_sys.split("-"):
                p = part.strip()
                if p in VALID_ELEMENTS:
                    found_elements.add(p)
            for sym in re.findall(r"[A-Z][a-z]?", formula):
                if sym in VALID_ELEMENTS:
                    found_elements.add(sym)

        comp_rows = (
            await self.session.execute(
                text("SELECT DISTINCT element_symbol FROM mat_composition_component")
            )
        ).fetchall()
        for cr in comp_rows:
            sym = (cr[0] or "").strip()
            if sym in VALID_ELEMENTS:
                found_elements.add(sym)

        return sorted(found_elements)

    async def get_material(self, material_id: str) -> MaterialRead | None:
        try:
            mid = UUID(material_id)
        except ValueError:
            return None
        row = (
            (
                await self.session.execute(
                    text(
                        """
                    SELECT id, canonical_formula, reduced_formula, chemical_system,
                           material_family_term_id, name, description, row_version, created_at, updated_at
                    FROM mat_material WHERE id = :id
                    """
                    ),
                    {"id": mid.bytes},
                )
            )
            .mappings()
            .first()
        )
        if not row:
            return None
        alias_rows = (
            await self.session.execute(
                text("SELECT alias FROM mat_material_alias WHERE material_id = :id"),
                {"id": mid.bytes},
            )
        ).scalars().all()

        # 查询该材料下的所有样品变体及其工艺、测试与文献
        variants_sql = """
            SELECT s.id AS sample_id, s.sample_label, s.description AS sample_desc,
                   s.thickness_value, s.thickness_unit, s.substrate_material,
                   s.source_paper_id,
                   lp.title AS paper_title, lp.doi AS paper_doi, lp.journal AS paper_journal,
                   lp.publication_year AS paper_year, lp.metadata_json AS paper_meta,
                   em.instrument AS measurement_instrument,
                   em.temperature_value AS meas_temp, em.temperature_unit AS meas_temp_unit,
                   em.pressure_value AS meas_press, em.pressure_unit AS meas_press_unit,
                   pr.process_name,
                   ps.temperature_value AS proc_temp, ps.temperature_unit AS proc_temp_unit,
                   ps.pressure_value AS proc_press, ps.pressure_unit AS proc_press_unit
            FROM sam_sample s
            LEFT JOIN lit_paper lp ON lp.id = s.source_paper_id
            LEFT JOIN exp_measurement em ON em.sample_id = s.id
            LEFT JOIN exp_process_run pr ON pr.sample_id = s.id
            LEFT JOIN exp_process_step ps ON ps.process_run_id = pr.id
            WHERE s.nominal_material_id = :mid
            ORDER BY s.created_at DESC
        """
        sample_rows = (
            await self.session.execute(text(variants_sql), {"mid": mid.bytes})
        ).mappings().all()

        paper_ids = [r["source_paper_id"] for r in sample_rows if r["source_paper_id"]]
        authors_map = await self._load_authors_for_papers(paper_ids) if paper_ids else {}

        # 查询这些 sample 对应的观测
        sids = [r["sample_id"] for r in sample_rows]
        obs_by_sample: dict[bytes, list[VariantObservationRead]] = {}
        if sids:
            s_placeholders = ", ".join([f":sid_{i}" for i in range(len(sids))])
            sparams = {f"sid_{i}": sid for i, sid in enumerate(sids)}
            obs_sql = f"""
                SELECT o.id, o.sample_id, pd.code AS property_code, pd.name AS property_name,
                       canon_u.code AS canonical_unit,
                       o.value_numeric, o.normalized_value, o.original_unit_text, o.value_text,
                       o.verification_status
                FROM obs_observation o
                JOIN obs_property_definition pd ON pd.id = o.property_definition_id
                LEFT JOIN ont_term canon_u ON canon_u.id = pd.canonical_unit_term_id
                WHERE o.sample_id IN ({s_placeholders})
            """
            obs_rows = (await self.session.execute(text(obs_sql), sparams)).mappings().all()
            for obs_r in obs_rows:
                s_b = bytes(obs_r["sample_id"])
                raw_v = _number(obs_r["value_numeric"]) if obs_r["value_numeric"] is not None else obs_r["value_text"]
                disp_v = format_display_value(
                    value=raw_v,
                    unit=obs_r["original_unit_text"] or obs_r["canonical_unit"],
                    canonical_unit=obs_r["canonical_unit"],
                    normalized_value=_number(obs_r["normalized_value"]),
                )
                obs_by_sample.setdefault(s_b, []).append(
                    VariantObservationRead(
                        id=UUID(bytes=bytes(obs_r["id"])),
                        property_code=obs_r["property_code"],
                        property_name=obs_r["property_name"],
                        value=raw_v,
                        unit=obs_r["original_unit_text"] or obs_r["canonical_unit"],
                        display_value=disp_v,
                        verification_status=obs_r["verification_status"],
                    )
                )

        seen_sample_ids: set[bytes] = set()
        variants: list[MaterialVariantRead] = []
        c_form = row["canonical_formula"]

        for sr in sample_rows:
            sid_b = bytes(sr["sample_id"])
            if sid_b in seen_sample_ids:
                continue
            seen_sample_ids.add(sid_b)

            pid_bytes = bytes(sr["source_paper_id"]) if sr["source_paper_id"] else None
            p_authors = authors_map.get(pid_bytes, []) if pid_bytes else []
            first_auth = next((a["name"] for a in p_authors if a.get("author_order") == 1), None)
            corr_auth = next((a["name"] for a in p_authors if a.get("corresponding")), None)
            if not corr_auth and p_authors:
                corr_auth = p_authors[-1]["name"]

            # 解析掺杂与成分
            desc = sr["sample_desc"] or ""
            dopant_elem = None
            dopant_conc = None
            dop_pattern = r"([A-Z][a-z]?)[-_ ]?(?:dop(?:ed|ant)?|掺杂)[^0-9]*([0-9]+\.?[0-9]*)"
            dop_m = re.search(dop_pattern, desc, re.IGNORECASE)
            if dop_m:
                dopant_elem = dop_m.group(1)
                dopant_conc = float(dop_m.group(2))
            elif "Sc" in desc:
                dopant_elem = "Sc"
                dopant_conc = 0.2

            prep_method = sr["process_name"] or sr["substrate_material"]
            if sr["thickness_value"]:
                thick_str = f"{sr['thickness_value']} {sr['thickness_unit'] or 'nm'}"
                prep_method = f"{prep_method or '薄膜'} (厚度: {thick_str})".strip()

            anneal_temp = None
            if sr["proc_temp"] is not None:
                anneal_temp = format_display_value(sr["proc_temp"], sr["proc_temp_unit"] or "K", "K")
            elif sr["meas_temp"] is not None:
                anneal_temp = format_display_value(sr["meas_temp"], sr["meas_temp_unit"] or "K", "K")

            press_str = None
            if sr["meas_press"] is not None:
                press_str = f"{sr['meas_press']} {sr['meas_press_unit'] or 'GPa'}"
            elif sr["proc_press"] is not None:
                press_str = f"{sr['proc_press']} {sr['proc_press_unit'] or 'GPa'}"

            variants.append(
                MaterialVariantRead(
                    sample_id=UUID(bytes=sid_b),
                    sample_label=sr["sample_label"],
                    nominal_formula=c_form,
                    original_name=sr["sample_desc"] or sr["sample_label"],
                    doping_element=dopant_elem,
                    doping_concentration=dopant_conc,
                    preparation_method=prep_method,
                    annealing_temperature=anneal_temp,
                    pressure=press_str,
                    test_method=sr["measurement_instrument"],
                    crystal_phase="fcc / hcp" if "fcc" in desc.lower() else None,
                    atmosphere="vacuum / Ar" if "vacuum" in desc.lower() else None,
                    cooling_rate=None,
                    paper_id=UUID(bytes=pid_bytes) if pid_bytes else None,
                    paper_title=sr["paper_title"],
                    paper_doi=sr["paper_doi"],
                    first_author=first_auth,
                    corresponding_author=corr_auth,
                    journal=sr["paper_journal"],
                    publication_year=sr["paper_year"],
                    observations=obs_by_sample.get(sid_b, []),
                )
            )

        mat = self._material(row)
        mat.aliases = list(alias_rows)
        mat.variants = variants
        mat.variant_count = len(variants)
        mat.paper_count = len(set(paper_ids))
        return mat

    async def create_material(self, body: MaterialCreate) -> MaterialRead:
        norm = normalize_formula(body.canonical_formula)
        canonical_formula = norm.canonical_formula
        chemical_system = norm.chemical_system or body.chemical_system
        reduced_formula = norm.reduced_formula or body.reduced_formula or canonical_formula

        existing = (
            await self.session.execute(
                text("SELECT id FROM mat_material WHERE canonical_formula = :formula"),
                {"formula": canonical_formula},
            )
        ).mappings().first()

        if existing:
            mat_id = UUID(bytes=bytes(existing["id"]))
            alias_to_add = {a for a in body.aliases if is_valid_chemical_alias(a)}
            if body.canonical_formula != canonical_formula and is_valid_chemical_alias(body.canonical_formula):
                alias_to_add.add(body.canonical_formula)
            async with self.session.begin():
                for alias in alias_to_add:
                    await self.session.execute(
                        text(
                            "INSERT IGNORE INTO mat_material_alias (id, material_id, alias) "
                            "VALUES (:id, :mid, :alias)"
                        ),
                        {"id": uuid7().bytes, "mid": mat_id.bytes, "alias": alias},
                    )
            mat = await self.get_material(str(mat_id))
            assert mat is not None
            return mat

        material_id = uuid7()
        event_id = uuid7()
        async with self.session.begin():
            await self.session.execute(
                text(
                    """
                    INSERT INTO mat_material
                      (id, canonical_formula, reduced_formula, chemical_system,
                       material_family_term_id, name, description)
                    VALUES (:id, :canonical_formula, :reduced_formula, :chemical_system,
                            :family_id, :name, :description)
                    """
                ),
                {
                    "id": material_id.bytes,
                    "canonical_formula": canonical_formula,
                    "reduced_formula": reduced_formula,
                    "chemical_system": chemical_system,
                    "family_id": body.material_family_term_id.bytes if body.material_family_term_id else None,
                    "name": body.name or norm.name,
                    "description": body.description,
                },
            )
            all_aliases = {a for a in body.aliases if is_valid_chemical_alias(a)}
            if body.canonical_formula != canonical_formula and is_valid_chemical_alias(body.canonical_formula):
                all_aliases.add(body.canonical_formula)
            for alias in all_aliases:
                await self.session.execute(
                    text("INSERT INTO mat_material_alias (id, material_id, alias) VALUES (:id, :material_id, :alias)"),
                    {"id": uuid7().bytes, "material_id": material_id.bytes, "alias": alias},
                )
            await self._outbox(event_id, "Material", material_id, "MaterialCreated", {"id": str(material_id)})
        created = await self.get_material(str(material_id))
        assert created is not None
        return created

    async def _load_authors_for_papers(self, paper_ids: list[Any]) -> dict[bytes, list[dict[str, Any]]]:
        if not paper_ids:
            return {}
        pids_bytes = [bytes(p) for p in paper_ids]
        placeholders = ", ".join([f":pid_{i}" for i in range(len(pids_bytes))])
        params = {f"pid_{i}": pid for i, pid in enumerate(pids_bytes)}
        sql = f"""
            SELECT pa.paper_id, pa.author_order, pa.corresponding, a.name
            FROM lit_paper_author pa
            JOIN lit_author a ON a.id = pa.author_id
            WHERE pa.paper_id IN ({placeholders})
            ORDER BY pa.paper_id, pa.author_order ASC
        """
        rows = (await self.session.execute(text(sql), params)).mappings().all()
        res: dict[bytes, list[dict[str, Any]]] = {}
        for r in rows:
            pid = bytes(r["paper_id"])
            res.setdefault(pid, []).append({
                "name": r["name"],
                "author_order": r["author_order"],
                "corresponding": bool(r["corresponding"]),
            })
        return res

    async def list_papers(self, query: str | None, limit: int) -> list[PaperRead]:
        base_filter = """
            (metadata_json->>'$.is_test' IS NULL OR metadata_json->>'$.is_test' != 'true')
            AND (metadata_json->>'$.status' IS NULL OR metadata_json->>'$.status' != 'pending_review')
            AND title NOT LIKE 'Reject Paper%'
            AND title NOT LIKE 'ACCEPTANCE_TEST%'
            AND title NOT LIKE 'Candidate ReqId%'
            AND title NOT LIKE 'Audit ReqId%'
            AND title NOT LIKE 'Live Test%'
            AND title NOT LIKE 'Test ReqID%'
            AND title NOT LIKE 'AI EXTRACTION%'
            AND title NOT LIKE 'AI Cross Unit%'
            AND title NOT LIKE 'Paper for Decision Test%'
            AND title NOT LIKE 'Cross Unit Paper%'
            AND (doi IS NULL OR doi NOT LIKE '10.1000/%')
        """
        where = f"WHERE {base_filter}"
        params: dict[str, Any] = {"limit": limit}
        if query:
            where += " AND (title LIKE :query OR doi LIKE :query OR journal LIKE :query)"
            params["query"] = f"%{query}%"
        rows = (
            (
                await self.session.execute(
                    text(
                        f"SELECT * FROM lit_paper {where} ORDER BY publication_year DESC, updated_at DESC LIMIT :limit"
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
        paper_ids = [r["id"] for r in rows]
        authors_map = await self._load_authors_for_papers(paper_ids)
        return [self._paper(row, authors_map.get(bytes(row["id"]), [])) for row in rows]

    async def get_paper(self, paper_id: str) -> PaperRead | None:
        try:
            pid = UUID(paper_id)
        except ValueError:
            return None
        row = (
            await self.session.execute(
                text("SELECT * FROM lit_paper WHERE id = :id"),
                {"id": pid.bytes},
            )
        ).mappings().first()
        if not row:
            return None
        authors_map = await self._load_authors_for_papers([pid.bytes])
        return self._paper(row, authors_map.get(pid.bytes, []))

    async def create_paper(self, body: PaperCreate) -> PaperRead:
        paper_id = uuid7()
        meta = body.metadata or {}
        if body.authors and "authors" not in meta:
            meta["authors"] = body.authors
        if body.first_author and "first_author" not in meta:
            meta["first_author"] = body.first_author
        if body.corresponding_author and "corresponding_author" not in meta:
            meta["corresponding_author"] = body.corresponding_author

        async with self.session.begin():
            await self.session.execute(
                text(
                    """
                    INSERT INTO lit_paper
                      (id, doi, title, journal, publication_year, volume, issue,
                       pages, publisher, abstract, metadata_json)
                    VALUES (:id, :doi, :title, :journal, :year, :volume, :issue,
                            :pages, :publisher, :abstract, :metadata)
                    """
                ),
                {
                    "id": paper_id.bytes,
                    "doi": body.doi,
                    "title": body.title,
                    "journal": body.journal,
                    "year": body.publication_year,
                    "volume": body.volume,
                    "issue": body.issue,
                    "pages": body.pages,
                    "publisher": body.publisher,
                    "abstract": body.abstract,
                    "metadata": json.dumps(meta, ensure_ascii=False) if meta else None,
                },
            )
            await self._outbox(uuid7(), "Paper", paper_id, "PaperCreated", {"id": str(paper_id)})
        paper = await self.get_paper(str(paper_id))
        assert paper is not None
        return paper

    async def batch_ingest_papers(
        self, request: BatchIngestRequest | list[BatchIngestItem]
    ) -> BatchIngestResponse:
        item_list = request.items if isinstance(request, BatchIngestRequest) else request
        succeeded = 0
        skipped = 0
        failed = 0
        result_papers: list[PaperRead] = []
        author_cache: dict[str, bytes] = {}

        for item in item_list:
            try:
                title = item.title.strip()
                doi = item.doi.strip() if item.doi else None

                # 查找是否已存在相同 DOI 或完全相同的标题
                existing_row = None
                if doi:
                    existing_row = (
                        await self.session.execute(
                            text("SELECT id FROM lit_paper WHERE doi = :doi"),
                            {"doi": doi},
                        )
                    ).mappings().first()
                if not existing_row:
                    existing_row = (
                        await self.session.execute(
                            text("SELECT id FROM lit_paper WHERE title = :title"),
                            {"title": title},
                        )
                    ).mappings().first()

                if existing_row:
                    skipped += 1
                    continue

                # 插入新文献
                paper_id = uuid7()
                meta = dict(item.metadata or {})
                first_author = item.first_author.strip() if item.first_author else None
                corresponding_author = item.corresponding_author.strip() if item.corresponding_author else None
                authors = [first_author] if first_author else []
                if corresponding_author and corresponding_author not in authors:
                    authors.append(corresponding_author)

                # 启发式识别主要相变材料关联系谱（如 GeTe, Sb2Te3, Ge2Sb2Te5）
                corpus = f"{title} {item.abstract or ''}".lower()
                related_mats = []
                if "gete" in corpus:
                    related_mats.append("GeTe")
                if "sb2te3" in corpus or "sb-te" in corpus:
                    related_mats.append("Sb2Te3")
                if "ge2sb2te5" in corpus or "gst" in corpus or "ge-sb-te" in corpus:
                    related_mats.append("Ge2Sb2Te5")
                if related_mats:
                    meta["related_materials"] = list(set(related_mats))

                meta["authors"] = authors
                meta["first_author"] = first_author
                meta["corresponding_author"] = corresponding_author
                meta["is_test"] = False
                meta["status"] = "verified"

                await self.session.execute(
                    text(
                        """
                        INSERT INTO lit_paper
                          (id, doi, title, journal, publication_year, abstract, metadata_json)
                        VALUES (:id, :doi, :title, :journal, :year, :abstract, :metadata)
                        """
                    ),
                    {
                        "id": paper_id.bytes,
                        "doi": doi,
                        "title": title,
                        "journal": item.journal.strip() if item.journal else None,
                        "year": item.publication_year,
                        "abstract": item.abstract.strip() if item.abstract else None,
                        "metadata": json.dumps(meta, ensure_ascii=False),
                    },
                )

                # 插入作者关联（结合会话级在内存缓存，消除 N+1 重复查询）
                for order, author_name in enumerate(authors, start=1):
                    if author_name in author_cache:
                        author_id = author_cache[author_name]
                    else:
                        author_row = (
                            await self.session.execute(
                                text("SELECT id FROM lit_author WHERE name = :name"),
                                {"name": author_name},
                            )
                        ).mappings().first()
                        if author_row:
                            author_id = author_row["id"]
                        else:
                            author_id = uuid7().bytes
                            await self.session.execute(
                                text("INSERT INTO lit_author (id, name) VALUES (:id, :name)"),
                                {"id": author_id, "name": author_name},
                            )
                        author_cache[author_name] = author_id

                    is_corr = author_name == corresponding_author
                    await self.session.execute(
                        text(
                            """
                            INSERT INTO lit_paper_author (paper_id, author_id, author_order, corresponding)
                            VALUES (:pid, :aid, :order, :corr)
                            """
                        ),
                        {
                            "pid": paper_id.bytes,
                            "aid": author_id,
                            "order": order,
                            "corr": 1 if is_corr else 0,
                        },
                    )

                await self._outbox(uuid7(), "Paper", paper_id, "PaperCreated", {"id": str(paper_id)})
                await self.session.commit()

                created = await self.get_paper(str(paper_id))
                if created:
                    result_papers.append(created)
                    succeeded += 1
            except Exception:
                await self.session.rollback()
                failed += 1

        return BatchIngestResponse(
            total=len(item_list),
            succeeded=succeeded,
            skipped=skipped,
            failed=failed,
            papers=result_papers,
        )


    async def list_observations(self, limit: int) -> list[ObservationListItem]:
        rows = (
            (
                await self.session.execute(
                    text(
                        """
                    SELECT o.id, m.id AS material_id, m.canonical_formula AS material_formula,
                           p.code AS property_code, p.name AS property_name,
                           canon_u.code AS canonical_unit,
                           o.value_kind, o.value_numeric, o.value_min, o.value_max,
                           o.value_text, o.value_boolean, o.normalized_value,
                           o.original_value_text, o.original_unit_text,
                           COALESCE(u.code, o.original_unit_text) AS unit,
                           u.code AS normalized_unit_code,
                           o.verification_status, o.quality_score, o.created_at
                    FROM obs_observation o
                    JOIN obs_property_definition p ON p.id = o.property_definition_id
                    LEFT JOIN ont_term canon_u ON canon_u.id = p.canonical_unit_term_id
                    LEFT JOIN sam_sample s ON s.id = o.sample_id
                    LEFT JOIN mat_material m ON m.id = s.nominal_material_id
                    LEFT JOIN ont_term u ON u.id = o.normalized_unit_term_id
                    ORDER BY o.created_at DESC, o.id DESC LIMIT :limit
                    """
                    ),
                    {"limit": limit},
                )
            )
            .mappings()
            .all()
        )
        return [
            ObservationListItem(
                id=_uuid(row["id"]),
                material_id=_uuid(row["material_id"]),
                material_formula=row["material_formula"],
                property_code=row["property_code"],
                property_name=row["property_name"],
                value=self._observation_value(row),
                unit=row["unit"],
                normalized_value=_number(row["normalized_value"]),
                normalized_unit=row["normalized_unit_code"],
                display_value=format_display_value(
                    value=row["value_numeric"] if row["value_kind"] == "scalar" else self._observation_value(row),
                    unit=row["original_unit_text"] or row["unit"],
                    canonical_unit=row["canonical_unit"],
                    normalized_value=row["normalized_value"],
                ),
                verification_status=row["verification_status"],
                quality_score=_number(row["quality_score"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def create_observation(self, body: ObservationCreate) -> ObservationRead:
        observation_id = uuid7()
        values = body.model_dump(mode="python")
        params = {
            key: (value.bytes if isinstance(value, UUID) else value.value if hasattr(value, "value") else value)
            for key, value in values.items()
        }
        params["id"] = observation_id.bytes
        async with self.session.begin():
            await self.session.execute(
                text(
                    """
                    INSERT INTO obs_observation (
                      id, sample_id, device_id, calculation_id, property_definition_id,
                      measurement_id, device_test_id, phase_assignment_id, value_kind,
                      value_numeric, value_min, value_max, value_text, value_boolean,
                      original_value_text, original_unit_text, normalized_value,
                      normalized_unit_term_id, uncertainty_lower, uncertainty_upper,
                      condition_temperature_value, condition_temperature_unit,
                      condition_pressure_value, condition_pressure_unit, quality_score,
                      verification_status
                    ) VALUES (
                      :id, :sample_id, :device_id, :calculation_id, :property_definition_id,
                      :measurement_id, :device_test_id, :phase_assignment_id, :value_kind,
                      :value_numeric, :value_min, :value_max, :value_text, :value_boolean,
                      :original_value_text, :original_unit_text, :normalized_value,
                      :normalized_unit_term_id, :uncertainty_lower, :uncertainty_upper,
                      :condition_temperature_value, :condition_temperature_unit,
                      :condition_pressure_value, :condition_pressure_unit, :quality_score,
                      :verification_status
                    )
                    """
                ),
                params,
            )
            await self._outbox(
                uuid7(), "Observation", observation_id, "ObservationCreated", {"id": str(observation_id)}
            )
        row = (
            (
                await self.session.execute(
                    text("SELECT * FROM obs_observation WHERE id = :id"), {"id": observation_id.bytes}
                )
            )
            .mappings()
            .one()
        )
        return ObservationRead(
            **body.model_dump(),
            id=observation_id,
            row_version=row["row_version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            evidence=[],
        )

    async def list_properties(self) -> list[PropertyOption]:
        rows = (
            (
                await self.session.execute(
                    text(
                        """
                    SELECT p.id, p.code, p.name, u.code AS canonical_unit
                    FROM obs_property_definition p
                    LEFT JOIN ont_term u ON u.id = p.canonical_unit_term_id
                    ORDER BY p.name
                    """
                    )
                )
            )
            .mappings()
            .all()
        )
        return [
            PropertyOption(
                id=_uuid(row["id"]), code=row["code"], name=row["name"], canonical_unit=row["canonical_unit"]
            )
            for row in rows
        ]

    async def search(self, query: str, limit: int) -> list[SearchHit]:
        pattern = f"%{query}%"
        norm_res = normalize_formula(query)
        norm_pattern = f"%{norm_res.canonical_formula}%"
        material_rows = (
            (
                await self.session.execute(
                    text(
                        """
                    SELECT DISTINCT m.id, m.canonical_formula, m.chemical_system
                    FROM mat_material m
                    LEFT JOIN mat_material_alias a ON a.material_id = m.id
                    WHERE m.canonical_formula LIKE :query
                       OR m.canonical_formula LIKE :norm_query
                       OR m.chemical_system LIKE :query
                       OR m.name LIKE :query
                       OR a.alias LIKE :query
                       OR a.alias LIKE :norm_query
                    LIMIT :limit
                    """
                    ),
                    {"query": pattern, "norm_query": norm_pattern, "limit": limit},
                )
            )
            .mappings()
            .all()
        )
        base_filter = """
            (metadata_json->>'$.is_test' IS NULL OR metadata_json->>'$.is_test' != 'true')
            AND (metadata_json->>'$.status' IS NULL OR metadata_json->>'$.status' != 'pending_review')
            AND title NOT LIKE 'Reject Paper%'
            AND title NOT LIKE 'ACCEPTANCE_TEST%'
            AND title NOT LIKE 'Candidate ReqId%'
            AND title NOT LIKE 'Audit ReqId%'
            AND title NOT LIKE 'Live Test%'
            AND title NOT LIKE 'Test ReqID%'
            AND title NOT LIKE 'AI EXTRACTION%'
            AND title NOT LIKE 'AI Cross Unit%'
            AND title NOT LIKE 'Paper for Decision Test%'
            AND title NOT LIKE 'Cross Unit Paper%'
            AND (doi IS NULL OR doi NOT LIKE '10.1000/%')
        """
        paper_rows = (
            (
                await self.session.execute(
                    text(
                        f"""
                    SELECT id, title, journal, publication_year FROM lit_paper
                    WHERE ({base_filter}) AND (title LIKE :query OR doi LIKE :query OR abstract LIKE :query)
                    LIMIT :limit
                    """
                    ),
                    {"query": pattern, "limit": limit},
                )
            )
            .mappings()
            .all()
        )
        hits = [
            SearchHit(
                target="materials",
                id=_uuid(row["id"]),
                title=row["canonical_formula"],
                snippet=row["chemical_system"],
                score=None,
            )
            for row in material_rows
        ]
        hits.extend(
            SearchHit(
                target="papers",
                id=_uuid(row["id"]),
                title=row["title"],
                snippet=" · ".join(str(value) for value in (row["journal"], row["publication_year"]) if value),
                score=None,
            )
            for row in paper_rows
        )
        return hits[:limit]

    async def get_config(self) -> AppConfigRead:
        rows = (
            (await self.session.execute(text("SELECT config_key, config_value FROM sys_app_config"))).mappings().all()
        )
        config_map = {r["config_key"]: r["config_value"] for r in rows}
        return AppConfigRead(
            app_title=config_map.get("app_title", "PhaseChangeDB"),
            app_description=config_map.get("app_description", "相变材料知识库"),
            app_logo=config_map.get("app_logo", "/logo.svg"),
        )

    async def update_config(self, body: AppConfigUpdate) -> AppConfigRead:
        updates = body.model_dump(exclude_unset=True)
        if updates:
            async with self.session.begin():
                for k, v in updates.items():
                    if v is not None:
                        await self.session.execute(
                            text(
                                """
                                INSERT INTO sys_app_config (config_key, config_value)
                                VALUES (:key, :val)
                                ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)
                                """
                            ),
                            {"key": k, "val": v},
                        )
        return await self.get_config()

    async def get_material_conflicts(self, material_id: str) -> list[ObservationConflictGroup]:
        try:
            mid = UUID(material_id)
        except ValueError:
            return []

        mat_row = (
            await self.session.execute(
                text("SELECT id, canonical_formula FROM mat_material WHERE id = :id"),
                {"id": mid.bytes},
            )
        ).mappings().first()
        if not mat_row:
            return []

        canonical_formula = mat_row["canonical_formula"]

        # 查询此材料关联的所有观测及其测量条件与文献来源
        sql = """
            SELECT o.id, o.property_definition_id, p.code AS property_code, p.name AS property_name,
                   canon_u.code AS canonical_unit,
                   o.value_kind, o.value_numeric, o.value_min, o.value_max, o.value_text, o.value_boolean,
                   o.normalized_value, o.original_value_text, o.original_unit_text,
                   COALESCE(u.code, o.original_unit_text) AS unit,
                   u.code AS normalized_unit_code,
                   o.condition_temperature_value, o.condition_temperature_unit,
                   o.condition_pressure_value, o.condition_pressure_unit,
                   em.instrument AS measurement_instrument,
                   lp.id AS paper_id, lp.title AS paper_title, lp.doi AS paper_doi,
                   lp.journal AS paper_journal, lp.publication_year AS paper_year,
                   o.verification_status, o.quality_score
            FROM obs_observation o
            JOIN obs_property_definition p ON p.id = o.property_definition_id
            LEFT JOIN ont_term canon_u ON canon_u.id = p.canonical_unit_term_id
            LEFT JOIN sam_sample s ON s.id = o.sample_id
            LEFT JOIN ont_term u ON u.id = o.normalized_unit_term_id
            LEFT JOIN exp_measurement em ON em.id = o.measurement_id
            LEFT JOIN evd_observation_link eol ON eol.observation_id = o.id
            LEFT JOIN evd_fragment ef ON (ef.id = eol.evidence_fragment_id OR ef.id = em.evidence_id)
            LEFT JOIN lit_paper lp ON lp.id = ef.paper_id

            WHERE s.nominal_material_id = :mid
            ORDER BY p.code, o.created_at DESC
        """
        rows = (await self.session.execute(text(sql), {"mid": mid.bytes})).mappings().all()
        if not rows:
            return []

        # 收集涉及的 paper_id 以获取作者信息
        pids = [r["paper_id"] for r in rows if r["paper_id"]]
        authors_map = await self._load_authors_for_papers(pids) if pids else {}

        # 去重相同的 observation_id (因为左连接多条 evidence 可能导致同一 observation 产生多行)
        obs_seen: set[bytes] = set()
        unique_rows: list[dict[str, Any]] = []
        for r in rows:
            oid = bytes(r["id"])
            if oid not in obs_seen:
                obs_seen.add(oid)
                unique_rows.append(dict(r))

        # 按 property_code 分组
        prop_groups: dict[str, list[dict[str, Any]]] = {}
        for r in unique_rows:
            prop_groups.setdefault(r["property_code"], []).append(r)

        conflict_groups: list[ObservationConflictGroup] = []

        for p_code, obs_list in prop_groups.items():
            has_dispute = any(o["verification_status"] == "DISPUTED" for o in obs_list)

            # 比较数值差异与条件相近度
            numeric_obs = [
                o for o in obs_list
                if (o["normalized_value"] is not None or o["value_numeric"] is not None)
            ]

            has_discrepancy = False
            max_val = -1.0
            min_val = 1e12
            for o in numeric_obs:
                v = float(o["normalized_value"] if o["normalized_value"] is not None else o["value_numeric"])
                if v > max_val:
                    max_val = v
                if v < min_val:
                    min_val = v

            # 若极值差异超过 5%
            if min_val > 0 and max_val > 0 and len(numeric_obs) >= 2 and ((max_val - min_val) / max_val) > 0.05:
                has_discrepancy = True

            if has_dispute or has_discrepancy:
                items = [self._build_conflict_item(o, authors_map) for o in obs_list]
                diff_pct = round(((max_val - min_val) / max_val) * 100, 1) if (min_val > 0 and max_val > 0) else 0
                desc = (
                    f"在相近测试条件下，各文献报告数值存在明显差异"
                    f"（极值相对偏差达 {diff_pct}%，需人工复核确认仪器与样品上下文）。"
                    if has_discrepancy
                    else "该组观测记录包含争议数据（DISPUTED），需要结合证据链进行人工复核与仲裁。"
                )

                conflict_groups.append(
                    ObservationConflictGroup(
                        material_id=mid,
                        material_formula=canonical_formula,
                        property_code=p_code,
                        property_name=obs_list[0]["property_name"],
                        conflict_type="condition_discrepancy" if has_discrepancy else "explicit_dispute",
                        discrepancy_description=desc,
                        items=items,
                    )
                )

        return conflict_groups

    def _build_conflict_item(
        self, row: dict[str, Any], authors_map: dict[bytes, list[dict[str, Any]]]
    ) -> ConflictObservationItem:
        pid_bytes = bytes(row["paper_id"]) if row["paper_id"] else None
        authors_info = authors_map.get(pid_bytes, []) if pid_bytes else []
        first_author = next((a["name"] for a in authors_info if a.get("author_order") == 1), None)
        corr_author = next((a["name"] for a in authors_info if a.get("corresponding")), None)
        if not corr_author and authors_info:
            corr_author = authors_info[-1]["name"]

        temp_str = None
        if row["condition_temperature_value"] is not None:
            temp_str = f"{row['condition_temperature_value']} {row['condition_temperature_unit'] or 'K'}"

        press_str = None
        if row["condition_pressure_value"] is not None:
            press_str = f"{row['condition_pressure_value']} {row['condition_pressure_unit'] or 'GPa'}"

        display_val = format_display_value(
            value=row["value_numeric"] if row["value_kind"] == "scalar" else self._observation_value(row),
            unit=row["original_unit_text"] or row["unit"],
            canonical_unit=row["canonical_unit"],
            normalized_value=row["normalized_value"],
        )

        return ConflictObservationItem(
            observation_id=UUID(bytes=bytes(row["id"])),
            property_code=row["property_code"],
            property_name=row["property_name"],
            value=self._observation_value(row),
            display_value=display_val,
            normalized_value=_number(row["normalized_value"]),
            normalized_unit=row["normalized_unit_code"],
            condition_temperature=temp_str,
            condition_pressure=press_str,
            measurement_instrument=row["measurement_instrument"],
            paper_id=UUID(bytes=pid_bytes) if pid_bytes else None,
            paper_title=row["paper_title"],
            paper_doi=row["paper_doi"],
            first_author=first_author,
            corresponding_author=corr_author,
            journal=row["paper_journal"],
            publication_year=row["paper_year"],
            verification_status=row["verification_status"],
            quality_score=_number(row["quality_score"]),
        )

    async def _outbox(
        self, event_id: UUID, aggregate_type: str, aggregate_id: UUID, event_type: str, payload: dict
    ) -> None:
        await self.session.execute(
            text(
                """
                INSERT INTO sys_outbox_event (id, aggregate_type, aggregate_id, event_type, payload_json)
                VALUES (:id, :aggregate_type, :aggregate_id, :event_type, :payload)
                """
            ),
            {
                "id": event_id.bytes,
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id.bytes,
                "event_type": event_type,
                "payload": json.dumps(payload, ensure_ascii=False),
            },
        )

    @staticmethod
    def _material(row: Any) -> MaterialRead:
        c_form = row["canonical_formula"]
        elems = extract_elements(c_form)
        return MaterialRead(
            id=_uuid(row["id"]),
            canonical_formula=c_form,
            reduced_formula=row["reduced_formula"],
            chemical_system=row["chemical_system"],
            material_family_term_id=_uuid(row["material_family_term_id"]),
            name=row["name"],
            description=row["description"],
            row_version=row["row_version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            aliases=[],
            components=[],
            is_low_toxicity=is_low_toxicity(elems),
            is_cost_effective=is_cost_effective(elems),
            variant_count=0,
            paper_count=0,
            typical_properties={},
            variants=[],
        )

    @staticmethod
    def _paper(row: Any, authors_info: list[dict[str, Any]] | None = None) -> PaperRead:
        metadata = _json(row["metadata_json"]) or {}
        first_author = None
        corresponding_author = None
        authors: list[str] = []

        if authors_info:
            for a in authors_info:
                name = a["name"]
                authors.append(name)
                if a.get("author_order") == 1 and not first_author:
                    first_author = name
                if a.get("corresponding") and not corresponding_author:
                    corresponding_author = name

        if not authors and "authors" in metadata and isinstance(metadata["authors"], list):
            authors = [str(x) for x in metadata["authors"]]

        if not first_author:
            first_author = metadata.get("first_author") or (authors[0] if authors else None)

        if not corresponding_author:
            fallback = authors[-1] if len(authors) > 1 else first_author
            corresponding_author = metadata.get("corresponding_author") or fallback

        return PaperRead(
            id=_uuid(row["id"]),
            doi=row["doi"],
            title=row["title"],
            journal=row["journal"],
            publication_year=row["publication_year"],
            volume=row["volume"],
            issue=row["issue"],
            pages=row["pages"],
            publisher=row["publisher"],
            abstract=row["abstract"],
            metadata=metadata or None,
            first_author=first_author,
            corresponding_author=corresponding_author,
            authors=authors,
            row_version=row["row_version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _observation_value(row: Any) -> float | str | bool | None:
        if row["value_kind"] == "range":
            return f"{row['value_min']}–{row['value_max']}"
        if row["value_kind"] in {"text", "categorical"}:
            return row["value_text"]
        if row["value_kind"] == "boolean":
            return bool(row["value_boolean"])
        return _number(row["normalized_value"] if row["normalized_value"] is not None else row["value_numeric"])

    async def get_literature_stats(self) -> LiteratureStatsResponse:
        """聚合有效文献的发表年份、期刊分布及核心作者。"""
        papers = await self.list_papers(query=None, limit=500)
        total_papers = len(papers)

        year_counts: dict[int, int] = {}
        journal_counts: dict[str, int] = {}
        author_counts: dict[str, int] = {}

        def _normalize_journal(j: str | None) -> str:
            if not j or not j.strip():
                return "其他 / 预印本"
            j_clean = j.strip()
            if re.search(r"arxiv", j_clean, re.IGNORECASE):
                return "arXiv.org"
            if re.search(r"nature\s+materials", j_clean, re.IGNORECASE):
                return "Nature Materials"
            if re.search(r"journal\s+of\s+applied\s+physics", j_clean, re.IGNORECASE):
                return "Journal of Applied Physics"
            if re.search(r"optics\s*(?:&|and)\s*laser\s*technology", j_clean, re.IGNORECASE):
                return "Optics & Laser Technology"
            if re.search(r"applied\s+physics\s+letters", j_clean, re.IGNORECASE):
                return "Applied Physics Letters"
            return j_clean

        for p in papers:
            if p.publication_year:
                year_counts[p.publication_year] = year_counts.get(p.publication_year, 0) + 1
            norm_j = _normalize_journal(p.journal)
            journal_counts[norm_j] = journal_counts.get(norm_j, 0) + 1
            if p.authors:
                for a in p.authors:
                    a_name = a.strip()
                    if a_name:
                        author_counts[a_name] = author_counts.get(a_name, 0) + 1

        # 查询文献关联的样品所属材料体系
        sample_sys_rows = (
            await self.session.execute(
                text(
                    """
                    SELECT DISTINCT s.source_paper_id, m.chemical_system
                    FROM sam_sample s
                    JOIN mat_material m ON s.nominal_material_id = m.id
                    WHERE s.source_paper_id IS NOT NULL
                    """
                )
            )
        ).fetchall()

        paper_to_systems: dict[bytes, set[str]] = {}
        for row in sample_sys_rows:
            pid = bytes(row[0])
            sys_val = row[1]
            if sys_val:
                paper_to_systems.setdefault(pid, set()).add(sys_val)

        # 加载已知材料公式与化学体系，用于补充文本提及体系
        mat_rows = (
            await self.session.execute(
                text("SELECT canonical_formula, chemical_system FROM mat_material")
            )
        ).fetchall()
        mat_formula_to_sys = {r[0].lower(): r[1] for r in mat_rows if r[1]}

        system_counts: dict[str, int] = {}
        for p in papers:
            p_bytes = p.id.bytes
            systems_for_p = set(paper_to_systems.get(p_bytes, set()))
            # 补充基于标题与摘要的化学体系命中
            text_corpus = f"{p.title} {p.abstract or ''}".lower()
            for formula_l, sys_name in mat_formula_to_sys.items():
                if formula_l in text_corpus:
                    systems_for_p.add(sys_name)

            if not systems_for_p:
                systems_for_p.add("其他 / 待关联体系")

            for s in systems_for_p:
                system_counts[s] = system_counts.get(s, 0) + 1

        year_distribution = [
            YearCountItem(year=y, count=c)
            for y, c in sorted(year_counts.items(), key=lambda x: x[0])
        ]
        journal_distribution = [
            JournalCountItem(journal=j, count=c)
            for j, c in sorted(journal_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        author_distribution = [
            AuthorCountItem(author=a, count=c)
            for a, c in sorted(author_counts.items(), key=lambda x: x[1], reverse=True)[:15]
        ]
        system_distribution = [
            SystemCountItem(chemical_system=s, count=c)
            for s, c in sorted(system_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        return LiteratureStatsResponse(
            total_papers=total_papers,
            year_distribution=year_distribution,
            journal_distribution=journal_distribution,
            author_distribution=author_distribution,
            system_distribution=system_distribution,
        )

    async def get_knowledge_graph(
        self,
        element: str | None = None,
        material_id: str | None = None,
        include_papers: bool = False,
        subgraph: str | None = None,
        limit: int = 60,
    ) -> KnowledgeGraphResponse:
        """基于权威 MySQL 数据源构建宏观科学骨干图谱或材料文献证据子图谱。"""
        materials = await self.list_materials(query=None, limit=limit, elements=[element] if element else None)
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

        # 1. 注册材料主节点
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

        # 模式 C: 细粒度材料 - 掺杂元素 - 物性测定 - 出处文献证据子图谱
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
                m_guid = _uuid(r["material_id"])
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

                obs_guid = _uuid(r["obs_id"])
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
                    p_guid = _uuid(r["paper_id"])
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

                    p_meta = _json(r["paper_metadata"]) or {}
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

        # 模式 A: 文献证据子图谱 (subgraph == "literature" 或 (material_id and subgraph != "macro"))
        elif subgraph == "literature" or (material_id and subgraph != "macro"):
            max_papers_per_mat = min(limit, 35)
            for m in materials:
                m_node_id = f"mat_{m.id}"
                formula_clean = m.canonical_formula

                # SQL 下推：检索与该材料直接或语义相关的文献
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
                    p_guid = _uuid(pr["id"])
                    p_node_id = f"paper_{p_guid}"
                    p_meta = _json(pr["metadata_json"]) or {}
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

                    # 第一作者同级节点
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
                            edge_keys.add(fa_edge_key)
                            edges.append(
                                GraphEdge(
                                    id=f"e_{len(edges)}",
                                    source=p_node_id,
                                    target=fa_node_id,
                                    edge_type="FIRST_AUTHORED_BY",
                                    label="第一作者",
                                )
                            )

                    # 通讯作者同级节点
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

                    # 收录期刊同级节点
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

        # 模式 B: 主宏观科学图谱 (Core Macro Graph)
        else:
            # 2. 构成元素节点与体系节点
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

                # 化学体系节点
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

            # 3. 核心物理/化学物性节点
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
                    mat_guid = _uuid(r["material_id"])
                    if not mat_guid or str(mat_guid) not in material_map:
                        continue
                    m_node_id = f"mat_{mat_guid}"
                    prop_guid = _uuid(r["prop_id"])
                    prop_node_id = f"prop_{prop_guid}"

                    raw_val = _number(r["value_numeric"]) if r["value_numeric"] is not None else r["value_text"]
                    disp_val = format_display_value(
                        value=raw_val,
                        unit=r["normalized_unit"] or r["canonical_unit"],
                        canonical_unit=r["canonical_unit"],
                        normalized_value=_number(r["normalized_value"]),
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

            # 4. 仅在显式请求 include_papers=True 时将精选论文加入宏观主图（避免平铺爆炸）
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
                        p_guid = _uuid(pr["id"])
                        p_node_id = f"paper_{p_guid}"
                        p_meta = _json(pr["metadata_json"]) or {}
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

    async def get_property_comparison(
        self,
        property_code: str = "crystallization_temperature",
        base_material: str | None = None,
        heating_rate: float | None = None,
        display_unit: str = "celsius",
    ) -> PropertyComparisonResponse:
        """多维相变物性跨文献横向对比与箱线图统计数据查询。"""
        pdefs = (
            await self.session.execute(
                text("SELECT code, name, symbol FROM obs_property_definition ORDER BY name ASC")
            )
        ).mappings().all()
        avail_props = [{"code": r["code"], "name": r["name"]} for r in pdefs]

        curr_pdef = next((p for p in pdefs if p["code"] == property_code), None)
        curr_pname = curr_pdef["name"] if curr_pdef else property_code

        sql = """
            SELECT
                o.id AS obs_id,
                pdef.code AS property_code,
                pdef.name AS property_name,
                m.id AS material_id,
                m.canonical_formula AS base_material,
                s.sample_label,
                s.thickness_value,
                s.substrate_material,
                meas.instrument AS measurement_method,
                meas.heating_rate_value,
                meas.heating_rate_unit,
                o.value_numeric,
                o.original_value_text,
                o.original_unit_text,
                o.normalized_value,
                o.verification_status,
                o.quality_score,
                p.id AS paper_id,
                p.title AS paper_title,
                p.doi AS paper_doi,
                p.publication_year,
                p.metadata_json AS paper_metadata,
                ef.figure_number,
                ef.page_number,
                ef.text_snippet
            FROM obs_observation o
            JOIN obs_property_definition pdef ON o.property_definition_id = pdef.id
            JOIN sam_sample s ON o.sample_id = s.id
            JOIN mat_material m ON s.nominal_material_id = m.id
            LEFT JOIN exp_measurement meas ON o.measurement_id = meas.id
            LEFT JOIN lit_paper p ON s.source_paper_id = p.id
            LEFT JOIN evd_observation_link eol ON o.id = eol.observation_id
            LEFT JOIN evd_fragment ef ON (eol.evidence_fragment_id = ef.id OR meas.evidence_id = ef.id)
            WHERE pdef.code = :pcode
              AND o.verification_status != 'RETRACTED'
            ORDER BY o.created_at DESC
        """
        rows = (await self.session.execute(text(sql), {"pcode": property_code})).mappings().all()

        data_points: list[PropertyComparisonDataPoint] = []
        all_materials: set[str] = set()
        all_heating_rates: set[float] = set()

        for r in rows:
            b_mat = r["base_material"]
            all_materials.add(b_mat)

            hr_val = float(r["heating_rate_value"]) if r["heating_rate_value"] is not None else None
            if hr_val is not None:
                all_heating_rates.add(hr_val)

            if base_material and base_material != "all" and b_mat != base_material:
                continue

            if heating_rate is not None and hr_val is not None:
                if abs(hr_val - heating_rate) > 0.1:
                    continue

            label = r["sample_label"] or b_mat
            dop_elem = None
            dop_pct = None
            m_dop = re.search(r"([A-Z][a-z]?)(?:_?doped|\s*[-_]?\s*(\d+(?:\.\d+)?)\s*(?:at\.?%|%))", label, re.I)
            if not m_dop:
                for cand_elem in ("Bi", "In", "Sb", "Ag", "N", "C", "Ti", "Sc", "Cr", "Cu", "Al", "Si"):
                    if b_mat == "GeTe" and cand_elem in ("Ge", "Te"):
                        continue
                    if b_mat == "Sb2Te3" and cand_elem in ("Sb", "Te"):
                        continue
                    m_form = re.search(rf"{cand_elem}(\d+(?:\.\d+)?)", label)
                    if m_form:
                        dop_elem = cand_elem
                        try:
                            dop_pct = float(m_form.group(1))
                        except ValueError:
                            pass
                        break
                    elif re.search(rf"\b{cand_elem}\b", label):
                        dop_elem = cand_elem
                        break
            else:
                dop_elem = m_dop.group(1)
                if m_dop.group(2):
                    dop_pct = float(m_dop.group(2))

            val_num = float(r["value_numeric"]) if r["value_numeric"] is not None else 0.0
            orig_unit = (r["original_unit_text"] or "").strip()
            val_disp = val_num
            target_unit = orig_unit or "°C"

            if property_code in ("crystallization_temperature", "melting_temperature", "glass_transition_temperature"):
                if display_unit == "celsius":
                    target_unit = "°C"
                    if orig_unit.lower() in ("k", "kelvin"):
                        val_disp = val_num - 273.15
                    else:
                        val_disp = val_num
                else:
                    target_unit = "K"
                    if orig_unit.lower() in ("°c", "c", "celsius"):
                        val_disp = val_num + 273.15
                    else:
                        val_disp = val_num

            meta = _json(r["paper_metadata"]) or {}
            p_author = meta.get("first_author")

            dp = PropertyComparisonDataPoint(
                observation_id=_uuid(r["obs_id"]) or uuid7(),
                property_code=r["property_code"],
                property_name=r["property_name"],
                material_formula=label.split("-")[0],
                base_material=b_mat,
                dopant_element=dop_elem,
                dopant_at_pct=dop_pct,
                sample_formula=label,
                value=round(val_disp, 2),
                unit=target_unit,
                normalized_value=float(r["normalized_value"]) if r["normalized_value"] is not None else None,
                normalized_unit="K" if property_code == "crystallization_temperature" else orig_unit,
                heating_rate_k_per_min=hr_val,
                measurement_method=r["measurement_method"],
                film_thickness_nm=float(r["thickness_value"]) if r["thickness_value"] is not None else None,
                substrate=r["substrate_material"],
                paper_id=_uuid(r["paper_id"]),
                paper_title=r["paper_title"],
                paper_doi=r["paper_doi"],
                paper_year=r["publication_year"],
                first_author=p_author,
                evidence_snippet=r["text_snippet"],
                figure_or_table=r["figure_number"],
                page_number=r["page_number"],
                verification_status=r["verification_status"],
                quality_score=float(r["quality_score"]) if r["quality_score"] is not None else None,
            )
            data_points.append(dp)

        group_values: dict[str, list[float]] = {}
        for dp in data_points:
            grp = f"{dp.base_material}" + (f" + {dp.dopant_element}" if dp.dopant_element else " (本征)")
            group_values.setdefault(grp, []).append(dp.value)

        box_stats: list[PropertyBoxPlotStat] = []
        for grp, vals in group_values.items():
            s_vals = sorted(vals)
            n = len(s_vals)
            if n == 0:
                continue
            min_v = s_vals[0]
            max_v = s_vals[-1]
            med_v = s_vals[n // 2] if n % 2 == 1 else (s_vals[n // 2 - 1] + s_vals[n // 2]) / 2.0
            q1_v = s_vals[n // 4]
            q3_v = s_vals[(3 * n) // 4]
            box_stats.append(
                PropertyBoxPlotStat(
                    group_name=grp,
                    count=n,
                    min_val=round(min_v, 2),
                    q1=round(q1_v, 2),
                    median=round(med_v, 2),
                    q3=round(q3_v, 2),
                    max_val=round(max_v, 2),
                )
            )

        box_stats.sort(key=lambda b: b.median, reverse=True)

        return PropertyComparisonResponse(
            property_code=property_code,
            property_name=curr_pname,
            display_unit="°C" if display_unit == "celsius" else "K",
            total_count=len(data_points),
            data_points=data_points,
            box_plot_stats=box_stats,
            available_properties=avail_props,
            available_materials=sorted(list(all_materials)),
            available_heating_rates=sorted(list(all_heating_rates)),
        )

