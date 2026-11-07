"""Reporting: deterministic PDF generation and optional email delivery."""

from src.reporting.emailer import (
    EmailConfigError,
    EmailError,
    EmailResult,
    EmailSettings,
    build_message,
    send_email,
)
from src.reporting.pdf import generate_report
from src.reporting.summary import build_text_summary

__all__ = [
    "EmailConfigError",
    "EmailError",
    "EmailResult",
    "EmailSettings",
    "build_message",
    "build_text_summary",
    "generate_report",
    "send_email",
]
