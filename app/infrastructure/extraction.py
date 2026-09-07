"""PhaseChangeDB AI 提取候选暂存、审核与晋升持久化仓储。"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from app.domain.workflow import (
    DomainConflictError,
    DomainValidationError,
    EntityNotFoundError,
    PreconditionFailedError,
    resolve_and_validate_normalization,
    validate_candidate_review,
    validate_sha256_hex,
    validate_storage_uri,
)
from app.models.common import CandidateStatus
from app.models.extraction import (
    CandidateObservationData,
    CandidateReviewRequest,
    CandidateReviewResponse,
    ExtractionCandidateCreateRequest,
    ExtractionCandidateCreateResponse,
    ExtractionCandidateRead,
)


def _json_dumps(val: Any) -> str:
    return json.dumps(val, ensure_ascii=False, default=str)


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


class MySQLExtractionRepository:
    """负责 AI 提取结果暂存区 (ext_*) 与人工晋升至正式 Observation 的事务编排。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def stage_candidate(
        self,
        body: ExtractionCandidateCreateRequest,
        idempotency_key: str,
        request_path: str,
        request_id: str | None,
    ) -> ExtractionCandidateCreateResponse:
        """暂存 AI 提取候选数据。

        严格不变量：
        - 数据只进入 ext_* 暂存表。
        - 严禁直接写入 obs_observation。
        - 保存未经覆盖的原始候选载荷 JSON。
        - 暂存写入、审计与 Outbox 事件在同一事务中提交。
        """
        validate_storage_uri(body.document.storage_uri)
        validate_sha256_hex(body.document.sha256)

        request_raw = body.model_dump(mode="json")
        request_hash = hashlib.sha256(
            json.dumps(request_raw, sort_keys=True).encode("utf-8")
        ).hexdigest()

        tx_mgr = self.session.begin_nested() if self.session.in_transaction() else self.session.begin()
        async with tx_mgr:
            # 1. 幂等性检查
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
                    cached_data = existing_key_row["response_json"]
                    if isinstance(cached_data, str):
                        cached_data = json.loads(cached_data)
                    return ExtractionCandidateCreateResponse(**cached_data)
                else:
                    raise DomainConflictError("Idempotency-Key 冲突：相同的 key 提交了不同的请求载荷。")

            # 2. 文档制品 (Artifact)
            artifact_row = (
                (
                    await self.session.execute(
                        text(
                            """
                            SELECT id FROM sys_artifact
                            WHERE sha256_hex = :sha256 LIMIT 1
                            """
                        ),
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
                        INSERT INTO sys_artifact
                          (id, storage_uri, sha256_hex, mime_type, byte_size, original_filename, metadata_json)
                        VALUES (:id, :uri, :sha256, :mime, NULL, :fname, :meta)
                        """
                    ),
                    {
                        "id": artifact_id.bytes,
                        "uri": body.document.storage_uri,
                        "sha256": body.document.sha256,
                        "mime": "application/pdf",
                        "fname": body.document.storage_uri.split("/")[-1],
                        "meta": _json_dumps({"source": "extraction_staging"}),
                    },
                )

            # 3. 文献 (Paper)
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
                        "metadata": _json_dumps(body.paper.metadata) if body.paper.metadata else None,
                    },
                )

            # 4. 文档记录 (Document)
            document_id = uuid7()
            await self.session.execute(
                text(
                    """
                    INSERT INTO lit_document
                      (id, paper_id, document_type, artifact_id, parse_status, checksum_sha256_hex)
                    VALUES (:id, :paper_id, :doc_type, :artifact_id, 'parsed', :checksum)
                    """
                ),
                {
                    "id": document_id.bytes,
                    "paper_id": paper_id.bytes,
                    "artifact_id": artifact_id.bytes,
                    "doc_type": body.document.document_type,
                    "checksum": body.document.sha256,
                },
            )

            # 5. 提取运行记录 (ext_run)
            run_id = uuid7()
            now_dt = datetime.now(UTC)
            await self.session.execute(
                text(
                    """
                    INSERT INTO ext_run
                      (id, document_id, parser_version, model_name, model_version,
                       prompt_version, ontology_version, status, started_at, completed_at, metrics_json, created_at)
                    VALUES
                      (:id, :document_id, '1.0', :model_name, :model_version,
                       :prompt_version, :ontology_version, 'completed', :now, :now, :metrics, :now)
                    """
                ),
                {
                    "id": run_id.bytes,
                    "document_id": document_id.bytes,
                    "model_name": body.model_name,
                    "model_version": body.model_version,
                    "prompt_version": body.prompt_version,
                    "ontology_version": body.ontology_version,
                    "now": now_dt,
                    "metrics": _json_dumps({"confidence": body.confidence}),
                },
            )

            # 6. 证据溯源片段 (evd_fragment)
            evidence_id = uuid7()
            await self.session.execute(
                text(
                    """
                    INSERT INTO evd_fragment
                      (id, paper_id, document_id, artifact_id, fragment_type, page_number, section,
                       figure_number, table_number, text_snippet)
                    VALUES (:id, :paper_id, :doc_id, :artifact_id, :frag_type, :page, :section, :fig, :tab, :snippet)
                    """
                ),
                {
                    "id": evidence_id.bytes,
                    "paper_id": paper_id.bytes,
                    "doc_id": document_id.bytes,
                    "artifact_id": artifact_id.bytes,
                    "frag_type": body.candidate_data.evidence.fragment_type,
                    "page": body.candidate_data.evidence.page_number,
                    "section": body.candidate_data.evidence.section,
                    "fig": body.candidate_data.evidence.figure_number,
                    "tab": body.candidate_data.evidence.table_number,
                    "snippet": body.candidate_data.evidence.text_snippet,
                },
            )

            # 7. 候选观测记录 (ext_candidate)
            candidate_id = uuid7()
            raw_candidate_payload = body.candidate_data.model_dump(mode="json")
            await self.session.execute(
                text(
                    """
                    INSERT INTO ext_candidate
                      (id, extraction_run_id, candidate_type, candidate_payload_json,
                       confidence, evidence_fragment_id, status, promoted_entity_type,
                       promoted_entity_id, row_version, created_at, updated_at)
                    VALUES
                      (:id, :run_id, :cand_type, :payload, :confidence,
                       :evd_id, 'pending', NULL, NULL, 1, :now, :now)
                    """
                ),
                {
                    "id": candidate_id.bytes,
                    "run_id": run_id.bytes,
                    "cand_type": body.candidate_type,
                    "payload": _json_dumps(raw_candidate_payload),
                    "confidence": Decimal(str(body.confidence)) if body.confidence is not None else None,
                    "evd_id": evidence_id.bytes,
                    "now": now_dt,
                },
            )

            # 8. 审计记录 (sys_audit_log)
            audit_id = uuid7()
            await self.session.execute(
                text(
                    """
                    INSERT INTO sys_audit_log
                      (id, actor_id, actor_type, action, entity_type, entity_id,
                       before_json, after_json, request_id, created_at)
                    VALUES (:id, NULL, 'ai_extractor', 'stage_candidate', 'extraction_candidate',
                            :cand_id, NULL, :after, :req_id, :now)
                    """
                ),
                {
                    "id": audit_id.bytes,
                    "cand_id": candidate_id.bytes,
                    "after": _json_dumps({
                        "candidate_id": str(candidate_id),
                        "run_id": str(run_id),
                        "candidate_type": body.candidate_type,
                    }),
                    "req_id": request_id,
                    "now": now_dt,
                },
            )

            # 9. Outbox 事件 (sys_outbox_event)
            outbox_id = uuid7()
            await self.session.execute(
                text(
                    """
                    INSERT INTO sys_outbox_event
                      (id, aggregate_type, aggregate_id, event_type, payload_json, created_at)
                    VALUES (:id, 'extraction_candidate', :cand_id, 'extraction.candidate.staged', :payload, :now)
                    """
                ),
                {
                    "id": outbox_id.bytes,
                    "cand_id": candidate_id.bytes,
                    "payload": _json_dumps({
                        "candidate_id": str(candidate_id),
                        "run_id": str(run_id),
                        "document_id": str(document_id),
                    }),
                    "now": now_dt,
                },
            )

            # 10. 保存响应结构与幂等记录
            response_obj = ExtractionCandidateCreateResponse(
                candidate_id=candidate_id,
                extraction_run_id=run_id,
                candidate_type=body.candidate_type,
                status="pending",
                row_version=1,
                created_at=now_dt,
            )

            await self.session.execute(
                text(
                    """
                    INSERT INTO sys_idempotency_key
                      (idempotency_key, request_path, request_hash, response_status, response_json, created_at)
                    VALUES (:key, :path, :hash, 201, :resp, :now)
                    """
                ),
                {
                    "key": idempotency_key,
                    "path": request_path,
                    "hash": request_hash,
                    "resp": _json_dumps(response_obj.model_dump(mode="json")),
                    "now": now_dt,
                },
            )

            return response_obj

    async def get_candidate(self, candidate_id: UUID) -> ExtractionCandidateRead:
        """获取提取候选详情与原始载荷。"""
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT id, extraction_run_id, candidate_type, candidate_payload_json,
                           confidence, evidence_fragment_id, status, promoted_entity_type,
                           promoted_entity_id, row_version, created_at
                    FROM ext_candidate
                    WHERE id = :id
                    """
                ),
                {"id": candidate_id.bytes},
            )
        ).mappings().first()

        if not row:
            raise EntityNotFoundError(f"指定的 candidate_id {candidate_id} 不存在")

        payload = row["candidate_payload_json"]
        if isinstance(payload, str):
            payload = json.loads(payload)

        cand_status = (
            CandidateStatus(row["status"])
            if row["status"] in CandidateStatus.__members__.values()
            else row["status"]
        )

        return ExtractionCandidateRead(
            id=_uuid(row["id"]) or candidate_id,
            extraction_run_id=_uuid(row["extraction_run_id"]),
            candidate_type=row["candidate_type"],
            candidate_payload=payload,
            confidence=float(row["confidence"]) if row["confidence"] is not None else None,
            evidence_fragment_id=_uuid(row["evidence_fragment_id"]),
            status=cand_status,
            promoted_entity_type=row["promoted_entity_type"],
            promoted_entity_id=_uuid(row["promoted_entity_id"]),
            row_version=int(row["row_version"]),
            created_at=row["created_at"],
        )

    async def review_candidate(
        self,
        candidate_id: UUID,
        expected_version: int,
        review: CandidateReviewRequest,
        request_id: str | None,
    ) -> CandidateReviewResponse:
        """审核并晋升提取候选记录。

        严格不变量：
        - 要求 If-Match: W/"<row_version>" 乐观锁。
        - 候选只能在 pending 状态下处理，重复处理返回 409。
        - ACCEPT：单个事务内创建正式 Observation (状态为 HUMAN_REVIEWED)、
          Evidence Link、ext_review、Audit、Outbox。
        - REJECT：只写入 ext_review 并更新状态为 rejected，严禁创建 Observation。
        """
        tx_mgr = self.session.begin_nested() if self.session.in_transaction() else self.session.begin()
        async with tx_mgr:
            # 1. 锁候选行
            cand_row = (
                await self.session.execute(
                    text(
                        """
                        SELECT id, extraction_run_id, candidate_type, candidate_payload_json,
                               confidence, evidence_fragment_id, status, row_version
                        FROM ext_candidate
                        WHERE id = :id FOR UPDATE
                        """
                    ),
                    {"id": candidate_id.bytes},
                )
            ).mappings().first()

            if not cand_row:
                raise EntityNotFoundError(f"指定的 candidate_id {candidate_id} 不存在")

            current_version = int(cand_row["row_version"])
            if current_version != expected_version:
                raise PreconditionFailedError(
                    f"版本冲突：当前候选版本为 W/\"{current_version}\"，提供的 If-Match 为 W/\"{expected_version}\""
                )

            current_status = cand_row["status"]
            has_evidence = cand_row["evidence_fragment_id"] is not None
            decision_raw = review.decision.lower()
            if decision_raw == "accept":
                decision_norm = "accept"
            elif decision_raw == "reject":
                decision_norm = "reject"
            else:
                raise DomainValidationError(f"非法的审核决定: '{review.decision}'，只允许: accept, reject")

            if decision_norm == "reject" and review.corrected_payload is not None:
                raise DomainValidationError("reject 决策不允许携带 corrected_payload")

            validate_candidate_review(
                current_status=current_status,
                decision=decision_norm,
                has_evidence=has_evidence,
            )

            # 解析 Reviewer ID (如果是合法 UUID 则直接使用，否则生成确定性 UUIDv5)
            reviewer_str = review.reviewer.strip()
            try:
                reviewer_uuid = UUID(reviewer_str)
            except ValueError:
                reviewer_uuid = uuid5(NAMESPACE_URL, f"phasechangedb:reviewer:{reviewer_str}")

            now_dt = datetime.now(UTC)
            review_id = uuid7()
            raw_payload = cand_row["candidate_payload_json"]
            payload_dict = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload

            # 2. 如果是 REJECT：不创建 Observation，仅更新候选状态与审核记录
            if decision_norm == "reject":
                new_version = current_version + 1
                await self.session.execute(
                    text(
                        """
                        UPDATE ext_candidate
                        SET status = 'rejected',
                            row_version = :new_version,
                            updated_at = :now
                        WHERE id = :id
                        """
                    ),
                    {
                        "id": candidate_id.bytes,
                        "new_version": new_version,
                        "now": now_dt,
                    },
                )

                await self.session.execute(
                    text(
                        """
                        INSERT INTO ext_review
                          (id, candidate_id, reviewer_id, reviewer_name, observation_id,
                           decision, before_json, after_json, comment, reviewed_at)
                        VALUES
                          (:id, :cid, :rid, :rname, NULL,
                           'reject', :before, :after, :comment, :now)
                        """
                    ),
                    {
                        "id": review_id.bytes,
                        "cid": candidate_id.bytes,
                        "rid": reviewer_uuid.bytes,
                        "rname": reviewer_str,
                        "before": _json_dumps({"status": current_status, "payload": payload_dict}),
                        "after": _json_dumps({"status": "rejected"}),
                        "comment": review.comment,
                        "now": now_dt,
                    },
                )

                # 审计与 Outbox
                audit_id = uuid7()
                await self.session.execute(
                    text(
                        """
                        INSERT INTO sys_audit_log
                          (id, actor_id, actor_type, action, entity_type, entity_id,
                           before_json, after_json, request_id, created_at)
                        VALUES (:id, :actor_id, 'reviewer', 'reject_candidate', 'extraction_candidate',
                                :cid, :before, :after, :req_id, :now)
                        """
                    ),
                    {
                        "id": audit_id.bytes,
                        "actor_id": reviewer_uuid.bytes,
                        "cid": candidate_id.bytes,
                        "before": _json_dumps({"status": current_status}),
                        "after": _json_dumps({"status": "rejected"}),
                        "req_id": request_id,
                        "now": now_dt,
                    },
                )

                outbox_id = uuid7()
                await self.session.execute(
                    text(
                        """
                        INSERT INTO sys_outbox_event
                          (id, aggregate_type, aggregate_id, event_type, payload_json, created_at)
                        VALUES (:id, 'extraction_candidate', :cid, 'extraction.candidate.rejected', :payload, :now)
                        """
                    ),
                    {
                        "id": outbox_id.bytes,
                        "cid": candidate_id.bytes,
                        "payload": _json_dumps({
                            "candidate_id": str(candidate_id),
                            "reviewer": reviewer_str,
                            "decision": "reject",
                        }),
                        "now": now_dt,
                    },
                )

                return CandidateReviewResponse(
                    candidate_id=candidate_id,
                    extraction_run_id=_uuid(cand_row["extraction_run_id"]) or candidate_id,
                    status="rejected",
                    decision="reject",
                    reviewer=reviewer_str,
                    row_version=new_version,
                    promoted_observation_id=None,
                    reviewed_at=now_dt,
                )

            # 3. 如果是 ACCEPT：晋升为正式 Observation
            if review.corrected_payload:
                payload_dict.update(review.corrected_payload)

            candidate_data = CandidateObservationData(**payload_dict)

            # 查询提取运行关联的文献和文档
            run_row = (
                await self.session.execute(
                    text(
                        """
                        SELECT r.document_id, d.paper_id
                        FROM ext_run r
                        JOIN lit_document d ON r.document_id = d.id
                        WHERE r.id = :rid
                        """
                    ),
                    {"rid": cand_row["extraction_run_id"]},
                )
            ).mappings().first()

            if not run_row:
                raise EntityNotFoundError(f"关联的 extraction_run {cand_row['extraction_run_id']} 不存在")

            paper_id = _uuid(run_row["paper_id"])
            evidence_id = _uuid(cand_row["evidence_fragment_id"])
            assert paper_id is not None
            assert evidence_id is not None

            # 处理材料 (Material)
            if candidate_data.material_id:
                material_id = candidate_data.material_id
                mat_check = (
                    await self.session.execute(
                        text("SELECT id FROM mat_material WHERE id = :id"),
                        {"id": material_id.bytes},
                    )
                ).first()
                if not mat_check:
                    raise EntityNotFoundError(f"指定的 material_id {material_id} 不存在")
            else:
                assert candidate_data.material is not None
                material_id = uuid7()
                await self.session.execute(
                    text(
                        """
                        INSERT INTO mat_material
                          (id, canonical_formula, reduced_formula, chemical_system,
                           material_family_term_id, name, description)
                        VALUES (:id, :formula, :reduced, :system, :family_id, :name, :description)
                        """
                    ),
                    {
                        "id": material_id.bytes,
                        "formula": candidate_data.material.canonical_formula,
                        "reduced": candidate_data.material.reduced_formula,
                        "system": candidate_data.material.chemical_system,
                        "family_id": (
                            candidate_data.material.material_family_term_id.bytes
                            if candidate_data.material.material_family_term_id
                            else None
                        ),
                        "name": candidate_data.material.name,
                        "description": candidate_data.material.description,
                    },
                )

            # 处理样品 (Sample)
            sample_id = uuid7()
            await self.session.execute(
                text(
                    """
                    INSERT INTO sam_sample
                      (id, nominal_material_id, source_paper_id, sample_label,
                       sample_type_term_id, thickness_value, thickness_unit,
                       substrate_material, description, row_version)
                    VALUES (:id, :mat_id, :paper_id, :label, :type_id, :thick, :unit, :substrate, :desc, 1)
                    """
                ),
                {
                    "id": sample_id.bytes,
                    "mat_id": material_id.bytes,
                    "paper_id": paper_id.bytes,
                    "label": candidate_data.sample.sample_label,
                    "type_id": candidate_data.sample.sample_type_term_id.bytes,
                    "thick": candidate_data.sample.thickness_value,
                    "unit": candidate_data.sample.thickness_unit,
                    "substrate": candidate_data.sample.substrate_material,
                    "desc": candidate_data.sample.description,
                },
            )

            # 处理实验测量 (Measurement)
            measurement_id = uuid7()
            await self.session.execute(
                text(
                    """
                    INSERT INTO exp_measurement
                      (id, sample_id, measurement_type_term_id, instrument,
                       temperature_value, temperature_unit, source_paper_id, evidence_id)
                    VALUES (:id, :sample_id, :type_id, :instrument, :temp_val, :temp_unit, :paper_id, :evd_id)
                    """
                ),
                {
                    "id": measurement_id.bytes,
                    "sample_id": sample_id.bytes,
                    "type_id": candidate_data.measurement.measurement_type_term_id.bytes,
                    "instrument": candidate_data.measurement.instrument,
                    "temp_val": candidate_data.measurement.temperature_value,
                    "temp_unit": candidate_data.measurement.temperature_unit,
                    "paper_id": paper_id.bytes,
                    "evd_id": evidence_id.bytes,
                },
            )

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
                    {"id": candidate_data.property_definition_id.bytes},
                )
            ).mappings().first()

            if not prop_row:
                raise EntityNotFoundError(
                    f"指定的 property_definition_id {candidate_data.property_definition_id} 不存在"
                )

            canonical_unit_id = (
                UUID(bytes=bytes(prop_row["canonical_unit_term_id"]))
                if prop_row["canonical_unit_term_id"]
                else None
            )
            canonical_unit_symbol = prop_row["canonical_unit_code"]

            # 严格单位归一化校验
            norm_val, norm_unit_id = resolve_and_validate_normalization(
                original_value_text=candidate_data.original_value_text,
                original_unit_text=candidate_data.original_unit_text,
                value_numeric=candidate_data.value_numeric,
                normalized_value=candidate_data.normalized_value,
                normalized_unit_term_id=candidate_data.normalized_unit_term_id,
                canonical_unit_term_id=canonical_unit_id,
                canonical_unit_symbol=canonical_unit_symbol,
            )

            val_numeric_dec = (
                Decimal(str(candidate_data.value_numeric))
                if candidate_data.value_numeric is not None
                else None
            )
            val_min_dec = (
                Decimal(str(candidate_data.value_min))
                if candidate_data.value_min is not None
                else None
            )
            val_max_dec = (
                Decimal(str(candidate_data.value_max))
                if candidate_data.value_max is not None
                else None
            )
            unc_lower_dec = (
                Decimal(str(candidate_data.uncertainty_lower))
                if candidate_data.uncertainty_lower is not None
                else None
            )
            unc_upper_dec = (
                Decimal(str(candidate_data.uncertainty_upper))
                if candidate_data.uncertainty_upper is not None
                else None
            )
            cond_temp_dec = (
                Decimal(str(candidate_data.condition_temperature_value))
                if candidate_data.condition_temperature_value is not None
                else None
            )

            # 创建正式 Observation（状态必须为 HUMAN_REVIEWED，严禁直接设为 VERIFIED 或保持 AI_EXTRACTED）
            observation_id = uuid7()
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
                      :quality_score, 'HUMAN_REVIEWED', 1, :created_at, :created_at
                    )
                    """
                ),
                {
                    "id": observation_id.bytes,
                    "sample_id": sample_id.bytes,
                    "property_definition_id": candidate_data.property_definition_id.bytes,
                    "measurement_id": measurement_id.bytes,
                    "value_kind": candidate_data.value_kind.value,
                    "value_numeric": val_numeric_dec,
                    "value_min": val_min_dec,
                    "value_max": val_max_dec,
                    "value_text": candidate_data.value_text,
                    "value_boolean": candidate_data.value_boolean,
                    "original_value_text": candidate_data.original_value_text,
                    "original_unit_text": candidate_data.original_unit_text,
                    "normalized_value": norm_val,
                    "normalized_unit_term_id": norm_unit_id.bytes if norm_unit_id else None,
                    "uncertainty_lower": unc_lower_dec,
                    "uncertainty_upper": unc_upper_dec,
                    "condition_temperature_value": cond_temp_dec,
                    "condition_temperature_unit": candidate_data.condition_temperature_unit,
                    "quality_score": candidate_data.quality_score,
                    "created_at": now_dt,
                },
            )

            # 关联证据 (evd_observation_link)
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
                    "confidence": candidate_data.quality_score or 1.0,
                },
            )

            # 更新候选记录状态为 accepted 并关联生成的 observation_id
            new_version = current_version + 1
            await self.session.execute(
                text(
                    """
                    UPDATE ext_candidate
                    SET status = 'accepted',
                        promoted_entity_type = 'observation',
                        promoted_entity_id = :obs_id,
                        row_version = :new_version,
                        updated_at = :now
                    WHERE id = :id
                    """
                ),
                {
                    "id": candidate_id.bytes,
                    "obs_id": observation_id.bytes,
                    "new_version": new_version,
                    "now": now_dt,
                },
            )

            # 写入不可变审核记录 (ext_review)
            await self.session.execute(
                text(
                    """
                    INSERT INTO ext_review
                      (id, candidate_id, reviewer_id, reviewer_name, observation_id,
                       decision, before_json, after_json, comment, reviewed_at)
                    VALUES
                      (:id, :cid, :rid, :rname, :obs_id,
                       :decision, :before, :after, :comment, :now)
                    """
                ),
                {
                    "id": review_id.bytes,
                    "cid": candidate_id.bytes,
                    "rid": reviewer_uuid.bytes,
                    "rname": reviewer_str,
                    "obs_id": observation_id.bytes,
                    "decision": decision_norm,
                    "before": _json_dumps({"status": current_status, "payload": payload_dict}),
                    "after": _json_dumps({
                        "status": "accepted",
                        "promoted_observation_id": str(observation_id),
                        "verification_status": "HUMAN_REVIEWED",
                    }),
                    "comment": review.comment,
                    "now": now_dt,
                },
            )

            # 写入审计记录 (sys_audit_log)
            audit_id = uuid7()
            await self.session.execute(
                text(
                    """
                    INSERT INTO sys_audit_log
                      (id, actor_id, actor_type, action, entity_type, entity_id,
                       before_json, after_json, request_id, created_at)
                    VALUES (:id, :actor_id, 'reviewer', 'promote_candidate', 'obs_observation',
                            :obs_id, NULL, :after, :req_id, :now)
                    """
                ),
                {
                    "id": audit_id.bytes,
                    "actor_id": reviewer_uuid.bytes,
                    "obs_id": observation_id.bytes,
                    "after": _json_dumps({
                        "candidate_id": str(candidate_id),
                        "promoted_observation_id": str(observation_id),
                        "verification_status": "HUMAN_REVIEWED",
                    }),
                    "req_id": request_id,
                    "now": now_dt,
                },
            )

            # 写入 Outbox 事件 (sys_outbox_event)
            outbox_id = uuid7()
            await self.session.execute(
                text(
                    """
                    INSERT INTO sys_outbox_event
                      (id, aggregate_type, aggregate_id, event_type, payload_json, created_at)
                    VALUES (:id, 'obs_observation', :obs_id, 'observation.promoted', :payload, :now)
                    """
                ),
                {
                    "id": outbox_id.bytes,
                    "obs_id": observation_id.bytes,
                    "payload": _json_dumps({
                        "candidate_id": str(candidate_id),
                        "observation_id": str(observation_id),
                        "material_id": str(material_id),
                        "verification_status": "HUMAN_REVIEWED",
                    }),
                    "now": now_dt,
                },
            )

            return CandidateReviewResponse(
                candidate_id=candidate_id,
                extraction_run_id=_uuid(cand_row["extraction_run_id"]) or candidate_id,
                status="accepted",
                decision=decision_norm,
                reviewer=reviewer_str,
                row_version=new_version,
                promoted_observation_id=observation_id,
                reviewed_at=now_dt,
            )
