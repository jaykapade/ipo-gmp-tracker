
from pydantic import BaseModel


class IPO(BaseModel):
    """
    Common IPO data model.

    normalized_name is the canonical identity used to match
    the same IPO across different sources.
    """

    name: str
    normalized_name: str

    # Source-specific ID
    ipo_id: int | None = None

    # Common IPO information
    category: str | None = None

    # IPO Watch fields
    status: str | None = None
    gmp_indicator: str | None = None

    # GMP data
    gmp: float | None = None
    gmp_percent: float | None = None

    # Pricing
    issue_price: float | None = None
    issue_price_lower: float | None = None
    issue_price_upper: float | None = None
    estimated_listing_price: float | None = None

    # Other IPO information
    ipo_size_cr: str | None = None
    pe: float | None = None
    sector: str | None = None
    exchange: str | None = None
    lot_size: str | None = None
    subscription: float | None = None

    # Provenance
    source_url: str | None = None
    rhp_url: str | None = None

    # Dates
    open_date: str | None = None
    close_date: str | None = None
    listing_date: str | None = None

    updated_at: str | None = None
