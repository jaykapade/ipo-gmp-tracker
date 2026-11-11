"""Tests for the streaming chat endpoint."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from requests import ConnectionError

from src.api.chat import ChatRequest
from src.api.main import create_app
from src.config import LLMSettings
from src.database import db
from src.models.ipo import IPO
from src.utils.normalization import normalize_name


def make_ipo(name: str, *, gmp_percent: float, status: str = "Open") -> IPO:
    return IPO(
        name=name,
        normalized_name=normalize_name(name),
        category="SME",
        status=status,
        issue_price=100.0,
        issue_price_lower=95.0,
        issue_price_upper=100.0,
        estimated_listing_price=100.0 + gmp_percent,
        ipo_size_cr="50.00",
        sector="Packaging",
        exchange="NSE",
        subscription=3.0,
        pe=20.0,
        open_date="2026-01-01",
        close_date="2099-01-01",
        gmp=gmp_percent,
        gmp_percent=gmp_percent,
    )


def _sse_events(response: TestClient) -> list[dict]:
    """Parse Server-Sent Events from a streaming test response."""
    events: list[dict] = []
    current_type: str | None = None
    data_lines: list[str] = []

    for line in response.iter_lines():
        if line.startswith("event:"):
            current_type = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())
        elif line == "" and data_lines and current_type is not None:
            payload = "\n".join(data_lines)
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                parsed = {"raw": payload}
            events.append({"type": current_type, "data": parsed})
            current_type = None
            data_lines = []

    return events


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test.db"
    report_dir = tmp_path / "reports"

    db.save_ipo_with_gmp(
        make_ipo("Above Ltd", gmp_percent=30),
        "test",
        db_path=db_path,
    )
    db.save_ipo_with_gmp(
        make_ipo("Below Ltd", gmp_percent=5),
        "test",
        db_path=db_path,
    )
    db.save_ipo_with_gmp(
        make_ipo("Sunrise Packaging", gmp_percent=22),
        "test",
        db_path=db_path,
    )

    app = create_app(
        db_path=db_path,
        report_dir=report_dir,
        api_token="test-token",
        llm_settings=LLMSettings(),
    )

    with TestClient(app) as test_client:
        yield test_client


def test_chat_streams_answer_for_known_ipo(client):
    response = client.post("/api/chat", json={"message": "Tell me about Above Ltd"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _sse_events(response)
    types = [event["type"] for event in events]
    assert "thinking" in types
    assert any(t == "tool_call" for t in types)
    assert any(t == "tool_result" for t in types)
    assert any(t == "content" for t in types)

    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    done = done_events[0]["data"]
    assert done["refusal"] is False
    assert done["primary_ipo_id"] is not None
    assert done["data_as_of"] is not None
    assert len(done["citations"]) >= 1

    # The composed answer should mention GMP and the company name.
    content = "".join(
        e["data"].get("delta", "")
        for e in events
        if e["type"] == "content"
    )
    assert "Above Ltd" in content
    assert "30.0%" in content or "30%" in content


def test_chat_refuses_when_no_match(client):
    response = client.post(
        "/api/chat", json={"message": "Tell me about Nonexistent Corp"}
    )
    assert response.status_code == 200

    events = _sse_events(response)
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["data"]["refusal"] is True
    assert done_events[0]["data"]["primary_ipo_id"] is None

    content = "".join(
        e["data"].get("delta", "")
        for e in events
        if e["type"] == "content"
    )
    assert "couldn't find" in content.lower() or "empty" in content.lower()


def test_chat_requires_message(client):
    response = client.post("/api/chat", json={})
    assert response.status_code == 422


def test_chat_accepts_conversation_id(client):
    response = client.post(
        "/api/chat",
        json={"message": "Above Ltd", "conversation_id": "fixed-conv-1"},
    )
    assert response.status_code == 200
    events = _sse_events(response)
    done_events = [e for e in events if e["type"] == "done"]
    assert done_events[0]["data"]["conversation_id"] == "fixed-conv-1"


def test_chat_request_model_validation():
    valid = ChatRequest(message="hi")
    assert valid.message == "hi"
    assert valid.conversation_id is None

    with pytest.raises(ValidationError):
        ChatRequest(message="x" * 1001)


# --- AI provider integration -------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


class _FakeSession:
    def __init__(self, post=None):
        self._post = list(post or [])

    def post(self, url, json=None, headers=None, timeout=None):
        if not self._post:
            raise ConnectionError("connection refused (queue empty)")
        return self._post.pop(0)


def _completion(text: str) -> _FakeResponse:
    return _FakeResponse(
        payload={
            "choices": [
                {"message": {"role": "assistant", "content": text},
                 "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
    )


@pytest.fixture
def llm_app(tmp_path):
    """App factory with an AI-enabled chat over a fake provider session."""

    def build(*, post_responses):
        from src.llm import LLMClient

        db_path = tmp_path / "test.db"
        report_dir = tmp_path / "reports"
        db.save_ipo_with_gmp(
            make_ipo("Above Ltd", gmp_percent=30), "test", db_path=db_path
        )
        settings = LLMSettings(enabled=True, provider="ollama", model="test-model")
        app = create_app(
            db_path=db_path,
            report_dir=report_dir,
            api_token="test-token",
            llm_settings=settings,
        )
        app.state.llm = LLMClient(settings, session=_FakeSession(post_responses))
        return app

    return build


def test_chat_uses_configured_llm_when_available(llm_app):
    app = llm_app(post_responses=[_completion("Above Ltd carries a 30% premium.")])

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/chat", json={"message": "Tell me about Above Ltd"}
        )

    assert response.status_code == 200
    events = _sse_events(response)
    done = [e for e in events if e["type"] == "done"][0]["data"]

    assert done["refusal"] is False
    assert done["llm"]["used"] is True
    assert done["llm"]["provider"] == "ollama"
    assert done["llm"]["model"] == "test-model"

    content = "".join(
        e["data"].get("delta", "") for e in events if e["type"] == "content"
    )
    assert "Above Ltd carries a 30% premium." in content

    # The AI answer still cites the underlying whitelisted tool results.
    assert len(done["citations"]) >= 1


def test_chat_falls_back_to_deterministic_answer_when_llm_fails(llm_app):
    app = llm_app(post_responses=[])  # provider raises on every call

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/chat", json={"message": "Tell me about Above Ltd"}
        )

    assert response.status_code == 200
    events = _sse_events(response)
    done = [e for e in events if e["type"] == "done"][0]["data"]

    assert done["llm"]["used"] is False
    assert "reason" in done["llm"]

    content = "".join(
        e["data"].get("delta", "") for e in events if e["type"] == "content"
    )
    assert "Above Ltd" in content
    assert "30.0%" in content or "30%" in content
