"""Tests for persistence and the read helpers used by the analysis layer."""

from datetime import date

from src.analysis.analyzer import analyze_candidate
from src.analysis.filters import Candidate
from src.database import db
from src.models.ipo import IPO
from src.utils.normalization import normalize_name


def make_ipo(name: str, **overrides) -> IPO:
    values = {
        "name": name,
        "normalized_name": normalize_name(name),
        "category": "SME",
        "status": "Open",
        "issue_price": 100.0,
        "issue_price_lower": 95.0,
        "issue_price_upper": 100.0,
        "estimated_listing_price": 125.0,
        "ipo_size_cr": "50.00",
        "sector": "Packaging",
        "exchange": "NSE",
        "lot_size": "1,200 shares",
        "subscription": 2.5,
        "open_date": "2026-09-10",
        "close_date": "2026-09-14",
        "source_url": "https://example.test/ipo",
        "gmp": 25.0,
        "gmp_percent": 25.0,
    }
    values.update(overrides)
    return IPO(**values)


def test_save_ipo_with_gmp_persists_extended_fields(tmp_path):
    db_path = tmp_path / "test.db"

    ipo_id = db.save_ipo_with_gmp(make_ipo("Example Ltd"), "test", db_path=db_path)
    saved = db.get_ipo(ipo_id, db_path=db_path)

    assert saved is not None
    assert saved["name"] == "Example Ltd"
    assert saved["sector"] == "Packaging"
    assert saved["exchange"] == "NSE"
    assert saved["lot_size"] == "1,200 shares"
    assert saved["subscription"] == 2.5
    assert saved["issue_price_lower"] == 95.0
    assert saved["issue_price_upper"] == 100.0
    assert saved["source_url"] == "https://example.test/ipo"


def test_upsert_does_not_erase_fields_from_another_source(tmp_path):
    db_path = tmp_path / "test.db"

    ipo_id = db.save_ipo_with_gmp(make_ipo("Example Ltd"), "source-a", db_path=db_path)
    db.save_ipo_with_gmp(
        make_ipo("Example Ltd", sector=None, lot_size=None, subscription=None),
        "source-b",
        db_path=db_path,
    )

    saved = db.get_ipo(ipo_id, db_path=db_path)

    assert saved is not None
    assert saved["sector"] == "Packaging"
    assert saved["lot_size"] == "1,200 shares"
    assert saved["subscription"] == 2.5


def test_get_candidates_returns_latest_gmp_and_derives_percent(tmp_path):
    db_path = tmp_path / "test.db"

    # Explicit percentage above the threshold.
    db.save_ipo_with_gmp(make_ipo("Above Ltd", gmp=30.0, gmp_percent=30.0), "test", db_path=db_path)
    # Below the threshold.
    db.save_ipo_with_gmp(make_ipo("Below Ltd", gmp=5.0, gmp_percent=5.0), "test", db_path=db_path)
    # No percentage, but issue price allows deriving it: 25 / 100 = 25%.
    db.save_ipo_with_gmp(make_ipo("Derived Ltd", gmp=25.0, gmp_percent=None), "test", db_path=db_path)

    candidates = db.get_candidates(20.0, db_path=db_path)
    names = {row["name"] for row in candidates}

    assert names == {"Above Ltd", "Derived Ltd"}

    derived = next(row for row in candidates if row["name"] == "Derived Ltd")
    assert derived["latest_gmp_percent"] == 25.0
    assert derived["latest_gmp_percent_derived"] == 1


def test_get_gmp_history_is_newest_first(tmp_path):
    db_path = tmp_path / "test.db"

    ipo_id = db.get_or_create_ipo(make_ipo("Example Ltd"), db_path=db_path)
    db.save_gmp(
        ipo_id,
        gmp=10.0,
        gmp_percent=10.0,
        source="source",
        recorded_at="2026-09-01T00:00:00+00:00",
        db_path=db_path,
    )
    db.save_gmp(
        ipo_id,
        gmp=20.0,
        gmp_percent=20.0,
        source="source",
        recorded_at="2026-09-02T00:00:00+00:00",
        db_path=db_path,
    )

    history = db.get_gmp_history(ipo_id, db_path=db_path)

    assert [row["gmp"] for row in history[:2]] == [20.0, 10.0]


def test_analysis_report_round_trip(tmp_path):
    db_path = tmp_path / "test.db"

    ipo_id = db.save_ipo_with_gmp(make_ipo("Example Ltd"), "test", db_path=db_path)
    candidate = Candidate(
        ipo=db.get_ipo(ipo_id, db_path=db_path),
        latest_gmp=db.get_gmp_history(ipo_id, db_path=db_path)[0],
        history=db.get_gmp_history(ipo_id, db_path=db_path),
        close_date=date(2026, 9, 14),
    )

    analysis = analyze_candidate(candidate, today=date(2026, 9, 12))
    report_id = db.save_analysis_report(analysis, db_path=db_path)
    loaded = db.get_latest_analysis(ipo_id, db_path=db_path)

    assert report_id > 0
    assert loaded is not None
    assert loaded["ipo_id"] == ipo_id
    assert loaded["score"] == analysis.score
    assert loaded["verdict"] == analysis.verdict
