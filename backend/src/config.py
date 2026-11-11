"""Central configuration for the IPO Checker.

Everything has a safe default so the project works without a ``.env`` file.
Values can be overridden with environment variables (or a ``.env`` file when
``python-dotenv`` is installed).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
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


def _env_optional(name: str) -> str | None:
    """Return a trimmed env value, or ``None`` when unset/blank."""

    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def current_fiscal_year(today: date | None = None) -> str:
    """Return the Indian fiscal year label (April–March), e.g. ``2026-27``."""

    reference = today or date.today()  # noqa: DTZ011 - calendar date, not a timestamp
    start_year = reference.year if reference.month >= 4 else reference.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


# --- Database ---------------------------------------------------------------

DB_PATH = _env_path("IPO_DB_PATH", "data/ipo_intelligence.db")

# --- Screening --------------------------------------------------------------

MIN_GMP_PERCENT = _env_float("MIN_GMP_PERCENT", 20.0)
INCLUDE_UPCOMING = _env_bool("INCLUDE_UPCOMING", False)

# --- HTTP -------------------------------------------------------------------

REQUEST_TIMEOUT = _env_float("REQUEST_TIMEOUT", 30.0)
REQUEST_DELAY_SECONDS = _env_float("REQUEST_DELAY_SECONDS", 1.0)
USER_AGENT = _env(
    "USER_AGENT",
    "IPO-Checker/0.1 (personal research; polite scraper)",
)

# --- Sources ----------------------------------------------------------------

INVESTORGAIN_REPORT_ID = _env_int("INVESTORGAIN_REPORT_ID", 331)
INVESTORGAIN_YEAR = _env_int(
    "INVESTORGAIN_YEAR",
    date.today().year,  # noqa: DTZ011 - calendar year, not a timestamp
)
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


# --- AI / LLM (optional, provider-agnostic) ----------------------------------
#
# Switching providers is a config change, not a code change. Local providers
# are the default; cloud providers additionally require LLM_ALLOW_CLOUD=true
# and LLM_API_KEY so nothing leaves the machine by accident.


@dataclass(frozen=True)
class LLMSettings:
    """AI provider selection, read from the ``LLM_*`` environment variables."""

    enabled: bool = False
    provider: str = "ollama"
    base_url: str | None = None
    api_key: str = ""
    model: str = "qwen2.5:7b-instruct"
    embed_provider: str = "ollama"
    embed_model: str = "nomic-embed-text"
    embed_base_url: str | None = None
    fallback_providers: tuple[str, ...] = ()
    allow_cloud: bool = False
    temperature: float = 0.0
    timeout_seconds: float = 120.0
    max_context: int = 8192
    cache: bool = True

    @classmethod
    def from_env(cls) -> LLMSettings:
        """Build settings from the current environment."""

        return cls(
            enabled=_env_bool("LLM_ENABLED", False),
            provider=_env("LLM_PROVIDER", "ollama").lower(),
            base_url=_env_optional("LLM_BASE_URL"),
            api_key=_env("LLM_API_KEY", ""),
            model=_env("LLM_MODEL", "qwen2.5:7b-instruct"),
            embed_provider=_env("LLM_EMBED_PROVIDER", "ollama").lower(),
            embed_model=_env("LLM_EMBED_MODEL", "nomic-embed-text"),
            embed_base_url=_env_optional("LLM_EMBED_BASE_URL"),
            fallback_providers=tuple(
                name.strip()
                for name in _env("LLM_FALLBACK_PROVIDERS", "").split(",")
                if name.strip()
            ),
            allow_cloud=_env_bool("LLM_ALLOW_CLOUD", False),
            temperature=_env_float("LLM_TEMPERATURE", 0.0),
            timeout_seconds=_env_float("LLM_TIMEOUT_SECONDS", 120.0),
            max_context=_env_int("LLM_MAX_CONTEXT", 8192),
            cache=_env_bool("LLM_CACHE", True),
        )


LLM = LLMSettings.from_env()
