"""Sends password-reset emails. Falls back to a documented demo mode without SMTP."""
import os, smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from flask import current_app

def send_reset_email(to_addr, link, minutes):
    body = (f"Someone requested a password reset for your account.\n\n"
            f"Reset link (valid for {minutes} minutes, single use):\n{link}\n\n"
            f"If this wasn't you, ignore this email.")
    host = os.getenv("SMTP_HOST")
    if host:
        msg = EmailMessage()
        msg["Subject"], msg["To"] = "Password reset", to_addr
        msg["From"] = os.getenv("MAIL_FROM") or os.getenv("SMTP_USER", "")
        msg.set_content(body)
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", 587)), timeout=15) as s:
            s.starttls()
            if os.getenv("SMTP_USER"):
                s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD", ""))
            s.send_message(msg)
    else:  # DEMO MODE: no email leaves the machine
        print(f"\n[DEMO MAIL] To: {to_addr}\n{body}\n", flush=True)
        log = Path(current_app.instance_path) / "outbox.log"
        with log.open("a", encoding="utf-8") as f:
            f.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S} To: {to_addr}\n{body}\n")
