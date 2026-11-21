"""AI research: web evidence gathering and multi-perspective review.

See ``orchestrator.py`` for the pipeline and docs/ipo-research-framework.md
section H for the specification it implements.
"""

from src.research.jobs import ResearchJobs
from src.research.orchestrator import (
    STAGES,
    ResearchError,
    ResearchResult,
    run_research,
)
from src.research.prompts import PROMPT_VERSION

__all__ = [
    "PROMPT_VERSION",
    "STAGES",
    "ResearchError",
    "ResearchJobs",
    "ResearchResult",
    "run_research",
]
