"""Background research jobs for the API.

A research run takes minutes, so ``POST /api/ipos/{id}/research`` queues it
on a single worker thread and returns immediately; the UI polls the run.
One worker keeps subscription usage predictable — runs execute one at a
time, while each run's own steps are throttled by ``LLM_MAX_CONCURRENCY``.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.database import db
from src.research.orchestrator import ResearchError, run_research
from src.research.prompts import PROMPT_VERSION

if TYPE_CHECKING:
    from src.llm import LLMClient

logger = logging.getLogger(__name__)


class ResearchJobs:
    """Queue research runs; at most one active run per IPO."""

    def __init__(self, client: LLMClient, *, db_path: str | Path | None = None) -> None:
        self.client = client
        self.db_path = db_path
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="research"
        )
        self._lock = threading.Lock()

    def submit(self, ipo_id: int) -> tuple[dict[str, Any], bool]:
        """Queue a run; returns ``(run, created)``.

        An already queued/running run for the IPO is returned unchanged with
        ``created=False`` so double-clicks never start duplicate runs.
        """

        with self._lock:
            active = db.get_active_research_run(ipo_id, db_path=self.db_path)
            if active is not None:
                return active, False
            run_id = db.create_research_run(
                ipo_id, prompt_version=PROMPT_VERSION, db_path=self.db_path
            )
        self._executor.submit(self._execute, ipo_id, run_id)
        run = db.get_research_run(run_id, db_path=self.db_path)
        assert run is not None
        return run, True

    def _execute(self, ipo_id: int, run_id: int) -> None:
        try:
            run_research(
                ipo_id, client=self.client, db_path=self.db_path, run_id=run_id
            )
        except ResearchError as exc:
            logger.warning("Research run %s failed: %s", run_id, exc)
        except Exception:  # noqa: BLE001 - keep the worker alive
            logger.exception("Unexpected error in research run %s", run_id)
            db.update_research_run(
                run_id, status="failed", error="unexpected error", db_path=self.db_path
            )

    def shutdown(self, *, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=True)


__all__ = ["ResearchJobs"]
