# 🪲 Handoff: Troubleshooting PandasAI Metadata Discovery

## 📋 Project Context

We are building a Natural Language Interface to PostGIS for California's
bioeconomy. We've stabilized the connection (Hybrid IAM Proxy + Static Login)
and resolved the `Agent` constructor compatibility issues.

## 🚧 The Current Blocker

The `Agent` initializes correctly, but the `VirtualDataFrames` are registered
with **zero columns** (`No columns found`). This indicates that PandasAI's
internal introspection (which uses SQLAlchemy to fetch table schemas) is failing
to see the columns in the PostgreSQL views, even though the tunnel is open and
credentials are correct.

## 🔍 Investigation Path for Next Agent

1.  **Search Path vs. Explicit Schema**: We are currently passing fully
    qualified names (e.g., `ca_biositing.analysis_data_view`) in the `table`
    field of the source config.
    - _Hypothesis_: PandasAI or its underlying SQLAlchemy connector might be
      incorrectly parsing the `.` in the table name or failing to handle
      cross-schema lookups during introspection.
2.  **Engine Kwargs**: We might need to pass `engine_kwargs` with
    `connect_args={"options": "-c search_path=ca_biositing,data_portal"}`
    directly into the `VirtualDataFrame` source config to ensure the driver
    knows where to look for metadata.
3.  **Permissions**: Verify if the `biocirv_readonly` user has `USAGE`
    permissions on the `ca_biositing` and `data_portal` schemas, and `SELECT` on
    the views.

## 🔄 Workflow Requirements

- **Submodule Context**: All code is in the `biocirv-ai` submodule.
- **Persistence**: You **MUST** commit and push changes to the `dev` branch for
  the Google Colab environment to see them.
- **Verification**: Use the `Connectivity Smoke Test` in the notebook. A
  successful fix will show `Ready (X columns)` for each dataset during
  registration.

## 📚 Reference Docs

- [`handoffs/project_vision_and_architecture.md`](handoffs/project_vision_and_architecture.md):
  High-level technical stack.
- [`src/ca_biositing/ai_exploration/sandbox_setup.py`](src/ca_biositing/ai_exploration/sandbox_setup.py):
  The core agent factory.

---

**Current Error Log in Colab**:

```text
📦 Registering 6 virtual datasets...
  ⚠️ ca_biositing.analysis_data_view: No columns found.
  ⚠️ ca_biositing.analysis_average_view: No columns found.
  ...
✅ BioCirv AI Agent Ready!
```
