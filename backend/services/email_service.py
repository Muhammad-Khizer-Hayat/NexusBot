import os, smtplib
from email.mime.text import MIMEText

SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

def send_otp_email(to_email: str, otp: str) -> bool:
    if not SMTP_USER or not SMTP_PASSWORD:
        print("[Email] SMTP not configured — cannot send OTP")
        return False

    body = f"""Your NexusBot verification code is: {otp}

This code expires in 10 minutes. If you didn't request this, ignore this email."""

    msg = MIMEText(body)
    msg["Subject"] = "Your NexusBot verification code"
    msg["From"]    = SMTP_USER
    msg["To"]      = to_email

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [to_email], msg.as_string())
        print(f"[Email] OTP sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send OTP: {e}")
        return False