"""SMTP email delivery with a safe dry-run mode."""

from __future__ import annotations

import mimetypes
import re
import smtplib
from collections.abc import Iterable
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path

from src import config


class EmailError(RuntimeError):
    """Base class for email delivery problems."""


class EmailConfigError(EmailError):
    """Raised when required SMTP or recipient settings are missing."""


def _split_addresses(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    parts = re.split(r"[,;]", value)
    return tuple(part.strip() for part in parts if part.strip())


@dataclass(frozen=True)
class EmailSettings:
    """Everything needed to send one message."""

    host: str
    port: int = 587
    username: str = ""
    password: str = ""
    use_tls: bool = True
    sender: str = ""
    recipients: tuple[str, ...] = ()
    subject_prefix: str = "[IPO Checker]"

    @classmethod
    def from_config(cls) -> EmailSettings:
        """Read settings from ``src.config`` (environment / ``.env``)."""

        return cls(
            host=config.SMTP_HOST,
            port=config.SMTP_PORT,
            username=config.SMTP_USER,
            password=config.SMTP_PASSWORD,
            use_tls=config.SMTP_USE_TLS,
            sender=config.EMAIL_FROM,
            recipients=_split_addresses(config.EMAIL_TO),
            subject_prefix=config.EMAIL_SUBJECT_PREFIX,
        )

    def validate(self, *, dry_run: bool) -> None:
        if not self.recipients:
            raise EmailConfigError(
                "EMAIL_TO is empty; set at least one recipient address."
            )
        if not dry_run and not self.host:
            raise EmailConfigError("SMTP_HOST is empty; set the SMTP server.")
        if not dry_run and not self.sender:
            raise EmailConfigError("EMAIL_FROM is empty; set the sender address.")


@dataclass(frozen=True)
class EmailResult:
    """Outcome of a send attempt, including dry runs."""

    sent: bool
    dry_run: bool
    subject: str
    sender: str
    recipients: tuple[str, ...]
    attachments: tuple[str, ...]


def _attachment_part(path: Path) -> tuple[str, bytes, str]:
    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type:
        maintype, subtype = mime_type.split("/", 1)
    else:
        maintype, subtype = "application", "octet-stream"
    return path.name, path.read_bytes(), f"{maintype}/{subtype}"


def build_message(
    settings: EmailSettings,
    *,
    subject: str,
    body: str,
    attachments: Iterable[str | Path] = (),
) -> EmailMessage:
    """Build the ``EmailMessage`` without connecting to a server."""

    message = EmailMessage()
    message["Subject"] = f"{settings.subject_prefix} {subject}".strip()
    message["From"] = settings.sender
    message["To"] = ", ".join(settings.recipients)
    message.set_content(body)

    for attachment in attachments:
        path = Path(attachment)
        if not path.is_file():
            raise FileNotFoundError(f"Attachment not found: {path}")

        filename, payload, mime_type = _attachment_part(path)
        maintype, subtype = mime_type.split("/", 1)
        message.add_attachment(
            payload,
            maintype=maintype,
            subtype=subtype,
            filename=filename,
        )

    return message


def send_email(
    *,
    subject: str,
    body: str,
    attachments: Iterable[str | Path] = (),
    settings: EmailSettings | None = None,
    dry_run: bool = False,
) -> EmailResult:
    """Send an email, or validate and describe it when ``dry_run`` is true."""

    resolved = settings or EmailSettings.from_config()
    resolved.validate(dry_run=dry_run)

    paths = tuple(Path(path) for path in attachments)
    message = build_message(
        resolved,
        subject=subject,
        body=body,
        attachments=paths,
    )

    result = EmailResult(
        sent=False,
        dry_run=dry_run,
        subject=str(message["Subject"]),
        sender=resolved.sender,
        recipients=resolved.recipients,
        attachments=tuple(str(path) for path in paths),
    )

    if dry_run:
        return result

    with smtplib.SMTP(
        resolved.host,
        resolved.port,
        timeout=config.REQUEST_TIMEOUT,
    ) as smtp:
        smtp.ehlo()
        if resolved.use_tls:
            smtp.starttls()
            smtp.ehlo()
        if resolved.username:
            smtp.login(resolved.username, resolved.password)
        smtp.send_message(message)

    return EmailResult(
        sent=True,
        dry_run=False,
        subject=result.subject,
        sender=result.sender,
        recipients=result.recipients,
        attachments=result.attachments,
    )
