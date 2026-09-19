"""PhaseChangeDB 观测记录与物性横向对比分析 MySQL 仓储实现。

负责物性定义查询、观测记录增删查、跨文献物性横向对比与四分位数箱线图统计计算。
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from app.domain.normalization import format_display_value
from app.infrastructure.repositories.base import BaseMySQLRepository, to_json, to_number, to_uuid
from app.models.mvp import (
    ObservationListItem,
    PropertyBoxPlotStat,
    PropertyComparisonDataPoint,
    PropertyComparisonResponse,
    PropertyOption,
)
from app.models.observation import ObservationCreate, ObservationRead


class MySQLObservationRepository(BaseMySQLRepository):
    """观测记录与物性分析 MySQL 仓储。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_observations(self, limit: int = 50) -> list[ObservationListItem]:
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
                id=to_uuid(row["id"]),
                material_id=to_uuid(row["material_id"]),
                material_formula=row["material_formula"],
                property_code=row["property_code"],
                property_name=row["property_name"],
                value=self._observation_value(row),
                unit=row["unit"],
                normalized_value=to_number(row["normalized_value"]),
                normalized_unit=row["normalized_unit_code"],
                display_value=format_display_value(
                    value=row["value_numeric"] if row["value_kind"] == "scalar" else self._observation_value(row),
                    unit=row["original_unit_text"] or row["unit"],
                    canonical_unit=row["canonical_unit"],
                    normalized_value=row["normalized_value"],
                ),
                verification_status=row["verification_status"],
                quality_score=to_number(row["quality_score"]),
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
            await self.outbox(
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
                id=to_uuid(row["id"]), code=row["code"], name=row["name"], canonical_unit=row["canonical_unit"]
            )
            for row in rows
        ]

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

            meta = to_json(r["paper_metadata"]) or {}
            p_author = meta.get("first_author")

            dp = PropertyComparisonDataPoint(
                observation_id=to_uuid(r["obs_id"]) or uuid7(),
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
                paper_id=to_uuid(r["paper_id"]),
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

    @staticmethod
    def _observation_value(row: Any) -> float | str | bool | None:
        if row["value_kind"] == "range":
            return f"{row['value_min']}–{row['value_max']}"
        if row["value_kind"] in {"text", "categorical"}:
            return row["value_text"]
        if row["value_kind"] == "boolean":
            return bool(row["value_boolean"])
        return to_number(row["normalized_value"] if row["normalized_value"] is not None else row["value_numeric"])
