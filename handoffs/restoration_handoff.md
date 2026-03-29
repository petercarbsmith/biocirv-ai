# Handoff: Restoring AI Agent Logic to Working Baseline

## 🎯 Goal

Restore the `PandasAI Agent` initialization logic to the stable baseline found
in commit
[`b2bb674`](https://github.com/sustainability-software-lab/biocirv-ai/commit/b2bb674e7c599417caefba7dad6203b1479e2305),
while preserving the current **automatic view discovery** and **specialized
notebook rendering**.

## 📍 Context

The current "hardened" version of
[`analysis/biocirv-ai/src/ca_biositing/ai_exploration/sandbox_setup.py`](analysis/biocirv-ai/src/ca_biositing/ai_exploration/sandbox_setup.py)
has become over-engineered with monkeypatches attempting to solve
`TypeError: unhashable type: 'list'`. These patches are now causing
`ValidationError` in Jupyter due to class identity mismatches (likely caused by
module purging/reloading).

The version at commit
[`b2bb674`](https://github.com/sustainability-software-lab/biocirv-ai/commit/b2bb674e7c599417caefba7dad6203b1479e2305)
was working well using a simpler `SmartDataframe` approach.

## 🛠️ Restoration Requirements

### 1. Agent Logic (Revert to `b2bb674`)

- Revert the `get_agent` function to use `SmartDataframe` instead of
  `PandasConnector`.
- Critical line from the working version:
  ```python
  sdf = SmartDataframe(df, name=view, description=f"View '{view}' with columns: {metadata}")
  sdf.schema.name = view # Vital for internal schema consistency
  ```
- Use the current `discover_views` and `fetch_table_metadata` logic from
  [`analysis/biocirv-ai/src/ca_biositing/ai_exploration/schema.py`](analysis/biocirv-ai/src/ca_biositing/ai_exploration/schema.py).

### 2. Rendering (Preserve Current)

- The user likes the current notebook rendering (DataFrames triggering VS Code
  Data Viewer, interactive Plotly figures).
- Keep the enhanced `SandboxResponseParser` and its logic for unwrapping
  `Response` objects.

### 3. Cleanup

- Remove the aggressive "Nuclear Cache Killer" and complex `sys.modules`
  purging.
- The `unhashable type: 'list'` issue should be addressed by ensuring
  `SmartDataframe` state is consistent, rather than global monkeypatching.
- If patching is still needed, prefer targeted fixes in `__init__` rather than
  purging modules.

## 📂 Reference Files

- **Legacy Hardened Version**:
  [`analysis/biocirv-ai/src/ca_biositing/ai_exploration/legacy/sandbox_setup_hardened.py`](analysis/biocirv-ai/src/ca_biositing/ai_exploration/legacy/sandbox_setup_hardened.py)
  (The over-engineered version to be simplified).
- **Working Baseline**: See commit `b2bb674` for the original
  `get_agent_with_metadata` implementation.

## 🧪 Testing

1.  Verify with
    [`analysis/biocirv-ai/debug_chat.py`](analysis/biocirv-ai/debug_chat.py)
    (CLI).
2.  Verify in Jupyter using
    [`analysis/biocirv-ai/notebooks/sandbox_exploration.ipynb`](analysis/biocirv-ai/notebooks/sandbox_exploration.ipynb).
    - Ensure that running Cell 1 (LLM init) and then Cell 2 (Agent init) doesn't
      cause `ValidationError`.
