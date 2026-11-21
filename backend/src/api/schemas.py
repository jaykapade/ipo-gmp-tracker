"""Pydantic schemas for the HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.models.analysis import IPOAnalysis


class AIRoleHealth(BaseModel):
    """Resolved provider/model and availability for one generation role."""

    enabled: bool
    provider: str
    model: str
    available: bool
    detail: str


class AIHealth(BaseModel):
    """Configured AI provider availability (never triggers a generation)."""

    enabled: bool
    provider: str
    model: str
    embed_provider: str
    embed_model: str
    rerank_provider: str = "llm"
    available: bool
    detail: str
    roles: dict[str, AIRoleHealth] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    database: str
    generated_at: str
    ai: AIHealth


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

    research_status: str | None = None
    research_verdict: str | None = None


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


class IPOSourceOut(BaseModel):
    """Provenance link between a canonical IPO and one source record."""

    source: str
    source_ipo_id: str | None = None
    source_url: str | None = None
    first_seen_at: str
    last_seen_at: str


class IPODetail(IPOSummary):
    rhp_url: str | None = None
    gmp_history: list[GMPPoint] = Field(default_factory=list)
    sources: list[IPOSourceOut] = Field(default_factory=list)
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


class FacetValue(BaseModel):
    value: str | None = None
    count: int


class IPOFacets(BaseModel):
    """Filter values that actually occur in the data, with counts."""

    total: int
    statuses: list[FacetValue] = Field(default_factory=list)
    categories: list[FacetValue] = Field(default_factory=list)
    sectors: list[FacetValue] = Field(default_factory=list)
    researched: int = 0
    screen_floor: float


class ResearchOutputOut(BaseModel):
    id: int
    kind: str
    provider: str | None = None
    model: str | None = None
    prompt_version: str
    confidence: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    data_left_machine: bool = False
    created_at: str
    output: dict[str, Any]
    citations: list[Any] | None = None


class ResearchRunOut(BaseModel):
    id: int
    ipo_id: int
    status: str
    stage: str | None = None
    error: str | None = None
    prompt_version: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    stages: list[str] = Field(default_factory=list)


class ResearchDetail(ResearchRunOut):
    outputs: list[ResearchOutputOut] = Field(default_factory=list)
    latest_completed: ResearchDetail | None = None


class DuplicatePairOut(BaseModel):
    first_id: int
    first_name: str
    second_id: int
    second_name: str
    score: float


class SubscriptionRequest(BaseModel):
    email: str = Field(max_length=320)
    subscribed: bool


class UnsubscribeRequest(BaseModel):
    token: str = Field(min_length=10, max_length=100)


class SubscriptionStatus(BaseModel):
    subscribed: bool
