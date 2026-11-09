"""Shared HTTP session with retries, timeouts and a documented user agent."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src import config


@dataclass
class RateLimiter:
    """Space requests apart by at least ``min_interval`` seconds.

    The first call never sleeps. Later calls sleep only for the time still
    missing, so a slow response already counts towards the interval. This is
    the "polite scraper" behaviour: no hammering a public endpoint.
    """

    min_interval: float = 1.0
    _last_request: float | None = field(default=None, init=False)

    def wait(self) -> float:
        """Sleep if needed and return the number of seconds slept."""

        if self.min_interval <= 0:
            return 0.0

        now = time.monotonic()
        if self._last_request is None:
            self._last_request = now
            return 0.0

        delay = self.min_interval - (now - self._last_request)
        if delay > 0:
            time.sleep(delay)
        else:
            delay = 0.0

        self._last_request = time.monotonic()
        return delay


def create_session() -> requests.Session:
    """Return a polite session that retries transient failures.

    A single retry policy for every source keeps scrape behaviour predictable:
    three attempts with exponential backoff on rate limits and 5xx responses.
    """

    session = requests.Session()

    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)

    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": config.USER_AGENT,
            "Accept": "application/json, text/plain, */*",
        }
    )

    return session
