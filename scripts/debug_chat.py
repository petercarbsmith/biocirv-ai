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
        # Adjusting schemas to match get_agent's expected qualified_views
        qualified_views = ["ca_biositing.analysis_data_view", "ca_biositing.usda_census_view"]
        print(f"Initializing agent with qualified views: {qualified_views}")
        agent = get_agent(llm, db_config, qualified_views=qualified_views)

        print("\n--- Running Diagnostic Queries ---")

        # Simple query
        print("\n1. Simple Data Query:")
        print(agent.chat("Show me 3 records from the analysis_data_view"))

        # Schema discovery query
        print("\n2. Column Discovery Query:")
        print(agent.chat("What are the columns in analysis_data_view?"))

        # Verify Trinity Output
        print("\n3. Trinity Output Check:")
        response = agent.chat("Plot 5 records from analysis_data_view.")
        print(f"Response Type: {type(response)}")

        # Accessing the parser instance from the agent via its context
        parser = None
        if hasattr(agent, "context") and hasattr(agent.context, "response_parser"):
            parser = agent.context.response_parser
        elif hasattr(agent, "response_parser"):
            parser = agent.response_parser
        
        if parser and hasattr(parser, "get_trinity"):
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
