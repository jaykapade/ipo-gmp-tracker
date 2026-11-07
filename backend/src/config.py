"""Central configuration for the IPO Checker.

Everything has a safe default so the project works without a ``.env`` file.
Values can be overridden with environment variables (or a ``.env`` file when
``python-dotenv`` is installed).
"""

from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def setup_logging() -> None:
    """Configure structured logging for the CLI and scrapers."""

    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _load_dotenv() -> None:
    """Load ``.env`` if python-dotenv is available; stay silent otherwise."""

    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    load_dotenv(REPO_ROOT / ".env")


_load_dotenv()


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value is not None and value.strip() else default


LOG_LEVEL = _env("LOG_LEVEL", "INFO").upper()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_path(name: str, default: str) -> Path:
    """Return a path, resolving relative values against the repo root.

    Resolving against the repo root means the database is found regardless of
    which directory the command is launched from.
    """

    path = Path(_env(name, default)).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def current_fiscal_year(today: date | None = None) -> str:
    """Return the Indian fiscal year label (April–March), e.g. ``2026-27``."""

    reference = today or date.today()
    start_year = reference.year if reference.month >= 4 else reference.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


# --- Database ---------------------------------------------------------------

DB_PATH = _env_path("IPO_DB_PATH", "data/ipo_intelligence.db")

# --- Screening --------------------------------------------------------------

MIN_GMP_PERCENT = _env_float("MIN_GMP_PERCENT", 20.0)
INCLUDE_UPCOMING = _env_bool("INCLUDE_UPCOMING", False)

# --- HTTP -------------------------------------------------------------------

REQUEST_TIMEOUT = _env_float("REQUEST_TIMEOUT", 30.0)
USER_AGENT = _env(
    "USER_AGENT",
    "IPO-Checker/0.1 (personal research; polite scraper)",
)

# --- Sources ----------------------------------------------------------------

INVESTORGAIN_REPORT_ID = _env_int("INVESTORGAIN_REPORT_ID", 331)
INVESTORGAIN_YEAR = _env_int("INVESTORGAIN_YEAR", date.today().year)
INVESTORGAIN_FISCAL_YEAR = _env(
    "INVESTORGAIN_FISCAL_YEAR",
    current_fiscal_year(),
)
INVESTORGAIN_URL = _env(
    "INVESTORGAIN_URL",
    "https://webnodejs.investorgain.com/cloud/v2/report/data-read/"
    f"{INVESTORGAIN_REPORT_ID}/1/9/{INVESTORGAIN_YEAR}/"
    f"{INVESTORGAIN_FISCAL_YEAR}/0/all?search=&v=19-49",
)

IPOWATCH_URL = _env(
    "IPOWATCH_URL",
    "https://ipowatch.in/ipo-grey-market-premium-latest-ipo-gmp/",
)
IPOWATCH_API_URL = _env(
    "IPOWATCH_API_URL",
    "https://ipowatch.in/server/api/ipo/GetIpoListingByStatus",
)

# --- Reporting --------------------------------------------------------------

REPORT_OUTPUT_DIR = _env_path("REPORT_OUTPUT_DIR", "reports")

# --- Email (SMTP) -----------------------------------------------------------

SMTP_HOST = _env("SMTP_HOST", "")
SMTP_PORT = _env_int("SMTP_PORT", 587)
SMTP_USE_TLS = _env_bool("SMTP_USE_TLS", True)
SMTP_USER = _env("SMTP_USER", "")
SMTP_PASSWORD = _env("SMTP_PASSWORD", "")
EMAIL_FROM = _env("EMAIL_FROM", SMTP_USER)
EMAIL_TO = _env("EMAIL_TO", "")
EMAIL_SUBJECT_PREFIX = _env("EMAIL_SUBJECT_PREFIX", "[IPO Checker]")

# --- API --------------------------------------------------------------------

API_HOST = _env("API_HOST", "127.0.0.1")
API_PORT = _env_int("API_PORT", 8000)
API_TOKEN = _env("API_TOKEN", "change-me")
CORS_ORIGINS = tuple(
    origin.strip()
    for origin in _env(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
)
