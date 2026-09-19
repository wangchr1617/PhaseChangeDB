# PhaseChangeDB

PhaseChangeDB 是面向相变材料的、以证据为基础的科学数据与知识发现平台。平台将材料、文献、实验样品、科学观测与原始证据组织为可追溯的数据闭环链路，并提供中文 Web 操作界面与统一检索入口。

> 当前版本：`0.2.0-mvp`。材料、文献、文档制品元数据、实体样品、实验测量、证据片段、性质观测、概览统计、基础词法检索、完整科研数据录入与人工审核状态机已在 MySQL 8.4 中完全打通。

---

## 🚀 快速上手 (Quick Start)

为了让不同背景的研究人员（无论是实验科学家还是计算研究者）均能零门槛体验，PhaseChangeDB 提供了三种开箱即用的运行方式：

### 方式一：GitHub Codespaces 云端一键运行（完全免安装 · 论文审稿推荐）
无需在电脑上配置任何环境，直接在网页浏览器中秒级拉起专属云端沙箱（支持在浏览器中直接上传/拖拽本地 PDF 文献）：

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/wangchr1617/PhaseChangeDB)

### 方式二：本地 Python 单命令直启（免 Docker · 免 MySQL · 免 Node.js）
电脑只要安装了 Python 3.10+，克隆代码后一条命令启动，系统会自动在默认浏览器打开操作界面：
```bash
python run_demo.py
```
> **设计亮点**：
> - 仓库内置了仅 460 KB 的预编译生产前端，无需安装 Node.js/pnpm 编译；
> - 若本地未运行 MySQL 8.4，启动器将自动无缝切换至【内置科学演示模式】，包含真实的 GeTe / Sb₂Te₃ 核心物性分布、3D 知识图谱与文献证据链，支持即时交互探索。

### 方式三：Docker Compose 完整集群部署（开发与生产部署）
适合需要完整权威数据库事务与长期运维的场景：
```bash
docker compose up -d
# 访问地址：http://localhost:8080 (Web 交互界面) 或 http://localhost:8000/docs (Swagger API 契约)
```

---

## MVP v0.2.0 核心功能

1. **科研数据录入与严格人工确认**：
   - **人工专家录入**（`/v1/workflow/intake`）：录入文献、文档元数据（`s3://` / `https://` 协议与 SHA-256 校验）、材料、样品、实验测量、证据片段与观测。生成的观测状态强制且默认设为 `HUMAN_REVIEWED`，拒绝直接创建为 `VERIFIED` 或 `AI_*`；
   - **严格单位归一化不变量**：当前 MVP 阶段尚未接入跨单位自动换算引擎；当且仅当原始单位与性质定义的规范单位完全一致时，才校验并写入 `normalized_*`；若原始单位不同，调用方必须省略 `normalized_*`（由系统安全置为 NULL），严禁伪造换算结果；若在异单位情况下强行传入 `normalized_*` 将直接返回 HTTP 400 拒绝；数值使用 `Decimal` 严格防止浮点精度丢失；
   - **单一事务提交**：所有实体与关联在单个 MySQL 8.4 事务中原子提交，同时写入 `sys_audit_log` 审计记录与 `sys_outbox_event` 事件。

2. **AI 提取候选完全暂存与晋升链路**：
   - **AI 提取候选暂存**（`/v1/extractions/candidates`）：AI 提取结果仅写入 `ext_*` 暂存表（`ext_run`, `ext_candidate`, `lit_document`, `evd_fragment`），记录模型版本、提示词版本、本体版本、置信度与证据片段；**绝对不直接写入 `obs_observation`**；当前 MVP 的 PDF 上传与提取仅负责登记和校验元数据与对象存储引用（`storage_uri`、SHA-256），尚未挂载真实 OCR/多模态抽取流水线；
   - **候选人工审核晋升**（`/v1/extraction-candidates/{id}/review`）：候选审核仅支持 `accept` 与 `reject` 两种决策。人工专家审核通过（`accept`）时，原子创建正式 `obs_observation`（状态为 `HUMAN_REVIEWED`）、关联证据及不可变审核记录 `ext_review`（可按需携带 `corrected_payload`）；审核拒绝（`reject`）时仅更新候选状态为 `rejected`，严禁产生 Observation，且禁止携带修正载荷（HTTP 422）。

3. **观测人工审核状态机与证据溯源**：
   - 观测值详情展示：完整回溯材料、文献出处、样品参数与对应证据原文及图表号；
   - 状态机流转控制：`HUMAN_REVIEWED` → `VERIFIED`，支持 `DISPUTED`（存疑）与 `RETRACTED`（撤回）；
   - 晋升为 `VERIFIED` 必须已有可定位的关联证据片段；
   - 撤回（`RETRACTED`）为终态不可逆；
   - 严格通过 `If-Match: W/"<row_version>"` 乐观锁防止并发丢失更新；
   - 本地 `Authorization: Bearer <PCM_REVIEWER_TOKEN>` 权限保护。

4. **幂等性保障**：
   - 录入端点强制要求 `Idempotency-Key`；
   - 同 Key 同载荷幂等返回首次创建数据，同 Key 异载荷返回 `409 Conflict`；
   - 幂等记录与业务数据在同一事务中提交，失败时整体回滚。

5. **系统探针与统一错误规范**：
   - `/health`：存活探针（Liveness），确认应用服务进程存活（HTTP 200）；
   - `/ready`：就绪探针（Readiness），探测 MySQL 8.4 实际连接（就绪 200，未就绪 503）；
   - 所有业务异常统一采用 RFC 7807 `application/problem+json` 格式，携带统一追踪的 `request_id`。

6. **中文 Web 响应式界面**：
   - 数据概览仪表盘与最新观测列表；
   - 检索与材料库、文献目录浏览；
   - 模块化“录入与审核工作流”界面，支持人工表单录入、ID 详情检索与人工审核操作面板。

---

## 技术栈

- **权威事实源**：MySQL 8.4 LTS（InnoDB、`BINARY(16)` 紧凑保存 UUIDv7）；
- **后端**：Python 3.11+、FastAPI、Pydantic、SQLAlchemy Async、asyncmy、cryptography；
- **包管理与运行**：uv，依赖锁定于 `uv.lock`；
- **前端**：React 19、TypeScript、Vite，组件按 API、类型、表单、详情面板拆分；
- **前端包管理**：pnpm 11+，依赖锁定于 `frontend/pnpm-lock.yaml`；
- **容器编排**：Docker Compose（仅本地绑定 `127.0.0.1` 端口）。

---

## 最快启动方式：Docker Compose

### 1. 配置环境变量
```bash
cp .env.example .env
```
在 `.env` 中设置本地 Reviewer Token（例如：`PCM_REVIEWER_TOKEN=my-local-reviewer-secret`）。

### 2. 构建并启动服务
```bash
docker compose up --build -d
```

### 3. 访问系统
- **中文 Web 界面**：<http://localhost:8080>
  - 点击左侧主导航中的 **“录入与审核工作流”** 即可进入核心业务闭环；
- **API 文档 (Swagger)**：<http://localhost:8000/docs>
- **存活探针**：<http://localhost:8000/health>
- **就绪探针**：<http://localhost:8000/ready>

### 4. 核心工作流 cURL 快速演练

```bash
# 1. 提交 AI 提取候选暂存（需 Idempotency-Key，仅写入 ext_* 暂存表）
curl -X POST http://127.0.0.1:8000/v1/extractions/candidates \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: ai-demo-key-001" \
  -d '{
    "model_name": "LlmExtractor", "model_version": "v1.0",
    "prompt_version": "ner-v1", "ontology_version": "0.1",
    "paper": {"title": "GST Phase Change Study", "doi": "10.1000/gst-study-001", "journal": "APL", "publication_year": 2026},
    "document": {"storage_uri": "s3://phasechangedb/papers/gst.pdf", "sha256": "4a5b6c7d8e9f0123456789abcdef0123456789abcdef0123456789abcdef0123", "document_type": "main_article"},
    "candidate_type": "observation", "confidence": 0.95,
    "candidate_data": {
      "material": {"canonical_formula": "Ge2Sb2Te5", "chemical_system": "Ge-Sb-Te", "name": "GST-225"},
      "sample": {"sample_label": "GST_THIN_FILM_01", "sample_type_term_id": "01a06666-3c71-7ee0-898e-5414acccb1c7", "thickness_value": 50, "thickness_unit": "nm"},
      "measurement": {"measurement_type_term_id": "01a06670-0000-7000-8000-000000000007", "instrument": "DSC"},
      "evidence": {"page_number": 3, "section": "Results", "text_snippet": "Activation energy is 2.35 eV.", "fragment_type": "paragraph"},
      "property_definition_id": "01a06666-90fe-7157-8efe-0faf744b5ded",
      "value_kind": "scalar", "value_numeric": 2.35, "original_value_text": "2.35", "original_unit_text": "eV", "quality_score": 0.95
    }
  }'

# 2. 人工专家审核通过候选并晋升为正式观测（需 If-Match 乐观锁与 Reviewer Token）
# 晋升后在 obs_observation 中生成 HUMAN_REVIEWED 状态的正式记录
curl -X POST http://127.0.0.1:8000/v1/extraction-candidates/<CANDIDATE_ID>/review \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer reviewer-token-dev-secret-2026" \
  -H 'If-Match: W/"1"' \
  -d '{"decision": "accept", "reviewer": "Curator Alice", "comment": "Cross-checked with spectrum"}'

# 3. 观测详情溯源查询
curl http://127.0.0.1:8000/v1/workflow/observations/<OBSERVATION_ID>

# 4. 观测人工审核晋升为 VERIFIED 状态
curl -X POST http://127.0.0.1:8000/v1/workflow/observations/<OBSERVATION_ID>/review \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer reviewer-token-dev-secret-2026" \
  -H 'If-Match: W/"1"' \
  -d '{"decision": "VERIFIED", "reviewer": "Curator Alice", "comment": "Fully verified"}'
```

### 5. 停止服务
```bash
docker compose down
```
如需保留数据直接使用上述命令；若明确需要清空数据库重新初始化，可执行 `docker compose down -v`。

---

## 常用开发与测试命令

### 后端测试与 Lint
```bash
# 执行代码格式与静态检查
uv run ruff check app tests scripts

# 运行单元测试与契约测试
uv run pytest

# 运行包含真实 MySQL 8.4 的全套集成测试
PCM_INTEGRATION=1 uv run pytest

# 重新生成 openapi.json（严禁手工修改）
uv run python scripts/generate_openapi.py
```

### 前端开发与构建
```bash
corepack pnpm --dir frontend lint
corepack pnpm --dir frontend typecheck
corepack pnpm --dir frontend build
```

---

## 当前边界与限制

1. **投影层暂缓**：Elasticsearch 词法/向量混合检索与 Neo4j 知识图谱投影 Worker 属于下一阶段里程碑，本版本权威数据落入 MySQL 并在同一事务生成 Outbox 事件；
2. **远程文档上传**：本阶段 API 负责登记 S3/HTTPS 文档的存储 URI 与 SHA-256 校验和，不执行实际的大型文件流式上传；
3. **权限边界**：MVP 采用单机共享的 `PCM_REVIEWER_TOKEN` 进行审核认证，多租户与 RBAC 留待后续迭代。
