"""Pydantic models for deterministic IPO analysis output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ScoreFactor(BaseModel):
    """One transparent input to the weighted score."""

    key: str
    label: str
    weight: float
    score: float
    weighted_score: float
    explanation: str
    data_available: bool = True


class ChecklistItem(BaseModel):
    """One line of the human-readable analysis checklist."""

    key: str
    label: str
    status: Literal["pass", "warn", "fail", "manual"]
    detail: str


class IPOAnalysis(BaseModel):
    """Analysis result for a single IPO.

    Every number is computed deterministically from stored data. Items that need
    RHP/financial statements are marked ``manual`` rather than guessed.
    """

    ipo_id: int
    name: str
    score: float
    verdict: Literal["Strong", "Watch", "Avoid"]

    gmp: float | None = None
    gmp_percent: float | None = None
    gmp_percent_derived: bool = False
    issue_price: float | None = None
    issue_size_cr: float | None = None
    subscription: float | None = None
    pe: float | None = None
    close_date: str | None = None

    factors: list[ScoreFactor] = Field(default_factory=list)
    checklist: list[ChecklistItem] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)

    generated_at: str
