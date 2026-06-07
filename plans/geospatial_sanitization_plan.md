# Plan: Simplified Geospatial Sanitization & AI Agent Prototype

## 🎯 Goal

Create a streamlined, "no-geo" version of the BioCirv AI Agent that is
unencumbered by PostGIS geometry type failures. This prototype will focus on
stability and ease of use with standard data types while still allowing the AI
to "see" location data as text.

## 🏗️ Architecture: `sandbox_setup_no_geo.py`

### 1. The "Sanitized Wrapper" Strategy

Instead of pointing the AI at raw database views that contain binary PostGIS
geometry columns, we will:

- Detect columns named `geom` or of type `geometry`.
- Wrap the view in a virtual subquery:
  `SELECT *, ST_AsText(geom) as geom_text FROM schema.view`.
- This ensures the AI sees human-readable strings like `POINT(-121 38)` instead
  of crashing on hex data.

### 2. Streamlined Loading

- Remove "Ghost Frame" monkeypatching where possible.
- Use `SQLDatasetLoader` or `ViewDatasetLoader` from PandasAI natively.
- Leverage the `SemanticLayerSchema` for explicit column definitions if
  discovery fails.

### 3. "Trinity" Result Persistence

- Maintain the `TrinityResult` format (Code, Data, Plot) as it's critical for
  stakeholder satisfaction.
- Ensure `SandboxResponseParser` is compatible with the simplified setup.

## 📋 Step-by-Step Implementation

1.  **Define `sandbox_setup_no_geo.py`**:
    - Copy core `CBORGLLM`, `TrinityResult`, and `SandboxResponseParser` from
      `sandbox_setup.py`.
    - Implement a new `get_agent` function that uses the subquery wrapper logic.
    - Use `ViewDatasetLoader` if appropriate for materialized views.
2.  **Schema Sanitization Logic**:
    - Add a helper to inspect columns and generate the `ST_AsText` SQL wrapper.
3.  **Validation**:
    - Create `scripts/test_no_geo_agent.py` to verify:
      - Connection to Cloud SQL / Local DB.
      - Successful metadata discovery of wrapped views.
      - Natural language query execution (e.g., "Show me the first 5 records of
        landiq_record_view").
4.  **Handoff & Documentation**:
    - Update `AGENTS.md` to point to the new "Stable Prototype" entry point.

## ⚠️ Risks & Mitigations

- **Performance**: Large subqueries might be slower than raw views. _Mitigation:
  Use `LIMIT` hints or ensure materialized views are indexed._
- **PandasAI Versioning**: `ViewDatasetLoader` might have specific requirements.
  _Mitigation: Check `pixi.toml` and local site-packages if errors occur._
