"""Tests for the IPO Watch JSON row mapping."""

import pytest

from src.scrapers.ipowatch import convert_to_ipo

ROW = {
    "id": 1141,
    "slug": "vedant-poly-fabs-ipo-details",
    "name": "Vedant Poly Fabs",
    "type": "NSE Emerge",
    "issueStatus": "Closed",
    "sector": "Packaging",
    "issuePrice": 94.0,
    "estPrice": 95,
    "premiumPct": 1.06,
    "priceBand": "₹88.00 - ₹94.00",
    "lotSize": "1,200 shares",
    "issueSize": 566820000.0,
    "openDate": "2 Nov 2026",
    "closeDate": "4 Nov 2026",
    "listingDate": "2026-11-09T00:00:00",
    "gmp": 1.0,
    "subscription": 1.9,
}


def test_convert_to_ipo_maps_all_fields():
    ipo = convert_to_ipo(ROW)

    assert ipo.name == "Vedant Poly Fabs"
    assert ipo.normalized_name == "vedant_poly_fabs"
    assert ipo.category == "SME"
    assert ipo.exchange == "NSE"
    assert ipo.status == "Closed"
    assert ipo.sector == "Packaging"

    assert ipo.gmp == 1.0
    assert ipo.gmp_percent == 1.06
    assert ipo.issue_price == 94.0
    assert ipo.issue_price_lower == 88.0
    assert ipo.issue_price_upper == 94.0
    assert ipo.estimated_listing_price == 95.0

    assert ipo.ipo_size_cr == "56.68"
    assert ipo.lot_size == "1,200 shares"
    assert ipo.subscription == 1.9

    assert ipo.open_date == "2026-11-02"
    assert ipo.close_date == "2026-11-04"
    assert ipo.listing_date == "2026-11-09"
    assert ipo.source_url == "https://ipowatch.in/vedant-poly-fabs-ipo-details/"


@pytest.mark.parametrize(
    ("ipo_type", "category", "exchange"),
    [
        ("BSE SME", "SME", "BSE"),
        ("NSE Emerge", "SME", "NSE"),
        ("Mainboard", "Mainboard", None),
        ("NSE/BSE Mainboard", "Mainboard", "NSE/BSE"),
        (None, "Mainboard", None),
    ],
)
def test_type_classification(ipo_type, category, exchange):
    ipo = convert_to_ipo({"name": "Example Ltd", "type": ipo_type})

    assert ipo.category == category
    assert ipo.exchange == exchange


def test_issue_price_falls_back_to_upper_band():
    row = {
        "name": "Example Ltd",
        "priceBand": "₹88.00 - ₹94.00",
    }

    ipo = convert_to_ipo(row)

    assert ipo.issue_price == 94.0
    assert ipo.issue_price_lower == 88.0
    assert ipo.issue_price_upper == 94.0


def test_missing_name_raises():
    with pytest.raises(ValueError, match="company name"):
        convert_to_ipo({"id": 1})
