"""Kuber configuration — reads Plaid credentials from the project-root .env file."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Walk up from scripts/ to find the project root .env
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

PLAID_CLIENT_ID: str = os.environ.get("PLAID_CLIENT_ID", "")
PLAID_SECRET: str = os.environ.get("PLAID_SECRET", "")
PLAID_ENV: str = os.environ.get("PLAID_ENV", "production")
PLAID_LINK_PORT: int = int(os.environ.get("PLAID_LINK_PORT", "8765"))

DATA_DIR: Path = _project_root / "data"
