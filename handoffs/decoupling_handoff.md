# Handoff: Decoupling biocirv-ai from ca-biositing

## Overview

The goal is to fully decouple the `biocirv-ai` submodule from the parent
`ca-biositing` repository's dependency tree. This allows the AI exploration
tools to use modern libraries (Pandas 2.x, PandasAI 2.3.x) without conflicting
with the parent repo's legacy pins (Pandas 1.5.3).

## Status

- `biocirv-ai` is already a submodule located at `analysis/biocirv-ai/`.
- Modernization of the AI logic and notebook cleanup is complete.
- Temporary "bridge" configurations exist in the parent `pixi.toml` that need to
  be reverted.

## Action Plan

### 1. Revert Parent Repository Changes

The parent repo should have zero knowledge of AI dependencies.

- **File**: `pixi.toml` (root)
- **Actions**:
  - Remove the `ai` environment from `[environments]`.
  - Remove the `ai` feature from `[environments]`.
  - Delete the `[feature.ai.dependencies]` and `[feature.ai.pypi-dependencies]`
    blocks.
  - Ensure `[pypi-dependencies]` is back to its original state (only
    `sqlalchemy`).

### 2. Configure Standalone AI Manifests

The submodule must manage its own modern environment.

- **Directory**: `analysis/biocirv-ai/`
- **File**: `analysis/biocirv-ai/pyproject.toml`
  - Ensure `pandas >= 2.2.0` is specified.
  - Ensure `pandasai >= 2.3.0` and `pandasai-sql[postgres]` are present.
- **File**: `analysis/biocirv-ai/pixi.toml`
  - Update `[dependencies]` to use `python = "3.11.*"` and `pandas = ">=2.2"`.
  - Ensure it is fully solvable independently of the parent.

### 3. Verification

- Run `pixi install` in the root to ensure the parent repo is stable.
- `cd analysis/biocirv-ai` and run `pixi install` to ensure the submodule solves
  its own modern stack.

---

## Handoff Prompt for AI Assistant

```text
Goal: Fully decouple the 'biocirv-ai' submodule from the parent 'ca-biositing' dependency tree.

Context:
The parent repo is pinned to Pandas 1.5.3. The AI tools need Pandas 2.x.
The AI repo is a submodule at 'analysis/biocirv-ai/' and has its own manifests.

Tasks:
1. Revert 'pixi.toml' (root): Remove the 'ai' environment and 'feature.ai' blocks. Restore it to match upstream (only core dependencies).
2. Update 'analysis/biocirv-ai/pyproject.toml': Ensure it uses 'pandas >= 2.2.0' and the latest 'pandasai-sql[postgres]'.
3. Update 'analysis/biocirv-ai/pixi.toml': Update to 'python 3.11' and 'pandas >= 2.2' to ensure it solves independently with a modern stack.
4. Verify: Ensure 'pixi install' works in BOTH the root directory and the 'analysis/biocirv-ai' directory independently.
```
