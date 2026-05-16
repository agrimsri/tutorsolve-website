import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import sendgrid
from sendgrid.helpers.mail import Email, Mail, To
from flask import current_app

from app import celery


# ── Provider implementations ──────────────────────────────────────────────────

def _send_via_sendgrid(to_email, to_name, subject, html_content, text_content):
    """Send email using the SendGrid API."""
    cfg = current_app.config

    sg = sendgrid.SendGridAPIClient(cfg["SENDGRID_API_KEY"])
    message = Mail(
        from_email=Email(
            cfg.get("SENDGRID_FROM_EMAIL", "support@tutorsolve.com"),
            cfg.get("SENDGRID_FROM_NAME", "TutorSolve"),
        ),
        to_emails=To(to_email, to_name),
        subject=subject,
        html_content=html_content,
        plain_text_content=text_content or (html_content[:100] if html_content else ""),
    )
    response = sg.send(message)
    logging.info(f"[email] SendGrid → {to_email} | status {response.status_code}")


def _send_via_smtp(to_email, to_name, subject, html_content, text_content):
    """Send email using Google SMTP (or any SMTP server)."""
    cfg = current_app.config

    mail_server   = cfg.get("MAIL_SERVER", "smtp.gmail.com")
    mail_port     = cfg.get("MAIL_PORT", 587)
    mail_username = cfg.get("MAIL_USERNAME", "")
    mail_password = cfg.get("MAIL_PASSWORD", "")
    from_email    = cfg.get("SENDGRID_FROM_EMAIL", "support@tutorsolve.com")
    from_name     = cfg.get("SENDGRID_FROM_NAME", "TutorSolve")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{from_name} <{from_email}>"
    msg["To"]      = f"{to_name} <{to_email}>"

    plain_text = text_content or (html_content[:100] if html_content else "")
    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    with smtplib.SMTP(mail_server, mail_port) as server:
        server.starttls()
        if mail_username and mail_password:
            server.login(mail_username, mail_password)
        server.send_message(msg, from_addr=from_email, to_addrs=[to_email])

    logging.info(f"[email] SMTP → {to_email}")


# ── Celery task ───────────────────────────────────────────────────────────────

@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_task(self, to_email, to_name, subject, html_content, text_content=None):
    """
    Generic email send task. All email sending routes through here.

    The active provider is chosen by EMAIL_PROVIDER in .env:
        EMAIL_PROVIDER=sendgrid   → uses SendGrid API
        EMAIL_PROVIDER=smtp       → uses SMTP (default, currently Gmail)

    Retries up to 3 times on failure with a 60-second delay.
    """
    provider = current_app.config.get("EMAIL_PROVIDER", "smtp")

    try:
        if provider == "sendgrid":
            _send_via_sendgrid(to_email, to_name, subject, html_content, text_content)
        else:
            _send_via_smtp(to_email, to_name, subject, html_content, text_content)

    except Exception as exc:
        logging.error(f"[email] Send failed via {provider} to {to_email}: {exc}")
        raise self.retry(exc=exc)
