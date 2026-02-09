from __future__ import annotations

# Backward-compatible import path:
# keep `uvicorn local_review_copilot.app:app` working.
from .server import app

__all__ = ["app"]
