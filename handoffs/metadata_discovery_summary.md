# 🪲 Troubleshooting Summary: PandasAI Metadata Discovery

## 🔍 The Problem
The BioCirv AI Agent initializes successfully, but the `VirtualDataFrames` register with **zero columns** (`No columns found`). This blocks the LLM from understanding the database schema, leading to failed or hallucinated SQL generation.

## 🛠️ Strategies Attempted

### 1. Schema & Search Path Optimization
*   **Reasoning**: SQLAlchemy might fail to introspect views if the `search_path` isn't set or if schema/table names are ambiguous.
*   **Action**: Explicitly set `search_path` in `connect_args` and split `schema`/`table` into separate configuration fields.
*   **Result**: Connection was stable, but introspection still returned zero columns.

### 2. Manual SQL Introspection (Success)
*   **Reasoning**: If the library's automated discovery fails (likely due to PostGIS `geometry` types or complex view definitions), we can fetch the columns ourselves.
*   **Action**: Implemented a tiered discovery fallback using `SELECT * FROM "schema"."table" LIMIT 0`.
*   **Result**: **Success**. The fallback successfully retrieves the column list (e.g., "12 columns found"), proving the views exist and are accessible.

### 3. Attribute Injection (`object.__setattr__`)
*   **Reasoning**: Once we have the columns, we tried to force them into the `VirtualDataFrame` instance.
*   **Action**: Used `object.__setattr__` to target `_columns`, `_schema.columns`, and `_connector._columns`.
*   **Result**: Met resistance. Pandas-based objects often protect the `.columns` attribute, triggering warnings: *"Pandas doesn't allow columns to be created via a new attribute name"*.

### 4. Subclassing `VirtualDataFrame` (Current State)
*   **Reasoning**: The most robust way to force metadata is to override the property itself.
*   **Action**: Created `BioCirvVirtualDataFrame` which overrides the `@property columns`.
*   **Hurdle**: Initially triggered a `maximum recursion depth exceeded` error because `hasattr()` on a Pandas-like object can trigger recursive attribute lookups.
*   **Fix**: Switched to recursion-safe `self.__dict__.get("_forced_columns")` lookups.

## 🚧 Current State & Findings
*   **Database Connectivity**: ✅ Verified healthy via Cloud SQL Proxy.
*   **Schema Validity**: ✅ `ca_biositing` schema and views verified.
*   **Column Retrieval**: ✅ Manual SQL discovery is successfully finding the columns.
*   **The Blocker**: The `VirtualDataFrame` (specifically the version in Colab) is highly protective of its internal state. Even when we "see" the columns via SQL, the object often reports them as empty to the Agent's registry.

## 📋 Handoff Recommendations
*   **Verify Subclassing**: The latest push (`dev` branch) uses the recursion-safe `BioCirvVirtualDataFrame`. Verify if this finally reflects "Ready (X columns)" in the logs.
*   **Registry Check**: If the logs show "Ready" but the Agent still fails, the issue may lie in how the `Registry` (internal to PandasAI) caches these objects.
*   **Manual Schema Dict**: We may need to pass a full `pandasai.Schema` object to the constructor if the property override is still bypassed.

**Current Files**: 
- [`src/ca_biositing/ai_exploration/sandbox_setup.py`](src/ca_biositing/ai_exploration/sandbox_setup.py): Contains the subclassing and tiered discovery logic.
