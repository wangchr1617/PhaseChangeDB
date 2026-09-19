"""PhaseChangeDB 文献领域 MySQL 仓储实现。

负责学术论文查询、作者多对多映射加载、单篇录入、批量导入与文献统计分布。
"""

from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from app.infrastructure.repositories.base import BaseMySQLRepository, to_json, to_uuid
from app.models.batch_upload import (
    AuthorCountItem,
    BatchIngestItem,
    BatchIngestRequest,
    BatchIngestResponse,
    JournalCountItem,
    LiteratureStatsResponse,
    SystemCountItem,
    YearCountItem,
)
from app.models.literature import PaperCreate, PaperRead


class MySQLLiteratureRepository(BaseMySQLRepository):
    """文献领域 MySQL 仓储。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

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

    async def list_papers(self, query: str | None = None, limit: int = 50) -> list[PaperRead]:
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
            await self.outbox(uuid7(), "Paper", paper_id, "PaperCreated", {"id": str(paper_id)})
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

                paper_id = uuid7()
                meta = dict(item.metadata or {})
                first_author = item.first_author.strip() if item.first_author else None
                corresponding_author = item.corresponding_author.strip() if item.corresponding_author else None
                authors = [first_author] if first_author else []
                if corresponding_author and corresponding_author not in authors:
                    authors.append(corresponding_author)

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

                await self.outbox(uuid7(), "Paper", paper_id, "PaperCreated", {"id": str(paper_id)})
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

    async def get_literature_stats(self) -> LiteratureStatsResponse:
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

    @staticmethod
    def _paper(row: Any, authors_info: list[dict[str, Any]] | None = None) -> PaperRead:
        metadata = to_json(row["metadata_json"]) or {}
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
            id=to_uuid(row["id"]),
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
