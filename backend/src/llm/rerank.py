"""Passage reranking behind one swappable contract.

See docs/ipo-research-framework.md §P2/§P3. Ollama serves no true reranker,
so the default backend (``RERANK_PROVIDER=llm``) asks the **extractor** role to
score each passage 0–10 as schema-validated JSON. Because it goes through the
provider-agnostic :class:`~src.llm.client.LLMClient`, the same backend runs on
a local model, the Claude subscription (``claude-code``) or a cloud API.

``fastembed`` (true BGE cross-encoder) and ``llamacpp`` (``/v1/rerank``) are
documented upgrade paths that plug into the same :class:`RerankProvider`.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from src.llm.base import LLMError, LLMMessage

if TYPE_CHECKING:
    from src.llm.client import LLMClient

logger = logging.getLogger(__name__)

RERANK_PROMPT_VERSION = "rerank-v1"
_MAX_PASSAGE_CHARS = 2000

_RERANK_SYSTEM_PROMPT = (
    "You score how relevant numbered passages are to a query for an Indian "
    "IPO research assistant. Score each passage from 0 (irrelevant) to 10 "
    "(directly answers the query). Judge relevance only — do not answer the "
    "query. Return JSON only: "
    '{"scores": [{"index": <passage number>, "score": <0-10>}, ...]} '
    "with one entry for every passage."
)


class _PassageScore(BaseModel):
    index: int
    score: float = Field(ge=0, le=10)


class RerankScores(BaseModel):
    """Schema the extractor model must return."""

    scores: list[_PassageScore]


@dataclass(frozen=True)
class RankedPassage:
    """One passage with its relevance score and original position."""

    index: int
    text: str
    score: float


class RerankProvider(ABC):
    """Reorder passages by relevance to a query."""

    name: str = "unknown"

    @abstractmethod
    def rerank(
        self, query: str, passages: list[str], *, top_k: int | None = None
    ) -> list[RankedPassage]:
        """Return passages sorted by descending relevance (stable on ties)."""


class IdentityReranker(RerankProvider):
    """No-op ranking: keeps retrieval order. Used when AI is unavailable."""

    name = "identity"

    def rerank(
        self, query: str, passages: list[str], *, top_k: int | None = None
    ) -> list[RankedPassage]:
        ranked = [
            RankedPassage(index=i, text=text, score=0.0)
            for i, text in enumerate(passages)
        ]
        return ranked[:top_k] if top_k is not None else ranked


class LLMReranker(RerankProvider):
    """Score passages with the extractor role (provider-agnostic)."""

    name = "llm"

    def __init__(self, client: LLMClient) -> None:
        self.client = client

    def rerank(
        self, query: str, passages: list[str], *, top_k: int | None = None
    ) -> list[RankedPassage]:
        if not passages:
            return []

        numbered = "\n\n".join(
            f"[{i}] {text[:_MAX_PASSAGE_CHARS]}" for i, text in enumerate(passages)
        )
        messages = [
            LLMMessage("system", _RERANK_SYSTEM_PROMPT),
            LLMMessage("user", f"Query: {query}\n\nPassages:\n{numbered}"),
        ]

        try:
            response = self.client.generate(
                messages,
                response_schema=RerankScores,
                temperature=0.0,
                prompt_version=RERANK_PROMPT_VERSION,
            )
        except LLMError as exc:
            # Ranking is an optimisation; never fail retrieval because of it.
            logger.warning("LLM rerank failed, keeping retrieval order: %s", exc)
            return IdentityReranker().rerank(query, passages, top_k=top_k)

        scores: dict[int, float] = {}
        parsed: RerankScores = response.parsed
        for item in parsed.scores:
            if 0 <= item.index < len(passages):
                scores.setdefault(item.index, item.score)

        ranked = [
            RankedPassage(index=i, text=text, score=scores.get(i, 0.0))
            for i, text in enumerate(passages)
        ]
        # sorted() is stable, so equal scores keep retrieval order.
        ranked.sort(key=lambda passage: passage.score, reverse=True)
        return ranked[:top_k] if top_k is not None else ranked


_PLANNED_BACKENDS = {"fastembed", "llamacpp"}


def create_reranker(name: str, client: LLMClient) -> RerankProvider:
    """Build the reranker selected by ``RERANK_PROVIDER``.

    ``llm`` uses the extractor role of ``client``. ``ollama-llm`` is accepted
    as the documented alias. When AI is disabled the identity ranker is used.
    """

    key = name.lower().strip()
    if key in {"llm", "ollama-llm"}:
        extractor = client.for_role("extractor")
        if not extractor.enabled:
            return IdentityReranker()
        return LLMReranker(extractor)
    if key in {"none", "identity"}:
        return IdentityReranker()
    if key in _PLANNED_BACKENDS:
        raise NotImplementedError(
            f"rerank backend {key!r} is planned but not implemented yet; "
            "use RERANK_PROVIDER=llm"
        )
    raise ValueError(
        f"unknown rerank provider {name!r}; known: llm, ollama-llm, identity"
    )


__all__ = [
    "IdentityReranker",
    "LLMReranker",
    "RankedPassage",
    "RerankProvider",
    "RerankScores",
    "create_reranker",
]
