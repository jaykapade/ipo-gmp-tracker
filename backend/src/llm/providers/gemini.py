"""Native Google Gemini adapter (Generative Language API).

Gemini uses ``contents``/``parts`` payloads, a ``systemInstruction`` field and
supports JSON output through ``generationConfig.responseMimeType``. Embeddings
run through ``batchEmbedContents`` with the separately configured
``LLM_EMBED_MODEL``.
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


class GeminiProvider(LLMProvider):
    """Adapter for ``POST {base_url}/models/{model}:generateContent``."""

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        api_key: str,
        timeout: float = 120.0,
        session: Any | None = None,
    ) -> None:
        self.name = "gemini"
        self.model = model
        self.is_cloud = True
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._session = session

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            # Header, not query param, so the key never lands in URL logs.
            headers["x-goog-api-key"] = self.api_key
        return headers

    def _model_path(self, operation: str) -> str:
        return f"models/{self.model.lstrip('/')}:{operation}"

    def _request(
        self,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        method: str = "POST",
        timeout: float | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        session = self._session if self._session is not None else requests.Session()
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
            raise ProviderUnavailableError(f"gemini: request failed: {exc}") from exc

        if response.status_code >= 400:
            try:
                body = response.json()
                detail = str(body.get("error", {}).get("message", ""))[:200]
            except Exception:  # noqa: BLE001 - best-effort error text
                detail = ""
            if response.status_code in (401, 403):
                raise ProviderNotConfiguredError(
                    f"gemini: HTTP {response.status_code} {detail} (check LLM_API_KEY)"
                )
            raise ProviderUnavailableError(
                f"gemini: HTTP {response.status_code} {detail}",
                status_code=response.status_code,
            )

        try:
            return response.json()
        except ValueError as exc:
            raise ProviderUnavailableError(
                "gemini: response was not valid JSON"
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
        contents = [
            {
                "role": "model" if message.role == "assistant" else "user",
                "parts": [{"text": message.content}],
            }
            for message in messages
            if message.role != "system"
        ]

        payload: dict[str, Any] = {"contents": contents}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        generation_config: dict[str, Any] = {}
        if temperature is not None:
            generation_config["temperature"] = temperature
        if max_tokens is not None:
            generation_config["maxOutputTokens"] = max_tokens
        if response_schema is not None:
            generation_config["responseMimeType"] = "application/json"
        if generation_config:
            payload["generationConfig"] = generation_config

        started = time.monotonic()
        body = self._request(self._model_path("generateContent"), payload)

        candidates = body.get("candidates") or []
        if not candidates:
            raise ProviderUnavailableError("gemini: response contained no candidates")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts)
        usage_meta = body.get("usageMetadata") or {}

        parsed = None
        if response_schema is not None:
            parsed = validate_against_schema(text, response_schema)

        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            usage=TokenUsage(
                input_tokens=usage_meta.get("promptTokenCount"),
                output_tokens=usage_meta.get("candidatesTokenCount"),
            ),
            finish_reason=candidates[0].get("finishReason"),
            latency_seconds=time.monotonic() - started,
            parsed=parsed,
        )

    def embed(self, texts: list[str]) -> EmbeddingResponse:
        requests_list = [
            {
                "model": f"models/{self.model}",
                "content": {"parts": [{"text": text}]},
            }
            for text in texts
        ]
        body = self._request(
            self._model_path("batchEmbedContents"), {"requests": requests_list}
        )
        embeddings = body.get("embeddings") or []
        vectors = [item.get("values") or [] for item in embeddings]
        if len(vectors) != len(texts):
            raise ProviderUnavailableError(
                f"gemini: expected {len(texts)} embeddings, got {len(vectors)}"
            )
        return EmbeddingResponse(vectors=vectors, provider=self.name, model=self.model)

    def health(self, timeout: float | None = None) -> ProviderHealth:
        effective = timeout if timeout is not None else _DEFAULT_HEALTH_TIMEOUT
        try:
            self._request("models", method="GET", timeout=effective)
        except ProviderNotConfiguredError as exc:
            return ProviderHealth(ok=False, detail=str(exc))
        except ProviderUnavailableError as exc:
            return ProviderHealth(ok=False, detail=str(exc))
        return ProviderHealth(ok=True, detail="gemini reachable")

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            json_mode=True,
            tools=True,
            embeddings=True,
            vision=True,
            streaming=True,
            context_window=1_000_000,
        )


__all__ = ["GeminiProvider"]
