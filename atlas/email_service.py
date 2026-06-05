from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Protocol

logger = logging.getLogger(__name__)


SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "noreply@futureinfrastructure.com")
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "FUTURE Infrastructure Atlas")
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")


def _is_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASS)


def _build_api_key_email(
    to_email: str,
    display_name: str,
    api_key: str,
    plan_name: str,
) -> MIMEMultipart:
    subject = "Your FUTURE Infrastructure Atlas API key is ready"
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0f;color:#e0e0e0;padding:32px">
<div style="max-width:520px;margin:0 auto;background:#111;border:1px solid #222;border-radius:8px;padding:32px">
<div style="text-align:center;margin-bottom:24px">
<h1 style="font-size:14px;letter-spacing:2px;text-transform:uppercase;color:#d69a13;margin:0">FUTURE Infrastructure Atlas</h1>
</div>
<p style="font-size:14px;line-height:1.6;margin:0 0 16px">Hi {display_name},</p>
<p style="font-size:14px;line-height:1.6;margin:0 0 16px">Your <strong>{plan_name}</strong> plan is now active. Use the API key below to authenticate your requests.</p>
<div style="background:#0d1117;border:1px solid #333;border-radius:6px;padding:16px;margin:16px 0;word-break:break-all;font-family:'SF Mono','Fira Code',monospace;font-size:13px;color:#d69a13;text-align:center">{api_key}</div>
<p style="font-size:13px;line-height:1.5;margin:0 0 16px;color:#808088">Include this key in the <code style="background:#0d1117;padding:1px 6px;border-radius:3px;font-size:12px;color:#d69a13">X-API-Key</code> header of your API requests. You can also manage usage from the Enterprise Dashboard.</p>
<div style="border-top:1px solid #222;padding-top:16px;margin-top:16px;font-size:11px;color:#5a5a62;text-align:center">
If you did not create this account, ignore this email.<br>
&copy; 2026 FUTURE Infrastructure Intelligence
</div>
</div>
</body>
</html>"""
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(f"Your API key is: {api_key}\n\nInclude it in the X-API-Key header.", "plain"))
    msg.attach(MIMEText(html, "html"))
    return msg


def send_api_key_email(to_email: str, display_name: str, api_key: str, plan_name: str) -> bool:
    if not _is_configured():
        logger.warning("SMTP not configured; skipping email to %s", to_email)
        return False
    try:
        msg = _build_api_key_email(to_email, display_name, api_key, plan_name)
        ctx = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            if SMTP_USE_TLS:
                server.starttls(context=ctx)
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, [to_email], msg.as_string())
        logger.info("API key email sent to %s", to_email)
        return True
    except Exception:
        logger.exception("Failed to send API key email to %s", to_email)
        return False


class EmailSender(Protocol):
    def send_api_key_email(self, to_email: str, display_name: str, api_key: str, plan_name: str) -> bool: ...
