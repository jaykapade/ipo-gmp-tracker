"""Provider registry and factory.

``create_provider`` is the only place that knows which adapter class belongs
to which provider name. Cloud providers (OpenAI, Anthropic, Gemini, OpenRouter,
Groq) require ``LLM_ALLOW_CLOUD`` to be enabled and an API key, so documents
never leave the machine by accident.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from src.llm.base import (
    CloudDisabledError,
    LLMProvider,
    ProviderNotConfiguredError,
    UnknownProviderError,
)
from src.llm.providers.anthropic import AnthropicProvider
from src.llm.providers.gemini import GeminiProvider
from src.llm.providers.null import NullProvider
from src.llm.providers.openai_compat import OpenAICompatibleProvider


@dataclass(frozen=True)
class ProviderSpec:
    """Static facts about a named provider."""

    kind: Literal["openai-compat", "anthropic", "gemini"]
    default_base_url: str
    is_cloud: bool


PROVIDER_SPECS: dict[str, ProviderSpec] = {
    # Local runtimes (OpenAI-compatible endpoints).
    "ollama": ProviderSpec("openai-compat", "http://localhost:11434/v1", False),
    "lmstudio": ProviderSpec("openai-compat", "http://localhost:1234/v1", False),
    "llamacpp": ProviderSpec("openai-compat", "http://localhost:8080/v1", False),
    "vllm": ProviderSpec("openai-compat", "http://localhost:8000/v1", False),
    "openai-compatible": ProviderSpec("openai-compat", "", False),
    # Cloud providers (explicit opt-in required).
    "openai": ProviderSpec("openai-compat", "https://api.openai.com/v1", True),
    "openrouter": ProviderSpec("openai-compat", "https://openrouter.ai/api/v1", True),
    "groq": ProviderSpec("openai-compat", "https://api.groq.com/openai/v1", True),
    "anthropic": ProviderSpec("anthropic", "https://api.anthropic.com", True),
    "gemini": ProviderSpec(
        "gemini", "https://generativelanguage.googleapis.com/v1beta", True
    ),
}

_KNOWN_PROVIDERS = ", ".join(sorted(PROVIDER_SPECS))


def is_cloud_provider(name: str) -> bool:
    """Return True when the provider sends data to a third-party cloud."""

    spec = PROVIDER_SPECS.get(name.lower().strip())
    return spec.is_cloud if spec is not None else False


def create_provider(
    name: str,
    *,
    model: str,
    base_url: str | None = None,
    api_key: str = "",
    timeout: float = 120.0,
    allow_cloud: bool = False,
    session: Any | None = None,
) -> LLMProvider:
    """Build a provider adapter by name.

    Raises :class:`UnknownProviderError` for unregistered names,
    :class:`CloudDisabledError` when a cloud provider is requested without
    ``allow_cloud`` and :class:`ProviderNotConfiguredError` when required
    configuration (API key, base URL) is missing.
    """

    key = name.lower().strip()
    spec = PROVIDER_SPECS.get(key)
    if spec is None:
        raise UnknownProviderError(
            f"unknown LLM provider {name!r}; known providers: {_KNOWN_PROVIDERS}"
        )

    if spec.is_cloud and not allow_cloud:
        raise CloudDisabledError(
            f"provider {key!r} is a cloud provider; set LLM_ALLOW_CLOUD=true "
            "to opt in before any document leaves this machine"
        )
    if spec.is_cloud and not api_key:
        raise ProviderNotConfiguredError(f"provider {key!r} requires LLM_API_KEY")

    resolved_base = (base_url or spec.default_base_url).strip()
    if not resolved_base:
        raise ProviderNotConfiguredError(
            f"provider {key!r} requires LLM_BASE_URL (it has no default)"
        )

    if spec.kind == "openai-compat":
        return OpenAICompatibleProvider(
            key,
            model=model,
            base_url=resolved_base,
            api_key=api_key,
            timeout=timeout,
            session=session,
            is_cloud=spec.is_cloud,
        )
    if spec.kind == "anthropic":
        return AnthropicProvider(
            model=model,
            base_url=resolved_base,
            api_key=api_key,
            timeout=timeout,
            session=session,
        )
    return GeminiProvider(
        model=model,
        base_url=resolved_base,
        api_key=api_key,
        timeout=timeout,
        session=session,
    )


__all__ = [
    "NullProvider",
    "ProviderSpec",
    "PROVIDER_SPECS",
    "create_provider",
    "is_cloud_provider",
]
