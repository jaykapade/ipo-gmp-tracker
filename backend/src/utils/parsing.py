"""Shared parsing helpers for scrapers and the analysis layer.

Scraped data is messy: numbers arrive as ``₹1,234.50``, percentages as
``14.32%``, and dates in half a dozen formats. Keeping the conversion rules in
one place means every source is parsed the same way and the rules can be tested
without touching the network.
"""

from __future__ import annotations

import html
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

# Indian Standard Time. IPO dates are Indian dates, so "today" is an IST date
# even when the machine running the code is in another timezone.
IST = timezone(timedelta(hours=5, minutes=30))

_EMPTY_VALUES = {
    "",
    "-",
    "--",
    "—",
    "–",
    "n/a",
    "na",
    "none",
    "null",
    "nil",
}

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_PERCENT_IN_BRACKETS_RE = re.compile(r"\(\s*(-?\d+(?:\.\d+)?)\s*%\s*\)")

# Inactive statuses win even when another keyword matches. "Closed" must be
# checked before "close" so an IPO that has finished bidding is not treated as
# an IPO that closes later.
_INACTIVE_KEYWORDS = (
    "withdrawn",
    "listed",
    "allotted",
    "refund",
    "cancelled",
    "canceled",
    "closed",
)
_ACTIVE_KEYWORDS = ("open", "live", "active", "bidding")

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d-%b-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%b %d %Y",
    "%B %d, %Y",
    "%B %d %Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y/%m/%d",
    # Year-less formats. The year is inferred from today's date.
    "%d-%b",
    "%d %b",
    "%d %B",
    "%b %d",
    "%B %d",
)

_DATE_TOKEN_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}\s*[-–—/]\s*[A-Za-z]{3,9}(?:\s*[-–—/]\s*\d{2,4})?"
    r"|[A-Za-z]{3,9}\s+\d{1,2},?\s*\d{4}"
)

_COMPACT_RANGE_RE = re.compile(
    r"(\d{1,2})\s*[-–—]\s*(\d{1,2})\s+([A-Za-z]{3,9})(?:\s+(\d{4}))?"
)


def clean_text(value: Any) -> str | None:
    """Strip HTML tags/entities and collapse whitespace.

    Returns ``None`` for empty or missing values so callers can rely on a
    single "no value" representation.
    """

    if value is None:
        return None

    text = html.unescape(str(value))
    text = _TAG_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()

    return text or None


def parse_float(value: Any) -> float | None:
    """Parse the first number in a value, tolerating currency symbols/commas.

    Examples::

        "₹1,234.50"  -> 1234.5
        "14.32%"     -> 14.32
        "-"          -> None
        "(12.5)"     -> -12.5
    """

    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = clean_text(value)
    if text is None:
        return None

    lowered = text.lower()
    if lowered in _EMPTY_VALUES:
        return None

    negative = lowered.startswith("(") and lowered.endswith(")")
    text = text.replace(",", "")

    match = _NUMBER_RE.search(text)
    if not match:
        return None

    number = float(match.group())
    return -number if negative else number


def parse_int(value: Any) -> int | None:
    """Like :func:`parse_float` but returns an integer."""

    number = parse_float(value)
    return int(number) if number is not None else None


def parse_price_band(value: Any) -> tuple[float | None, float | None]:
    """Split a price band such as ``₹62 - ₹66`` into ``(62.0, 66.0)``.

    Returns ``(None, None)`` when no number is present. A single price produces
    ``(price, None)``.
    """

    text = clean_text(value)
    if text is None:
        return None, None

    text = text.replace(",", "")
    numbers = [float(match) for match in re.findall(r"\d+(?:\.\d+)?", text)]

    if not numbers:
        return None, None
    if len(numbers) == 1:
        return numbers[0], None
    return numbers[0], numbers[1]


def parse_number_with_percent(value: Any) -> tuple[float | None, float | None]:
    """Split a cell like ``₹455 (12.35%)`` into ``(455.0, 12.35)``.

    The percentage in brackets is removed before the absolute number is parsed,
    which avoids accidentally reading the percentage as the price.
    """

    text = clean_text(value)
    if text is None:
        return None, None

    percent: float | None = None
    match = _PERCENT_IN_BRACKETS_RE.search(text)
    if match:
        percent = float(match.group(1))
        text = text[: match.start()]

    return parse_float(text), percent


def _infer_year(month: int, day: int, today: date) -> date:
    """Attach a year to a date that did not include one.

    Dates more than six months in the past are assumed to belong to next year,
    so a year-less "1-Jan" seen in November becomes next January rather than
    last January.
    """

    candidate = date(today.year, month, day)
    if candidate < today - timedelta(days=180):
        candidate = date(today.year + 1, month, day)

    return candidate


def parse_date(value: Any, *, today: date | None = None) -> date | None:
    """Parse the common date formats used by IPO sources.

    Accepts ISO dates/datetimes (including a trailing ``Z``), ``24-Sep-2026``,
    ``24 Sep 2026``, ``Sep 24, 2026``, ``24/09/2026`` and year-less variants
    such as ``24-Sep``. Returns ``None`` when a value cannot be parsed.
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(IST).date()
        return value.date()

    if isinstance(value, date):
        return value

    text = clean_text(value)
    if text is None:
        return None

    # ISO datetimes such as 2026-09-24T00:00:00.000Z.
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        parsed = None

    if parsed is not None:
        if parsed.tzinfo is not None:
            return parsed.astimezone(IST).date()
        return parsed.date()

    # Drop an optional weekday prefix, e.g. "Mon, 24 Sep 2026".
    text = re.sub(
        r"^(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*,?\s+",
        "",
        text,
        flags=re.IGNORECASE,
    )

    reference_day = today or today_ist()

    for date_format in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, date_format)
        except ValueError:
            continue

        if "%Y" in date_format:
            return parsed.date()

        return _infer_year(parsed.month, parsed.day, reference_day)

    return None


def split_date_range(
    value: Any,
    *,
    today: date | None = None,
) -> tuple[date | None, date | None]:
    """Split a combined date-range cell into ``(open_date, close_date)``.

    Handles forms like::

        "24-Sep-2026 to 28-Sep-2026"
        "24 Sep - 28 Sep 2026"
        "24-28 Sep 2026"
        "24 Sep 2026"
    """

    text = clean_text(value)
    if text is None:
        return None, None

    # "24-28 Sep 2026" has two days but only one month/year.
    compact = _COMPACT_RANGE_RE.search(text)
    if compact:
        start_day, end_day, month_name, year = compact.groups()
        if year:
            start = parse_date(f"{start_day}-{month_name}-{year}", today=today)
            end = parse_date(f"{end_day}-{month_name}-{year}", today=today)
        else:
            start = parse_date(f"{start_day}-{month_name}", today=today)
            end = parse_date(f"{end_day}-{month_name}", today=today)

        if start or end:
            return start, end

    parts = re.split(
        r"\s+(?:to|until|till|through|[-–—])\s+",
        text,
        flags=re.IGNORECASE,
    )
    if len(parts) >= 2:
        return parse_date(parts[0], today=today), parse_date(parts[1], today=today)

    tokens = [match.group(0) for match in _DATE_TOKEN_RE.finditer(text)]
    if len(tokens) >= 2:
        return parse_date(tokens[0], today=today), parse_date(tokens[1], today=today)
    if tokens:
        return parse_date(tokens[0], today=today), None

    # A single date without dashes/slashes, e.g. "24 Sep 2026", is not matched
    # by _DATE_TOKEN_RE. Try the whole string before giving up.
    single = parse_date(text, today=today)
    if single is not None:
        return single, None

    return None, None


def today_ist() -> date:
    """Return the current date in Indian Standard Time."""

    return datetime.now(IST).date()


def is_open_status(status: str | None) -> bool:
    """Return ``True`` only when the IPO status is exactly ``open``.

    Statuses such as ``Upcoming``, ``Closed``, ``Listed``, ``Withdrawn`` etc.
    are not saved. The match is case-insensitive and ignores surrounding
    whitespace.
    """

    return (status or "").strip().lower() == "open"


def derive_status_from_dates(
    open_date: str | None,
    close_date: str | None,
    *,
    today: date | None = None,
) -> str | None:
    """Derive an IPO status from its open and close dates.

    Returns ``"open"`` when today falls within the open/close window,
    ``"upcoming"`` when the open date is in the future, ``"closed"`` when the
    close date is in the past, or ``None`` when the dates can't be parsed.
    """

    reference_day = today or today_ist()

    parsed_open = parse_date(open_date) if open_date else None
    parsed_close = parse_date(close_date) if close_date else None

    if parsed_open is None and parsed_close is None:
        return None

    if parsed_open is not None and parsed_open > reference_day:
        return "upcoming"

    if parsed_close is not None and parsed_close < reference_day:
        return "closed"

    if parsed_open is not None and parsed_close is not None:
        if parsed_open <= reference_day <= parsed_close:
            return "open"

    if parsed_open is not None and reference_day >= parsed_open:
        return "open"

    return None


def is_active_status(
    status: str | None,
    open_date: date | None = None,
    close_date: date | None = None,
    *,
    include_upcoming: bool = False,
    today: date | None = None,
) -> bool:
    """Decide whether an IPO is still actionable.

    As a last resort, when the source does not provide a usable status, the
    open/close date range is used.
    """

    reference_day = today or today_ist()
    lowered = (status or "").strip().lower()

    if any(keyword in lowered for keyword in _INACTIVE_KEYWORDS):
        return False

    if "upcoming" in lowered:
        return include_upcoming

    if any(keyword in lowered for keyword in _ACTIVE_KEYWORDS):
        # An "open" status with a close date in the past is stale data.
        return close_date is None or close_date >= reference_day

    if "close" in lowered:
        # "Closes today" / "Closing" is still actionable today.
        return close_date is not None and close_date >= reference_day

    if open_date and close_date:
        return open_date <= reference_day <= close_date
    if open_date:
        return reference_day >= open_date
    if close_date:
        return reference_day <= close_date

    return False
