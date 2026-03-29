import sys
import os
sys.path.append('src')

from ca_biositing.ai_exploration.sandbox_setup import init_sandbox, get_agent
import traceback

def debug_chat():
    try:
        llm, engine = init_sandbox()
        # Use multiple views to verify multi-source logic
        views = ["analysis_data_view", "usda_census_view"]
        print(f"Initializing agent with views: {views}")
        agent = get_agent(llm, engine, view_names=views)

        print("\n--- Running Diagnostic Queries ---")

        # Simple query
        print("\n1. Row Count Query:")
        print(agent.chat("How many rows are there?"))

        # Complex JOIN query (triggers SQL skill)
        print("\n2. JOIN Query:")
        query = "Join analysis_data_view and usda_census_view on geoid and find the top 5 records with highest value in analysis_data_view."
        print(agent.chat(query))

        # Schema discovery query
        print("\n3. Column Discovery Query:")
        print(agent.chat("List the columns in the analysis_data_view"))
    except Exception as e:
        print(f"Caught exception: {type(e).__name__}: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    debug_chat()
