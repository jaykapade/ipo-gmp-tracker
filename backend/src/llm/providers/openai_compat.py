"""OpenAI-compatible adapter.

One adapter covers every endpoint that speaks the OpenAI HTTP API: local
runtimes (Ollama, LM Studio, llama.cpp server, vLLM) and cloud providers
(OpenAI, OpenRouter, Groq, or any OpenAI-compatible gateway). Only the base
URL, model name and API key differ — which is exactly what ``LLM_*`` config
selects.

JSON mode is requested via ``response_format`` when a schema is supplied; if
the server rejects ``response_format`` (older local servers do), the request is
retried once without it and the output is still validated by pydantic, so
behaviour stays safe.
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

_DEFAULT_HEALTH_TIMEOUT = 5.0


class OpenAICompatibleProvider(LLMProvider):
    """Adapter for ``{base_url}/chat/completions`` and ``/embeddings``."""

    def __init__(
        self,
        name: str,
        *,
        model: str,
        base_url: str,
        api_key: str = "",
        timeout: float = 120.0,
        session: Any | None = None,
        is_cloud: bool = False,
    ) -> None:
        self.name = name
        self.model = model
        self.is_cloud = is_cloud
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._session = session
        self._capabilities = ProviderCapabilities(
            json_mode=True,
            tools=True,
            embeddings=True,
            streaming=True,
        )

    # --- Internals ---------------------------------------------------------

    def _session_or_new(self) -> Any:
        if self._session is not None:
            return self._session
        return requests.Session()

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        session = self._session_or_new()
        request_timeout = timeout if timeout is not None else self.timeout
        try:
            if method == "GET":
                response = session.get(
                    url, headers=self._headers(), timeout=request_timeout
                )
            else:
                response = session.post(
                    url,
                    json=payload,
                    headers=self._headers(),
                    timeout=request_timeout,
                )
        except requests.RequestException as exc:
            raise ProviderUnavailableError(
                f"{self.name}: request failed: {exc}"
            ) from exc

        if response.status_code >= 400:
            detail = self._error_detail(response)
            if response.status_code in (401, 403):
                raise ProviderNotConfiguredError(
                    f"{self.name}: HTTP {response.status_code} {detail} "
                    "(check LLM_API_KEY)"
                )
            raise ProviderUnavailableError(
                f"{self.name}: HTTP {response.status_code} {detail}",
                status_code=response.status_code,
            )

        try:
            return response.json()
        except ValueError as exc:
            raise ProviderUnavailableError(
                f"{self.name}: response was not valid JSON"
            ) from exc

    @staticmethod
    def _error_detail(response: Any) -> str:
        try:
            body = response.json()
        except Exception:  # noqa: BLE001 - best-effort error text
            return ""
        if isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict) and error.get("message"):
                return str(error["message"])
            if error:
                return str(error)
            return str(body.get("detail", ""))[:200]
        return ""

    # --- LLMProvider contract ----------------------------------------------

    def generate(
        self,
        messages: list[LLMMessage],
        *,
        response_schema: type[BaseModel] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if response_schema is not None and self._capabilities.json_mode:
            payload["response_format"] = {"type": "json_object"}

        started = time.monotonic()
        try:
            body = self._request("POST", "chat/completions", payload)
        except ProviderUnavailableError as exc:
            # Some local servers reject response_format; retry once without it
            # and rely on pydantic validation instead.
            if exc.status_code == 400 and "response_format" in payload:
                retry = {k: v for k, v in payload.items() if k != "response_format"}
                body = self._request("POST", "chat/completions", retry)
            else:
                raise

        choices = body.get("choices") or []
        if not choices:
            raise ProviderUnavailableError(
                f"{self.name}: response contained no choices"
            )
        message = choices[0].get("message") or {}
        text = message.get("content") or ""
        usage_raw = body.get("usage") or {}
        usage = TokenUsage(
            input_tokens=usage_raw.get("prompt_tokens"),
            output_tokens=usage_raw.get("completion_tokens"),
        )

        parsed = None
        if response_schema is not None:
            parsed = validate_against_schema(text, response_schema)

        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            usage=usage,
            finish_reason=choices[0].get("finish_reason"),
            latency_seconds=time.monotonic() - started,
            parsed=parsed,
        )

    def embed(self, texts: list[str]) -> EmbeddingResponse:
        payload = {"model": self.model, "input": list(texts)}
        body = self._request("POST", "embeddings", payload)
        data = body.get("data") or []
        vectors = [item.get("embedding") or [] for item in data]
        if len(vectors) != len(texts):
            raise ProviderUnavailableError(
                f"{self.name}: expected {len(texts)} embeddings, got {len(vectors)}"
            )
        usage_raw = body.get("usage") or {}
        return EmbeddingResponse(
            vectors=vectors,
            provider=self.name,
            model=self.model,
            usage=TokenUsage(
                input_tokens=usage_raw.get("prompt_tokens"),
                output_tokens=usage_raw.get("total_tokens"),
            ),
        )

    def health(self, timeout: float | None = None) -> ProviderHealth:
        effective = timeout if timeout is not None else _DEFAULT_HEALTH_TIMEOUT
        try:
            self._request("GET", "models", timeout=effective)
        except ProviderNotConfiguredError as exc:
            return ProviderHealth(ok=False, detail=str(exc))
        except ProviderUnavailableError as exc:
            return ProviderHealth(ok=False, detail=str(exc))
        return ProviderHealth(
            ok=True, detail=f"{self.name} reachable at {self.base_url}"
        )

    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities


__all__ = ["OpenAICompatibleProvider"]
