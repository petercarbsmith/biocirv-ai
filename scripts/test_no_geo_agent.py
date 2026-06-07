import os
from ca_biositing.ai_exploration.sandbox_setup_no_geo import init_sandbox, get_agent_no_geo

def main():
    print("🚀 Starting No-Geo Sandbox Diagnostic...")

    try:
        # 1. Initialize Sandbox
        llm, db_config = init_sandbox()
        print("✅ Sandbox initialized.")

        # 2. Get Agent
        # We test with non-geospatial views as requested
        views = ["ca_biositing.analysis_data_view", "ca_biositing.analysis_average_view"]
        agent = get_agent_no_geo(llm, db_config, views=views)
        print("✅ Agent created.")

        # 3. Test Query
        query = "What are the first 3 records of analysis_data_view? Return them as a dataframe."
        print(f"🤔 Sending query: '{query}'")

        result = agent.chat(query)

        # 4. Inspect Result
        print("\n--- Result Summary ---")
        print(f"Code Executed:\n{result.code}")
        if result.data is not None:
            print(f"\nData Received (Shape: {result.data.shape}):")
            print(result.data.head())
        else:
            print("\n❌ No data returned.")

        if result.answer:
            print(f"\nAnswer: {result.answer}")

    except Exception as e:
        print(f"\n❌ Diagnostic failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
