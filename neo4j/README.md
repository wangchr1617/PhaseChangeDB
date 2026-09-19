<div align="center">

# PhaseChangeDB 知识图谱拓扑投影层 (Neo4j)

**面向相变材料多维关系的图拓扑投影与推理架构**  
*Graph Topology Projection & Scientific Discovery for PhaseChangeDB*

[**简体中文**](README.md) | [**English**](README_EN.md)

</div>

---

## 1. 架构定位与投影原则

在 PhaseChangeDB 中，Neo4j 作为**只读的科学关系拓扑投影层**存在，用于支持多跳科学关系遍历、材料微观结构关联发现与知识盲区推断。

- **非权威数据源**：图数据库不作为事实存储源，所有拓扑节点与关系边均通过消费 MySQL Outbox 事务事件异步产生；
- **随时可重建性**：当图模式变更或数据产生漂移时，可通过 Outbox 事件回放或全量快照一键重构完整图谱；
- **故障隔离**：Neo4j 服务的不可用不得阻断任何上游业务 API 的正常写入。

---

## 2. 节点标识与图本体规范 (Identity & Ontology)

1. **全局统一 UUID**：除元素节点外，所有实体（`Material`、`Sample`、`Observation`、`Paper`、`Author`、`Journal` 等）的节点 ID 均必须采用规范的**小写 UUIDv7 字符串**，与 MySQL 保持严格一对一映射；
2. **化学元素特例 (`Element`)**：化学元素以区分大小写的标准元素符号作为自然唯一标识（如 `Ge`、`Sb`、`Te`、`Bi`）；
3. **严禁图层幽灵实体**：禁止直接在 Neo4j 中创建在 MySQL 权威库中不存在的独立科学实体。

---

## 3. 幂等消费与学术状态投影 (Idempotency & State Lifecycle)

- **幂等写入保障**：所有投影事件消费者必须安全可重试。Cypher 语句一律采用基于唯一约束标识的 `MERGE`，然后执行 `SET` 更新属性及 `MERGE` 关联关系；
- **科学状态保留而不物理删除**：
  - 在相变材料研究中，文献撤回（`RETRACTED`）与实验数据争议（`DISPUTED`）本身是极具价值的科学历史记录；
  - 科学记录发生变更时，应通过改变节点状态属性（如 `status = 'RETRACTED'`）进行投影流转，严禁直接在图谱中物理抹除节点；物理删除仅保留用于测试环境或系统级垃圾清理。

---

## 4. 关键 Outbox 事件模型

- `MaterialCreated`, `MaterialUpdated`
- `SampleCreated`, `SampleUpdated`
- `ObservationCreated`, `ObservationVerified`, `ObservationRetracted`
- `EvidenceCreated`
- `ClaimCreated`, `ClaimVerified`, `ClaimDisputed`
- `KnowledgeGapComputed`
