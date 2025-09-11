import asyncio
import smtplib
from email.mime.text import MIMEText
from app.core.config import settings

def _send_email_sync(to_email: str, subject: str, body: str) -> None:
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.MAIL_FROM
    msg["To"] = to_email

    # Respect timeout to avoid hanging the app
    timeout = float(settings.SMTP_TIMEOUT_SECONDS)
    server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout)
    try:
        if settings.SMTP_TLS:
            server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:
            server.close()

async def send_email(to_email: str, subject: str, body: str) -> None:
    # Short-circuit in dev or placeholder host
    if (not settings.EMAIL_ENABLED) or settings.SMTP_HOST in {"smtp.example.com", "", None}:
        print(f"[DEV EMAIL] To: {to_email}\nSubject: {subject}\n\n{body}\n")
        return

    # Offload synchronous SMTP work to thread so we don't block the event loop
    try:
        await asyncio.to_thread(_send_email_sync, to_email, subject, body)
    except Exception as e:
        # In production you'd log this; for now print
        print(f"[EMAIL ERROR] {e}")
