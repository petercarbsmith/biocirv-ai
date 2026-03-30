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
from pandasai import Agent
from pandasai.connectors import PostgreSQLConnector
from pandasai.responses.response_parser import ResponseParser

# Internal imports
from ca_biositing.ai_exploration.schema import discover_views, fetch_table_metadata

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
        if self.answer:
            print(f"Answer: {self.answer}")
        if self.plot:
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
        code = agent.last_code_executed

        # Log the code to the session log
        if code:
            SESSION_CODE_LOG.append(code)

        data = None
        plot = None
        answer = None

        result = self._last_result or LAST_RESULT_CACHE.get("result")

        # Visualization Unwrapping Logic
        if isinstance(result, dict):
            res_type = result.get("type")
            res_value = result.get("value")
            if res_type == "dataframe":
                data = res_value
            elif res_type == "plot":
                plot = res_value
                # If it's a path to a file, try to load it as an Image for convenience
                if isinstance(plot, str) and os.path.exists(plot):
                    plot = Image(filename=plot)
            elif res_type == "string":
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

def init_sandbox(model_name: Optional[str] = None, cloud_mode: bool = False):
    """Initializes the sandbox environment and returns the LLM and DB config."""
    api_key = os.getenv("CBORG_API_KEY")
    api_url = os.getenv("CBORG_API_URL", "https://api.cborg.lbl.gov/v1")
    selected_model = model_name or os.getenv("CBORG_MODEL") or "gemini-3-flash"

    if not api_key:
        raise ValueError("CBORG_API_KEY not found. Please check your .env file or Colab secrets.")

    llm = CBORGLLM(api_token=api_key, api_base=api_url, model=selected_model)

    config = {
        "db_user": os.getenv("DB_USER", "biocirv_user"),
        "db_pass": os.getenv("DB_PASSWORD", "biocirv_dev_password"),
        "db_host": os.getenv("DB_HOST", "localhost"),
        "db_port": os.getenv("DB_PORT", "5432"),
        "db_name": os.getenv("DB_NAME", "biocirv_db"),
        "cloud_mode": cloud_mode or os.getenv("CLOUD_MODE", "false").lower() == "true",
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

def get_agent(llm: CBORGLLM, db_config: Dict[str, Any], schemas: List[str] = ["ca_biositing", "analytics", "data_portal"], view_names: Optional[List[str]] = None):
    """Creates a SQL-first PandasAI agent using SQLConnector."""

    # Add search_path to connection arguments for PostgreSQL
    search_path = ",".join(schemas)

    if db_config.get("cloud_mode"):
        engine = get_cloud_engine(db_config)
    else:
        # Create engine for discovery
        db_url = f"postgresql+psycopg2://{db_config['db_user']}:{db_config['db_pass']}@{db_config['db_host']}:{db_config['db_port']}/{db_config['db_name']}"
        engine = create_engine(db_url)
    if view_names is None:
        view_names = discover_views(engine, schemas)

    # Configure PostgreSQLConnectors for all discovered views
    connectors = []

    # Phase 2: Enrich schema metadata
    for view in view_names:
        # Fetch metadata/field descriptions for the view
        field_descriptions = {}
        try:
            # We use the fetch_table_metadata to at least get columns,
            # ideally we'd have a source for actual descriptions.
            # For now, we'll label them from documentation if available.
            column_str = fetch_table_metadata(engine, view)
            # You could parse column_str to build field_descriptions if needed
        except Exception:
            pass

        if db_config.get("cloud_mode"):
            # For Cloud SQL IAM, we use the engine directly if possible,
            # but PostgreSQLConnector expects credentials.
            # PandasAI SQLConnector also supports SQLAlchemy engine directly in recent versions
            # or we can pass a custom creator/url.
            connectors.append(PostgreSQLConnector(config={
                "username": db_config['db_iam_user'],
                "database": db_config['db_name'],
                "table": view,
                "driver": "pg8000",
                "field_descriptions": field_descriptions,
                "use_sqlalchemy": True,
                "engine": engine, # Some versions of PandasAI allow passing the engine
                "connect_args": {
                    "options": f"-c search_path={search_path}"
                }
            }))
        else:
            connectors.append(PostgreSQLConnector(config={
                "username": db_config['db_user'],
                "password": db_config['db_pass'],
                "host": db_config['db_host'],
                "port": db_config['db_port'],
                "database": db_config['db_name'],
                "table": view,
                "where": None,
                "field_descriptions": field_descriptions,
                "connect_args": {
                    "options": f"-c search_path={search_path}"
                }
            }))

    if not connectors:
        # Fallback if discovery fails
        if db_config.get("cloud_mode"):
            connectors.append(PostgreSQLConnector(config={
                "username": db_config['db_iam_user'],
                "database": db_config['db_name'],
                "table": "analysis_data_view",
                "use_sqlalchemy": True,
                "engine": engine,
                "connect_args": {
                    "options": f"-c search_path={search_path}"
                }
            }))
        else:
            connectors.append(PostgreSQLConnector(config={
                "username": db_config['db_user'],
                "password": db_config['db_pass'],
                "host": db_config['db_host'],
                "port": db_config['db_port'],
                "database": db_config['db_name'],
                "table": "analysis_data_view",
                "where": None,
                "connect_args": {
                    "options": f"-c search_path={search_path}"
                }
            }))

    # Configure Agent
    agent = Agent(
        connectors,
        description="A PostgreSQL database containing BioCirv analytics and geospatial views.",
        config={
            "llm": llm,
            "verbose": True,
            "response_parser": SandboxResponseParser,
            "enable_cache": False,
            "use_error_correction_framework": True,
            "custom_whitelisted_dependencies": ["sqlalchemy", "psycopg2", "plotly", "matplotlib", "seaborn"],
            "save_charts": True,
            "save_charts_path": "exports/charts",
        }
    )

    # Ensure search_path is set for the connection if possible via engine/connector
    # For PostgreSQL, we can often pass it in connection arguments or execute it
    # SQLConnector uses sqlalchemy under the hood.

    return agent
