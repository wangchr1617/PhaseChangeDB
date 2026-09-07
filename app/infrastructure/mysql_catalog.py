import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

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

    async def list_materials(self, query: str | None, limit: int) -> list[MaterialRead]:
        where = ""
        params: dict[str, Any] = {"limit": limit}
        if query:
            where = "WHERE canonical_formula LIKE :query OR chemical_system LIKE :query OR name LIKE :query"
            params["query"] = f"%{query}%"
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

    async def get_material(self, material_id: str) -> MaterialRead | None:
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
                    {"id": UUID(material_id).bytes},
                )
            )
            .mappings()
            .first()
        )
        return self._material(row) if row else None

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

    async def list_papers(self, query: str | None, limit: int) -> list[PaperRead]:
        where = ""
        params: dict[str, Any] = {"limit": limit}
        if query:
            where = "WHERE title LIKE :query OR doi LIKE :query OR journal LIKE :query"
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
        return [self._paper(row) for row in rows]

    async def create_paper(self, body: PaperCreate) -> PaperRead:
        paper_id = uuid7()
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
                    "metadata": json.dumps(body.metadata, ensure_ascii=False) if body.metadata else None,
                },
            )
            await self._outbox(uuid7(), "Paper", paper_id, "PaperCreated", {"id": str(paper_id)})
        rows = await self.list_papers(body.title, 1)
        return rows[0]

    async def list_observations(self, limit: int) -> list[ObservationListItem]:
        rows = (
            (
                await self.session.execute(
                    text(
                        """
                    SELECT o.id, m.id AS material_id, m.canonical_formula AS material_formula,
                           p.code AS property_code, p.name AS property_name,
                           o.value_kind, o.value_numeric, o.value_min, o.value_max,
                           o.value_text, o.value_boolean, o.normalized_value,
                           COALESCE(u.code, o.original_unit_text) AS unit,
                           o.verification_status, o.quality_score, o.created_at
                    FROM obs_observation o
                    JOIN obs_property_definition p ON p.id = o.property_definition_id
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
        paper_rows = (
            (
                await self.session.execute(
                    text(
                        """
                    SELECT id, title, journal, publication_year FROM lit_paper
                    WHERE title LIKE :query OR doi LIKE :query OR abstract LIKE :query
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
    def _paper(row: Any) -> PaperRead:
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
            metadata=_json(row["metadata_json"]),
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
