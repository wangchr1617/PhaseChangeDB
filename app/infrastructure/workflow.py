from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from app.domain.workflow import (
    DomainConflictError,
    EntityNotFoundError,
    PreconditionFailedError,
    resolve_and_validate_normalization,
    validate_manual_intake_verification_status,
    validate_review_transition,
    validate_sha256_hex,
    validate_storage_uri,
)
from app.models.common import VerificationStatus
from app.models.workflow import (
    ObservationDetailRead,
    ObservationReviewRequest,
    ObservationReviewResponse,
    WorkflowIntakeRequest,
    WorkflowIntakeResponse,
)


def _uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return UUID(bytes=bytes(value))
    if isinstance(value, str):
        return UUID(value)
    return None


def _number(value: Decimal | int | float | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _json_serialize(obj: Any) -> Any:
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, (datetime,)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (bytes, bytearray, memoryview)):
        return bytes(obj).hex()
    if isinstance(obj, dict):
        return {k: _json_serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_serialize(item) for item in obj]
    return obj


def json_dumps(data: Any) -> str:
    return json.dumps(_json_serialize(data), ensure_ascii=False)


class MySQLWorkflowRepository:
    """负责核心闭环工作流在 MySQL 中的事务与持久化。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def intake(
        self,
        body: WorkflowIntakeRequest,
        idempotency_key: str,
        request_path: str,
        request_id: str | None,
    ) -> WorkflowIntakeResponse:
        """单事务完成 Paper, Artifact, Document, Material, Sample, Evidence, Measurement, Observation 录入。"""
        # 1. 校验输入规则
        validate_storage_uri(body.document.storage_uri)
        validate_sha256_hex(body.document.sha256)
        validate_manual_intake_verification_status(body.observation.verification_status)

        # 2. 计算载荷哈希用于幂等比对
        request_raw = body.model_dump(mode="json")
        request_hash = hashlib.sha256(json.dumps(request_raw, sort_keys=True).encode("utf-8")).hexdigest()

        tx_mgr = self.session.begin_nested() if self.session.in_transaction() else self.session.begin()
        async with tx_mgr:
            # 3. 检查幂等记录 (FOR UPDATE)
            existing_key_row = (
                (
                    await self.session.execute(
                        text(
                            """
                            SELECT request_hash, response_status, response_json
                            FROM sys_idempotency_key
                            WHERE idempotency_key = :key FOR UPDATE
                            """
                        ),
                        {"key": idempotency_key},
                    )
                )
                .mappings()
                .first()
            )

            if existing_key_row:
                if existing_key_row["request_hash"] == request_hash:
                    # 相同请求重复提交，直接返回之前持久化的响应
                    cached_data = existing_key_row["response_json"]
                    if isinstance(cached_data, str):
                        cached_data = json.loads(cached_data)
                    return WorkflowIntakeResponse(**cached_data)
                else:
                    raise DomainConflictError("Idempotency-Key 冲突：相同的 key 提交了不同的请求载荷。")

            # 4. 文献记录 (Paper)
            if body.paper_id:
                paper_id = body.paper_id
                paper_check = (
                    await self.session.execute(
                        text("SELECT id FROM lit_paper WHERE id = :id"),
                        {"id": paper_id.bytes},
                    )
                ).first()
                if not paper_check:
                    raise EntityNotFoundError(f"指定的 paper_id {paper_id} 不存在")
            else:
                assert body.paper is not None
                paper_id = uuid7()
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
                        "doi": body.paper.doi,
                        "title": body.paper.title,
                        "journal": body.paper.journal,
                        "year": body.paper.publication_year,
                        "volume": body.paper.volume,
                        "issue": body.paper.issue,
                        "pages": body.paper.pages,
                        "publisher": body.paper.publisher,
                        "abstract": body.paper.abstract,
                        "metadata": json_dumps(body.paper.metadata) if body.paper.metadata else None,
                    },
                )
                await self._outbox(
                    event_id=uuid7(),
                    aggregate_type="Paper",
                    aggregate_id=paper_id,
                    event_type="PaperCreated",
                    payload={"id": str(paper_id), "title": body.paper.title},
                )

            # 5. 文档制品 (Artifact) - 相同 SHA-256 复用 Artifact
            artifact_row = (
                (
                    await self.session.execute(
                        text("SELECT id FROM sys_artifact WHERE sha256_hex = :sha256"),
                        {"sha256": body.document.sha256},
                    )
                )
                .mappings()
                .first()
            )

            if artifact_row:
                artifact_id = _uuid(artifact_row["id"])
                assert artifact_id is not None
            else:
                artifact_id = uuid7()
                await self.session.execute(
                    text(
                        """
                        INSERT INTO sys_artifact (id, storage_uri, sha256_hex, mime_type)
                        VALUES (:id, :storage_uri, :sha256_hex, 'application/pdf')
                        """
                    ),
                    {
                        "id": artifact_id.bytes,
                        "storage_uri": body.document.storage_uri,
                        "sha256_hex": body.document.sha256,
                    },
                )

            # 6. 登记文献文档 (lit_document)
            document_id = uuid7()
            await self.session.execute(
                text(
                    """
                    INSERT INTO lit_document
                      (id, paper_id, document_type, artifact_id, parse_status, checksum_sha256_hex)
                    VALUES (:id, :paper_id, :document_type, :artifact_id, 'parsed', :checksum)
                    """
                ),
                {
                    "id": document_id.bytes,
                    "paper_id": paper_id.bytes,
                    "document_type": body.document.document_type,
                    "artifact_id": artifact_id.bytes,
                    "checksum": body.document.sha256,
                },
            )

            # 7. 材料记录 (Material)
            if body.material_id:
                material_id = body.material_id
                mat_check = (
                    await self.session.execute(
                        text("SELECT id FROM mat_material WHERE id = :id"),
                        {"id": material_id.bytes},
                    )
                ).first()
                if not mat_check:
                    raise EntityNotFoundError(f"指定的 material_id {material_id} 不存在")
            else:
                assert body.material is not None
                existing_mat = (
                    await self.session.execute(
                        text(
                            """
                            SELECT id FROM mat_material
                            WHERE canonical_formula = :formula AND chemical_system = :system
                            """
                        ),
                        {
                            "formula": body.material.canonical_formula,
                            "system": body.material.chemical_system,
                        },
                    )
                ).mappings().first()

                if existing_mat:
                    material_id = _uuid(existing_mat["id"])
                    assert material_id is not None
                else:
                    material_id = uuid7()
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
                            "canonical_formula": body.material.canonical_formula,
                            "reduced_formula": body.material.reduced_formula,
                            "chemical_system": body.material.chemical_system,
                            "family_id": body.material.material_family_term_id.bytes
                            if body.material.material_family_term_id
                            else None,
                            "name": body.material.name,
                            "description": body.material.description,
                        },
                    )
                    for alias in dict.fromkeys(body.material.aliases):
                        await self.session.execute(
                            text(
                                "INSERT INTO mat_material_alias (id, material_id, alias) "
                                "VALUES (:id, :material_id, :alias)"
                            ),
                            {"id": uuid7().bytes, "material_id": material_id.bytes, "alias": alias},
                        )
                    await self._outbox(
                        event_id=uuid7(),
                        aggregate_type="Material",
                        aggregate_id=material_id,
                        event_type="MaterialCreated",
                        payload={"id": str(material_id), "formula": body.material.canonical_formula},
                    )

            # 8. 实体样品 (Sample)
            sample_id = uuid7()
            await self.session.execute(
                text(
                    """
                    INSERT INTO sam_sample
                      (id, nominal_material_id, source_paper_id, sample_label,
                       sample_type_term_id, thickness_value, thickness_unit,
                       substrate_material, description, row_version)
                    VALUES (:id, :material_id, :paper_id, :sample_label,
                            :sample_type_term_id, :thickness_value, :thickness_unit,
                            :substrate_material, :description, 1)
                    """
                ),
                {
                    "id": sample_id.bytes,
                    "material_id": material_id.bytes,
                    "paper_id": paper_id.bytes,
                    "sample_label": body.sample.sample_label,
                    "sample_type_term_id": body.sample.sample_type_term_id.bytes,
                    "thickness_value": body.sample.thickness_value,
                    "thickness_unit": body.sample.thickness_unit,
                    "substrate_material": body.sample.substrate_material,
                    "description": body.sample.description,
                },
            )

            # 9. 证据片段 (evd_fragment)
            evidence_id = uuid7()
            await self.session.execute(
                text(
                    """
                    INSERT INTO evd_fragment
                      (id, paper_id, document_id, fragment_type, page_number,
                       section, figure_number, table_number, text_snippet, artifact_id)
                    VALUES (:id, :paper_id, :document_id, :fragment_type, :page_number,
                            :section, :figure_number, :table_number, :text_snippet, :artifact_id)
                    """
                ),
                {
                    "id": evidence_id.bytes,
                    "paper_id": paper_id.bytes,
                    "document_id": document_id.bytes,
                    "fragment_type": body.evidence.fragment_type,
                    "page_number": body.evidence.page_number,
                    "section": body.evidence.section,
                    "figure_number": body.evidence.figure_number,
                    "table_number": body.evidence.table_number,
                    "text_snippet": body.evidence.text_snippet,
                    "artifact_id": artifact_id.bytes,
                },
            )

            # 10. 实验测量 (Measurement)
            measurement_id = uuid7()
            await self.session.execute(
                text(
                    """
                    INSERT INTO exp_measurement
                      (id, sample_id, measurement_type_term_id, instrument,
                       temperature_value, temperature_unit, source_paper_id, evidence_id)
                    VALUES (:id, :sample_id, :measurement_type_term_id, :instrument,
                            :temperature_value, :temperature_unit, :paper_id, :evidence_id)
                    """
                ),
                {
                    "id": measurement_id.bytes,
                    "sample_id": sample_id.bytes,
                    "measurement_type_term_id": body.measurement.measurement_type_term_id.bytes,
                    "instrument": body.measurement.instrument,
                    "temperature_value": body.measurement.temperature_value,
                    "temperature_unit": body.measurement.temperature_unit,
                    "paper_id": paper_id.bytes,
                    "evidence_id": evidence_id.bytes,
                },
            )

            # 11. 科学观测 (Observation)
            observation_id = uuid7()
            created_at = datetime.now(UTC)

            # 查询属性定义及规范单位
            prop_row = (
                await self.session.execute(
                    text(
                        """
                        SELECT p.id, p.canonical_unit_term_id, u.code AS canonical_unit_code
                        FROM obs_property_definition p
                        LEFT JOIN ont_term u ON p.canonical_unit_term_id = u.id
                        WHERE p.id = :id
                        """
                    ),
                    {"id": body.observation.property_definition_id.bytes},
                )
            ).mappings().first()
            if not prop_row:
                raise EntityNotFoundError(
                    f"指定的 property_definition_id {body.observation.property_definition_id} 不存在"
                )

            canonical_unit_id = (
                UUID(bytes=bytes(prop_row["canonical_unit_term_id"]))
                if prop_row["canonical_unit_term_id"]
                else None
            )
            canonical_unit_symbol = prop_row["canonical_unit_code"]

            # 严格单位与归一化校验（禁止隐式伪造回退到 value_numeric）
            norm_val, norm_unit_id = resolve_and_validate_normalization(
                original_value_text=body.observation.original_value_text,
                original_unit_text=body.observation.original_unit_text,
                value_numeric=body.observation.value_numeric,
                normalized_value=body.observation.normalized_value,
                normalized_unit_term_id=body.observation.normalized_unit_term_id,
                canonical_unit_term_id=canonical_unit_id,
                canonical_unit_symbol=canonical_unit_symbol,
            )

            val_numeric_dec = (
                Decimal(str(body.observation.value_numeric))
                if body.observation.value_numeric is not None
                else None
            )
            val_min_dec = (
                Decimal(str(body.observation.value_min))
                if body.observation.value_min is not None
                else None
            )
            val_max_dec = (
                Decimal(str(body.observation.value_max))
                if body.observation.value_max is not None
                else None
            )
            unc_lower_dec = (
                Decimal(str(body.observation.uncertainty_lower))
                if body.observation.uncertainty_lower is not None
                else None
            )
            unc_upper_dec = (
                Decimal(str(body.observation.uncertainty_upper))
                if body.observation.uncertainty_upper is not None
                else None
            )
            cond_temp_dec = (
                Decimal(str(body.observation.condition_temperature_value))
                if body.observation.condition_temperature_value is not None
                else None
            )

            await self.session.execute(
                text(
                    """
                    INSERT INTO obs_observation (
                      id, sample_id, property_definition_id, measurement_id,
                      value_kind, value_numeric, value_min, value_max, value_text, value_boolean,
                      original_value_text, original_unit_text, normalized_value, normalized_unit_term_id,
                      uncertainty_lower, uncertainty_upper, condition_temperature_value, condition_temperature_unit,
                      quality_score, verification_status, row_version, created_at, updated_at
                    ) VALUES (
                      :id, :sample_id, :property_definition_id, :measurement_id,
                      :value_kind, :value_numeric, :value_min, :value_max, :value_text, :value_boolean,
                      :original_value_text, :original_unit_text, :normalized_value, :normalized_unit_term_id,
                      :uncertainty_lower, :uncertainty_upper, :condition_temperature_value, :condition_temperature_unit,
                      :quality_score, :verification_status, 1, :created_at, :created_at
                    )
                    """
                ),
                {
                    "id": observation_id.bytes,
                    "sample_id": sample_id.bytes,
                    "property_definition_id": body.observation.property_definition_id.bytes,
                    "measurement_id": measurement_id.bytes,
                    "value_kind": body.observation.value_kind.value,
                    "value_numeric": val_numeric_dec,
                    "value_min": val_min_dec,
                    "value_max": val_max_dec,
                    "value_text": body.observation.value_text,
                    "value_boolean": body.observation.value_boolean,
                    "original_value_text": body.observation.original_value_text,
                    "original_unit_text": body.observation.original_unit_text,
                    "normalized_value": norm_val,
                    "normalized_unit_term_id": norm_unit_id.bytes if norm_unit_id else None,
                    "uncertainty_lower": unc_lower_dec,
                    "uncertainty_upper": unc_upper_dec,
                    "condition_temperature_value": cond_temp_dec,
                    "condition_temperature_unit": body.observation.condition_temperature_unit,
                    "quality_score": body.observation.quality_score,
                    "verification_status": body.observation.verification_status.value,
                    "created_at": created_at,
                },
            )

            # 12. 关联观测与证据 (evd_observation_link)
            await self.session.execute(
                text(
                    """
                    INSERT INTO evd_observation_link
                      (observation_id, evidence_fragment_id, evidence_role, confidence)
                    VALUES (:obs_id, :evd_id, 'primary', :confidence)
                    """
                ),
                {
                    "obs_id": observation_id.bytes,
                    "evd_id": evidence_id.bytes,
                    "confidence": body.observation.quality_score or 1.0,
                },
            )

            # 13. 审计日志 (sys_audit_log)
            await self._audit(
                action="observation_intake",
                entity_type="Observation",
                entity_id=observation_id,
                before_json=None,
                after_json={
                    "status": body.observation.verification_status.value,
                    "property_definition_id": str(body.observation.property_definition_id),
                    "material_id": str(material_id),
                    "paper_id": str(paper_id),
                    "row_version": 1,
                },
                request_id=request_id,
            )

            # 14. Outbox 事件 (sys_outbox_event)
            await self._outbox(
                event_id=uuid7(),
                aggregate_type="Observation",
                aggregate_id=observation_id,
                event_type="ObservationCreated",
                payload={
                    "id": str(observation_id),
                    "material_id": str(material_id),
                    "sample_id": str(sample_id),
                    "property_id": str(body.observation.property_definition_id),
                    "status": body.observation.verification_status.value,
                    "row_version": 1,
                },
            )

            # 15. 构建响应
            response = WorkflowIntakeResponse(
                observation_id=observation_id,
                paper_id=paper_id,
                document_id=document_id,
                artifact_id=artifact_id,
                material_id=material_id,
                sample_id=sample_id,
                measurement_id=measurement_id,
                evidence_id=evidence_id,
                verification_status=body.observation.verification_status,
                row_version=1,
                created_at=created_at,
            )

            # 16. 持久化幂等记录 (同一事务提交)
            await self.session.execute(
                text(
                    """
                    INSERT INTO sys_idempotency_key
                      (idempotency_key, request_path, request_hash, response_status, response_json)
                    VALUES (:key, :path, :hash, 201, :json)
                    """
                ),
                {
                    "key": idempotency_key,
                    "path": request_path,
                    "hash": request_hash,
                    "json": json_dumps(response.model_dump(mode="json")),
                },
            )

            return response

    async def get_observation_detail(self, observation_id: UUID) -> ObservationDetailRead:
        """获取观测详情及其完整上下文（材料、文献、样品、测量、证据来源）。"""
        obs_row = (
            (
                await self.session.execute(
                    text(
                        """
                        SELECT
                          o.id, o.verification_status, o.row_version, o.created_at, o.updated_at,
                          o.value_kind, o.value_numeric, o.value_min, o.value_max, o.value_text, o.value_boolean,
                          o.original_value_text, o.original_unit_text, o.normalized_value,
                          o.uncertainty_lower, o.uncertainty_upper,
                          o.condition_temperature_value, o.condition_temperature_unit,
                          o.quality_score,
                          p.code AS property_code, p.name AS property_name, pu.code AS property_unit,
                          m.id AS material_id, m.canonical_formula, m.chemical_system, m.name AS material_name,
                          s.id AS sample_id, s.sample_label, st.label AS sample_type_label,
                          s.thickness_value, s.thickness_unit,
                          meas.id AS measurement_id, mt.label AS measurement_type_label,
                          meas.temperature_value AS meas_temp_value, meas.temperature_unit AS meas_temp_unit,
                          u.code AS normalized_unit
                        FROM obs_observation o
                        JOIN obs_property_definition p ON p.id = o.property_definition_id
                        LEFT JOIN ont_term pu ON pu.id = p.canonical_unit_term_id
                        LEFT JOIN sam_sample s ON s.id = o.sample_id
                        LEFT JOIN mat_material m ON m.id = s.nominal_material_id
                        LEFT JOIN ont_term st ON st.id = s.sample_type_term_id
                        LEFT JOIN exp_measurement meas ON meas.id = o.measurement_id
                        LEFT JOIN ont_term mt ON mt.id = meas.measurement_type_term_id
                        LEFT JOIN ont_term u ON u.id = o.normalized_unit_term_id
                        WHERE o.id = :id
                        """
                    ),
                    {"id": observation_id.bytes},
                )
            )
            .mappings()
            .first()
        )

        if not obs_row:
            raise EntityNotFoundError(f"观测 {observation_id} 不存在")

        # 查询关联的证据片段列表
        evidence_rows = (
            (
                await self.session.execute(
                    text(
                        """
                        SELECT
                          e.id, e.paper_id, p.title AS paper_title, p.doi AS paper_doi,
                          e.document_id, a.storage_uri,
                          e.page_number, e.section, e.figure_number, e.table_number, e.text_snippet
                        FROM evd_observation_link l
                        JOIN evd_fragment e ON e.id = l.evidence_fragment_id
                        JOIN lit_paper p ON p.id = e.paper_id
                        LEFT JOIN lit_document d ON d.id = e.document_id
                        LEFT JOIN sys_artifact a ON a.id = d.artifact_id
                        WHERE l.observation_id = :id
                        ORDER BY e.created_at ASC
                        """
                    ),
                    {"id": observation_id.bytes},
                )
            )
            .mappings()
            .all()
        )

        evidence_list = [
            {
                "id": str(_uuid(r["id"])),
                "paper_id": str(_uuid(r["paper_id"])),
                "paper_title": r["paper_title"],
                "paper_doi": r["paper_doi"],
                "document_id": str(_uuid(r["document_id"])),
                "storage_uri": r["storage_uri"],
                "page_number": r["page_number"],
                "section": r["section"],
                "figure_number": r["figure_number"],
                "table_number": r["table_number"],
                "text_snippet": r["text_snippet"],
            }
            for r in evidence_rows
        ]

        return ObservationDetailRead(
            id=observation_id,
            verification_status=VerificationStatus(obs_row["verification_status"]),
            row_version=obs_row["row_version"],
            created_at=obs_row["created_at"],
            updated_at=obs_row["updated_at"],
            value_kind=obs_row["value_kind"],
            value_numeric=_number(obs_row["value_numeric"]),
            value_min=_number(obs_row["value_min"]),
            value_max=_number(obs_row["value_max"]),
            value_text=obs_row["value_text"],
            value_boolean=bool(obs_row["value_boolean"]) if obs_row["value_boolean"] is not None else None,
            original_value_text=obs_row["original_value_text"],
            original_unit_text=obs_row["original_unit_text"],
            normalized_value=_number(obs_row["normalized_value"]),
            normalized_unit=obs_row["normalized_unit"],
            uncertainty_lower=_number(obs_row["uncertainty_lower"]),
            uncertainty_upper=_number(obs_row["uncertainty_upper"]),
            condition_temperature_value=_number(obs_row["condition_temperature_value"]),
            condition_temperature_unit=obs_row["condition_temperature_unit"],
            quality_score=_number(obs_row["quality_score"]),
            property={
                "code": obs_row["property_code"],
                "name": obs_row["property_name"],
                "canonical_unit": obs_row["property_unit"],
            },
            material={
                "id": str(_uuid(obs_row["material_id"])),
                "canonical_formula": obs_row["canonical_formula"],
                "chemical_system": obs_row["chemical_system"],
                "name": obs_row["material_name"],
            },
            sample={
                "id": str(_uuid(obs_row["sample_id"])),
                "sample_label": obs_row["sample_label"],
                "sample_type_label": obs_row["sample_type_label"],
                "thickness_value": _number(obs_row["thickness_value"]),
                "thickness_unit": obs_row["thickness_unit"],
            },
            measurement={
                "id": str(_uuid(obs_row["measurement_id"])),
                "measurement_type_label": obs_row["measurement_type_label"],
                "temperature_value": _number(obs_row["meas_temp_value"]),
                "temperature_unit": obs_row["meas_temp_unit"],
            }
            if obs_row["measurement_id"]
            else None,
            evidence=evidence_list,
        )

    async def review_observation(
        self,
        observation_id: UUID,
        expected_version: int,
        review: ObservationReviewRequest,
        request_id: str | None,
    ) -> ObservationReviewResponse:
        """带 If-Match 乐观锁的审核状态流转。"""
        now = datetime.now(UTC)

        tx_mgr = self.session.begin_nested() if self.session.in_transaction() else self.session.begin()
        async with tx_mgr:
            # 1. 锁行并检查当前状态与版本
            row = (
                (
                    await self.session.execute(
                        text("SELECT verification_status, row_version FROM obs_observation WHERE id = :id FOR UPDATE"),
                        {"id": observation_id.bytes},
                    )
                )
                .mappings()
                .first()
            )

            if not row:
                raise EntityNotFoundError(f"观测 {observation_id} 不存在")

            current_status = VerificationStatus(row["verification_status"])
            current_version = row["row_version"]

            # 2. 检查版本匹配
            if current_version != expected_version:
                raise PreconditionFailedError(
                    f"观测版本已过期或不匹配（当前版本: W/\"{current_version}\"，提交: W/\"{expected_version}\"）"
                )

            # 3. 检查是否有有效关联证据
            evidence_count = (
                await self.session.execute(
                    text("SELECT COUNT(*) FROM evd_observation_link WHERE observation_id = :id"),
                    {"id": observation_id.bytes},
                )
            ).scalar_one()

            # 4. 状态机流转合法性校验
            validate_review_transition(current_status, review.decision, has_evidence=(evidence_count > 0))

            # 5. 执行更新 (SQL 中带上 row_version 条件保证原子性)
            new_version = current_version + 1
            result = await self.session.execute(
                text(
                    """
                    UPDATE obs_observation
                    SET verification_status = :status,
                        row_version = :new_version,
                        updated_at = :now
                    WHERE id = :id AND row_version = :expected_version
                    """
                ),
                {
                    "status": review.decision.value,
                    "new_version": new_version,
                    "now": now,
                    "id": observation_id.bytes,
                    "expected_version": expected_version,
                },
            )

            if result.rowcount == 0:
                raise PreconditionFailedError("乐观锁冲突：观测记录在审核提交时已被其他请求更新")

            # 6. 审计日志 (sys_audit_log)
            await self._audit(
                action="observation_review",
                entity_type="Observation",
                entity_id=observation_id,
                before_json={
                    "verification_status": current_status.value,
                    "row_version": current_version,
                },
                after_json={
                    "verification_status": review.decision.value,
                    "row_version": new_version,
                    "reviewer": review.reviewer,
                    "decision": review.decision.value,
                    "comment": review.comment,
                },
                request_id=request_id,
            )

            # 7. Outbox 事件 (sys_outbox_event)
            await self._outbox(
                event_id=uuid7(),
                aggregate_type="Observation",
                aggregate_id=observation_id,
                event_type="ObservationReviewed",
                payload={
                    "id": str(observation_id),
                    "status": review.decision.value,
                    "row_version": new_version,
                    "previous_status": current_status.value,
                    "reviewer": review.reviewer,
                },
            )

            return ObservationReviewResponse(
                observation_id=observation_id,
                previous_status=current_status,
                new_status=review.decision,
                row_version=new_version,
                reviewer=review.reviewer,
                decision=review.decision,
                comment=review.comment,
                reviewed_at=now,
            )

    async def list_terms_by_namespace(self, namespace: str) -> list[dict[str, Any]]:
        """按命名空间获取本体术语。"""
        rows = (
            (
                await self.session.execute(
                    text(
                        """
                        SELECT id, namespace, code, label, definition
                        FROM ont_term
                        WHERE namespace = :namespace AND deprecated = FALSE
                        ORDER BY label ASC
                        """
                    ),
                    {"namespace": namespace},
                )
            )
            .mappings()
            .all()
        )
        return [
            {
                "id": str(_uuid(r["id"])),
                "namespace": r["namespace"],
                "code": r["code"],
                "label": r["label"],
                "definition": r["definition"],
            }
            for r in rows
        ]

    async def _audit(
        self,
        action: str,
        entity_type: str,
        entity_id: UUID,
        before_json: dict | None,
        after_json: dict | None,
        request_id: str | None,
    ) -> None:
        await self.session.execute(
            text(
                """
                INSERT INTO sys_audit_log
                  (id, actor_type, action, entity_type, entity_id, before_json, after_json, request_id)
                VALUES (:id, 'reviewer', :action, :entity_type, :entity_id, :before, :after, :req_id)
                """
            ),
            {
                "id": uuid7().bytes,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id.bytes,
                "before": json_dumps(before_json) if before_json else None,
                "after": json_dumps(after_json) if after_json else None,
                "req_id": request_id,
            },
        )

    async def _outbox(
        self,
        event_id: UUID,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict,
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
                "payload": json_dumps(payload),
            },
        )
