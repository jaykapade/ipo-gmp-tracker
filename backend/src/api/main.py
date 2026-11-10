"""FastAPI application factory for the IPO Checker.

Run it with::

    python -m src.main serve
    # or
    uvicorn src.api.main:app --reload --port 8000

The API is read-only by default. ``POST /api/analyze`` and ``POST /api/reports``
require the ``X-API-Token`` header when ``API_TOKEN`` is configured.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src import config
from src.api.chat import router as chat_router
from src.api.routes import router


def create_app(
    *,
    db_path: str | Path | None = None,
    report_dir: str | Path | None = None,
    api_token: str | None = None,
    cors_origins: tuple[str, ...] | None = None,
) -> FastAPI:
    """Build an app with optional per-instance paths (used by tests)."""

    app = FastAPI(
        title="IPO Checker API",
        version="0.1.0",
        description=(
            "Read-only access to scraped IPOs, deterministic analysis and "
            "generated PDF reports. Mutating endpoints require X-API-Token."
        ),
    )

    app.state.db_path = db_path
    app.state.report_dir = (
        Path(report_dir) if report_dir is not None else config.REPORT_OUTPUT_DIR
    )
    app.state.api_token = (
        config.API_TOKEN if api_token is None else api_token
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors_origins or config.CORS_ORIGINS),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    app.include_router(chat_router)
    return app


app = create_app()
