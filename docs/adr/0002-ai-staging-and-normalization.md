# ADR-0002：AI 提取暂存隔离与严格单位归一化不变量

- 状态：已采用
- 日期：2026-09-07

## 背景

代码与架构审查发现两个关键的 P1 科学数据不变量问题：
1. **AI 提取隔离缺失**：AI 提取生成的数据此前可能直接写入 `obs_observation` 正式观测表，绕过了“AI 提取结果只能写入 `ext_*` 暂存表，不能直接生成 `VERIFIED` 或正式观测”的核心原则；
2. **隐式归一化回退缺陷**：当调用方未提供归一化数值时，系统隐式地将原始数值复制为归一化数值（`normalized_value = value_numeric`），造成未经明确换算确认的虚假归一化数据；浮点转换还可能带来科学计算精度损失。

此外，还存在 `paper_id` 与 `paper` 互斥不严格、`If-Match` 格式容错放宽、非公开 URI 协议未阻断等契约一致性问题。

## 决策

1. **AI 提取候选完全暂存隔离**：
   - 新增 `POST /v1/extractions/candidates` 端点与底层存储实现。AI 提取运行、制品哈希、源文档、证据片段及待审观测载荷完全保存在 `ext_run`、`ext_candidate`、`lit_document`、`evd_fragment` 等 `ext_*` 暂存表中；
   - 提取候选录入绝对不向 `obs_observation` 写入任何记录。
2. **显式人工审核晋升链路**：
   - 暴露 `POST /v1/extraction-candidates/{candidate_id}/review` 审核端点；
   - 携带 `If-Match: W/"<row_version>"` 乐观锁与 Reviewer Token 认证；
   - 审核通过（`accept` / `promote`）时，在单一 MySQL 事务内原子创建正式 `obs_observation`（初始状态强制为 `HUMAN_REVIEWED`）、`evd_observation_link`、`ext_review` 不可变审核记录、`sys_audit_log` 审计记录与 `sys_outbox_event` 事件；
   - 审核拒绝（`reject`）时，仅更新候选状态为 `rejected` 并写入不可变审核记录，严禁生成任何 Observation。
3. **人工录入端点收敛**：
   - `/v1/workflow/intake` 仅面向人工专家录入，其观测状态默认且强制为 `HUMAN_REVIEWED`；拒绝 `AI_EXTRACTED`、`AI_VALIDATED` 或直接标记 `VERIFIED`（HTTP 422）；
   - 严格互斥校验：`paper_id` 与 `paper` 必须且只能提供其一；`material_id` 与 `material` 必须且只能提供其一。
4. **彻底消除隐式归一化回退**：
   - 当调用方未提供归一化值与单位时，若原始单位与性质定义规范单位严格字面匹配，自动完成同单位规范化；否则 `normalized_value` 与 `normalized_unit_term_id` 严格保持 `NULL`，绝不盲目复制数值；
   - 归一化字段必须成对提供且单位必须与性质定义一致，非法组合直接拒绝（HTTP 422）；
   - 使用 `Decimal` 严格保持科学有效数字精度，避免浮点数舍入偏差。
5. **公共契约与协议加固**：
   - 文档存储协议仅开放 `s3://` 与 `https://`，公共接口拒绝 `http://` 与 `demo://`；
   - `If-Match` 严格匹配 `W/"<row_version>"` 弱 ETag 格式；
   - 全链路（中间件、请求上下文、Problem Details 响应体、响应头、审计日志）透传统一 `X-Request-ID`。

## 理由

- 科学数据库的信任基础在于证据的严谨性与溯源性。未经专家复核的 AI 产物不得与经过同行评议和人工审校的科学观测混同；
- 单位换算是材料数据检索、横向对比与机器学习建模的核心，任何未经验证的单位假定都会导致严重的科学结论偏差；
- 事务一致性与乐观锁保证了高并发审核场景下的数据准确与防丢失更新。

## 影响

- 数据库迁移 `mysql/005_extraction_staging.sql` 为 `ext_candidate` 补充 `row_version`，为 `ext_review` 补充 `reviewer_name` 与 `observation_id`；
- API 模型和客户端调用契约全面适配，前端录入界面与说明同步对齐；
- 重新生成 `app/api/openapi.json` 并通过契约测试验证。
