import json
import re
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from app.domain.normalization import format_display_value
from app.models.batch_upload import (
    BatchIngestItem,
    BatchIngestRequest,
    BatchIngestResponse,
    ConflictObservationItem,
    ObservationConflictGroup,
)
from app.models.config import AppConfigRead, AppConfigUpdate
from app.models.literature import PaperCreate, PaperRead
from app.models.material import MaterialCreate, MaterialRead
from app.models.mvp import DashboardRead, ObservationListItem, PropertyOption
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


VALID_ELEMENTS: set[str] = {
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
    "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca",
    "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
    "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Y", "Zr",
    "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn",
    "Sb", "Te", "I", "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd",
    "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb",
    "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg",
    "Tl", "Pb", "Bi", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Th",
    "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm",
    "Md", "No", "Lr", "Rf", "Db", "Sg", "Bh", "Hs", "Mt", "Ds",
    "Rg", "Cn", "Nh", "Fl", "Mc", "Lv", "Ts", "Og",
}


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
        self, query: str | None, limit: int, elements: list[str] | None = None
    ) -> list[MaterialRead]:
        conditions = [
            "canonical_formula NOT LIKE 'CandReqId%'",
            "canonical_formula NOT LIKE 'ReqIdMat%'",
            "canonical_formula NOT LIKE 'AcceptanceMat%'",
        ]
        params: dict[str, Any] = {"limit": limit}

        if query:
            conditions.append("(canonical_formula LIKE :query OR chemical_system LIKE :query OR name LIKE :query)")
            params["query"] = f"%{query}%"

        if elements:
            for idx, el in enumerate(elements):
                el_clean = el.strip()
                if not el_clean:
                    continue
                sys_param = f"elem_sys_{idx}"
                form_param = f"elem_form_{idx}"
                conditions.append(
                    f"(CONCAT('-', chemical_system, '-') LIKE :{sys_param} OR canonical_formula LIKE :{form_param})"
                )
                params[sys_param] = f"%-{el_clean}-%"
                params[form_param] = f"%{el_clean}%"

        where = f"WHERE {' AND '.join(conditions)}"
        rows = (
            (
                await self.session.execute(
                    text(
                        f"""
                    SELECT id, canonical_formula, reduced_formula, chemical_system,
                           material_family_term_id, name, description, row_version, created_at, updated_at
                    FROM mat_material {where}
                    ORDER BY updated_at DESC, id DESC LIMIT :limit
                    """
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
        return [self._material(row) for row in rows]

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
        mat = self._material(row)
        mat.aliases = list(alias_rows)
        return mat

    async def create_material(self, body: MaterialCreate) -> MaterialRead:
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
                    "canonical_formula": body.canonical_formula,
                    "reduced_formula": body.reduced_formula,
                    "chemical_system": body.chemical_system,
                    "family_id": body.material_family_term_id.bytes if body.material_family_term_id else None,
                    "name": body.name,
                    "description": body.description,
                },
            )
            for alias in dict.fromkeys(body.aliases):
                await self.session.execute(
                    text("INSERT INTO mat_material_alias (id, material_id, alias) VALUES (:id, :material_id, :alias)"),
                    {"id": uuid7().bytes, "material_id": material_id.bytes, "alias": alias},
                )
            await self._outbox(event_id, "Material", material_id, "MaterialCreated", {"id": str(material_id)})
        created = await self.get_material(str(material_id))
        assert created is not None
        created.aliases = body.aliases
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
                meta = item.metadata or {}
                first_author = item.first_author.strip() if item.first_author else None
                corresponding_author = item.corresponding_author.strip() if item.corresponding_author else None
                authors = [first_author] if first_author else []
                if corresponding_author and corresponding_author not in authors:
                    authors.append(corresponding_author)

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

                # 插入作者关联
                for order, author_name in enumerate(authors, start=1):
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
        material_rows = (
            (
                await self.session.execute(
                    text(
                        """
                    SELECT id, canonical_formula, chemical_system FROM mat_material
                    WHERE canonical_formula LIKE :query OR chemical_system LIKE :query OR name LIKE :query
                    LIMIT :limit
                    """
                    ),
                    {"query": pattern, "limit": limit},
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
        return MaterialRead(
            id=_uuid(row["id"]),
            canonical_formula=row["canonical_formula"],
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
