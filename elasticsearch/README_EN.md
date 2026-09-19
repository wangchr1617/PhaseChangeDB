<div align="center">

# Search Projection Layer (Elasticsearch)

**Hybrid Lexical & Vector Search Architecture for PhaseChangeDB**

[**English**](README_EN.md) | [**简体中文**](README.md)

</div>

---

## 1. Architectural Role & Principles

In PhaseChangeDB, **MySQL 8.4 is the sole authoritative System of Record**. Elasticsearch serves strictly as a **read-only, disposable, and fully rebuildable derived projection layer**.

- **No Distributed Dual-Writes**: HTTP write APIs commit exclusively to MySQL; asynchronous outbox events stream updates to Elasticsearch;
- **Fault Isolation**: Outages or latency spikes in Elasticsearch never fail authoritative MySQL transactions;
- **Deterministic Rebuilding**: Index consumers are idempotent and support complete re-indexing from historical MySQL event logs at any time.

---

## 2. Hybrid Retrieval Strategy (Lexical + Vector with RRF)

Scientific queries on phase-change materials require exact token precision: chemical formulas (`Ge2Sb2Te5`), element symbols (`Sb`, `Te`), space groups (`R3m`, `Fm-3m`), and DOIs are case-sensitive and demand strict lexical matching. Vector-only retrieval often produces false positives and ungrounded hallucinations for these scientific entities.

PhaseChangeDB uses **BM25 Lexical + 1024-dim Dense Vector Hybrid Retrieval**:

```text
User Query ──┬──> BM25 Lexical Search (Exact match: formulas, DOIs, space groups, property codes) ──┐
             │                                                                                  ├──> Reciprocal Rank Fusion (RRF) ──> Final Ranked Results
             └──> Dense Vector Search (1024-dim: semantic intent & contextual similarity) ──────┘
```

- **Vector Constraints**: Pinned 1024-dimensional `dense_vector`. Changing the embedding model or dimension constitutes a new index generation (e.g., `v2`); never mix embeddings from different models in the same physical index;
- **Reciprocal Rank Fusion (RRF)**: Merges lexical and vector ranking lists, preserving precision for chemical entities while maintaining semantic flexibility for natural language queries.

---

## 3. Index Templates & Atomic Alias Switching

Applications **always query through stable aliases**, never connecting directly to physical index names. During re-indexing, the new generation index is populated first, followed by an atomic alias swap via `_aliases`.

### 3.1 Install Index Templates

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

### 3.2 Initialize Physical Indices and Bind Stable Aliases

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
