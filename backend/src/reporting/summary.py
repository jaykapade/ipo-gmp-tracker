"""Plain-text summaries used by the CLI and the email body."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING

from src.models.analysis import IPOAnalysis
from src.utils.parsing import IST

if TYPE_CHECKING:
    from src.research.digest import ResearchDigest


def _number(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    return f"{value:,.2f}{suffix}"


def _rupees(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"Rs {value:,.2f}"


def format_research_time(value: str | None) -> str:
    """ISO timestamp -> '21 Nov 2026, 09:10 IST' (or the raw value)."""

    if not value:
        return "n/a"
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return value
    return moment.astimezone(IST).strftime("%d %b %Y, %H:%M IST")


def research_headline(digest: ResearchDigest) -> str:
    """'Watch (low confidence, 2 disputes)' or a short reason it is missing."""

    if not digest.has_result:
        return "not available"
    parts = [f"{digest.confidence or 'unknown'} confidence"]
    if digest.disputes:
        parts.append(f"{digest.disputes} dispute{'s' if digest.disputes != 1 else ''}")
    return f"{digest.verdict} ({', '.join(parts)})"


def _research_lines(digest: ResearchDigest) -> list[str]:
    lines = [f"   AI research: {research_headline(digest)}"]
    if digest.has_result:
        lines[0] += f" -- {format_research_time(digest.researched_at)}"
        if digest.conclusion:
            lines.append(f"   AI view: {digest.conclusion}")
        if digest.strengths:
            lines.append(f"   AI strength: {digest.strengths[0]}")
        if digest.risks:
            lines.append(f"   AI risk: {digest.risks[0]}")
    if digest.note:
        lines.append(f"   Note: {digest.note}")
    return lines


def build_text_summary(
    analyses: list[IPOAnalysis],
    *,
    min_gmp_percent: float,
    include_upcoming: bool = False,
    generated_at: datetime | None = None,
    research: Mapping[int, ResearchDigest] | None = None,
) -> str:
    """Return a readable summary suitable for a terminal or an email body.

    ``research`` adds each IPO's AI research verdict beside (never instead
    of) the rule-based score.
    """

    moment = (generated_at or datetime.now(IST)).astimezone(IST)
    lines = [
        "IPO Checker analysis",
        f"Generated: {moment.strftime('%d %b %Y, %H:%M IST')}",
        (
            f"Filter: latest GMP >= {min_gmp_percent:g}%"
            f" | upcoming {'included' if include_upcoming else 'excluded'}"
        ),
    ]
    if research is not None:
        lines.append(
            "AI research: included beside the rule-based score; web facts are "
            "unverified."
        )
    lines.append("")

    if not analyses:
        lines.append("No IPOs matched the current criteria.")
        lines.append("")
        lines.append(
            "Tip: run `python -m src.main scrape` first, or lower `MIN_GMP_PERCENT`."
        )
        return "\n".join(lines)

    for index, analysis in enumerate(analyses, start=1):
        gmp_note = " (derived)" if analysis.gmp_percent_derived else ""
        lines.append(
            f"{index}. {analysis.name} -- {analysis.verdict} "
            f"({analysis.score:.1f}/100)"
        )
        lines.append(
            "   "
            f"GMP: {_rupees(analysis.gmp)}"
            f" ({_number(analysis.gmp_percent, '%')}{gmp_note})"
            f" | Issue: {_rupees(analysis.issue_price)}"
            f" | Closes: {analysis.close_date or 'n/a'}"
        )
        lines.append(
            "   "
            f"Subscription: {_number(analysis.subscription, 'x')}"
            f" | P/E: {_number(analysis.pe)}"
            f" | Issue size: {_number(analysis.issue_size_cr, ' cr')}"
        )

        if analysis.strengths:
            lines.append(f"   Strength: {analysis.strengths[0]}")
        if analysis.risks:
            lines.append(f"   Risk: {analysis.risks[0]}")

        if research is not None and analysis.ipo_id in research:
            lines.extend(_research_lines(research[analysis.ipo_id]))

        lines.append("")

    lines.append("Grey-market premium is unofficial and can change at any time.")
    lines.append("This report is for personal research, not investment advice.")
    return "\n".join(lines)
