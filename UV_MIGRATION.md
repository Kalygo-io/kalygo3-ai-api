# Migration to UV and LangChain 1.0+

This document describes the migration from `pip` to `uv` and the upgrade to LangChain 1.0+.

## Changes Made

### 1. Package Management Migration (pip → uv)

- **Created `pyproject.toml`**: Migrated all dependencies from `requirements.txt` to `pyproject.toml` format
- **Updated Dockerfiles**: Both `Dockerfile.dev` and `Dockerfile.prod` now use `uv` instead of `pip`
  - Uses `uv pip install --system --no-cache .` to install dependencies
  - `uv` binary is copied from the official Docker image

### 2. LangChain Upgrade (0.3.27 → 1.0+)

- **Updated LangChain packages**:
  - `langchain>=1.0.0`
  - `langchain-core>=1.0.0`
  - `langchain-openai>=1.0.0`
  - `langchain-community>=0.3.31`
  - `langchain-ollama>=0.3.10` (compatible version)

### 3. Code Updates

- **Updated imports**:
  - `from langchain.tools.base import StructuredTool` → `from langchain_core.tools import StructuredTool`
  - `from langchain_core.pydantic_v1 import` → `from pydantic import` (already migrated earlier)
  
- **Note**: Other LangChain imports (`langchain.agents`, `langchain.memory`, `langchain.callbacks`) remain compatible with LangChain 1.0+

## Usage

### Development Container

The dev container will automatically use `uv` when building. Dependencies are installed from `pyproject.toml`.

### Production Container

The production container uses `uv` for faster, more reliable dependency installation.

### Local Development

To use `uv` locally:

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv pip install -e .

# Or use uv sync if you want a virtual environment
uv sync
```

## Testing

After migration, verify that:
1. The application imports successfully
2. All LangChain agents and tools work correctly
3. The Docker containers build successfully

## Rollback

If you need to rollback:
1. Revert `pyproject.toml` changes
2. Revert Dockerfile changes
3. Use `requirements.txt` with `pip` as before

