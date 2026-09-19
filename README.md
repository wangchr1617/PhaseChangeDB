<div align="center">

# PhaseChangeDB

**面向相变材料的、以证据为基础的科学数据库与知识发现平台**  
*An Evidence-Grounded Scientific Database and Knowledge Discovery Platform for Phase-Change Materials*

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/wangchr1617/PhaseChangeDB)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-009688.svg)](https://fastapi.tiangolo.com)
[![React 19](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev/)
[![MySQL 8.4 LTS](https://img.shields.io/badge/MySQL-8.4_LTS-4479A1.svg)](https://www.mysql.com/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

[**简体中文**](README.md) | [**English**](README_EN.md)

</div>

---

## 1. 项目愿景与科学背景

**PhaseChangeDB** 致力于解决相变材料（Phase-Change Materials, PCM）及相变存储器（PCRAM / 神经形态计算器件）研究领域长期存在的**数据碎片化、实验条件不可比、单位标准不统一及 AI 提取缺乏可溯源证据**的核心痛点。

在传统文献调研中：
- 关键物理性质（如结晶温度 $T_c$、熔点 $T_m$）高度依赖于**升温速率（Heating Rate）**与退火制备工艺，脱离具体测定条件的数值不具备科学横向可比性；
- 结晶活化能 $E_a$、脉冲结晶时间 $t_{\text{cryst}}$ 与薄膜电阻率 $\rho$ 报告单位多样（如 $\text{eV} \leftrightarrow \text{kJ/mol}$，$\text{s} \leftrightarrow \text{ns}$，$\Omega\cdot\text{cm} \leftrightarrow \Omega\cdot\text{m}$），手工汇总换算极易产生偏差；
- 大语言模型直接提取文献容易产生幻觉，缺乏精准对应到文献页码、图表与正文段落的可验证证据链（Evidence Traceability）。

PhaseChangeDB 将材料组成、实体样品、实验条件、测定观测与原始文献证据统一构建为严密的闭环数据链路，提供从“宏观知识图谱探索”到“跨文献物性横向对齐”，再到“原子级文献证据穿透”的全方位基础设施。

---

## 2. 🚀 快速上手 (Quick Start)

为满足实验科学家、计算材料学者与软件工程人员的不同使用习惯，平台提供三种开箱即用的运行方式：

### 方式一：GitHub Codespaces 云端一键运行（零安装 · 审稿与快速体验首选）

无需在本地电脑配置任何环境或安装软件，直接在网页浏览器中拉起专属的云端沙箱（支持在浏览器中直接上传本地 PDF 文献）：

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/wangchr1617/PhaseChangeDB)

1. 点击上方徽章，登录 GitHub 账号即可自动创建云端容器；
2. 容器启动后将自动执行初始化，并在右下角弹出浏览器直达通知；
3. 打开自动转发的 Web 端口（8080），即刻开始使用完整系统。

### 方式二：本地 Python 单命令直启（免 Docker · 免 MySQL · 免 Node.js）

只要您的电脑安装了 Python 3.11+，克隆代码后在项目根目录运行单启动脚本：

```bash
python run_demo.py
```

- **极简免编**：仓库已内置仅 460 KB 的预编译前端静态资源，无需配置 Node.js 或执行 pnpm 构建；
- **自适应科学演示模式**：若本地未运行 MySQL 8.4，启动器将自动平滑切换至【内置科学演示模式 (`PCM_DEMO_MODE=1`)】，预置真实的 GeTe、$\text{Sb}_2\text{Te}_3$ 等体系的核心物性分布、3D 知识图谱与文献证据，完全离线且杜绝运行时报错；
- **浏览器自动直达**：服务就绪后，脚本会自动拉起系统默认浏览器访问 `http://localhost:8000`。

### 方式三：Docker Compose 完整生产集群部署（开发与长期运维）

适合需要完整 MySQL 8.4 事务保障、持久化数据存储与长期部署的场景：

```bash
# 1. 复制环境变量配置文件
cp .env.example .env

# 2. 构建并启动容器集群
docker compose up -d

# 3. 访问服务
# Web 交互界面: http://localhost:8080
# Swagger API 文档: http://localhost:8000/docs
# 系统存活/就绪探针: http://localhost:8000/health , http://localhost:8000/ready
```

停止服务时执行：
```bash
docker compose down
```

---

## 3. 核心科学特性

### 3.1 跨文献物性横向对比看板 (Cross-Paper Property Comparison & Alignment)
- **多体系同屏对比**：支持同时勾选 GeTe、$\text{Sb}_2\text{Te}_3$、$\text{Ge}_2\text{Sb}_2\text{Te}_5$ (GST) 等多种基体材料及各类掺杂体系（Bi、In、N、C、Ti、Sc 等）；
- **实验条件严格对齐**：支持按升温速率（如 10 K/min、20 K/min、40 K/min）与基底条件动态过滤，确保横向对比符合相变动力学规律；
- **动态科学单位换算**：
  - 温度参数（$T_c, T_m, T_g$）：支持 $\text{K} \leftrightarrow \text{°C}$ 实时换算；
  - 激活能参数（$E_a$）：支持 $\text{eV} \leftrightarrow \text{kJ/mol}$ 实时换算（$1\text{ eV} \approx 96.4853\text{ kJ/mol}$）；
  - 时间参数（$t_{\text{cryst}}$）：支持 $\text{s} \leftrightarrow \text{ns}$ 换算；
  - 电阻率（$\rho$）：支持 $\Omega\cdot\text{cm} \leftrightarrow \Omega\cdot\text{m}$ 换算；
- **全要素科学证据抽屉**：点击任意散点或表格项，侧边栏无刷新滑出，穿透查看名义化学式、掺杂比例、文献出处、DOI 外部链接、图表定位（如 `Figure 3(a)`）及正文证据摘录片段（Evidence Fragment）。

### 3.2 细粒度科学知识图谱 (Fine-Grained Evidence Knowledge Graph)
- **多维度图谱视角切换**：
  - `🔬 宏观科学网络` (Core Macro Graph)：展示材料组成、化学元素与标准物性指标的核心骨干拓扑；
  - `🔗 细粒度物性证据链` (Fine-Grained Evidence Graph)：贯通【基体材料】$\rightarrow$【掺杂样品】$\rightarrow$【实测物性 (带升温速率)】$\rightarrow$【出处文献】$\rightarrow$【作者】全证据链；
  - `📚 材料文献星丛` (Literature Subgraph)：以特定材料为核心，展示其关联学术文献、作者群与收录期刊；
- **单节点关联子图动态聚焦**：
  - 单击节点呼出浮动控制条与侧边栏控制器；
  - 支持 **一级关联（直接邻居）**、**二级关联（次级外延）** 与 **三级关联（深度拓扑）** 自由切换，隐藏无关噪点；
  - 设置 80 节点防掉帧安全上限与毫秒级拓扑提取耗时监控，支持一键“返回全图”。

### 3.3 文献智能解析与受控专家审核流 (Scientist Agent & Curated Intake)
- **多模态文献提取流水线**：支持单篇或批量上传 PDF 压缩包（如 1000 篇文献包），自动化解析元数据、化学式、相变物性与测定条件；
- **暂存区严格隔离**：AI 与模型提取结果只能写入暂存表（`ext_candidate`），记录模型名称、版本、提示词工程版本与本体版本；**严禁未审核模型输出直接污染权威库**；
- **专家审核晋升状态机**：
  - 审核流转：`AI_EXTRACTED` $\rightarrow$ `HUMAN_REVIEWED` $\rightarrow$ `VERIFIED`，支持 `DISPUTED`（争议存疑）与 `RETRACTED`（学术撤回）；
  - 晋升为正式观测记录时，在单个 MySQL 事务中原子创建材料、样品、测量记录及不可变审核轨迹。

---

## 4. 架构原则与科学数据不变量

为保证学术数据的严谨性与系统稳定性，系统严格恪守以下架构不变量：

```text
客户端 (Web / CLI) -> FastAPI 路由 -> 应用编排服务 -> 领域校验
                    -> 仓储协议 -> MySQL 8.4 (权威事实源) + Outbox 事件
                                          |
                                    (异步工作进程)
                                          v
                    Elasticsearch 检索投影 / Neo4j 拓扑投影 / 对象存储
```

1. **权威事实源与投影分离**：
   - MySQL 8.4/InnoDB 是系统唯一的权威事实源（System of Record）；
   - Elasticsearch 与 Neo4j 作为可丢弃、可重建的只读投影层，两者的可用性不影响权威写入事务；
2. **材料与实体样品分离**：
   - `Material` 表达化学组成与理想材料身份；`Sample` 表达具备具体制备工艺、掺杂浓度、几何尺寸与实验上下文的实体样品；
3. **测量主体与条件不变量**：
   - 一条 `Observation` 必须且仅能关联一个主体（`sample_id`、`device_id` 或 `calculation_id`）；
   - 归一化时必须同时保留原始报告数值与原始单位（`original_*`）；
   - 浮点精度要求严格的小数统一持久化为 MySQL `DECIMAL` 类型，杜绝二进制浮点精度漂移；
4. **标识与并发控制**：
   - 实体 ID 应用层采用 UUIDv7，MySQL 内部使用 `BINARY(16)` 紧凑高效存储；
   - 核心可变实体采用乐观并发控制（`row_version`），变更请求需提供 `If-Match` 头防范丢失更新。

---

## 5. 项目代码结构

```text
PhaseChangeDB/
├── .devcontainer/             # GitHub Codespaces 云端沙箱配置
├── app/
│   ├── api/                   # HTTP 传输适配层与 FastAPI 路由端点
│   ├── application/           # 业务用例编排、文献解析与工作流服务
│   ├── core/                  # 配置管理、安全认证与环境设定
│   ├── demo/                  # 离线科学演示数据源与降级仓储实现
│   ├── domain/                # 领域核心实体、物性提取 Schema 与不变量校验
│   ├── infrastructure/        # MySQL 仓储、数据库连接与提取实现
│   ├── models/                # 公共 Pydantic 请求与响应契约模型
│   └── static/                # 内置预编译前端生产静态资源 (460 KB)
├── docs/                      # 架构决策记录 (ADR) 与本地验收文档
├── elasticsearch/             # 检索投影配置、索引模板与 RRF 说明
├── frontend/                  # React 19 + TypeScript + Vite 前端应用源码
├── mysql/                     # MySQL 8.4 权威数据模式初始化脚本
├── neo4j/                     # 知识图谱拓扑投影规则与节点定义
├── scripts/                   # 自动化运维、契约生成与辅助工具
├── tests/                     # 单元测试、集成测试与 API 契约测试
├── compose.yaml               # Docker Compose 集群服务定义
├── pyproject.toml             # Python 项目元数据与依赖定义
├── run_demo.py                # 跨平台单命令免配置启动器
└── README.md                  # 中文主文档 (当前文档)
```

---

## 6. 开发、测试与代码规范

本仓库采用固定锁文件的现代工具链以确保可复现构建：

### 6.1 后端环境与测试

```bash
# 1. 静态检查与代码风格审查
uv run ruff check app tests scripts

# 2. 运行单元测试与契约测试
uv run pytest

# 3. 运行含真实 MySQL 8.4 容器的全套集成测试
PCM_INTEGRATION=1 uv run pytest

# 4. 重新导出标准 openapi.json (禁止手工编辑生成文件)
uv run python scripts/generate_openapi.py
```

### 6.2 前端代码与构建

```bash
# 1. 代码风格审查
corepack pnpm --dir frontend lint

# 2. TypeScript 类型静态检查
corepack pnpm --dir frontend typecheck

# 3. 生产环境静态打包
corepack pnpm --dir frontend build
```

---

## 7. 路线图 (Roadmap)

- [x] **v0.1.0**：核心材料库、文献目录、观测记录与审核状态机打通；
- [x] **v0.2.0**：细粒度科学知识图谱多级关联、跨文献物性横向对比看板、实验条件动态归一化与 Codespaces 支持；
- [ ] **v0.3.0**：接入 Elasticsearch 词法与密集向量（Dense Vector）RRF 混合检索投影；
- [ ] **v0.4.0**：接入 Neo4j 图数据库执行多跳复杂科学关系路径推理与假说发现；
- [ ] **v0.5.0**：第一性原理 DFT 计算数据接入（电子能带结构、声子谱与相变势能面）。

---

## 8. 引用与致谢 (Citation)

如果您在相变材料研究、文献数据挖掘或科学发现中使用了 PhaseChangeDB，欢迎引用本项目：

```bibtex
@software{phasechangedb2026,
  author       = {PhaseChangeDB Contributors},
  title        = {PhaseChangeDB: Evidence-Grounded Scientific Database and Knowledge Discovery Platform for Phase-Change Materials},
  year         = {2026},
  publisher    = {GitHub},
  journal      = {GitHub repository},
  howpublished = {\url{https://github.com/wangchr1617/PhaseChangeDB}}
}
```

---

## 9. 开源许可证 (License)

本项目采用 [Apache License 2.0](LICENSE) 开源许可证。
