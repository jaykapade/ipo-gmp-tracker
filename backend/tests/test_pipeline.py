"""Tests for the shared pipeline and the CLI wiring."""

import json

from src.database import db
from src.main import main
from src.models.ipo import IPO
from src.pipeline import analyses_as_json, analyze_pipeline
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
