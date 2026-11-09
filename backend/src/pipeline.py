"""Pipeline orchestration shared by the CLI and future API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from src import config
from src.analysis import analyze_candidates, select_candidates
from src.database import db
from src.models.analysis import IPOAnalysis
from src.scrapers.base import BaseScraper
from src.scrapers.errors import ScraperError
from src.scrapers.investorgain import InvestorGainScraper
from src.scrapers.ipowatch import IpoWatchScraper
from src.utils.parsing import (
    IST,
    derive_status_from_dates,
    is_open_status,
)

# One instance per source. They create their HTTP session lazily, so importing
# this module never opens a connection.
SCRAPERS: dict[str, BaseScraper] = {
    "ipowatch": IpoWatchScraper(),
    "investorgain": InvestorGainScraper(),
}


@dataclass
class ScrapeResult:
    """Per-source outcome of a scrape."""

    source: str
    saved: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


def _fail_scrape_run(
    run_id: int,
    result: ScrapeResult,
    error: Exception,
    db_path: str | Path | None,
) -> None:
    """Record a fetch/parse failure and keep the remaining sources running."""

    result.errors.append(f"fetch failed: {error}")
    db.update_scrape_run(
        run_id,
        status="failed",
        error_message=str(error),
        db_path=db_path,
    )


@dataclass
class AnalysisRun:
    """The result of one screening + analysis pass."""

    analyses: list[IPOAnalysis]
    min_gmp_percent: float
    include_upcoming: bool
    generated_at: datetime


def scrape_sources(
    sources: list[str],
    *,
    db_path: str | Path | None = None,
) -> list[ScrapeResult]:
    """Scrape one or more sources, isolating failures per row and per source."""

    results: list[ScrapeResult] = []

    for name in sources:
        scraper = SCRAPERS.get(name)
        if scraper is None:
            raise ValueError(f"Unknown source: {name}")

        result = ScrapeResult(source=scraper.source_name)

        run_id = db.create_scrape_run(scraper.source_name, db_path=db_path)

        try:
            payload = scraper.fetch()
            rows = scraper.rows(payload)
        except ScraperError as error:
            _fail_scrape_run(run_id, result, error, db_path)
            results.append(result)
            continue
        except Exception as error:  # noqa: BLE001 - report and continue
            _fail_scrape_run(run_id, result, error, db_path)
            results.append(result)
            continue

        rows_scraped = len(rows)

        for row in rows:
            try:
                ipo = scraper.convert_row(row)

                # Only save IPOs that are currently open. Sources that don't
                # provide a status (e.g. InvestorGain) get one derived from
                # their open/close dates.
                status = ipo.status
                if status is None:
                    status = derive_status_from_dates(
                        ipo.open_date, ipo.close_date
                    )
                if status is not None and not is_open_status(status):
                    continue

                # Persist the derived status too, otherwise InvestorGain rows
                # keep status = NULL and cannot be filtered by status later.
                if status is not None:
                    ipo.status = status

                scraper.save(
                    ipo,
                    db_path=db_path,
                    scrape_run_id=run_id,
                )
                result.saved += 1
            except Exception as error:  # noqa: BLE001 - report and continue
                result.failed += 1
                result.errors.append(str(error))

        db.update_scrape_run(
            run_id,
            status="completed",
            rows_scraped=rows_scraped,
            rows_saved=result.saved,
            rows_failed=result.failed,
            error_message=(
                "; ".join(result.errors[:3]) if result.errors else None
            ),
            db_path=db_path,
        )

        results.append(result)

    return results


def analyze_pipeline(
    *,
    min_gmp_percent: float | None = None,
    include_upcoming: bool | None = None,
    persist: bool = True,
    db_path: str | Path | None = None,
    today: date | None = None,
) -> AnalysisRun:
    """Select candidates, analyse them and optionally persist each report."""

    threshold = (
        config.MIN_GMP_PERCENT if min_gmp_percent is None else min_gmp_percent
    )
    upcoming = (
        config.INCLUDE_UPCOMING if include_upcoming is None else include_upcoming
    )

    candidates = select_candidates(
        min_gmp_percent=threshold,
        include_upcoming=upcoming,
        db_path=db_path,
    )
    analyses = analyze_candidates(candidates, today=today)

    if persist:
        for analysis in analyses:
            db.save_analysis_report(analysis, db_path=db_path)

    return AnalysisRun(
        analyses=analyses,
        min_gmp_percent=threshold,
        include_upcoming=upcoming,
        generated_at=datetime.now(IST),
    )


def analyses_as_json(analyses: list[IPOAnalysis]) -> str:
    """Serialise analyses for scripting or piping."""

    import json

    return json.dumps(
        [analysis.model_dump() for analysis in analyses],
        indent=2,
        default=str,
    )


def summarise_scrape(results: list[ScrapeResult]) -> str:
    lines: list[str] = []
    for result in results:
        lines.append(
            f"{result.source}: saved {result.saved}, failed {result.failed}"
        )
        for error in result.errors[:5]:
            lines.append(f"  - {error}")
        if len(result.errors) > 5:
            lines.append(f"  - ... {len(result.errors) - 5} more error(s)")
    return "\n".join(lines)
