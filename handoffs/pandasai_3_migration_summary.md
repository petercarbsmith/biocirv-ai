# 📦 PandasAI 3.0+ Migration: VirtualDataFrame Strategy

This document summarizes the research and implementation strategy for migrating
the BioCirv AI Agent to PandasAI 3.0+.

## 🔍 The Problem: "The Engine Error"

In earlier versions of PandasAI, it was common to pass a `SQLAlchemy Engine` or
a `PostgreSQLConnector` directly to the `Agent`. In PandasAI 3.0+, this results
in: `AttributeError: 'Engine' object has no attribute 'schema'`

This happens because the new `Agent` base class strictly validates that its
input is a list of `DataFrame` or `VirtualDataFrame` objects.

## 🛠️ Research Findings

### 1. Connector Deprecation

The `PostgreSQLConnector` class is no longer a top-level import in `pandasai`
and has been largely replaced by the **Semantic Layer API**.

### 2. The Role of `pandasai_sql`

The `pandasai_sql` library is now an **extension**, not a source for connector
classes. It provides the internal `load_from_postgres` functions that PandasAI's
`SQLDatasetLoader` calls under the hood.

**DO NOT** try to import `PostgreSQLConnector` from `pandasai_sql`.

### 3. VirtualDataFrames (The Solution)

The correct way to interface with SQL databases now is to create a
`VirtualDataFrame` for every table or view you want the agent to see.

## 🚀 Implementation Strategy

### 1. Lazy Loading with `create()`

Instead of loading data into memory, use `pandasai.create()` with a `source`
configuration.

```python
from pandasai import create as create_dataset

source_config = {
    "type": "postgres",
    "table": "your_view_name",
    "connection": {
        "host": "localhost",
        "port": 5432,
        "database": "db_name",
        "user": "user",
        "password": "password"
    }
}

vdf = create_dataset(
    path="organization/dataset-name", # Path must be lowercase-hyphenated
    description="Description for the LLM",
    source=source_config
)
```

### 2. Dataset Persistence

PandasAI 3.0+ saves "Dataset" metadata (YAML schemas) to a local `datasets/`
directory.

- **Initialization Logic**: Our `get_agent()` now tries to `load()` an existing
  dataset first to avoid "Dataset already exists" errors, falling back to
  `create()` only if necessary.
- **Path Naming**: Paths passed to `create()` **MUST** be lowercase and use
  hyphens (e.g., `biocirv/analysis-data-view`).

### 3. Response Parsing

The `ResponseParser` import path moved to `pandasai.core.response.parser`. We
use a defensive import block to maintain compatibility across slight version
variances.

## 📈 Performance Implications

- **No RAM Bloat**: `VirtualDataFrames` are lazy. They only fetch metadata
  (columns/types) at initialization.
- **Server-Side Execution**: Heavy lifting (SQL generation and execution) still
  happens in PostgreSQL/PostGIS.
- **Minimized Payload**: Only the final result sets (e.g., aggregations) are
  transferred to the Python environment.

## 📝 Usage for Next Agent

When adding new views to the agent:

1. Ensure the view is added to the `view_names` discovery logic.
2. The `get_agent()` function will automatically handle the `VirtualDataFrame`
   registration.
3. If schema metadata changes, you may need to delete the local `datasets/`
   folder to force a re-generation of the YAML schemas.
