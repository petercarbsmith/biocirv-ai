# 🪲 Handoff: Troubleshooting Data Visibility & Database Empty Results

## 📋 Project Context

We have stabilized the **BioCirv AI Agent** constructor and resolved both the
**Metadata Discovery** blockers (using "Ghost Frames") and the **Response
Parser** `AttributeError`. The agent is now initializing with correct column
schemas and executing `.chat()` calls without crashing.

## 🚧 The Current Blocker

The Agent is executing queries but returning empty results or indicating it
cannot find data, even though the metadata (columns) is correctly discovered.

**Observation**:

- Metadata discovery (columns) works using `LIMIT 0` against the views.
- LLM generated SQL seems correct.
- Results are empty or "no data found".

## 🔍 Investigation Path for Next Agent

1.  **Direct Data Check**: Use a raw SQLAlchemy script (bypassing PandasAI) to
    query the top 5 rows from each view. If this returns data, the issue is with
    PandasAI's connection routing.
2.  **Schema Search Path**: Verify if the `search_path` (set to
    `ca_biositing,data_portal`) is correctly applied during the execution phase.
    If the LLM generates a query like `SELECT * FROM analysis_data_view` but the
    search path isn't active, it will fail.
3.  **Permissions**: Ensure the `biocirv_readonly` user has `SELECT` permissions
    on the _actual data_ in the `public` schema if the views in `ca_biositing`
    are just pointers to `public` tables.
4.  **Materialized View Population**: Check if the materialized views are
    actually populated:
    ```sql
    SELECT schemaname, matviewname, ispopulated FROM pg_matviews;
    ```
    If `ispopulated` is false, run `pixi run refresh-views`.

## 🔄 Workflow Requirements

- **Persistence**: You **MUST** commit and push changes to the `dev` branch for
  the Google Colab environment to see them.
- **Verification**: Use the `Query 1: Data Summary` cell. A successful fix will
  return a `TrinityResult` with a non-empty DataFrame.

## 📚 Relevant Files & Documentation

- [`handoffs/response_parser_troubleshooting.md`](handoffs/response_parser_troubleshooting.md):
  Previous blocker details.
- [`handoffs/metadata_discovery_summary.md`](handoffs/metadata_discovery_summary.md):
  Context on how we bypass introspection.
- [`src/ca_biositing/ai_exploration/sandbox_setup.py`](src/ca_biositing/ai_exploration/sandbox_setup.py):
  The core agent factory.
- [`scripts/debug_db.py`](scripts/debug_db.py): Use this to verify raw database
  connectivity and data presence.
