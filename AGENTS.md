# 🤖 AI Agent Orientation: BioCirv AI Submodule

Welcome, Agent. This submodule (`analysis/biocirv-ai`) is the "Natural Language to Geospatial Analytics" engine for the BioCirv project. Your goal is to maintain and enhance an AI agent that allows stakeholders to query California's bioeconomy data using natural language.

## 🎯 Overall Goal
Provide a seamless, SQL-first interface to PostGIS views hosted in Google Cloud SQL. The agent should return a "Trinity" of results: **Generated Code**, **Raw Data (DataFrame)**, and **Interactive Plots**.

## 🏗️ Key Architecture & Strategies

Before making changes, you **MUST** understand these core strategies:

- **Ghost Frame Strategy**: We bypass PandasAI's failing SQLAlchemy introspection (often caused by PostGIS types) by manually discovering columns and injecting them via empty "Ghost" DataFrames during initialization.
  - See: [`handoffs/metadata_discovery_summary.md`](handoffs/metadata_discovery_summary.md)
- **PandasAI 3.0+ Migration**: We use the Semantic Layer API with `VirtualDataFrames`. Do not load data into memory.
  - See: [`handoffs/pandasai_3_migration_summary.md`](handoffs/pandasai_3_migration_summary.md)
- **Trinity Result Format**: Our custom `BioCirvAgent` and `SandboxResponseParser` ensure that code, data, and plots are captured together.
  - See: [`handoffs/fix_response_parser_log.md`](handoffs/fix_response_parser_log.md)
- **Vision & Roadmap**:
  - See: [`handoffs/project_vision_and_architecture.md`](handoffs/project_vision_and_architecture.md)
  - See: [`plans/modernization_roadmap.md`](plans/modernization_roadmap.md)

## 📂 Relevant Files

### Core Logic
- [`src/ca_biositing/ai_exploration/sandbox_setup.py`](src/ca_biositing/ai_exploration/sandbox_setup.py): The main factory (`get_agent`) and agent class definitions. **Primary area for logic fixes.**
- [`src/ca_biositing/ai_exploration/sandbox_setup_no_geo.py`](src/ca_biositing/ai_exploration/sandbox_setup_no_geo.py): Simplified factory for the **Stable Prototype**. Focuses on non-geospatial views.
- [`src/ca_biositing/ai_exploration/schema.py`](src/ca_biositing/ai_exploration/schema.py): Metadata discovery and view inspection logic.
- [`src/ca_biositing/ai_exploration/colab_setup.py`](src/ca_biositing/ai_exploration/colab_setup.py): Environment initialization for Google Colab.

### Interfaces & Testing Grounds
- [`notebooks/biocirv_ai_stable_prototype.ipynb`](notebooks/biocirv_ai_stable_prototype.ipynb): **The primary stable prototype.** Use this for stakeholders who need reliable, non-geospatial analysis.
- [`notebooks/biocirv_ai_analysis_playground.ipynb`](notebooks/biocirv_ai_analysis_playground.ipynb): The experimental testing ground and original stakeholder interface.
- [`notebooks/sandbox_exploration.ipynb`](notebooks/sandbox_exploration.ipynb): Developer sandbox for testing new features.

### Diagnostics & Testing
- [`scripts/`](scripts/): **Always create diagnostic or reproduction scripts here.**
  - `debug_db.py`: Check raw database connectivity and data presence.
  - `debug_chat.py`: CLI interface for testing agent responses.
  - `inspect_vdf.py`: Inspect the internal state of VirtualDataFrames.

## 🚀 Execution Environment
This project is designed to run in **Google Colab**. 
- **Current Setup**: We use the **Colab VS Code Extension** to run a **Python 3.11 kernel** on a remote Colab instance. This provides a Linux environment compatible with our dependencies.
- **Future State**: The code will eventually transition to being run directly on the Google Colab web interface for stakeholders.

## 🚧 Current Troubleshooting
We are currently investigating why queries return empty results despite correct metadata discovery.
- See: [`handoffs/data_validation_troubleshooting.md`](handoffs/data_validation_troubleshooting.md)

## 🔄 Workflow Rules
1. **Persistence**: Because we use Colab kernels, changes are only observable by the runtime when they are pushed. You **MUST** commit and push your changes to the `dev` branch for the Colab environment to see them.
2. **Logging**: Prior to every commit, update [`handoffs/fix_response_parser_log.md`](handoffs/fix_response_parser_log.md) (or create a new relevant log) to track changes and resulting errors.
3. **Environment**: This submodule is managed by Pixi. Always run `pixi run ...` or ensure you are in the pixi environment.
