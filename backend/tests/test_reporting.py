"""Tests for PDF generation and the SMTP dry-run path."""

from datetime import date

import pytest

from src.analysis.analyzer import analyze_candidate
from src.analysis.filters import Candidate
from src.reporting.emailer import (
    EmailConfigError,
    EmailSettings,
    build_message,
    send_email,
)
from src.reporting.pdf import generate_report


def make_analysis(
    *,
    gmp: float = 35.0,
    gmp_percent: float = 35.0,
    pe: float = 18.0,
    subscription: float = 5.0,
):
    ipo = {
        "id": 1,
        "name": "Example Industries Ltd",
        "issue_price": 100.0,
        "ipo_size_cr": "80.00",
        "subscription": subscription,
        "pe": pe,
        "close_date": "2026-09-20",
        "status": "Open",
    }
    history = [
        {
            "gmp": gmp,
            "gmp_percent": gmp_percent,
            "source": "test",
            "recorded_at": "2026-09-15T00:00:00+00:00",
        },
        {
            "gmp": 20.0,
            "gmp_percent": 20.0,
            "source": "test",
            "recorded_at": "2026-09-10T00:00:00+00:00",
        },
    ]
    candidate = Candidate(
        ipo=ipo,
        latest_gmp=history[0],
        history=history,
        close_date=date(2026, 9, 20),
    )
    return analyze_candidate(candidate, today=date(2026, 9, 15))


def test_generate_report_creates_pdf(tmp_path):
    output = tmp_path / "report.pdf"

    path = generate_report(
        [make_analysis()],
        output_path=output,
        min_gmp_percent=20,
        include_upcoming=False,
    )

    assert path == output
    payload = output.read_bytes()
    assert payload.startswith(b"%PDF")
    assert len(payload) > 1000


def test_generate_report_handles_empty_candidates(tmp_path):
    output = tmp_path / "empty.pdf"

    path = generate_report([], output_path=output, min_gmp_percent=20)

    assert path.exists()
    assert path.read_bytes().startswith(b"%PDF")


def test_build_message_includes_prefix_and_attachment(tmp_path):
    attachment = tmp_path / "report.pdf"
    attachment.write_bytes(b"%PDF-1.4 test")

    settings = EmailSettings(
        host="smtp.example.com",
        sender="from@example.com",
        recipients=("to@example.com", "second@example.com"),
    )

    message = build_message(
        settings,
        subject="Daily report",
        body="Body text",
        attachments=[attachment],
    )

    assert message["Subject"] == "[IPO Checker] Daily report"
    assert message["From"] == "from@example.com"
    assert message["To"] == "to@example.com, second@example.com"

    parts = list(message.iter_parts())
    assert any(part.get_filename() == "report.pdf" for part in parts)


def test_send_email_dry_run_does_not_connect(tmp_path):
    attachment = tmp_path / "report.pdf"
    attachment.write_bytes(b"%PDF-1.4 test")

    settings = EmailSettings(
        host="",  # dry runs must not need a server
        sender="from@example.com",
        recipients=("to@example.com",),
    )

    result = send_email(
        subject="Daily report",
        body="Body text",
        attachments=[attachment],
        settings=settings,
        dry_run=True,
    )

    assert result.dry_run is True
    assert result.sent is False
    assert result.subject == "[IPO Checker] Daily report"
    assert result.recipients == ("to@example.com",)
    assert result.attachments == (str(attachment),)


def test_send_email_requires_recipients():
    settings = EmailSettings(
        host="smtp.example.com",
        sender="from@example.com",
        recipients=(),
    )

    with pytest.raises(EmailConfigError, match="EMAIL_TO"):
        send_email(
            subject="Report",
            body="Body",
            settings=settings,
            dry_run=True,
        )


def test_send_email_requires_host_when_sending():
    settings = EmailSettings(
        host="",
        sender="from@example.com",
        recipients=("to@example.com",),
    )

    with pytest.raises(EmailConfigError, match="SMTP_HOST"):
        send_email(
            subject="Report",
            body="Body",
            settings=settings,
            dry_run=False,
        )


def test_missing_attachment_raises(tmp_path):
    settings = EmailSettings(
        host="smtp.example.com",
        sender="from@example.com",
        recipients=("to@example.com",),
    )

    with pytest.raises(FileNotFoundError):
        send_email(
            subject="Report",
            body="Body",
            attachments=[tmp_path / "missing.pdf"],
            settings=settings,
            dry_run=True,
        )
