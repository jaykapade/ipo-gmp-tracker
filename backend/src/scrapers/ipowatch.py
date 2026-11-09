"""IPO Watch scraper.

The public GMP page is a Next.js app that renders its table from the private
JSON API ``/server/api/ipo/GetIpoListingByStatus``. Reading that JSON is far
more stable than parsing the hydrated HTML, and it also gives us the issue
price band, lot size, sector, subscription and listing date.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from src import config
from src.models.ipo import IPO
from src.scrapers.base import BaseScraper, payload_rows
from src.scrapers.errors import ParseError
from src.utils.normalization import normalize_name
from src.utils.parsing import (
    clean_text,
    derive_status_from_dates,
    is_open_status,
    parse_date,
    parse_float,
    parse_int,
    parse_price_band,
)

SOURCE = "IPO Watch"

logger = logging.getLogger(__name__)


def _as_iso_date(value):
    """Return an ISO date string when possible, otherwise the cleaned text."""

    parsed = parse_date(value)
    return parsed.isoformat() if parsed else clean_text(value)


def _issue_size_cr(value) -> str | None:
    """Convert the API's rupee amount into a crore string."""

    rupees = parse_float(value)
    if rupees is None:
        return None
    return f"{rupees / 10_000_000:.2f}"


def _category(ipo_type: str | None) -> str:
    upper = (ipo_type or "").upper()
    return "SME" if "SME" in upper or "EMERGE" in upper else "Mainboard"


def _exchange(ipo_type: str | None) -> str | None:
    upper = (ipo_type or "").upper()
    exchanges = [name for name in ("NSE", "BSE") if name in upper]
    return "/".join(exchanges) if exchanges else None


def _source_url(slug: str | None) -> str | None:
    slug = clean_text(slug)
    if not slug:
        return None
    return f"https://ipowatch.in/{slug.strip('/')}/"


class IpoWatchScraper(BaseScraper):
    """Scraper for the JSON API behind the IPO Watch GMP page."""

    source_name = SOURCE

    def fetch(self) -> Any:
        return self.get_json(config.IPOWATCH_API_URL)

    def rows(self, payload: Any) -> list[Any]:
        try:
            return payload_rows(payload, "data", "result")
        except ParseError as error:
            message = (
                payload.get("message") if isinstance(payload, dict) else None
            )
            raise ParseError(
                f"IPO Watch returned an unexpected payload: "
                f"{message or payload!r}"
            ) from error

    def convert_row(self, item: dict) -> IPO:
        name = clean_text(item.get("name"))
        if not name:
            raise ParseError("IPO Watch row has no company name")

        lower, upper = parse_price_band(item.get("priceBand"))
        issue_price = parse_float(item.get("issuePrice"))
        if issue_price is None:
            issue_price = upper if upper is not None else lower

        return IPO(
            name=name,
            normalized_name=normalize_name(name),
            ipo_id=parse_int(item.get("id")),
            category=_category(item.get("type")),
            status=clean_text(item.get("issueStatus")),
            gmp=parse_float(item.get("gmp")),
            gmp_percent=parse_float(item.get("premiumPct")),
            issue_price=issue_price,
            issue_price_lower=lower,
            issue_price_upper=upper,
            estimated_listing_price=parse_float(item.get("estPrice")),
            ipo_size_cr=_issue_size_cr(item.get("issueSize")),
            sector=clean_text(item.get("sector")),
            exchange=_exchange(item.get("type")),
            lot_size=clean_text(item.get("lotSize")),
            subscription=parse_float(item.get("subscription")),
            open_date=_as_iso_date(item.get("openDate")),
            close_date=_as_iso_date(item.get("closeDate")),
            listing_date=_as_iso_date(item.get("listingDate")),
            source_url=_source_url(item.get("slug")),
        )


# --- Backwards-compatible module helpers -----------------------------------


def fetch_ipo_data(session: requests.Session | None = None) -> list[dict]:
    """Fetch the IPO listing payload from IPO Watch."""

    scraper = IpoWatchScraper(session=session)
    return scraper.rows(scraper.fetch())


def convert_to_ipo(item: dict) -> IPO:
    """Map one IPO Watch row onto the common IPO model."""

    return IpoWatchScraper().convert_row(item)


def main() -> None:
    config.setup_logging()
    scraper = IpoWatchScraper()
    rows = scraper.rows(scraper.fetch())

    logger.info("Found %d IPOs\n", len(rows))

    saved = 0
    failed = 0

    for item in rows:
        # One malformed row must not abort the whole scrape.
        try:
            ipo = scraper.convert_row(item)

            # Only save IPOs that are currently open. Derive status from
            # open/close dates when the source does not provide one.
            status = ipo.status
            if status is None:
                status = derive_status_from_dates(ipo.open_date, ipo.close_date)
            if status is not None and not is_open_status(status):
                continue

            if status is not None:
                ipo.status = status

            db_id = scraper.save(ipo)
        except Exception as error:  # noqa: BLE001 - report and continue
            failed += 1
            logger.error("Failed to save row %r: %s", item.get("id"), error)
            continue

        logger.info(
            "%-40s -> %-35s GMP: %-6s Status: %-10s [DB ID: %s]",
            ipo.name,
            ipo.normalized_name,
            ipo.gmp,
            ipo.status,
            db_id,
        )
        saved += 1

    logger.info("Saved %d IPO records (%d failed).", saved, failed)


if __name__ == "__main__":
    main()
