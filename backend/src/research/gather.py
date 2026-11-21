"""Evidence gathering: web facts from the researcher role plus DB facts.

The researcher (``LLMClient.for_role("researcher")``, web-enabled
``claude-code``) returns schema-validated facts with source URLs. The
pipeline — not the model — assigns ids: ``W1…`` for web facts and ``D1…``
for facts drawn from this app's own deterministic data, so perspectives can
cite the stored GMP history and screening score too.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.llm.base import LLMMessage
from src.research.prompts import GATHER_CHECKLIST, GATHER_SYSTEM, PROMPT_VERSION
from src.research.schemas import Fact, FactPack, GatherResult

if TYPE_CHECKING:
    from src.llm import LLMClient, LLMResponse

_IDENTITY_FIELDS = (
    ("category", "Category"),
    ("exchange", "Exchange"),
    ("sector", "Sector"),
    ("open_date", "Opens"),
    ("close_date", "Closes"),
    ("listing_date", "Lists"),
    ("ipo_size_cr", "Issue size"),
    ("lot_size", "Lot size"),
)


def _price_band(ipo: dict[str, Any]) -> str | None:
    low, high = ipo.get("issue_price_lower"), ipo.get("issue_price_upper")
    if low and high:
        return f"₹{low:g}–₹{high:g}"
    price = ipo.get("issue_price")
    return f"₹{price:g}" if price else None


def build_gather_messages(ipo: dict[str, Any]) -> list[LLMMessage]:
    """Prompt for the web researcher, seeded with what the DB already knows."""

    lines = [f"Company: {ipo['name']}"]
    band = _price_band(ipo)
    if band:
        lines.append(f"Price band: {band}")
    for key, label in _IDENTITY_FIELDS:
        if ipo.get(key):
            lines.append(f"{label}: {ipo[key]}")
    if ipo.get("rhp_url"):
        lines.append(f"Known RHP URL: {ipo['rhp_url']}")

    user = (
        "Research this Indian IPO.\n\n"
        + "\n".join(lines)
        + "\n\n"
        + GATHER_CHECKLIST
        + "\n\nMake sure the facts are about this exact company and issue "
        "(match the price band and dates), not a similarly named one."
    )
    return [LLMMessage("system", GATHER_SYSTEM), LLMMessage("user", user)]


def database_facts(
    ipo: dict[str, Any],
    gmp_history: list[dict[str, Any]],
    analysis: dict[str, Any] | None,
) -> list[Fact]:
    """Facts from this app's own data (``source_type='database'``)."""

    facts: list[dict[str, Any]] = []

    band = _price_band(ipo)
    if band:
        facts.append({"category": "issue", "claim": "Price band", "value": band})
    if ipo.get("ipo_size_cr"):
        facts.append(
            {
                "category": "issue",
                "claim": "Issue size",
                "value": str(ipo["ipo_size_cr"]),
            }
        )
    if ipo.get("lot_size"):
        facts.append(
            {"category": "issue", "claim": "Lot size", "value": str(ipo["lot_size"])}
        )
    if ipo.get("close_date"):
        facts.append(
            {"category": "issue", "claim": "Issue closes", "value": ipo["close_date"]}
        )
    if ipo.get("pe") is not None:
        facts.append(
            {
                "category": "valuation",
                "claim": "P/E at the issue price (as reported by the GMP source)",
                "value": f"{ipo['pe']:g}",
            }
        )
    if ipo.get("subscription") is not None:
        facts.append(
            {
                "category": "market",
                "claim": "Overall subscription (latest scrape)",
                "value": f"{ipo['subscription']:g}x",
            }
        )

    observations = [row for row in gmp_history if row.get("gmp") is not None]
    if observations:
        ordered = sorted(observations, key=lambda row: row.get("recorded_at") or "")
        first, last = ordered[0], ordered[-1]
        pct = last.get("gmp_percent")
        facts.append(
            {
                "category": "market",
                "claim": "Latest grey market premium (unofficial, speculative)",
                "value": f"₹{last['gmp']:g}"
                + (f" ({pct:.1f}%)" if pct is not None else ""),
                "as_of": last.get("recorded_at"),
                "source_title": last.get("source"),
            }
        )
        if len(ordered) > 1:
            facts.append(
                {
                    "category": "market",
                    "claim": f"GMP trend across {len(ordered)} observations",
                    "value": f"₹{first['gmp']:g} → ₹{last['gmp']:g}",
                    "as_of": last.get("recorded_at"),
                }
            )

    if analysis:
        facts.append(
            {
                "category": "market",
                "claim": "Deterministic screening score and verdict (this app)",
                "value": f"{analysis.get('score')} / {analysis.get('verdict')}",
                "as_of": analysis.get("generated_at"),
            }
        )

    return [
        Fact(id=f"D{index}", source_type="database", **fact)
        for index, fact in enumerate(facts, start=1)
    ]


def gather_facts(
    ipo: dict[str, Any],
    *,
    gmp_history: list[dict[str, Any]],
    analysis: dict[str, Any] | None,
    researcher: LLMClient,
) -> tuple[FactPack, LLMResponse]:
    """Run the web researcher and merge its facts with the DB facts."""

    response = researcher.generate(
        build_gather_messages(ipo),
        response_schema=GatherResult,
        prompt_version=PROMPT_VERSION,
    )
    result: GatherResult = response.parsed
    gathered_at = datetime.now(UTC).isoformat()

    seen: set[tuple[str, str | None]] = set()
    web_facts: list[Fact] = []
    for item in result.facts:
        key = (item.claim.strip().lower(), (item.value or "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        web_facts.append(
            Fact(
                id=f"W{len(web_facts) + 1}",
                as_of=gathered_at,
                **item.model_dump(),
            )
        )

    pack = FactPack(
        ipo_id=int(ipo["id"]),
        ipo_name=str(ipo["name"]),
        facts=[*web_facts, *database_facts(ipo, gmp_history, analysis)],
        gaps=result.gaps,
        rhp_url=result.rhp_url or ipo.get("rhp_url"),
        gathered_at=gathered_at,
    )
    return pack, response


def render_facts(pack: FactPack) -> str:
    """Compact, citable fact listing for downstream prompts."""

    lines = []
    for fact in pack.facts:
        detail = fact.claim
        if fact.value:
            detail += f": {fact.value}"
        if fact.period:
            detail += f" ({fact.period})"
        source = fact.source_title or fact.source_url or "this app"
        lines.append(
            f"[{fact.id}] ({fact.category}; {fact.source_type}) {detail} "
            f"— source: {source}"
        )
    if pack.gaps:
        lines.append("")
        lines.append("Not found during research: " + "; ".join(pack.gaps))
    return "\n".join(lines)


__all__ = [
    "build_gather_messages",
    "database_facts",
    "gather_facts",
    "render_facts",
]
