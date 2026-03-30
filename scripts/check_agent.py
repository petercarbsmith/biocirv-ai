import sys
import os

# Add src to path relative to this script
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ca_biositing.ai_exploration.sandbox_setup import init_sandbox, get_agent
llm, db_config = init_sandbox()
agent = get_agent(llm, db_config, view_names=["analysis_data_view"])
print("Agent attributes:", [a for a in dir(agent) if "parser" in a.lower()])
