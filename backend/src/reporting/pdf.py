"""PDF report generation using ReportLab.

Layout: page 1 is the overview (verdict counts and a summary table); every
IPO then gets its own page with verdict tiles (rule-based score and, when
research digests are passed, the AI view beside it), key numbers, the
rule-based strengths/risks/gaps, the AI research block, the score breakdown,
the checklist and a "Sources" block of clickable links (scraped market-data
pages and the web sources the AI research cited). Every page carries a small
header and a footer with the page number.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src import config
from src.models.analysis import ChecklistItem, IPOAnalysis, ScoreFactor
from src.reporting.sources import SourceLink
from src.reporting.summary import (
    _number,
    _rupees,
    format_research_time,
    research_headline,
)
from src.utils.parsing import IST

if TYPE_CHECKING:
    from src.research.digest import ResearchDigest

_INK = colors.HexColor("#101828")
_MUTED = colors.HexColor("#667085")
_BORDER = colors.HexColor("#EAECF0")
_HEADER_BG = colors.HexColor("#F2F4F7")
_BAND = colors.HexColor("#FCFCFD")
_BRAND = colors.HexColor("#1D4ED8")
_LINK = "#1D4ED8"

_VERDICT_COLORS = {
    "Strong": colors.HexColor("#1B7F3B"),
    "Watch": colors.HexColor("#B54708"),
    "Avoid": colors.HexColor("#B42318"),
}
_VERDICT_TINTS = {
    "Strong": colors.HexColor("#ECFDF3"),
    "Watch": colors.HexColor("#FFFAEB"),
    "Avoid": colors.HexColor("#FEF3F2"),
}
_STATUS_COLORS = {
    "pass": colors.HexColor("#1B7F3B"),
    "warn": colors.HexColor("#B54708"),
    "fail": colors.HexColor("#B42318"),
    "manual": _MUTED,
}

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 16 * mm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN

# Research runs can cite dozens of pages; the PDF lists the first ones.
MAX_RESEARCH_SOURCES = 30


def _safe(value: object) -> str:
    """Escape ReportLab paragraph markup; Helvetica has no rupee glyph."""

    return escape(str(value).replace("₹", "Rs. "))


def _date(value: str | None) -> str:
    """'2026-11-23' -> '23 Nov 2026' (other values pass through)."""

    if not value:
        return "n/a"
    try:
        return date.fromisoformat(value).strftime("%d %b %Y")
    except ValueError:
        return value


def _style(name: str, **kwargs) -> ParagraphStyle:
    values = {"fontName": "Helvetica", "fontSize": 9, "leading": 12, "textColor": _INK}
    values.update(kwargs)
    return ParagraphStyle(name, **values)


def _styles() -> dict[str, ParagraphStyle]:
    return {
        "title": _style("Title", fontName="Helvetica-Bold", fontSize=22, leading=26),
        "subtitle": _style("Subtitle", fontSize=9.5, leading=13, textColor=_MUTED),
        "ipo": _style("IPO", fontName="Helvetica-Bold", fontSize=18, leading=22),
        "h2": _style(
            "H2", fontName="Helvetica-Bold", fontSize=11.5, leading=14,
            spaceBefore=12, spaceAfter=5, keepWithNext=1,
        ),
        "body": _style("Body", fontSize=9, leading=13, spaceAfter=3),
        "small": _style("Small", fontSize=7.5, leading=10, textColor=_MUTED),
        "label": _style("Label", fontSize=7, leading=9, textColor=_MUTED),
        "value": _style("Value", fontName="Helvetica-Bold", fontSize=11, leading=14),
        "tile_value": _style("TileValue", fontName="Helvetica-Bold", fontSize=15, leading=19),
        "cell": _style("Cell", fontSize=8, leading=10.5),
        "cell_bold": _style("CellBold", fontName="Helvetica-Bold", fontSize=8, leading=10.5),
        "th": _style("TH", fontName="Helvetica-Bold", fontSize=7.5, leading=10, textColor=_MUTED),
        "link": _style("Link", fontSize=8, leading=10.5),
        "url": _style(
            "Url", fontSize=6.5, leading=8.5, spaceAfter=3, textColor=_MUTED,
            wordWrap="CJK",  # long URLs have no spaces; let them break anywhere
        ),
    }


def _p(value: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(_safe(value), style)


def _colored(value: object, style: ParagraphStyle, color: colors.Color) -> Paragraph:
    return Paragraph(_safe(value), ParagraphStyle(f"{style.name}-c", parent=style, textColor=color))


def _bullets(values: list[str], style: ParagraphStyle) -> ListFlowable:
    return ListFlowable(
        [_p(value, style) for value in values],
        bulletType="bullet",
        start="•",
        bulletFontSize=8,
        leftIndent=10,
    )


def _data_table(data: list[list], widths_mm: list[float], *, total_row: bool = False) -> Table:
    """Full-width table: muted header row, light row bands, hairline rules."""

    table = Table(data, colWidths=[w * mm for w in widths_mm], repeatRows=1, hAlign="LEFT")
    commands: list[tuple] = [
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _BAND]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, _BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if total_row:
        commands += [
            ("BACKGROUND", (0, -1), (-1, -1), _HEADER_BG),
            ("LINEABOVE", (0, -1), (-1, -1), 0.8, _INK),
        ]
    table.setStyle(TableStyle(commands))
    return table


def _tiles(cells: list[list], backgrounds: list[colors.Color], height_pad: float = 7) -> Table:
    """A row of tinted tiles separated by white gutters."""

    width = CONTENT_WIDTH / len(cells)
    table = Table([cells], colWidths=[width] * len(cells), hAlign="LEFT")
    commands: list[tuple] = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), height_pad),
        ("BOTTOMPADDING", (0, 0), (-1, -1), height_pad),
        ("LINEAFTER", (0, 0), (-2, -1), 4, colors.white),
    ]
    commands += [("BACKGROUND", (i, 0), (i, 0), bg) for i, bg in enumerate(backgrounds)]
    table.setStyle(TableStyle(commands))
    return table


# --- Overview page -------------------------------------------------------------


def _count_tiles(analyses: list[IPOAnalysis], styles: dict) -> Table:
    counts = [("Candidates", str(len(analyses)), _INK, _HEADER_BG)]
    for verdict in ("Strong", "Watch", "Avoid"):
        total = sum(1 for a in analyses if a.verdict == verdict)
        counts.append((verdict, str(total), _VERDICT_COLORS[verdict], _VERDICT_TINTS[verdict]))
    return _tiles(
        [[_p(label, styles["label"]), _colored(value, styles["tile_value"], color)]
         for label, value, color, _ in counts],
        [bg for *_, bg in counts],
    )


def _verdict_text(verdict: str | None, style: ParagraphStyle) -> Paragraph:
    return _colored(verdict or "n/a", style, _VERDICT_COLORS.get(verdict or "", _MUTED))


def _summary_table(
    analyses: list[IPOAnalysis],
    styles: dict[str, ParagraphStyle],
    research: Mapping[int, ResearchDigest] | None = None,
) -> Table:
    header = ["#", "IPO", "Rule-based", "Score", "GMP %", "Issue price", "Closes"]
    widths = [8, 52, 22, 15, 18, 24, 22]
    if research is not None:
        header.append("AI view")
        widths = [8, 44, 21, 14, 17, 23, 22, 17]
    widths[1] += CONTENT_WIDTH / mm - sum(widths)  # the name column takes the rest

    data: list[list] = [[_p(label, styles["th"]) for label in header]]
    for index, analysis in enumerate(analyses, start=1):
        row = [
            _p(index, styles["cell"]),
            _p(analysis.name, styles["cell_bold"]),
            _verdict_text(analysis.verdict, styles["cell_bold"]),
            _p(f"{analysis.score:.1f}", styles["cell"]),
            _p(_number(analysis.gmp_percent, "%"), styles["cell"]),
            _p(_rupees(analysis.issue_price), styles["cell"]),
            _p(_date(analysis.close_date), styles["cell"]),
        ]
        if research is not None:
            digest = research.get(analysis.ipo_id)
            has = digest is not None and digest.has_result
            row.append(_verdict_text(digest.verdict if has else None, styles["cell_bold"]))
        data.append(row)
    return _data_table(data, widths)


# --- Per-IPO page --------------------------------------------------------------


def _verdict_tiles(
    analysis: IPOAnalysis,
    digest: ResearchDigest | None,
    styles: dict,
    with_research: bool,
) -> Table:
    cells = [[
        _p("RULE-BASED SCORE", styles["label"]),
        _verdict_text(analysis.verdict, styles["tile_value"]),
        _p(f"{analysis.score:.1f} / 100", styles["cell"]),
    ]]
    backgrounds = [_VERDICT_TINTS.get(analysis.verdict, _HEADER_BG)]
    if with_research:
        if digest is not None and digest.has_result:
            detail = research_headline(digest).split("(", 1)[-1].rstrip(")")
            cells.append([
                _p("AI RESEARCH VIEW", styles["label"]),
                _verdict_text(digest.verdict, styles["tile_value"]),
                _p(detail, styles["cell"]),
            ])
            backgrounds.append(_VERDICT_TINTS.get(digest.verdict or "", _HEADER_BG))
        else:
            cells.append([
                _p("AI RESEARCH VIEW", styles["label"]),
                _p("Not available", styles["tile_value"]),
                _p((digest.note if digest else None) or "No AI research yet.", styles["cell"]),
            ])
            backgrounds.append(_HEADER_BG)
    return _tiles(cells, backgrounds)


def _metric_grid(analysis: IPOAnalysis, styles: dict) -> Table:
    gmp_percent = _number(analysis.gmp_percent, "%")
    if analysis.gmp_percent_derived:
        gmp_percent += " (derived)"
    metrics = [
        ("GMP", _rupees(analysis.gmp)),
        ("GMP %", gmp_percent),
        ("Issue price", _rupees(analysis.issue_price)),
        ("Closes", _date(analysis.close_date)),
        ("Subscription", _number(analysis.subscription, "x")),
        ("P/E", _number(analysis.pe)),
        ("Issue size", _number(analysis.issue_size_cr, " cr")),
        ("Score", f"{analysis.score:.1f} / 100"),
    ]
    cells = [[_p(label, styles["label"]), _p(value, styles["value"])] for label, value in metrics]
    width = CONTENT_WIDTH / 4
    table = Table([cells[:4], cells[4:]], colWidths=[width] * 4, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _BAND),
        ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, _BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _highlights_table(analysis: IPOAnalysis, styles: dict) -> Table:
    columns = [
        ("Strengths", analysis.strengths, _VERDICT_COLORS["Strong"]),
        ("Risks", analysis.risks, _VERDICT_COLORS["Avoid"]),
        ("Data gaps", analysis.data_gaps, _MUTED),
    ]
    header = [_colored(title, styles["cell_bold"], color) for title, _, color in columns]
    body = [
        _bullets(values, styles["cell"]) if values else _p("None.", styles["cell"])
        for _, values, _ in columns
    ]
    width = CONTENT_WIDTH / mm / 3
    return _data_table([header, body], [width] * 3)


def _factors_table(factors: list[ScoreFactor], styles: dict, total: float) -> Table:
    data: list[list] = [[
        _p(label, styles["th"]) for label in ("Factor", "Weight", "Score", "Weighted", "Explanation")
    ]]
    for factor in factors:
        data.append([
            _p(factor.label, styles["cell_bold"]),
            _p(f"{factor.weight * 100:.0f}%", styles["cell"]),
            _p(f"{factor.score:.1f}", styles["cell"]),
            _p(f"{factor.weighted_score:.2f}", styles["cell"]),
            _p(factor.explanation, styles["cell"]),
        ])
    data.append([
        _p("Total", styles["cell_bold"]), _p("", styles["cell"]), _p("", styles["cell"]),
        _p(f"{total:.1f}", styles["cell_bold"]), _p("out of 100", styles["cell"]),
    ])
    return _data_table(data, [30, 16, 16, 18, 98], total_row=True)


def _checklist_table(checklist: list[ChecklistItem], styles: dict) -> Table:
    data: list[list] = [[_p(label, styles["th"]) for label in ("Check", "Status", "Detail")]]
    for item in checklist:
        data.append([
            _p(item.label, styles["cell_bold"]),
            _colored(item.status.upper(), styles["cell_bold"],
                     _STATUS_COLORS.get(item.status, _INK)),
            _p(item.detail, styles["cell"]),
        ])
    return _data_table(data, [42, 20, 116])


def _research_story(digest: ResearchDigest | None, styles: dict) -> list:
    story: list = [
        _p("AI research", styles["h2"]),
        _p("Shown beside the rule-based score, never instead of it.", styles["small"]),
        Spacer(1, 2 * mm),
    ]
    if digest is None or not digest.has_result:
        note = digest.note if digest is not None else None
        story.append(_p(note or "No AI research yet.", styles["body"]))
        return story

    if digest.conclusion:
        story.append(_p(digest.conclusion, styles["body"]))
    columns = [
        ("Strengths", digest.strengths[:3], _VERDICT_COLORS["Strong"]),
        ("Risks", digest.risks[:3], _VERDICT_COLORS["Avoid"]),
    ]
    if any(values for _, values, _ in columns):
        story.append(Spacer(1, 2 * mm))
        header = [_colored(title, styles["cell_bold"], color) for title, _, color in columns]
        body = [
            _bullets(values, styles["cell"]) if values else _p("None.", styles["cell"])
            for _, values, _ in columns
        ]
        half = CONTENT_WIDTH / mm / 2
        story.append(_data_table([header, body], [half, half]))
    caveat = (
        f"Researched {format_research_time(digest.researched_at)}"
        f" (run #{digest.run_id}). Facts were gathered from the web and are "
        "unverified until checked against the RHP."
    )
    if digest.note:
        caveat = f"{digest.note} {caveat}"
    story += [Spacer(1, 2 * mm), _p(caveat, styles["small"])]
    return story


def _link_paragraphs(link: SourceLink, styles: dict[str, ParagraphStyle]) -> list:
    href = escape(link.url, {'"': "&quot;"})
    label = f'<link href="{href}" color="{_LINK}">{_safe(link.label)}</link>'
    if link.kind in {"official", "exchange"}:  # call out primary sources only
        label += f' <font color="#667085" size="7">{_safe(link.kind.upper())}</font>'
    url = f'<link href="{href}" color="#667085">{_safe(link.url)}</link>'
    return [Paragraph(label, styles["link"]), Paragraph(url, styles["url"])]


def _sources_story(
    market: list[SourceLink],
    digest: ResearchDigest | None,
    styles: dict[str, ParagraphStyle],
) -> list:
    research = list(digest.sources) if digest is not None and digest.has_result else []
    if not market and not research:
        return []

    story: list = [_p("Sources", styles["h2"])]
    if market:
        story.append(_p("Market data (GMP, price, dates, subscription)", styles["label"]))
        story.append(Spacer(1, 1 * mm))
        for link in market:
            story.extend(_link_paragraphs(link, styles))
    if research:
        story.append(Spacer(1, 2 * mm))
        story.append(_p(
            f"Web sources cited by AI research ({len(research)}, run #{digest.run_id})",
            styles["label"],
        ))
        story.append(Spacer(1, 1 * mm))
        for link in research[:MAX_RESEARCH_SOURCES]:
            story.extend(_link_paragraphs(link, styles))
        hidden = len(research) - MAX_RESEARCH_SOURCES
        if hidden > 0:
            story.append(_p(
                f"+ {hidden} more; see the IPO's AI research tab in the app.", styles["small"]
            ))
    return story


def _analysis_story(
    analysis: IPOAnalysis,
    styles: dict[str, ParagraphStyle],
    research: Mapping[int, ResearchDigest] | None = None,
    sources: Mapping[int, list[SourceLink]] | None = None,
) -> list:
    digest = (research or {}).get(analysis.ipo_id)
    story: list = [
        _p(analysis.name, styles["ipo"]),
        Spacer(1, 4 * mm),
        _verdict_tiles(analysis, digest, styles, research is not None),
        Spacer(1, 3 * mm),
        _metric_grid(analysis, styles),
        _p("Rule-based view", styles["h2"]),
        _highlights_table(analysis, styles),
    ]
    if research is not None:
        story.extend(_research_story(digest, styles))
    story += [
        _p("Score breakdown", styles["h2"]),
        _factors_table(analysis.factors, styles, analysis.score),
        _p("Checklist", styles["h2"]),
        _checklist_table(analysis.checklist, styles),
    ]
    story.extend(
        _sources_story(list((sources or {}).get(analysis.ipo_id, [])), digest, styles)
    )
    return story


def _page_decorator(title: str, moment: datetime):
    """Header (title, date) and footer (disclaimer, page number) on every page."""

    def draw(canvas, document) -> None:
        canvas.saveState()
        canvas.setFillColor(_BRAND)
        canvas.rect(0, PAGE_HEIGHT - 3 * mm, PAGE_WIDTH, 3 * mm, stroke=0, fill=1)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(_INK)
        canvas.drawString(MARGIN, PAGE_HEIGHT - 10 * mm, title)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(_MUTED)
        canvas.drawRightString(
            PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 10 * mm, moment.strftime("%d %b %Y, %H:%M IST")
        )
        canvas.setStrokeColor(_BORDER)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, 12 * mm, PAGE_WIDTH - MARGIN, 12 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(
            MARGIN, 8 * mm, "Personal research, not investment advice. GMP is unofficial."
        )
        canvas.drawRightString(PAGE_WIDTH - MARGIN, 8 * mm, f"Page {document.page}")
        canvas.restoreState()

    return draw


def generate_report(
    analyses: list[IPOAnalysis],
    *,
    output_path: str | Path | None = None,
    title: str = "IPO Checker Report",
    min_gmp_percent: float | None = None,
    include_upcoming: bool = False,
    generated_at: datetime | None = None,
    research: Mapping[int, ResearchDigest] | None = None,
    sources: Mapping[int, list[SourceLink]] | None = None,
) -> Path:
    """Write a PDF report and return its path.

    ``research`` (from :mod:`src.research.digest`) adds an AI view column and
    an "AI research" block per IPO. ``sources`` (from
    :func:`src.reporting.sources.collect_sources`) lists the market-data pages
    per IPO; research sources come from the digests.

    When ``output_path`` is omitted, the file is written to
    ``REPORT_OUTPUT_DIR`` with a timestamped name.
    """

    moment = (generated_at or datetime.now(IST)).astimezone(IST)

    if output_path is None:
        filename = f"ipo_report_{moment.strftime('%Y%m%d_%H%M%S')}.pdf"
        destination = config.REPORT_OUTPUT_DIR / filename
    else:
        destination = Path(output_path)
        if not destination.is_absolute():
            destination = config.REPO_ROOT / destination

    destination.parent.mkdir(parents=True, exist_ok=True)

    styles = _styles()
    subtitle = f"Generated {moment.strftime('%d %b %Y, %H:%M IST')}"
    if min_gmp_percent is not None:
        subtitle += (
            f"  ·  Screen: latest GMP at least {min_gmp_percent:g}%, upcoming IPOs "
            f"{'included' if include_upcoming else 'excluded'}"
        )
    story: list = [
        _p(title, styles["title"]),
        Spacer(1, 1 * mm),
        _p(subtitle, styles["subtitle"]),
        Spacer(1, 6 * mm),
    ]

    disclaimer = _p(
        "Grey-market premium is unofficial, speculative and can vanish "
        "before listing. This report is for personal research and is not "
        "investment advice. Always verify with the official RHP and the "
        "NSE/BSE filings.",
        styles["small"],
    )
    if not analyses:
        story += [
            _p("No IPOs matched the current criteria in this run.", styles["body"]),
            _p("Run a scrape first, or lower the minimum GMP percentage.", styles["small"]),
            Spacer(1, 6 * mm),
            disclaimer,
        ]
    else:
        story += [
            _count_tiles(analyses, styles),
            _p("Summary", styles["h2"]),
            _summary_table(analyses, styles, research),
            Spacer(1, 3 * mm),
            _p(
                "Each IPO has its own page with the score breakdown, checklist, "
                + ("AI research " if research is not None else "")
                + "and sources.",
                styles["small"],
            ),
            Spacer(1, 6 * mm),
            disclaimer,
        ]
        for analysis in analyses:
            story.append(PageBreak())
            story.extend(_analysis_story(analysis, styles, research, sources))

    document = SimpleDocTemplate(
        str(destination),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=title,
        author="IPO Checker",
    )
    decorate = _page_decorator(title, moment)
    document.build(story, onFirstPage=decorate, onLaterPages=decorate)

    return destination
