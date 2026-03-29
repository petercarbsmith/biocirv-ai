# Phase 1 COMPLETED: BioCirv AI Modernization (Stabilization)

## 🎯 Phase 1 Result

Successfully migrated the AI sandbox to a stable, SQL-first architecture using
PandasAI 2.3.x. All legacy monkeypatching and environment instabilities in
Jupyter have been resolved.

## 🎯 Original Task Overview

Implement Phase 1 of the **BioCirv AI Modernization Roadmap**. The goal is to
move the current AI Exploration sandbox from a brittle, monkeypatched prototype
to a stable, SQL-first architecture using the latest stable version of PandasAI.

## 📂 Reference Documentation

- **Primary Roadmap:**
  [`analysis/biocirv-ai/plans/modernization_roadmap.md`](analysis/biocirv-ai/plans/modernization_roadmap.md)
- **Current Setup File:**
  [`analysis/biocirv-ai/src/ca_biositing/ai_exploration/sandbox_setup.py`](analysis/biocirv-ai/src/ca_biositing/ai_exploration/sandbox_setup.py)
- **Schema Discovery:**
  [`analysis/biocirv-ai/src/ca_biositing/ai_exploration/schema.py`](analysis/biocirv-ai/src/ca_biositing/ai_exploration/schema.py)

## 🛠️ Implementation Requirements (Phase 1)

### 1. Dependency Update

- Update
  [`analysis/biocirv-ai/pyproject.toml`](analysis/biocirv-ai/pyproject.toml) and
  [`analysis/biocirv-ai/pixi.toml`](analysis/biocirv-ai/pixi.toml).
- Target the latest stable PandasAI release (>= 2.3.0).
- Remove restrictive pins on `pandas` and `sqlalchemy` that were causing
  historical clashes.

### 2. SQL-First Refactor

- Rewrite
  [`sandbox_setup.py`](analysis/biocirv-ai/src/ca_biositing/ai_exploration/sandbox_setup.py)
  to use `SQLConnector`.
- The LLM should execute SQL directly against database views (including
  **materialized views**) rather than loading DataFrames into memory.
- **Multi-Schema Awareness:** Natively support joins and queries across separate
  schemas (e.g., `ca_biositing`, `analytics`, `data_portal`).

### 3. Cleanup & Stabilization

- **Remove all monkeypatches** (`functools.cache` overrides, `sys.modules`
  purging, etc.).
- Modernize `CBORGLLM` to align with the latest PandasAI `LLM` base class.
- Configure the Agent to support **Matplotlib**, **Seaborn**, and **Plotly**
  backends.

### 4. Rich Result Parsing (The "Trinity" Output)

- Enhance `SandboxResponseParser` to capture and return a unified result object
  containing:
  1.  **The Code:** Both the generated SQL query and any Python post-processing
      code.
  2.  **The Data:** The resulting raw DataFrame used to derive the answer.
  3.  **The Plot:** An interactive Plotly figure or static chart
      (Seaborn/Matplotlib).

## 🧪 Testing

- Verify using
  [`analysis/biocirv-ai/debug_chat.py`](analysis/biocirv-ai/debug_chat.py).
- Ensure natural language joins across schemas work via SQL generation.
- Ensure interactive Plotly figures render correctly in the notebook.

---

## ✅ Final Completion Status (March 2026)

- [x] **Dependency Update:** Updated `pixi.toml` and `pyproject.toml` to stable
      PandasAI 2.3.0 and pandas 1.5.3.
- [x] **SQL-First Architecture:** Replaced SmartDataframe loading with
      `PostgreSQLConnector` for direct database execution.
- [x] **Multi-Schema Support:** Configured `search_path` to handle
      `ca_biositing`, `analytics`, and `data_portal` views.
- [x] **Clean State:** Removed all module purging and cache-killing
      monkeypatches.
- [x] **Trinity Output:** Implemented `SandboxResponseParser` to capture Code,
      Data, and Plots.
- [x] **Verification:** Validated multi-view joins and visualization generation
      via `debug_chat.py`.

**Next Steps:** Proceed to [Phase 2 Handoff](modernization_phase_2.md).
