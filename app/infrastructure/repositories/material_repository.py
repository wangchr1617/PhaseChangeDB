"""PhaseChangeDB 材料领域 MySQL 仓储实现。

负责材料目录检索、周期表元素统计、变体样品查询、冲突数据检测与材料创建。
"""

from __future__ import annotations

import re
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
from app.infrastructure.repositories.base import BaseMySQLRepository, to_number, to_uuid
from app.models.batch_upload import ConflictObservationItem, ObservationConflictGroup
from app.models.material import MaterialCreate, MaterialRead, MaterialVariantRead, VariantObservationRead


class MySQLMaterialRepository(BaseMySQLRepository):
    """材料领域 MySQL 仓储。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

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

        mids = [r["id"] for r in rows]
        placeholders = ", ".join([f":mid_{i}" for i in range(len(mids))])
        mparams = {f"mid_{i}": mid for i, mid in enumerate(mids)}

        alias_sql = f"SELECT material_id, alias FROM mat_material_alias WHERE material_id IN ({placeholders})"
        alias_rows = (await self.session.execute(text(alias_sql), mparams)).mappings().all()
        aliases_by_mat: dict[bytes, list[str]] = {}
        for ar in alias_rows:
            aliases_by_mat.setdefault(bytes(ar["material_id"]), []).append(ar["alias"])

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

            num_val = to_number(sr["normalized_value"] if sr["normalized_value"] is not None else sr["value_numeric"])
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
                raw_v = to_number(obs_r["value_numeric"]) if obs_r["value_numeric"] is not None else obs_r["value_text"]
                disp_v = format_display_value(
                    value=raw_v,
                    unit=obs_r["original_unit_text"] or obs_r["canonical_unit"],
                    canonical_unit=obs_r["canonical_unit"],
                    normalized_value=to_number(obs_r["normalized_value"]),
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
            await self.outbox(event_id, "Material", material_id, "MaterialCreated", {"id": str(material_id)})
        created = await self.get_material(str(material_id))
        assert created is not None
        return created

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

        pids = [r["paper_id"] for r in rows if r["paper_id"]]
        authors_map = await self._load_authors_for_papers(pids) if pids else {}

        obs_seen: set[bytes] = set()
        unique_rows: list[dict[str, Any]] = []
        for r in rows:
            oid = bytes(r["id"])
            if oid not in obs_seen:
                obs_seen.add(oid)
                unique_rows.append(dict(r))

        prop_groups: dict[str, list[dict[str, Any]]] = {}
        for r in unique_rows:
            prop_groups.setdefault(r["property_code"], []).append(r)

        conflict_groups: list[ObservationConflictGroup] = []

        for p_code, obs_list in prop_groups.items():
            has_dispute = any(o["verification_status"] == "DISPUTED" for o in obs_list)

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
            normalized_value=to_number(row["normalized_value"]),
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
            quality_score=to_number(row["quality_score"]),
        )

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

    @staticmethod
    def _material(row: Any) -> MaterialRead:
        c_form = row["canonical_formula"]
        elems = extract_elements(c_form)
        return MaterialRead(
            id=to_uuid(row["id"]),
            canonical_formula=c_form,
            reduced_formula=row["reduced_formula"],
            chemical_system=row["chemical_system"],
            material_family_term_id=to_uuid(row["material_family_term_id"]),
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
    def _observation_value(row: Any) -> float | str | bool | None:
        if row["value_kind"] == "range":
            return f"{row['value_min']}–{row['value_max']}"
        if row["value_kind"] in {"text", "categorical"}:
            return row["value_text"]
        if row["value_kind"] == "boolean":
            return bool(row["value_boolean"])
        return to_number(row["normalized_value"] if row["normalized_value"] is not None else row["value_numeric"])
