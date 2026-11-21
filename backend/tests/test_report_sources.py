"""Tests for report sources: scraped market-data pages and research URLs."""

from __future__ import annotations

import pytest
from tests.test_report_research import _research
from tests.test_research import ScriptedCLI
from tests.test_research import db_path as _db_path  # noqa: F401 - fixture

from src import config
from src.database import db
from src.reporting import pdf
from src.reporting.pdf import generate_report
from src.reporting.sources import collect_sources, market_sources, research_sources
from src.reporting.summary import build_text_summary

db_path = _db_path


def test_research_sources_dedupes_skips_database_and_orders_official_first():
    links = research_sources(
        {
            "facts": [
                {"source_url": "https://news.example.com/a", "source_type": "secondary"},
                {"source_url": "https://news.example.com/a", "source_type": "secondary"},
                {"source_url": None, "source_type": "database"},
                {"source_url": "not-a-url", "source_type": "secondary"},
                {
                    "source_url": "https://nseindia.com/x",
                    "source_title": "NSE notice",
                    "source_type": "exchange",
                },
                {
                    "source_url": "https://sebi.gov.in/rhp.pdf",
                    "source_title": "RHP",
                    "source_type": "official",
                },
            ]
        }
    )
    assert [link.url for link in links] == [
        "https://sebi.gov.in/rhp.pdf",
        "https://nseindia.com/x",
        "https://news.example.com/a",
    ]
    assert links[0].label == "RHP"
    assert links[2].label == "https://news.example.com/a"  # no title -> URL
    assert research_sources(None) == []


def test_market_sources_use_page_urls_and_investorgain_board(db_path):
    ipo_id = db.list_ipos(limit=10, db_path=db_path)[0]["id"]
    db.record_ipo_source(
        ipo_id,
        "IPO Watch",
        source_ipo_id=1,
        source_url="https://ipowatch.in/x-ipo-details/",
        db_path=db_path,
    )
    db.record_ipo_source(ipo_id, "InvestorGain", source_ipo_id=2, db_path=db_path)

    links = market_sources(ipo_id, db_path=db_path)
    urls = [link.url for link in links]
    assert "https://ipowatch.in/x-ipo-details/" in urls
    assert config.INVESTORGAIN_PAGE_URL in urls
    assert all(link.kind == "market data" for link in links)
    # The fixture's "test" source has no URL and is left out.
    assert len(links) == 2


@pytest.fixture
def researched(db_path):
    ipo_id, digest = _research(db_path, ScriptedCLI())
    db.record_ipo_source(
        ipo_id,
        "IPO Watch",
        source_ipo_id=1,
        source_url="https://ipowatch.in/crystal-ipo-details/",
        db_path=db_path,
    )
    return db_path, ipo_id, digest


def test_digest_carries_research_sources(researched):
    _, _, digest = researched
    urls = [link.url for link in digest.sources]
    # The gatherer drops the duplicate fact, so only the RHP URL remains.
    assert urls == ["https://example.com/rhp.pdf"]
    assert digest.sources[0].kind == "official"


def test_pdf_and_email_list_sources(researched, tmp_path, monkeypatch):
    from tests.test_reporting import make_analysis

    path_db, ipo_id, digest = researched
    analysis = make_analysis().model_copy(update={"ipo_id": ipo_id})
    sources = collect_sources([ipo_id], db_path=path_db)

    text = build_text_summary(
        [analysis], min_gmp_percent=20, research={ipo_id: digest}, sources=sources
    )
    assert (
        "Source: IPO Watch (GMP, price, dates) -- "
        "https://ipowatch.in/crystal-ipo-details/"
    ) in text
    assert "AI research sources: 1 web page (all linked in the PDF)" in text

    seen: list[str] = []
    original = pdf._link_paragraphs
    monkeypatch.setattr(
        pdf,
        "_link_paragraphs",
        lambda link, styles: seen.append(link.url) or original(link, styles),
    )
    out = generate_report(
        [analysis],
        output_path=tmp_path / "sources.pdf",
        min_gmp_percent=20,
        research={ipo_id: digest},
        sources=sources,
    )
    data = out.read_bytes()
    assert data.startswith(b"%PDF")
    assert seen == [
        "https://ipowatch.in/crystal-ipo-details/",
        "https://example.com/rhp.pdf",
    ]
    assert b"https://example.com/rhp.pdf" in data  # clickable link annotation


def test_pdf_caps_research_sources(researched, tmp_path, monkeypatch):
    from dataclasses import replace

    from tests.test_reporting import make_analysis

    _, ipo_id, digest = researched
    extra = replace(digest.sources[0], url="https://news.example.com/a")
    digest.sources = [*digest.sources, extra]
    monkeypatch.setattr(pdf, "MAX_RESEARCH_SOURCES", 1)
    analysis = make_analysis().model_copy(update={"ipo_id": ipo_id})
    out = generate_report(
        [analysis], output_path=tmp_path / "cap.pdf", research={ipo_id: digest}
    )
    data = out.read_bytes()
    assert b"https://example.com/rhp.pdf" in data
    assert b"https://news.example.com/a" not in data
