"""FastAPI application factory for the IPO Checker.

Run it with::

    python -m src.main serve
    # or
    uvicorn src.api.main:app --reload --port 8000

The API is read-only by default. ``POST /api/analyze`` and ``POST /api/reports``
require the ``X-API-Token`` header when ``API_TOKEN`` is configured.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src import config
from src.api.chat import router as chat_router
from src.api.routes import router
from src.config import LLMSettings
from src.database import db
from src.llm import LLMClient
from src.research import ResearchJobs

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    stale = db.mark_stale_research_runs_failed(db_path=app.state.db_path)
    if stale:
        logger.warning("Marked %d interrupted research run(s) as failed", stale)
    yield
    app.state.research.shutdown()


def create_app(
    *,
    db_path: str | Path | None = None,
    report_dir: str | Path | None = None,
    api_token: str | None = None,
    cors_origins: tuple[str, ...] | None = None,
    llm_settings: LLMSettings | None = None,
) -> FastAPI:
    """Build an app with optional per-instance paths (used by tests)."""

    app = FastAPI(
        title="IPO Checker API",
        version="0.1.0",
        description=(
            "Read-only access to scraped IPOs, deterministic analysis and "
            "generated PDF reports. Mutating endpoints require X-API-Token."
        ),
        lifespan=_lifespan,
    )

    app.state.db_path = db_path
    app.state.report_dir = (
        Path(report_dir) if report_dir is not None else config.REPORT_OUTPUT_DIR
    )
    app.state.api_token = (
        config.API_TOKEN if api_token is None else api_token
    )
    app.state.llm = LLMClient(
        llm_settings if llm_settings is not None else config.LLM
    )
    app.state.research = ResearchJobs(app.state.llm, db_path=db_path)

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
