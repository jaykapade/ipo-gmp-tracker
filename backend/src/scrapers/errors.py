"""Typed exceptions raised by the scraper layer.

Why not plain ``Exception``? Typed errors let callers tell *what* went wrong
without parsing message strings. The pipeline can then decide whether a
failure is recoverable (one bad row) or fatal (the whole fetch failed).

``ParseError`` also inherits from ``ValueError`` for backwards compatibility:
older callers used ``pytest.raises(ValueError)`` and still work.
"""

from __future__ import annotations


class ScraperError(Exception):
    """Base class for every scraper failure."""


class FetchError(ScraperError):
    """The remote source could not be fetched or did not return JSON."""


class ParseError(ScraperError, ValueError):
    """The payload did not match the shape the scraper expects."""
