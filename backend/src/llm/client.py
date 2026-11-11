"""Config-only provider resolution, fallback chain and response cache.

:class:`LLMClient` turns the ``LLM_*`` settings into a working provider
chain. Callers use ``generate``/``embed`` and never know which vendor served
the request; the response carries the provenance instead.

Safety rules implemented here:

* ``LLM_ENABLED=false`` (the default) makes every call fail fast with
  :class:`ProviderUnavailableError` so deterministic code paths take over.
* Cloud providers are only constructed when ``LLM_ALLOW_CLOUD`` is true, and
  a cloud fallback is always logged — never silent.
* Responses are cached (keyed by provider, model, prompt version, message
  hash and parameters) so identical questions do not re-bill or re-run.
"""

from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from src.llm.base import (
    EmbeddingResponse,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    ProviderNotConfiguredError,
    ProviderUnavailableError,
)
from src.llm.providers import create_provider
from src.llm.providers.null import NullProvider

if TYPE_CHECKING:
    from pydantic import BaseModel

    from src.config import LLMSettings

logger = logging.getLogger(__name__)

DEFAULT_CACHE_SIZE = 128

_CONSTRUCTION_ERRORS = (
    ProviderNotConfiguredError,
    ProviderUnavailableError,
)


class LLMClient:
    """Resolve providers from settings and run cached generations."""

    def __init__(self, settings: LLMSettings, *, session: Any | None = None) -> None:
        self.settings = settings
        self._session = session
        self._chain: list[LLMProvider] | None = None
        self._cache: OrderedDict[tuple[Any, ...], LLMResponse] = OrderedDict()

    # --- Resolution --------------------------------------------------------

    @property
    def enabled(self) -> bool:
        """Whether AI is switched on at all (``LLM_ENABLED``)."""

        return bool(self.settings.enabled)

    def provider_chain(self) -> list[LLMProvider]:
        """Return the chat provider chain, primary first."""

        if self._chain is None:
            self._chain = self._build_chain()
        return list(self._chain)

    def _build_chain(self) -> list[LLMProvider]:
        if not self.enabled:
            return [NullProvider("LLM_ENABLED=false; deterministic mode")]

        chain: list[LLMProvider] = []
        skipped: list[str] = []
        names = [self.settings.provider, *self.settings.fallback_providers]
        for name in names:
            try:
                chain.append(
                    create_provider(
                        name,
                        model=self.settings.model,
                        base_url=self.settings.base_url,
                        api_key=self.settings.api_key,
                        timeout=self.settings.timeout_seconds,
                        allow_cloud=self.settings.allow_cloud,
                        session=self._session,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - config errors, log and skip
                skipped.append(f"{name}: {exc}")
                logger.warning("Skipping LLM provider %r: %s", name, exc)

        if not chain:
            return [NullProvider("; ".join(skipped) or "no providers configured")]
        return chain

    def primary_provider(self) -> LLMProvider:
        """Return the configured primary chat provider (or the null one)."""

        return self.provider_chain()[0]

    def embed_provider(self) -> LLMProvider:
        """Return the (separately configured) embedding provider."""

        if not self.enabled:
            return NullProvider("LLM_ENABLED=false; deterministic mode")

        base_url = self.settings.embed_base_url
        if base_url is None and self.settings.embed_provider == self.settings.provider:
            # Reuse the chat base URL when both roles use the same provider.
            base_url = self.settings.base_url

        try:
            return create_provider(
                self.settings.embed_provider,
                model=self.settings.embed_model,
                base_url=base_url,
                api_key=self.settings.api_key,
                timeout=self.settings.timeout_seconds,
                allow_cloud=self.settings.allow_cloud,
                session=self._session,
            )
        except Exception as exc:  # noqa: BLE001 - config errors, log and skip
            logger.warning(
                "Embedding provider %r unavailable: %s",
                self.settings.embed_provider,
                exc,
            )
            return NullProvider(f"embedding provider unavailable: {exc}")

    # --- Generation --------------------------------------------------------

    def generate(
        self,
        messages: list[LLMMessage],
        *,
        response_schema: type[BaseModel] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        prompt_version: str = "v1",
    ) -> LLMResponse:
        """Run one generation, walking the fallback chain on failure.

        Cloud fallbacks only run when ``LLM_ALLOW_CLOUD`` permitted their
        construction, and every hop is logged.
        """

        effective_temperature = (
            temperature if temperature is not None else self.settings.temperature
        )

        attempts: list[str] = []
        for provider in self.provider_chain():
            cache_key = self._cache_key(
                provider,
                messages,
                response_schema,
                effective_temperature,
                max_tokens,
                prompt_version,
            )
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

            try:
                response = provider.generate(
                    messages,
                    response_schema=response_schema,
                    temperature=effective_temperature,
                    max_tokens=max_tokens,
                )
            except _CONSTRUCTION_ERRORS as exc:
                attempts.append(f"{provider.name}: {exc}")
                logger.warning(
                    "LLM provider %s failed, trying next in chain: %s",
                    provider.name,
                    exc,
                )
                continue

            if self.settings.cache:
                self._cache[cache_key] = response
                while len(self._cache) > DEFAULT_CACHE_SIZE:
                    self._cache.popitem(last=False)
            return response

        raise ProviderUnavailableError(
            "all LLM providers failed — " + "; ".join(attempts)
        )

    def embed(self, texts: list[str]) -> EmbeddingResponse:
        """Embed texts with the configured embedding provider."""

        return self.embed_provider().embed(texts)

    # --- Health ------------------------------------------------------------

    def status(self, *, health_timeout: float = 5.0) -> dict[str, Any]:
        """Summarise the AI layer for ``GET /api/health`` (cheap, no generate)."""

        info: dict[str, Any] = {
            "enabled": self.enabled,
            "provider": self.settings.provider,
            "model": self.settings.model,
            "embed_provider": self.settings.embed_provider,
            "embed_model": self.settings.embed_model,
            "available": False,
            "detail": "",
        }

        if not self.enabled:
            info["detail"] = "LLM_ENABLED=false; deterministic mode"
            return info

        primary = self.primary_provider()
        if isinstance(primary, NullProvider):
            info["detail"] = primary.reason
            return info

        health = primary.health(timeout=health_timeout)
        info["available"] = health.ok
        info["detail"] = health.detail
        return info

    # --- Cache -------------------------------------------------------------

    def clear_cache(self) -> None:
        """Drop all cached responses (used by tests and config reloads)."""

        self._cache.clear()

    def _cache_key(
        self,
        provider: LLMProvider,
        messages: Iterable[LLMMessage],
        response_schema: type[BaseModel] | None,
        temperature: float | None,
        max_tokens: int | None,
        prompt_version: str,
    ) -> tuple[Any, ...]:
        digest = hashlib.sha256(
            "\x1e".join(
                f"{message.role}:{message.content}" for message in messages
            ).encode("utf-8")
        ).hexdigest()
        schema_name = response_schema.__name__ if response_schema else None
        return (
            provider.name,
            provider.model,
            prompt_version,
            temperature,
            max_tokens,
            schema_name,
            digest,
        )


_default_client: LLMClient | None = None


def get_client(settings: LLMSettings | None = None) -> LLMClient:
    """Return the default client (built from ``config.LLM``) or a fresh one."""

    global _default_client
    if settings is not None:
        return LLMClient(settings)
    if _default_client is None:
        from src import config

        _default_client = LLMClient(config.LLM)
    return _default_client


__all__ = ["LLMClient", "get_client"]
