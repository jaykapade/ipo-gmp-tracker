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
    python -m src.main notify --dry-run            # daily digest to subscribers
    python -m src.main notify --research           # ...the full research report instead
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
from src.reporting.email_html import build_html_summary
from src.reporting.sources import collect_sources

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


def _write_report(
    run: AnalysisRun,
    research: dict | None,
    *,
    output: str | None,
    db_path: str | None,
):
    """Write the PDF; return ``(path, text, html(unsubscribe_url=None))`` for the email."""

    sources = collect_sources([analysis.ipo_id for analysis in run.analyses], db_path=db_path)
    summary = {
        "min_gmp_percent": run.min_gmp_percent,
        "include_upcoming": run.include_upcoming,
        "generated_at": run.generated_at,
        "research": research,
        "sources": sources,
    }
    path = generate_report(run.analyses, output_path=output, **summary)
    print(f"Report written: {path}")
    text = build_text_summary(run.analyses, **summary)
    return path, text, lambda unsubscribe_url=None: build_html_summary(
        run.analyses, unsubscribe_url=unsubscribe_url, **summary
    )


def _report_subject(run: AnalysisRun) -> str:
    return f"IPO report: {len(run.analyses)} candidate(s)"


def _report_and_maybe_email(
    args: argparse.Namespace,
    run: AnalysisRun,
    research: dict | None = None,
) -> None:
    path, body, html = _write_report(run, research, output=args.output, db_path=args.db_path)

    if not args.email:
        if args.dry_run:
            print("--dry-run has no effect without --email.")
        return

    result = send_email(
        subject=_report_subject(run),
        body=body,
        html=html(),
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


def _cmd_notify(args: argparse.Namespace) -> int:
    """Email confirmed subscribers the open-IPO digest, or with ``--research``
    the same report and PDF as ``run --research --email`` (stored research only)."""

    from src.reporting.subscribers import send_daily_digest, send_report

    if args.research:
        from src.database import db
        from src.research.digest import stored_digests

        run = analyze_pipeline(persist=False, db_path=args.db_path)
        subscribers = len(db.list_confirmed_subscribers(db_path=args.db_path))
        if not run.analyses or not subscribers:
            logger.info(
                "No research report sent: %d screened IPO(s), %d subscriber(s).",
                len(run.analyses),
                subscribers,
            )
            return 0
        research = stored_digests([a.ipo_id for a in run.analyses], db_path=args.db_path)
        path, text, html = _write_report(run, research, output=None, db_path=args.db_path)
        result = send_report(
            subject=_report_subject(run),
            build=lambda url: (f"{text}\n\nUnsubscribe: {url}", html(url)),
            count=len(run.analyses),
            attachments=[path],
            db_path=args.db_path,
            dry_run=args.dry_run,
        )
        what = "research report"
    else:
        result = send_daily_digest(db_path=args.db_path, dry_run=args.dry_run)
        what = "digest"
    verb = "Would send" if args.dry_run else "Sent"
    logger.info(
        "%s the %s (%d IPOs) to %d of %d subscriber(s); %d failed.",
        verb,
        what,
        result.open_ipos,
        result.sent,
        result.subscribers,
        result.failed,
    )
    return 1 if result.failed else 0


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

    notify = subparsers.add_parser(
        "notify",
        help="Email today's open IPOs and GMP to confirmed subscribers.",
    )
    notify.add_argument(
        "--dry-run",
        action="store_true",
        help="Build every email without sending it.",
    )
    notify.add_argument(
        "--research",
        action=argparse.BooleanOptionalAction,
        default=config.DIGEST_RESEARCH,
        help="Send the full research report and PDF instead of the digest "
        "(default: DIGEST_RESEARCH).",
    )
    notify.set_defaults(func=_cmd_notify)

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
    # Windows writes redirected output as cp1252, which cannot encode "₹".
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
