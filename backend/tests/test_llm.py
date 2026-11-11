"""Tests for the provider-agnostic AI layer.

All provider adapters are exercised offline through a fake HTTP session that
records calls and returns canned payloads, so behaviour is deterministic and
no local model runtime or cloud API key is needed.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from requests import ConnectionError

from src.config import LLMSettings
from src.llm import (
    CloudDisabledError,
    LLMClient,
    LLMMessage,
    LLMResponseValidationError,
    NullProvider,
    ProviderNotConfiguredError,
    ProviderUnavailableError,
    UnknownProviderError,
    create_provider,
    extract_json_object,
)
from src.llm.base import validate_against_schema

# --- Fakes -------------------------------------------------------------------


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


class FakeSession:
    """Canned-response session; raises when the queue runs dry."""

    def __init__(self, *, post=None, get=None):
        self._post = list(post or [])
        self._get = list(get or [])
        self.calls: list[tuple[str, str, dict | None]] = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append(("POST", url, json))
        return self._next(self._post)

    def get(self, url, headers=None, timeout=None):
        self.calls.append(("GET", url, None))
        return self._next(self._get)

    def _next(self, queue):
        if not queue:
            raise ConnectionError("connection refused (queue empty)")
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def chat_completion(text: str, *, model: str = "test-model") -> FakeResponse:
    return FakeResponse(
        payload={
            "choices": [
                {
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 12, "completion_tokens": 34},
            "model": model,
        }
    )


class Verdict(BaseModel):
    verdict: str
    score: int


# --- Shared validation -------------------------------------------------------


def test_extract_json_object_tolerates_fences_and_prose():
    assert extract_json_object('{"a": 1}') == {"a": 1}
    assert extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json_object('Sure! {"a": 1} hope that helps') == {"a": 1}
    with pytest.raises(LLMResponseValidationError):
        extract_json_object("no json here")


def test_validate_against_schema_rejects_wrong_shape():
    parsed = validate_against_schema('{"verdict": "Watch", "score": 40}', Verdict)
    assert parsed.verdict == "Watch"
    with pytest.raises(LLMResponseValidationError):
        validate_against_schema('{"verdict": "Watch"}', Verdict)


# --- Factory and cloud safety ------------------------------------------------


def test_unknown_provider_raises():
    with pytest.raises(UnknownProviderError):
        create_provider("not-a-provider", model="m", base_url="http://x")


def test_cloud_providers_require_opt_in():
    with pytest.raises(CloudDisabledError):
        create_provider("openai", model="gpt-4o-mini", api_key="k", allow_cloud=False)
    with pytest.raises(ProviderNotConfiguredError):
        create_provider("openai", model="gpt-4o-mini", allow_cloud=True)  # no api key


def test_openai_compatible_requires_base_url():
    with pytest.raises(ProviderNotConfiguredError):
        create_provider("openai-compatible", model="m")


def test_is_cloud_provider():
    from src.llm import is_cloud_provider

    assert is_cloud_provider("openai")
    assert is_cloud_provider("Anthropic")
    assert not is_cloud_provider("ollama")
    assert not is_cloud_provider("lmstudio")


# --- NullProvider ------------------------------------------------------------


def test_null_provider_fails_every_call():
    provider = NullProvider("LLM_ENABLED=false; deterministic mode")

    with pytest.raises(ProviderUnavailableError):
        provider.generate([LLMMessage("user", "hi")])
    with pytest.raises(ProviderUnavailableError):
        provider.embed(["hi"])
    assert provider.health().ok is False
    capabilities = provider.capabilities()
    assert capabilities.json_mode is False
    assert capabilities.tools is False
    assert capabilities.embeddings is False


# --- OpenAI-compatible adapter ----------------------------------------------


def make_ollama(session) -> object:
    return create_provider(
        "ollama",
        model="test-model",
        base_url="http://localhost:11434/v1",
        session=session,
    )


def test_openai_compat_generate_and_payload():
    session = FakeSession(post=[chat_completion("hello world")])
    provider = make_ollama(session)

    response = provider.generate(
        [LLMMessage("system", "be brief"), LLMMessage("user", "hi")],
        temperature=0.2,
    )

    assert response.text == "hello world"
    assert response.provider == "ollama"
    assert response.model == "test-model"
    assert response.usage.input_tokens == 12
    assert response.usage.output_tokens == 34
    assert response.parsed is None

    method, url, payload = session.calls[0]
    assert method == "POST"
    assert url == "http://localhost:11434/v1/chat/completions"
    assert payload["model"] == "test-model"
    assert payload["temperature"] == 0.2
    assert payload["messages"] == [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "hi"},
    ]


def test_openai_compat_generate_with_schema_uses_json_mode():
    session = FakeSession(post=[chat_completion('{"verdict": "Strong", "score": 80}')])
    provider = make_ollama(session)

    response = provider.generate(
        [LLMMessage("user", "analyse")], response_schema=Verdict
    )

    assert response.parsed == Verdict(verdict="Strong", score=80)
    assert session.calls[0][2]["response_format"] == {"type": "json_object"}


def test_openai_compat_retries_without_response_format_on_400():
    session = FakeSession(
        post=[
            FakeResponse(
                status_code=400, payload={"error": {"message": "response_format"}}
            ),
            chat_completion('{"verdict": "Watch", "score": 50}'),
        ]
    )
    provider = make_ollama(session)

    response = provider.generate(
        [LLMMessage("user", "analyse")], response_schema=Verdict
    )

    assert response.parsed.verdict == "Watch"
    first_payload, second_payload = session.calls[0][2], session.calls[1][2]
    assert "response_format" in first_payload
    assert "response_format" not in second_payload


def test_openai_compat_maps_auth_errors():
    session = FakeSession(
        post=[FakeResponse(status_code=401, payload={"error": {"message": "bad key"}})]
    )
    provider = make_ollama(session)

    with pytest.raises(ProviderNotConfiguredError):
        provider.generate([LLMMessage("user", "hi")])


def test_openai_compat_embed():
    session = FakeSession(
        post=[
            FakeResponse(
                payload={
                    "data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}],
                    "usage": {"prompt_tokens": 8, "total_tokens": 8},
                }
            )
        ]
    )
    provider = make_ollama(session)

    embedding = provider.embed(["alpha", "beta"])

    assert embedding.vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert embedding.provider == "ollama"
    method, url, payload = session.calls[0]
    assert method == "POST"
    assert url.endswith("/embeddings")
    assert payload["input"] == ["alpha", "beta"]


def test_openai_compat_health():
    ok = make_ollama(FakeSession(get=[FakeResponse(payload={"data": []})]))
    assert ok.health().ok is True

    down = make_ollama(FakeSession(get=[]))
    health = down.health()
    assert health.ok is False
    assert "connection refused" in health.detail


# --- Anthropic adapter --------------------------------------------------------


def make_anthropic(session) -> object:
    return create_provider(
        "anthropic",
        model="claude-test",
        api_key="key",
        allow_cloud=True,
        session=session,
    )


def test_anthropic_generate_separates_system_and_requires_max_tokens():
    session = FakeSession(
        post=[
            FakeResponse(
                payload={
                    "content": [{"type": "text", "text": "answer"}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 5, "output_tokens": 7},
                }
            )
        ]
    )
    provider = make_anthropic(session)

    response = provider.generate(
        [LLMMessage("system", "sys"), LLMMessage("user", "q")],
        temperature=0.0,
    )

    assert response.text == "answer"
    assert response.finish_reason == "end_turn"
    assert response.usage.input_tokens == 5

    method, url, payload = session.calls[0]
    assert method == "POST"
    assert url == "https://api.anthropic.com/v1/messages"
    assert payload["system"] == "sys"
    assert payload["messages"] == [{"role": "user", "content": "q"}]
    assert payload["max_tokens"] > 0  # mandatory for Anthropic


def test_anthropic_has_no_embeddings_and_no_network_health():
    provider = make_anthropic(FakeSession())

    with pytest.raises(ProviderNotConfiguredError):
        provider.embed(["text"])

    assert provider.health().ok is True  # key present, no probe
    assert provider.capabilities().embeddings is False


# --- Gemini adapter -----------------------------------------------------------


def make_gemini(session) -> object:
    return create_provider(
        "gemini",
        model="gemini-test",
        api_key="key",
        allow_cloud=True,
        session=session,
    )


def test_gemini_generate_and_json_mime_type():
    session = FakeSession(
        post=[
            FakeResponse(
                payload={
                    "candidates": [
                        {
                            "content": {
                                "parts": [{"text": '{"verdict": "Watch", "score": 55}'}]
                            },
                            "finishReason": "STOP",
                        }
                    ],
                    "usageMetadata": {
                        "promptTokenCount": 3,
                        "candidatesTokenCount": 4,
                    },
                }
            )
        ]
    )
    provider = make_gemini(session)

    response = provider.generate(
        [LLMMessage("system", "sys"), LLMMessage("user", "q")],
        response_schema=Verdict,
    )

    assert response.parsed == Verdict(verdict="Watch", score=55)
    assert response.finish_reason == "STOP"
    assert response.usage.input_tokens == 3

    method, url, payload = session.calls[0]
    assert url.endswith("/models/gemini-test:generateContent")
    assert payload["systemInstruction"] == {"parts": [{"text": "sys"}]}
    assert payload["contents"] == [{"role": "user", "parts": [{"text": "q"}]}]
    assert payload["generationConfig"]["responseMimeType"] == "application/json"


def test_gemini_embed_uses_batch_contents():
    session = FakeSession(
        post=[
            FakeResponse(payload={"embeddings": [{"values": [1.0]}, {"values": [2.0]}]})
        ]
    )
    provider = make_gemini(session)

    embedding = provider.embed(["a", "b"])

    assert embedding.vectors == [[1.0], [2.0]]
    method, url, payload = session.calls[0]
    assert url.endswith("/models/gemini-test:batchEmbedContents")
    assert len(payload["requests"]) == 2


# --- Client: resolution, fallback, caching ------------------------------------


def test_disabled_client_fails_fast_and_reports_status():
    client = LLMClient(LLMSettings())

    assert client.enabled is False
    with pytest.raises(ProviderUnavailableError):
        client.generate([LLMMessage("user", "hi")])
    with pytest.raises(ProviderUnavailableError):
        client.embed(["hi"])

    status = client.status()
    assert status["enabled"] is False
    assert status["available"] is False
    assert "LLM_ENABLED=false" in status["detail"]


def test_client_walks_fallback_chain():
    settings = LLMSettings(
        enabled=True,
        provider="ollama",
        model="primary-model",
        fallback_providers=("lmstudio",),
    )
    session = FakeSession(
        post=[
            ConnectionError("primary down"),
            chat_completion("from fallback", model="primary-model"),
        ]
    )
    client = LLMClient(settings, session=session)

    response = client.generate([LLMMessage("user", "hi")])

    assert response.text == "from fallback"
    urls = [call[1] for call in session.calls]
    assert urls[0].startswith("http://localhost:11434")
    assert urls[1].startswith("http://localhost:1234")


def test_client_never_falls_back_to_cloud_without_opt_in():
    settings = LLMSettings(
        enabled=True,
        provider="ollama",
        fallback_providers=("openai",),
        allow_cloud=False,
    )
    session = FakeSession(post=[ConnectionError("primary down")])
    client = LLMClient(settings, session=session)

    with pytest.raises(ProviderUnavailableError) as excinfo:
        client.generate([LLMMessage("user", "hi")])

    # Only the local primary was contacted; the cloud fallback was skipped.
    assert len(session.calls) == 1
    assert "all LLM providers failed" in str(excinfo.value)


def test_client_cloud_fallback_works_when_allowed():
    settings = LLMSettings(
        enabled=True,
        provider="ollama",
        api_key="k",
        fallback_providers=("openai",),
        allow_cloud=True,
    )
    session = FakeSession(
        post=[
            ConnectionError("primary down"),
            chat_completion("from cloud"),
        ]
    )
    client = LLMClient(settings, session=session)

    response = client.generate([LLMMessage("user", "hi")])

    assert response.text == "from cloud"
    assert session.calls[1][1].startswith("https://api.openai.com")


def test_client_caches_identical_generations():
    settings = LLMSettings(enabled=True, provider="ollama")
    session = FakeSession(post=[chat_completion("once"), chat_completion("again")])
    client = LLMClient(settings, session=session)

    first = client.generate([LLMMessage("user", "hi")], prompt_version="chat-v1")
    second = client.generate([LLMMessage("user", "hi")], prompt_version="chat-v1")

    assert first is second
    assert len(session.calls) == 1

    # A different prompt version or message must bypass the cache.
    client.generate([LLMMessage("user", "hi")], prompt_version="chat-v2")
    assert len(session.calls) == 2


def test_client_status_reports_unreachable_primary():
    settings = LLMSettings(enabled=True, provider="ollama")
    client = LLMClient(settings, session=FakeSession(get=[]))

    status = client.status()
    assert status["enabled"] is True
    assert status["available"] is False
    assert "connection refused" in status["detail"]


def test_client_status_reports_cloud_gated_primary():
    settings = LLMSettings(enabled=True, provider="openai", api_key="k")
    client = LLMClient(settings)

    status = client.status()
    assert status["available"] is False
    assert "LLM_ALLOW_CLOUD" in status["detail"]


def test_client_embed_uses_separate_provider():
    settings = LLMSettings(
        enabled=True,
        provider="ollama",
        embed_provider="lmstudio",
        embed_model="embed-x",
    )
    session = FakeSession(
        post=[
            FakeResponse(payload={"data": [{"embedding": [0.5]}]}),
        ]
    )
    client = LLMClient(settings, session=session)

    embedding = client.embed(["hello"])

    assert embedding.model == "embed-x"
    assert session.calls[0][1].startswith("http://localhost:1234")


def test_client_embed_reuses_chat_base_url_for_same_provider():
    settings = LLMSettings(
        enabled=True,
        provider="ollama",
        base_url="http://custom:9999/v1",
        embed_provider="ollama",
        embed_model="embed-x",
    )
    session = FakeSession(post=[FakeResponse(payload={"data": [{"embedding": [0.5]}]})])
    client = LLMClient(settings, session=session)

    client.embed(["hello"])

    assert session.calls[0][1].startswith("http://custom:9999")


# --- Config -------------------------------------------------------------------


def test_llm_settings_from_env(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER", "Anthropic")
    monkeypatch.setenv("LLM_BASE_URL", "https://proxy.example")
    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_MODEL", "claude-x")
    monkeypatch.setenv("LLM_EMBED_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_EMBED_MODEL", "nomic-embed-text")
    monkeypatch.setenv("LLM_EMBED_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_FALLBACK_PROVIDERS", "ollama, lmstudio")
    monkeypatch.setenv("LLM_ALLOW_CLOUD", "1")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.3")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("LLM_MAX_CONTEXT", "4096")
    monkeypatch.setenv("LLM_CACHE", "false")

    settings = LLMSettings.from_env()

    assert settings.enabled is True
    assert settings.provider == "anthropic"
    assert settings.base_url == "https://proxy.example"
    assert settings.api_key == "secret"
    assert settings.model == "claude-x"
    assert settings.embed_provider == "ollama"
    assert settings.embed_model == "nomic-embed-text"
    assert settings.embed_base_url == "http://localhost:11434/v1"
    assert settings.fallback_providers == ("ollama", "lmstudio")
    assert settings.allow_cloud is True
    assert settings.temperature == 0.3
    assert settings.timeout_seconds == 45.0
    assert settings.max_context == 4096
    assert settings.cache is False
