"""Numeric metrics derived from a candidate and its GMP history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from src.analysis.filters import Candidate
from src.utils.parsing import parse_date, parse_float, today_ist


@dataclass(frozen=True)
class Metrics:
    """Everything the scorer and checklist are allowed to look at."""

    gmp: float | None
    gmp_percent: float | None
    gmp_percent_derived: bool = False
    gmp_trend: float | None = None
    gmp_trend_label: str = "Unknown"
    issue_price: float | None = None
    issue_size_cr: float | None = None
    subscription: float | None = None
    pe: float | None = None
    days_to_close: int | None = None
    history_points: int = 0
    source_count: int = 0
    source_spread_percent: float | None = None


def _as_float(value: Any) -> float | None:
    return parse_float(value) if value is not None else None


def _trend_label(change: float | None) -> str:
    if change is None:
        return "Unknown"
    if change > 2.0:
        return "Rising"
    if change < -2.0:
        return "Falling"
    return "Stable"


def compute_metrics(
    candidate: Candidate,
    *,
    today: date | None = None,
) -> Metrics:
    """Compute all metrics from the candidate row and GMP history."""

    ipo = candidate.ipo
    reference_day = today or today_ist()

    gmp = candidate.gmp
    if gmp is None:
        gmp = _as_float(ipo.get("latest_gmp"))

    gmp_percent = candidate.gmp_percent
    derived = False
    if gmp_percent is None:
        gmp_percent = _as_float(ipo.get("latest_gmp_percent"))

    issue_price = _as_float(ipo.get("issue_price"))
    if gmp_percent is None and gmp is not None and issue_price:
        gmp_percent = (gmp * 100.0) / issue_price
        derived = True

    history = candidate.history or []

    percent_points = [
        value
        for row in history
        if (value := _as_float(row.get("gmp_percent"))) is not None
    ]
    if len(percent_points) >= 2:
        gmp_trend = percent_points[0] - percent_points[-1]
    else:
        gmp_trend = None

    latest_by_source: dict[str, float] = {}
    for row in history:
        source = row.get("source")
        value = _as_float(row.get("gmp_percent"))
        if source and value is not None and source not in latest_by_source:
            latest_by_source[source] = value

    if len(latest_by_source) >= 2:
        values = list(latest_by_source.values())
        source_spread = max(values) - min(values)
    else:
        source_spread = None

    close_date = candidate.close_date or parse_date(ipo.get("close_date"))
    days_to_close = (close_date - reference_day).days if close_date else None

    return Metrics(
        gmp=gmp,
        gmp_percent=gmp_percent,
        gmp_percent_derived=derived,
        gmp_trend=gmp_trend,
        gmp_trend_label=_trend_label(gmp_trend),
        issue_price=issue_price,
        issue_size_cr=_as_float(ipo.get("ipo_size_cr")),
        subscription=_as_float(ipo.get("subscription")),
        pe=_as_float(ipo.get("pe")),
        days_to_close=days_to_close,
        history_points=len(history),
        source_count=len(latest_by_source) or (1 if history else 0),
        source_spread_percent=source_spread,
    )
