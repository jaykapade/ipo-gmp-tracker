"""Subscriber emails: the daily open-IPO digest and the research report.

Every subscriber email carries a link to the frontend's ``/subscription`` page,
which unsubscribes with the subscriber's token.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from src import config
from src.database import db
from src.reporting.email_html import (
    _BORDER,
    _INK,
    _LINK,
    _MUTED,
    _date,
    _e,
    _rupees,
    page,
)
from src.reporting.emailer import EmailSettings, send_email
from src.reporting.summary import _number
from src.utils.parsing import IST

logger = logging.getLogger(__name__)

_EMAIL = re.compile(r"[^@\s<>,;\"']+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+")
DIGEST_LIMIT = 50


def normalize_email(raw: str) -> str | None:
    """Return the lower-cased address, or ``None`` if it does not look valid."""

    email = raw.strip().lower()
    return email if len(email) <= 254 and _EMAIL.fullmatch(email) else None


def subscription_link(action: str, token: str) -> str:
    return f"{config.SITE_URL}/subscription?{urlencode({'action': action, 'token': token})}"


def _settings_for(email: str, settings: EmailSettings | None) -> EmailSettings:
    return replace(settings or EmailSettings.from_config(), recipients=(email,))


def _gmp(ipo: dict[str, Any]) -> str:
    text = _rupees(ipo.get("latest_gmp"))
    if ipo.get("latest_gmp_percent") is not None:
        text += f" ({_number(ipo['latest_gmp_percent'], '%')})"
    return text


def _price(ipo: dict[str, Any]) -> float | None:
    return ipo.get("issue_price") or ipo.get("issue_price_upper")


def build_digest(
    ipos: list[dict[str, Any]],
    *,
    unsubscribe_url: str,
    generated_at: datetime | None = None,
) -> tuple[str, str]:
    """Return ``(text, html)`` listing open IPOs with their latest GMP."""

    moment = (generated_at or datetime.now(IST)).astimezone(IST)
    when = moment.strftime("%d %b %Y")
    count = f"{len(ipos)} open IPO{'s' if len(ipos) != 1 else ''}"

    lines = [f"Open IPOs on {when}: {len(ipos)}", ""]
    for ipo in ipos:
        lines.append(
            f"- {ipo['name']} ({ipo.get('category') or 'IPO'}): GMP {_gmp(ipo)}, "
            f"issue {_rupees(_price(ipo))}, closes {_date(ipo.get('close_date'))}"
        )
    lines += ["", f"Unsubscribe: {unsubscribe_url}"]

    cell = f"padding:9px 8px;border-top:1px solid {_BORDER};font-size:13px;color:{_INK};"
    head = f"padding:6px 8px;font-size:11px;color:{_MUTED};text-align:left;"
    body = "".join(
        f'<tr><td style="{cell}"><strong>{_e(ipo["name"])}</strong>'
        f'<div style="font-size:11px;color:{_MUTED};">{_e(ipo.get("category") or "IPO")}</div></td>'
        f'<td style="{cell}white-space:nowrap;">{_e(_gmp(ipo))}</td>'
        f'<td style="{cell}white-space:nowrap;">{_e(_rupees(_price(ipo)))}</td>'
        f'<td style="{cell}white-space:nowrap;">{_e(_date(ipo.get("close_date")))}</td></tr>'
        for ipo in ipos
    )
    rows = (
        f'<tr><td style="padding:8px 16px 16px;border-top:1px solid {_BORDER};">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        f'<tr><th style="{head}">IPO</th><th style="{head}">GMP</th>'
        f'<th style="{head}">Issue price</th><th style="{head}">Closes</th></tr>'
        f"{body}</table></td></tr>"
    )
    html = page(
        "Open IPOs today",
        preheader=f"{count} with the latest grey-market premium.",
        header=f'<div style="font-size:13px;color:{_MUTED};">{_e(when)} · {_e(count)}, '
        "highest GMP first</div>",
        rows=rows,
        footer=(
            "You get this because you subscribed on IPO Checker. "
            f'<a href="{_e(unsubscribe_url)}" style="color:{_LINK};">Unsubscribe</a>'
        ),
    )
    return "\n".join(lines), html


@dataclass(frozen=True)
class DigestResult:
    subscribers: int
    sent: int
    failed: int
    open_ipos: int


def send_daily_digest(
    *,
    db_path: str | Path | None = None,
    settings: EmailSettings | None = None,
    dry_run: bool = False,
) -> DigestResult:
    """Email the open-IPO digest to every confirmed subscriber.

    Nothing is sent on days without open IPOs. One failed address does not stop
    the others.
    """

    subscribers = db.list_confirmed_subscribers(db_path=db_path)
    ipos = db.list_ipos(
        status="open", sort="gmp_percent", order="desc", limit=DIGEST_LIMIT, db_path=db_path
    )
    if not subscribers or not ipos:
        return DigestResult(len(subscribers), 0, 0, len(ipos))

    sent, failed = _send_each(
        subscribers,
        subject=f"Open IPOs today: {len(ipos)}",
        build=lambda unsubscribe: build_digest(ipos, unsubscribe_url=unsubscribe),
        settings=settings,
        dry_run=dry_run,
    )
    return DigestResult(len(subscribers), sent, failed, len(ipos))


def send_report(
    *,
    subject: str,
    build: Callable[[str], tuple[str, str]],
    count: int,
    attachments: Iterable[str | Path] = (),
    db_path: str | Path | None = None,
    settings: EmailSettings | None = None,
    dry_run: bool = False,
) -> DigestResult:
    """Email the owner's research report to every confirmed subscriber.

    ``build(unsubscribe_url)`` returns ``(text, html)``; ``count`` is the number
    of IPOs in it (for the result only).
    """

    subscribers = db.list_confirmed_subscribers(db_path=db_path)
    sent, failed = _send_each(
        subscribers,
        subject=subject,
        build=build,
        attachments=tuple(attachments),
        settings=settings,
        dry_run=dry_run,
    )
    return DigestResult(len(subscribers), sent, failed, count)


def _send_each(
    subscribers: list[dict[str, str]],
    *,
    subject: str,
    build: Callable[[str], tuple[str, str]],
    attachments: tuple[str | Path, ...] = (),
    settings: EmailSettings | None,
    dry_run: bool,
) -> tuple[int, int]:
    """Send one email per subscriber with their own unsubscribe link; (sent, failed)."""

    sent = failed = 0
    # shortcut: one SMTP connection per subscriber, fine for dozens; batch past a few hundred.
    for subscriber in subscribers:
        unsubscribe = subscription_link("unsubscribe", subscriber["token"])
        text, html = build(unsubscribe)
        try:
            send_email(
                subject=subject,
                body=text,
                html=html,
                attachments=attachments,
                settings=_settings_for(subscriber["email"], settings),
                dry_run=dry_run,
                list_unsubscribe=unsubscribe,
            )
            sent += 1
        except Exception:
            failed += 1
            logger.exception("Email to %s failed", subscriber["email"])
    return sent, failed


__all__ = [
    "DigestResult",
    "build_digest",
    "normalize_email",
    "send_daily_digest",
    "send_report",
    "subscription_link",
]
