"""Plain-text summaries used by the CLI and the email body."""

from __future__ import annotations

from datetime import datetime

from src.models.analysis import IPOAnalysis
from src.utils.parsing import IST


def _number(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    return f"{value:,.2f}{suffix}"


def _rupees(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"Rs {value:,.2f}"


def build_text_summary(
    analyses: list[IPOAnalysis],
    *,
    min_gmp_percent: float,
    include_upcoming: bool = False,
    generated_at: datetime | None = None,
) -> str:
    """Return a readable summary suitable for a terminal or an email body."""

    moment = (generated_at or datetime.now(IST)).astimezone(IST)
    lines = [
        "IPO Checker analysis",
        f"Generated: {moment.strftime('%d %b %Y, %H:%M IST')}",
        (
            f"Filter: latest GMP >= {min_gmp_percent:g}%"
            f" | upcoming {'included' if include_upcoming else 'excluded'}"
        ),
        "",
    ]

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

        lines.append("")

    lines.append("Grey-market premium is unofficial and can change at any time.")
    lines.append("This report is for personal research, not investment advice.")
    return "\n".join(lines)
