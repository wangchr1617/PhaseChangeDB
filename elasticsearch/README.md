<div align="center">

# PhaseChangeDB 检索投影层 (Elasticsearch)

**面向相变材料科学数据的词法与向量混合检索架构**  
*Hybrid Lexical & Vector Search Projection for PhaseChangeDB*

[**简体中文**](README.md) | [**English**](README_EN.md)

</div>

---

## 1. 架构定位与基本原则

在 PhaseChangeDB 的架构体系中，**MySQL 8.4 是唯一的权威事实源（System of Record）**，Elasticsearch 属于**只读、可丢弃且随时可全量重构的派生投影层**。

- **禁止跨库分布式事务**：业务 API 写入只提交至 MySQL，并通过事务内落库的 Outbox 事件表异步同步至 Elasticsearch；
- **故障隔离保障**：Elasticsearch 实例的不可用、网络抖动或重建重放，严禁阻断或导致 MySQL 权威数据的写入失败；
- **确定性重建能力**：投影消费者必须具备幂等性，任何时候均可从 MySQL 历史数据流中安全重放与完整重建索引。

---

## 2. 混合检索策略 (Hybrid Retrieval & RRF)

相变材料领域的检索具有高度的科学专业性：化学式（如 `Ge2Sb2Te5`）、元素符号（如 `Sb`、`Te`）、空间群（如 `R3m`、`Fm-3m`）与 DOI 区分大小写且要求严格匹配，纯向量检索（Vector-only RAG）在处理此类实体时极易产生幻觉与查准率崩塌。

因此，PhaseChangeDB 采用 **词法检索 + 向量检索混合融合方案**：

```text
用户查询 (Query) ──┬──> BM25 词法检索 (精确匹配: 化学式、DOI、空间群、属性代码) ──┐
                  │                                                              ├──> 倒数排名融合 (RRF) ──> 最终排序结果
                  └──> 稠密向量检索 (1024-dim Dense Vector: 语义相似度) ─────────┘
```

- **向量配置**：使用不可变的 1024 维 `dense_vector`（固定多语言科学嵌入配置）；若更换嵌入模型或调整维度，必须升级索引代际（如 `v2`）并全量重建，严禁在同一物理索引中混合不同模型的向量；
- **倒数排名融合 (Reciprocal Rank Fusion, RRF)**：合并两路检索得分，确保化学式与专业实体的精确性，同时兼具自然语言问答的语义泛化能力。

---

## 3. 索引模板与零停机别名切换 (Atomic Alias Switching)

应用程序代码**必须始终通过稳定的 Alias 别名进行读取**，严禁直连物理索引名。在全量重建期间，先向新物理索引写入数据，随后通过 `_aliases` 端点执行原子切换。

### 3.1 安装索引模板

```bash
export ES_URL="http://localhost:9200"

curl -X PUT "$ES_URL/_index_template/pcm-papers-v1" \
  -H 'Content-Type: application/json' --data-binary @pcm-papers-template.json
curl -X PUT "$ES_URL/_index_template/pcm-evidence-v1" \
  -H 'Content-Type: application/json' --data-binary @pcm-evidence-template.json
curl -X PUT "$ES_URL/_index_template/pcm-materials-v1" \
  -H 'Content-Type: application/json' --data-binary @pcm-materials-template.json
curl -X PUT "$ES_URL/_index_template/pcm-observations-v1" \
  -H 'Content-Type: application/json' --data-binary @pcm-observations-template.json
curl -X PUT "$ES_URL/_index_template/pcm-claims-v1" \
  -H 'Content-Type: application/json' --data-binary @pcm-claims-template.json
```

### 3.2 创建初始物理索引并绑定稳定 Alias

```bash
curl -X PUT "$ES_URL/pcm-papers-v1-000001"
curl -X PUT "$ES_URL/pcm-evidence-v1-000001"
curl -X PUT "$ES_URL/pcm-materials-v1-000001"
curl -X PUT "$ES_URL/pcm-observations-v1-000001"
curl -X PUT "$ES_URL/pcm-claims-v1-000001"

curl -X POST "$ES_URL/_aliases" -H 'Content-Type: application/json' -d '{
  "actions": [
    {"add": {"index": "pcm-papers-v1-000001", "alias": "pcm-papers"}},
    {"add": {"index": "pcm-evidence-v1-000001", "alias": "pcm-evidence"}},
    {"add": {"index": "pcm-materials-v1-000001", "alias": "pcm-materials"}},
    {"add": {"index": "pcm-observations-v1-000001", "alias": "pcm-observations"}},
    {"add": {"index": "pcm-claims-v1-000001", "alias": "pcm-claims"}}
  ]
}'
```
