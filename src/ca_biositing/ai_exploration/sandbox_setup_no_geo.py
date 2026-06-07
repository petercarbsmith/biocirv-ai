import os
import pandas as pd
import requests
import plotly.io as pio
import plotly.graph_objects as go
from dotenv import load_dotenv
from IPython.display import display
from typing import Optional, List, Any, Dict

# --- PandasAI Imports ---
from pandasai.llm.base import LLM
from pandasai import Agent, create as create_dataset

# Set Plotly for VS Code/Jupyter compatibility
pio.renderers.default = 'notebook'

# Initialize session-level log for generated code
SESSION_CODE_LOG = []

# Load environment variables
load_dotenv()

class CBORGLLM(LLM):
    """Custom LLM class for CBORG gateway."""
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
        if "SELECT" in prompt.upper() or "SQL" in prompt.upper():
            prompt += "\n\nCRITICAL: You are querying a PostgreSQL database. Always use PostgreSQL-compatible syntax."

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0
        }
        try:
            response = self._session.post(f"{self.api_base}/chat/completions", json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            if "result =" in content and "```" not in content:
                content = f"```python\n{content}\n```"
            return content
        except Exception as e:
            return f"Error connecting to CBORG API: {str(e)}"

    @property
    def type(self) -> str:
        return "cborg"

class TrinityResult:
    """Encapsulates Code, Data, and Plot."""
    def __init__(self, code: str, data: Optional[pd.DataFrame] = None, plot: Any = None, answer: Any = None):
        self.code = code
        self.data = data
        self.plot = plot
        self.answer = answer

    def _repr_html_(self):
        if isinstance(self.plot, (go.Figure, go.FigureWidget)):
            return self.plot._repr_html_()
        html = []
        if self.answer is not None:
            html.append(f"<div style='margin-bottom: 10px;'><strong>Answer:</strong> {self.answer}</div>")
        if self.data is not None:
            html.append(f"<div><strong>Data (Preview):</strong><br/>{self.data.head().to_html()}</div>")
        return "".join(html) if html else f"TrinityResult(code_len={len(self.code)})"

    def display(self):
        if self.answer is not None: print(f"Answer: {self.answer}")
        if self.plot is not None: display(self.plot)
        if self.data is not None: display(self.data)

class BioCirvAgent(Agent):
    """Subclassed Agent to ensure TrinityResult is returned."""
    def chat(self, prompt: str, output_type: Optional[str] = None) -> TrinityResult:
        result = super().chat(prompt, output_type)
        code = getattr(self, "last_code_executed", "")
        if code: SESSION_CODE_LOG.append(code)

        data, plot, answer = None, None, result
        if result is not None and hasattr(result, "value"):
            val = result.value
            if isinstance(val, pd.DataFrame): data = val
            elif "Chart" in result.__class__.__name__: plot = val
            else: answer = val
        elif isinstance(result, pd.DataFrame): data = result
        elif isinstance(result, (go.Figure, go.FigureWidget)): plot = result

        return TrinityResult(code=code, data=data, plot=plot, answer=answer)

def init_sandbox(model_name: Optional[str] = None, cloud_mode: bool = False):
    """Initializes the sandbox environment and returns the LLM and DB config."""
    api_key = os.getenv("CBORG_API_KEY")
    api_url = os.getenv("CBORG_API_URL", "https://api.cborg.lbl.gov/v1")
    selected_model = model_name or os.getenv("CBORG_MODEL") or "gemini-3-flash"

    if not api_key:
        raise ValueError("CBORG_API_KEY not found.")

    llm = CBORGLLM(api_token=api_key, api_base=api_url, model=selected_model)

    is_cloud = cloud_mode or os.getenv("CLOUD_MODE", "false").lower() == "true"
    config = {
        "db_user": os.getenv("DB_USER", "biocirv_readonly" if is_cloud else "biocirv_user"),
        "db_pass": os.getenv("DB_PASS", os.getenv("DB_PASSWORD", "biocirv_dev_password")),
        "db_host": os.getenv("DB_HOST", "127.0.0.1"),
        "db_port": os.getenv("DB_PORT", "5434"),
        "db_name": os.getenv("DB_NAME", "biocirv-staging" if is_cloud else "biocirv_db"),
        "cloud_mode": is_cloud,
    }
    print(f"Initialized BioCirv AI (Simple) | Model: {selected_model} | {'☁️ Cloud' if is_cloud else '💻 Local'}")
    return llm, config

def get_agent_no_geo(llm: CBORGLLM, db_config: Dict[str, Any], views: Optional[List[str]] = None):
    """Factory for a simple AI agent using the recommended create() pattern with metadata."""

    search_path = "ca_biositing,data_portal,public"
    connection_params = {
        "host": db_config.get('db_host', '127.0.0.1'),
        "port": int(db_config.get('db_port', 5434)),
        "database": db_config['db_name'],
        "user": db_config['db_user'],
        "password": db_config['db_pass'],
        "options": f"-c search_path={search_path}"
    }

    # Use explicit metadata to avoid initialization crashes
    view_metadata = {
        "ca_biositing.analysis_data_view": [
            {"name": "id", "type": "integer"},
            {"name": "county", "type": "string"},
            {"name": "resource", "type": "string"},
            {"name": "value", "type": "number"}
        ],
        "ca_biositing.analysis_average_view": [
            {"name": "id", "type": "integer"},
            {"name": "county", "type": "string"},
            {"name": "resource", "type": "string"},
            {"name": "avg_value", "type": "number"}
        ]
    }

    views = views or list(view_metadata.keys())
    datasets = []
    print(f"📦 Registering {len(views)} datasets via create() factory...")

    import time
    session_ts = int(time.time())

    for view in views:
        try:
            schema_part, table_part = view.split(".") if "." in view else ("public", view)
            safe_name = view.replace(".", "-").replace("_", "-").lower()
            dataset_path = f"biocirv/{safe_name}-{session_ts}"
            cols = view_metadata.get(view, [{"name": "id", "type": "integer"}])

            vdf = create_dataset(
                path=dataset_path,
                description=f"BioCirv view: {view}",
                source={
                    "type": "postgres",
                    "connection": connection_params,
                    "table": table_part,
                    "schema": schema_part,
                    "columns": cols
                }
            )

            # GHOST SHADOWING: Block early DB hits
            try:
                vdf.head = lambda n=5: pd.DataFrame(columns=[c['name'] for c in cols])
                vdf.__dict__['rows_count'] = 0

                loader = getattr(vdf, "_loader", None)
                if loader:
                    import types
                    loader.get_row_count = types.MethodType(lambda self: 0, loader)
                    loader.execute_query = types.MethodType(lambda self, q, p=None: pd.DataFrame(), loader)
            except Exception:
                pass

            datasets.append(vdf)
            print(f"  ✅ {view}: Ready")
        except Exception as e:
            print(f"  ❌ Error registering {view}: {e}")

    if not datasets:
        raise RuntimeError("Failed to register any datasets. Check database and view settings.")

    return BioCirvAgent(
        datasets,
        config={
            "llm": llm,
            "verbose": True,
            "enable_cache": False,
            "use_error_correction_framework": True,
            "custom_whitelisted_dependencies": ["sqlalchemy", "psycopg2", "plotly", "matplotlib"],
        }
    )
