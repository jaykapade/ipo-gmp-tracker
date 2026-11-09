"""InvestorGain JSON API scraper."""

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
    parse_float,
    parse_int,
)

SOURCE = "InvestorGain"
URL = config.INVESTORGAIN_URL

logger = logging.getLogger(__name__)


class InvestorGainScraper(BaseScraper):
    """Scraper for the undocumented InvestorGain report endpoint."""

    source_name = SOURCE

    def fetch(self) -> Any:
        return self.get_json(URL)

    def rows(self, payload: Any) -> list[Any]:
        return payload_rows(payload, "reportTableData")

    def convert_row(self, ipo_data: dict) -> IPO:
        name = clean_text(ipo_data.get("~ipo_name"))
        if not name:
            raise ParseError("InvestorGain row has no IPO name")

        return IPO(
            name=name,
            normalized_name=normalize_name(name),
            ipo_id=parse_int(ipo_data.get("~id")),
            category=clean_text(ipo_data.get("~IPO_Category")),
            gmp=parse_float(ipo_data.get("~max_gmp1")),
            gmp_percent=parse_float(ipo_data.get("~gmp_percent_calc")),
            issue_price=parse_float(ipo_data.get("Price (₹)")),
            ipo_size_cr=clean_text(ipo_data.get("IPO Size")),
            pe=parse_float(ipo_data.get("~P/E")),
            open_date=clean_text(ipo_data.get("~Srt_Open")),
            close_date=clean_text(ipo_data.get("~Srt_Close")),
            listing_date=clean_text(ipo_data.get("~Str_Listing")),
            updated_at=clean_text(ipo_data.get("Updated-On")),
        )


# --- Backwards-compatible module helpers -----------------------------------


def fetch_ipo_data(session: requests.Session | None = None) -> list[dict]:
    """Fetch the report payload from InvestorGain."""

    scraper = InvestorGainScraper(session=session)
    return scraper.rows(scraper.fetch())


def convert_to_ipo(ipo_data: dict) -> IPO:
    """Map one InvestorGain report row onto the common IPO model."""

    return InvestorGainScraper().convert_row(ipo_data)


def main() -> None:
    config.setup_logging()
    scraper = InvestorGainScraper()
    ipo_data = scraper.rows(scraper.fetch())

    logger.info("Found %d IPOs\n", len(ipo_data))

    saved = 0
    failed = 0

    for data in ipo_data:
        # One malformed row must not abort the whole scrape.
        try:
            ipo = scraper.convert_row(data)

            # Only save IPOs that are currently open. InvestorGain doesn't
            # provide a status field, so derive one from open/close dates.
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
            logger.error("Failed to save row: %s", error)
            continue

        logger.info(
            "%-40s -> %-35s [DB ID: %s]", ipo.name, ipo.normalized_name, db_id
        )
        saved += 1

    logger.info("Saved %d IPO records (%d failed).", saved, failed)


if __name__ == "__main__":
    main()
