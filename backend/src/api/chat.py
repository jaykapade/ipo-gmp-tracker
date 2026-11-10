"""Streaming chat endpoint grounded in whitelisted data tools.

The endpoint never exposes raw SQL to the model layer. Every answer is composed
from deterministic database lookups (``list_ipos``, ``get_ipo``,
``get_gmp_history`` and ``get_latest_analysis``) and streamed to the client as
Server-Sent Events. Missing data triggers an explicit refusal instead of a guess.

Events (``data: <json>`` lines):

* ``thinking`` — the assistant is working
* ``tool_call`` — a whitelisted tool is being invoked
* ``tool_result`` — tool output (summarised; full payloads stay server-side)
* ``content`` — incremental answer text (``delta`` field)
* ``done`` — final metadata (conversation id, data timestamp, citations)
* ``error`` — something went wrong

The local-first AI provider hook is intentionally left as a future integration;
with ``LLM_ENABLED=false`` (the default) the deterministic path below is used.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.database import db

router = APIRouter(prefix="/api")

# Words that never form part of an IPO company name when extracting candidates.
_STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "can", "to", "of", "in",
    "for", "on", "with", "at", "by", "from", "as", "about", "into", "through",
    "during", "before", "after", "above", "below", "between", "under", "again",
    "further", "once", "here", "there", "when", "where", "why", "how",
    "all", "any", "both", "each", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "s", "t", "just", "don", "now", "i", "me", "my", "myself", "we", "our",
    "ours", "ourselves", "you", "your", "yours", "yourself", "yourselves", "he",
    "him", "his", "himself", "she", "her", "hers", "herself", "it", "its",
    "itself", "they", "them", "their", "theirs", "themselves", "what", "which",
    "who", "whom", "this", "that", "these", "those", "am", "tell", "show",
    "give", "find", "list", "search", "ipo", "ipos", "grey", "market",
    "premium", "gmp", "data", "current", "latest", "active", "upcoming",
    "closed", "listed",
}

# Maximum company-name candidates extracted from one message.
_MAX_NAME_CANDIDATES = 3
# Maximum IPO rows returned per tool call.
_MAX_SEARCH_RESULTS = 5


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=1000)
    conversation_id: str | None = None


def _sse(event_type: str, data: Any) -> str:
    """Format one Server-Sent Event line block."""
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n"


def _extract_name_candidates(message: str) -> list[str]:
    """Pull plausible company-name fragments out of a free-text message.

    Capitalised runs of letters are treated as name candidates. This is
    intentionally conservative — false positives still resolve through the
    whitelisted search tool, and an empty result triggers a refusal rather
    than a guess.
    """

    # Split on punctuation and connectors, keep alphabetic runs.
    tokens = re.findall(r"[A-Za-z][A-Za-z&.'\- ]{1,40}", message)
    candidates: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        cleaned = " ".join(
            part for part in token.split() if part.lower() not in _STOP_WORDS
        ).strip()
        if not cleaned or cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())
        candidates.append(cleaned)
        if len(candidates) >= _MAX_NAME_CANDIDATES:
            break
    return candidates


def _format_money(value: Any) -> str:
    if value is None:
        return "not disclosed"
    try:
        return f"₹{float(value):,.2f} cr"
    except (TypeError, ValueError):
        return str(value)


def _format_percent(value: Any) -> str:
    if value is None:
        return "not disclosed"
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return str(value)


def _latest_recorded_at(rows: list[dict[str, Any]]) -> str | None:
    dates = [row.get("recorded_at") for row in rows if row.get("recorded_at")]
    dates = [d for d in dates if d]
    return max(dates) if dates else None


async def _sleep() -> None:
    """Yield to the event loop so SSE chunks flush incrementally."""
    await asyncio.sleep(0)


async def _stream_chat(
    message: str,
    conversation_id: str | None,
    db_path: Any,
) -> AsyncIterator[str]:
    conversation_id = conversation_id or str(uuid.uuid4())
    sources: list[dict[str, Any]] = []

    def cite(source: dict[str, Any]) -> str:
        sources.append(source)
        return f"[{len(sources)}]"

    yield _sse("thinking", {"status": "reading your question"})
    await _sleep()

    # --- Tool: search IPOs by name candidates (whitelisted) -----------------
    name_candidates = _extract_name_candidates(message)
    matches: list[dict[str, Any]] = []
    seen_ids: set[int] = set()

    for candidate in name_candidates:
        yield _sse(
            "tool_call",
            {"tool": "search_ipos", "args": {"q": candidate, "limit": _MAX_SEARCH_RESULTS}},
        )
        await _sleep()
        rows = db.list_ipos(q=candidate, limit=_MAX_SEARCH_RESULTS, db_path=db_path)
        for row in rows:
            if row["id"] not in seen_ids:
                seen_ids.add(row["id"])
                matches.append(row)
        yield _sse(
            "tool_result",
            {
                "tool": "search_ipos",
                "args": {"q": candidate},
                "returned": len(rows),
            },
        )
        await _sleep()

    # --- Compose the grounded answer ---------------------------------------
    answer_parts: list[str] = []

    if not matches:
        total = db.count_ipos(db_path=db_path)
        answer_parts.append(
            f"I couldn't find any IPO matching your question in the current "
            f"database ({total} IPOs stored). "
        )
        if total:
            answer_parts.append(
                "Try a company name from the dashboard shortlist, or run a "
                "scrape to bring in fresh data."
            )
        else:
            answer_parts.append(
                "The database is empty. Run ``uv run python -m src.main scrape`` "
                "from ``backend/`` to populate it, then ask again."
            )
        answer = "".join(answer_parts)
        for chunk in _chunk(answer):
            yield _sse("content", {"delta": chunk})
            await _sleep()
        yield _sse(
            "done",
            {
                "conversation_id": conversation_id,
                "data_as_of": None,
                "citations": sources,
                "primary_ipo_id": None,
                "refusal": True,
            },
        )
        return

    # Use the best match as the primary answer, list the rest as "also matched".
    primary = matches[0]
    ipo_id = int(primary["id"])
    detail = db.get_ipo(ipo_id, db_path=db_path) or {}
    history = db.get_gmp_history(ipo_id, limit=5, db_path=db_path)
    analysis = db.get_latest_analysis(ipo_id, db_path=db_path)
    latest = history[0] if history else None

    data_as_of = _latest_recorded_at(history) or primary.get("latest_gmp_recorded_at")

    name = primary.get("name") or detail.get("name") or "this IPO"
    answer_parts.append("Based on the latest data")

    if data_as_of:
        answer_parts.append(f" (as of {data_as_of})")
    answer_parts.append(
        f": **{name}** — {detail.get('category') or 'IPO'} on "
        f"{detail.get('exchange') or 'the exchange'}."
    )

    gmp_percent = latest.get("gmp_percent") if latest else primary.get("gmp_percent")
    gmp = latest.get("gmp") if latest else primary.get("gmp")
    source = latest.get("source") if latest else primary.get("latest_gmp_source")

    answer_parts.append(
        f" Its latest GMP is {_format_percent(gmp_percent)}"
    )
    if gmp is not None:
        answer_parts.append(f" (₹{gmp:,.2f})")
    answer_parts.append(
        f" from {source or 'an undisclosed source'}{cite({'type': 'gmp_history', 'ipo_id': ipo_id})}.\n"
    )

    close_date = detail.get("close_date") or primary.get("close_date")
    issue_price = detail.get("issue_price") or primary.get("issue_price")
    subscription = detail.get("subscription") or primary.get("subscription")
    pe = detail.get("pe") or primary.get("pe")

    answer_parts.append(
        f"It closes {close_date or 'on an undisclosed date'}, with an issue price "
        f"of {_format_money(issue_price)}"
    )
    if subscription is not None:
        answer_parts.append(f", subscribed {subscription:.1f}x")
    if pe is not None:
        answer_parts.append(f", P/E of {pe:.1f}")
    answer_parts.append(f".{cite({'type': 'ipo_detail', 'ipo_id': ipo_id})}\n")

    if analysis:
        verdict = analysis.get("verdict")
        score = analysis.get("score")
        answer_parts.append(
            f"Deterministic analysis: {verdict or 'Watch'} verdict "
            f"(score {score:.0f}/100)."
        )
        strengths = analysis.get("strengths") or []
        risks = analysis.get("risks") or []
        gaps = analysis.get("data_gaps") or []
        if strengths:
            answer_parts.append(
                f" Strengths: {', '.join(strengths[:3])}."
            )
        if risks:
            answer_parts.append(f" Risks: {', '.join(risks[:3])}.")
        if gaps:
            answer_parts.append(f" Data gaps: {', '.join(gaps[:3])}.")
        answer_parts.append(
            f"{cite({'type': 'analysis', 'ipo_id': ipo_id})}\n"
        )

    if len(matches) > 1:
        also = ", ".join(
            f"{m.get('name')}" for m in matches[1:]
        )
        answer_parts.append(
            f"\nAlso matched: {also}. Ask about one by name for details."
        )

    answer = "".join(answer_parts)
    for chunk in _chunk(answer):
        yield _sse("content", {"delta": chunk})
        await _sleep()

    yield _sse(
        "done",
        {
            "conversation_id": conversation_id,
            "data_as_of": data_as_of,
            "citations": sources,
            "primary_ipo_id": ipo_id,
            "refusal": False,
        },
    )


def _chunk(text: str, size: int = 12) -> list[str]:
    """Split text into small chunks for a streaming effect."""
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


@router.post("/chat", tags=["chat"])
async def chat(request: Request, body: ChatRequest) -> StreamingResponse:
    """Stream a grounded, tool-based answer to a user question."""

    return StreamingResponse(
        _stream_chat(
            message=body.message,
            conversation_id=body.conversation_id,
            db_path=request.app.state.db_path,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = ["router", "ChatRequest"]
