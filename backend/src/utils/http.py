"""Shared HTTP session with retries, timeouts and a documented user agent."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src import config


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
