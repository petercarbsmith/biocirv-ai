# Handoff: BioCirv AI Modernization (Phase 4)

## 🎯 Task Overview

Proceed to **Phase 4: Production Refinement & Advanced Tooling** of the BioCirv
AI Modernization Roadmap.

The goal is to enhance the system's intelligence and analytical capabilities
through semantic enrichment and custom geospatial tools.

## 📂 Current State (Post-Phase 3)

- **Platform:** Google Colab / GCP Cloud SQL (IAM-based auth).
- **Core:** SQL-First architecture using `PandasAI 2.3.x` and a custom `Trinity`
  output.
- **Security:** Managed secrets (`google.colab.userdata`) and read-only IAM
  connections.
- **Interface:** `notebooks/biocirv_ai_analysis_playground.ipynb`.

## 🛠️ Implementation Requirements (Phase 4)

### 1. Semantic Layer Enrichment

- Implement a **Metadata Registry** (e.g., a JSON or YAML file) that defines:
  - Business definitions for key views.
  - Value constraints and valid categories for categorical fields.
  - Relationships between views that the LLM should know about.
- Update `sandbox_setup.py` to inject this metadata into the
  `PostgreSQLConnector`.

### 2. Tool-Augmented Analysis

- Create a `tools/` directory in `src/ca_biositing/ai_exploration/tools/`.
- Implement initial **Geospatial Tools**:
  - `calculate_buffer(point, radius)`: Helper for radius-based filtering.
  - `get_drive_time(origin, destination)`: Integration with routing APIs (if
    available).
- Register these tools with the PandasAI Agent to allow it to call them for
  specialized logic.

### 3. Result Persistence

- Implement a `ResultLogger` that saves successful queries, their SQL, and a
  hash of the data to a local or cloud-based "Knowledge Base."
- Enable stakeholders to "bookmark" or "publish" high-value results.

### 4. Rendering Improvements

- Refine the `TrinityResult._repr_html_` to include:
  - Collapsible code sections.
  - Download buttons for CSV/JSON exports.
  - Improved layout for multi-plot scenarios.

---

## ✅ Phase 3 Completion Checklist (For Reference)

- [x] `colab_setup.py` for automated cloud initialization.
- [x] GCP Cloud SQL IAM-based authentication implemented.
- [x] "Cloud Mode" switch in `sandbox_setup.py`.
- [x] `biocirv_ai_analysis_playground.ipynb` deployed and verified with staging
      defaults.
