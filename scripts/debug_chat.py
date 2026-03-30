import sys
import os

# Add src to path relative to this script
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

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

        # Accessing the parser instance from the agent via its config
        parser_cls = agent.config.response_parser
        # PandasAI instantiates the parser during chat. We can instantiate one for retrieval.
        parser = parser_cls(agent.context)
        if hasattr(parser, "get_trinity"):
            # We need the parser that was actually used to have the _last_result.
            # In PandasAI 2.3.x, the agent doesn't store the parser instance easily.
            # However, our SandboxResponseParser could be improved to store results in a class-level or session-level cache if needed.
            # For now, let's try to see if we can get it from the agent.
            trinity = parser.get_trinity(agent)
            print(f"Trinity: {trinity}")
            print("Code found:", bool(trinity.code))
            print("Data found:", bool(trinity.data))
            print("Plot found:", bool(trinity.plot))

            # Verify session log
            from ca_biositing.ai_exploration.sandbox_setup import SESSION_CODE_LOG
            print(f"Session Code Log Size: {len(SESSION_CODE_LOG)}")

        # Complex Join test (100k+ row verify)
        print("\n5. Large Data Join Performance (100k+ rows):")
        # Assuming analysis_data_view is large
        query = "Join analysis_data_view and usda_census_view and summarize the total value by commodity."
        print(agent.chat(query))

    except Exception as e:
        print(f"Caught exception: {type(e).__name__}: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    debug_chat()
