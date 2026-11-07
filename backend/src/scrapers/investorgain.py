"""InvestorGain JSON API scraper."""

from __future__ import annotations

import logging
import requests

from src import config
from src.database.db import save_ipo_with_gmp
from src.models.ipo import IPO
from src.utils.http import create_session
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


def fetch_ipo_data(session: requests.Session | None = None) -> list[dict]:
    """Fetch the report payload from InvestorGain."""

    session = session or create_session()
    response = session.get(URL, timeout=config.REQUEST_TIMEOUT)
    response.raise_for_status()

    data = response.json()
    return data["reportTableData"]


def convert_to_ipo(ipo_data: dict) -> IPO:
    """Map one InvestorGain report row onto the common IPO model."""

    name = clean_text(ipo_data.get("~ipo_name"))
    if not name:
        raise ValueError("InvestorGain row has no IPO name")

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


def main() -> None:
    config.setup_logging()
    ipo_data = fetch_ipo_data()

    logger.info("Found %d IPOs\n", len(ipo_data))

    saved = 0
    failed = 0

    for data in ipo_data:
        # One malformed row must not abort the whole scrape.
        try:
            ipo = convert_to_ipo(data)

            # Only save IPOs that are currently open. InvestorGain doesn't
            # provide a status field, so derive one from open/close dates.
            status = ipo.status
            if status is None:
                status = derive_status_from_dates(ipo.open_date, ipo.close_date)
            if status is not None and not is_open_status(status):
                continue

            db_id = save_ipo_with_gmp(ipo, source=SOURCE)
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
