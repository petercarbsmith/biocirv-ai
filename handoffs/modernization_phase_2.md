# Handoff: BioCirv AI Modernization (Phase 2)

## 🎯 Task Overview

Proceed to **Phase 2: Rich Result Engineering** of the BioCirv AI Modernization
Roadmap. The foundation is now a stable, SQL-first architecture using PandasAI
2.3.x.

## 📂 Current State (Post-Phase 1)

- **Architecture:** SQL-First using `PostgreSQLConnector`.
- **Dependencies:** `pandasai>=2.3.0`, `pandas==1.5.3` (Pinned for GIS
  stability).
- **Setup File:**
  [`analysis/biocirv-ai/src/ca_biositing/ai_exploration/sandbox_setup.py`](../src/ca_biositing/ai_exploration/sandbox_setup.py)
- **Key Feature:** The `SandboxResponseParser` now implements `get_trinity()`,
  which returns a unified dictionary of **Code**, **Data**, and **Plot**.

## 🛠️ Implementation Requirements (Phase 2)

### 1. Robust Trinity UI/UX

- Refine the parser to handle more complex multi-step results.
- Ensure that when an Agent is used in a notebook, it returns a renderable
  object that displays the Plotly figure by default but keeps the raw Data and
  Code accessible.
- Standardize the storage of generated SQL and Python code into a session-level
  log.

### 2. Multi-Backend Visualization Polishing

- Ensure **Plotly** figures are always returned as interactive `go.Figure`
  objects for VS Code/Jupyter rendering.
- Standardize the "Matplotlib fallback" to save charts to `exports/charts/` with
  deterministic naming.
- Implement a "Visualization Unwrapper" that can extract a plot from a complex
  response even if the LLM returned it as a string path.

### 3. Schema Metadata Enrichment

- Update the `SQLConnector` configuration to include `field_descriptions` pulled
  from the repository's documentation or DB comments.
- Improve the "PostgreSQL Hint" in `CBORGLLM.call()` to guide the LLM toward
  optimized geospatial querying if possible.

### 4. Advanced Testing

- Verify that the `Agent` can correctly join a 100k+ row materialized view with
  a smaller reference table without memory spikes (verifying the SQL-first
  delegation).

---

## ✅ Phase 1 Completion Checklist (For Reference)

- [x] Update `pixi.toml` / `pyproject.toml` to PandasAI 2.3.x.
- [x] Implement `SQLConnector` / `PostgreSQLConnector` in `sandbox_setup.py`.
- [x] Remove all monkeypatches and module purging.
- [x] Modernize `CBORGLLM` with proper typing and PostgreSQL hints.
- [x] Implement initial `SandboxResponseParser` for "Trinity" outputs.
- [x] Verify multi-schema joins in `debug_chat.py`.
