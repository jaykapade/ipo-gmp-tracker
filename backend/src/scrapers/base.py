"""Shared scraper interface.

Each source implements :class:`BaseScraper`:

* ``fetch()``       -> the raw decoded payload (usually a dict)
* ``rows(payload)`` -> the list of records inside that payload
* ``convert_row(r)`` -> one :class:`~src.models.ipo.IPO`

Keeping those steps separate lets the pipeline isolate one malformed row
without aborting the whole run, while ``parse()``/``scrape()`` still offer a
simple all-or-nothing path for scripts and tests.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar

import requests

from src import config
from src.database import db
from src.models.ipo import IPO
from src.scrapers.errors import FetchError, ParseError
from src.utils.http import RateLimiter, create_session


class BaseScraper(ABC):
    """Blueprint shared by every source."""

    #: Human-readable source name stored in the database.
    source_name: ClassVar[str]

    def __init__(
        self,
        session: requests.Session | None = None,
        *,
        request_delay: float | None = None,
    ) -> None:
        self._session = session
        self.limiter = RateLimiter(
            config.REQUEST_DELAY_SECONDS
            if request_delay is None
            else request_delay
        )

    @property
    def session(self) -> requests.Session:
        """Create the HTTP session lazily so pure parsing stays cheap."""

        if self._session is None:
            self._session = create_session()
        return self._session

    # --- Required by every source -----------------------------------------

    @abstractmethod
    def fetch(self) -> Any:
        """Fetch and decode the raw payload from the source."""

    @abstractmethod
    def rows(self, payload: Any) -> list[Any]:
        """Return the record list inside ``payload``."""

    @abstractmethod
    def convert_row(self, row: Any) -> IPO:
        """Map one source row onto the common :class:`IPO` model."""

    # --- Shared behaviour --------------------------------------------------

    def get_json(self, url: str) -> Any:
        """GET ``url`` politely and decode JSON, raising typed errors."""

        self.limiter.wait()
        try:
            response = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()
        except requests.RequestException as error:
            raise FetchError(
                f"{self.source_name}: request failed: {error}"
            ) from error

        try:
            return response.json()
        except ValueError as error:
            raise FetchError(
                f"{self.source_name}: response was not valid JSON"
            ) from error

    def parse(self, payload: Any) -> list[IPO]:
        """Strictly convert every row; raises on the first bad row."""

        return [self.convert_row(row) for row in self.rows(payload)]

    def scrape(self) -> list[IPO]:
        """Fetch once and return every row as an ``IPO``."""

        return self.parse(self.fetch())

    def save(
        self,
        ipo: IPO,
        *,
        db_path: str | Path | None = None,
        scrape_run_id: int | None = None,
    ) -> int:
        """Persist an IPO and its GMP observation for this source."""

        return db.save_ipo_with_gmp(
            ipo,
            source=self.source_name,
            db_path=db_path,
            scrape_run_id=scrape_run_id,
        )


def payload_rows(payload: Any, *keys: str) -> list[Any]:
    """Extract the first list found under ``keys`` or raise ``ParseError``.

    A small helper because several sources wrap their rows differently, e.g.
    ``{"data": [...]}`` versus ``{"reportTableData": [...]}``.
    """

    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value

    raise ParseError(f"unexpected payload shape: {payload!r}")
