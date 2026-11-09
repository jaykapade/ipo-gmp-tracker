"""Tests for the scraper blueprint, typed errors and rate limiting."""

from __future__ import annotations

import pytest
import requests

from src.database import db
from src.models.ipo import IPO
from src.scrapers.base import payload_rows
from src.scrapers.errors import FetchError, ParseError
from src.scrapers.investorgain import InvestorGainScraper
from src.scrapers.ipowatch import IpoWatchScraper
from src.utils.http import RateLimiter


class FakeResponse:
    def __init__(self, payload=None, *, json_error=None):
        self._payload = payload
        self._json_error = json_error

    def raise_for_status(self):
        return None

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


class FakeSession:
    def __init__(self, response=None, *, error=None):
        self.response = response
        self.error = error
        self.calls = 0

    def get(self, url, timeout=None):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.response


def test_payload_rows_accepts_a_plain_list():
    assert payload_rows([1, 2]) == [1, 2]


def test_payload_rows_reads_the_first_matching_key():
    assert payload_rows({"data": [1]}, "data", "result") == [1]
    assert payload_rows({"result": [2]}, "data", "result") == [2]


def test_payload_rows_raises_parse_error_for_unknown_shape():
    with pytest.raises(ParseError, match="unexpected payload"):
        payload_rows({"message": "captcha"})


def test_get_json_wraps_a_non_json_body():
    scraper = IpoWatchScraper(
        session=FakeSession(FakeResponse(json_error=ValueError("html"))),
        request_delay=0,
    )

    with pytest.raises(FetchError, match="not valid JSON"):
        scraper.fetch()


def test_get_json_wraps_a_network_error():
    scraper = IpoWatchScraper(
        session=FakeSession(error=requests.ConnectionError("offline")),
        request_delay=0,
    )

    with pytest.raises(FetchError, match="request failed"):
        scraper.fetch()


def test_ipowatch_scrape_returns_models():
    session = FakeSession(FakeResponse({"data": [{"id": 1, "name": "Example Ltd"}]}))
    scraper = IpoWatchScraper(session=session, request_delay=0)

    ipos = scraper.scrape()

    assert session.calls == 1
    assert [ipo.name for ipo in ipos] == ["Example Ltd"]


def test_investorgain_rows_reads_report_table_data():
    scraper = InvestorGainScraper(request_delay=0)

    rows = scraper.rows({"reportTableData": [{"~ipo_name": "Example Ltd"}]})

    assert rows == [{"~ipo_name": "Example Ltd"}]


def test_scraper_save_records_provenance(tmp_path):
    db_path = tmp_path / "test.db"
    scraper = IpoWatchScraper(session=FakeSession(), request_delay=0)
    ipo = IPO(
        name="Example Ltd",
        normalized_name="example",
        ipo_id=42,
        source_url="https://example.test/ipo",
    )

    ipo_id = scraper.save(ipo, db_path=db_path)
    sources = db.get_ipo_sources(ipo_id, db_path=db_path)

    assert len(sources) == 1
    assert sources[0]["source"] == "IPO Watch"
    assert sources[0]["source_ipo_id"] == "42"
    assert sources[0]["source_url"] == "https://example.test/ipo"


def test_rate_limiter_first_call_never_sleeps(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(
        "src.utils.http.time.sleep",
        lambda seconds: slept.append(seconds),
    )

    limiter = RateLimiter(min_interval=10)

    assert limiter.wait() == 0.0
    assert slept == []


def test_rate_limiter_sleeps_between_calls(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(
        "src.utils.http.time.sleep",
        lambda seconds: slept.append(seconds),
    )

    limiter = RateLimiter(min_interval=10)
    limiter.wait()
    delay = limiter.wait()

    assert delay > 0
    assert slept and slept[0] > 0


def test_rate_limiter_can_be_disabled():
    limiter = RateLimiter(min_interval=0)

    assert limiter.wait() == 0.0
    assert limiter.wait() == 0.0
