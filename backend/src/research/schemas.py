"""Typed shapes for AI research (framework section H).

Two families live here:

* **Model-facing schemas** (``GatherResult``, ``Perspective``,
  ``VerifierReview``, ``ChallengerReview``, ``Assessment``) are passed to the
  provider as JSON schemas and validated with the shared
  :func:`~src.llm.base.validate_against_schema` gate.
* **Stored shapes** (``Fact``, ``FactPack``) add the ids and provenance the
  pipeline assigns itself, so the model never invents fact ids.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

FactCategory = Literal[
    "issue",
    "business",
    "financials",
    "valuation",
    "peers",
    "risk",
    "market",
    "news",
]
SourceType = Literal["official", "exchange", "secondary", "database"]
ConfidenceLevel = Literal["high", "medium", "low"]
PerspectiveKey = Literal["h1", "h2", "h3", "h4"]
Verdict = Literal["Strong", "Watch", "Avoid"]


# --- Evidence ----------------------------------------------------------------


class GatheredFact(BaseModel):
    """One fact as returned by the web researcher (no id yet)."""

    category: FactCategory
    claim: str = Field(description="One self-contained factual statement.")
    value: str | None = Field(
        default=None, description="The key figure with its unit, e.g. '₹455 cr'."
    )
    period: str | None = Field(
        default=None, description="Period the figure refers to, e.g. 'FY25'."
    )
    source_url: str = Field(description="URL of the page the fact came from.")
    source_title: str | None = None
    source_type: Literal["official", "exchange", "secondary"] = Field(
        description="official = RHP/DRHP/SEBI/company; exchange = NSE/BSE; "
        "secondary = media, aggregators, broker notes."
    )


class GatherResult(BaseModel):
    """Model output of the web-research step."""

    facts: list[GatheredFact]
    gaps: list[str] = Field(
        default_factory=list,
        description="Important items that could not be found.",
    )
    rhp_url: str | None = Field(
        default=None, description="Direct URL of the RHP/DRHP PDF if found."
    )


class Fact(BaseModel):
    """A stored, citable fact with a pipeline-assigned id (``W1``, ``D1`` …)."""

    id: str
    category: FactCategory
    claim: str
    value: str | None = None
    period: str | None = None
    source_url: str | None = None
    source_title: str | None = None
    source_type: SourceType
    as_of: str | None = None


class FactPack(BaseModel):
    """Everything the perspectives are allowed to know about one IPO."""

    ipo_id: int
    ipo_name: str
    facts: list[Fact]
    gaps: list[str] = Field(default_factory=list)
    rhp_url: str | None = None
    gathered_at: str

    def ids(self) -> set[str]:
        return {fact.id for fact in self.facts}


# --- Perspectives (H1–H4) ----------------------------------------------------


class EvidencePoint(BaseModel):
    point: str = Field(description="One finding, stated plainly.")
    fact_ids: list[str] = Field(
        description="Ids of the facts that support this point, e.g. ['W3','D1']."
    )


class Confidence(BaseModel):
    level: ConfidenceLevel
    reason: str


class Perspective(BaseModel):
    """Model output for one isolated perspective."""

    evidence: list[EvidencePoint]
    conclusion: str = Field(description="Short, non-advisory conclusion.")
    confidence: Confidence
    missing_information: list[str] = Field(
        default_factory=list,
        description="What would change the conclusion if it were known.",
    )


class PerspectiveRecord(Perspective):
    """A stored perspective plus what the citation gate removed."""

    key: PerspectiveKey
    title: str
    dropped_evidence: list[str] = Field(default_factory=list)
    error: str | None = None


# --- Verification and challenge ----------------------------------------------


class Review(BaseModel):
    finding_id: str = Field(description="Id of the finding, e.g. 'h2.3'.")
    stance: Literal["agree", "disagree", "unsupported"]
    reason: str
    fact_ids: list[str] = Field(default_factory=list)


class VerifierReview(BaseModel):
    reviews: list[Review]


class Ruling(BaseModel):
    finding_id: str
    ruling: Literal["uphold_finding", "uphold_verifier", "unresolved"]
    reason: str


class ChallengerReview(BaseModel):
    rulings: list[Ruling]


class Dispute(BaseModel):
    """A finding the verifier did not accept, with both positions."""

    finding_id: str
    perspective: PerspectiveKey
    finding: str
    stance: Literal["disagree", "unsupported"]
    verifier_reason: str
    ruling: Literal["uphold_finding", "uphold_verifier", "unresolved"] = "unresolved"
    ruling_reason: str | None = None


# --- Synthesis (H5) ----------------------------------------------------------


class Assessment(BaseModel):
    verdict: Verdict
    conclusion: str
    strengths: list[str] = Field(description="Top three strengths.")
    risks: list[str] = Field(description="Top three risks.")
    what_would_change: list[str]
    confidence: Confidence


__all__ = [
    "Assessment",
    "ChallengerReview",
    "Confidence",
    "Dispute",
    "EvidencePoint",
    "Fact",
    "FactPack",
    "GatherResult",
    "GatheredFact",
    "Perspective",
    "PerspectiveKey",
    "PerspectiveRecord",
    "Review",
    "Ruling",
    "VerifierReview",
]
