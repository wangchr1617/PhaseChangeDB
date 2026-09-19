"""PhaseChangeDB 系统配置、全局概览与基础检索 MySQL 仓储。"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.material_normalizer import normalize_formula
from app.infrastructure.repositories.base import BaseMySQLRepository, to_uuid
from app.models.config import AppConfigRead, AppConfigUpdate
from app.models.mvp import DashboardRead
from app.models.search import SearchHit


class MySQLConfigRepository(BaseMySQLRepository):
    """系统配置、概览统计与跨领域模糊检索仓储。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

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
                id=to_uuid(row["id"]),
                title=row["canonical_formula"],
                snippet=row["chemical_system"],
                score=None,
            )
            for row in material_rows
        ]
        hits.extend(
            [
                SearchHit(
                    target="papers",
                    id=to_uuid(row["id"]),
                    title=row["title"],
                    snippet=" · ".join(str(value) for value in (row["journal"], row["publication_year"]) if value),
                    score=None,
                )
                for row in paper_rows
            ]
        )
        return hits[:limit]
