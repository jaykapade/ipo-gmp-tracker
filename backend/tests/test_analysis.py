"""Tests for metrics, scoring, checklist and the analysis object."""

from datetime import date

from src.analysis.analyzer import analyze_candidate
from src.analysis.checklist import build_checklist
from src.analysis.filters import Candidate
from src.analysis.metrics import compute_metrics
from src.analysis.scoring import WEIGHTS, overall_score, score_metrics, verdict_for


def make_candidate(
    *,
    gmp: float | None = 25.0,
    gmp_percent: float | None = 25.0,
    issue_price: float | None = 100.0,
    pe: float | None = 20.0,
    issue_size_cr: str | None = "50.00",
    subscription: float | None = 3.0,
    history: list[dict] | None = None,
) -> Candidate:
    ipo = {
        "id": 1,
        "name": "Example Ltd",
        "issue_price": issue_price,
        "ipo_size_cr": issue_size_cr,
        "subscription": subscription,
        "pe": pe,
        "close_date": "2026-09-20",
        "status": "Open",
    }
    latest = {
        "gmp": gmp,
        "gmp_percent": gmp_percent,
        "source": "test",
        "recorded_at": "2026-09-15T00:00:00+00:00",
    }
    if history is None:
        history = [
            {
                "gmp": 25.0,
                "gmp_percent": 25.0,
                "source": "test",
                "recorded_at": "2026-09-15T00:00:00+00:00",
            },
            {
                "gmp": 20.0,
                "gmp_percent": 20.0,
                "source": "test",
                "recorded_at": "2026-09-10T00:00:00+00:00",
            },
        ]
    return Candidate(
        ipo=ipo,
        latest_gmp=latest,
        history=history,
        open_date=date(2026, 9, 10),
        close_date=date(2026, 9, 20),
    )


def test_metrics_derive_gmp_percent_when_missing():
    candidate = make_candidate(gmp=25.0, gmp_percent=None)

    metrics = compute_metrics(candidate, today=date(2026, 9, 15))

    assert metrics.gmp_percent == 25.0
    assert metrics.gmp_percent_derived is True
    assert metrics.days_to_close == 5


def test_metrics_compute_trend_and_source_spread():
    history = [
        {
            "gmp": 30.0,
            "gmp_percent": 30.0,
            "source": "source-a",
            "recorded_at": "2026-09-15T00:00:00+00:00",
        },
        {
            "gmp": 20.0,
            "gmp_percent": 20.0,
            "source": "source-b",
            "recorded_at": "2026-09-14T00:00:00+00:00",
        },
    ]
    candidate = make_candidate(gmp=30.0, gmp_percent=30.0, history=history)

    metrics = compute_metrics(candidate, today=date(2026, 9, 15))

    assert metrics.gmp_trend == 10.0
    assert metrics.gmp_trend_label == "Rising"
    assert metrics.source_count == 2
    assert metrics.source_spread_percent == 10.0


def test_weights_sum_to_one():
    assert round(sum(WEIGHTS.values()), 6) == 1.0


def test_scores_are_bounded_and_weighted():
    factors = score_metrics(compute_metrics(make_candidate()))

    assert len(factors) == 5
    assert all(0 <= factor.score <= 100 for factor in factors)
    assert 0 <= overall_score(factors) <= 100


def test_verdict_thresholds():
    assert verdict_for(70) == "Strong"
    assert verdict_for(69.9) == "Watch"
    assert verdict_for(45) == "Watch"
    assert verdict_for(44.9) == "Avoid"


def test_checklist_marks_missing_data_as_manual():
    candidate = make_candidate(pe=None, subscription=None, issue_size_cr=None)
    checklist = build_checklist(compute_metrics(candidate))

    statuses = {item.key: item.status for item in checklist}

    assert statuses["gmp"] == "pass"
    assert statuses["valuation"] == "manual"
    assert statuses["subscription"] == "manual"
    assert statuses["issue_size"] == "manual"
    assert statuses["fundamentals"] == "manual"


def test_analyze_candidate_returns_strong_verdict_for_strong_numbers():
    candidate = make_candidate(
        gmp=50.0,
        gmp_percent=50.0,
        pe=15.0,
        issue_size_cr="100.00",
        subscription=8.0,
    )

    analysis = analyze_candidate(candidate, today=date(2026, 9, 15))

    assert analysis.verdict == "Strong"
    assert analysis.score >= 70
    assert analysis.gmp_percent == 50.0
    assert analysis.strengths
    assert analysis.checklist


def test_analyze_candidate_returns_avoid_for_weak_numbers():
    candidate = make_candidate(
        gmp=5.0,
        gmp_percent=5.0,
        pe=60.0,
        issue_size_cr="5.00",
        subscription=0.5,
    )

    analysis = analyze_candidate(candidate, today=date(2026, 9, 15))

    assert analysis.verdict == "Avoid"
    assert analysis.score < 45
    assert any("P/E" in risk for risk in analysis.risks)
