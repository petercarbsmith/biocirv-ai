# 🗺️ Handoff: On-the-Fly Geospatial Sanitization Strategy

## 📋 Context

We have identified that **PostGIS Geometry types** are the primary source of
instability in the BioCirv AI Agent. PandasAI's internal SQLAlchemy
introspection crashes when it encounters these types, and the LLM cannot reason
about binary hex data.

## 🚀 The New Strategy: "The Sanitized Wrapper"

Instead of forcing the AI to query raw database views, we point it at a
**Virtual Subquery**. This subquery uses PostGIS functions to cast geometries to
human-readable strings _before_ the Python environment even sees them.

### 1. SQL Transformation

For every view with a geometry column, we wrap it in a subquery:

```sql
SELECT * FROM (
    SELECT record_id, ST_AsText(geom) as geom, ...
    FROM ca_biositing.landiq_record_view
) AS virtual_table
```

### 2. Implementation: `sandbox_setup_no_geo.py`

We are moving logic to a new, simplified factory file.

- **No Ghost Frames**: Since the AI only sees standard types (text, numeric), we
  don't need the complex "Ghost Frame" hacks.
- **Explicit Loaders**: We use the standard `SQLDatasetLoader` and
  `SemanticLayerSchema` as requested.
- **Safe Head**: We continue to shadow `vdf.head()` during initialization to
  prevent unnecessary/fragile DB calls during prompt serialization.

## 🛠️ Components

- **File**:
  `analysis/biocirv-ai/src/ca_biositing/ai_exploration/sandbox_setup_no_geo.py`
  (New simplified entry point)
- **Mechanism**: Automatic detection of 'geom' columns and injection of
  `ST_AsText()` wrapper.
- **Interface**: The Colab notebook imports from this new file to ensure a clean
  break from the previous "hacky" architecture.

## ✅ Benefits

1. **Zero DB Maintenance**: No migrations needed.
2. **LLM Reasoning**: The AI can read `POINT(-121.4 38.5)` and understands it is
   a location.
3. **Stability**: SQLAlchemy/PandasAI see 100% standard SQL types.
