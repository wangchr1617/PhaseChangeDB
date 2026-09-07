from __future__ import annotations

import os
import uuid

import httpx
import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.infrastructure.database import session_factory
from app.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("PCM_INTEGRATION") != "1",
    reason="需要真实 MySQL 环境，设置 PCM_INTEGRATION=1 显式开启",
)

TEST_REVIEWER_TOKEN = "pcm-test-reviewer-token-secret-2026"


@pytest.fixture(autouse=True)
def setup_reviewer_token():
    settings = get_settings()
    original_token = settings.reviewer_token
    settings.reviewer_token = TEST_REVIEWER_TOKEN
    yield
    settings.reviewer_token = original_token


@pytest.mark.asyncio
async def test_mysql_is_ready_and_seeded():
    """1. 验证真实 MySQL 8.4 已就绪且包含基础种子数据。"""
    async with session_factory() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM ont_term"))
        term_count = result.scalar_one()
        assert term_count > 0, "ont_term 表中缺少基础术语种子数据"

        result = await session.execute(text("SELECT COUNT(*) FROM obs_property_definition"))
        prop_count = result.scalar_one()
        assert prop_count > 0, "obs_property_definition 表中缺少性质定义种子数据"


@pytest.mark.asyncio
async def test_full_workflow_intake_and_review_lifecycle():
    """验证人工科研数据录入、归一化为空保证、幂等控制、证据溯源到审核流转的全生命周期。"""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 查找依赖的种子 UUID
        async with session_factory() as session:
            sample_type_id = (
                await session.execute(
                    text("SELECT id FROM ont_term WHERE namespace = 'sample_type' LIMIT 1")
                )
            ).scalar_one()
            meas_type_id = (
                await session.execute(
                    text("SELECT id FROM ont_term WHERE namespace = 'measurement_type' LIMIT 1")
                )
            ).scalar_one()
            prop_id = (
                await session.execute(
                    text("SELECT id FROM obs_property_definition WHERE code = 'crystallization_temperature' LIMIT 1")
                )
            ).scalar_one()

        sample_type_uuid = str(uuid.UUID(bytes=bytes(sample_type_id)))
        meas_type_uuid = str(uuid.UUID(bytes=bytes(meas_type_id)))
        prop_uuid = str(uuid.UUID(bytes=bytes(prop_id)))

        # 2. 构造人工录入请求（初始状态为 HUMAN_REVIEWED，不提供 normalized_value）
        idempotency_key = f"acceptance-key-{uuid.uuid4()}"
        unique_suffix = uuid.uuid4().hex[:8]
        req_id = f"req-acceptance-intake-{unique_suffix}"
        intake_payload = {
            "paper": {
                "title": f"ACCEPTANCE_TEST Paper {unique_suffix}",
                "doi": f"10.1000/acceptance-{unique_suffix}",
                "journal": "Test Materials",
                "publication_year": 2026,
            },
            "document": {
                "storage_uri": "s3://phasechangedb/test/acceptance.pdf",
                "sha256": "93a44bbbb96c751ca06b526fe571763aa6113791b97777227b0998b8f1f5d8c3",
                "document_type": "main_article",
            },
            "material": {
                "canonical_formula": f"Ge2Sb2Te5_{unique_suffix}",
                "reduced_formula": f"Ge2Sb2Te5_{unique_suffix}",
                "chemical_system": "Ge-Sb-Te",
                "name": f"ACCEPTANCE_TEST GST {unique_suffix}",
                "aliases": [f"TEST_ALIAS_{unique_suffix}"],
            },
            "sample": {
                "sample_label": f"ACCEPTANCE_SAMPLE_{unique_suffix}",
                "sample_type_term_id": sample_type_uuid,
                "thickness_value": 150.0,
                "thickness_unit": "nm",
                "substrate_material": "Si/SiO2",
            },
            "evidence": {
                "page_number": 3,
                "section": "Results",
                "figure_number": "Fig. 4a",
                "table_number": None,
                "text_snippet": "ACCEPTANCE TEST: The crystallization temperature was measured to be 453 K.",
                "fragment_type": "paragraph",
            },
            "measurement": {
                "measurement_type_term_id": meas_type_uuid,
                "instrument": "DSC 8500",
                "temperature_value": 300.0,
                "temperature_unit": "K",
            },
            "observation": {
                "property_definition_id": prop_uuid,
                "value_kind": "scalar",
                "value_numeric": 453.0,
                "original_value_text": "453",
                "original_unit_text": "K",
                "condition_temperature_value": 300.0,
                "condition_temperature_unit": "K",
                "uncertainty_lower": 1.5,
                "uncertainty_upper": 1.5,
                "quality_score": 0.95,
                "verification_status": "HUMAN_REVIEWED",
            },
        }

        # 3. 提交完整人工录入（带 Idempotency-Key 与 Bearer Token 与 X-Request-ID）
        res_intake = await client.post(
            "/v1/workflow/intake",
            json=intake_payload,
            headers={
                "Idempotency-Key": idempotency_key,
                "Authorization": f"Bearer {TEST_REVIEWER_TOKEN}",
                "X-Request-ID": req_id,
            },
        )
        assert res_intake.status_code == 201, res_intake.text
        assert res_intake.headers["X-Request-ID"] == req_id
        data = res_intake.json()
        obs_id = data["observation_id"]
        assert data["verification_status"] == "HUMAN_REVIEWED"
        assert data["row_version"] == 1

        # 验证数据库中未归一化数据保持 normalized_* 为 NULL
        async with session_factory() as session:
            obs_row = (
                await session.execute(
                    text(
                        """
                        SELECT normalized_value, normalized_unit_term_id, original_value_text, original_unit_text
                        FROM obs_observation WHERE id = :id
                        """
                    ),
                    {"id": uuid.UUID(obs_id).bytes},
                )
            ).mappings().first()
            assert obs_row is not None
            assert obs_row["normalized_value"] is None, "未执行明确归一化时 normalized_value 必须为 NULL"
            assert obs_row["normalized_unit_term_id"] is None, "未执行明确归一化时 normalized_unit_term_id 必须为 NULL"
            assert obs_row["original_value_text"] == "453"
            assert obs_row["original_unit_text"] == "K"

            # 验证 Request ID 在 sys_audit_log 中一致
            audit_row = (
                await session.execute(
                    text("SELECT request_id FROM sys_audit_log WHERE entity_id = :id ORDER BY created_at DESC LIMIT 1"),
                    {"id": uuid.UUID(obs_id).bytes},
                )
            ).mappings().first()
            assert audit_row is not None
            assert audit_row["request_id"] == req_id

        # 4. 幂等性测试：相同 Key + 相同 Payload -> 必须返回 201 且结果相同
        res_idempotent = await client.post(
            "/v1/workflow/intake",
            json=intake_payload,
            headers={
                "Idempotency-Key": idempotency_key,
                "Authorization": f"Bearer {TEST_REVIEWER_TOKEN}",
                "X-Request-ID": "req-acceptance-intake-dup",
            },
        )
        assert res_idempotent.status_code == 201
        assert res_idempotent.json()["observation_id"] == obs_id

        # 5. 幂等性测试：相同 Key + 不同 Payload -> 必须返回 409 Conflict
        conflicting_payload = dict(intake_payload)
        conflicting_payload["sample"] = dict(intake_payload["sample"])
        conflicting_payload["sample"]["sample_label"] = "CONFLICTING_LABEL"
        res_conflict = await client.post(
            "/v1/workflow/intake",
            json=conflicting_payload,
            headers={
                "Idempotency-Key": idempotency_key,
                "Authorization": f"Bearer {TEST_REVIEWER_TOKEN}",
            },
        )
        assert res_conflict.status_code == 409
        assert "Idempotency-Key" in res_conflict.json()["detail"]

        # 6. 查看观测详情及其完整证据上下文
        res_detail = await client.get(f"/v1/workflow/observations/{obs_id}")
        assert res_detail.status_code == 200
        detail = res_detail.json()
        assert detail["id"] == obs_id
        assert detail["original_value_text"] == "453"
        assert detail["original_unit_text"] == "K"
        assert detail["normalized_value"] is None
        assert detail["verification_status"] == "HUMAN_REVIEWED"
        assert detail["row_version"] == 1
        assert len(detail["evidence"]) == 1
        assert "ACCEPTANCE TEST" in detail["evidence"][0]["text_snippet"]
        assert detail["evidence"][0]["figure_number"] == "Fig. 4a"

        # 7. 验证持久层 Outbox、Audit、Evidence Link 事务一致性
        async with session_factory() as session:
            outbox_count = (
                await session.execute(
                    text("SELECT COUNT(*) FROM sys_outbox_event WHERE aggregate_id = :id"),
                    {"id": uuid.UUID(obs_id).bytes},
                )
            ).scalar_one()
            assert outbox_count >= 1, "未找到关联的 sys_outbox_event"

            audit_count = (
                await session.execute(
                    text("SELECT COUNT(*) FROM sys_audit_log WHERE entity_id = :id"),
                    {"id": uuid.UUID(obs_id).bytes},
                )
            ).scalar_one()
            assert audit_count >= 1, "未找到关联的 sys_audit_log"

            link_count = (
                await session.execute(
                    text("SELECT COUNT(*) FROM evd_observation_link WHERE observation_id = :id"),
                    {"id": uuid.UUID(obs_id).bytes},
                )
            ).scalar_one()
            assert link_count == 1, "未找到 evd_observation_link 证据关联"

        # 8. 权限校验：无 Token / 错误 Token 审核返回 401
        res_unauth = await client.post(
            f"/v1/workflow/observations/{obs_id}/review",
            json={"decision": "VERIFIED", "reviewer": "Alice"},
            headers={"If-Match": 'W/"1"'},
        )
        assert res_unauth.status_code == 401

        res_wrong_token = await client.post(
            f"/v1/workflow/observations/{obs_id}/review",
            json={"decision": "VERIFIED", "reviewer": "Alice"},
            headers={"If-Match": 'W/"1"', "Authorization": "Bearer wrong-token-xyz"},
        )
        assert res_wrong_token.status_code == 401

        # 9. 乐观锁校验：旧版本或错误 If-Match 返回 412
        res_stale = await client.post(
            f"/v1/workflow/observations/{obs_id}/review",
            json={"decision": "VERIFIED", "reviewer": "Alice"},
            headers={"If-Match": 'W/"99"', "Authorization": f"Bearer {TEST_REVIEWER_TOKEN}"},
        )
        assert res_stale.status_code == 412

        # 10. 正确流转 1: HUMAN_REVIEWED -> VERIFIED (If-Match: W/"1")
        res_step1 = await client.post(
            f"/v1/workflow/observations/{obs_id}/review",
            json={
                "decision": "VERIFIED",
                "comment": "ACCEPTANCE: Scientific evidence fully verified",
                "reviewer": "Bob (Senior Reviewer)",
            },
            headers={"If-Match": 'W/"1"', "Authorization": f"Bearer {TEST_REVIEWER_TOKEN}"},
        )
        assert res_step1.status_code == 200
        step1_data = res_step1.json()
        assert step1_data["previous_status"] == "HUMAN_REVIEWED"
        assert step1_data["new_status"] == "VERIFIED"
        assert step1_data["row_version"] == 2

        # 11. 正确流转 2: VERIFIED -> RETRACTED (If-Match: W/"2")
        res_step2 = await client.post(
            f"/v1/workflow/observations/{obs_id}/review",
            json={
                "decision": "RETRACTED",
                "comment": "ACCEPTANCE: Retracted for testing terminal state",
                "reviewer": "Admin",
            },
            headers={"If-Match": 'W/"2"', "Authorization": f"Bearer {TEST_REVIEWER_TOKEN}"},
        )
        assert res_step2.status_code == 200
        step2_data = res_step2.json()
        assert step2_data["new_status"] == "RETRACTED"
        assert step2_data["row_version"] == 3

        # 12. 终态不可逆校验: RETRACTED 不能恢复为 VERIFIED
        res_revive = await client.post(
            f"/v1/workflow/observations/{obs_id}/review",
            json={"decision": "VERIFIED", "reviewer": "Admin"},
            headers={"If-Match": 'W/"3"', "Authorization": f"Bearer {TEST_REVIEWER_TOKEN}"},
        )
        assert res_revive.status_code == 409
        assert "终态，不可逆" in res_revive.json()["detail"]


@pytest.mark.asyncio
async def test_ai_extraction_staging_and_promotion_lifecycle():
    """验证 AI 提取候选暂存、拒绝分支、晋升为 HUMAN_REVIEWED 正式 Observation 的完整闭环。"""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 查找依赖的种子 UUID
        async with session_factory() as session:
            sample_type_id = (
                await session.execute(
                    text("SELECT id FROM ont_term WHERE namespace = 'sample_type' LIMIT 1")
                )
            ).scalar_one()
            meas_type_id = (
                await session.execute(
                    text("SELECT id FROM ont_term WHERE namespace = 'measurement_type' LIMIT 1")
                )
            ).scalar_one()
            prop_id = (
                await session.execute(
                    text("SELECT id FROM obs_property_definition WHERE code = 'crystallization_temperature' LIMIT 1")
                )
            ).scalar_one()

        sample_type_uuid = str(uuid.UUID(bytes=bytes(sample_type_id)))
        meas_type_uuid = str(uuid.UUID(bytes=bytes(meas_type_id)))
        prop_uuid = str(uuid.UUID(bytes=bytes(prop_id)))

        unique_suffix = uuid.uuid4().hex[:8]
        candidate_req = {
            "model_name": "PhaseLlmExtractor",
            "model_version": "v2.0",
            "prompt_version": "ner-pvd-v1",
            "ontology_version": "0.1",
            "paper": {
                "title": f"AI EXTRACTION Paper {unique_suffix}",
                "doi": f"10.1000/ai-ext-{unique_suffix}",
                "journal": "Nature Materials",
                "publication_year": 2026,
            },
            "document": {
                "storage_uri": "s3://phasechangedb/articles/ai-paper.pdf",
                "sha256": "84a44bbbb96c751ca06b526fe571763aa6113791b97777227b0998b8f1f5d8c4",
                "document_type": "main_article",
            },
            "candidate_type": "observation",
            "confidence": 0.88,
            "candidate_data": {
                "material": {
                    "canonical_formula": f"Sb2Te3_{unique_suffix}",
                    "chemical_system": "Sb-Te",
                    "name": f"Antimony Telluride {unique_suffix}",
                },
                "sample": {
                    "sample_label": f"AI_SAMPLE_{unique_suffix}",
                    "sample_type_term_id": sample_type_uuid,
                    "thickness_value": 50.0,
                    "thickness_unit": "nm",
                    "substrate_material": "Si",
                },
                "measurement": {
                    "measurement_type_term_id": meas_type_uuid,
                    "instrument": "Ellipsometer",
                    "temperature_value": 300.0,
                    "temperature_unit": "K",
                },
                "evidence": {
                    "page_number": 2,
                    "section": "Methods",
                    "figure_number": "Fig. 2",
                    "text_snippet": "AI EXTRACTED: crystallization temperature observed around 420 K.",
                    "fragment_type": "paragraph",
                },
                "property_definition_id": prop_uuid,
                "value_kind": "scalar",
                "value_numeric": 420.0,
                "original_value_text": f"420_{unique_suffix}",
                "original_unit_text": "K",
                "quality_score": 0.88,
            },
        }

        # 2. 提交暂存候选（要求 Idempotency-Key）
        stage_key = f"ai-stage-key-{unique_suffix}"
        res_stage = await client.post(
            "/v1/extractions/candidates",
            json=candidate_req,
            headers={
                "Idempotency-Key": stage_key,
                "X-Request-ID": f"req-stage-{unique_suffix}",
            },
        )
        assert res_stage.status_code == 201, res_stage.text
        stage_data = res_stage.json()
        candidate_id = stage_data["candidate_id"]
        run_id = stage_data["extraction_run_id"]
        assert run_id is not None
        assert stage_data["status"] == "pending"
        assert stage_data["row_version"] == 1

        # 3. 关键验证：暂存候选绝对不能产生正式 Observation！
        async with session_factory() as session:
            # 验证 ext_candidate 存在且状态为 pending
            cand_check = (
                await session.execute(
                    text("SELECT status, promoted_entity_id FROM ext_candidate WHERE id = :id"),
                    {"id": uuid.UUID(candidate_id).bytes},
                )
            ).mappings().first()
            assert cand_check is not None
            assert cand_check["status"] == "pending"
            assert cand_check["promoted_entity_id"] is None

            # 验证正式 Observation 表中没有任何以该候选 ID 关联的记录
            obs_check = (
                await session.execute(
                    text(
                        "SELECT COUNT(*) FROM obs_observation "
                        "WHERE original_value_text = :val AND quality_score = 0.88"
                    ),
                    {"val": f"420_{unique_suffix}"},
                )
            ).scalar_one()
            assert obs_check == 0, "暂存阶段严禁向 obs_observation 写入正式记录！"

        # 4. 获取候选详情
        res_cand = await client.get(f"/v1/extraction-candidates/{candidate_id}")
        assert res_cand.status_code == 200
        cand_detail = res_cand.json()
        assert cand_detail["id"] == candidate_id
        assert cand_detail["status"] == "pending"
        assert cand_detail["row_version"] == 1
        assert cand_detail["candidate_payload"]["original_value_text"] == f"420_{unique_suffix}"

        # 5. 测试拒绝分支 (REJECT)：先创建一个候选并拒绝它
        reject_suffix = uuid.uuid4().hex[:8]
        reject_req = dict(candidate_req)
        reject_req["paper"] = {
            "title": f"Reject Paper {reject_suffix}",
            "doi": f"10.1000/ai-ext-reject-{reject_suffix}",
            "journal": "Nature Materials",
            "publication_year": 2026,
        }
        reject_req["document"] = dict(candidate_req["document"])
        reject_req["document"]["sha256"] = "1" * 64
        reject_req["candidate_data"] = dict(candidate_req["candidate_data"])
        reject_req["candidate_data"]["material"] = {
            "canonical_formula": f"Reject_{reject_suffix}",
            "chemical_system": "Re-Jt",
            "name": "Reject Candidate",
        }
        res_rej_stage = await client.post(
            "/v1/extractions/candidates",
            json=reject_req,
            headers={"Idempotency-Key": f"rej-key-{reject_suffix}"},
        )
        assert res_rej_stage.status_code == 201
        rej_candidate_id = res_rej_stage.json()["candidate_id"]

        # 审核 REJECT（If-Match: W/"1"）
        res_rej_review = await client.post(
            f"/v1/extraction-candidates/{rej_candidate_id}/review",
            json={
                "decision": "reject",
                "reviewer": "Curator Jack",
                "comment": "Data quality does not meet criteria",
            },
            headers={
                "Authorization": f"Bearer {TEST_REVIEWER_TOKEN}",
                "If-Match": 'W/"1"',
            },
        )
        assert res_rej_review.status_code == 200
        rej_data = res_rej_review.json()
        assert rej_data["status"] == "rejected"
        assert rej_data["decision"] == "reject"
        assert rej_data["promoted_observation_id"] is None
        assert rej_data["row_version"] == 2

        # 确认 REJECT 后数据库依然没有产生 Observation
        async with session_factory() as session:
            rej_cand_db = (
                await session.execute(
                    text("SELECT status, promoted_entity_id FROM ext_candidate WHERE id = :id"),
                    {"id": uuid.UUID(rej_candidate_id).bytes},
                )
            ).mappings().first()
            assert rej_cand_db["status"] == "rejected"
            assert rej_cand_db["promoted_entity_id"] is None

        # 6. 审核晋升原候选 (ACCEPT / PROMOTE)
        # 验证 If-Match 乐观锁：旧版本/错误格式返回 412 或 400
        res_wrong_etag = await client.post(
            f"/v1/extraction-candidates/{candidate_id}/review",
            json={"decision": "accept", "reviewer": "Dr. Smith"},
            headers={
                "Authorization": f"Bearer {TEST_REVIEWER_TOKEN}",
                "If-Match": "1",  # 缺少 W/"" 前缀，格式错误
            },
        )
        assert res_wrong_etag.status_code == 400

        res_stale_etag = await client.post(
            f"/v1/extraction-candidates/{candidate_id}/review",
            json={"decision": "accept", "reviewer": "Dr. Smith"},
            headers={
                "Authorization": f"Bearer {TEST_REVIEWER_TOKEN}",
                "If-Match": 'W/"5"',  # 版本不匹配
            },
        )
        assert res_stale_etag.status_code == 412

        # 成功晋升 (If-Match: W/"1")
        promote_req_id = f"req-promote-{unique_suffix}"
        res_promote = await client.post(
            f"/v1/extraction-candidates/{candidate_id}/review",
            json={
                "decision": "accept",
                "reviewer": "Dr. Smith",
                "comment": "Validated by expert curator, promoted to official observation.",
            },
            headers={
                "Authorization": f"Bearer {TEST_REVIEWER_TOKEN}",
                "If-Match": 'W/"1"',
                "X-Request-ID": promote_req_id,
            },
        )
        assert res_promote.status_code == 200, res_promote.text
        promote_data = res_promote.json()
        assert promote_data["status"] == "accepted"
        assert promote_data["decision"] == "accept"
        assert promote_data["row_version"] == 2
        promoted_obs_id = promote_data["promoted_observation_id"]
        assert promoted_obs_id is not None

        # 7. 验证正式 Observation 的属性：状态为 HUMAN_REVIEWED，且归一化值为空
        res_promoted_obs = await client.get(f"/v1/workflow/observations/{promoted_obs_id}")
        assert res_promoted_obs.status_code == 200
        obs_data = res_promoted_obs.json()
        assert obs_data["id"] == promoted_obs_id
        assert obs_data["verification_status"] == "HUMAN_REVIEWED", "晋升出的 Observation 状态必须为 HUMAN_REVIEWED"
        assert obs_data["original_value_text"] == f"420_{unique_suffix}"
        assert obs_data["original_unit_text"] == "K"
        assert obs_data["normalized_value"] is None, "未执行明确归一化时 normalized_value 必须为 NULL"
        assert obs_data["row_version"] == 1
        assert len(obs_data["evidence"]) >= 1

        # 8. 验证不可变审核记录 (ext_review) 与事务一致性
        async with session_factory() as session:
            review_row = (
                await session.execute(
                    text(
                        """
                        SELECT reviewer_name, decision, observation_id, comment
                        FROM ext_review WHERE candidate_id = :cid
                        """
                    ),
                    {"cid": uuid.UUID(candidate_id).bytes},
                )
            ).mappings().first()
            assert review_row is not None
            assert review_row["reviewer_name"] == "Dr. Smith"
            assert review_row["decision"] == "accept"
            assert uuid.UUID(bytes=bytes(review_row["observation_id"])) == uuid.UUID(promoted_obs_id)

            # 验证 Audit 与 Outbox 均写入
            audit_count = (
                await session.execute(
                    text("SELECT COUNT(*) FROM sys_audit_log WHERE entity_id = :obs_id"),
                    {"obs_id": uuid.UUID(promoted_obs_id).bytes},
                )
            ).scalar_one()
            assert audit_count >= 1

            outbox_count = (
                await session.execute(
                    text("SELECT COUNT(*) FROM sys_outbox_event WHERE aggregate_id = :obs_id"),
                    {"obs_id": uuid.UUID(promoted_obs_id).bytes},
                )
            ).scalar_one()
            assert outbox_count >= 1

        # 9. 验证不可重复晋升：已处理过的候选再次审核返回 409
        res_dup_promote = await client.post(
            f"/v1/extraction-candidates/{candidate_id}/review",
            json={"decision": "accept", "reviewer": "Dr. Smith"},
            headers={
                "Authorization": f"Bearer {TEST_REVIEWER_TOKEN}",
                "If-Match": 'W/"2"',
            },
        )
        assert res_dup_promote.status_code == 409
        assert "已被处理" in res_dup_promote.json()["detail"]

        # 10. 验证正式流转：由 HUMAN_REVIEWED 正常晋升为 VERIFIED
        res_verify = await client.post(
            f"/v1/workflow/observations/{promoted_obs_id}/review",
            json={
                "decision": "VERIFIED",
                "reviewer": "Chief Scientist",
                "comment": "Peer verified scientific claim",
            },
            headers={
                "Authorization": f"Bearer {TEST_REVIEWER_TOKEN}",
                "If-Match": 'W/"1"',
            },
        )
        assert res_verify.status_code == 200
        verify_data = res_verify.json()
        assert verify_data["previous_status"] == "HUMAN_REVIEWED"
        assert verify_data["new_status"] == "VERIFIED"
        assert verify_data["row_version"] == 2
