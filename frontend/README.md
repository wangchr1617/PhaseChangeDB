<div align="center">

# PhaseChangeDB 前端应用

**面向相变材料的科学可视化、知识图谱与证据对齐界面**  
*Scientific Visualization, Knowledge Graph & Evidence Alignment Web UI for PhaseChangeDB*

[**简体中文**](README.md) | [**English**](README_EN.md)

</div>

---

## 1. 架构定位与技术栈

PhaseChangeDB 前端是一个采用现代 Web 标准构建的单页应用（SPA），专注于为相变材料领域的科研工作者提供直观、严谨的数据检索、科学可视化与证据溯源交互。

- **核心框架**：React 19 + TypeScript 5
- **构建工具**：Vite 8
- **包管理器**：pnpm (通过 corepack 管理，锁文件为 `pnpm-lock.yaml`)
- **可视化引擎**：纯原生 SVG 高性能渲染（杜绝沉重的第三方图表库黑盒，实现精准的坐标变换与毫秒级渲染）
- **图谱仿真**：基于广度优先搜索 (BFS) 与无向邻接索引的多级关联力导向子图引擎

---

## 2. 核心模块与组件设计

```text
frontend/src/
├── api/                       # 后端 API 强类型客户端与请求封装
├── components/
│   ├── PropertyComparisonBoard.tsx    # 跨文献物性横向对比看板 (散点/箱线/单位换算/证据抽屉)
│   ├── KnowledgeGraphPlaceholder.tsx  # 细粒度科学知识图谱 (BFS多级子图聚焦/三重视角)
│   ├── LiteratureAgentView.tsx        # 相变文献智能解析智能体 (多模态工作流与模型配置)
│   ├── Workflow.tsx                   # 科学数据录入与专家审核状态机操作面板
│   ├── PeriodicTable.tsx              # 元素周期表联动筛选器 (支持多选与本地记忆)
│   ├── BatchUploadModal.tsx           # 文献批量上传与多模态解析触发弹窗
│   └── LiteratureStatsView.tsx        # 文献摄取统计与年份/期刊分布
├── types/                     # 与后端 OpenAPI 契约严格对齐的 TypeScript 接口
├── App.tsx                    # 应用主外壳、视图切换与全局检索
└── App.css                    # 统一科学设计系统与响应式流式排版
```

### 关键组件功能：
1. **物性横向对比看板 (`PropertyComparisonBoard`)**：
   - 支持多材料体系（GeTe, $\text{Sb}_2\text{Te}_3$, GST 等）同屏多选对比；
   - 升温速率等温对齐（10 K/min, 20 K/min, 40 K/min）；
   - SI 与工程单位实时无损互转（K / °C, eV / kJ·mol⁻¹, s / ns, $\Omega\cdot\text{cm}$ / $\Omega\cdot\text{m}$）；
   - 交互式散点图、五数概括箱线统计图与右侧滑出式证据穿透抽屉。
2. **细粒度知识图谱 (`KnowledgeGraphPlaceholder`)**：
   - 提供“宏观科学网络”、“细粒度证据链”与“文献星丛”三重视角；
   - 单节点单击触发 BFS 关联子图提取，支持 1 级（直连）、2 级（次级）与 3 级（深度）关联子图即时隔离；
   - 具备 80 节点防卡死保护机制与毫秒级图谱计算耗时监控。
3. **元素周期表与多维筛选器 (`PeriodicTable`)**：
   - 与材料库无缝联动，支持按化学元素组合、相变温度区间、潜热阈值及低毒/成本可控性进行联合过滤。

---

## 3. 双运行模式支持

前端被设计为具备极高环境适应性的双重运行架构：

1. **反向代理模式（生产容器集群）**：
   - 由 Nginx 容器提供静态托管，并将 `/api/*` 请求透明代理至后端 FastAPI（端口 8000）；
   - 访问地址：`http://localhost:8080`。
2. **直连模式（单进程免配置启动器）**：
   - 编译后的产物内置于后端 `app/static/` 目录，直接由 FastAPI 静态文件服务提供；
   - 无需任何 Node.js、pnpm 或 Nginx 依赖，运行 `python run_demo.py` 即可在 `http://localhost:8000` 完整使用。

---

## 4. 本地开发与工程命令

```bash
# 1. 安装依赖
corepack pnpm install

# 2. 启动本地热重载开发服务器 (默认端口 5173，自动代理 /api 至 8000)
corepack pnpm dev

# 3. 执行 TypeScript 静态类型检查
corepack pnpm typecheck

# 4. 执行代码风格与语法检查
corepack pnpm lint

# 5. 生产构建打包 (产物输出至 dist/)
corepack pnpm build
```
