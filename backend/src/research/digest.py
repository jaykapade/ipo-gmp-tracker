"""Short research summaries for reports, and research-on-demand for ``run``.

``research_for_report`` is what ``run --research`` / ``report --research``
call after the deterministic analysis: for each screened IPO it reuses a
recent completed research run, runs a new one when the last is too old, and
never lets an AI problem stop the report. Every IPO gets a
:class:`ResearchDigest` describing what the report can show.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from src.database import db
from src.reporting.sources import SourceLink, research_sources

logger = logging.getLogger(__name__)

DigestStatus = Literal[
    "new",  # researched during this run
    "reused",  # a completed run newer than the max age
    "in_progress",  # another process is researching it right now
    "failed",  # a new run failed this time
    "unavailable",  # AI is disabled or not configured
    "none",  # no research and none attempted
]

_NOTES: dict[str, str] = {
    "in_progress": "AI research is still running for this IPO.",
    "failed": "AI research failed this run.",
    "unavailable": "AI research unavailable (AI is disabled or not configured).",
    "none": "No AI research yet.",
}


@dataclass
class ResearchDigest:
    """What a report shows about one IPO's AI research."""

    ipo_id: int
    status: DigestStatus
    verdict: str | None = None
    confidence: str | None = None
    conclusion: str | None = None
    strengths: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    disputes: int = 0
    researched_at: str | None = None
    run_id: int | None = None
    error: str | None = None
    sources: list[SourceLink] = field(default_factory=list)

    @property
    def has_result(self) -> bool:
        return self.verdict is not None

    @property
    def note(self) -> str | None:
        """A one-line caveat for the report, or ``None`` when the result is current."""

        base = _NOTES.get(self.status)
        if base is None:
            return None
        if self.status == "failed" and self.error:
            base = f"{base[:-1]}: {self.error[:160]}"
        if self.has_result:
            base += " Showing the previous result."
        return base


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _completed_run(latest: dict[str, Any] | None) -> dict[str, Any] | None:
    if latest is None:
        return None
    if latest.get("status") == "done":
        return latest
    return latest.get("latest_completed")


def _fill_from_run(digest: ResearchDigest, run: dict[str, Any] | None) -> ResearchDigest:
    if run is None:
        return digest
    outputs = {item["kind"]: item["output"] for item in run.get("outputs", [])}
    assessment = outputs.get("h5")
    if not isinstance(assessment, dict):
        return digest
    digest.verdict = assessment.get("verdict")
    digest.confidence = (assessment.get("confidence") or {}).get("level")
    digest.conclusion = assessment.get("conclusion")
    digest.strengths = list(assessment.get("strengths") or [])
    digest.risks = list(assessment.get("risks") or [])
    disputes = outputs.get("disputes")
    if isinstance(disputes, dict):
        disputes = disputes.get("disputes")
    digest.disputes = len(disputes) if isinstance(disputes, list) else 0
    digest.researched_at = run.get("finished_at") or run.get("created_at")
    digest.run_id = run.get("id")
    digest.sources = research_sources(outputs.get("facts"))
    return digest


def latest_digest(
    ipo_id: int,
    *,
    status: DigestStatus = "reused",
    error: str | None = None,
    db_path: str | Path | None = None,
) -> ResearchDigest:
    """Summarise the newest completed research for an IPO."""

    latest = db.get_latest_research(ipo_id, db_path=db_path)
    digest = ResearchDigest(ipo_id=ipo_id, status=status, error=error)
    return _fill_from_run(digest, _completed_run(latest))


def _is_fresh(digest: ResearchDigest, max_age: timedelta, now: datetime) -> bool:
    moment = _parse_time(digest.researched_at)
    return digest.has_result and moment is not None and now - moment <= max_age


def research_for_report(
    ipo_ids: Iterable[int],
    *,
    client: Any,
    max_age_hours: float,
    db_path: str | Path | None = None,
    on_event: Callable[[int, str], None] | None = None,
    now: datetime | None = None,
) -> dict[int, ResearchDigest]:
    """Make sure each IPO has recent research, then summarise it.

    ``client`` is an :class:`~src.llm.LLMClient`. Research runs one IPO at a
    time; failures are recorded on the digest and the loop carries on.
    """

    from src.research.orchestrator import ResearchError, run_research

    emit = on_event or (lambda _ipo_id, _message: None)
    moment = now or datetime.now(UTC)
    max_age = timedelta(hours=max(0.0, max_age_hours))
    ai_on = bool(client is not None and client.for_role("analyst").enabled)
    # Otherwise a run orphaned by a killed process blocks its IPO forever.
    db.mark_stale_research_runs_failed(db_path=db_path)

    digests: dict[int, ResearchDigest] = {}
    for ipo_id in ipo_ids:
        current = latest_digest(ipo_id, db_path=db_path)

        if _is_fresh(current, max_age, moment):
            emit(ipo_id, f"reusing research from {current.researched_at}")
            digests[ipo_id] = current
            continue

        if db.get_active_research_run(ipo_id, db_path=db_path) is not None:
            emit(ipo_id, "research already in progress; not starting another")
            current.status = "in_progress"
            digests[ipo_id] = current
            continue

        if not ai_on:
            current.status = "unavailable"
            digests[ipo_id] = current
            continue

        emit(ipo_id, "researching")
        try:
            run_research(
                ipo_id,
                client=client,
                db_path=db_path,
                on_stage=lambda stage, _id=ipo_id: emit(_id, f"stage {stage}"),
            )
        except ResearchError as exc:
            logger.warning("Research for IPO %s failed: %s", ipo_id, exc)
            emit(ipo_id, f"failed: {exc}")
            digests[ipo_id] = latest_digest(
                ipo_id, status="failed", error=str(exc), db_path=db_path
            )
            continue

        digests[ipo_id] = latest_digest(ipo_id, status="new", db_path=db_path)

    return digests


def stored_digests(
    ipo_ids: Iterable[int],
    *,
    db_path: str | Path | None = None,
) -> dict[int, ResearchDigest]:
    """Summaries of whatever research already exists; never runs anything."""

    digests: dict[int, ResearchDigest] = {}
    for ipo_id in ipo_ids:
        digest = latest_digest(ipo_id, db_path=db_path)
        if not digest.has_result:
            digest.status = "none"
        digests[ipo_id] = digest
    return digests


__all__ = [
    "ResearchDigest",
    "latest_digest",
    "research_for_report",
    "stored_digests",
]
