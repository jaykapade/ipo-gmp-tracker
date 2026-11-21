"""Provider-agnostic AI layer.

One contract (:class:`~src.llm.base.LLMProvider`) covers local runtimes
(Ollama, LM Studio, llama.cpp, vLLM) and cloud providers (OpenAI, Anthropic,
Gemini, OpenRouter, Groq, any OpenAI-compatible endpoint). Selection is
config-only through the ``LLM_*`` settings; callers never import a vendor SDK.

With ``LLM_ENABLED=false`` (the default) every call fails fast with
:class:`ProviderUnavailableError` and callers fall back to deterministic
templates, so the core pipeline works without any model runtime.
"""

from __future__ import annotations

from src.llm.base import (
    CloudDisabledError,
    EmbeddingResponse,
    LLMError,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    LLMResponseValidationError,
    ProviderCapabilities,
    ProviderHealth,
    ProviderNotConfiguredError,
    ProviderUnavailableError,
    Role,
    TokenUsage,
    UnknownProviderError,
    extract_json_object,
    validate_against_schema,
)
from src.llm.client import LLMClient, get_client
from src.llm.providers import (
    PROVIDER_SPECS,
    NullProvider,
    create_provider,
    is_cloud_provider,
)
from src.llm.rerank import (
    IdentityReranker,
    LLMReranker,
    RankedPassage,
    RerankProvider,
    create_reranker,
)

__all__ = [
    "CloudDisabledError",
    "EmbeddingResponse",
    "LLMClient",
    "LLMError",
    "LLMMessage",
    "LLMProvider",
    "LLMResponse",
    "LLMResponseValidationError",
    "NullProvider",
    "IdentityReranker",
    "LLMReranker",
    "PROVIDER_SPECS",
    "ProviderCapabilities",
    "ProviderHealth",
    "ProviderNotConfiguredError",
    "ProviderUnavailableError",
    "RankedPassage",
    "RerankProvider",
    "Role",
    "TokenUsage",
    "UnknownProviderError",
    "create_provider",
    "create_reranker",
    "extract_json_object",
    "get_client",
    "is_cloud_provider",
    "validate_against_schema",
]
