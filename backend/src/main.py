"""Command-line entry point for the IPO Checker pipeline.

Examples::

    python -m src.main scrape
    python -m src.main scrape --source ipowatch
    python -m src.main analyze
    python -m src.main analyze --json
    python -m src.main report
    python -m src.main report --email --dry-run
    python -m src.main run --email
    python -m src.main run --research --email      # the scheduled job
    python -m src.main research 12
    python -m src.main research --all-open
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from src import config
from src.pipeline import (
    SCRAPERS,
    AnalysisRun,
    analyses_as_json,
    analyze_pipeline,
    scrape_sources,
    summarise_scrape,
)
from src.reporting import build_text_summary, generate_report, send_email

logger = logging.getLogger(__name__)


def _analysis_kwargs(args: argparse.Namespace) -> dict:
    return {
        "min_gmp_percent": args.min_gmp,
        "include_upcoming": args.include_upcoming,
        "persist": not args.no_persist,
        "db_path": args.db_path,
    }


def _print_summary(run: AnalysisRun, research: dict | None = None) -> None:
    print(
        build_text_summary(
            run.analyses,
            min_gmp_percent=run.min_gmp_percent,
            include_upcoming=run.include_upcoming,
            generated_at=run.generated_at,
            research=research,
        )
    )


def _research_screened(args: argparse.Namespace, run: AnalysisRun) -> dict | None:
    """With ``--research``: make sure every screened IPO has recent research.

    Returns digests keyed by IPO id, or ``None`` without ``--research``.
    AI problems never stop the report; they show up as notes in it.
    """

    if not getattr(args, "research", False):
        return None

    from src.llm import LLMClient
    from src.research.digest import research_for_report

    ipo_ids = [analysis.ipo_id for analysis in run.analyses]
    if not ipo_ids:
        return {}

    max_age = (
        args.research_max_age
        if args.research_max_age is not None
        else config.RESEARCH_MAX_AGE_HOURS
    )
    names = {analysis.ipo_id: analysis.name for analysis in run.analyses}
    client = LLMClient(config.LLM)
    if not client.for_role("analyst").enabled:
        logger.warning(
            "--research: AI is disabled; the report shows stored research only."
        )

    def on_event(ipo_id: int, message: str) -> None:
        logger.info("Research #%s %s: %s", ipo_id, names.get(ipo_id, ""), message)

    return research_for_report(
        ipo_ids,
        client=client,
        max_age_hours=max_age,
        db_path=args.db_path,
        on_event=on_event,
    )


def _report_and_maybe_email(
    args: argparse.Namespace,
    run: AnalysisRun,
    research: dict | None = None,
) -> None:
    path = generate_report(
        run.analyses,
        output_path=args.output,
        min_gmp_percent=run.min_gmp_percent,
        include_upcoming=run.include_upcoming,
        generated_at=run.generated_at,
        research=research,
    )
    print(f"Report written: {path}")

    if not args.email:
        if args.dry_run:
            print("--dry-run has no effect without --email.")
        return

    body = build_text_summary(
        run.analyses,
        min_gmp_percent=run.min_gmp_percent,
        include_upcoming=run.include_upcoming,
        generated_at=run.generated_at,
        research=research,
    )
    result = send_email(
        subject=f"IPO report: {len(run.analyses)} candidate(s)",
        body=body,
        attachments=[path],
        dry_run=args.dry_run,
    )

    if result.dry_run:
        logger.info(
            "Dry run: would email %d recipient(s) (%s) with %s.",
            len(result.recipients),
            ", ".join(result.recipients),
            path.name,
        )
    else:
        logger.info(
            "Emailed %s to %s.",
            path.name,
            ", ".join(result.recipients),
        )


def _cmd_scrape(args: argparse.Namespace) -> int:
    sources = list(SCRAPERS) if args.source == "all" else [args.source]
    results = scrape_sources(sources, db_path=args.db_path)
    for line in summarise_scrape(results).splitlines():
        logger.info("%s", line)

    failed = any(result.errors for result in results)
    return 1 if failed else 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    run = analyze_pipeline(**_analysis_kwargs(args))

    if args.json:
        print(analyses_as_json(run.analyses))
    else:
        _print_summary(run)

    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    run = analyze_pipeline(**_analysis_kwargs(args))
    research = _research_screened(args, run)
    _print_summary(run, research)
    _report_and_maybe_email(args, run, research)
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    sources = list(SCRAPERS) if args.source == "all" else [args.source]
    results = scrape_sources(sources, db_path=args.db_path)
    for line in summarise_scrape(results).splitlines():
        logger.info("%s", line)

    run = analyze_pipeline(**_analysis_kwargs(args))
    research = _research_screened(args, run)
    _print_summary(run, research)
    _report_and_maybe_email(args, run, research)

    return 1 if any(result.errors for result in results) else 0


def _cmd_research(args: argparse.Namespace) -> int:
    """Run AI research synchronously for one IPO or every open IPO."""

    from src.database import db
    from src.llm import LLMClient
    from src.research import ResearchError, run_research

    client = LLMClient(config.LLM)
    if not client.for_role("analyst").enabled:
        print("AI is disabled. Set LLM_ENABLED=true (see backend/.env.example).")
        return 2

    if args.all_open:
        rows = db.list_ipos(status="open", limit=200, db_path=args.db_path)
        ipo_ids = [int(row["id"]) for row in rows]
    elif args.ipo_id is not None:
        ipo_ids = [args.ipo_id]
    else:
        print("Give an IPO id or --all-open.")
        return 2

    if not ipo_ids:
        print("No IPOs to research.")
        return 0

    failures = 0
    for ipo_id in ipo_ids:
        ipo = db.get_ipo(ipo_id, db_path=args.db_path)
        if ipo is None:
            print(f"IPO {ipo_id} not found.")
            failures += 1
            continue
        print(f"\n== Researching #{ipo_id} {ipo['name']} ==")
        try:
            result = run_research(
                ipo_id,
                client=client,
                db_path=args.db_path,
                on_stage=lambda stage: print(f"  - {stage}", flush=True),
            )
        except ResearchError as exc:
            print(f"  failed: {exc}")
            failures += 1
            continue

        assessment = result.assessment
        web = sum(1 for f in result.fact_pack.facts if f.source_type != "database")
        print(
            f"  facts: {len(result.fact_pack.facts)} ({web} from the web) · "
            f"disputes: {len(result.disputes)}"
        )
        print(
            f"  verdict: {assessment.verdict} "
            f"(confidence {assessment.confidence.level})"
        )
        print(f"  {assessment.conclusion}")
        for note in result.notes:
            print(f"  note: {note}")

    return 1 if failures else 0


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    if args.db_path:
        # ``--reload`` starts a subprocess, which re-reads the environment.
        os.environ["IPO_DB_PATH"] = str(args.db_path)

    if args.reload:
        uvicorn.run(
            "src.api.main:app",
            host=args.host,
            port=args.port,
            reload=True,
        )
    else:
        from src.api.main import create_app

        uvicorn.run(
            create_app(db_path=args.db_path),
            host=args.host,
            port=args.port,
        )

    return 0


def _add_analysis_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--min-gmp",
        type=float,
        default=None,
        help="Minimum latest GMP percentage (default: MIN_GMP_PERCENT).",
    )
    parser.add_argument(
        "--include-upcoming",
        action="store_true",
        default=None,
        help="Include IPOs whose status is Upcoming.",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Analyse without writing rows to analysis_reports.",
    )


def _add_report_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output",
        default=None,
        help="PDF output path (default: reports/ipo_report_<timestamp>.pdf).",
    )
    parser.add_argument(
        "--email",
        action="store_true",
        help="Email the generated PDF using the SMTP settings.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and describe the email without sending it.",
    )
    parser.add_argument(
        "--research",
        action="store_true",
        help=(
            "Run AI research for each screened IPO (reusing recent results) "
            "and include it in the report and email. Needs LLM_ENABLED."
        ),
    )
    parser.add_argument(
        "--research-max-age",
        type=float,
        default=None,
        metavar="HOURS",
        help=(
            "Reuse completed research newer than this "
            "(default: RESEARCH_MAX_AGE_HOURS, 24). 0 always re-runs."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.main",
        description="Scrape, analyse, report and email IPO candidates.",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Override the SQLite database path for this command.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    scrape = subparsers.add_parser("scrape", help="Fetch and persist IPOs.")
    scrape.add_argument(
        "--source",
        choices=["all", *SCRAPERS],
        default="all",
        help="Source to scrape (default: all).",
    )
    scrape.set_defaults(func=_cmd_scrape)

    analyze = subparsers.add_parser(
        "analyze",
        help="Screen candidates and store deterministic analyses.",
    )
    _add_analysis_args(analyze)
    analyze.add_argument(
        "--json",
        action="store_true",
        help="Print the full analysis payload as JSON.",
    )
    analyze.set_defaults(func=_cmd_analyze)

    report = subparsers.add_parser(
        "report",
        help="Analyse candidates and generate a PDF report.",
    )
    _add_analysis_args(report)
    _add_report_args(report)
    report.set_defaults(func=_cmd_report)

    run = subparsers.add_parser(
        "run",
        help="Scrape, analyse, generate a report and optionally email it.",
    )
    run.add_argument(
        "--source",
        choices=["all", *SCRAPERS],
        default="all",
        help="Source to scrape (default: all).",
    )
    _add_analysis_args(run)
    _add_report_args(run)
    run.set_defaults(func=_cmd_run)

    research = subparsers.add_parser(
        "research",
        help="Run AI web research + multi-perspective review (needs LLM_ENABLED).",
    )
    research.add_argument(
        "ipo_id", type=int, nargs="?", help="IPO id (see the dashboard URL)."
    )
    research.add_argument(
        "--all-open",
        action="store_true",
        help="Research every IPO whose status is open, one after another.",
    )
    research.set_defaults(func=_cmd_research)

    serve = subparsers.add_parser(
        "serve",
        help="Run the FastAPI service (read-only + token-protected actions).",
    )
    serve.add_argument(
        "--host",
        default=config.API_HOST,
        help=f"Bind host (default: {config.API_HOST}).",
    )
    serve.add_argument(
        "--port",
        type=int,
        default=config.API_PORT,
        help=f"Bind port (default: {config.API_PORT}).",
    )
    serve.add_argument(
        "--reload",
        action="store_true",
        help="Auto-reload on code changes (development only).",
    )
    serve.set_defaults(func=_cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    config.setup_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
