from sqlalchemy import text
from typing import List, Optional

def fetch_table_metadata(engine, table_name: str, schema: Optional[str] = None) -> str:
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


def fetch_column_info(engine, table_name: str, schema: Optional[str] = None) -> List[dict]:
    """Returns structured column metadata for a given table or materialized view."""
    query = text(
        """
        SELECT a.attname AS column_name,
               format_type(a.atttypid, a.atttypmod) AS data_type
        FROM pg_attribute a
        JOIN pg_class t ON a.attrelid = t.oid
        JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE t.relname = :table
          AND a.attnum > 0
          AND NOT a.attisdropped
        """ + (" AND n.nspname = :schema" if schema else "")
    )

    params = {"table": table_name}
    if schema:
        params["schema"] = schema

    try:
        with engine.connect() as conn:
            result = conn.execute(query, params)
            return [{"name": row[0], "type": row[1]} for row in result]
    except Exception:
        return []

def discover_views(engine, schemas: List[str] = ["ca_biositing", "data_portal"]) -> List[dict]:
    """Automatically discovers all views in the specified schemas, returning list of {schema, table}."""
    query = text("""
        SELECT table_schema as schema_name, table_name
        FROM information_schema.views
        WHERE table_schema = ANY(:schemas)
        AND table_name NOT LIKE 'pg_%%'
        UNION
        SELECT schemaname as schema_name, matviewname as table_name
        FROM pg_matviews
        WHERE schemaname = ANY(:schemas)
    """)

    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"schemas": schemas})
            views = [{"schema": row[0], "table": row[1]} for row in result]
        print(f"Auto-discovered {len(views)} views in schemas: {', '.join(schemas)}")
        return views
    except Exception as e:
        print(f"WARNING: View discovery failed: {e}")
        return []
