"""The provider-agnostic AI contract.

Every AI provider — local (Ollama, LM Studio, llama.cpp) or cloud (OpenAI,
Anthropic, Gemini, OpenRouter, Groq, any OpenAI-compatible endpoint) —
implements :class:`LLMProvider`. Callers depend on this module only and never
import a vendor SDK, so switching providers is a config change.

Design rules (see the README section "Where AI is needed"):

* ``generate`` returns the model text plus provenance (provider, model, token
  usage). When ``response_schema`` is supplied the output must validate against
  that pydantic model or :class:`LLMResponseValidationError` is raised.
* AI never replaces deterministic filters or calculations; it only reads,
  explains and retrieves.
* The same validation helpers below run for local and cloud providers alike.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

Role = Literal["system", "user", "assistant"]


class LLMError(Exception):
    """Base class for every AI-layer failure."""


class UnknownProviderError(LLMError):
    """The configured provider name is not in the registry."""


class ProviderNotConfiguredError(LLMError):
    """The provider is missing required configuration (e.g. an API key)."""


class CloudDisabledError(LLMError):
    """A cloud provider was selected while ``LLM_ALLOW_CLOUD`` is false."""


class ProviderUnavailableError(LLMError):
    """The provider could not be reached or returned a transient failure."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class LLMResponseValidationError(LLMError):
    """The model output did not match the requested response schema."""


class LLMMessage:
    """One chat message in the provider-neutral format."""

    __slots__ = ("role", "content")

    def __init__(self, role: Role, content: str) -> None:
        self.role = role
        self.content = content

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"LLMMessage(role={self.role!r}, content={self.content[:40]!r}…)"


class TokenUsage:
    """Token accounting for one provider call (audit/provenance)."""

    __slots__ = ("input_tokens", "output_tokens")

    def __init__(
        self,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class LLMResponse:
    """A completed generation with full provenance."""

    __slots__ = (
        "text",
        "provider",
        "model",
        "usage",
        "finish_reason",
        "latency_seconds",
        "parsed",
    )

    def __init__(
        self,
        *,
        text: str,
        provider: str,
        model: str,
        usage: TokenUsage | None = None,
        finish_reason: str | None = None,
        latency_seconds: float | None = None,
        parsed: Any = None,
    ) -> None:
        self.text = text
        self.provider = provider
        self.model = model
        self.usage = usage
        self.finish_reason = finish_reason
        self.latency_seconds = latency_seconds
        self.parsed = parsed


class EmbeddingResponse:
    """Vectors returned by one embedding call."""

    __slots__ = ("vectors", "provider", "model", "usage")

    def __init__(
        self,
        *,
        vectors: list[list[float]],
        provider: str,
        model: str,
        usage: TokenUsage | None = None,
    ) -> None:
        self.vectors = vectors
        self.provider = provider
        self.model = model
        self.usage = usage


class ProviderHealth:
    """Result of a (cheap) provider availability check."""

    __slots__ = ("ok", "detail")

    def __init__(self, ok: bool, detail: str) -> None:
        self.ok = ok
        self.detail = detail


class ProviderCapabilities:
    """Feature flags so callers can degrade gracefully per provider."""

    __slots__ = (
        "json_mode",
        "tools",
        "embeddings",
        "vision",
        "streaming",
        "web_research",
        "context_window",
        "cost_usd_per_million_input",
        "cost_usd_per_million_output",
    )

    def __init__(
        self,
        *,
        json_mode: bool = False,
        tools: bool = False,
        embeddings: bool = False,
        vision: bool = False,
        streaming: bool = False,
        web_research: bool = False,
        context_window: int | None = None,
        cost_usd_per_million_input: float | None = None,
        cost_usd_per_million_output: float | None = None,
    ) -> None:
        self.json_mode = json_mode
        self.tools = tools
        self.embeddings = embeddings
        self.vision = vision
        self.streaming = streaming
        self.web_research = web_research
        self.context_window = context_window
        self.cost_usd_per_million_input = cost_usd_per_million_input
        self.cost_usd_per_million_output = cost_usd_per_million_output


class LLMProvider(ABC):
    """The contract every provider adapter implements.

    ``generate`` may raise :class:`ProviderUnavailableError` (network, 5xx,
    timeout) or :class:`ProviderNotConfiguredError` (auth). ``embed`` may raise
    :class:`ProviderNotConfiguredError` when the provider has no embeddings
    API. ``health`` must stay cheap — it backs ``GET /api/health``.
    """

    name: str = "unknown"
    model: str = ""
    is_cloud: bool = False

    @abstractmethod
    def generate(
        self,
        messages: list[LLMMessage],
        *,
        response_schema: type[BaseModel] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Run one completion and return the text with provenance.

        When ``response_schema`` is given, adapters must request structured
        output where the API supports it and validate with
        :func:`validate_against_schema` before returning; ``parsed`` on the
        response then holds the validated object.
        """

    @abstractmethod
    def embed(self, texts: list[str]) -> EmbeddingResponse:
        """Embed texts with the provider's embedding model."""

    @abstractmethod
    def health(self, timeout: float | None = None) -> ProviderHealth:
        """Cheap availability check; must not run a full generation."""

    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Report feature flags for this provider."""


# --- Shared validation (identical for local and cloud providers) -------------


def extract_json_object(text: str) -> Any:
    """Parse JSON out of a model response.

    Tolerates markdown code fences and surrounding prose, since local models
    frequently wrap JSON in them. Raises
    :class:`LLMResponseValidationError` when no JSON object can be recovered.
    """

    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fall back to the outermost braces — the model may have added prose.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMResponseValidationError(
                f"model output is not valid JSON: {exc}"
            ) from exc

    raise LLMResponseValidationError("model output contained no JSON object")


def validate_against_schema(text: str, schema: type[BaseModel]) -> BaseModel:
    """Validate model JSON output against a pydantic schema.

    The same check runs for every provider, so a cloud answer is validated
    exactly like a local one.
    """

    data = extract_json_object(text)
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        raise LLMResponseValidationError(
            f"model output failed {schema.__name__} validation: {exc}"
        ) from exc


__all__ = [
    "CloudDisabledError",
    "EmbeddingResponse",
    "LLMError",
    "LLMMessage",
    "LLMProvider",
    "LLMResponse",
    "LLMResponseValidationError",
    "ProviderCapabilities",
    "ProviderHealth",
    "ProviderNotConfiguredError",
    "ProviderUnavailableError",
    "Role",
    "TokenUsage",
    "UnknownProviderError",
    "extract_json_object",
    "validate_against_schema",
]
