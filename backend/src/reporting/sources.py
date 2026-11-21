"""Where each report figure came from: scraped market data and research URLs.

``collect_sources`` gathers, per IPO, the pages the scrapers read (IPO Watch
detail page, InvestorGain GMP board, the RHP when known). The web sources the
AI research cited come from the research digest (``ResearchDigest.sources``).
Both are shown in the PDF and, in short form, in the email body.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src import config
from src.database import db

# Order used when listing research sources: primary documents first.
SOURCE_TYPE_ORDER = {"official": 0, "exchange": 1, "secondary": 2}


@dataclass(frozen=True)
class SourceLink:
    """One source shown in a report."""

    label: str
    url: str
    kind: str  # "market data", "official", "exchange" or "secondary"


def _market_link(row: dict[str, Any]) -> SourceLink | None:
    source = str(row.get("source") or "").strip()
    url = row.get("source_url")
    if not url and source.lower() == "investorgain":
        # The API row has no per-IPO page; link the public GMP board it feeds.
        url = config.INVESTORGAIN_PAGE_URL
    if not url:
        return None
    return SourceLink(label=f"{source or 'Source'} (GMP, price, dates)", url=url, kind="market data")


def market_sources(ipo_id: int, *, db_path: str | Path | None = None) -> list[SourceLink]:
    """Pages the scrapers read for one IPO, plus its RHP when known."""

    links: list[SourceLink] = []
    seen: set[str] = set()
    for row in db.get_ipo_sources(ipo_id, db_path=db_path):
        link = _market_link(row)
        if link is not None and link.url not in seen:
            seen.add(link.url)
            links.append(link)

    ipo = db.get_ipo(ipo_id, db_path=db_path) or {}
    rhp = ipo.get("rhp_url")
    if rhp and rhp not in seen:
        links.append(SourceLink(label="Red Herring Prospectus (RHP)", url=rhp, kind="official"))
    return links


def collect_sources(
    ipo_ids: Iterable[int],
    *,
    db_path: str | Path | None = None,
) -> dict[int, list[SourceLink]]:
    """Market-data sources for every IPO in a report, keyed by IPO id."""

    return {ipo_id: market_sources(ipo_id, db_path=db_path) for ipo_id in ipo_ids}


def research_sources(facts_output: Any) -> list[SourceLink]:
    """Unique web sources from a research run's ``facts`` output.

    Facts taken from this app's own database have no URL and are skipped.
    Official and exchange sources come first.
    """

    if isinstance(facts_output, dict):
        facts = facts_output.get("facts")
    else:
        facts = facts_output
    if not isinstance(facts, list):
        return []

    links: dict[str, SourceLink] = {}
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        url = str(fact.get("source_url") or "").strip()
        if not url.lower().startswith(("http://", "https://")) or url in links:
            continue
        kind = str(fact.get("source_type") or "secondary")
        label = str(fact.get("source_title") or "").strip() or url
        links[url] = SourceLink(label=label, url=url, kind=kind)

    return sorted(links.values(), key=lambda link: SOURCE_TYPE_ORDER.get(link.kind, 9))


__all__ = [
    "SourceLink",
    "collect_sources",
    "market_sources",
    "research_sources",
]
