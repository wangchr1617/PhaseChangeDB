# PhaseChangeDB v0.2.0 MVP 本地集成与核心闭环验收报告

- **验收日期**：2026-09-07
- **执行环境**：macOS (Darwin aarch64)、Docker Desktop 27.4.0 (Compose v2.31.0)、Python 3.13 (uv 0.12.10)、Node.js 22 (pnpm 11.25.0)、MySQL 8.4 LTS (InnoDB)。
- **目标版本**：v0.2.0 MVP 核心闭环。

---

## 1. 验收概要结论

**全部验收项均在真实本地环境与真实容器环境中执行通过**。
原 v0.1.0-mvp 中“Docker 环境缺失、未在真实容器中运行、观测无录入表单、审核未打通”等阻塞结论已全部解除。

核心实现与验证覆盖：
1. 文献、文档制品元数据、材料、样品、实验测量、证据片段、性质观测在单个 MySQL 8.4 事务中原子入库；
2. 完整的数据幂等性机制（同 Key 同 Payload 幂等重放，同 Key 异 Payload 返回 409 Conflict）；
3. 证据溯源展示与带 `If-Match: W/"<row_version>"` 乐观锁的人工审核状态机（`AI_EXTRACTED` → `HUMAN_REVIEWED` → `VERIFIED`，支持 `DISPUTED` 与终态不可逆的 `RETRACTED`）；
4. 本地 Reviewer Token 权限隔离（`Authorization: Bearer <PCM_REVIEWER_TOKEN>`）；
5. 统一 RFC 7807 `application/problem+json` 错误响应与 `request_id` 追踪；
6. 区分 `/health`（存活探针）与 `/ready`（就绪探针，探测真实数据库）；
7. 模块化中文 Web 工作流界面（拆分为 API 客户端、类型定义、录入表单组件与观测详情审核面板）；
8. Docker 容器数据持久性（容器重启后数据完整保留）；
9. 由真实应用重新导出的 `app/api/openapi.json`。

---

## 2. 实际运行验收命令与结果

### 2.1 后端代码质量与静态检查
```bash
uv run ruff check app tests scripts
```
- **输出结果**：`All checks passed!`（退出码 0）。

### 2.2 前端代码质量、类型检查与生产构建
```bash
corepack pnpm --dir frontend lint
corepack pnpm --dir frontend typecheck
corepack pnpm --dir frontend build
```
- **输出结果**：
  - `oxlint`: Found 0 warnings and 0 errors. Finished in 44ms on 8 files.
  - `tsc -b`: 类型检查无任何错误通过。
  - `vite build`: `dist/index.html`、`dist/assets/*.css`、`dist/assets/*.js` 打包成功（退出码 0）。

### 2.3 单元测试与契约测试
```bash
uv run pytest
```
- **输出结果**：`28 passed, 5 skipped in 0.20s`（退出码 0）。
- **覆盖内容**：
  - AI 暂存隔离与晋升契约校验，候选审核决策严格限定为 `accept` 与 `reject`（拒绝 `modify`/`promote` 返回 422，`reject` 携带修正载荷返回 422）；
  - 严格单位归一化校验（同单位解析、异单位禁止伪造归一化返回 DomainValidationError、成对约束与 Decimal 科学精度保存）；
  - `paper`/`paper_id` 与 `material`/`material_id` 严格互斥校验（HTTP 422）；
  - `storage_uri` 协议白名单校验（仅允许 `s3://` 与 `https://`，阻断 `http://` 与 `demo://`）；
  - `If-Match: W/"<row_version>"` 严格弱 ETag 正则校验；
  - 状态机流转矩阵、跳过审核拒绝、无证据不能验证、撤回后不可恢复；
  - RFC 7807 统一错误模型（400/401/404/409/412/422/503）与 `request_id` 穿透；
  - Observation 主体排他性与范围数值校验；
  - OpenAPI 契约端点完整性、方法覆盖与生成的模式强一致性检查。

### 2.4 真实 MySQL 8.4 集成测试
```bash
PCM_INTEGRATION=1 uv run pytest
```
- **输出结果**：`33 passed in 0.45s`（退出码 0，包含全部 28 项单元/契约测试与 5 项真实 MySQL 集成闭环）。
- **验证内容**：
  - MySQL 8.4 就绪与核心种子数据存在；
  - **AI 提取候选暂存、拒绝分支与晋升闭环**：
    1. AI 提交候选至 `/v1/extractions/candidates`，验证仅落入 `ext_*` 暂存表，`obs_observation` 记录数为 0；
    2. 候选审核决策收敛校验：`modify`、`promote` 及 `reject` 附带 `corrected_payload` 均被拦截并返回 422；
    3. 候选拒绝分支测试：验证更新状态为 `rejected`、记录不可变 `ext_review` 且绝不产生 Observation；
    4. `If-Match` 乐观锁测试（格式错误返回 400，版本不匹配返回 412）；
    5. 候选审核晋升（`accept`）：单个事务内原子生成 `HUMAN_REVIEWED` 状态的正式 Observation，`normalized_value` 在无换算时严格保持为 `NULL`；
    6. 不可变审核记录 `ext_review` 校验与 Reviewer 身份追溯；
    7. 关联证据片段 `evd_fragment` 与 `evd_observation_link` 事务一致性；
    8. 事务性 `sys_audit_log` 与 `sys_outbox_event` 生成；
  - **人工录入工作流闭环**：
    - `POST /v1/workflow/intake` 录入观测直接生成 `HUMAN_REVIEWED` 状态（拒绝 `AI_*` 状态与直接 `VERIFIED`）；
    - 严格同单位归一化计算与非同单位保持 NULL；
    - 关联的 Outbox 事件、审计日志与证据关联单一事务写入；
    - 幂等性控制（同 Key 幂等重放，异 Key 载荷冲突 409）；
    - 权限控制（缺少或错误 Reviewer Token 返回 401）；
    - 完整审核状态流转（`HUMAN_REVIEWED` → `VERIFIED` → `RETRACTED`）与版本号递增；
    - 终态记录不可逆校验（已撤回记录禁止恢复）；
  - **跨单位归一化拒绝与事务原子回滚**：
    - 录入端点传入异单位伪造归一化值（如原始单位为 `K`，规范单位为 `eV`）被严格阻断并返回 400；
    - 候选审核晋升端点传入异单位修正归一化值同样被阻断并返回 400；
    - 验证事务完全原子回滚，数据库中无任何文献、材料、样品或观测的半途脏残留；
  - **全链路 Request ID 透传与审计落地**：
    - 客户端不传递 `X-Request-ID` 时，服务端自动生成 UUIDv7；
    - 验证在响应头 `X-Request-ID` 与 MySQL 审计日志 `sys_audit_log.request_id` 中的值完全一致；
    - 覆盖人工录入、候选暂存、候选审核与观测审核全生命周期。

### 2.5 Docker Compose 编排与冒烟测试
```bash
docker compose config
docker compose up --build -d
docker compose ps
```
- **端口绑定**：
  - MySQL: `127.0.0.1:3306:3306`
  - FastAPI API: `127.0.0.1:8000:8000`
  - Nginx Web: `127.0.0.1:8080:80`
- **容器健康状态**：
  - `phasechangedb-mysql-1`: Up (healthy)
  - `phasechangedb-api-1`: Up
  - `phasechangedb-web-1`: Up

冒烟测试 HTTP 响应验证：
```bash
curl -fsS http://127.0.0.1:8000/health
# -> {"status":"ok"} (HTTP 200)

curl -fsS http://127.0.0.1:8000/ready
# -> {"status":"ready","database":"connected"} (HTTP 200)

curl -fsS http://127.0.0.1:8000/v1/dashboard
# -> 返回包含 materials, papers, observations, verified_observations, pending_outbox_events 的 JSON (HTTP 200)

curl -fsS -I http://127.0.0.1:8080/
# -> HTTP/1.1 200 OK (Nginx 前端页面)

curl -fsS http://127.0.0.1:8080/api/health
# -> {"status":"ok"} (Web 反向代理 API 正常)
```

### 2.6 数据持久性验证
1. 插入标有 `ACCEPTANCE_PERSISTENCE_RECORD` 的观测数据（ID: `01a077aa-3176-7c2d-82e8-d8f0d110d8f6`）；
2. 执行容器重启：`docker compose restart`；
3. 重启后再次查询：
```bash
curl -fsS http://127.0.0.1:8000/v1/workflow/observations/01a077aa-3176-7c2d-82e8-d8f0d110d8f6
```
- **输出结果**：成功返回该条记录及其材料、样品、测量条件与关联的证据原文，数据完好保留。

---

## 3. 真实剩余限制

1. **投影层 Worker 待落**：本轮保证 MySQL 权威事实写入并在同一事务生成标准 Outbox 事件；Elasticsearch 混合检索与 Neo4j 图谱投影将在下一里程碑接出。
2. **远程文档上传与自动抽取流水线**：当前接口负责登记和校验 S3/HTTPS 文档的存储 URI 与 SHA-256，属于文档元数据与对象存储引用登记；尚未接入实际的大文件直传或分片上传协议，也尚未挂载真实 OCR/多模态模型自动抽取流水线，提取数据目前通过候选端点以结构化载荷模拟暂存。
3. **权限边界**：本阶段采用单机共享的 Reviewer Token（`PCM_REVIEWER_TOKEN`）进行认证隔离，多租户与 RBAC 权限留待后续版本实现。
