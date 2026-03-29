import sys
import os

# --- 1. IMMEDIATE JUPYTER RECOVERY (Experimental) ---
# This MUST happen before any pandasai imports to avoid class identity mismatches
def is_notebook():
    try:
        from IPython import get_ipython
        if get_ipython() is None:
            return False
        shell = get_ipython().__class__.__name__
        return shell == 'ZMQInteractiveShell'
    except (NameError, ImportError):
        return False

if is_notebook() and not hasattr(sys, "_PANDASAI_PURGED"):
    # Clear already loaded pandasai modules to force a clean state for our patches
    # We only do this once to avoid destroying instances already in memory
    for mod in list(sys.modules.keys()):
        if mod.startswith("pandasai") and mod != "pandasai.pandas":
            del sys.modules[mod]
    sys._PANDASAI_PURGED = True
    print("DEBUG: Notebook environment detected. Purged pandasai modules for clean patching.")

import functools
import pandas as pd
import requests
import json
import plotly.io as pio
import plotly.graph_objects as go
from dotenv import load_dotenv

# Now import LLM after the potential purge
try:
    from pandasai.llm.base import LLM
except ImportError:
    # Fallback for different versions
    try:
        from pandasai.llm import LLM
    except ImportError:
        LLM = object

try:
    # PandasAI 2.0 location
    from pandasai.responses.response_parser import ResponseParser
except ImportError:
    # PandasAI 3.0 or alternative core location
    try:
        from pandasai.core.response.parser import ResponseParser
    except ImportError:
        # Fallback for older versions or other layouts
        from pandasai.responses import ResponseParser
from sqlalchemy import create_engine, text
from IPython.display import display, Image, HTML
from typing import Optional, List, Any

# Internal imports
from ca_biositing.ai_exploration.schema import discover_views, fetch_table_metadata

# --- MONKEYPATCH FOR UNHASHABLE LIST ERROR ---
import traceback
import functools
import sys
import logging
from typing import Any

# Replace functools.cache and lru_cache globally to catch new definitions EARLY
def debug_cache_wrapper(func):
    if hasattr(func, "_is_debug_wrapper"):
        return func

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            hash(args)
            try:
                hash(frozenset(kwargs.items()))
            except TypeError:
                pass
        except TypeError as e:
            if "unhashable" in str(e).lower():
                print(f"\n!!! CACHE HASHING ERROR DETECTED !!!")
                print(f"Function: {func.__module__}.{func.__name__}")
                print(f"Error: {e}")
                for i, arg in enumerate(args):
                    try: hash(arg)
                    except TypeError: print(f"  - Unhashable Arg[{i}] (type {type(arg).__name__})")
                for k, v in kwargs.items():
                    try: hash(v)
                    except TypeError: print(f"  - Unhashable Kwarg['{k}'] (type {type(v).__name__})")
            raise
        return func(*args, **kwargs)
    wrapper._is_debug_wrapper = True
    return wrapper

original_cache = functools.cache
original_lru_cache = functools.lru_cache
functools.cache = debug_cache_wrapper
def debug_lru_cache(*args, **kwargs):
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return debug_cache_wrapper(args[0])
    return debug_cache_wrapper
functools.lru_cache = debug_lru_cache

# Pre-import problematic modules
try:
    import pandasai
    import pandasai.schemas.df_config
    import pandasai.connectors.base
    import pandasai.connectors.pandas
    import pandasai.connectors.sql
    import pandasai.agent
    import pandasai.helpers.cache
except ImportError:
    pass

# Force immediate execution of the cache killer
def strip_all_pandasai_caches(verbose=True):
    count = 0
    try:
        from functools import cached_property
    except ImportError:
        cached_property = None

    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("pandasai") and mod_name != "pandasai.pandas":
            mod = sys.modules[mod_name]
            for attr_name in list(mod.__dict__.keys()):
                try:
                    attr = mod.__dict__[attr_name]
                    # A. Handle classes
                    if isinstance(attr, type) and getattr(attr, "__module__", "").startswith("pandasai"):
                        for m_name in list(attr.__dict__.keys()):
                            obj = attr.__dict__[m_name]
                            # 1. Strip functools.cache / lru_cache
                            if hasattr(obj, "cache_info") or hasattr(obj, "__wrapped__"):
                                if hasattr(obj, "__wrapped__"):
                                    original = obj.__wrapped__
                                    while hasattr(original, "__wrapped__"):
                                        original = original.__wrapped__
                                    setattr(attr, m_name, original)
                                    count += 1
                            # 2. Strip cached_property
                            elif cached_property and isinstance(obj, cached_property):
                                setattr(attr, m_name, property(obj.func))
                                count += 1

                    # B. Handle standalone functions
                    elif callable(attr) and getattr(attr, "__module__", "").startswith("pandasai"):
                        if hasattr(attr, "cache_info") or hasattr(attr, "__wrapped__"):
                            if hasattr(attr, "__wrapped__"):
                                original = attr.__wrapped__
                                while hasattr(original, "__wrapped__"):
                                    original = original.__wrapped__
                                setattr(mod, attr_name, original)
                                count += 1
                except Exception: continue
    if count > 0 and verbose:
        print(f"DEBUG: Nuclear Cache Killer stripped {count} caches from pandasai.")
    return count

strip_all_pandasai_caches()

# Patch Agent.chat to show us WHERE it's failing
try:
    from pandasai.agent import Agent as PAIAgent
    original_agent_chat = PAIAgent.chat
    def patched_agent_chat(self, *args, **kwargs):
        try:
            return original_agent_chat(self, *args, **kwargs)
        except Exception:
            print("\n!!! AGENT CHAT CRITICAL FAILURE !!!")
            traceback.print_exc()
            raise
    PAIAgent.chat = patched_agent_chat
except Exception: pass

# 2. Force Hashability by ID for problematic classes
try:
    from pandasai.connectors.base import BaseConnector
    from pandasai.connectors.pandas import PandasConnector
    from pandasai.schemas.df_config import Config as PAIConfig
    from pandasai.connectors.base import BaseConnectorConfig
    from pandasai.agent import Agent
    from pandasai.smart_dataframe import SmartDataframe
    from pandasai.smart_datalake import SmartDatalake

    # Target all config, connector, and core classes
    classes_to_patch = [
        BaseConnector, PandasConnector, PAIConfig, BaseConnectorConfig,
        Agent, SmartDataframe, SmartDatalake
    ]

    # Also try to get PandasConnectorConfig if it exists
    try:
        from pandasai.connectors.pandas import PandasConnectorConfig
        classes_to_patch.append(PandasConnectorConfig)
    except ImportError:
        pass

    for cls in classes_to_patch:
        cls.__hash__ = lambda self: id(self)

    print(f"DEBUG: Forced ID-based hashability on {len(classes_to_patch)} classes.")

    # 3. Patch Pydantic Config for all identified classes to be extremely permissive
    try:
        from pydantic import BaseModel
        for cls in classes_to_patch:
            if issubclass(cls, BaseModel):
                # Pydantic V2
                if hasattr(cls, "model_config"):
                    cls.model_config["arbitrary_types_allowed"] = True
                    cls.model_config["validate_assignment"] = False
                # Pydantic V1
                elif hasattr(cls, "Config"):
                    # Use setattr to be safe with descriptors
                    setattr(cls.Config, "arbitrary_types_allowed", True)
                    setattr(cls.Config, "validate_assignment", False)
        print("DEBUG: Hardened Pydantic models for arbitrary types.")
    except Exception as e:
        print(f"DEBUG: Pydantic hardening failed: {e}")

    # 4. Patch __init__ to force tuples and handle LLM identity crisis
    original_config_init = PAIConfig.__init__
    def patched_config_init(self, **data):
        # A. Fix unhashable lists
        if "custom_whitelisted_dependencies" in data and isinstance(data["custom_whitelisted_dependencies"], list):
            data["custom_whitelisted_dependencies"] = tuple(data["custom_whitelisted_dependencies"])

        # B. Handle LLM class identity mismatch in Jupyter
        # If the LLM object comes from a previous execution of this module,
        # it won't pass Pydantic's 'instance of LLM' check.
        llm_val = data.get("llm")
        if llm_val and not isinstance(llm_val, LLM):
            # If it looks like an LLM, bypass validation for this field
            if hasattr(llm_val, "call") and (hasattr(llm_val, "type") or hasattr(llm_val, "_type")):
                data_copy = data.copy()
                data_copy.pop("llm")
                original_config_init(self, **data_copy)
                object.__setattr__(self, "llm", llm_val)
                return

        original_config_init(self, **data)
    PAIConfig.__init__ = patched_config_init

    original_bcc_init = BaseConnectorConfig.__init__
    def patched_bcc_init(self, **data):
        if "where" in data and isinstance(data["where"], list):
            data["where"] = tuple(tuple(x) if isinstance(x, list) else x for x in data["where"])
        original_bcc_init(self, **data)
    BaseConnectorConfig.__init__ = patched_bcc_init

except Exception as e:
    print(f"DEBUG: Failed to force hashability or apply model patches: {e}")
# --------------------------------------------

# Set Plotly for VS Code/Jupyter compatibility
pio.renderers.default = 'notebook'

# Load environment variables
load_dotenv()

AVAILABLE_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-pro",
    "gpt-4o",
    "gpt-4o-mini",
    "claude-3-5-sonnet",
]

class CBORGLLM(LLM):
    """Hardened Custom LLM class for CBORG gateway in PandasAI 3.0"""
    def __init__(self, api_token: str, api_base: str = "https://api.cborg.lbl.gov/v1", model: str = "gemini-2.0-flash"):
        super().__init__()
        self.api_token = api_token
        self.api_base = api_base
        self.model = model
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        })

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

            # HARDENING: Ensure we return something PandasAI can parse.
            # If the model didn't use code blocks but wrote code, wrap it.
            if "result =" in content and "```" not in content:
                # Basic heuristic: if it looks like python but no backticks
                content = f"```python\n{content}\n```"

            # If the model used code blocks but added text after, PandasAI might struggle
            # if there are multiple blocks. We favor the first block containing 'result ='.
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
            # Remove template noise that LLMs sometimes repeat
            lines = code_str.splitlines()
            cleaned = []
            for line in lines:
                # Skip lines that are clearly instructions from the prompt
                if line.strip().startswith('type (possible values "string"'):
                    continue
                if "# TODO: import" in line:
                    continue
                cleaned.append(line)
            return "\n".join(cleaned).strip()

        try:
            # Try standard extraction first
            extracted = self._extract_code(response)
            return clean_potential_code(extracted)
        except Exception:
            import re
            # Aggressive regex for code blocks
            code_blocks = re.findall(r"```(?:python|py)?\n(.*?)```", response, re.DOTALL)
            if code_blocks:
                for block in code_blocks:
                    if "result =" in block:
                        cleaned = clean_potential_code(block)
                        if self._is_python_code(cleaned):
                            return cleaned

                # Fallback to first block
                cleaned = clean_potential_code(code_blocks[0])
                return cleaned

            # Last resort: find code patterns
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
        """
        Extremely permissive validator to allow raw objects and unconventional formats.
        """
        return # Bypassing all base validation to ensure no InvalidOutputValueMismatch

    def parse(self, result: Any, last_code_executed: str = None) -> Any:
        """
        Override parse to return raw values instead of wrapped Response objects.
        This enables VS Code's Data Viewer and Plotly interactive features.
        """
        # 1. Handle raw DataFrames
        if isinstance(result, pd.DataFrame):
            return result

        # 2. Handle raw Plotly Figures or similar interactive objects
        if isinstance(result, go.Figure) or hasattr(result, 'to_html'):
            return result

        # 3. Handle dictionaries (the standard PandasAI format or raw data)
        parsed_result = None
        if isinstance(result, dict):
            # Check if it's a Plotly figure dict
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

            # If it's a generic dict that looks like data (list of records), convert to DF
            if parsed_result is None:
                for key, val in result.items():
                    if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                        try:
                            parsed_result = pd.DataFrame(val)
                            break
                        except Exception:
                            pass

        # 4. Fallback to base parser but unwrap the value
        if parsed_result is None:
            try:
                base_response = super().parse(result, last_code_executed)
                parsed_result = getattr(base_response, 'value', base_response)
            except Exception:
                parsed_result = result

        # 5. Final Formatting for Notebook Display
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
    selected_model = model_name or os.getenv("CBORG_MODEL") or "gemini-2.0-flash"

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
    from pandasai import Agent, SmartDataframe, skill, skills

    # If no views provided, auto-discover them
    if view_names is None:
        view_names = discover_views(engine, schemas)

    primary_schema = os.getenv("DB_SCHEMA", schemas[0])

    # 1. Define SQL Skill
    @skill
    def execute_sql_query(query: str):
        """
        Executes a read-only SQL SELECT query against the PostgreSQL database.
        Use this for complex joins or aggregations across multiple views.
        Authorized views: {authorized_views}
        """
        import pandas as pd # Import inside to avoid module-level issues
        print(f"Executing SQL: {query}")
        if not query.strip().lower().startswith("select") and "set search_path" not in query.lower():
            raise ValueError("Only SELECT queries are allowed via this skill.")

        with engine.connect() as conn:
            conn.execute(text(f"SET search_path TO {', '.join(schemas)}, public"))
            return pd.read_sql(text(query), conn)

    execute_sql_query.__doc__ = execute_sql_query.__doc__.format(authorized_views=", ".join(view_names))

    # 2. Load DataFrames (Connectors)
    # Using raw DataFrames and PandasConnector to avoid recursion in SmartDataframe
    from pandasai.connectors.pandas import PandasConnector

    connectors = []
    from pandasai.connectors.pandas import PandasConnector

    for view in view_names:
        print(f"DEBUG: Starting load for {view}")
        try:
            with engine.connect() as conn:
                # Apply search path to this connection
                conn.execute(text(f"SET search_path TO {', '.join(schemas)}, public"))
                # Use simple name, relying on search_path
                df = pd.read_sql(text(f"SELECT * FROM {view} LIMIT 5000"), conn)

            if df.empty:
                print(f"- Warning: {view} returned no rows.")

            metadata = fetch_table_metadata(engine, view)

            # Initialize Connector
            connector = PandasConnector(
                {"original_df": df},
                name=view,
                description=f"View '{view}' with columns: {metadata}"
            )
            connectors.append(connector)
            print(f"- Loaded {view} ({len(df)} rows)")
        except Exception as e:
            print(f"- Error loading {view}: {e}")

    if not connectors:
        raise RuntimeError("No dataframes could be loaded. Check DB and connection.")

    # 3. Configure Agent
    agent_config = {
        "llm": llm,
        "verbose": True,
        "response_parser": SandboxResponseParser,
        "enforce_privacy": False,
        "enable_cache": False,
        "use_error_correction_framework": True,
        "custom_whitelisted_dependencies": ("sqlalchemy", "psycopg2", "plotly")
    }

    # Initialize Agent directly (avoids SmartDatalake/SmartDataframe overhead)
    agent = Agent(connectors, config=agent_config)
    agent.add_skills(execute_sql_query)

    # WHAPPING: Whitelist the table names in the Agent's state to prevent MaliciousQueryError
    # This was a key part of the working commit b2bb674
    try:
        if hasattr(agent, "_state") and hasattr(agent._state, "authorized_table_names"):
            for view in view_names:
                if view not in agent._state.authorized_table_names:
                    agent._state.authorized_table_names.append(view)
    except Exception:
        pass

    return agent
