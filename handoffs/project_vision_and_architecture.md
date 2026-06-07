# 🌟 BioCirv AI Agent: Strategic Vision & Architecture

## 🎯 Big Vision

The **BioCirv AI Agent** is designed to democratize California's bioeconomy
data. Our goal is to provide researchers and policy-makers with a "Natural
Language Interface to Geospatial Analytics." Instead of writing complex SQL or
using rigid GIS tools, users should be able to ask questions like: _"Show me a
bar chart of the top 10 counties by biomass potential"_ or _"Which counties have
high biomass and are within 50 miles of a major highway?"_

## 🏗️ Technical Architecture

### 1. The Intelligence Layer (**PandasAI 3.0+**)

We use PandasAI's **Semantic Layer API** to manage the relationship between
natural language and data.

- **`VirtualDataFrames`**: We do not load data into memory. We create virtual
  pointers to database views. This keeps the environment lightweight and allows
  the LLM to leverage the power of the database engine.
- **CBORG LLM Gateway**: A specialized scientific LLM gateway (LBL) used to
  translate queries into PostgreSQL/PostGIS syntax.

### 2. The Data Layer (**PostgreSQL + PostGIS**)

All analysis happens server-side in Google Cloud SQL.

- **View Discovery**: The agent automatically scans the `ca_biositing` and
  `data_portal` schemas to discover available analytical views.
- **Geospatial Power**: The agent is prompted to prefer optimized geospatial
  queries (PostGIS) for distance and location-based analysis.

### 3. The Connectivity Layer (**Hybrid Auth**)

To bridge the gap between a local environment (or Colab) and secure GCP
resources:

- **Cloud SQL Auth Proxy v2**: Handles the secure IAM tunnel using the user's
  Google Identity.
- **Static Login**: Uses a read-only database user (`biocirv_readonly`) for
  consistent driver compatibility.

## 🔄 Development Workflow

### Observation through Persistence

Because this agent operates in a **Google Colab** environment while the code
lives in a **GitHub Submodule**, changes are only observable by the runtime when
they are pushed to the repository.

**CRITICAL RULE**: After making changes to `sandbox_setup.py` or the notebook,
you **MUST** commit and push your changes to the `dev` branch of the
`biocirv-ai` submodule for the "Nuclear Setup" in Colab to pick them up.

### Verification Cycle

1. Edit code in `src/ca_biositing/ai_exploration/`.
2. Commit and Push to `origin dev`.
3. Restart the Colab Runtime and re-run the setup cell.
4. Verify the fix using the **Connectivity Smoke Test** or starter queries.

## 🚧 Current Frontier

We have stabilized the connection. We are now working on **PandasAI Source
Compatibility**—ensuring the virtual datasets are correctly registered so the
Agent can begin executing queries.
