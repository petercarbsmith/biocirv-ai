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
        code = getattr(agent, "last_code_executed", "")

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

class BioCirvAgent(Agent):
    """Subclassed Agent to ensure TrinityResult is returned from chat()."""
    def chat(self, prompt: str, output_type: Optional[str] = None) -> TrinityResult:
        # Standard chat call
        result = super().chat(prompt, output_type)

        # In recent versions, chat() might return the result directly
        # or it might be stored in the parser.
        if hasattr(self.response_parser, 'get_trinity'):
            return self.response_parser.get_trinity(self)

        # Fallback manual wrapping if parser isn't cooperative
        code = getattr(self, "last_code_executed", "")
        return TrinityResult(code=code, answer=result)

def init_sandbox(model_name: Optional[str] = None, cloud_mode: bool = False):
    """Initializes the sandbox environment and returns the LLM and DB config."""
    api_key = os.getenv("CBORG_API_KEY")
    api_url = os.getenv("CBORG_API_URL", "https://api.cborg.lbl.gov/v1")
    selected_model = model_name or os.getenv("CBORG_MODEL") or "gemini-3-flash"

    if not api_key:
        raise ValueError("CBORG_API_KEY not found. Please check your .env file or Colab secrets.")

    llm = CBORGLLM(api_token=api_key, api_base=api_url, model=selected_model)

    # Use 5434 as default port to avoid conflicts in Colab/local
    config = {
        "db_user": os.getenv("DB_USER", os.getenv("DB_IAM_USER", "biocirv_user")),
        "db_pass": os.getenv("DB_PASSWORD", os.getenv("DB_PASS", "biocirv_dev_password")),
        "db_host": os.getenv("DB_HOST", "127.0.0.1"),
        "db_port": os.getenv("DB_PORT", "5434"),
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

def get_agent(llm: CBORGLLM, db_config: Dict[str, Any], schemas: List[str] = ["ca_biositing", "data_portal"], view_names: Optional[List[str]] = None):
    """Creates a SQL-first PandasAI agent using SQLConnector or SQLAlchemy engine."""

    # Add search_path to connection arguments for PostgreSQL
    search_path = ",".join(schemas)

    if db_config.get("cloud_mode"):
        # When using the Proxy strategy, we can use standard psycopg2 for discovery
        # if the proxy is running on localhost.
        # Fallback to get_cloud_engine (Python Connector) if Proxy isn't preferred or available.
        if db_config.get("db_host") in ["localhost", "127.0.0.1", "0.0.0.0"]:
             import urllib.parse
             user = urllib.parse.quote_plus(db_config['db_user'])
             # For IAM Auth through proxy, we often don't need a password if --auto-iam-auth is used,
             # but SQLAlchemy URL needs a placeholder.
             db_url = f"postgresql+psycopg2://{user}:{db_config['db_pass']}@{db_config['db_host']}:{db_config['db_port']}/{db_config['db_name']}"
             
             # Increase pool recycle and add SSL mode disable (Proxy handles SSL)
             engine = create_engine(
                 db_url,
                 connect_args={"sslmode": "disable"},
                 pool_pre_ping=True
             )
             print(f"🔌 Connecting to database via Cloud SQL Proxy (Localhost:{db_config['db_port']})")
        else:
             engine = get_cloud_engine(db_config)
             print("☁️ Connecting to database via Cloud SQL Python Connector (IAM)")
    else:
        # Create engine for discovery
        db_url = f"postgresql+psycopg2://{db_config['db_user']}:{db_config['db_pass']}@{db_config['db_host']}:{db_config['db_port']}/{db_config['db_name']}"
        engine = create_engine(db_url)
    
    try:
        if view_names is None:
            view_names = discover_views(engine, schemas)
    except Exception as e:
        print(f"⚠️ Warning: View discovery failed: {e}")
        view_names = ["analysis_data_view"] # Fallback to a safe guess

    # Configure connectors using the new Semantic Layer API (PandasAI 3.0+)
    connectors = []

    # Import load/create once
    try:
        from pandasai import load as load_func
        load_dataset = load_func
    except ImportError:
        load_dataset = None

    # Phase 2: Create Virtual DataFrames
    for view in view_names:
        try:
            # Check if dataset already exists to avoid ValueError
            view_path = view.lower().replace("_", "-")
            dataset_path = f"biocirv/{view_path}"

            if load_dataset:
                try:
                    vdf = load_dataset(dataset_path)
                    connectors.append(vdf)
                    continue
                except Exception:
                    # If load fails, we proceed to create
                    pass

            # In PandasAI 3.0+, we use 'create' to define a VirtualDataFrame
            # and provide a 'source' dictionary.
            if db_config.get("cloud_mode"):
                # Hybrid Authentication Strategy:
                # 1. Cloud SQL Proxy handles the secure tunnel (IAM).
                # 2. Application logs in with traditional username/password (Static).
                source_config = {
                    "type": "postgres",
                    "table": view,
                    "connection": {
                        "host": db_config.get('db_host', '127.0.0.1'),
                        "port": int(db_config.get('db_port', 5434)),
                        "database": db_config['db_name'],
                        "user": db_config['db_user'],
                        "password": db_config['db_pass']
                    }
                }
            else:
                source_config = {
                    "type": "postgres",
                    "table": view,
                    "connection": {
                        "host": db_config['db_host'],
                        "port": int(db_config['db_port']),
                        "database": db_config['db_name'],
                        "user": db_config['db_user'],
                        "password": db_config['db_pass']
                    }
                }

            # Use 'create' to get a VirtualDataFrame
            # Convert view name to lowercase and hyphens for the path
            view_path = view.lower().replace("_", "-")

            vdf = create_dataset(
                path=f"biocirv/{view_path}",
                description=f"BioCirv view: {view}",
                source=source_config
            )
            connectors.append(vdf)
        except Exception as e:
            print(f"⚠️ Error creating VirtualDataFrame for view {view}: {e}")

    if not connectors:
        # Fallback to a default view if discovery failed
        default_table = "analysis_data_view"

        if load_dataset:
            try:
                default_path = default_table.lower().replace("_", "-")
                dataset_path = f"biocirv/{default_path}"
                vdf = load_dataset(dataset_path)
                connectors.append(vdf)
            except Exception:
                pass

    if not connectors:
        # Still none? Try creating default
        default_table = "analysis_data_view" # Ensure it is defined
        try:
            source_config = {
                "type": "postgres",
                "table": default_table,
                "connection": {
                    "host": db_config.get('db_host', '127.0.0.1'),
                    "port": int(db_config.get('db_port', 5434)),
                    "database": db_config['db_name'],
                    "user": db_config.get('db_user', db_config.get('db_iam_user')),
                    "password": db_config.get('db_pass', 'none')
                }
            }
            # Convert to lowercase and hyphens
            default_path = default_table.lower().replace("_", "-")

            vdf = create_dataset(
                path=f"biocirv/{default_path}",
                description=f"BioCirv default view: {default_table}",
                source=source_config
            )
            connectors.append(vdf)
        except Exception as e:
            print(f"⚠️ Error creating default VirtualDataFrame: {e}")

    # Configure Agent
    # In PandasAI 3.0+, Agent expects a list of (Virtual)DataFrames.
    agent = BioCirvAgent(
        connectors,
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
