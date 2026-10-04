"""SMTP delivery adapter with explicit manual-delivery fallback."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import settings


def send_transactional_email(recipient: str, subject: str, body: str) -> str:
    """Send through configured SMTP, otherwise signal a real manual workflow."""
    if not settings.smtp_configured:
        return "manual"
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as client:
        if settings.SMTP_USE_TLS:
            client.starttls()
        if settings.SMTP_USERNAME:
            client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        client.send_message(message)
    return "email"
