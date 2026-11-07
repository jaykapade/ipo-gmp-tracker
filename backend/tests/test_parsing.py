from datetime import UTC, date, datetime

import pytest

from src.utils.parsing import (
    clean_text,
    is_active_status,
    parse_date,
    parse_float,
    parse_int,
    parse_number_with_percent,
    parse_price_band,
    split_date_range,
)

# --- clean_text -------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("<b>Hello</b> &amp; welcome", "Hello & welcome"),
        ("  a \n\t b  ", "a b"),
        ("<div><span>GMP</span></div>", "GMP"),
    ],
)
def test_clean_text(raw, expected):
    assert clean_text(raw) == expected


# --- Numbers ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("-", None),
        ("--", None),
        ("—", None),
        ("N/A", None),
        ("na", None),
        ("₹1,234.50", 1234.5),
        ("14.32%", 14.32),
        ("(12.5)", -12.5),
        ("abc", None),
        (42, 42.0),
        (1.5, 1.5),
    ],
)
def test_parse_float(raw, expected):
    assert parse_float(raw) == expected


def test_parse_float_rejects_booleans():
    assert parse_float(True) is None
    assert parse_float(False) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("42.9", 42),
        ("₹1,234", 1234),
        ("-", None),
        (None, None),
    ],
)
def test_parse_int(raw, expected):
    assert parse_int(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("₹455 (12.35%)", (455.0, 12.35)),
        ("₹455", (455.0, None)),
        ("-", (None, None)),
        (None, (None, None)),
    ],
)
def test_parse_number_with_percent(raw, expected):
    assert parse_number_with_percent(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("₹62 - ₹66", (62.0, 66.0)),
        ("₹1,234 - ₹1,500", (1234.0, 1500.0)),
        ("₹94", (94.0, None)),
        ("-", (None, None)),
        (None, (None, None)),
    ],
)
def test_parse_price_band(raw, expected):
    assert parse_price_band(raw) == expected


# --- Dates ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-09-24", date(2026, 9, 24)),
        ("24-Sep-2026", date(2026, 9, 24)),
        ("24 Sep 2026", date(2026, 9, 24)),
        ("24 September 2026", date(2026, 9, 24)),
        ("Sep 24, 2026", date(2026, 9, 24)),
        ("September 24, 2026", date(2026, 9, 24)),
        ("24/09/2026", date(2026, 9, 24)),
        ("24-09-2026", date(2026, 9, 24)),
        ("2026/09/24", date(2026, 9, 24)),
        ("2026-09-24T00:00:00Z", date(2026, 9, 24)),
        ("2026-09-24T05:30:00+05:30", date(2026, 9, 24)),
        ("Mon, 24 Sep 2026", date(2026, 9, 24)),
        ("not a date", None),
        ("2026-13-45", None),
        ("", None),
        ("-", None),
        (None, None),
    ],
)
def test_parse_date(raw, expected):
    assert parse_date(raw) == expected


def test_parse_date_year_less_uses_reference_year():
    assert parse_date("24-Sep", today=date(2026, 9, 1)) == date(2026, 9, 24)


def test_parse_date_year_less_rolls_into_next_year():
    assert parse_date("01-Jan", today=date(2026, 11, 7)) == date(2027, 1, 1)


def test_parse_date_accepts_date_objects():
    day = date(2026, 9, 24)

    assert parse_date(day) == day
    assert parse_date(datetime(2026, 9, 24, 23, 0)) == day


def test_parse_date_converts_timezone_to_ist():
    # 23:00 UTC is 04:30 IST on the next calendar day.
    utc_value = datetime(2026, 9, 24, 23, 0, tzinfo=UTC)

    assert parse_date(utc_value) == date(2026, 9, 25)


# --- Date ranges ------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "24-Sep-2026 to 28-Sep-2026",
            (date(2026, 9, 24), date(2026, 9, 28)),
        ),
        (
            "24 Sep - 28 Sep 2026",
            (date(2026, 9, 24), date(2026, 9, 28)),
        ),
        (
            "24-28 Sep 2026",
            (date(2026, 9, 24), date(2026, 9, 28)),
        ),
        (
            "24-Sep-2026 28-Sep-2026",
            (date(2026, 9, 24), date(2026, 9, 28)),
        ),
        ("24 Sep 2026", (date(2026, 9, 24), None)),
        ("24-Sep-2026", (date(2026, 9, 24), None)),
        ("-", (None, None)),
        (None, (None, None)),
    ],
)
def test_split_date_range(raw, expected):
    assert split_date_range(raw, today=date(2026, 9, 1)) == expected


# --- Active status ----------------------------------------------------------

TODAY = date(2026, 9, 15)


@pytest.mark.parametrize(
    ("status", "open_date", "close_date", "include_upcoming", "expected"),
    [
        # Explicitly active status, still open.
        ("Open", date(2026, 9, 14), date(2026, 9, 18), False, True),
        # "Open" but the close date has passed: stale source data.
        ("Open", date(2026, 9, 1), date(2026, 9, 10), False, False),
        # Inactive keywords always win.
        ("Listed", None, None, False, False),
        ("Closed", date(2026, 9, 1), date(2026, 9, 18), False, False),
        ("Withdrawn", None, None, False, False),
        # Upcoming is opt-in.
        ("Upcoming", None, None, False, False),
        ("Upcoming", None, None, True, True),
        # Closing today is still actionable.
        ("Closes today", None, TODAY, False, True),
        ("Closes today", None, date(2026, 9, 10), False, False),
        # No status: fall back to the date range.
        (None, date(2026, 9, 10), date(2026, 9, 20), False, True),
        (None, date(2026, 9, 10), date(2026, 9, 20), False, True),
        (None, date(2026, 9, 20), None, False, False),
        (None, date(2026, 9, 1), None, False, True),
        (None, None, None, False, False),
    ],
)
def test_is_active_status(
    status,
    open_date,
    close_date,
    include_upcoming,
    expected,
):
    assert (
        is_active_status(
            status,
            open_date,
            close_date,
            include_upcoming=include_upcoming,
            today=TODAY,
        )
        is expected
    )
