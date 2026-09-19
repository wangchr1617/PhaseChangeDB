<div align="center">

# PhaseChangeDB Frontend Application

**Scientific Visualization, Knowledge Graph & Evidence Alignment Web UI for PhaseChangeDB**

[**English**](README_EN.md) | [**简体中文**](README.md)

</div>

---

## 1. Architectural Positioning & Tech Stack

The PhaseChangeDB frontend is a modern Single Page Application (SPA) built to scientific standards, engineered to provide materials researchers with intuitive exploration, rigorous visualization, and verifiable literature provenance.

- **Core Framework**: React 19 + TypeScript 5
- **Build Tool**: Vite 8
- **Package Manager**: pnpm (managed via corepack, locked with `pnpm-lock.yaml`)
- **Visualization Engine**: Native SVG rendering (avoiding bloated chart library abstractions to ensure exact coordinate transforms and sub-millisecond redraws)
- **Graph Simulation**: Force-directed layout engine coupled with Breadth-First Search (BFS) and bidirectional adjacency indexing for sub-graph isolation

---

## 2. Component Architecture

```text
frontend/src/
├── api/                       # Typed HTTP client services
├── components/
│   ├── PropertyComparisonBoard.tsx    # Cross-paper property comparison (scatter, boxplot, units, drawer)
│   ├── KnowledgeGraphPlaceholder.tsx  # Fine-grained knowledge graph (BFS subgraphs, 3 views)
│   ├── LiteratureAgentView.tsx        # Scientist agent workflow and model configurations
│   ├── Workflow.tsx                   # Intake form & curator promotion state machine
│   ├── PeriodicTable.tsx              # Interactive periodic table filter with local state persistence
│   ├── BatchUploadModal.tsx           # Batch document upload & parser invocation modal
│   └── LiteratureStatsView.tsx        # Ingestion analytics & year/journal distribution
├── types/                     # TypeScript interfaces strictly aligned with OpenAPI schemas
├── App.tsx                    # Main app shell, navigation, and global lexical search
└── App.css                    # Design tokens, typography, and responsive grid layout
```

### Key Highlights:
1. **Property Comparison Board (`PropertyComparisonBoard`)**:
   - Multi-system selection (GeTe, $\text{Sb}_2\text{Te}_3$, GST) with dopant grouping;
   - Heating rate condition alignment (10 K/min, 20 K/min, 40 K/min);
   - Lossless unit conversion ($\text{K} \leftrightarrow \text{°C}$, $\text{eV} \leftrightarrow \text{kJ/mol}$, $\text{s} \leftrightarrow \text{ns}$, $\Omega\cdot\text{cm} \leftrightarrow \Omega\cdot\text{m}$);
   - Interactive scatter plots, five-number summary box plots, and a sliding evidence drawer linking to external DOIs and verbatim snippets.
2. **Fine-Grained Knowledge Graph (`KnowledgeGraphPlaceholder`)**:
   - 3 perspective views: Macro Graph, Fine-Grained Evidence Chain, and Literature Subgraph;
   - Single-node click activates BFS ego-network filtering for 1st, 2nd, and 3rd degree neighbor isolation;
   - Built-in 80-node safety threshold and real-time execution profiling to prevent UI freezes.
3. **Periodic Table & Multi-Dimensional Filter (`PeriodicTable`)**:
   - Filter materials by chemical elements, transition temperature ranges, latent heat, and non-toxicity / cost-effectiveness criteria.

---

## 3. Dual Runtime Support

The frontend is architected for dual-environment deployment:

1. **Reverse Proxy Mode (Docker Cluster)**:
   - Served via Nginx on port 8080, transparently forwarding `/api/*` to the FastAPI backend (port 8000).
2. **Direct Embedded Mode (Zero-Dependency Launcher)**:
   - Precompiled assets reside in `app/static/`, served directly by FastAPI;
   - Requires no Node.js or Nginx installation; simply run `python run_demo.py` to access the full UI at `http://localhost:8000`.

---

## 4. Development & Build Commands

```bash
# 1. Install dependencies
corepack pnpm install

# 2. Start local hot-reloading dev server (port 5173, proxies /api to 8000)
corepack pnpm dev

# 3. Static type check
corepack pnpm typecheck

# 4. Code quality & linting
corepack pnpm lint

# 5. Production build (emits to dist/)
corepack pnpm build
```
