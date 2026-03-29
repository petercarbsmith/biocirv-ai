import sys
import os
import functools
import pandas as pd
import requests
import json
import plotly.io as pio
import plotly.graph_objects as go
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from IPython.display import display, Image, HTML
from typing import Optional, List, Any

# --- 1. Notebook Recovery ---
def is_notebook():
    try:
        from IPython import get_ipython
        if get_ipython() is None: return False
        shell = get_ipython().__class__.__name__
        return shell == 'ZMQInteractiveShell'
    except (NameError, ImportError):
        return False

if is_notebook() and not hasattr(sys, "_PANDASAI_PURGED"):
    # Purge existing pandasai modules to force a clean state for our patches
    for mod in list(sys.modules.keys()):
        if mod.startswith("pandasai") and mod != "pandasai.pandas":
            del sys.modules[mod]
    sys._PANDASAI_PURGED = True

# --- 2. PandasAI Imports ---
try:
    from pandasai.llm.base import LLM
except ImportError:
    try:
        from pandasai.llm import LLM
    except ImportError:
        LLM = object

try:
    from pandasai.responses.response_parser import ResponseParser
except ImportError:
    try:
        from pandasai.core.response.parser import ResponseParser
    except ImportError:
        from pandasai.responses import ResponseParser

from pandasai import Agent, SmartDataframe, skill

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

# --- 3. Targeted Patches for Unhashable Type Errors ---
def apply_targeted_patches():
    """Applies surgical patches to PandasAI to prevent hashing errors in Jupyter."""
    try:
        import pandasai.schemas.df_config
        import pandasai.agent
        import pandasai.smart_dataframe
        import pandasai.connectors.base
        import pandasai.smart_datalake

        PAIConfig = pandasai.schemas.df_config.Config
        PAIAgent = pandasai.agent.Agent
        PAISDF = pandasai.smart_dataframe.SmartDataframe
        PAIDatalake = pandasai.smart_datalake.SmartDatalake
        BaseConnector = pandasai.connectors.base.BaseConnector
        BaseConnectorConfig = pandasai.connectors.base.BaseConnectorConfig

        # A. Patch Config to ensure lists are converted to tuples where needed for hashing
        # This is the most common source of "unhashable type: 'list'"
        _original_config_init = PAIConfig.__init__
        def _patched_config_init(self, **data):
            for key in ["custom_whitelisted_dependencies", "middlewares", "additional_filters"]:
                if key in data and isinstance(data[key], list):
                    data[key] = tuple(data[key])
            _original_config_init(self, **data)
        PAIConfig.__init__ = _patched_config_init

        # B. Force ID-based hashability for core classes
        # This prevents Pydantic from trying to content-hash objects whose identities drift in Jupyter
        for cls in [PAIAgent, PAISDF, PAIDatalake, BaseConnector, PAIConfig, BaseConnectorConfig]:
            cls.__hash__ = lambda self: id(self)

        # C. Patch Agent.chat to provide full traceback in notebook for better debugging
        _original_chat = PAIAgent.chat
        def _patched_chat(self, *args, **kwargs):
            try:
                return _original_chat(self, *args, **kwargs)
            except Exception:
                import traceback
                print("\n!!! AGENT CHAT CRITICAL FAILURE !!!")
                traceback.print_exc()
                raise
        PAIAgent.chat = _patched_chat

    except Exception as e:
        if is_notebook():
            print(f"DEBUG: Patching failed (this is expected if modules are being reloaded): {e}")

apply_targeted_patches()

class CBORGLLM(LLM):
    """Hardened Custom LLM class for CBORG gateway"""
    def __init__(self, api_token: str, api_base: str = "https://api.cborg.lbl.gov/v1", model: str = "gemini-3-flash"):
        super().__init__()
        self.api_token = api_token
        self.api_base = api_base
        self.model = model
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        })

    def __hash__(self):
        return id(self)

    def call(self, instruction, context=None):
        prompt = instruction.to_string()
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
    def type(self):
        return "cborg"

    def generate_code(self, instruction, context):
        """Resilient code generation and extraction"""
        response = self.call(instruction, context)

        def clean_potential_code(code_str):
            lines = code_str.splitlines()
            cleaned = []
            for line in lines:
                if line.strip().startswith('type (possible values "string"'):
                    continue
                if "# TODO: import" in line:
                    continue
                cleaned.append(line)
            return "\n".join(cleaned).strip()

        try:
            extracted = self._extract_code(response)
            return clean_potential_code(extracted)
        except Exception:
            import re
            code_blocks = re.findall(r"```(?:python|py)?\n(.*?)```", response, re.DOTALL)
            if code_blocks:
                for block in code_blocks:
                    if "result =" in block:
                        cleaned = clean_potential_code(block)
                        if self._is_python_code(cleaned):
                            return cleaned
                cleaned = clean_potential_code(code_blocks[0])
                return cleaned

            if "result =" in response:
                lines = response.splitlines()
                code_lines = []
                in_code = False
                for line in lines:
                    if any(line.strip().startswith(p) for p in ["import ", "df =", "dfs[", "result =", "query =", "try:"]):
                        in_code = True
                    if in_code:
                        if line.strip().startswith('type (possible values "string"'):
                            continue
                        code_lines.append(line)

                if code_lines:
                    candidate = "\n".join(code_lines)
                    if self._is_python_code(candidate):
                        return candidate
            raise

class SandboxResponseParser(ResponseParser):
    """
    Custom Response Parser for the AI Sandbox.
    Ensures DataFrames and Plotly Figures are returned as raw objects
    to enable native VS Code / Jupyter rendering.
    """
    def __init__(self, context):
        super().__init__(context)

    def _validate_response(self, result: Any):
        """Extremely permissive validator to allow raw objects."""
        return

    def parse(self, result: Any, last_code_executed: str = None) -> Any:
        """Override parse to return raw values instead of wrapped Response objects."""
        if isinstance(result, pd.DataFrame):
            return result

        if isinstance(result, go.Figure) or hasattr(result, 'to_html'):
            return result

        parsed_result = None
        if isinstance(result, dict):
            if "data" in result and "layout" in result:
                try:
                    parsed_result = go.Figure(result)
                except Exception:
                    pass

            if parsed_result is None:
                response_type = result.get("type")
                if response_type == "plot":
                    parsed_result = self.format_plot(result)
                elif response_type in ["dataframe", "table"]:
                    val = result.get("value")
                    if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                        parsed_result = pd.DataFrame(val)
                    else:
                        parsed_result = val

            if parsed_result is None:
                for key, val in result.items():
                    if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                        try:
                            parsed_result = pd.DataFrame(val)
                            break
                        except Exception:
                            pass

        if parsed_result is None:
            try:
                base_response = super().parse(result, last_code_executed)
                parsed_result = getattr(base_response, 'value', base_response)
            except Exception:
                parsed_result = result

        if isinstance(parsed_result, str):
            lower_res = parsed_result.lower()
            if any(marker in lower_res for marker in ["<html", "<div", "plotly", "window.plotlyconfig"]):
                return HTML(parsed_result)

            if (parsed_result.strip().startswith('{"data":') or parsed_result.strip().startswith('{"layout":')) and len(parsed_result) > 100:
                try:
                    return go.Figure(json.loads(parsed_result))
                except Exception:
                    pass

        if isinstance(parsed_result, str) and (parsed_result.endswith('.png') or parsed_result.endswith('.jpg')):
            if os.path.exists(parsed_result):
                return Image(filename=parsed_result)

        return parsed_result

    def format_plot(self, result: dict) -> Any:
        val = result.get("value")
        if isinstance(val, dict) and "data" in val and "layout" in val:
            try:
                return go.Figure(val)
            except Exception:
                return val
        if isinstance(val, go.Figure) or hasattr(val, 'to_html'):
            return val
        if isinstance(val, str) and any(marker in val.lower() for marker in ["<html", "<div", "plotly"]):
            return val
        if isinstance(val, str) and (val.endswith('.png') or val.endswith('.jpg')):
            if os.path.exists(val):
                return Image(filename=val)
            rel_path = os.path.join(os.getcwd(), val)
            if os.path.exists(rel_path):
                return Image(filename=rel_path)
        return super().format_plot(result)

    def format_dataframe(self, result: dict) -> pd.DataFrame:
        return result.get("value")

    def format_table(self, result: dict) -> pd.DataFrame:
        return result.get("value")

def init_sandbox(model_name: Optional[str] = None):
    """Initializes the sandbox environment and returns the LLM and DB engine."""
    api_key = os.getenv("CBORG_API_KEY")
    api_url = os.getenv("CBORG_API_URL", "https://api.cborg.lbl.gov/v1")
    selected_model = model_name or os.getenv("CBORG_MODEL") or "gemini-3-flash"

    if not api_key:
        raise ValueError("CBORG_API_KEY not found. Please check your .env file.")

    llm = CBORGLLM(api_token=api_key, api_base=api_url, model=selected_model)

    DB_USER = os.getenv("DB_USER", "biocirv_user")
    DB_PASS = os.getenv("DB_PASSWORD", "biocirv_dev_password")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "biocirv_db")

    DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(DATABASE_URL)

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"Initialized BioCirv AI with model: {selected_model}")
        print(f"Connected to Database: {DB_NAME}")
    except Exception as e:
        print(f"WARNING: Database connection failed: {e}")

    return llm, engine

def get_agent(llm, engine, view_names: Optional[List[str]] = None, schemas: List[str] = ["ca_biositing", "data_portal"]):
    """Creates a PandasAI agent with enriched metadata and custom SQL skill."""

    # If no views provided, auto-discover them
    if view_names is None:
        view_names = discover_views(engine, schemas)

    # 1. Define SQL Skill
    @skill
    def execute_sql_query(query: str):
        """
        Executes a read-only SQL SELECT query against the PostgreSQL database.
        Use this for complex joins or aggregations across multiple views.
        Authorized views: {authorized_views}
        """
        print(f"Executing SQL: {query}")
        if not query.strip().lower().startswith("select") and "set search_path" not in query.lower():
            raise ValueError("Only SELECT queries are allowed via this skill.")

        with engine.connect() as conn:
            conn.execute(text(f"SET search_path TO {', '.join(schemas)}, public"))
            return pd.read_sql(text(query), conn)

    if execute_sql_query.__doc__:
        execute_sql_query.__doc__ = execute_sql_query.__doc__.format(authorized_views=", ".join(view_names))

    # Common shared config to ensure hashability and consistent behavior
    shared_config = {
        "llm": llm,
        "verbose": True,
        "response_parser": SandboxResponseParser,
        "enforce_privacy": False,
        "enable_cache": False,
        "use_error_correction_framework": True,
        "custom_whitelisted_dependencies": ("sqlalchemy", "psycopg2", "plotly")
    }

    # 2. Load SmartDataframes (Working version baseline)
    smart_dfs = []
    for view in view_names:
        print(f"DEBUG: Starting load for {view}")
        try:
            with engine.connect() as conn:
                conn.execute(text(f"SET search_path TO {', '.join(schemas)}, public"))
                df = pd.read_sql(text(f"SELECT * FROM {view} LIMIT 5000"), conn)

            if df.empty:
                print(f"- Warning: {view} returned no rows.")

            metadata = fetch_table_metadata(engine, view)

            # Revert to SmartDataframe using the baseline approach
            # Pass shared_config to ensure all objects are configured identically
            sdf = SmartDataframe(
                df,
                name=view,
                description=f"View '{view}' with columns: {metadata}",
                config=shared_config
            )

            # Vital for internal schema consistency
            try:
                if hasattr(sdf, "schema"):
                    sdf.schema.name = view
            except Exception:
                pass

            smart_dfs.append(sdf)
            print(f"- Loaded {view} ({len(df)} rows)")
        except Exception as e:
            print(f"- Error loading {view}: {e}")

    if not smart_dfs:
        raise RuntimeError("No dataframes could be loaded. Check DB and connection.")

    # 3. Configure Agent
    agent = Agent(smart_dfs, config=shared_config)
    agent.add_skills(execute_sql_query)

    # Whitelist the table names in the Agent's state to prevent MaliciousQueryError
    try:
        if hasattr(agent, "_state") and hasattr(agent._state, "authorized_table_names"):
            for view in view_names:
                if view not in agent._state.authorized_table_names:
                    agent._state.authorized_table_names.append(view)
    except Exception:
        pass

    return agent
