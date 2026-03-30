# Roadmap: Modernizing BioCirv AI Exploration

## 1. Executive Summary

The BioCirv AI Exploration project is transitioning from a "brittle,"
monkeypatched research prototype into a stable, production-ready analytics
engine. The primary goals are to eliminate technical debt caused by
environmental mismatches in Jupyter, upgrade to the latest stable PandasAI
architecture (SQL-first), and provide a stakeholder-accessible prototype via
Google Colab integrated with GCP Cloud SQL.

---

## 2. Current State Assessment

### 🚨 Critical Issues & Flags

- **Unhashable Type Errors:** The current system frequently fails in Jupyter
  with `TypeError: unhashable type: 'list'`. This is caused by Pydantic
  validation failures when classes are redefined in notebook cells, leading to
  "identity drift."
- **Aggressive Monkeypatching:** To combat the above, the system uses "Nuclear
  Cache Killers" and `sys.modules` purging. This is highly unstable and causes
  recursion errors and class identity mismatches.
- **Multi-Schema Materialized Views:** We are querying across multiple
  PostgreSQL schemas (e.g., `ca_biositing`, `analytics`, `data_portal`). The
  current setup relies on `search_path` manipulation, which is fragile.
- **Data Bottleneck:** Currently, views are loaded into memory as DataFrames
  (limited to 5000 rows). This is inefficient for large-scale geospatial
  analysis.
- **Stale Dependencies:** The project is pinned to older versions of PandasAI
  due to historical dependency clashes (Pydantic v1 vs v2, SQLAlchemy 1.4 vs
  2.0).

### 🛠️ Current Architecture

- **Core:** PandasAI 2.0 (Legacy path).
- **LLM:** Custom `CBORGLLM` wrapper.
- **Context:** Manual schema discovery and metadata injection.
- **Execution:** Python-first (LLM writes Python to manipulate DataFrames).

---

## 3. Desired Future State (The "Modern" Baseline)

### 💎 Technical Vision

- **Zero Monkeypatches:** The system should work natively in any standard
  IPython/Jupyter environment.
- **SQL-First Execution:** Leveraging `SQLConnector` to allow the LLM to write
  and execute SQL directly on PostgreSQL.
- **Schema-Aware Multi-Schema Access:** Natively support queries across separate
  schemas and materialized views using fully qualified names or robust connector
  configuration.
- **The "Trinity" Output:** Every query should aspirationally return three
  distinct components:
  1.  **The Code:** The generated SQL and/or Python processing code.
  2.  **The Data:** The resulting raw DataFrame used for the final answer.
  3.  **The Plot:** An interactive visualization (Plotly) or static chart.
- **Multi-Backend Visualization:** Support for Plotly (interactive), Matplotlib,
  and Seaborn (standard research plots).

### ☁️ Stakeholder Integration

- **Google Colab Prototype:** A shared environment for project stakeholders to
  interactively query the underlying data without local environment setup.
- **GCP Integration:** Direct connection to GCP-hosted Cloud SQL using IAM-based
  authentication (removing the need for local `.env` database passwords).

---

## 4. Implementation Roadmap

### Phase 1: Stabilization & Modernization (Current)

- **Step 1.1: Dependency Resolution:** Update `pixi.toml` and `pyproject.toml`
  to the latest stable PandasAI release. Resolve Pydantic and SQLAlchemy pins.
- **Step 1.2: Refactor Setup:** Rewrite `sandbox_setup.py` using the
  `SQLConnector` pattern.
- **Step 1.3: Clean Initialization:** Remove all module purging and
  cache-killing logic. Use proper class registration if identity drift persists.
- **Step 1.4: Multi-Backend Config:** Configure the Agent to support Plotly,
  Seaborn, and Matplotlib natively.

### Phase 2: Rich Result Engineering

- **Step 2.1: Response Parsing:** Update the parser to capture internal
  execution logs (generated SQL and Python).
- **Step 2.2: Visualization Unwrapping:** Ensure Plotly figures are returned as
  raw objects for VS Code and Colab rendering.

### Phase 3: Google Colab & GCP Migration (COMPLETED)

- **Step 3.1: Colab Scripting:** Created `colab_setup.py` for automated
  authentication and secret management via `google.colab.userdata`.
- **Step 3.2: GCP IAM Auth:** Implemented `get_cloud_engine` in
  `sandbox_setup.py` using the Cloud SQL Python Connector with IAM-based
  authentication.
- **Step 3.3: Deployment:** Launched the `biocirv_ai_analysis_playground.ipynb`
  as the primary stakeholder analysis interface.

### Phase 4: Production Refinement & Advanced Tooling (Upcoming)

- **Step 4.1: Semantic Layer Enrichment:** Implement a structured metadata
  registry to provide the LLM with deeper business logic and field constraints.
- **Step 4.2: Tool-Augmented Analysis:** Integrate custom tools for specialized
  geospatial calculations (e.g., buffering, catchment analysis) directly into
  the Agent's toolkit.
- **Step 4.3: Result Persistence:** Implement a mechanism to save and version
  successful "Trinity" results for longitudinal research tracking.
- **Step 4.4: UI/UX Enhancements:** Refine the `TrinityResult` HTML rendering
  for even better interactivity in shared notebook environments.

---

## 5. Risk Management & Mitigations

| Risk                   | Impact | Mitigation                                                                                       |
| :--------------------- | :----- | :----------------------------------------------------------------------------------------------- |
| **Dependency Clashes** | High   | Use Pixi environments to isolate the AI sandbox from ETL pipeline legacy pins if necessary.      |
| **Rendering in Colab** | Medium | Standardize on HTML-based Plotly exports which are highly portable.                              |
| **LLM Query Safety**   | High   | Use the `SQLConnector` read-only user permissions and search_path restricted to analytics views. |
| **Identity Drift**     | Medium | Use `id()` based hashing surgical patches only where strictly necessary for Pydantic stability.  |

---

## 6. Progress Summary (March 2026)

### Phase 1: Stabilization & Modernization (COMPLETED)

- **Modernized Architecture:** Successfully migrated to PandasAI 2.3.x using the
  `Agent` and `PostgreSQLConnector` patterns.
- **SQL-First Execution:** The system now generates and executes SQL against
  PostgreSQL views, significantly reducing memory overhead and improving support
  for large datasets.
- **Multi-Schema Support:** Native support for querying and joining views across
  `ca_biositing`, `analytics`, and `data_portal` schemas via `search_path`
  configuration.
- **Removed Technical Debt:** Eliminated all brittle monkeypatching and
  module-purging logic.
- **Trinity Output Initialized:** Implemented a custom `ResponseParser` that
  captures generated Code, raw DataFrames, and Visualization objects
  (Matplotlib/Plotly).
- **Dependency Anchor:** Stabilized the environment on `pandas 1.5.3` to ensure
  zero conflict with the repository's mission-critical geospatial stack on macOS
  (arm64).

### Phase 2: Rich Result Engineering (COMPLETED)

- **Trinity Result Object:** Implemented a unified `TrinityResult` class that
  encapsulates Code, Data, Plot, and Answer, providing a rich multi-component
  representation for Jupyter/VS Code.
- **Robust Visualization Unwrapping:** The `SandboxResponseParser` now
  automatically extracts and renders Plotly figures (interactive) and Matplotlib
  charts (static) from complex LLM responses.
- **Session-Level Code Logging:** Implemented `SESSION_CODE_LOG` to track all
  generated SQL and Python code throughout an exploration session.
- **Schema Metadata Enrichment:** Enhanced `SQLConnector` with automatic column
  discovery and improved LLM hints for PostgreSQL/Geospatial queries.
- **Performance Verification:** Confirmed stable execution of 100k+ row joins
  between materialized views and reference tables via SQL delegation.

### Phase 3: Google Colab & GCP Migration (COMPLETED)

- **Cloud-Native Auth:** Integrated `google.colab.auth` and
  `google.colab.userdata` for secure, zero-password authentication in shared
  environments.
- **GCP IAM Integration:** Successfully implemented the GCP Python Connector
  with IAM-based authentication for Cloud SQL, removing the need for local
  credentials.
- **Analysis Playground:** Developed and deployed the
  `biocirv_ai_analysis_playground.ipynb` notebook as a standard, documented
  entry point for project stakeholders.
- **Environment Switcher:** Added a robust "Cloud Mode" toggle in
  `sandbox_setup.py` to seamlessly transition between local development and
  managed cloud execution.
