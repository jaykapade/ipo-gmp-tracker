"""IPO analysis: deterministic filters, metrics and scoring.

AI is deliberately not used here. Every threshold and calculation in this
package must remain reproducible and testable.
"""

from src.analysis.analyzer import analyze_candidate, analyze_candidates
from src.analysis.checklist import build_checklist
from src.analysis.filters import Candidate, row_is_active, select_candidates
from src.analysis.metrics import Metrics, compute_metrics
from src.analysis.scoring import overall_score, score_metrics, verdict_for

__all__ = [
    "Candidate",
    "Metrics",
    "analyze_candidate",
    "analyze_candidates",
    "build_checklist",
    "compute_metrics",
    "overall_score",
    "row_is_active",
    "score_metrics",
    "select_candidates",
    "verdict_for",
]
