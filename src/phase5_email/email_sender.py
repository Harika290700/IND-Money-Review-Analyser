"""
Phase 5 -- SMTP Email Dispatch

Sends the weekly pulse report as a multipart email (HTML + plain-text fallback)
using Python's built-in smtplib and email.mime modules.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config

logger = logging.getLogger(__name__)


def send_pulse_email(
    html_content: str,
    text_content: str,
    recipient_email: str,
    recipient_name: str,
    date_range: str,
) -> bool:
    """
    Send the weekly pulse email via SMTP.

    Args:
        html_content:   Rendered HTML report string (already personalised).
        text_content:   Plain-text fallback string (already personalised).
        recipient_email: Recipient email address (provided by the frontend UI).
        recipient_name:  Recipient name (used in the subject line).
        date_range:      Human-readable date range for the subject line.

    Returns:
        True on success.

    Raises:
        ValueError:  If no recipient or SMTP credentials are configured.
        smtplib.SMTPException: On any SMTP-level failure.
    """
    if not recipient_email:
        raise ValueError(
            "No recipient specified. Enter a recipient "
            "email address in the UI."
        )

    sender = config.SMTP_USER
    if not sender or not config.SMTP_PASSWORD:
        raise ValueError(
            "SMTP credentials not configured. "
            "Set SMTP_USER and SMTP_PASSWORD in .env."
        )

    subject = f"IND Money Weekly Pulse -- Week of {date_range}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = (
        f"{recipient_name} <{recipient_email}>"
        if recipient_name
        else recipient_email
    )

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    logger.info(
        "Sending pulse email to %s <%s> via %s:%s …",
        recipient_name, recipient_email, config.SMTP_HOST, config.SMTP_PORT,
    )

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender, config.SMTP_PASSWORD)
        server.sendmail(sender, [recipient_email], msg.as_string())

    logger.info("Email sent successfully to %s.", recipient_name)
    return True
