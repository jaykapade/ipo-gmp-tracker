"""HTML email body: the same content as the text summary, laid out for mail clients.

Mail clients ignore stylesheets and modern CSS, so the layout uses nested
tables and inline styles only, at most 600px wide, with no images or scripts.
Every value from the database or the AI research is HTML-escaped.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from html import escape
from typing import TYPE_CHECKING

from src.models.analysis import IPOAnalysis
from src.reporting.summary import _number, format_research_time
from src.utils.parsing import IST

if TYPE_CHECKING:
    from src.reporting.sources import SourceLink
    from src.research.digest import ResearchDigest

_FONT = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
_INK = "#101828"
_MUTED = "#667085"
_BORDER = "#EAECF0"
_LINK = "#1D4ED8"
_VERDICT = {  # text colour, background tint
    "Strong": ("#1B7F3B", "#ECFDF3"),
    "Watch": ("#B54708", "#FFFAEB"),
    "Avoid": ("#B42318", "#FEF3F2"),
}

# The PDF carries the full AI conclusion; the email shows the opening.
AI_SNIPPET_CHARS = 320


def _e(value: object) -> str:
    return escape(str(value), quote=True)


def _rupees(value: float | None) -> str:
    return "n/a" if value is None else f"₹{value:,.2f}"


def _date(value: str | None) -> str:
    if not value:
        return "n/a"
    try:
        return date.fromisoformat(value).strftime("%d %b %Y")
    except ValueError:
        return value


def _snippet(text: str, limit: int = AI_SNIPPET_CHARS) -> str:
    """Cut at the last sentence end before ``limit`` (or hard-cut with an ellipsis)."""

    if len(text) <= limit:
        return text
    cut = text.rfind(". ", 0, limit)
    return text[: cut + 1] if cut > limit // 3 else text[:limit].rstrip() + "…"


def _pill(label: str, verdict: str | None, detail: str) -> str:
    color, tint = _VERDICT.get(verdict or "", (_MUTED, "#F2F4F7"))
    return (
        f'<td style="background:{tint};border-radius:8px;padding:10px 12px;'
        f'vertical-align:top;width:50%;">'
        f'<div style="font-size:11px;color:{_MUTED};text-transform:uppercase;'
        f'letter-spacing:.04em;">{_e(label)}</div>'
        f'<div style="font-size:18px;font-weight:700;color:{color};margin-top:2px;">'
        f"{_e(verdict or 'Not available')}</div>"
        f'<div style="font-size:12px;color:{_INK};margin-top:2px;">{_e(detail)}</div>'
        "</td>"
    )


def _metrics(analysis: IPOAnalysis) -> str:
    gmp = _rupees(analysis.gmp)
    if analysis.gmp_percent is not None:
        gmp += f" ({_number(analysis.gmp_percent, '%')})"
    cells = [
        ("GMP", gmp),
        ("Issue price", _rupees(analysis.issue_price)),
        ("Closes", _date(analysis.close_date)),
        ("Subscription", _number(analysis.subscription, "x")),
        ("P/E", _number(analysis.pe)),
        ("Issue size", _number(analysis.issue_size_cr, " cr")),
    ]
    rows = []
    for start in (0, 3):
        tds = "".join(
            f'<td style="padding:8px 10px;border-top:1px solid {_BORDER};width:33%;'
            f'vertical-align:top;"><div style="font-size:11px;color:{_MUTED};">{_e(label)}</div>'
            f'<div style="font-size:14px;font-weight:600;color:{_INK};">{_e(value)}</div></td>'
            for label, value in cells[start : start + 3]
        )
        rows.append(f"<tr>{tds}</tr>")
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="margin-top:12px;border-bottom:1px solid {_BORDER};">{"".join(rows)}</table>'
    )


def _line(label: str, text: str, color: str = _INK) -> str:
    return (
        f'<p style="margin:8px 0 0;font-size:13px;line-height:1.5;color:{_INK};">'
        f'<strong style="color:{color};">{_e(label)}:</strong> {_e(text)}</p>'
    )


def _card(
    analysis: IPOAnalysis,
    digest: ResearchDigest | None,
    links: list[SourceLink],
    with_research: bool,
) -> str:
    strong, avoid = _VERDICT["Strong"][0], _VERDICT["Avoid"][0]
    pills = _pill("Rule-based", analysis.verdict, f"{analysis.score:.1f} / 100")
    has_ai = digest is not None and digest.has_result
    if with_research:
        if has_ai:
            detail = f"{digest.confidence or 'unknown'} confidence"
            if digest.disputes:
                detail += f", {digest.disputes} dispute{'s' if digest.disputes != 1 else ''}"
        else:
            detail = "No AI research yet"
        pills += '<td style="width:8px;"></td>' + _pill(
            "AI research", digest.verdict if has_ai else None, detail
        )

    body = [
        f'<h2 style="margin:0;font-size:18px;color:{_INK};">{_e(analysis.name)}</h2>',
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="margin-top:10px;"><tr>{pills}</tr></table>',
        _metrics(analysis),
    ]
    if analysis.strengths:
        body.append(_line("Strength", analysis.strengths[0], strong))
    if analysis.risks:
        body.append(_line("Risk", analysis.risks[0], avoid))
    if has_ai:
        if digest.conclusion:
            body.append(_line("AI view", _snippet(digest.conclusion)))
        if digest.risks:
            body.append(_line("AI top risk", _snippet(digest.risks[0], 220), avoid))
        body.append(
            f'<p style="margin:6px 0 0;font-size:11px;color:{_MUTED};">Researched '
            f"{_e(format_research_time(digest.researched_at))}; web facts are unverified.</p>"
        )
    if digest is not None and digest.note:
        body.append(
            f'<p style="margin:6px 0 0;font-size:12px;color:{_MUTED};">{_e(digest.note)}</p>'
        )

    sources = [
        f'<a href="{_e(link.url)}" style="color:{_LINK};text-decoration:none;">{_e(link.label)}</a>'
        for link in links
    ]
    if has_ai and digest.sources:
        count = len(digest.sources)
        sources.append(f"{count} AI research source{'s' if count != 1 else ''} (in the PDF)")
    if sources:
        body.append(
            f'<p style="margin:10px 0 0;font-size:12px;color:{_MUTED};">Sources: '
            + " · ".join(sources)
            + "</p>"
        )

    return (
        f'<tr><td style="padding:20px 24px;border-top:1px solid {_BORDER};">'
        + "".join(body)
        + "</td></tr>"
    )


def build_html_summary(
    analyses: list[IPOAnalysis],
    *,
    min_gmp_percent: float,
    include_upcoming: bool = False,
    generated_at: datetime | None = None,
    research: Mapping[int, ResearchDigest] | None = None,
    sources: Mapping[int, list[SourceLink]] | None = None,
    unsubscribe_url: str | None = None,
) -> str:
    """Return the HTML email body (pair it with ``build_text_summary``)."""

    moment = (generated_at or datetime.now(IST)).astimezone(IST)
    count = len(analyses)
    if analyses:
        names = ", ".join(f"{a.name} ({a.verdict})" for a in analyses[:3])
        preheader = f"{count} IPO{'s' if count != 1 else ''} passed today's screen: {names}"
        verdicts = " · ".join(
            f"{sum(1 for a in analyses if a.verdict == v)} {v}" for v in ("Strong", "Watch", "Avoid")
        )
        overview = f"{count} candidate{'s' if count != 1 else ''} · {verdicts}"
        cards = "".join(
            _card(
                analysis,
                (research or {}).get(analysis.ipo_id),
                list((sources or {}).get(analysis.ipo_id, [])),
                research is not None,
            )
            for analysis in analyses
        )
    else:
        preheader = overview = "No IPOs matched today's screen."
        cards = (
            f'<tr><td style="padding:20px 24px;border-top:1px solid {_BORDER};'
            f'font-size:14px;color:{_INK};">No IPOs matched the current criteria. '
            "Run a scrape first, or lower the minimum GMP percentage.</td></tr>"
        )

    screen = (
        f"Screen: latest GMP at least {min_gmp_percent:g}%, upcoming IPOs "
        f"{'included' if include_upcoming else 'excluded'}"
    )
    header = (
        f'<div style="font-size:13px;color:{_MUTED};">'
        f"{_e(moment.strftime('%d %b %Y, %H:%M IST'))} · {_e(screen)}</div>"
        f'<div style="margin-top:12px;font-size:14px;font-weight:600;color:{_INK};">'
        f"{_e(overview)}</div>"
    )
    footer = (
        "The attached PDF has the full score breakdown, checklist, AI research and "
        "every source."
    )
    if unsubscribe_url:
        footer += (
            "<br>You get this because you subscribed on IPO Checker. "
            f'<a href="{_e(unsubscribe_url)}" style="color:{_LINK};">Unsubscribe</a>'
        )
    return page("Daily IPO report", preheader=preheader, header=header, rows=cards, footer=footer)


def page(title: str, *, preheader: str, header: str, rows: str, footer: str) -> str:
    """Wrap pre-escaped ``header``/``rows``/``footer`` HTML in the email frame.

    ``rows`` is a run of ``<tr>`` elements; the disclaimer is always appended.
    """

    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(title)}</title></head>
<body style="margin:0;padding:0;background:#F2F4F7;font-family:{_FONT};">
<div style="display:none;max-height:0;overflow:hidden;">{_e(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F2F4F7;">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
 style="max-width:600px;background:#FFFFFF;border:1px solid {_BORDER};border-radius:12px;
 border-top:4px solid {_LINK};">
<tr><td style="padding:24px 24px 18px;">
<div style="font-size:12px;font-weight:600;color:{_LINK};letter-spacing:.04em;">IPO CHECKER</div>
<h1 style="margin:6px 0 4px;font-size:22px;color:{_INK};">{_e(title)}</h1>
{header}
</td></tr>
{rows}
<tr><td style="padding:18px 24px;border-top:1px solid {_BORDER};background:#FCFCFD;
 border-radius:0 0 12px 12px;font-size:12px;line-height:1.5;color:{_MUTED};">
{footer}<br>
Grey-market premium is unofficial and can change at any time. This is for personal
research, not investment advice.
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>
"""


__all__ = ["build_html_summary", "page"]
