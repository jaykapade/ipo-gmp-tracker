"""Name normalisation shared by every scraper.

This module deliberately contains *only* normalisation logic. Scraping and
parsing live in ``backend/scrapers`` and ``backend/utils/parsing.py``.
"""

from __future__ import annotations

import re

# Matches the company suffixes we want to ignore when matching names across
# sources. Keep this in sync with the alias table planned for cross-source
# matching.
_COMPANY_SUFFIX_RE = re.compile(
    r"\b(limited|ltd|ltd\.|limited\.)\b",
    re.IGNORECASE,
)


def normalize_name(name: str | None) -> str:
    """Convert an IPO/company name into a stable cross-source key.

    Examples::

        A-One Steels          -> a_one_steels
        A One Steels          -> a_one_steels
        A-ONE STEELS          -> a_one_steels
        A-One Steels Ltd      -> a_one_steels
        A-One Steels Limited  -> a_one_steels
    """

    if not name:
        return ""

    name = name.lower().strip()
    name = _COMPANY_SUFFIX_RE.sub("", name)

    # Replace anything that is not a letter or number with an underscore.
    name = re.sub(r"[^a-z0-9]+", "_", name)

    return name.strip("_")
