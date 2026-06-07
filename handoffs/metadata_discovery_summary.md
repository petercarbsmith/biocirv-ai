# 🪲 Troubleshooting Summary: PandasAI Metadata Discovery

## 🔍 The Problem

The BioCirv AI Agent initializes successfully, but the `VirtualDataFrames` were
registering with **zero columns** (`No columns found`). This blocked the LLM
from understanding the database schema, leading to failed or hallucinated SQL
generation. The underlying cause was SQLAlchemy's introspection failing on
PostGIS `geometry` types and complex view definitions.

## 🛠️ Strategies Attempted

### 1. Schema & Search Path Optimization

- **Action**: Explicitly set `search_path` in `connect_args` and split
  `schema`/`table` into separate fields.
- **Result**: Connection was stable, but automated introspection still returned
  zero columns.

### 2. Manual SQL Introspection (Success)

- **Action**: Implemented a tiered discovery fallback using
  `SELECT * FROM "schema"."table" LIMIT 0`.
- **Result**: **Success**. This reliably retrieved column names from the
  database, bypassing driver-level introspection bugs.

### 3. Attribute Injection (`object.__setattr__`)

- **Action**: Tried to force discovered columns into the `VirtualDataFrame`
  instance after creation.
- **Result**: Failed. The library's internal state management blocked
  late-binding metadata injection.

### 4. Subclassing `VirtualDataFrame`

- **Action**: Created a subclass to override the `.columns` property.
- **Result**: Failed. Triggered recursion errors and "Missing DataLoader"
  requirements.

## ✅ The Final Solution: The "Ghost Frame" Strategy

The winning strategy involved providing the metadata _at the moment of creation_
using officially supported (but strict) parameters.

1.  **Manual SQL Pre-Discovery**: Before calling the factory, we run a raw SQL
    `LIMIT 0` query to fetch the actual column names.
2.  **Ghost Frame Creation**: We create an empty `pandas.DataFrame` with those
    column names.
3.  **PandasAI Type Wrapping**: We wrap that pandas DF in a `pandasai.DataFrame`
    object to satisfy the library's internal type-checking.
4.  **Factory Injection**: We pass this "Ghost Frame" into the
    `create_dataset(..., df=ghost_df)` factory.
5.  **Hybrid Result**: The resulting `VirtualDataFrame` inherits the correct
    schema from the Ghost Frame while still using the `source_config` to route
    all actual LLM queries to the PostgreSQL database.

## 🚧 Current State

- **Agent Status**: `✅ BioCirv AI Agent Ready!`
- **Metadata Discovery**: `✅ Ready (X columns)` for all 6 BioCirv views.
- **Persistence**: The fix is hardened in
  `src/ca_biositing/ai_exploration/sandbox_setup.py` and pushed to the `dev`
  branch.

## 📋 Handoff Recommendations

The agent is now fully aware of the BioCirv schema. Future views should be added
to the `qualified_views` list in `get_agent()`, and the Ghost Frame strategy
will automatically handle their metadata discovery.
