import sys
import os
sys.path.append('src')

from ca_biositing.ai_exploration.sandbox_setup import init_sandbox, get_agent
import traceback

def debug_chat():
    try:
        llm, db_config = init_sandbox()
        # Use multiple views to verify multi-source logic
        schemas = ["ca_biositing", "analytics", "data_portal"]
        views = ["analysis_data_view", "usda_census_view"]
        print(f"Initializing agent with schemas: {schemas} and views: {views}")
        agent = get_agent(llm, db_config, schemas=schemas, view_names=views)

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

        # Verify Trinity Output
        print("\n4. Trinity Output Check:")
        response = agent.chat("Plot the top 5 records from analysis_data_view by value.")
        print(f"Response Type: {type(response)}")

        parser = agent.config.response_parser(agent.context)
        # Note: In actual usage, the parser instance used by agent is needed to get the last result
        # but here we just show how it would be accessed if the parser stored it.
        # Since we just updated the code, let's see if we can get it from the agent's parser instance.
        if hasattr(agent, "response_parser") and hasattr(agent.response_parser, "get_trinity"):
            trinity = agent.response_parser.get_trinity(agent)
            print("Trinity Keys:", trinity.keys())
            print("Code found:", bool(trinity["code"]))
            print("Data found:", bool(trinity["data"]))
            print("Plot found:", bool(trinity["plot"]))

    except Exception as e:
        print(f"Caught exception: {type(e).__name__}: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    debug_chat()
