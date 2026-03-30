# Handoff: BioCirv AI Modernization (Phase 3)

## 🎯 Task Overview

Proceed to **Phase 3: Google Colab & GCP Migration** of the BioCirv AI
Modernization Roadmap.

The goal is to provide a stakeholder-accessible prototype that connects directly
to GCP Cloud SQL and runs in a managed environment (Google Colab).

## 📂 Current State (Post-Phase 2)

- **Architecture:** SQL-First architecture with rich "Trinity" results (Code,
  Data, Plot).
- **Environment:** Stabilized on `pandas 1.5.3`.
- **Features:** Automatic metadata discovery, session code logging, and
  multi-backend visualization unwrapping.
- **Repository Structure:** Consolidated scripts in
  `analysis/biocirv-ai/scripts/`.

## 🛠️ Implementation Requirements (Phase 3)

### 1. Colab Compatibility Scripting

- Create a standalone initialization script (`colab_setup.py`) that handles
  `google.colab.auth`.
- **Secret Management:** Use `google.colab.userdata.get('CBORG_API_KEY')` to
  safely retrieve the API key from Colab's built-in secrets manager.
- Ensure `pip install` commands for dependencies are handled gracefully within
  the Colab environment.
- Optimize the `TrinityResult` rendering for Colab's HTML outputs (e.g.,
  ensuring Plotly's `notebook_connected` renderer is used if needed).

### 2. GCP Cloud SQL Integration (IAM Auth)

- Implement `sqlalchemy` connection logic using the **GCP Python Connector for
  Cloud SQL**.
- **IAM Auth:** Replace hardcoded `.env` database passwords with IAM-based
  authentication (identity-based access) for more secure stakeholder usage.
- Update `sandbox_setup.py` to support a "Cloud Mode" switch.

### 3. Stakeholder Notebook (The "Playground")

- Create a well-documented Jupyter notebook template for stakeholders.
- Include "Starter Queries" for common bioeconomy site selection questions.
- Demonstrate the power of the "Trinity" output (showing the underlying SQL and
  data).

### 4. Security & Access Control

- Ensure the `SQLConnector` uses a restricted, read-only service account.
- Verify that the `search_path` is strictly limited to the necessary analytics
  views.

---

## ✅ Phase 2 Completion Checklist (For Reference)

- [x] Trinity Result Object implemented.
- [x] Robust Visualization Unwrapping (Plotly/Matplotlib).
- [x] Session-Level Code Logging.
- [x] Schema Metadata Enrichment.
- [x] 100k+ row join performance verified.
