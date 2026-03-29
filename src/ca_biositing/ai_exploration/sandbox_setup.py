import sys
import os
import pandas as pd
import requests
import json
import plotly.io as pio
import plotly.graph_objects as go
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
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
            prompt += "\n\nCRITICAL: You are querying a PostgreSQL database. Always use PostgreSQL-compatible syntax (e.g., use RANDOM() instead of RAND() for random ordering)."

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

        # If it's a Plotly figure or has to_html, return it directly
        if isinstance(result, go.Figure) or hasattr(result, 'to_html'):
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

    def get_trinity(self, agent: Agent) -> Dict[str, Any]:
        """Returns the Code, Data, and Plot for the last execution."""
        code = agent.last_code_executed
        data = None
        plot = None
        answer = None

        result = self._last_result

        if isinstance(result, dict):
            res_type = result.get("type")
            res_value = result.get("value")
            if res_type == "dataframe":
                data = res_value
            elif res_type == "plot":
                plot = res_value
            elif res_type == "string":
                answer = res_value
        elif isinstance(result, pd.DataFrame):
            data = result
        elif isinstance(result, (go.Figure, go.FigureWidget)):
            plot = result
        elif isinstance(result, str):
            answer = result

        return {
            "code": code,
            "data": data,
            "plot": plot,
            "answer": answer
        }

def init_sandbox(model_name: Optional[str] = None):
    """Initializes the sandbox environment and returns the LLM and DB config."""
    api_key = os.getenv("CBORG_API_KEY")
    api_url = os.getenv("CBORG_API_URL", "https://api.cborg.lbl.gov/v1")
    selected_model = model_name or os.getenv("CBORG_MODEL") or "gemini-3-flash"

    if not api_key:
        raise ValueError("CBORG_API_KEY not found. Please check your .env file.")

    llm = CBORGLLM(api_token=api_key, api_base=api_url, model=selected_model)

    config = {
        "db_user": os.getenv("DB_USER", "biocirv_user"),
        "db_pass": os.getenv("DB_PASSWORD", "biocirv_dev_password"),
        "db_host": os.getenv("DB_HOST", "localhost"),
        "db_port": os.getenv("DB_PORT", "5432"),
        "db_name": os.getenv("DB_NAME", "biocirv_db")
    }

    print(f"Initialized BioCirv AI with model: {selected_model}")
    return llm, config

def get_agent(llm: CBORGLLM, db_config: Dict[str, str], schemas: List[str] = ["ca_biositing", "analytics", "data_portal"], view_names: Optional[List[str]] = None):
    """Creates a SQL-first PandasAI agent using SQLConnector."""

    # Create engine for discovery
    db_url = f"postgresql+psycopg2://{db_config['db_user']}:{db_config['db_pass']}@{db_config['db_host']}:{db_config['db_port']}/{db_config['db_name']}"

    # Add search_path to connection arguments for PostgreSQL
    search_path = ",".join(schemas)

    # Discover views across all requested schemas to provide context if not provided
    engine = create_engine(db_url)
    if view_names is None:
        view_names = discover_views(engine, schemas)

    # Configure PostgreSQLConnectors for all discovered views
    connectors = []
    # For Phase 1, we register all discovered views as connectors to enable multi-df joins
    for view in view_names:
        connectors.append(PostgreSQLConnector(config={
            "username": db_config['db_user'],
            "password": db_config['db_pass'],
            "host": db_config['db_host'],
            "port": db_config['db_port'],
            "database": db_config['db_name'],
            "table": view,
            "where": None,
            "connect_args": {
                "options": f"-c search_path={search_path}"
            }
        }))

    if not connectors:
        # Fallback if discovery fails
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
