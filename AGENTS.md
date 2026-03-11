# AGENTS.md

Agent instructions for `bq_caapi_ge` -- Google ADK agents bridging the Conversational Analytics API with Gemini Enterprise via OAuth identity passthrough.

## Project Overview

- **Language:** Python 3.11 (`>=3.11,<3.12`)
- **Package manager:** `uv` (lockfile: `uv.lock`)
- **Framework:** Google ADK (`google-adk`), CA API (`google-cloud-geminidataanalytics`)
- **Linter/Formatter:** Ruff with default config (no `ruff.toml` or `[tool.ruff]`)
- **Tests:** None configured. If added, use `pytest` in a `tests/` directory.

## Build, Lint, and Run Commands

```bash
# Install all dependencies
uv sync
uv sync --group dev          # includes ruff

# Lint and format
uv run ruff check .           # lint
uv run ruff check --fix .     # lint with auto-fix
uv run ruff format .          # format
uv run ruff format --check .  # format check (CI)

# Run agents locally (requires configured .env)
export $(cat .env | xargs)
uv run adk run app/orders
uv run adk run app/inventory

# Run operational scripts
uv run python scripts/admin_tools.py
uv run python scripts/setup_auth.py
uv run python scripts/register_agents.py --orders-resource <RESOURCE>

# Deploy to Vertex AI Agent Engine
bash scripts/deploy_agents.sh

# Test web app (standalone Flask OAuth harness)
cd test_web && uv venv .venv && source .venv/bin/activate
uv pip install --index-url https://pypi.org/simple/ -r requirements.txt
python app.py
```

If tests are added, run a single test with:
```bash
uv run pytest tests/test_module.py::test_function -v
```

## Project Structure

```
app/                        # ADK agent packages (each is a deployable unit)
  orders/                   # Orders Analyst agent
    __init__.py             # Re-exports: from . import agent as agent
    agent.py                # Agent def, OAuth bridge, DataAgentToolset
  inventory/                # Inventory Analyst agent (same structure)
scripts/                    # Operational scripts (not part of agent packages)
  admin_tools.py            # Create/update backend Data Agents
  setup_auth.py             # Create OAuth authorization resources
  register_agents.py        # Register agents with Gemini Enterprise
  deploy_agents.sh          # Automated deployment to Agent Engine
test_web/                   # Flask OAuth test harness (standalone)
docs/examples/              # Reference implementations (print() is OK here)
```

## Code Style

### Formatting

- **Line length:** 88 characters (Ruff default)
- **Indentation:** 4 spaces
- **Quotes:** Double quotes
- **Trailing commas:** Use in multi-line structures

### Imports

Order (enforced by Ruff isort):
1. `from __future__ import annotations` (always first)
2. Standard library (`json`, `logging`, `os`, `datetime`, etc.)
3. Third-party (`google.adk`, `google.cloud`, `dotenv`, `flask`)
4. Local/relative imports

```python
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional

from google.adk.agents import Agent
from google.adk.tools.base_tool import BaseTool
```

### Type Annotations

- Every module starts with `from __future__ import annotations`
- Use lowercase generics: `dict[str, Any]`, `list[str]` (not `Dict`, `List`)
- Use PEP 604 unions: `str | None` (enabled by future annotations)
- Use `Optional[dict]` for return types (existing codebase convention)
- Type-annotate all function parameters and return values

### Naming Conventions

- **Functions/variables:** `snake_case` (`bridge_oauth_token`, `get_bq_refs`)
- **Constants:** `UPPER_SNAKE_CASE` (`PROJECT_ID`, `MODEL_NAME`, `SCOPES`)
- **Classes:** `PascalCase` (framework classes only; no custom classes)
- **Modules/files:** `snake_case` (`admin_tools.py`, `setup_auth.py`)
- **Agent names:** `snake_case` strings (`"orders_analyst"`, `"inventory_analyst"`)

### Logging

- Use `logging` module. Never use `print()` in agent or script code.
  (`print` is acceptable only in `docs/examples/` and `test_web/`.)
- Module-level setup:
  ```python
  logging.basicConfig(level=logging.INFO)
  logger = logging.getLogger(__name__)
  ```
- Scripts use extended format: `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"`
- Use f-strings in log messages (project convention, not `%s` style)

### Docstrings

Google-style docstrings on all public functions and script modules.
Include `Args:`, `Returns:`, `Raises:` sections where applicable:

```python
def create_auth_resource(auth_id: str) -> None:
    """Create an OAuth authorization resource in Gemini Enterprise.

    Args:
        auth_id: The authorization resource ID to create.

    Raises:
        ValueError: If OAUTH_CLIENT_ID or OAUTH_CLIENT_SECRET is not set.
    """
```

### Error Handling

- Raise `ValueError` for missing configuration or invalid input
- Catch specific exceptions, not bare `except Exception`
- Log errors with `logger.error()` and include `exc_info=True` when re-raising
- For "already exists" cases, catch and log as info rather than failing
- Use `check=False` with `subprocess.run` when handling errors manually;
  use `check=True` or `check_output` when failure should propagate

### Configuration

- All config via environment variables using `os.getenv()` with sensible defaults
- Use `python-dotenv` (`load_dotenv()`) for `.env` files
- Root `.env` for shared config; per-agent `.env` in `app/<agent>/`
- Never hardcode secrets; `.env` files are gitignored

### Agent Module Pattern

Each agent package (`app/orders/`, `app/inventory/`) follows:
- `__init__.py` re-exports: `from . import agent as agent`
- `agent.py` defines: module-level config, async `bridge_oauth_token` callback,
  `DataAgentCredentialsConfig`, `DataAgentToolset`, and a `root_agent` variable
- The `root_agent` variable name is required by the ADK framework

### Shell Scripts

- Use `#!/bin/bash` and `set -e`
- Validate required env vars early with clear error messages
- Use color codes for output (`RED`, `GREEN`, `YELLOW`, `NC`)
- Load `.env` with `export $(cat .env | xargs)`

## Environment and Secrets

- `.env` files are gitignored -- never commit them
- See `.env.example` for required variables
- Per-agent `.env` files: `app/orders/.env`, `app/inventory/.env`
- `OAUTH_CLIENT_ID` and `OAUTH_CLIENT_SECRET` are required for all operations
- `GOOGLE_GENAI_USE_VERTEXAI=TRUE` must be set for ADK to use Vertex AI
