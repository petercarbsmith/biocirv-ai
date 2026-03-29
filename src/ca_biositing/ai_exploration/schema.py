from sqlalchemy import text
from typing import List

def fetch_table_metadata(engine, table_name: str, schema: str = None) -> str:
    """Fetches column names and types for a given table or materialized view."""
    # information_schema.columns does not include materialized views
    query = text("""
        SELECT a.attname AS column_name,
               format_type(a.atttypid, a.atttypmod) AS data_type
        FROM pg_attribute a
        JOIN pg_class t ON a.attrelid = t.oid
        JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE t.relname = :table
          AND a.attnum > 0
          AND NOT a.attisdropped
    """ + (" AND n.nspname = :schema" if schema else ""))

    params = {"table": table_name}
    if schema:
        params["schema"] = schema

    try:
        with engine.connect() as conn:
            result = conn.execute(query, params)
            columns = [f"{row[0]} ({row[1]})" for row in result]
        return ", ".join(columns)
    except Exception:
        return "Unknown columns"

def discover_views(engine, schemas: List[str] = ["ca_biositing", "analytics"]) -> List[str]:
    """Automatically discovers all views in the specified schemas."""
    query = text("""
        SELECT table_name
        FROM information_schema.views
        WHERE table_schema = ANY(:schemas)
        AND table_name NOT LIKE 'pg_%%'
        UNION
        SELECT matviewname as table_name
        FROM pg_matviews
        WHERE schemaname = ANY(:schemas)
    """)

    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"schemas": schemas})
            views = [row[0] for row in result]
        print(f"Auto-discovered {len(views)} views in schemas: {', '.join(schemas)}")
        return views
    except Exception as e:
        print(f"WARNING: View discovery failed: {e}")
        return []
