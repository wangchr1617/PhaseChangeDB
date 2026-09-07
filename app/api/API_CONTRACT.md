# PhaseChangeDB FastAPI 接口契约 v0.2.0

基础路径：`/v1`

## 契约通用规则

### 1. 标识符（ID）规范
- 所有外部暴露的 ID 统一使用规范的小写 UUIDv7 字符串格式。
- 业务实体由应用层生成 UUIDv7。
- MySQL 数据库底层采用原样 `BINARY(16)` 紧凑保存，禁止使用面向 UUIDv1 的交换标志 `UUID_TO_BIN(uuid, 1)`。

### 2. 游标分页
- 集合列表接口统一使用不透明游标分页结构：
```json
{
  "items": [],
  "next_cursor": "opaque-token-or-null",
  "has_more": false
}
```
- 禁止直接暴露数据库数字 offset 作为公共 API 游标。

### 3. 乐观并发控制（Optimistic Locking）
- 可变核心科研实体携带 `row_version` 版本号。
- 观测的人工审核和核心实体更新请求必须携带：
```http
If-Match: W/"<row_version>"
```
- 若数据库中当前版本与提交版本不一致，服务端返回 `412 Precondition Failed`。
- 更新成功后，`row_version` 严格原子自增 1。

### 4. 统一错误规范（RFC 7807 Problem Details）
- 所有业务错误响应媒体类型为 `application/problem+json`，并且必须包含 `request_id`：
```json
{
  "type": "about:blank",
  "title": "错误类型说明",
  "status": 409,
  "detail": "具体业务错误信息",
  "request_id": "8f8b88...uuid"
}
```
- 状态码映射语义：
  - `400 Bad Request`：科学/领域参数非法、If-Match 格式错误。
  - `401 Unauthorized`：审核凭据缺失或 Reviewer Token 错误。
  - `404 Not Found`：实体资源不存在。
  - `409 Conflict`：唯一性冲突、非法状态机流转、Idempotency-Key 载荷冲突。
  - `412 Precondition Failed`：If-Match 版本过期。
  - `422 Unprocessable Content`：Pydantic 请求体结构校验未通过。
  - `503 Service Unavailable`：数据库未就绪或 Reviewer 功能未配置。

### 5. 幂等性控制（Idempotency）
- 完整科研数据录入端点强制要求 `Idempotency-Key: <UUID-or-String>`。
- 同一个 Key + 相同载荷：幂等返回首次创建的相同结果，不重复插入数据库。
- 同一个 Key + 不同载荷：返回 `409 Conflict`。
- 业务事务失败时，幂等记录随同领域数据原子回滚，不留下不完整的半途记录。

### 6. 审核权限与科学数据边界
- 审核流转接口强制要求本地 Reviewer 凭据：
```http
Authorization: Bearer <PCM_REVIEWER_TOKEN>
```
- 未配置 `PCM_REVIEWER_TOKEN` 时返回 `503 Service Unavailable`。
- Token 错误或缺失时返回 `401 Unauthorized`。
- 普通读取接口无需 Reviewer Token。
- **AI 提取隔离**：AI 提取只能进入暂存区（`POST /v1/extractions/candidates`，写入 `ext_*` 表），绝对禁止直接写入 `obs_observation` 正式观测表。
- **候选审核晋升**：暂存候选通过 `POST /v1/extraction-candidates/{candidate_id}/review` 显式人工审核晋升（`accept`/`promote`）为正式观测，初始状态强制为 `HUMAN_REVIEWED`，同时记录不可变审核历史（`ext_review`）；拒绝分支（`reject`）更新候选状态，绝不生成 Observation。
- **人工科研录入**：`POST /v1/workflow/intake` 仅面向人工专家录入，其观测状态默认且强制为 `HUMAN_REVIEWED`；拒绝 `AI_EXTRACTED`、`AI_VALIDATED` 或直接标记 `VERIFIED`（HTTP 422）。
- **观测验证要求**：观测晋升为 `VERIFIED` 状态必须已有至少一条可定位关联证据（`evd_observation_link`）。

### 7. 严格单位归一化不变量
- 绝不隐式回退：当调用方未提供归一化值时，若原始单位与性质定义规范单位字面匹配，自动完成同单位规范化；否则 `normalized_value` 与 `normalized_unit_term_id` 严格保持 `NULL`，绝不盲目复制数值。
- 成对约束：`normalized_value` 与 `normalized_unit_term_id` 必须成对提供，提供单一字段或单位与性质定义 canonical unit 不匹配时直接拒绝（HTTP 422）。
- 精度保护：数值在序列化与持久化过程中严格使用 `Decimal`，防止浮点转换精度损失。

---

## 接口注册与实现状态

### 系统探针（已实现）
- `GET /health`：存活探针（Liveness），用于确认进程存活，返回 200 `{"status": "ok"}`。
- `GET /ready`：就绪探针（Readiness），用于探测 MySQL 数据库连通性，健康返回 200，不可用返回 503。

### v0.2.0 核心工作流（已注册并真实实现）
- `POST /v1/workflow/intake`：人工科研记录录入（需 `Idempotency-Key` 与 Reviewer Token）。单事务原子登记 Paper、Artifact、Document、Material、Sample、Measurement、Evidence 与 Observation（状态为 `HUMAN_REVIEWED`）。
- `GET /v1/workflow/observations/{observation_id}`：获取观测详情与完整证据溯源上下文（材料、文献、样品、测量条件与关联的证据原文、页码、图表号）。
- `POST /v1/workflow/observations/{observation_id}/review`：执行观测人工审核流转（需 `If-Match: W/"<version>"` 与 Reviewer Token）。支持 `HUMAN_REVIEWED` → `VERIFIED` / `DISPUTED` / `RETRACTED`。
- `GET /v1/workflow/terms`：按命名空间查询本体术语（例如 `?namespace=sample_type` 或 `?namespace=measurement_type`）。

### AI 提取暂存与候选审核（已注册并真实实现）
- `POST /v1/extractions/candidates`：提交 AI 提取候选（需 `Idempotency-Key`）。仅写入 `ext_*` 暂存表，绝不产生正式 Observation。
- `GET /v1/extraction-candidates/{candidate_id}`：查询提取候选详情与原始提取载荷。
- `POST /v1/extraction-candidates/{candidate_id}/review`：人工审核提取候选（需 `If-Match: W/"<version>"` 与 Reviewer Token）。通过时原子创建 `HUMAN_REVIEWED` 观测及不可变审核记录，拒绝时不产生观测。

### MVP 目录与检索（已注册并真实实现）
- `GET /v1/dashboard`：系统概览与数据统计（材料数、论文数、观测数、已验证数、待投递事件数）。
- `GET /v1/materials`：材料目录列表与过滤。
- `POST /v1/materials`：创建材料记录。
- `GET /v1/materials/{material_id}`：获取单个材料详情。
- `GET /v1/papers`：文献目录列表与过滤。
- `POST /v1/papers`：创建文献记录。
- `GET /v1/observations`：观测数据列表。
- `GET /v1/properties`：获取物理与化学性质目录列表。
- `POST /v1/search`：基于 MySQL 的基础检索（化学式、体系、论文标题或 DOI）。

### 后续里程碑端点（已定义契约，未在当前服务实现）
以下端点在现阶段属于后续架构契约：
- `PATCH /v1/materials/{material_id}`
- `GET /v1/materials/{material_id}/observations`
- `POST /v1/samples`
- `GET /v1/samples/{sample_id}`
- `POST /v1/process-runs`
- `POST /v1/measurements`
- `POST /v1/devices`
- `POST /v1/structures`
- `POST /v1/calculations`
- `POST /v1/documents/{document_id}/extractions`
- `POST /v1/claims`
- `POST /v1/agent/query`

---

## 自动生成的 OpenAPI
本契约定义与生成的 `app/api/openapi.json` 保持严格一致。修改路由或模型后，必须通过 `scripts/generate_openapi.py` 重新生成，严禁手工篡改。
