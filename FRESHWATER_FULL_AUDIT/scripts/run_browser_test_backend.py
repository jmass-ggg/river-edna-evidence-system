#!/usr/bin/env python3
"""Start an isolated backend for Playwright browser verification."""
from __future__ import annotations

import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
database = Path(os.environ.get("EDNA_BROWSER_TEST_DB", "/tmp/edna-browser-test.sqlite"))
database.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{database}"
os.environ["DEBUG"] = "false"
sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import create_tables  # noqa: E402

create_tables()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=18001, log_level="warning")
