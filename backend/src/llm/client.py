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

Roles (analyst, verifier, extractor, challenger) resolve through
:meth:`LLMClient.for_role`; each role may use its own provider and model.
Fallback entries may pin a model with ``provider=model`` (for example
``ollama=qwen3.5:9b-q4_K_M``) because a cloud model id is meaningless to a
local runtime.
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

    def __init__(
        self,
        settings: LLMSettings,
        *,
        session: Any | None = None,
        runner: Any | None = None,
        role: str | None = None,
        disabled_reason: str | None = None,
    ) -> None:
        self.settings = settings
        self.role = role
        self._session = session
        self._runner = runner
        self._disabled_reason = disabled_reason
        self._chain: list[LLMProvider] | None = None
        self._cache: OrderedDict[tuple[Any, ...], LLMResponse] = OrderedDict()
        self._role_clients: dict[str, LLMClient] = {}

    # --- Resolution --------------------------------------------------------

    @property
    def enabled(self) -> bool:
        """Whether AI is switched on (``LLM_ENABLED``) for this client/role."""

        return bool(self.settings.enabled) and self._disabled_reason is None

    def for_role(self, role: str) -> LLMClient:
        """Return a client bound to one generation role's provider and model.

        Role clients are memoised so their caches persist. Optional roles
        (the challenger) stay disabled until their model is set explicitly.
        """

        key = role.lower().strip()
        client = self._role_clients.get(key)
        if client is None:
            from src.config import OPTIONAL_LLM_ROLES

            role_settings = self.settings.for_role(key)
            reason = None
            if key in OPTIONAL_LLM_ROLES and not self.settings.role_configured(key):
                reason = (
                    f"{key} role not configured "
                    f"(set LLM_ROLE_{key.upper()}_MODEL to enable it)"
                )
            client = LLMClient(
                role_settings,
                session=self._session,
                runner=self._runner,
                role=key,
                disabled_reason=reason,
            )
            self._role_clients[key] = client
        return client

    def provider_chain(self) -> list[LLMProvider]:
        """Return the chat provider chain, primary first."""

        if self._chain is None:
            self._chain = self._build_chain()
        return list(self._chain)

    def _disabled_detail(self) -> str:
        return self._disabled_reason or "LLM_ENABLED=false; deterministic mode"

    def _chain_entries(self) -> list[tuple[str, str, str | None]]:
        """``(provider, model, base_url)`` for the primary and each fallback."""

        primary = self.settings.provider
        entries = [(primary, self.settings.model, self.settings.base_url)]
        for raw in self.settings.fallback_providers:
            name, sep, model = raw.partition("=")
            name = name.strip().lower()
            model = model.strip() if sep and model.strip() else self.settings.model
            # The configured base URL belongs to the primary provider only.
            base_url = self.settings.base_url if name == primary else None
            entries.append((name, model, base_url))
        return entries

    def _build_chain(self) -> list[LLMProvider]:
        if not self.enabled:
            return [NullProvider(self._disabled_detail())]

        chain: list[LLMProvider] = []
        skipped: list[str] = []
        for name, model, base_url in self._chain_entries():
            try:
                chain.append(
                    create_provider(
                        name,
                        model=model,
                        base_url=base_url,
                        api_key=self.settings.api_key,
                        timeout=self.settings.timeout_seconds,
                        allow_cloud=self.settings.allow_cloud,
                        session=self._session,
                        max_concurrency=self.settings.max_concurrency,
                        runner=self._runner,
                        web_research=self.settings.web_research,
                        max_turns=self.settings.research_max_turns,
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

        if not self.settings.enabled:
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
                runner=self._runner,
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

    def status(
        self,
        *,
        health_timeout: float = 5.0,
        include_roles: bool = True,
    ) -> dict[str, Any]:
        """Summarise the AI layer for ``GET /api/health`` (cheap, no generate).

        Health probes are shared across roles that resolve to the same
        provider, so a health poll costs at most one probe per provider.
        """

        probes: dict[tuple[str, str], tuple[bool, str]] = {}
        info = self._status_entry(health_timeout, probes)
        info.update(
            embed_provider=self.settings.embed_provider,
            embed_model=self.settings.embed_model,
            rerank_provider=self.settings.rerank_provider,
        )
        if include_roles and self.role is None:
            from src.config import LLM_ROLES

            info["roles"] = {
                role: self.for_role(role)._status_entry(health_timeout, probes)
                for role in LLM_ROLES
            }
        return info

    def _status_entry(
        self,
        health_timeout: float,
        probes: dict[tuple[str, str], tuple[bool, str]],
    ) -> dict[str, Any]:
        info: dict[str, Any] = {
            "enabled": self.enabled,
            "provider": self.settings.provider,
            "model": self.settings.model,
            "available": False,
            "detail": "",
        }

        if not self.enabled:
            info["detail"] = self._disabled_detail()
            return info

        primary = self.primary_provider()
        if isinstance(primary, NullProvider):
            info["detail"] = primary.reason
            return info

        probe_key = (
            primary.name,
            str(getattr(primary, "base_url", getattr(primary, "binary", ""))),
        )
        if probe_key not in probes:
            health = primary.health(timeout=health_timeout)
            probes[probe_key] = (health.ok, health.detail)
        info["available"], info["detail"] = probes[probe_key]
        return info

    # --- Cache -------------------------------------------------------------

    def clear_cache(self) -> None:
        """Drop all cached responses (used by tests and config reloads)."""

        self._cache.clear()
        for client in self._role_clients.values():
            client.clear_cache()

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
