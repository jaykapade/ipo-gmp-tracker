"""HTTP routes for the IPO Checker API."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse

from src import config
from src.api.schemas import (
    AIHealth,
    AnalyzeRequest,
    AnalyzeResponse,
    DuplicatePairOut,
    GMPPoint,
    HealthResponse,
    IPODetail,
    IPOFacets,
    IPOPage,
    IPOSourceOut,
    IPOSummary,
    ReportInfo,
    ResearchDetail,
    ResearchRunOut,
)
from src.database import db
from src.llm import LLMClient
from src.models.analysis import IPOAnalysis
from src.pipeline import analyze_pipeline
from src.reporting import generate_report
from src.research import STAGES as RESEARCH_STAGES
from src.research import ResearchJobs
from src.utils.dedupe import find_duplicate_pairs

router = APIRouter(prefix="/api")


def _db_path(request: Request) -> str | Path | None:
    return request.app.state.db_path


def _report_dir(request: Request) -> Path:
    return Path(request.app.state.report_dir)


def require_token(
    request: Request,
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> None:
    """Protect mutating endpoints when ``API_TOKEN`` is configured."""

    expected = getattr(request.app.state, "api_token", None)
    if expected and x_api_token != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing X-API-Token header.",
        )


def _summary_from_scored_row(row: dict[str, Any]) -> IPOSummary:
    return IPOSummary(
        id=int(row["id"]),
        name=row["name"],
        category=row.get("category"),
        status=row.get("status"),
        sector=row.get("sector"),
        exchange=row.get("exchange"),
        issue_price=row.get("issue_price"),
        issue_price_lower=row.get("issue_price_lower"),
        issue_price_upper=row.get("issue_price_upper"),
        estimated_listing_price=row.get("estimated_listing_price"),
        ipo_size_cr=row.get("ipo_size_cr"),
        lot_size=row.get("lot_size"),
        subscription=row.get("subscription"),
        pe=row.get("pe"),
        gmp=row.get("latest_gmp"),
        gmp_percent=row.get("latest_gmp_percent"),
        gmp_percent_derived=bool(row.get("latest_gmp_percent_derived")),
        latest_gmp_source=row.get("latest_gmp_source"),
        latest_gmp_recorded_at=row.get("latest_gmp_recorded_at"),
        open_date=row.get("open_date"),
        close_date=row.get("close_date"),
        listing_date=row.get("listing_date"),
        source_url=row.get("source_url"),
        research_status=row.get("research_status"),
        research_verdict=row.get("research_verdict"),
    )


def _run_out(run: dict[str, Any]) -> ResearchRunOut:
    fields = {key: run.get(key) for key in ResearchRunOut.model_fields}
    fields["stages"] = list(RESEARCH_STAGES)
    return ResearchRunOut(**fields)


def _research_detail(run: dict[str, Any]) -> ResearchDetail:
    completed = run.get("latest_completed")
    return ResearchDetail(
        **_run_out(run).model_dump(),
        outputs=run.get("outputs") or [],
        latest_completed=_research_detail(completed) if completed else None,
    )


def _summary_from_ipo_row(
    row: dict[str, Any],
    latest: dict[str, Any] | None,
) -> IPOSummary:
    latest = latest or {}
    gmp = latest.get("gmp")
    gmp_percent = latest.get("gmp_percent")
    derived = False

    issue_price = row.get("issue_price")
    if gmp_percent is None and gmp is not None and issue_price:
        gmp_percent = (float(gmp) * 100.0) / float(issue_price)
        derived = True

    return IPOSummary(
        id=int(row["id"]),
        name=row["name"],
        category=row.get("category"),
        status=row.get("status"),
        sector=row.get("sector"),
        exchange=row.get("exchange"),
        issue_price=issue_price,
        issue_price_lower=row.get("issue_price_lower"),
        issue_price_upper=row.get("issue_price_upper"),
        estimated_listing_price=row.get("estimated_listing_price"),
        ipo_size_cr=row.get("ipo_size_cr"),
        lot_size=row.get("lot_size"),
        subscription=row.get("subscription"),
        pe=row.get("pe"),
        gmp=gmp,
        gmp_percent=gmp_percent,
        gmp_percent_derived=derived,
        latest_gmp_source=latest.get("source"),
        latest_gmp_recorded_at=latest.get("recorded_at"),
        open_date=row.get("open_date"),
        close_date=row.get("close_date"),
        listing_date=row.get("listing_date"),
        source_url=row.get("source_url"),
    )


def _report_info(path: Path) -> ReportInfo:
    stat = path.stat()
    return ReportInfo(
        filename=path.name,
        size_bytes=stat.st_size,
        modified_at=datetime.fromtimestamp(
            stat.st_mtime,
            tz=UTC,
        ).isoformat(),
        download_url=f"/api/reports/{path.name}",
    )


@router.get("", tags=["meta"])
def api_index() -> dict[str, str]:
    return {
        "name": "IPO Checker API",
        "docs": "/docs",
        "health": "/api/health",
    }


@router.get("/health", response_model=HealthResponse, tags=["meta"])
def health(request: Request) -> HealthResponse:
    llm_client: LLMClient = request.app.state.llm
    return HealthResponse(
        status="ok",
        database=str(_db_path(request) or config.DB_PATH),
        generated_at=datetime.now(UTC).isoformat(),
        ai=AIHealth(**llm_client.status()),
    )


@router.get("/ipos", response_model=IPOPage, tags=["ipos"])
def list_ipos(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    min_gmp: float | None = Query(default=None, ge=0),
    q: str | None = Query(default=None, max_length=100),
    category: Literal["mainboard", "sme"] | None = Query(default=None),
    has_research: bool | None = Query(default=None),
    sort: Literal[
        "name",
        "gmp_percent",
        "close_date",
        "subscription",
        "pe",
        "issue_price",
        "updated_at",
    ] = Query(default="name"),
    order: Literal["asc", "desc"] = Query(default="asc"),
) -> IPOPage:
    rows = db.list_ipos(
        status=status,
        min_gmp_percent=min_gmp,
        q=q,
        category=category,
        has_research=has_research,
        sort=sort,
        order=order,
        limit=limit,
        offset=offset,
        db_path=_db_path(request),
    )
    total = db.count_ipos(
        status=status,
        min_gmp_percent=min_gmp,
        q=q,
        category=category,
        has_research=has_research,
        db_path=_db_path(request),
    )

    return IPOPage(
        items=[_summary_from_scored_row(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/ipos/facets", response_model=IPOFacets, tags=["ipos"])
def ipo_facets(request: Request) -> IPOFacets:
    """Filter options that exist in the data (drives the dashboard filters)."""

    return IPOFacets(
        **db.get_ipo_facets(db_path=_db_path(request)),
        screen_floor=config.MIN_GMP_PERCENT,
    )


@router.get("/ipos/{ipo_id}", response_model=IPODetail, tags=["ipos"])
def get_ipo(request: Request, ipo_id: int) -> IPODetail:
    row = db.get_ipo(ipo_id, db_path=_db_path(request))
    if row is None:
        raise HTTPException(status_code=404, detail="IPO not found")

    history = db.get_gmp_history(
        ipo_id,
        limit=100,
        db_path=_db_path(request),
    )
    latest = history[0] if history else None
    summary = _summary_from_ipo_row(row, latest)
    research = db.get_latest_research(ipo_id, db_path=_db_path(request))
    if research is not None:
        summary.research_status = research["status"]
        done = research if research["status"] == "done" else research.get(
            "latest_completed"
        )
        if done:
            h5 = next((o for o in done["outputs"] if o["kind"] == "h5"), None)
            summary.research_verdict = h5["output"].get("verdict") if h5 else None

    return IPODetail(
        **summary.model_dump(),
        rhp_url=row.get("rhp_url"),
        gmp_history=[
            GMPPoint(
                source=item["source"],
                gmp=item.get("gmp"),
                gmp_percent=item.get("gmp_percent"),
                recorded_at=item["recorded_at"],
            )
            for item in history
        ],
        sources=[
            IPOSourceOut(**source)
            for source in db.get_ipo_sources(
                ipo_id,
                db_path=_db_path(request),
            )
        ],
        latest_analysis=db.get_latest_analysis(
            ipo_id,
            db_path=_db_path(request),
        ),
    )


@router.post(
    "/ipos/{ipo_id}/research",
    response_model=ResearchRunOut,
    status_code=202,
    dependencies=[Depends(require_token)],
    tags=["research"],
)
def start_research(request: Request, ipo_id: int) -> ResearchRunOut:
    """Queue an AI research run (web facts, H1-H5, verifier, disputes)."""

    if db.get_ipo(ipo_id, db_path=_db_path(request)) is None:
        raise HTTPException(status_code=404, detail="IPO not found")
    llm_client: LLMClient = request.app.state.llm
    if not llm_client.for_role("analyst").enabled:
        raise HTTPException(
            status_code=409,
            detail="AI is disabled; set LLM_ENABLED=true (see backend/.env.example).",
        )
    jobs: ResearchJobs = request.app.state.research
    run, _created = jobs.submit(ipo_id)
    return _run_out(run)


@router.get(
    "/ipos/{ipo_id}/research",
    response_model=ResearchDetail | None,
    tags=["research"],
)
def latest_research(request: Request, ipo_id: int) -> ResearchDetail | None:
    """Newest research run with its outputs (null when never researched)."""

    if db.get_ipo(ipo_id, db_path=_db_path(request)) is None:
        raise HTTPException(status_code=404, detail="IPO not found")
    run = db.get_latest_research(ipo_id, db_path=_db_path(request))
    return _research_detail(run) if run else None


@router.get(
    "/research/runs/{run_id}",
    response_model=ResearchRunOut,
    tags=["research"],
)
def research_run(request: Request, run_id: int) -> ResearchRunOut:
    run = db.get_research_run(run_id, db_path=_db_path(request))
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    return _run_out(run)


@router.get(
    "/candidates",
    response_model=list[IPOAnalysis],
    tags=["analysis"],
)
def list_candidates(
    request: Request,
    min_gmp: float | None = Query(default=None, ge=0),
    include_upcoming: bool | None = Query(default=None),
) -> list[IPOAnalysis]:
    run = analyze_pipeline(
        min_gmp_percent=min_gmp,
        include_upcoming=include_upcoming,
        persist=False,
        db_path=_db_path(request),
    )
    return run.analyses


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    dependencies=[Depends(require_token)],
    tags=["analysis"],
)
def run_analysis(
    request: Request,
    body: AnalyzeRequest | None = None,
) -> AnalyzeResponse:
    payload = body or AnalyzeRequest()
    run = analyze_pipeline(
        min_gmp_percent=payload.min_gmp_percent,
        include_upcoming=payload.include_upcoming,
        persist=payload.persist,
        db_path=_db_path(request),
    )
    return AnalyzeResponse(count=len(run.analyses), analyses=run.analyses)


@router.get("/reports", response_model=list[ReportInfo], tags=["reports"])
def list_reports(request: Request) -> list[ReportInfo]:
    report_dir = _report_dir(request)
    report_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(
        report_dir.glob("*.pdf"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return [_report_info(path) for path in files if path.is_file()]


@router.post(
    "/reports",
    response_model=ReportInfo,
    dependencies=[Depends(require_token)],
    tags=["reports"],
)
def create_report(
    request: Request,
    body: AnalyzeRequest | None = None,
) -> ReportInfo:
    payload = body or AnalyzeRequest()
    run = analyze_pipeline(
        min_gmp_percent=payload.min_gmp_percent,
        include_upcoming=payload.include_upcoming,
        persist=True,
        db_path=_db_path(request),
    )

    report_dir = _report_dir(request)
    report_dir.mkdir(parents=True, exist_ok=True)
    filename = (
        f"ipo_report_{run.generated_at.strftime('%Y%m%d_%H%M%S_%f')}.pdf"
    )

    path = generate_report(
        run.analyses,
        output_path=report_dir / filename,
        min_gmp_percent=run.min_gmp_percent,
        include_upcoming=run.include_upcoming,
        generated_at=run.generated_at,
    )
    return _report_info(path)


@router.get("/reports/{filename}", tags=["reports"])
def download_report(request: Request, filename: str) -> FileResponse:
    safe_name = Path(filename).name
    if safe_name != filename or not safe_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=404, detail="Report not found")

    path = _report_dir(request) / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=safe_name,
    )


@router.get(
    "/quality/duplicates",
    response_model=list[DuplicatePairOut],
    tags=["quality"],
)
def possible_duplicates(
    request: Request,
    threshold: float = Query(default=90.0, ge=0, le=100),
    limit: int = Query(default=500, ge=1, le=5000),
) -> list[DuplicatePairOut]:
    rows = db.list_ipos(limit=limit, db_path=_db_path(request))
    pairs = find_duplicate_pairs(rows, threshold=threshold)

    return [
        DuplicatePairOut(
            first_id=pair.first_id,
            first_name=pair.first_name,
            second_id=pair.second_id,
            second_name=pair.second_name,
            score=pair.score,
        )
        for pair in pairs
    ]
