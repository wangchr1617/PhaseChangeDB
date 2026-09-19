<div align="center">

# PhaseChangeDB

**An Evidence-Grounded Scientific Database and Knowledge Discovery Platform for Phase-Change Materials**

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/wangchr1617/PhaseChangeDB)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-009688.svg)](https://fastapi.tiangolo.com)
[![React 19](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev/)
[![MySQL 8.4 LTS](https://img.shields.io/badge/MySQL-8.4_LTS-4479A1.svg)](https://www.mysql.com/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

[**English**](README_EN.md) | [**简体中文**](README.md)

</div>

---

## 1. Vision & Scientific Background

**PhaseChangeDB** is an open-source scientific database and knowledge discovery infrastructure tailored for phase-change materials (PCM) and phase-change memory devices (PCRAM / neuromorphic computing architectures).

In empirical materials science literature:
- Key physical properties such as crystallization temperature ($T_c$) and melting temperature ($T_m$) strongly depend on **heating rates** and annealing protocols; comparing raw reported numbers across papers without condition alignment leads to severe systematic errors;
- Kinetic and transport parameters like activation energy ($E_a$), crystallization speed ($t_{\text{cryst}}$), and film resistivity ($\rho$) are reported in fragmented physical units ($\text{eV} \leftrightarrow \text{kJ/mol}$, $\text{s} \leftrightarrow \text{ns}$, $\Omega\cdot\text{cm} \leftrightarrow \Omega\cdot\text{m}$);
- Generative AI and LLMs often hallucinate scientific quantities when queried directly, lacking fine-grained evidentiary grounding in specific document pages, figures, tables, and text excerpts.

PhaseChangeDB structures chemical compositions, physical samples, measurement conditions, scientific observations, and verbatim literature evidence into a traceable, reproducible data loop. It provides an end-to-end platform bridging macro-level scientific knowledge graphs, cross-paper property alignment dashboards, and atomic-level evidence provenance.

---

## 2. 🚀 Quick Start

To support experimental researchers, computational materials scientists, and software engineers alike, PhaseChangeDB provides three friction-free execution modes:

### Mode 1: GitHub Codespaces (Zero Installation · Recommended for Peer Review)

Run the entire system in a sandboxed Linux container inside your browser without installing anything on your machine (supports uploading or dragging local PDF papers directly):

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/wangchr1617/PhaseChangeDB)

1. Click the badge above to spin up a private cloud VM via GitHub;
2. Once initialized, Codespaces automatically forwards port 8080 and notifies you with a link;
3. Open port 8080 in your browser to immediately use the full Web UI.

### Mode 2: Local Single-Command Runner (No Docker · No MySQL · No Node.js)

If you have Python 3.11+ installed, simply clone the repository and run:

```bash
python run_demo.py
```

- **Built-in Precompiled Frontend**: The repository ships with a 460 KB precompiled static bundle, eliminating the need to install Node.js, corepack, or pnpm;
- **Automatic Scientific Demo Fallback (`PCM_DEMO_MODE=1`)**: If a local MySQL 8.4 instance is not detected, the launcher automatically falls back to an offline scientific demo mode preloaded with authentic GeTe, $\text{Sb}_2\text{Te}_3$, and GST data points, 3D evidence graphs, and cross-paper comparisons;
- **Browser Auto-Launch**: Automatically opens `http://localhost:8000` in your default browser once the service is ready.

### Mode 3: Docker Compose Full Cluster (Production & Local Development)

Ideal for production deployments and environments requiring transactional ACID persistence:

```bash
# 1. Setup local environment variables
cp .env.example .env

# 2. Build and launch services in background
docker compose up -d

# 3. Access endpoints
# Web Dashboard: http://localhost:8080
# Swagger API Docs: http://localhost:8000/docs
# Liveness & Readiness Probes: http://localhost:8000/health , http://localhost:8000/ready
```

To stop the cluster:
```bash
docker compose down
```

---

## 3. Core Scientific Features

### 3.1 Cross-Paper Property Comparison & Alignment
- **Multi-System Concurrent Comparison**: Simultaneously select and compare multiple material families (GeTe, $\text{Sb}_2\text{Te}_3$, GST) across various dopants (Bi, In, N, C, Ti, Sc, etc.);
- **Experimental Condition Alignment**: Dynamically filter and align by heating rate (e.g., 10 K/min, 20 K/min, 40 K/min) and substrate type, adhering strictly to non-isothermal crystallization kinetics;
- **Dynamic Scientific Unit Conversion**:
  - Temperature ($T_c, T_m, T_g$): Real-time conversion between $\text{K} \leftrightarrow \text{°C}$;
  - Activation Energy ($E_a$): Seamless switching between $\text{eV} \leftrightarrow \text{kJ/mol}$ ($1\text{ eV} \approx 96.4853\text{ kJ/mol}$);
  - Crystallization Time ($t_{\text{cryst}}$): Toggle between $\text{s} \leftrightarrow \text{ns}$;
  - Resistivity ($\rho$): Switch between $\Omega\cdot\text{cm} \leftrightarrow \Omega\cdot\text{m}$;
- **Evidence Traceability Drawer**: Click any scatter point or table row to slide out the evidentiary drawer, inspecting nominal formula, dopant concentration, paper DOI, figure/table citation (e.g., `Figure 3(a)`), and verbatim text excerpts.

### 3.2 Fine-Grained Scientific Knowledge Graph
- **Three Perspective Views**:
  - `🔬 Core Macro Graph`: Top-level backbone showing material compositions, chemical elements, and standardized properties;
  - `🔗 Fine-Grained Evidence Graph`: Full-chain lineage connecting [Matrix Material] $\rightarrow$ [Doped Sample] $\rightarrow$ [Observation (with heating rate)] $\rightarrow$ [Paper] $\rightarrow$ [Author];
  - `📚 Literature Subgraph`: Ego-network centered on a specific material, highlighting citation clusters, author networks, and journal distributions;
- **Ego-Network Association Subgraph Filter**:
  - Click any node to open floating controls and sidebar depth options;
  - Select between **1st-Degree (direct neighbors)**, **2nd-Degree (extended network)**, and **3rd-Degree** association depths;
  - Built-in 80-node safety threshold and sub-millisecond graph extraction profiling to ensure 60 FPS smooth rendering.

### 3.3 Scientist Agent & Curated Ingestion Workflow
- **Multi-Modal Literature Ingestion**: Ingest single papers or batch archives (e.g., 1,000 PDF papers), parsing metadata, chemical formulas, and phase-transition properties;
- **Strict Staging Isolation**: AI extractions are strictly written to staging tables (`ext_candidate`), recording model name, prompt engineering version, ontology version, and confidence scores; **unvetted AI predictions never directly contaminate authoritative tables**;
- **Curator Promotion State Machine**:
  - Progression: `AI_EXTRACTED` $\rightarrow$ `HUMAN_REVIEWED` $\rightarrow$ `VERIFIED`, with support for scientific dispute (`DISPUTED`) and retraction (`RETRACTED`);
  - Formal promotion atomically creates samples, measurements, observations, and immutable audit logs within a single MySQL transaction.

---

## 4. Architectural Invariants

PhaseChangeDB enforces strict domain invariants to guarantee data reproducibility and consistency:

```text
Client (Web / CLI) -> FastAPI Router -> Application Orchestrator -> Domain Validation
                    -> Repository Protocol -> MySQL 8.4 (System of Record) + Outbox Events
                                                     |
                                            (Async Background Workers)
                                                     v
                    Elasticsearch Projections / Neo4j Graph Projections / S3 Object Store
```

1. **System of Record vs. Projections**:
   - MySQL 8.4/InnoDB is the sole authoritative system of record;
   - Elasticsearch and Neo4j are disposable, rebuildable read projections; their downtime never impacts authoritative write transactions;
2. **Material vs. Sample Separation**:
   - `Material` models chemical composition and identity; `Sample` represents an empirical specimen or simulation instance with specific thickness, substrate, and fabrication history;
3. **Observation & Condition Invariants**:
   - Every observation belongs to exactly one subject (`sample_id`, `device_id`, or `calculation_id`);
   - Both normalized SI values and original reported text/units (`original_*`) are permanently preserved;
   - Decimal quantities are stored as MySQL `DECIMAL` to eliminate floating-point drift;
4. **Identity & Concurrency Control**:
   - Entity IDs use UUIDv7, stored compactly as `BINARY(16)` in MySQL;
   - Mutable entities enforce optimistic concurrency control via `row_version` and `If-Match` precondition headers.

---

## 5. Repository Structure

```text
PhaseChangeDB/
├── .devcontainer/             # GitHub Codespaces cloud container configuration
├── app/
│   ├── api/                   # HTTP routers and transmission adapters
│   ├── application/           # Use cases, literature parser, and workflow orchestrators
│   ├── core/                  # Settings, configuration, and security tokens
│   ├── demo/                  # Offline scientific demo dataset and fallback repository
│   ├── domain/                # Scientific entities, extraction schemas, and invariants
│   ├── infrastructure/        # MySQL repositories, database pooling, and extractors
│   ├── models/                # Public Pydantic API schemas
│   └── static/                # Precompiled production frontend static bundle (460 KB)
├── docs/                      # Architectural Decision Records (ADRs) and reports
├── elasticsearch/             # Search templates, dense vector mapping, and RRF configs
├── frontend/                  # React 19 + TypeScript + Vite frontend source code
├── mysql/                     # MySQL 8.4 schema definitions and migrations
├── neo4j/                     # Knowledge graph schema and projection rules
├── scripts/                   # Auxiliary CLI tools and OpenAPI generator
├── tests/                     # Unit, integration, and contract tests
├── compose.yaml               # Docker Compose service orchestration
├── pyproject.toml             # Python packaging and dependency declarations
├── run_demo.py                # Cross-platform zero-dependency launcher
├── README.md                  # Chinese Documentation
└── README_EN.md               # English Documentation (this file)
```

---

## 6. Development & Testing

We rely on pinned lockfiles for deterministic local and CI builds:

### 6.1 Backend Tests & Quality Checks

```bash
# 1. Lint and format checking
uv run ruff check app tests scripts

# 2. Run unit and contract tests
uv run pytest

# 3. Run full integration suite against real MySQL 8.4
PCM_INTEGRATION=1 uv run pytest

# 4. Re-export official openapi.json (never edit manually)
uv run python scripts/generate_openapi.py
```

### 6.2 Frontend Build & Verification

```bash
# 1. Code style audit
corepack pnpm --dir frontend lint

# 2. TypeScript type check
corepack pnpm --dir frontend typecheck

# 3. Production build
corepack pnpm --dir frontend build
```

---

## 7. Roadmap

- [x] **v0.1.0**: Core materials, papers, observations, and review state machine;
- [x] **v0.2.0**: Multi-level association knowledge graph, cross-paper comparison board, dynamic condition normalization, and Codespaces integration;
- [ ] **v0.3.0**: Elasticsearch lexical + 1024-dim dense vector hybrid search with Reciprocal Rank Fusion (RRF);
- [ ] **v0.4.0**: Neo4j graph projection engine for complex multi-hop path inference;
- [ ] **v0.5.0**: Ab-initio DFT calculation ingestion (band structures, phonon dispersion, and phase transition barriers).

---

## 8. Citation

If you use PhaseChangeDB in your research, literature extraction pipelines, or device simulations, please cite:

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

## 9. License

PhaseChangeDB is licensed under the [Apache License 2.0](LICENSE).
