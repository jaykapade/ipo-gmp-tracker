"""Native Anthropic adapter (Messages API).

Anthropic's API differs materially from the OpenAI shape (system prompt is a
top-level field, ``max_tokens`` is mandatory, text arrives in content blocks),
so it gets a native adapter rather than the OpenAI-compatible one. Anthropic
offers no embeddings API, so ``embed`` fails with
:class:`ProviderNotConfiguredError` and callers should configure a separate
``LLM_EMBED_PROVIDER``.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import requests

from src.llm.base import (
    EmbeddingResponse,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    ProviderCapabilities,
    ProviderHealth,
    ProviderNotConfiguredError,
    ProviderUnavailableError,
    TokenUsage,
    validate_against_schema,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

_ANTHROPIC_VERSION = "2023-06-01"
_DEFAULT_MAX_TOKENS = 2048


class AnthropicProvider(LLMProvider):
    """Adapter for ``POST {base_url}/v1/messages``."""

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        api_key: str,
        timeout: float = 120.0,
        session: Any | None = None,
    ) -> None:
        self.name = "anthropic"
        self.model = model
        self.is_cloud = True
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._session = session

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
        }

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/v1/messages"
        session = self._session if self._session is not None else requests.Session()
        try:
            response = session.post(
                url, json=payload, headers=self._headers(), timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise ProviderUnavailableError(f"anthropic: request failed: {exc}") from exc

        if response.status_code >= 400:
            try:
                body = response.json()
                detail = str(body.get("error", {}).get("message", ""))[:200]
            except Exception:  # noqa: BLE001 - best-effort error text
                detail = ""
            if response.status_code in (401, 403):
                raise ProviderNotConfiguredError(
                    f"anthropic: HTTP {response.status_code} {detail} "
                    "(check LLM_API_KEY)"
                )
            raise ProviderUnavailableError(
                f"anthropic: HTTP {response.status_code} {detail}",
                status_code=response.status_code,
            )

        try:
            return response.json()
        except ValueError as exc:
            raise ProviderUnavailableError(
                "anthropic: response was not valid JSON"
            ) from exc

    def generate(
        self,
        messages: list[LLMMessage],
        *,
        response_schema: type[BaseModel] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        system = "\n\n".join(
            message.content for message in messages if message.role == "system"
        )
        chat = [
            {"role": message.role, "content": message.content}
            for message in messages
            if message.role != "system"
        ]

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens if max_tokens is not None else _DEFAULT_MAX_TOKENS,
            "messages": chat,
        }
        if system:
            payload["system"] = system
        if temperature is not None:
            payload["temperature"] = temperature

        started = time.monotonic()
        body = self._request(payload)

        blocks = body.get("content") or []
        text = "".join(
            block.get("text", "") for block in blocks if block.get("type") == "text"
        )
        usage_raw = body.get("usage") or {}

        parsed = None
        if response_schema is not None:
            # No native JSON mode; the shared validator is the only gate.
            parsed = validate_against_schema(text, response_schema)

        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            usage=TokenUsage(
                input_tokens=usage_raw.get("input_tokens"),
                output_tokens=usage_raw.get("output_tokens"),
            ),
            finish_reason=body.get("stop_reason"),
            latency_seconds=time.monotonic() - started,
            parsed=parsed,
        )

    def embed(self, texts: list[str]) -> EmbeddingResponse:
        raise ProviderNotConfiguredError(
            "anthropic has no embeddings API; set LLM_EMBED_PROVIDER "
            "(e.g. ollama with nomic-embed-text)"
        )

    def health(self, timeout: float | None = None) -> ProviderHealth:
        # No free health endpoint; a 1-token probe costs money on every poll.
        if not self.api_key:
            return ProviderHealth(ok=False, detail="LLM_API_KEY not set")
        return ProviderHealth(
            ok=True,
            detail="configured; key present (availability not probed — "
            "Anthropic has no free health endpoint)",
        )

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            json_mode=False,
            tools=True,
            embeddings=False,
            vision=True,
            streaming=True,
            context_window=200_000,
        )


__all__ = ["AnthropicProvider"]
