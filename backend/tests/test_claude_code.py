"""Offline tests for the Claude-subscription provider, role routing and rerank.

The ``claude`` CLI is replaced by a fake runner that records each invocation
and returns canned ``CompletedProcess`` objects, so no subscription, network
or installed CLI is needed.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time

import pytest
from pydantic import BaseModel

from src.config import LLMSettings, RoleOverride
from src.llm import (
    CloudDisabledError,
    IdentityReranker,
    LLMClient,
    LLMMessage,
    LLMReranker,
    ProviderNotConfiguredError,
    ProviderUnavailableError,
    create_provider,
    create_reranker,
)
from src.llm.providers.claude_code import ClaudeCodeProvider, render_transcript

# --- Fakes -------------------------------------------------------------------


def completed(payload=None, *, returncode=0, stdout=None, stderr=""):
    if stdout is None:
        stdout = json.dumps(payload) if payload is not None else ""
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


def cli_result(text, *, structured=None, is_error=False, usage=None):
    body = {
        "type": "result",
        "subtype": "error" if is_error else "success",
        "is_error": is_error,
        "result": text,
        "stop_reason": "end_turn",
        "usage": usage or {"input_tokens": 11, "output_tokens": 7},
    }
    if structured is not None:
        body["structured_output"] = structured
    return completed(body)


class FakeRunner:
    """Stands in for ``subprocess.run``; pops one canned result per call."""

    def __init__(self, *results):
        self.results = list(results)
        self.calls: list[dict] = []

    def __call__(self, command, **kwargs):
        self.calls.append({"command": command, **kwargs})
        if not self.results:
            raise AssertionError("FakeRunner: no canned result left")
        item = self.results.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def make_provider(runner, *, model="claude-sonnet-5-5", **kwargs):
    return create_provider(
        "claude-code",
        model=model,
        allow_cloud=True,
        runner=runner,
        **kwargs,
    )


def flag(command, name):
    return command[command.index(name) + 1]


class Verdict(BaseModel):
    verdict: str
    confidence: float


# --- Factory -----------------------------------------------------------------


def test_claude_code_requires_cloud_opt_in():
    with pytest.raises(CloudDisabledError):
        create_provider("claude-code", model="claude-sonnet-5-5")


def test_claude_code_needs_no_api_key_and_ignores_http_base_url():
    provider = create_provider(
        "claude-code",
        model="claude-sonnet-5-5",
        base_url="http://localhost:11434/v1",  # leftover Ollama URL
        allow_cloud=True,
        runner=FakeRunner(),
    )
    assert isinstance(provider, ClaudeCodeProvider)
    assert provider.is_cloud is True
    assert provider.binary == "claude"


def test_claude_code_missing_binary_is_not_configured(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _name: None)
    provider = create_provider(
        "claude-code", model="m", base_url="no-such-claude", allow_cloud=True
    )
    with pytest.raises(ProviderNotConfiguredError, match="not found"):
        provider.generate([LLMMessage("user", "hi")])


# --- Generation --------------------------------------------------------------


def test_generate_builds_headless_command_and_pipes_prompt(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "tok")
    runner = FakeRunner(cli_result("Above Ltd looks strong."))
    provider = make_provider(runner)

    response = provider.generate(
        [
            LLMMessage("system", "Be grounded."),
            LLMMessage("system", "Cite sources."),
            LLMMessage("user", "How is Above Ltd?"),
        ]
    )

    assert response.text == "Above Ltd looks strong."
    assert response.provider == "claude-code"
    assert response.model == "claude-sonnet-5-5"
    assert response.usage.input_tokens == 11
    assert response.usage.output_tokens == 7
    assert response.finish_reason == "end_turn"

    call = runner.calls[0]
    command = call["command"]
    assert command[0] == "claude"
    assert "-p" in command
    assert flag(command, "--output-format") == "json"
    assert flag(command, "--model") == "claude-sonnet-5-5"
    assert flag(command, "--tools") == ""
    assert flag(command, "--max-turns") == "1"
    assert flag(command, "--setting-sources") == ""
    assert "--no-session-persistence" in command
    assert "--strict-mcp-config" in command
    assert flag(command, "--system-prompt") == "Be grounded.\n\nCite sources."
    assert "--json-schema" not in command
    # Prompt goes on stdin, not argv.
    assert call["input"] == "How is Above Ltd?"
    assert "How is Above Ltd?" not in command
    # Subscription billing: API credentials never reach the CLI.
    assert "ANTHROPIC_API_KEY" not in call["env"]
    assert "ANTHROPIC_AUTH_TOKEN" not in call["env"]
    assert call["timeout"] == 120.0


def test_generate_with_schema_passes_json_schema_and_validates():
    runner = FakeRunner(
        cli_result(
            "ignored prose",
            structured={"verdict": "apply", "confidence": 0.8},
        )
    )
    provider = make_provider(runner)

    response = provider.generate(
        [LLMMessage("user", "Decide.")], response_schema=Verdict
    )

    assert response.parsed == Verdict(verdict="apply", confidence=0.8)
    command = runner.calls[0]["command"]
    schema = json.loads(flag(command, "--json-schema"))
    assert schema["required"] == ["verdict", "confidence"]
    assert int(flag(command, "--max-turns")) > 1


def test_generate_schema_falls_back_to_result_text():
    runner = FakeRunner(cli_result('{"verdict": "skip", "confidence": 0.4}'))
    provider = make_provider(runner)

    response = provider.generate(
        [LLMMessage("user", "Decide.")], response_schema=Verdict
    )
    assert response.parsed.verdict == "skip"


def test_render_transcript_labels_multi_turn_history():
    assert render_transcript([LLMMessage("user", "only")]) == "only"
    text = render_transcript(
        [
            LLMMessage("system", "sys"),
            LLMMessage("user", "q1"),
            LLMMessage("assistant", "a1"),
            LLMMessage("user", "q2"),
        ]
    )
    assert text == "User: q1\n\nAssistant: a1\n\nUser: q2"


@pytest.mark.parametrize(
    ("result", "error"),
    [
        (cli_result("rate limited", is_error=True), ProviderUnavailableError),
        (completed(returncode=1, stdout="", stderr="boom"), ProviderUnavailableError),
        (completed(stdout="not json"), ProviderUnavailableError),
        (
            completed(
                returncode=1, stdout="", stderr="Not logged in · Please run /login"
            ),
            ProviderNotConfiguredError,
        ),
        (subprocess.TimeoutExpired(cmd="claude", timeout=1), ProviderUnavailableError),
    ],
)
def test_generate_maps_failures(result, error):
    provider = make_provider(FakeRunner(result))
    with pytest.raises(error):
        provider.generate([LLMMessage("user", "hi")])


def test_embed_is_not_supported():
    provider = make_provider(FakeRunner())
    with pytest.raises(ProviderNotConfiguredError, match="no embeddings"):
        provider.embed(["x"])


def test_concurrency_gate_limits_parallel_cli_calls():
    active = 0
    peak = 0
    lock = threading.Lock()

    def slow_runner(command, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return cli_result("ok")

    provider = make_provider(slow_runner, max_concurrency=2)
    threads = [
        threading.Thread(
            target=provider.generate, args=([LLMMessage("user", f"q{i}")],)
        )
        for i in range(6)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert peak == 2


# --- Health ------------------------------------------------------------------


def test_health_reports_subscription_login():
    runner = FakeRunner(completed({"loggedIn": True, "authMethod": "claude.ai"}))
    health = make_provider(runner).health(timeout=3)

    assert health.ok is True
    assert "subscription" in health.detail
    assert runner.calls[0]["command"][1:] == ["auth", "status"]
    assert runner.calls[0]["timeout"] == 3


def test_health_reports_logged_out_and_api_key_logins():
    logged_out = make_provider(FakeRunner(completed({"loggedIn": False}))).health()
    assert logged_out.ok is False
    assert "claude auth login" in logged_out.detail

    api_login = make_provider(
        FakeRunner(completed({"loggedIn": True, "authMethod": "api_key"}))
    ).health()
    assert api_login.ok is True
    assert "not a subscription" in api_login.detail


# --- Role routing ------------------------------------------------------------


def subscription_settings(**overrides) -> LLMSettings:
    base = {
        "enabled": True,
        "provider": "claude-code",
        "model": "claude-sonnet-5-5",
        "allow_cloud": True,
        "roles": {
            "analyst": RoleOverride(model="claude-sonnet-5-5"),
            "verifier": RoleOverride(model="claude-opus-5-5"),
            "extractor": RoleOverride(model="claude-haiku-5-5"),
        },
    }
    base.update(overrides)
    return LLMSettings(**base)


def test_role_settings_from_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "claude-code")
    monkeypatch.setenv("LLM_MODEL", "claude-sonnet-5-5")
    monkeypatch.setenv("LLM_ROLE_VERIFIER_MODEL", "claude-opus-5-5")
    monkeypatch.setenv("LLM_ROLE_EXTRACTOR_PROVIDER", "Ollama")
    monkeypatch.setenv("LLM_ROLE_EXTRACTOR_MODEL", "qwen3.5:4b-q4_K_M")
    monkeypatch.setenv("LLM_ROLE_EXTRACTOR_FALLBACKS", "lmstudio")
    monkeypatch.setenv("LLM_ROLE_EMBEDDER_MODEL", "qwen3-embedding:0.6b")
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "3")
    monkeypatch.setenv("RERANK_PROVIDER", "LLM")
    for name in ("ANALYST", "CHALLENGER"):
        monkeypatch.delenv(f"LLM_ROLE_{name}_MODEL", raising=False)

    settings = LLMSettings.from_env()

    assert set(settings.roles) == {"verifier", "extractor"}
    assert settings.roles["extractor"].provider == "ollama"
    assert settings.roles["extractor"].fallback_providers == ("lmstudio",)
    assert settings.embed_model == "qwen3-embedding:0.6b"
    assert settings.max_concurrency == 3
    assert settings.rerank_provider == "llm"

    analyst = settings.for_role("analyst")
    assert (analyst.provider, analyst.model) == ("claude-code", "claude-sonnet-5-5")
    assert settings.for_role("verifier").model == "claude-opus-5-5"
    extractor = settings.for_role("extractor")
    assert (extractor.provider, extractor.model) == ("ollama", "qwen3.5:4b-q4_K_M")


def test_role_switching_provider_drops_global_base_url():
    settings = LLMSettings(
        enabled=True,
        provider="ollama",
        base_url="http://gpu-box:11434/v1",
        roles={
            "verifier": RoleOverride(provider="claude-code", model="claude-opus-5-5")
        },
    )
    assert settings.for_role("analyst").base_url == "http://gpu-box:11434/v1"
    assert settings.for_role("verifier").base_url is None
    with pytest.raises(ValueError, match="unknown LLM role"):
        settings.for_role("poet")


def test_for_role_routes_each_role_to_its_model():
    runner = FakeRunner(cli_result("analysis"), cli_result("verdict"))
    client = LLMClient(subscription_settings(), runner=runner)

    client.for_role("analyst").generate([LLMMessage("user", "a")])
    client.for_role("verifier").generate([LLMMessage("user", "v")])

    models = [flag(call["command"], "--model") for call in runner.calls]
    assert models == ["claude-sonnet-5-5", "claude-opus-5-5"]
    assert client.for_role("analyst") is client.for_role("analyst")


def test_challenger_is_skipped_until_configured():
    client = LLMClient(subscription_settings(), runner=FakeRunner())
    challenger = client.for_role("challenger")

    assert challenger.enabled is False
    with pytest.raises(ProviderUnavailableError, match="LLM_ROLE_CHALLENGER_MODEL"):
        challenger.generate([LLMMessage("user", "dispute")])

    roles = dict(subscription_settings().roles)
    roles["challenger"] = RoleOverride(model="claude-opus-5-5")
    configured = LLMClient(subscription_settings(roles=roles), runner=FakeRunner())
    assert configured.for_role("challenger").enabled is True


def test_fallback_entry_can_pin_a_local_model():
    settings = subscription_settings(fallback_providers=("ollama=qwen3.5:9b-q4_K_M",))
    client = LLMClient(settings, runner=FakeRunner())

    chain = client.for_role("analyst").provider_chain()

    assert [(p.name, p.model) for p in chain] == [
        ("claude-code", "claude-sonnet-5-5"),
        ("ollama", "qwen3.5:9b-q4_K_M"),
    ]
    # The fallback uses its own default URL, not the CLI path.
    assert chain[1].base_url == "http://localhost:11434/v1"


def test_status_reports_roles_with_one_probe_per_provider():
    runner = FakeRunner(completed({"loggedIn": True, "authMethod": "claude.ai"}))
    client = LLMClient(subscription_settings(), runner=runner)

    status = client.status()

    assert status["available"] is True
    assert status["rerank_provider"] == "llm"
    roles = status["roles"]
    assert set(roles) == {
        "analyst",
        "verifier",
        "extractor",
        "challenger",
        "researcher",
    }
    assert roles["verifier"]["model"] == "claude-opus-5-5"
    assert roles["extractor"]["available"] is True
    assert roles["challenger"]["enabled"] is False
    # Global + three enabled roles share one `claude auth status` call.
    assert len(runner.calls) == 1


# --- Rerank ------------------------------------------------------------------


def test_llm_reranker_orders_by_score_with_extractor_role():
    runner = FakeRunner(
        cli_result(
            "",
            structured={
                "scores": [
                    {"index": 0, "score": 2},
                    {"index": 1, "score": 9},
                    {"index": 2, "score": 2},
                    {"index": 7, "score": 10},  # out of range: ignored
                ]
            },
        )
    )
    client = LLMClient(subscription_settings(), runner=runner)
    reranker = create_reranker("llm", client)
    assert isinstance(reranker, LLMReranker)

    ranked = reranker.rerank("GMP trend", ["alpha", "beta", "gamma"], top_k=2)

    assert [(p.index, p.text, p.score) for p in ranked] == [
        (1, "beta", 9.0),
        (0, "alpha", 2.0),  # tie with gamma keeps retrieval order
    ]
    command = runner.calls[0]["command"]
    assert flag(command, "--model") == "claude-haiku-5-5"
    assert "--json-schema" in command


def test_llm_reranker_keeps_order_on_malformed_output():
    runner = FakeRunner(cli_result("not json at all"))
    client = LLMClient(subscription_settings(), runner=runner)

    ranked = create_reranker("llm", client).rerank("q", ["a", "b"])

    assert [p.text for p in ranked] == ["a", "b"]


def test_reranker_is_identity_when_ai_disabled_and_rejects_unknown():
    client = LLMClient(LLMSettings())
    assert isinstance(create_reranker("ollama-llm", client), IdentityReranker)
    assert create_reranker("llm", client).rerank("q", []) == []
    with pytest.raises(NotImplementedError):
        create_reranker("fastembed", client)
    with pytest.raises(ValueError):
        create_reranker("cohere", client)


# --- Researcher role (web research) ------------------------------------------


def test_researcher_inherits_extractor_and_enables_web_tools():
    settings = subscription_settings()
    researcher = settings.for_role("researcher")

    assert researcher.model == "claude-haiku-5-5"  # inherited from extractor
    assert researcher.web_research is True
    assert researcher.cache is False
    assert researcher.timeout_seconds >= settings.research_timeout_seconds

    roles = dict(settings.roles)
    roles["researcher"] = RoleOverride(model="claude-sonnet-5-5")
    assert subscription_settings(roles=roles).for_role("researcher").model == (
        "claude-sonnet-5-5"
    )


def test_researcher_command_allows_only_web_tools():
    runner = FakeRunner(cli_result("facts"))
    client = LLMClient(subscription_settings(research_max_turns=12), runner=runner)

    client.for_role("researcher").generate([LLMMessage("user", "research X")])

    command = runner.calls[0]["command"]
    assert flag(command, "--tools") == "WebSearch,WebFetch"
    assert flag(command, "--allowedTools") == "WebSearch,WebFetch"
    assert flag(command, "--max-turns") == "12"
    assert flag(command, "--model") == "claude-haiku-5-5"


def test_web_research_is_rejected_for_providers_without_tools():
    with pytest.raises(ProviderNotConfiguredError, match="web research"):
        create_provider("ollama", model="m", web_research=True, session=object())

    settings = LLMSettings(
        enabled=True,
        provider="ollama",
        roles={"extractor": RoleOverride(model="qwen3.5:4b-q4_K_M")},
    )
    researcher = LLMClient(settings).for_role("researcher")
    with pytest.raises(ProviderUnavailableError, match="web research"):
        researcher.generate([LLMMessage("user", "x")])
