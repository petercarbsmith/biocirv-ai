import sys
import os
from unittest.mock import MagicMock

# 1. Mock missing dependencies
mock_modules = [
    "plotly", "plotly.io", "plotly.graph_objects",
    "google", "google.cloud", "google.cloud.sql", "google.cloud.sql.connector",
    "pg8000", "IPython", "IPython.display", "pandasai", "pandasai.llm",
    "pandasai.llm.base", "pandasai.responses", "pandasai.responses.response_parser",
    "pandasai.core", "pandasai.core.response", "pandasai.core.response.parser"
]
for mod in mock_modules:
    sys.modules[mod] = MagicMock()

import pandasai
pandasai.Agent = MagicMock
pandasai.create = MagicMock(side_effect=lambda **kwargs: MagicMock(path=kwargs.get('path'), _source=kwargs.get('source'), columns=["col1"]))

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

try:
    from ca_biositing.ai_exploration.sandbox_setup import init_sandbox, get_agent
    print("✅ Imports successful")

    db_config = {
        "db_user": "test_user", "db_pass": "test_pass", "db_host": "127.0.0.1",
        "db_port": "5434", "db_name": "test_db", "cloud_mode": False
    }

    class MockLLM:
        def __init__(self): self.type = "mock"
        def call(self, instruction, context=None): return "mock"
    llm = MockLLM()

    print("Testing get_agent with explicit list...")
    views = ["ca_biositing.test_view", "data_portal.another_view"]
    agent = get_agent(llm, db_config, qualified_views=views)

    print("✅ Agent logic validated")

except Exception as e:
    print(f"❌ Validation failed: {e}")
    import traceback
    traceback.print_exc()
