# BioCirv AI Exploration Sandbox

Natural language data exploration for the CA Biositing project using **PandasAI
3.0+** and the **CBORG LLM gateway**.

## 🏗️ Architecture

- **Namespace Package**: `ca_biositing.ai_exploration`
- **LLM**: Hardened `CBORGLLM` wrapper with session pooling and timeouts.
- **Parser**: `SandboxResponseParser` for interactive Plotly figures and VS Code
  Data Viewer support.
- **Dynamic Discovery**: Automatically discovers PostgreSQL views for analysis.

## 🚀 Quick Start (Local)

1. **Install Pixi**: If you don't have it, install from
   [pixi.sh](https://pixi.sh).
2. **Setup Environment**:
   ```bash
   pixi install
   ```
3. **Configure Credentials**: Copy `.env.example` to `.env` and fill in your
   `CBORG_API_KEY` and database details.
4. **Install Kernel**:
   ```bash
   pixi run kernel-install
   ```
5. **Start Analysis**: Open `notebooks/ai_analysis.ipynb` and select the
   **Python (BioCirv AI)** kernel.

## ☁️ Google Colab Integration

You can install this package directly in Google Colab:

```python
!pip install git+https://github.com/sustainability-software-lab/biocirv-ai.git
```

## 🛠️ Development

- **Run Tests**: `pixi run test`
- **Check Environment**: `pixi run check-env`
