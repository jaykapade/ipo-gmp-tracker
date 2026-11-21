"""Central configuration for the IPO Checker.

Everything has a safe default so the project works without a ``.env`` file.
Values can be overridden with environment variables (or a ``.env`` file when
``python-dotenv`` is installed).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
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
    """Load ``.env.local`` then ``.env`` if python-dotenv is available.

    Real environment variables always win; ``.env.local`` (machine-specific,
    gitignored) overrides ``.env`` because the first file loaded sets a key.
    """

    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    for name in (".env.local", ".env"):
        load_dotenv(REPO_ROOT / name)


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

# --- Scheduled research -------------------------------------------------------

# ``run --research`` reuses an IPO's completed AI research when it is newer
# than this, instead of spending another run on it.
RESEARCH_MAX_AGE_HOURS = _env_float("RESEARCH_MAX_AGE_HOURS", 24.0)

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
#
# Generation roles (docs/ipo-research-framework.md §P4) can each point at a
# different provider/model via LLM_ROLE_<ROLE>_{PROVIDER,MODEL,BASE_URL,
# API_KEY,FALLBACKS}; unset fields inherit the global LLM_* values. The
# embedder role maps onto the LLM_EMBED_* settings.
#
# The researcher role gathers cited facts from the web (claude-code only for
# now). Its unset fields inherit the *extractor* role, not the globals.

LLM_ROLES: tuple[str, ...] = (
    "analyst",
    "verifier",
    "extractor",
    "challenger",
    "researcher",
)
# Optional roles stay off unless their model is configured explicitly.
OPTIONAL_LLM_ROLES: frozenset[str] = frozenset({"challenger"})
# Roles whose unset fields inherit another role instead of the globals.
ROLE_PARENTS: dict[str, str] = {"researcher": "extractor"}
# Roles that need a provider with web search/fetch tools.
WEB_LLM_ROLES: frozenset[str] = frozenset({"researcher"})


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


@dataclass(frozen=True)
class RoleOverride:
    """Per-role overrides; ``None`` means "inherit the global setting"."""

    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    fallback_providers: tuple[str, ...] | None = None

    @classmethod
    def from_env(cls, role: str) -> RoleOverride:
        prefix = f"LLM_ROLE_{role.upper()}_"
        provider = _env_optional(prefix + "PROVIDER")
        fallbacks = _env_optional(prefix + "FALLBACKS")
        return cls(
            provider=provider.lower() if provider else None,
            model=_env_optional(prefix + "MODEL"),
            base_url=_env_optional(prefix + "BASE_URL"),
            api_key=_env_optional(prefix + "API_KEY"),
            fallback_providers=_split_csv(fallbacks) if fallbacks else None,
        )

    def is_empty(self) -> bool:
        return all(
            value is None
            for value in (
                self.provider,
                self.model,
                self.base_url,
                self.api_key,
                self.fallback_providers,
            )
        )


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
    max_concurrency: int = 2
    rerank_provider: str = "llm"
    research_timeout_seconds: float = 600.0
    research_max_turns: int = 30
    web_research: bool = False
    roles: Mapping[str, RoleOverride] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> LLMSettings:
        """Build settings from the current environment."""

        return cls(
            enabled=_env_bool("LLM_ENABLED", False),
            provider=_env("LLM_PROVIDER", "ollama").lower(),
            base_url=_env_optional("LLM_BASE_URL"),
            api_key=_env("LLM_API_KEY", ""),
            model=_env("LLM_MODEL", "qwen2.5:7b-instruct"),
            embed_provider=_env(
                "LLM_ROLE_EMBEDDER_PROVIDER", _env("LLM_EMBED_PROVIDER", "ollama")
            ).lower(),
            embed_model=_env(
                "LLM_ROLE_EMBEDDER_MODEL", _env("LLM_EMBED_MODEL", "nomic-embed-text")
            ),
            embed_base_url=_env_optional("LLM_ROLE_EMBEDDER_BASE_URL")
            or _env_optional("LLM_EMBED_BASE_URL"),
            fallback_providers=_split_csv(_env("LLM_FALLBACK_PROVIDERS", "")),
            allow_cloud=_env_bool("LLM_ALLOW_CLOUD", False),
            temperature=_env_float("LLM_TEMPERATURE", 0.0),
            timeout_seconds=_env_float("LLM_TIMEOUT_SECONDS", 120.0),
            max_context=_env_int("LLM_MAX_CONTEXT", 8192),
            cache=_env_bool("LLM_CACHE", True),
            max_concurrency=_env_int("LLM_MAX_CONCURRENCY", 2),
            rerank_provider=_env("RERANK_PROVIDER", "llm").lower(),
            research_timeout_seconds=_env_float("RESEARCH_TIMEOUT_SECONDS", 600.0),
            research_max_turns=_env_int("RESEARCH_MAX_TURNS", 30),
            roles={
                role: override
                for role in LLM_ROLES
                if not (override := RoleOverride.from_env(role)).is_empty()
            },
        )

    def role_configured(self, role: str) -> bool:
        """Whether ``role`` has an explicit model (required for optional roles)."""

        override = self.roles.get(role)
        return override is not None and override.model is not None

    def for_role(self, role: str) -> LLMSettings:
        """Resolve the effective settings for one generation role.

        Unset role fields inherit the global values. The global base URL is
        only inherited when the role keeps the global provider — an Ollama URL
        is meaningless to a cloud provider (and vice versa).
        """

        if role not in LLM_ROLES:
            raise ValueError(
                f"unknown LLM role {role!r}; known roles: {', '.join(LLM_ROLES)}"
            )
        parent = ROLE_PARENTS.get(role)
        base = self.for_role(parent) if parent else self
        override = self.roles.get(role) or RoleOverride()
        resolved = _apply_override(base, override)
        if role in WEB_LLM_ROLES:
            resolved = replace(
                resolved,
                web_research=True,
                timeout_seconds=max(
                    resolved.timeout_seconds, self.research_timeout_seconds
                ),
                # A cached web answer would hide fresh filings; never cache.
                cache=False,
            )
        return resolved


def _apply_override(base: LLMSettings, override: RoleOverride) -> LLMSettings:
    """Layer one role override on top of ``base`` settings."""

    provider = override.provider or base.provider
    if override.base_url is not None:
        base_url: str | None = override.base_url
    elif provider == base.provider:
        base_url = base.base_url
    else:
        base_url = None
    return replace(
        base,
        provider=provider,
        model=override.model or base.model,
        base_url=base_url,
        api_key=override.api_key or base.api_key,
        fallback_providers=(
            override.fallback_providers
            if override.fallback_providers is not None
            else base.fallback_providers
        ),
        roles={},
    )


LLM = LLMSettings.from_env()
