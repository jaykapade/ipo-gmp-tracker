"""Tests for the shared pipeline and the CLI wiring."""

import json

from src.database import db
from src.main import main
from src.models.ipo import IPO
from src.pipeline import SCRAPERS, analyses_as_json, analyze_pipeline, scrape_sources
from src.scrapers.base import BaseScraper
from src.scrapers.errors import FetchError, ParseError
from src.utils.normalization import normalize_name


def make_ipo(name: str, **overrides) -> IPO:
    values = {
        "name": name,
        "normalized_name": normalize_name(name),
        "category": "SME",
        "status": "Open",
        "issue_price": 100.0,
        "estimated_listing_price": 130.0,
        "ipo_size_cr": "50.00",
        "sector": "Packaging",
        "subscription": 3.0,
        "pe": 20.0,
        "open_date": "2026-01-01",
        "close_date": "2099-01-01",
        "gmp": 30.0,
        "gmp_percent": 30.0,
    }
    values.update(overrides)
    return IPO(**values)


def test_analyze_pipeline_selects_and_persists(tmp_path):
    db_path = tmp_path / "test.db"
    ipo_id = db.save_ipo_with_gmp(make_ipo("Above Ltd"), "test", db_path=db_path)

    run = analyze_pipeline(
        min_gmp_percent=20,
        persist=True,
        db_path=db_path,
    )

    assert len(run.analyses) == 1
    assert run.analyses[0].name == "Above Ltd"
    assert run.analyses[0].verdict in {"Strong", "Watch", "Avoid"}

    saved = db.get_latest_analysis(ipo_id, db_path=db_path)
    assert saved is not None
    assert saved["ipo_id"] == ipo_id
    assert saved["score"] == run.analyses[0].score


def test_analyze_pipeline_applies_threshold(tmp_path):
    db_path = tmp_path / "test.db"
    db.save_ipo_with_gmp(
        make_ipo("Below Ltd", gmp=5.0, gmp_percent=5.0),
        "test",
        db_path=db_path,
    )

    run = analyze_pipeline(min_gmp_percent=20, db_path=db_path)

    assert run.analyses == []
    assert run.min_gmp_percent == 20


def test_analyze_pipeline_does_not_persist_when_disabled(tmp_path):
    db_path = tmp_path / "test.db"
    ipo_id = db.save_ipo_with_gmp(make_ipo("Above Ltd"), "test", db_path=db_path)

    run = analyze_pipeline(
        min_gmp_percent=20,
        persist=False,
        db_path=db_path,
    )

    assert len(run.analyses) == 1
    assert db.get_latest_analysis(ipo_id, db_path=db_path) is None


def test_analyses_as_json_is_parseable(tmp_path):
    db_path = tmp_path / "test.db"
    db.save_ipo_with_gmp(make_ipo("Above Ltd"), "test", db_path=db_path)

    run = analyze_pipeline(min_gmp_percent=20, db_path=db_path)
    payload = json.loads(analyses_as_json(run.analyses))

    assert payload[0]["name"] == "Above Ltd"
    assert "factors" in payload[0]
    assert "checklist" in payload[0]


def test_cli_analyze_json(tmp_path, capsys):
    db_path = tmp_path / "test.db"
    db.save_ipo_with_gmp(make_ipo("Above Ltd"), "test", db_path=db_path)

    exit_code = main(["--db-path", str(db_path), "analyze", "--json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    payload = json.loads(output)
    assert payload[0]["name"] == "Above Ltd"


class FakeScraper(BaseScraper):
    source_name = "Fake"

    def fetch(self):
        return {"data": [{"id": 1, "name": "Good Ltd"}, {"id": 2}]}

    def rows(self, payload):
        return payload["data"]

    def convert_row(self, row):
        name = row.get("name")
        if not name:
            raise ParseError("row has no name")
        return IPO(
            name=name,
            normalized_name=normalize_name(name),
            ipo_id=row["id"],
            status="Open",
            issue_price=100.0,
            gmp=30.0,
            gmp_percent=30.0,
        )


class FailingScraper(BaseScraper):
    source_name = "Failing"

    def fetch(self):
        raise FetchError("source is down")

    def rows(self, payload):
        return []

    def convert_row(self, row):
        raise AssertionError("should not be called")


def test_scrape_sources_isolates_bad_rows_and_records_provenance(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "test.db"
    monkeypatch.setitem(SCRAPERS, "fake", FakeScraper(request_delay=0))

    results = scrape_sources(["fake"], db_path=db_path)

    assert results[0].saved == 1
    assert results[0].failed == 1

    ipo = db.list_ipos(db_path=db_path)[0]
    sources = db.get_ipo_sources(ipo["id"], db_path=db_path)
    assert sources[0]["source"] == "Fake"
    assert sources[0]["source_ipo_id"] == "1"

    run = db.get_scrape_runs(db_path=db_path)[0]
    assert run["status"] == "completed"
    assert run["rows_scraped"] == 2
    assert run["rows_saved"] == 1
    assert run["rows_failed"] == 1


class DateStatusScraper(BaseScraper):
    source_name = "Dates"

    def fetch(self):
        return {}

    def rows(self, payload):
        return [{}]

    def convert_row(self, row):
        return IPO(
            name="Derived Status Ltd",
            normalized_name="derived_status",
            open_date="2000-01-01",
            close_date="2099-01-01",
            issue_price=100.0,
            gmp=30.0,
            gmp_percent=30.0,
        )


def test_scrape_sources_persists_a_derived_status(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setitem(SCRAPERS, "dates", DateStatusScraper(request_delay=0))

    results = scrape_sources(["dates"], db_path=db_path)

    assert results[0].saved == 1
    saved = db.list_ipos(db_path=db_path)[0]
    assert saved["status"] == "open"


def test_scrape_sources_closes_ipos_past_their_close_date(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    db.save_ipo_with_gmp(make_ipo("Ended Ltd", close_date="2020-01-01"), "test", db_path=db_path)
    db.save_ipo_with_gmp(make_ipo("Running Ltd"), "test", db_path=db_path)
    monkeypatch.setitem(SCRAPERS, "failing", FailingScraper(request_delay=0))

    scrape_sources(["failing"], db_path=db_path)

    statuses = {row["name"]: row["status"] for row in db.list_ipos(db_path=db_path)}
    assert statuses == {"Ended Ltd": "closed", "Running Ltd": "Open"}


def test_scrape_sources_marks_fetch_failure(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setitem(SCRAPERS, "failing", FailingScraper(request_delay=0))

    results = scrape_sources(["failing"], db_path=db_path)

    assert results[0].saved == 0
    assert results[0].errors == ["fetch failed: source is down"]

    run = db.get_scrape_runs(db_path=db_path)[0]
    assert run["status"] == "failed"
    assert "source is down" in run["error_message"]


def test_cli_report_writes_pdf(tmp_path, capsys):
    db_path = tmp_path / "test.db"
    output_path = tmp_path / "cli-report.pdf"
    db.save_ipo_with_gmp(make_ipo("Above Ltd"), "test", db_path=db_path)

    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "report",
            "--output",
            str(output_path),
            "--no-persist",
        ]
    )
    printed = capsys.readouterr().out

    assert exit_code == 0
    assert "Report written:" in printed
    assert output_path.exists()
    assert output_path.read_bytes().startswith(b"%PDF")
