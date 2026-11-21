"""Tests for email subscribers: double opt-in, unsubscribe and the daily digest."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.config import LLMSettings
from src.database import db
from src.models.ipo import IPO
from src.reporting import subscribers
from src.reporting.emailer import EmailSettings, build_message
from src.utils.normalization import normalize_name

HEADERS = {"X-API-Token": "test-token"}


def _subscribe(email: str, db_path) -> str:
    db.set_subscribed(email, True, db_path=db_path)
    return next(r["token"] for r in db.list_confirmed_subscribers(db_path=db_path) if r["email"] == email)


def _open_ipo(name: str) -> IPO:
    return IPO(
        name=name,
        normalized_name=normalize_name(name),
        category="SME",
        status="Open",
        issue_price=100.0,
        close_date="2099-01-01",
        gmp=25.0,
        gmp_percent=25.0,
    )


@pytest.fixture
def api(tmp_path):
    app = create_app(
        db_path=tmp_path / "t.db",
        report_dir=tmp_path,
        api_token="test-token",
        llm_settings=LLMSettings(),
    )
    with TestClient(app) as client:
        yield client, tmp_path / "t.db"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Me@Example.COM ", "me@example.com"),
        ("no-at-sign", None),
        ("a@b", None),
        ("a@b.com\r\nBcc: x@y.com", None),
        ("<a@b.com>", None),
    ],
)
def test_normalize_email(raw, expected):
    assert subscribers.normalize_email(raw) == expected


def test_subscribe_toggle_and_unsubscribe_link(api):
    client, db_path = api

    def put(email, subscribed, headers=HEADERS):
        return client.put(
            "/api/subscribers", json={"email": email, "subscribed": subscribed}, headers=headers
        )

    assert put("a@b.com", True, headers={}).status_code == 401
    assert put("x", True).status_code == 422

    assert put("A@b.com", True).json() == {"subscribed": True}
    status = client.get("/api/subscribers", params={"email": "a@b.com"}, headers=HEADERS)
    assert status.json() == {"subscribed": True}
    (row,) = db.list_confirmed_subscribers(db_path=db_path)
    assert row["email"] == "a@b.com"

    assert put("a@b.com", False).json() == {"subscribed": False}
    assert db.list_confirmed_subscribers(db_path=db_path) == []
    put("a@b.com", True)  # back on; the token (in old emails) stays the same
    assert db.list_confirmed_subscribers(db_path=db_path) == [row]

    link = client.post("/api/subscribers/unsubscribe", json={"token": row["token"]}, headers=HEADERS)
    assert link.json() == {"subscribed": False}
    assert db.list_confirmed_subscribers(db_path=db_path) == []
    bad = client.post("/api/subscribers/unsubscribe", json={"token": "x" * 20}, headers=HEADERS)
    assert bad.status_code == 404


def test_daily_digest_goes_to_confirmed_subscribers_only(tmp_path, monkeypatch):
    db_path = tmp_path / "t.db"
    db.save_ipo_with_gmp(_open_ipo("<b>Bold</b> Ltd"), "test", db_path=db_path)
    confirmed = _subscribe("in@example.com", db_path)
    db.set_subscribed("off@example.com", False, db_path=db_path)

    calls = []
    monkeypatch.setattr(subscribers, "send_email", lambda **kw: calls.append(kw))
    settings = EmailSettings(host="h", sender="from@example.com")
    result = subscribers.send_daily_digest(db_path=db_path, settings=settings)

    assert (result.subscribers, result.sent, result.failed, result.open_ipos) == (1, 1, 0, 1)
    call = calls[0]
    assert call["settings"].recipients == ("in@example.com",)
    assert call["list_unsubscribe"].endswith(f"action=unsubscribe&token={confirmed}")
    assert "&lt;b&gt;Bold&lt;/b&gt; Ltd" in call["html"] and "<b>Bold</b>" not in call["html"]
    assert call["list_unsubscribe"] in call["body"]

    message = build_message(
        settings, subject="s", body="b", list_unsubscribe=call["list_unsubscribe"]
    )
    assert message["List-Unsubscribe"] == f"<{call['list_unsubscribe']}>"


def test_no_digest_without_open_ipos(tmp_path, monkeypatch):
    db_path = tmp_path / "t.db"
    _subscribe("in@example.com", db_path)
    monkeypatch.setattr(subscribers, "send_email", lambda **kw: pytest.fail("sent"))

    result = subscribers.send_daily_digest(db_path=db_path)

    assert result.sent == 0 and result.open_ipos == 0



def test_report_goes_to_confirmed_subscribers_with_attachment(tmp_path, monkeypatch):
    db_path = tmp_path / "t.db"
    token = _subscribe("in@example.com", db_path)
    db.set_subscribed("off@example.com", False, db_path=db_path)
    calls = []
    monkeypatch.setattr(subscribers, "send_email", lambda **kw: calls.append(kw))

    result = subscribers.send_report(
        subject="IPO report",
        build=lambda url: (f"text {url}", f"html {url}"),
        count=1,
        attachments=["report.pdf"],
        db_path=db_path,
    )

    assert (result.subscribers, result.sent, result.failed) == (1, 1, 0)
    assert len(calls) == 1
    call = calls[0]
    assert call["settings"].recipients == ("in@example.com",)
    assert call["attachments"] == ("report.pdf",)
    assert call["body"] == f"text {call['list_unsubscribe']}"
    assert call["list_unsubscribe"].endswith(f"token={token}")


def test_notify_research_sends_the_report_with_pdf(tmp_path, monkeypatch):
    from src import config
    from src.main import main

    db_path = tmp_path / "t.db"
    db.save_ipo_with_gmp(_open_ipo("Alpha Ltd"), "test", db_path=db_path)
    _subscribe("in@example.com", db_path)
    monkeypatch.setattr(config, "REPORT_OUTPUT_DIR", tmp_path / "reports")
    calls = []
    monkeypatch.setattr(subscribers, "send_email", lambda **kw: calls.append(kw))

    assert main(["--db-path", str(db_path), "notify", "--research"]) == 0

    (call,) = calls
    (pdf,) = call["attachments"]
    assert pdf.suffix == ".pdf" and pdf.is_file()
    assert "Alpha Ltd" in call["html"] and "Unsubscribe</a>" in call["html"]
    assert call["body"].endswith(f"Unsubscribe: {call['list_unsubscribe']}")

