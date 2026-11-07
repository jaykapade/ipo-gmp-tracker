"""Filtering rules for turning the IPO universe into an actionable shortlist."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from src import config
from src.database import db
from src.utils.parsing import is_active_status, parse_date


@dataclass
class Candidate:
    """An IPO that passed the active + minimum-GMP filter."""

    ipo: dict[str, Any]
    latest_gmp: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    open_date: date | None = None
    close_date: date | None = None

    @property
    def name(self) -> str:
        return self.ipo.get("name") or ""

    @property
    def ipo_id(self) -> int:
        return int(self.ipo["id"])

    @property
    def gmp(self) -> float | None:
        value = self.latest_gmp.get("gmp")
        return float(value) if value is not None else None

    @property
    def gmp_percent(self) -> float | None:
        value = self.latest_gmp.get("gmp_percent")
        return float(value) if value is not None else None

    @property
    def gmp_percent_derived(self) -> bool:
        """True when GMP % was calculated from GMP ÷ issue price."""

        return bool(self.latest_gmp.get("derived"))

    @property
    def gmp_source(self) -> str | None:
        return self.latest_gmp.get("source")

    @property
    def gmp_recorded_at(self) -> str | None:
        return self.latest_gmp.get("recorded_at")


def row_is_active(
    row: dict[str, Any],
    include_upcoming: bool | None = None,
) -> bool:
    """Decide whether a database row represents an active IPO."""

    if include_upcoming is None:
        include_upcoming = config.INCLUDE_UPCOMING

    return is_active_status(
        status=row.get("status"),
        open_date=parse_date(row.get("open_date")),
        close_date=parse_date(row.get("close_date")),
        include_upcoming=include_upcoming,
    )


def select_candidates(
    min_gmp_percent: float | None = None,
    include_upcoming: bool | None = None,
    db_path: str | Path | None = None,
    include_history: bool = True,
    history_limit: int | None = 30,
) -> list[Candidate]:
    """Return active IPOs whose latest GMP is at or above the threshold.

    ``min_gmp_percent`` and ``include_upcoming`` fall back to the values in
    ``src.config`` (which can be set through environment variables).
    """

    threshold = (
        config.MIN_GMP_PERCENT if min_gmp_percent is None else min_gmp_percent
    )
    upcoming = (
        config.INCLUDE_UPCOMING if include_upcoming is None else include_upcoming
    )

    rows = db.get_candidates(min_gmp_percent=threshold, db_path=db_path)

    candidates: list[Candidate] = []
    for row in rows:
        if not row_is_active(row, include_upcoming=upcoming):
            continue

        latest_gmp = {
            "gmp": row.get("latest_gmp"),
            "gmp_percent": row.get("latest_gmp_percent"),
            "source": row.get("latest_gmp_source"),
            "recorded_at": row.get("latest_gmp_recorded_at"),
            "derived": bool(row.get("latest_gmp_percent_derived")),
        }

        history = (
            db.get_gmp_history(
                int(row["id"]),
                limit=history_limit,
                db_path=db_path,
            )
            if include_history
            else []
        )

        candidates.append(
            Candidate(
                ipo=row,
                latest_gmp=latest_gmp,
                history=history,
                open_date=parse_date(row.get("open_date")),
                close_date=parse_date(row.get("close_date")),
            )
        )

    return candidates
