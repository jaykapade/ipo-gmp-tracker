"""Pydantic schemas for the HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.models.analysis import IPOAnalysis


class HealthResponse(BaseModel):
    status: str
    database: str
    generated_at: str


class IPOSummary(BaseModel):
    id: int
    name: str
    category: str | None = None
    status: str | None = None
    sector: str | None = None
    exchange: str | None = None

    issue_price: float | None = None
    issue_price_lower: float | None = None
    issue_price_upper: float | None = None
    estimated_listing_price: float | None = None
    ipo_size_cr: str | None = None
    lot_size: str | None = None
    subscription: float | None = None
    pe: float | None = None

    gmp: float | None = None
    gmp_percent: float | None = None
    gmp_percent_derived: bool = False
    latest_gmp_source: str | None = None
    latest_gmp_recorded_at: str | None = None

    open_date: str | None = None
    close_date: str | None = None
    listing_date: str | None = None
    source_url: str | None = None


class IPOPage(BaseModel):
    items: list[IPOSummary] = Field(default_factory=list)
    total: int = 0
    limit: int
    offset: int


class GMPPoint(BaseModel):
    source: str
    gmp: float | None = None
    gmp_percent: float | None = None
    recorded_at: str


class IPODetail(IPOSummary):
    rhp_url: str | None = None
    gmp_history: list[GMPPoint] = Field(default_factory=list)
    latest_analysis: dict[str, Any] | None = None


class AnalyzeRequest(BaseModel):
    min_gmp_percent: float | None = None
    include_upcoming: bool | None = None
    persist: bool = True


class AnalyzeResponse(BaseModel):
    count: int
    analyses: list[IPOAnalysis] = Field(default_factory=list)


class ReportInfo(BaseModel):
    filename: str
    size_bytes: int
    modified_at: str
    download_url: str


class DuplicatePairOut(BaseModel):
    first_id: int
    first_name: str
    second_id: int
    second_name: str
    score: float
