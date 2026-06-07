"""Stable PandasAI agent setup for BioCirv AI (v2).

This module is a clean-room rewrite that avoids hacking PandasAI's internal
VirtualDataFrame state. Instead, it:

1. Discovers view schemas via SQLAlchemy and pg_catalog queries.
2. Builds proper Pydantic ColumnSchema objects with accurate data types.
3. Registers VirtualDataFrames via SQLDatasetLoader when available.
4. Provides a direct query helper for Google Colab using Cloud SQL Proxy and
   CBORG API gateway authentication.

The goal is to enable Google Colab users to query BioCirv materialized views
using plain-language prompts without modifying the legacy sandbox files.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from dotenv import load_dotenv

try:
    from pandasai import Agent
    from pandasai.llm.base import LLM
    from pandasai.data_loader.semantic_layer_schema import (
        ColumnSchema,
        SemanticLayerSchema,
    )
    from pandasai.data_loader.sql_loader import SQLDatasetLoader
    from pandasai import VirtualDataFrame
    HAS_PANDASAI = True
except ImportError:  # pragma: no cover
    HAS_PANDASAI = False

from ca_biositing.ai_exploration.schema import (
    discover_views,
    fetch_column_info,
    fetch_table_metadata,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def pg_type_to_pandasai(pg_type: str) -> str:
    """Map PostgreSQL type names to PandasAI semantic types."""
    lower = pg_type.lower()
    if any(key in lower for key in ["int", "serial", "bigint", "smallint"]):
        return "integer"
    if any(key in lower for key in ["float", "double", "numeric", "decimal", "real"]):
        return "float"
    if "bool" in lower:
        return "boolean"
    if any(key in lower for key in ["date", "time", "timestamp"]):
        return "date"
    return "string"


def build_column_schemas(engine: Engine, schema_name: str, view_name: str) -> List[ColumnSchema]:
    """Create ColumnSchema objects for a fully qualified view."""
    column_info = fetch_column_info(engine, table_name=view_name, schema=schema_name)
    columns = []
    for column in column_info:
        col_type = pg_type_to_pandasai(column["type"]) if column.get("type") else "string"
        columns.append(ColumnSchema(name=column["name"], type=col_type))
    return columns


@dataclass
class DBConfig:
    user: str
    password: str
    host: str
    port: int
    database: str
    search_path: str

    @classmethod
    def from_env(cls, cloud: bool) -> "DBConfig":
        return cls(
            user=os.getenv("DB_USER", "biocirv_readonly" if cloud else "biocirv_user"),
            password=os.getenv("DB_PASS", os.getenv("DB_PASSWORD", "biocirv_dev_password")),
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "5434")),
            database=os.getenv("DB_NAME", "biocirv-staging" if cloud else "biocirv_db"),
            search_path=os.getenv("DB_SEARCH_PATH", "ca_biositing,data_portal,public"),
        )

    def sql_url(self) -> str:
        return (
            "postgresql+psycopg2://"
            f"{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        )

    def connection_options(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "password": self.password,
            "options": f"-c search_path={self.search_path}",
            "connect_args": {"options": f"-c search_path={self.search_path}"},
        }


def create_introspection_engine(config: DBConfig) -> Engine:
    engine = create_engine(config.sql_url())
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return engine


def register_view_dataset(
    engine: Engine,
    db_config: DBConfig,
    qualified_view: str,
    dataset_suffix: str,
) -> VirtualDataFrame:
    """Create a VirtualDataFrame with proper ColumnSchema metadata."""
    if not HAS_PANDASAI:
        raise ImportError("PandasAI is required to register view datasets")

    schema_name, table_name = qualified_view.split(".", 1)
    columns = build_column_schemas(engine, schema_name, table_name)

    if not columns:
        raise ValueError(f"No columns discovered for {qualified_view}")

    dataset_name = qualified_view.replace(".", "-").replace("_", "-").lower()
    dataset_path = f"biocirv/{dataset_name}-{dataset_suffix}"

    source_config = {
        "type": "postgres",
        "table": table_name,
        "schema": schema_name,
        "connection": db_config.connection_options(),
    }

    semantic_schema = SemanticLayerSchema(
        name=dataset_name,
        description=f"BioCirv view: {qualified_view}",
        source=source_config,
        columns=columns,
    )

    loader = SQLDatasetLoader(semantic_schema, dataset_path)
    vdf = VirtualDataFrame(data_loader=loader, path=dataset_path)
    vdf.schema = semantic_schema
    return vdf


def create_agent(
    llm: LLM,
    db_config: DBConfig,
    qualified_views: Optional[Sequence[str]] = None,
) -> Agent:
    if not HAS_PANDASAI:
        raise ImportError("PandasAI is required to create the sandbox agent")

    views = list(qualified_views) if qualified_views else [
        "ca_biositing.analysis_data_view",
        "ca_biositing.analysis_average_view",
        "data_portal.mv_biomass_availability",
        "data_portal.mv_biomass_composition",
        "data_portal.mv_biomass_sample_stats",
        "data_portal.mv_biomass_fermentation",
    ]

    engine = create_introspection_engine(db_config)

    import time

    suffix = str(int(time.time()))
    connectors = []
    for view in views:
        try:
            connectors.append(register_view_dataset(engine, db_config, view, suffix))
        except Exception as exc:
            print(f"⚠️ Skipping {view}: {exc}")

    if not connectors:
        raise RuntimeError("No view datasets registered; agent cannot be created")

    system_prompt = (
        "You are the BioCirv AI data analyst. You have access to BioCirv's materialized "
        "views in PostgreSQL. Use fully-qualified table names (schema.table) and generate "
        "PostgreSQL-compliant SQL. Prefer aggregation queries and return concise tables and "
        "visualizations when prompted."
    )

    return Agent(
        connectors,
        config={
            "llm": llm,
            "verbose": True,
            "enable_cache": False,
            "use_error_correction_framework": True,
            "save_charts": True,
            "system_prompt": system_prompt,
        },
    )


def create_llm(model_name: Optional[str] = None) -> LLM:
    from ca_biositing.ai_exploration.sandbox_setup import CBORGLLM

    api_key = os.getenv("CBORG_API_KEY")
    if not api_key:
        raise ValueError("CBORG_API_KEY is required")

    api_base = os.getenv("CBORG_API_URL", "https://api.cborg.lbl.gov/v1")
    selected_model = model_name or os.getenv("CBORG_MODEL", "gemini-3-flash")
    return CBORGLLM(api_token=api_key, api_base=api_base, model=selected_model)


def init_agent(
    model_name: Optional[str] = None,
    cloud_mode: bool = True,
    qualified_views: Optional[Sequence[str]] = None,
) -> Agent:
    llm = create_llm(model_name)
    db_config = DBConfig.from_env(cloud=cloud_mode)
    return create_agent(llm, db_config, qualified_views)


__all__ = [
    "pg_type_to_pandasai",
    "build_column_schemas",
    "DBConfig",
    "create_agent",
    "init_agent",
]
