"""Transparent weighted scoring for IPO candidates.

No machine learning is used here. Each factor has an explicit weight and a
plain-English explanation so a score can always be audited.
"""

from __future__ import annotations

from src.analysis.metrics import Metrics
from src.models.analysis import ScoreFactor

# Weights must sum to 1.0.
WEIGHTS = {
    "gmp": 0.25,
    "valuation": 0.25,
    "fundamentals": 0.25,
    "subscription": 0.15,
    "risk": 0.10,
}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _linear_score(
    value: float,
    low: float,
    high: float,
    *,
    invert: bool = False,
) -> float:
    """Map a value from ``[low, high]`` onto 0–100, optionally inverted."""

    if high == low:
        return 50.0

    ratio = (value - low) / (high - low)
    if invert:
        ratio = 1.0 - ratio
    return _clamp(ratio * 100.0)


def _factor(
    key: str,
    label: str,
    weight: float,
    score: float,
    explanation: str,
    *,
    data_available: bool = True,
) -> ScoreFactor:
    score = round(_clamp(score), 1)
    return ScoreFactor(
        key=key,
        label=label,
        weight=weight,
        score=score,
        weighted_score=round(score * weight, 2),
        explanation=explanation,
        data_available=data_available,
    )


def score_metrics(metrics: Metrics) -> list[ScoreFactor]:
    """Turn metrics into weighted factors."""

    factors: list[ScoreFactor] = []

    # GMP — 0% scores 0, 60% or more scores 100.
    if metrics.gmp_percent is None:
        factors.append(
            _factor(
                "gmp",
                "GMP",
                WEIGHTS["gmp"],
                0,
                "No GMP percentage is available.",
                data_available=False,
            )
        )
    else:
        factors.append(
            _factor(
                "gmp",
                "GMP",
                WEIGHTS["gmp"],
                _linear_score(metrics.gmp_percent, 0, 60),
                f"Latest GMP is {metrics.gmp_percent:.1f}% of the issue price.",
            )
        )

    # Valuation — P/E of 10 or less scores 100, 40 or more scores 0.
    if metrics.pe is None:
        factors.append(
            _factor(
                "valuation",
                "Valuation",
                WEIGHTS["valuation"],
                50,
                "P/E is not available; a neutral score is used.",
                data_available=False,
            )
        )
    else:
        factors.append(
            _factor(
                "valuation",
                "Valuation",
                WEIGHTS["valuation"],
                _linear_score(metrics.pe, 10, 40, invert=True),
                f"Post-issue P/E is {metrics.pe:.1f}; lower is better.",
            )
        )

    # Fundamentals — the scraper does not ingest RHP financials yet.
    factors.append(
        _factor(
            "fundamentals",
            "Fundamentals",
            WEIGHTS["fundamentals"],
            50,
            "Revenue, margins and debt are not ingested yet; neutral score.",
            data_available=False,
        )
    )

    # Subscription — 0x scores 0, 10x or more scores 100.
    if metrics.subscription is None:
        factors.append(
            _factor(
                "subscription",
                "Subscription",
                WEIGHTS["subscription"],
                50,
                "Subscription data is not available; a neutral score is used.",
                data_available=False,
            )
        )
    else:
        factors.append(
            _factor(
                "subscription",
                "Subscription",
                WEIGHTS["subscription"],
                _linear_score(metrics.subscription, 0, 10),
                f"Overall subscription is {metrics.subscription:.2f}x.",
            )
        )

    # Risk — start at 100 and subtract for observable red flags.
    risk_score = 100.0
    reasons: list[str] = []

    if metrics.gmp_percent is not None and metrics.gmp_percent <= 0:
        risk_score -= 50
        reasons.append("GMP is zero or negative")
    if metrics.issue_price is None:
        risk_score -= 30
        reasons.append("issue price is missing")
    if metrics.pe is not None and metrics.pe > 50:
        risk_score -= 20
        reasons.append("P/E is above 50")
    if metrics.issue_size_cr is not None and metrics.issue_size_cr < 10:
        risk_score -= 15
        reasons.append("issue size is below ₹10 crore")
    if metrics.days_to_close is not None and metrics.days_to_close < 0:
        risk_score -= 40
        reasons.append("close date has passed")
    if metrics.days_to_close is not None and 0 <= metrics.days_to_close <= 1:
        risk_score -= 10
        reasons.append("bidding closes within a day")

    factors.append(
        _factor(
            "risk",
            "Risk",
            WEIGHTS["risk"],
            risk_score,
            "; ".join(reasons) if reasons else "No major numeric risk flags.",
        )
    )

    return factors


def overall_score(factors: list[ScoreFactor]) -> float:
    return round(sum(factor.weighted_score for factor in factors), 1)


def verdict_for(score: float) -> str:
    if score >= 70:
        return "Strong"
    if score >= 45:
        return "Watch"
    return "Avoid"
