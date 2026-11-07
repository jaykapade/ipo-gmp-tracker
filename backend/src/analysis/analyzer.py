"""Build a deterministic :class:`IPOAnalysis` from a candidate."""

from __future__ import annotations

from datetime import UTC, date, datetime

from src.analysis.checklist import build_checklist
from src.analysis.filters import Candidate
from src.analysis.metrics import Metrics, compute_metrics
from src.analysis.scoring import overall_score, score_metrics, verdict_for
from src.models.analysis import IPOAnalysis


def _narrative(
    metrics: Metrics,
) -> tuple[list[str], list[str], list[str]]:
    strengths: list[str] = []
    risks: list[str] = []
    gaps: list[str] = []

    if metrics.gmp_percent is not None and metrics.gmp_percent >= 30:
        strengths.append(
            f"GMP of {metrics.gmp_percent:.1f}% is comfortably above the 20% filter."
        )
    if metrics.gmp_trend_label == "Rising":
        strengths.append(f"GMP is rising ({metrics.gmp_trend:+.1f} points).")
    if metrics.subscription is not None and metrics.subscription >= 5:
        strengths.append(f"Strong subscription of {metrics.subscription:.2f}x.")
    if metrics.pe is not None and metrics.pe <= 20:
        strengths.append(f"Reasonable post-issue P/E of {metrics.pe:.1f}.")
    if metrics.issue_size_cr is not None and metrics.issue_size_cr >= 100:
        strengths.append(
            f"Meaningful issue size of ₹{metrics.issue_size_cr:.1f} crore."
        )

    if metrics.gmp_percent is not None and metrics.gmp_percent <= 0:
        risks.append("GMP is zero or negative, so listing gains may not materialise.")
    if metrics.gmp_trend_label == "Falling":
        risks.append(f"GMP is falling ({metrics.gmp_trend:+.1f} points).")
    if metrics.pe is not None and metrics.pe > 40:
        risks.append(f"Post-issue P/E of {metrics.pe:.1f} is high.")
    if metrics.subscription is not None and metrics.subscription < 1:
        risks.append(f"Subscription is only {metrics.subscription:.2f}x.")
    if metrics.issue_size_cr is not None and metrics.issue_size_cr < 10:
        risks.append(
            f"Small issue size of ₹{metrics.issue_size_cr:.1f} crore can be volatile."
        )
    if metrics.days_to_close is not None and 0 <= metrics.days_to_close <= 1:
        risks.append("Bidding closes within one day; there is little time to verify.")
    if metrics.source_spread_percent is not None and metrics.source_spread_percent > 10:
        risks.append(
            "Sources disagree on GMP by "
            f"{metrics.source_spread_percent:.1f} percentage points."
        )

    if metrics.pe is None:
        gaps.append("P/E is not available; valuation needs manual review.")
    if metrics.subscription is None:
        gaps.append("Subscription data is not available.")
    if metrics.issue_size_cr is None:
        gaps.append("Issue size is not available as a number.")
    if metrics.history_points < 2:
        gaps.append("Not enough GMP history to judge a trend.")
    if metrics.source_count < 2:
        gaps.append("Only one source has reported GMP so far.")
    gaps.append("RHP financials, objects of issue and risk factors are not ingested.")

    if not strengths:
        strengths.append("No clear numeric strength stands out yet.")
    if not risks:
        risks.append("No major numeric risk flags were detected.")

    return strengths, risks, gaps


def analyze_candidate(
    candidate: Candidate,
    *,
    today: date | None = None,
) -> IPOAnalysis:
    """Analyse one candidate using only deterministic, stored data."""

    metrics = compute_metrics(candidate, today=today)
    factors = score_metrics(metrics)
    score = overall_score(factors)
    strengths, risks, gaps = _narrative(metrics)

    ipo = candidate.ipo
    close_date = candidate.close_date or ipo.get("close_date")

    return IPOAnalysis(
        ipo_id=candidate.ipo_id,
        name=candidate.name,
        score=score,
        verdict=verdict_for(score),
        gmp=metrics.gmp,
        gmp_percent=metrics.gmp_percent,
        gmp_percent_derived=metrics.gmp_percent_derived,
        issue_price=metrics.issue_price,
        issue_size_cr=metrics.issue_size_cr,
        subscription=metrics.subscription,
        pe=metrics.pe,
        close_date=close_date.isoformat() if hasattr(close_date, "isoformat") else close_date,
        factors=factors,
        checklist=build_checklist(metrics),
        strengths=strengths,
        risks=risks,
        data_gaps=gaps,
        generated_at=datetime.now(UTC).isoformat(),
    )


def analyze_candidates(
    candidates: list[Candidate],
    *,
    today: date | None = None,
) -> list[IPOAnalysis]:
    return [analyze_candidate(candidate, today=today) for candidate in candidates]
