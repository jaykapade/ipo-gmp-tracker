"""Always-unavailable provider used when AI is disabled or nothing resolves."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.llm.base import (
    EmbeddingResponse,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    ProviderCapabilities,
    ProviderHealth,
    ProviderUnavailableError,
)

if TYPE_CHECKING:
    pass


class NullProvider(LLMProvider):
    """Stand-in that fails every call with a clear reason.

    Used when ``LLM_ENABLED=false`` (the default) or when no configured
    provider is usable, so callers can catch one exception type and fall back
    to deterministic templates.
    """

    def __init__(self, reason: str = "no LLM provider configured") -> None:
        self.name = "null"
        self.model = ""
        self.reason = reason

    def generate(
        self,
        messages: list[LLMMessage],
        *,
        response_schema: type | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        raise ProviderUnavailableError(self.reason)

    def embed(self, texts: list[str]) -> EmbeddingResponse:
        raise ProviderUnavailableError(self.reason)

    def health(self, timeout: float | None = None) -> ProviderHealth:
        return ProviderHealth(ok=False, detail=self.reason)

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities()


__all__ = ["NullProvider"]
