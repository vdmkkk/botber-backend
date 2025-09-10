import smtplib
from email.mime.text import MIMEText
from app.core.config import settings

async def send_email(to_email: str, subject: str, body: str) -> None:
    # Simple SMTP sender; for dev, you can print instead
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = settings.MAIL_FROM
        msg["To"] = to_email

        if settings.SMTP_TLS:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)

        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        # Dev fallback
        print(f"[DEV EMAIL] To: {to_email}\nSubject: {subject}\n\n{body}\n(Err: {e})")
