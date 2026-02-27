"""
Transactional email service.

Supports three backends:
  log   — just logs the email (default / dev mode)
  ses   — AWS SES via boto3
  smtp  — generic SMTP (SendGrid, Mailgun, etc.)

Set EMAIL_PROVIDER in your environment to activate a real backend.
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)


def _build_message(to: str, subject: str, body_html: str, body_text: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))
    return msg


def _send_ses(to: str, subject: str, body_html: str, body_text: str) -> None:
    import boto3
    region = settings.SES_REGION or settings.AWS_REGION
    client = boto3.client("ses", region_name=region)
    client.send_email(
        Source=settings.EMAIL_FROM,
        Destination={"ToAddresses": [to]},
        Message={
            "Subject": {"Data": subject},
            "Body": {
                "Text": {"Data": body_text},
                "Html": {"Data": body_html},
            },
        },
    )


def _send_smtp(to: str, subject: str, body_html: str, body_text: str) -> None:
    msg = _build_message(to, subject, body_html, body_text)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.EMAIL_FROM, [to], msg.as_string())


def send_email(to: str, subject: str, body_html: str, body_text: str = "") -> None:
    """Send a transactional email via the configured provider."""
    if not body_text:
        # Naive strip for plain-text fallback
        import re
        body_text = re.sub(r"<[^>]+>", "", body_html)

    provider = settings.EMAIL_PROVIDER.lower()

    if provider == "ses":
        try:
            _send_ses(to, subject, body_html, body_text)
            logger.info("[email] SES → %s | %s", to, subject)
        except Exception as exc:
            logger.error("[email] SES failed: %s", exc)
    elif provider == "smtp":
        try:
            _send_smtp(to, subject, body_html, body_text)
            logger.info("[email] SMTP → %s | %s", to, subject)
        except Exception as exc:
            logger.error("[email] SMTP failed: %s", exc)
    else:
        # log mode — always works, useful in dev
        logger.info("[email:log] TO=%s | SUBJECT=%s\n%s", to, subject, body_text)


# ── Job notification helpers ───────────────────────────────────────────────

_COMPLETED_HTML = """
<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px">
  <h2 style="color:#15803d">✅ Analysis Complete</h2>
  <p>Your pipeline job <strong>{job_id}</strong> has finished successfully.</p>
  <table style="border-collapse:collapse;width:100%;margin:16px 0">
    <tr><td style="padding:6px 0;color:#6b7280">Pipeline</td><td style="padding:6px 0;font-weight:600">{pipeline}</td></tr>
    <tr><td style="padding:6px 0;color:#6b7280">Job name</td><td style="padding:6px 0">{job_name}</td></tr>
    <tr><td style="padding:6px 0;color:#6b7280">Runtime</td><td style="padding:6px 0">{runtime}</td></tr>
  </table>
  <a href="{app_url}" style="display:inline-block;padding:10px 22px;background:#2563eb;color:#fff;border-radius:7px;text-decoration:none;font-weight:600">View Results →</a>
  <p style="color:#9ca3af;font-size:12px;margin-top:24px">This email was sent by BioAnalysis Platform. Results may be available for a limited time.</p>
</div>
"""

_FAILED_HTML = """
<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px">
  <h2 style="color:#b91c1c">❌ Analysis Failed</h2>
  <p>Your pipeline job <strong>{job_id}</strong> encountered an error.</p>
  <table style="border-collapse:collapse;width:100%;margin:16px 0">
    <tr><td style="padding:6px 0;color:#6b7280">Pipeline</td><td style="padding:6px 0;font-weight:600">{pipeline}</td></tr>
    <tr><td style="padding:6px 0;color:#6b7280">Job name</td><td style="padding:6px 0">{job_name}</td></tr>
    <tr><td style="padding:6px 0;color:#6b7280">Error</td><td style="padding:6px 0;color:#dc2626;font-family:monospace;font-size:12px">{error}</td></tr>
  </table>
  <a href="{app_url}" style="display:inline-block;padding:10px 22px;background:#2563eb;color:#fff;border-radius:7px;text-decoration:none;font-weight:600">View History →</a>
  <p style="color:#9ca3af;font-size:12px;margin-top:24px">You can retry the job from the History tab. If the error persists, please contact support.</p>
</div>
"""


def send_job_notification(
    to: str,
    job_id: str,
    status: str,
    pipeline: str = "Unknown",
    job_name: str = "",
    runtime: str = "",
    error: str = "",
) -> None:
    """Send a job completion or failure email."""
    display_name = job_name or job_id[:8]
    app_url = settings.APP_BASE_URL

    if status == "completed":
        subject = f"Analysis complete — {display_name}"
        body_html = _COMPLETED_HTML.format(
            job_id=job_id,
            pipeline=pipeline,
            job_name=display_name,
            runtime=runtime or "N/A",
            app_url=app_url,
        )
    else:
        subject = f"Analysis failed — {display_name}"
        body_html = _FAILED_HTML.format(
            job_id=job_id,
            pipeline=pipeline,
            job_name=display_name,
            error=error[:300] if error else "Unknown error",
            app_url=app_url,
        )

    send_email(to, subject, body_html)
