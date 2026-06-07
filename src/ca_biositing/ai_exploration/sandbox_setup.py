import sys
import os
import pandas as pd
import requests
import json
import plotly.io as pio
import plotly.graph_objects as go
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
try:
    from google.cloud.sql.connector import Connector, IPTypes
    import pg8000
    HAS_GCP_CONNECTOR = True
except ImportError:
    HAS_GCP_CONNECTOR = False

from IPython.display import display, Image, HTML
from typing import Optional, List, Any, Dict

# --- 1. PandasAI Imports ---
from pandasai.llm.base import LLM
from pandasai import Agent, DataFrame, VirtualDataFrame, create as create_dataset
try:
    from pandasai.core.response.parser import ResponseParser
except ImportError:
    try:
        from pandasai.responses.response_parser import ResponseParser
    except ImportError:
        ResponseParser = object

# Internal imports
from ca_biositing.ai_exploration.schema import discover_views, fetch_table_metadata

# PandasAI Advanced Imports for manual loader creation
try:
    from pandasai.data_loader.sql_loader import SQLDatasetLoader
    from pandasai.data_loader.semantic_layer_schema import SemanticLayerSchema
    HAS_ADVANCED_LOADERS = True
except ImportError:
    HAS_ADVANCED_LOADERS = False

# Set Plotly for VS Code/Jupyter compatibility
pio.renderers.default = 'notebook'

# Initialize session-level log for generated code
SESSION_CODE_LOG = []
LAST_RESULT_CACHE = {"result": None}

# Load environment variables
load_dotenv()

AVAILABLE_MODELS = [
    "gemini-3-flash",
    "gemini-2.0-flash",
    "gemini-1.5-pro",
    "gpt-4o",
    "gpt-4o-mini",
    "claude-3-5-sonnet",
]

class CBORGLLM(LLM):
    """Modernized Custom LLM class for CBORG gateway aligned with PandasAI >= 2.3.0"""
    def __init__(self, api_token: str, api_base: str = "https://api.cborg.lbl.gov/v1", model: str = "gemini-3-flash"):
        self.api_token = api_token
        self.api_base = api_base
        self.model = model
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        })

    def call(self, instruction: Any, context: Any = None) -> str:
        prompt = instruction.to_string()

        # Inject PostgreSQL dialect hint if SQL generation is detected
        if "SELECT" in prompt.upper() or "SQL" in prompt.upper():
            prompt += "\n\nCRITICAL: You are querying a PostgreSQL database."
            prompt += "\n- Always use PostgreSQL-compatible syntax (e.g., use RANDOM() instead of RAND())."
            prompt += "\n- Prefer optimized geospatial queries if applicable."
            prompt += "\n- Ensure all table/column names are correctly escaped if they contain special characters or are case-sensitive."

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0
        }
        try:
            response = self._session.post(
                f"{self.api_base}/chat/completions",
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            if "result =" in content and "```" not in content:
                content = f"```python\n{content}\n```"

            return content
        except requests.exceptions.Timeout:
            return "Error: The request to CBORG API timed out."
        except requests.exceptions.RequestException as e:
            return f"Error connecting to CBORG API: {str(e)}"
        except (KeyError, ValueError) as e:
            return f"Error parsing CBORG API response: {str(e)}"

    @property
    def type(self) -> str:
        return "cborg"

class TrinityResult:
    """
    A unified result object for the AI Sandbox that encapsulates the "Trinity"
    of outputs: Code, Data, and Plot.
    """
    def __init__(self, code: str, data: Optional[pd.DataFrame] = None, plot: Any = None, answer: Any = None):
        self.code = code
        self.data = data
        self.plot = plot
        self.answer = answer

    def _repr_html_(self):
        """Rich representation for Jupyter/VS Code."""
        # If there's a Plotly figure, it's often best to return its native rich representation
        if isinstance(self.plot, (go.Figure, go.FigureWidget)):
            return self.plot._repr_html_()

        html = []
        if self.answer is not None:
            html.append(f"<div style='margin-bottom: 10px;'><strong>Answer:</strong> {self.answer}</div>")

        if self.plot is not None:
            if isinstance(self.plot, Image):
                # Displaying an Image object in _repr_html_ is tricky without direct access to its data
                # For now, we'll assume the caller can display() it if needed, or we rely on the Answer/Data
                html.append("<div style='color: #666;'>[Static Plot Generated]</div>")

        if self.data is not None:
            html.append(f"<div><strong>Data (Preview):</strong><br/>{self.data.head().to_html()}</div>")

        if not html:
            return f"TrinityResult(code_len={len(self.code)})"

        return "".join(html)

    def __repr__(self):
        return f"TrinityResult(has_data={self.data is not None}, has_plot={self.plot is not None}, has_answer={self.answer is not None})"

    def display(self):
        """Explicitly display all components of the trinity."""
        if self.answer is not None:
            print(f"Answer: {self.answer}")
        if self.plot is not None:
            display(self.plot)
        if self.data is not None:
            display(self.data)

class SandboxResponseParser(ResponseParser):
    """
    Custom Response Parser for the AI Sandbox.
    Implements the "Trinity" output format: Code, Data, and Plot.
    Ensures DataFrames and Plotly Figures are returned as raw objects.
    """
    def __init__(self, context: Any):
        super().__init__(context)
        self._last_result = None

    def parse(self, result: Any) -> Any:
        """
        Captured the trinity of outputs.
        1. Code: Captured via agent.last_code_executed (external to parser usually)
        2. Data: The raw result if it's a dataframe
        3. Plot: The result if it's a figure
        """
        self._last_result = result
        LAST_RESULT_CACHE["result"] = result

        # If it's a Plotly figure or has to_html, return it directly
        if isinstance(result, (go.Figure, go.FigureWidget)) or hasattr(result, 'to_html'):
            return result

        # If it's a DataFrame, return it directly
        if isinstance(result, pd.DataFrame):
            return result

        # If it's a dictionary (standard PandasAI result format)
        if isinstance(result, dict):
            res_type = result.get("type")
            res_value = result.get("value")

            if res_type == "plot" and isinstance(res_value, str):
                if os.path.exists(res_value):
                    return Image(filename=res_value)

            if res_type == "dataframe":
                return res_value

        # Fallback to standard parsing but keep it permissive
        try:
            parsed = super().parse(result)
            # If super().parse returns a path to an image, wrap it
            if isinstance(parsed, str) and (parsed.endswith('.png') or parsed.endswith('.jpg')):
                if os.path.exists(parsed):
                    return Image(filename=parsed)
            return parsed
        except Exception:
            return result

    def get_trinity(self, agent: Agent) -> TrinityResult:
        """Returns the TrinityResult for the last execution."""
        code = getattr(agent, "last_code_executed", "")

        # Log the code to the session log
        if code:
            SESSION_CODE_LOG.append(code)

        data = None
        plot = None
        answer = None

        result = self._last_result or LAST_RESULT_CACHE.get("result")

        # Support for PandasAI 3.0+ Response objects
        if result is not None and hasattr(result, "value"):
            val = result.value
            # Determine type from object class or attributes if possible
            cls_name = result.__class__.__name__
            if "DataFrame" in cls_name or isinstance(val, pd.DataFrame):
                data = val
            elif "Chart" in cls_name or "Plot" in cls_name:
                plot = val
            else:
                answer = val

            if hasattr(result, "last_code_executed") and getattr(result, "last_code_executed", None):
                code = result.last_code_executed

        # Visualization Unwrapping Logic (for dict results or raw results)
        elif isinstance(result, dict):
            res_type = result.get("type")
            res_value = result.get("value")
            if res_type == "dataframe":
                data = res_value
            elif res_type == "plot":
                plot = res_value
                # If it's a path to a file, try to load it as an Image for convenience
                if isinstance(plot, str) and os.path.exists(plot):
                    plot = Image(filename=plot)
            elif res_type == "string" or res_type == "number":
                answer = res_value
        elif isinstance(result, pd.DataFrame):
            data = result
        elif isinstance(result, (go.Figure, go.FigureWidget)):
            plot = result
        elif isinstance(result, str):
            answer = result
        elif isinstance(result, Image):
            plot = result

        return TrinityResult(
            code=code,
            data=data,
            plot=plot,
            answer=answer
        )

class BioCirvAgent(Agent):
    """Subclassed Agent to ensure TrinityResult is returned from chat()."""
    def chat(self, prompt: str, output_type: Optional[str] = None) -> TrinityResult:
        # Standard chat call
        result = super().chat(prompt, output_type)

        # In PandasAI 3.0+, response_parser is often in self.context.response_parser
        # or self.config.response_parser. We check all locations defensively.
        parser = getattr(self, "response_parser", None)
        if parser is None and hasattr(self, "context"):
            parser = getattr(self.context, "response_parser", None)
        if parser is None and hasattr(self, "config"):
            # In some versions, it's a dict, in others an object
            config = self.config
            if isinstance(config, dict):
                parser = config.get("response_parser")
            else:
                parser = getattr(config, "response_parser", None)

        if parser and hasattr(parser, 'get_trinity'):
            return parser.get_trinity(self)

        # Fallback manual wrapping if parser isn't cooperative or accessible
        # We try to see if 'result' itself carries the trinity info (PandasAI 3.0 Response objects)
        code = getattr(self, "last_code_executed", "")
        data = None
        plot = None
        answer = result

        if result is not None and hasattr(result, "value"):
            answer = result.value
            if hasattr(result, "last_code_executed") and getattr(result, "last_code_executed", None):
                code = result.last_code_executed

            cls_name = result.__class__.__name__
            if "DataFrame" in cls_name:
                data = result.value
            elif "Chart" in cls_name:
                plot = result.value

        return TrinityResult(code=code, data=data, plot=plot, answer=answer)

def init_sandbox(model_name: Optional[str] = None, cloud_mode: bool = False):
    """Initializes the sandbox environment and returns the LLM and DB config."""
    api_key = os.getenv("CBORG_API_KEY")
    api_url = os.getenv("CBORG_API_URL", "https://api.cborg.lbl.gov/v1")
    selected_model = model_name or os.getenv("CBORG_MODEL") or "gemini-3-flash"

    if not api_key:
        raise ValueError("CBORG_API_KEY not found. Please check your .env file or Colab secrets.")

    llm = CBORGLLM(api_token=api_key, api_base=api_url, model=selected_model)

    # Force use of Cloud SQL Staging settings if CLOUD_MODE is true or if explicitly initialized
    cloud_mode_env = os.getenv("CLOUD_MODE", "false").lower() == "true"
    is_cloud = cloud_mode or cloud_mode_env

    config = {
        "db_user": os.getenv("DB_USER", "biocirv_readonly" if is_cloud else "biocirv_user"),
        "db_pass": os.getenv("DB_PASS", os.getenv("DB_PASSWORD", "biocirv_dev_password")),
        "db_host": os.getenv("DB_HOST", "127.0.0.1"),
        "db_port": os.getenv("DB_PORT", "5434"),
        "db_name": os.getenv("DB_NAME", "biocirv-staging" if is_cloud else "biocirv_db"),
        "cloud_mode": is_cloud,
        "instance_connection_name": os.getenv("INSTANCE_CONNECTION_NAME"),
        "db_iam_user": os.getenv("DB_IAM_USER")
    }

    mode_str = "☁️ Cloud Mode (GCP IAM)" if config["cloud_mode"] else "💻 Local Mode"
    print(f"Initialized BioCirv AI | Model: {selected_model} | {mode_str}")
    return llm, config

def get_cloud_engine(db_config: Dict[str, Any]):
    """Creates a SQLAlchemy engine for GCP Cloud SQL using IAM Auth."""
    if not HAS_GCP_CONNECTOR:
        raise ImportError("cloud-sql-python-connector and pg8000 are required for Cloud Mode.")

    connector = Connector()

    def getconn():
        conn = connector.connect(
            db_config["instance_connection_name"],
            "pg8000",
            user=db_config["db_iam_user"],
            db=db_config["db_name"],
            enable_iam_auth=True,
            ip_type=IPTypes.PUBLIC  # Or PRIVATE if in VPC
        )
        return conn

    engine = create_engine(
        "postgresql+pg8000://",
        creator=getconn,
    )
    return engine

def get_agent(llm: CBORGLLM, db_config: Dict[str, Any], qualified_views: Optional[List[str]] = None):
    """
    Creates a SQL-first PandasAI agent using an explicit list of qualified views (schema.table).
    Example: ["ca_biositing.analysis_data_view", "data_portal.usda_census_view"]
    """

    # 1. Standardize Connection Config (The Singleton)
    # We include all discovered schemas in the search_path to allow discovery
    # and querying without explicit schema prefixes. This ensures the
    # connection dictionaries remain bit-for-bit identical (compatible).
    all_schemas = list(set([v.split(".")[0] for v in qualified_views] if qualified_views else ["ca_biositing", "data_portal"]))
    # Ensure public is present for system types/extensions
    if "public" not in all_schemas:
        all_schemas.append("public")
    search_path = ",".join(all_schemas)

    # CRITICAL: This MUST be bit-for-bit identical for every VirtualDataFrame.
    # We add 'options' to set the search_path. We provide it both at the top level
    # and within connect_args to ensure compatibility across different PandasAI/SQLAlchemy versions.
    connection_params = {
        "host": str(db_config.get('db_host', '127.0.0.1')),
        "port": int(db_config.get('db_port', 5434)),
        "database": str(db_config['db_name']),
        "user": str(db_config['db_user']),
        "password": str(db_config['db_pass']),
        "options": f"-c search_path={search_path}",
        "connect_args": {
            "options": f"-c search_path={search_path}"
        }
    }

    # 1b. Create a shared SQLAlchemy engine for "Manual Injection" fallback
    # Since the Cloud SQL Proxy is running on localhost:5434, we use the
    # standard psycopg2 engine for discovery regardless of cloud_mode.
    try:
        # Create a basic engine for introspection without complex options
        # We rely on explicit schema naming during discovery
        url = f"postgresql+psycopg2://{connection_params['user']}:{connection_params['password']}@{connection_params['host']}:{connection_params['port']}/{connection_params['database']}"
        engine = create_engine(url)

        # Test the engine immediately
        with engine.connect() as conn:
            print(f"  🔗 Introspection engine connected to {connection_params['database']}")
            # Check schema existence
            res = conn.execute(text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'ca_biositing'"))
            if not res.fetchone():
                print("  ❌ WARNING: schema 'ca_biositing' not found in database!")
            else:
                print("  ✅ Schema 'ca_biositing' verified.")
    except Exception as e:
        print(f"  ⚠️ Failed to initialize introspection engine: {e}")
        engine = None

    # 2. Use default views if none provided
    if not qualified_views:
        qualified_views = [
            "ca_biositing.analysis_data_view",
            "ca_biositing.analysis_average_view",
            "ca_biositing.billion_ton_tileset_view",
            "ca_biositing.landiq_record_view",
            "ca_biositing.usda_census_view",
            "ca_biositing.usda_survey_view"
        ]

    connectors = []

    # Generate a session-specific timestamp to avoid stale registry hits in Colab
    import time
    session_ts = int(time.time())

    print(f"📦 Registering {len(qualified_views)} virtual datasets...")

    for view in qualified_views:
        try:
            # IMPORTANT: PandasAI 3.0+ expects 'org/dataset' format.
            # It also requires lowercase and hyphens (no underscores).
            safe_name = view.replace(".", "-").replace("_", "-").lower()
            dataset_path = f"biocirv/{safe_name}-{session_ts}"

            # Split schema and table for explicit schema parsing
            schema_part = view.split(".")[0] if "." in view else "public"
            table_part = view.split(".")[1] if "." in view else view

            # FALLBACK: Manual Metadata Discovery
            # If standard registration has been returning 0 columns, we fetch them manually.
            manual_columns = []
            manual_rows = 0
            if engine:
                try:
                    # 1. Try Primitive SQL Fallback (Most reliable for PostGIS views)
                    # We do this first to avoid SQLAlchemy's type-parsing logic for 'geometry' types.
                    with engine.connect() as conn:
                        # Quote names to handle case sensitivity and special chars
                        # Use a simpler query if needed
                        query = text(f'SELECT * FROM "{schema_part}"."{table_part}" LIMIT 0')
                        res = conn.execute(query)
                        manual_columns = [col for col in res.keys()]
                        if manual_columns:
                            print(f"    🔍 Manual SQL discovery success: {len(manual_columns)} columns")
                            # Also fetch row count to prevent the Loader failure later
                            try:
                                res_count = conn.execute(text(f'SELECT count(*) FROM "{schema_part}"."{table_part}"'))
                                row = res_count.fetchone()
                                manual_rows = row[0] if row else 0
                                print(f"    🔍 Manual row count success: {manual_rows} rows")
                            except Exception as e_count:
                                print(f"    ⚠️ Manual row count failed for {view}: {e_count}")
                except Exception as e1:
                    # 2. Try SQLAlchemy Inspector as backup
                    try:
                        from sqlalchemy import inspect
                        inspector = inspect(engine)
                        cols = inspector.get_columns(table_part, schema=schema_part)
                        if not cols:
                            cols = inspector.get_columns(table_part)
                        if cols:
                            manual_columns = [c['name'] for c in cols]
                    except Exception as e2:
                        print(f"  ⚠️ Manual discovery for {view} failed (SQL: {e1}, Inspector: {e2})")

            source_config = {
                "type": "postgres",
                "table": table_part,
                "schema": schema_part,
                "table_name": table_part,
                "schema_name": schema_part,
                "connection": connection_params
            }

            # If we found columns manually, inject them into the source config
            # This 'forced' injection bypasses the failing SQLAlchemy introspection inside PandasAI.
            # We use both 'columns' and 'fields' to satisfy different internal schema requirements.
            if manual_columns:
                source_config["columns"] = manual_columns
                source_config["fields"] = manual_columns

            # GHOST FRAME STRATEGY:
            # We wrap the empty pandas DataFrame in a PandasAI DataFrame
            # to satisfy the library's type checking.
            from pandasai import DataFrame as PA_DataFrame

            # If we don't have manual columns, we try one last effort to get them
            # or we use a minimal set to at least allow the object to be created.
            effective_columns = manual_columns if manual_columns else ["id", "value"]
            ghost_df = PA_DataFrame(pd.DataFrame(columns=effective_columns))

            vdf = None
            errors = []

            # Attempt 1: Advanced SQLDatasetLoader creation
            # This is the most robust way to ensure a data_loader is attached
            if HAS_ADVANCED_LOADERS:
                try:
                    # Construct a SemanticLayerSchema manually
                    # We use the FULL view name (schema.table) for the source config to avoid UndefinedTable
                    advanced_source_config = source_config.copy()
                    advanced_source_config["table"] = view

                    schema_data = {
                        "name": safe_name,
                        "description": f"BioCirv view: {view}",
                        "source": advanced_source_config,
                        "columns": [{"name": col, "type": "string"} for col in effective_columns]
                    }
                    pa_schema = SemanticLayerSchema(**schema_data)
                    loader = SQLDatasetLoader(pa_schema, dataset_path)

                    vdf = VirtualDataFrame(
                        data_loader=loader,
                        path=dataset_path
                    )
                    # Manually attach schema for serialization if needed
                    vdf.schema = pa_schema
                    print(f"    ✅ Created VirtualDataFrame via manual SQLDatasetLoader for {view}")
                except Exception as e0:
                    errors.append(f"advanced_loader: {e0}")

            # Attempt 2: Use create_dataset factory
            if vdf is None:
                try:
                    vdf = create_dataset(
                        path=dataset_path,
                        description=f"BioCirv view: {view}",
                        source=source_config
                    )
                    print(f"    ✅ Created VirtualDataFrame via factory for {view}")
                except Exception as e:
                    errors.append(f"factory: {e}")

            # Attempt 3: VirtualDataFrame with Ghost Frame (Manual)
            if vdf is None:
                try:
                    vdf = VirtualDataFrame(
                        source=source_config,
                        description=f"BioCirv view: {view}",
                        df=ghost_df
                    )
                    print(f"    ✅ Created VirtualDataFrame with Ghost Frame for {view}")
                except Exception as e2:
                    errors.append(f"vdf+ghost: {e2}")

            # Attempt 4: Pure VirtualDataFrame (Pure SQL)
            if vdf is None:
                try:
                    vdf = VirtualDataFrame(
                        source=source_config,
                        description=f"BioCirv view: {view}"
                    )
                    print(f"    ✅ Created pure VirtualDataFrame for {view}")
                except Exception as e3:
                    errors.append(f"vdf-pure: {e3}")
                    print(f"    ❌ Failed all attempts for {view}: {'; '.join(errors)}")
                    continue

            # Final forced injection into the specific internal containers we found in DIR logs
            if manual_columns:
                targets = [
                    (vdf, "_columns"),
                    (vdf, "columns"),
                    (getattr(vdf, "_connector", None), "columns"),
                    (getattr(vdf, "_connector", None), "_columns")
                ]
                for obj, attr in targets:
                    if obj is not None:
                        try:
                            # Use Index for 'columns', list for others
                            val = pd.Index(manual_columns) if attr == "columns" else manual_columns
                            object.__setattr__(obj, attr, val)
                        except Exception:
                            continue

                # Inject row count into loader to prevent execution during serialization
                loader = getattr(vdf, "_loader", None)
                if loader:
                    # Inject into the internal attribute if it exists
                    try:
                        object.__setattr__(loader, "_row_count", manual_rows)
                    except Exception:
                        pass

                    # Use method-level shadowing on the instance to return the manual count
                    # This prevents the loader from attempting to execute a COUNT(*) query
                    # during prompt serialization.
                    try:
                        loader.get_row_count = lambda: manual_rows
                    except Exception:
                        pass

                # Shadow at the VDF instance level as well.
                # In some versions of PandasAI, rows_count is a property or an attribute.
                try:
                    # Try setting attribute
                    object.__setattr__(vdf, "rows_count", manual_rows)
                    object.__setattr__(vdf, "_rows_count", manual_rows)
                except Exception:
                    pass

            # Verify columns were fetched
            # Avoid direct truth check on RangeIndex/Index to prevent "ambiguous truth value" error
            cols = getattr(vdf, "columns", [])

            # GHOST HEAD INJECTION:
            # We inject a dummy head to prevent PandasAI from attempting to query
            # the database during prompt serialization (which often fails due to search_path issues).
            if vdf is not None:
                try:
                    # Construct dummy data with same columns
                    dummy_head = pd.DataFrame(columns=manual_columns if manual_columns else effective_columns)

                    # We use object.__setattr__ to bypass property setters and force the cache
                    object.__setattr__(vdf, "_head", dummy_head)

                    # Also shadow the head method on the instance to return the dummy
                    vdf.head = lambda n=5: dummy_head
                except Exception:
                    pass

            # SEMANTIC LAYER INJECTION:
            # In PandasAI 3.0+, metadata is often read from the schema object.
            # We force-inject the columns into the schema object if it exists.
            if vdf is not None and hasattr(vdf, "schema") and vdf.schema is not None:
                try:
                    if manual_columns:
                        vdf.schema.columns = [{"name": col, "type": "string"} for col in manual_columns]
                except Exception:
                    pass

            if cols is None or len(cols) == 0:
                print(f"  ⚠️ {view}: No columns found.")
                # DIAGNOSTIC: Show us what's inside this object
                print(f"    🛠️ VDF Attributes: {[a for a in dir(vdf) if not a.startswith('__')]}")
                if hasattr(vdf, "_connector"):
                    print(f"    🛠️ Connector Attributes: {[a for a in dir(vdf._connector) if not a.startswith('__')]}")
            else:
                print(f"  ✅ {view}: Ready ({len(cols)} columns)")

            connectors.append(vdf)
        except Exception as e:
            print(f"  ❌ Error registering {view}: {e}")

    if not connectors:
        raise RuntimeError("Failed to register any VirtualDataFrames. Agent cannot start.")

    # 3. Configure Agent
    agent = BioCirvAgent(
        connectors,
        config={
            "llm": llm,
            "verbose": True,
            "response_parser": SandboxResponseParser,
            "enable_cache": False,
            "use_error_correction_framework": True,
            "max_retries": 2,
            "custom_whitelisted_dependencies": ["sqlalchemy", "psycopg2", "plotly", "matplotlib", "seaborn"],
            "save_charts": True,
            "save_charts_path": "exports/charts",
        }
    )

    # FINAL FIX: Add custom system prompt to guide LLM away from schema prefixes
    # and towards using correct column names from the provided metadata.
    try:
        # Check for both agent and its internal context messages
        msg = (
            "System: You are a PostgreSQL expert. Use the provided column names. "
            "CRITICAL: Always refer to tables BY THEIR QUALIFIED NAME (e.g. 'ca_biositing.analysis_data_view'). "
            "Table names in SQL MUST include the schema prefix (e.g. 'ca_biositing.') in ALL your queries to avoid 'UndefinedTable' errors. "
            "The search_path is set to include 'ca_biositing', 'data_portal', and 'public'. "
            "IMPORTANT: The 'value' column is a NUMERIC type. Do NOT use string functions like LIKE, REPLACE, or regex on it. "
            "Simply use SUM(value), AVG(value), etc. "
            "Keep SQL simple and standard to avoid parser errors."
        )
        if hasattr(agent, "add_message"):
            agent.add_message(msg)
        elif hasattr(agent, "context") and hasattr(agent.context, "messages"):
            agent.context.messages.append({
                "role": "system",
                "content": msg
            })
    except Exception as e:
        print(f"  ⚠️ Failed to inject system message: {e}")

    return agent
