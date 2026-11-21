"""PDF report generation using ReportLab.

The report mirrors the deterministic analysis payload: scores, factor
weights, checklist results and explicit data gaps. When research digests are
passed, each IPO also gets a clearly labelled "AI research" block (verdict,
confidence, strengths, risks) shown beside -- never instead of -- the
rule-based score.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src import config
from src.models.analysis import ChecklistItem, IPOAnalysis, ScoreFactor
from src.reporting.summary import format_research_time, research_headline
from src.utils.parsing import IST

if TYPE_CHECKING:
    from src.research.digest import ResearchDigest

_VERDICT_COLORS = {
    "Strong": colors.HexColor("#1B7F3B"),
    "Watch": colors.HexColor("#B7791F"),
    "Avoid": colors.HexColor("#B42318"),
}

_STATUS_COLORS = {
    "pass": colors.HexColor("#1B7F3B"),
    "warn": colors.HexColor("#B7791F"),
    "fail": colors.HexColor("#B42318"),
    "manual": colors.HexColor("#475467"),
}

_HEADER_BG = colors.HexColor("#EEF2F6")
_BORDER = colors.HexColor("#D0D5DD")
_MUTED = colors.HexColor("#475467")


def _safe(value: object) -> str:
    """Escape ReportLab paragraph markup and drop unsupported glyphs."""

    text = str(value).replace("₹", "Rs. ")
    return escape(text)


def _number(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    return f"{value:,.2f}{suffix}"


def _rupees(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"Rs {value:,.2f}"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            spaceAfter=4,
            alignment=0,
            textColor=colors.HexColor("#101828"),
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=_MUTED,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12.5,
            leading=15,
            spaceBefore=10,
            spaceAfter=4,
            textColor=colors.HexColor("#101828"),
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            spaceAfter=3,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10.5,
            textColor=_MUTED,
        ),
        "cell": ParagraphStyle(
            "Cell",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.5,
        ),
        "cell_bold": ParagraphStyle(
            "CellBold",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
        ),
        "verdict": ParagraphStyle(
            "Verdict",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
        ),
    }


def _paragraph(value: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(_safe(value), style)


def _base_table_style(header: bool = True) -> list[tuple]:
    commands: list[tuple] = [
        ("GRID", (0, 0), (-1, -1), 0.4, _BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    return commands


def _verdict_cell(
    verdict: str | None, styles: dict[str, ParagraphStyle]
) -> Paragraph:
    return Paragraph(
        _safe(verdict or "n/a"),
        ParagraphStyle(
            "VerdictCell",
            parent=styles["cell_bold"],
            textColor=_VERDICT_COLORS.get(verdict or "", _MUTED),
        ),
    )


def _summary_table(
    analyses: list[IPOAnalysis],
    styles: dict[str, ParagraphStyle],
    research: Mapping[int, ResearchDigest] | None = None,
) -> Table:
    header = ["IPO", "Verdict", "Score", "GMP %", "Issue", "Closes"]
    widths = [52, 20, 14, 18, 24, 22]
    if research is not None:
        header.append("AI view")
        widths = [46, 18, 13, 16, 22, 20, 26]

    data: list[list[Paragraph]] = [
        [_paragraph(label, styles["cell_bold"]) for label in header]
    ]

    for analysis in analyses:
        row = [
            _paragraph(analysis.name, styles["cell"]),
            _verdict_cell(analysis.verdict, styles),
            _paragraph(f"{analysis.score:.1f}", styles["cell"]),
            _paragraph(_number(analysis.gmp_percent, "%"), styles["cell"]),
            _paragraph(_rupees(analysis.issue_price), styles["cell"]),
            _paragraph(analysis.close_date or "n/a", styles["cell"]),
        ]
        if research is not None:
            digest = research.get(analysis.ipo_id)
            if digest is not None and digest.has_result:
                row.append(_verdict_cell(digest.verdict, styles))
            else:
                row.append(_paragraph("n/a", styles["cell"]))
        data.append(row)

    table = Table(
        data,
        colWidths=[width * mm for width in widths],
        repeatRows=1,
    )
    table.setStyle(TableStyle(_base_table_style()))
    return table


def _meta_table(
    analysis: IPOAnalysis,
    styles: dict[str, ParagraphStyle],
) -> Table:
    rows = [
        ("GMP", _rupees(analysis.gmp)),
        (
            "GMP %",
            _number(analysis.gmp_percent, "%")
            + (" (derived)" if analysis.gmp_percent_derived else ""),
        ),
        ("Issue price", _rupees(analysis.issue_price)),
        ("Issue size", _number(analysis.issue_size_cr, " cr")),
        ("Subscription", _number(analysis.subscription, "x")),
        ("P/E", _number(analysis.pe)),
        ("Closes", analysis.close_date or "n/a"),
    ]

    data = [
        [
            _paragraph(label, styles["cell_bold"]),
            _paragraph(value, styles["cell"]),
            _paragraph("", styles["cell"]),
            _paragraph("", styles["cell"]),
        ]
        for label, value in rows
    ]

    table = Table(
        data,
        colWidths=[24 * mm, 40 * mm, 24 * mm, 40 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, _BORDER),
                ("BACKGROUND", (0, 0), (0, -1), _HEADER_BG),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _factors_table(
    factors: list[ScoreFactor],
    styles: dict[str, ParagraphStyle],
) -> Table:
    data: list[list[Paragraph]] = [
        [
            _paragraph("Factor", styles["cell_bold"]),
            _paragraph("Weight", styles["cell_bold"]),
            _paragraph("Score", styles["cell_bold"]),
            _paragraph("Weighted", styles["cell_bold"]),
            _paragraph("Explanation", styles["cell_bold"]),
        ]
    ]

    for factor in factors:
        data.append(
            [
                _paragraph(factor.label, styles["cell"]),
                _paragraph(f"{factor.weight * 100:.0f}%", styles["cell"]),
                _paragraph(f"{factor.score:.1f}", styles["cell"]),
                _paragraph(f"{factor.weighted_score:.2f}", styles["cell"]),
                _paragraph(factor.explanation, styles["cell"]),
            ]
        )

    table = Table(
        data,
        colWidths=[24 * mm, 14 * mm, 13 * mm, 16 * mm, 91 * mm],
        repeatRows=1,
    )
    table.setStyle(TableStyle(_base_table_style()))
    return table


def _checklist_table(
    checklist: list[ChecklistItem],
    styles: dict[str, ParagraphStyle],
) -> Table:
    data: list[list[Paragraph]] = [
        [
            _paragraph("Check", styles["cell_bold"]),
            _paragraph("Status", styles["cell_bold"]),
            _paragraph("Detail", styles["cell_bold"]),
        ]
    ]

    for item in checklist:
        data.append(
            [
                _paragraph(item.label, styles["cell"]),
                Paragraph(
                    _safe(item.status.upper()),
                    ParagraphStyle(
                        "StatusCell",
                        parent=styles["cell_bold"],
                        textColor=_STATUS_COLORS.get(item.status, colors.black),
                    ),
                ),
                _paragraph(item.detail, styles["cell"]),
            ]
        )

    table = Table(
        data,
        colWidths=[34 * mm, 18 * mm, 106 * mm],
        repeatRows=1,
    )
    table.setStyle(TableStyle(_base_table_style()))
    return table


def _bullet_list(
    heading: str,
    values: list[str],
    styles: dict[str, ParagraphStyle],
) -> list:
    story: list = [_paragraph(heading, styles["h2"])]
    if not values:
        story.append(_paragraph("None.", styles["body"]))
        return story

    for value in values:
        story.append(_paragraph(f"- {value}", styles["body"]))
    return story


def _research_story(
    digest: ResearchDigest | None,
    styles: dict[str, ParagraphStyle],
) -> list:
    story: list = [
        _paragraph("AI research (beside the rule-based score)", styles["h2"])
    ]
    if digest is None or not digest.has_result:
        note = digest.note if digest is not None else None
        story.append(_paragraph(note or "No AI research yet.", styles["body"]))
        return story

    story.append(
        Paragraph(
            _safe(f"AI verdict: {research_headline(digest)}"),
            ParagraphStyle(
                "AIVerdict",
                parent=styles["verdict"],
                textColor=_VERDICT_COLORS.get(digest.verdict or "", colors.black),
            ),
        )
    )
    if digest.conclusion:
        story.append(_paragraph(digest.conclusion, styles["body"]))
    for label, values in (("Strengths", digest.strengths), ("Risks", digest.risks)):
        if values:
            story.append(_paragraph(f"{label}:", styles["cell_bold"]))
            for value in values[:3]:
                story.append(_paragraph(f"- {value}", styles["body"]))
    caveat = (
        f"Researched {format_research_time(digest.researched_at)}"
        f" (run #{digest.run_id}). Facts were gathered from the web and are "
        "unverified until checked against the RHP."
    )
    if digest.note:
        caveat = f"{digest.note} {caveat}"
    story.append(_paragraph(caveat, styles["small"]))
    return story


def _analysis_story(
    analysis: IPOAnalysis,
    styles: dict[str, ParagraphStyle],
    research: Mapping[int, ResearchDigest] | None = None,
) -> list:
    story: list = []

    heading = Paragraph(
        _safe(
            f"{analysis.name} -- {analysis.verdict} "
            f"({analysis.score:.1f}/100)"
        ),
        ParagraphStyle(
            "AnalysisHeading",
            parent=styles["h2"],
            textColor=_VERDICT_COLORS.get(analysis.verdict, colors.black),
        ),
    )
    story.append(KeepTogether([heading, Spacer(1, 2 * mm), _meta_table(analysis, styles)]))
    story.append(Spacer(1, 3 * mm))

    if research is not None:
        story.extend(_research_story(research.get(analysis.ipo_id), styles))
        story.append(Spacer(1, 3 * mm))

    story.append(_paragraph("Score breakdown", styles["h2"]))
    story.append(_factors_table(analysis.factors, styles))
    story.append(Spacer(1, 3 * mm))

    story.append(_paragraph("Checklist", styles["h2"]))
    story.append(_checklist_table(analysis.checklist, styles))
    story.append(Spacer(1, 3 * mm))

    story.extend(_bullet_list("Strengths", analysis.strengths, styles))
    story.extend(_bullet_list("Risks", analysis.risks, styles))
    story.extend(_bullet_list("Data gaps", analysis.data_gaps, styles))

    return story


def generate_report(
    analyses: list[IPOAnalysis],
    *,
    output_path: str | Path | None = None,
    title: str = "IPO Checker Report",
    min_gmp_percent: float | None = None,
    include_upcoming: bool = False,
    generated_at: datetime | None = None,
    research: Mapping[int, ResearchDigest] | None = None,
) -> Path:
    """Write a PDF report and return its path.

    ``research`` (from :mod:`src.research.digest`) adds an AI view column and
    an "AI research" block per IPO.

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
    story: list = [
        _paragraph(title, styles["title"]),
        _paragraph(
            f"Generated: {moment.strftime('%d %b %Y, %H:%M IST')}",
            styles["subtitle"],
        ),
    ]

    if min_gmp_percent is not None:
        story.append(
            _paragraph(
                f"Filter: latest GMP >= {min_gmp_percent:g}% "
                f"| upcoming {'included' if include_upcoming else 'excluded'}",
                styles["subtitle"],
            )
        )

    story.append(Spacer(1, 6 * mm))

    if not analyses:
        story.append(
            _paragraph(
                "No IPOs matched the current criteria in this run.",
                styles["body"],
            )
        )
        story.append(
            _paragraph(
                "Run a scrape first, or lower the minimum GMP percentage.",
                styles["small"],
            )
        )
    else:
        story.append(_paragraph("Summary", styles["h2"]))
        story.append(_summary_table(analyses, styles, research))
        story.append(Spacer(1, 4 * mm))

        for index, analysis in enumerate(analyses):
            if index:
                story.append(Spacer(1, 8 * mm))
            story.extend(_analysis_story(analysis, styles, research))

    story.append(Spacer(1, 8 * mm))
    story.append(
        _paragraph(
            "Grey-market premium is unofficial, speculative and can vanish "
            "before listing. This report is for personal research and is not "
            "investment advice. Always verify with the official RHP and the "
            "NSE/BSE filings.",
            styles["small"],
        )
    )

    document = SimpleDocTemplate(
        str(destination),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=title,
        author="IPO Checker",
    )
    document.build(story)

    return destination
