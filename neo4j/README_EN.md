<div align="center">

# Knowledge Graph Projection Layer (Neo4j)

**Graph Topology Projection & Scientific Discovery for PhaseChangeDB**

[**English**](README_EN.md) | [**简体中文**](README.md)

</div>

---

## 1. Architectural Role & Principles

In PhaseChangeDB, Neo4j serves strictly as a **read-only scientific graph topology projection layer**, designed for multi-hop relation traversals, material structure-property lineage exploration, and scientific hypothesis generation.

- **Non-Authoritative Projection**: The graph database is never a primary source of truth; all nodes and edges are derived asynchronously by consuming MySQL Outbox transaction events;
- **Rebuildable by Design**: The entire graph can be torn down and reconstituted deterministically from the MySQL event store whenever schemas evolve or projections drift;
- **Fault Isolation**: Outages or performance bottlenecks in Neo4j must never disrupt or block upstream write operations.

---

## 2. Identity & Graph Ontology Rules

1. **Canonical UUIDs**: With the exception of chemical elements, all entity nodes (`Material`, `Sample`, `Observation`, `Paper`, `Author`, `Journal`, etc.) must use canonical lower-case UUIDv7 strings matching MySQL primary keys;
2. **Chemical Element Exception (`Element`)**: Chemical elements use their case-sensitive IUPAC symbol as their unique natural identifier (`Ge`, `Sb`, `Te`, `Bi`);
3. **No Phantom Graph Entities**: Independent scientific entities must never be created solely within the graph layer without corresponding records in MySQL.

---

## 3. Idempotency & Scientific Lifecycle

- **Idempotent Handlers**: Every projector handler must be safely retryable. Cypher statements must use `MERGE` on the constrained identifier, followed by `SET` for mutable properties and `MERGE` for relationships;
- **State Projection Over Physical Deletion**:
  - In scientific inquiry, document retractions (`RETRACTED`) and disputed measurements (`DISPUTED`) are meaningful scientific states;
  - Projectors must update node status properties (`status: 'RETRACTED'`) rather than physically dropping nodes from the graph; physical deletion is reserved solely for data cleanup or testing.

---

## 4. Key Outbox Event Types

- `MaterialCreated`, `MaterialUpdated`
- `SampleCreated`, `SampleUpdated`
- `ObservationCreated`, `ObservationVerified`, `ObservationRetracted`
- `EvidenceCreated`
- `ClaimCreated`, `ClaimVerified`, `ClaimDisputed`
- `KnowledgeGapComputed`
