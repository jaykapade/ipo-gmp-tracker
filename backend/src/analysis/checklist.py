"""Checklist rules covering what the stored data can and cannot answer."""

from __future__ import annotations

from src.analysis.metrics import Metrics
from src.models.analysis import ChecklistItem


def _item(
    key: str,
    label: str,
    status: str,
    detail: str,
) -> ChecklistItem:
    return ChecklistItem(key=key, label=label, status=status, detail=detail)


def build_checklist(metrics: Metrics) -> list[ChecklistItem]:
    """Return pass/warn/fail/manual items for one IPO."""

    items: list[ChecklistItem] = []

    # Hard filter: latest GMP >= 20%.
    if metrics.gmp_percent is None:
        items.append(
            _item("gmp", "GMP at least 20%", "warn", "GMP percentage is missing.")
        )
    elif metrics.gmp_percent >= 20:
        items.append(
            _item(
                "gmp",
                "GMP at least 20%",
                "pass",
                f"Latest GMP is {metrics.gmp_percent:.1f}%.",
            )
        )
    else:
        items.append(
            _item(
                "gmp",
                "GMP at least 20%",
                "fail",
                f"Latest GMP is only {metrics.gmp_percent:.1f}%.",
            )
        )

    # GMP trend.
    if metrics.history_points < 2:
        items.append(
            _item(
                "gmp_trend",
                "GMP trend",
                "manual",
                "Not enough history to judge the trend.",
            )
        )
    elif metrics.gmp_trend_label == "Falling":
        items.append(
            _item(
                "gmp_trend",
                "GMP trend",
                "warn",
                f"GMP is falling ({metrics.gmp_trend:+.1f} percentage points).",
            )
        )
    else:
        items.append(
            _item(
                "gmp_trend",
                "GMP trend",
                "pass",
                f"GMP trend is {metrics.gmp_trend_label.lower()}.",
            )
        )

    # Valuation.
    if metrics.pe is None:
        items.append(
            _item(
                "valuation",
                "Valuation",
                "manual",
                "P/E and peer valuation are not available; read the RHP.",
            )
        )
    elif metrics.pe <= 25:
        items.append(
            _item(
                "valuation",
                "Valuation",
                "pass",
                f"Post-issue P/E is {metrics.pe:.1f}.",
            )
        )
    elif metrics.pe <= 40:
        items.append(
            _item(
                "valuation",
                "Valuation",
                "warn",
                f"Post-issue P/E is {metrics.pe:.1f}; compare with peers.",
            )
        )
    else:
        items.append(
            _item(
                "valuation",
                "Valuation",
                "fail",
                f"Post-issue P/E is {metrics.pe:.1f}, which is high.",
            )
        )

    # Issue size.
    if metrics.issue_size_cr is None:
        items.append(
            _item("issue_size", "Issue size", "manual", "Issue size is missing.")
        )
    elif metrics.issue_size_cr >= 10:
        items.append(
            _item(
                "issue_size",
                "Issue size",
                "pass",
                f"Issue size is ₹{metrics.issue_size_cr:.2f} crore.",
            )
        )
    else:
        items.append(
            _item(
                "issue_size",
                "Issue size",
                "warn",
                f"Issue size is only ₹{metrics.issue_size_cr:.2f} crore.",
            )
        )

    # Subscription.
    if metrics.subscription is None:
        items.append(
            _item(
                "subscription",
                "Subscription",
                "manual",
                "Subscription data is missing.",
            )
        )
    elif metrics.subscription >= 1:
        items.append(
            _item(
                "subscription",
                "Subscription",
                "pass",
                f"Overall subscription is {metrics.subscription:.2f}x.",
            )
        )
    else:
        items.append(
            _item(
                "subscription",
                "Subscription",
                "fail",
                f"Overall subscription is only {metrics.subscription:.2f}x.",
            )
        )

    # Cross-source agreement.
    if metrics.source_spread_percent is None:
        items.append(
            _item(
                "source_consistency",
                "Source consistency",
                "manual",
                "Only one source has a GMP percentage.",
            )
        )
    elif metrics.source_spread_percent <= 10:
        items.append(
            _item(
                "source_consistency",
                "Source consistency",
                "pass",
                f"Sources differ by {metrics.source_spread_percent:.1f} points.",
            )
        )
    else:
        items.append(
            _item(
                "source_consistency",
                "Source consistency",
                "warn",
                f"Sources differ by {metrics.source_spread_percent:.1f} points.",
            )
        )

    # Items that require reading the offer document.
    items.extend(
        [
            _item(
                "fundamentals",
                "Fundamentals",
                "manual",
                "Revenue, margins, debt and cash flow need the RHP.",
            ),
            _item(
                "objects",
                "Objects of the issue",
                "manual",
                "Check fresh issue vs OFS and use of proceeds in the RHP.",
            ),
            _item(
                "red_flags",
                "Red flags",
                "manual",
                "Check auditor changes, promoter selling, litigation and pledges.",
            ),
        ]
    )

    return items
