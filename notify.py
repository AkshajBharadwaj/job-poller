"""Barebones text + email senders. Reads credentials from .env at project root.

SMS goes through Twilio's REST API directly (curl_cffi call, no Twilio
SDK dependency) when SMS_ALERTS_ENABLED is true. Email uses SMTP or the
Gmail HTTPS API with an offline OAuth grant.
"""

import base64
import os
import smtplib
from email.utils import getaddresses
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

from . import http

load_dotenv(Path(__file__).resolve().parent / ".env")

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "")
TWILIO_TO_NUMBER = os.environ.get("TWILIO_TO_NUMBER", "")
SMS_ALERTS_ENABLED = os.environ.get("SMS_ALERTS_ENABLED", "").strip().lower() in ("1", "true", "yes")

OPT_IN_SENT_MARKER = Path(__file__).resolve().parent / ".sms_opt_in_sent"
OPT_IN_MESSAGE = (
    "Career Watch: You opted in to job alert texts by enabling SMS alerts "
    "in the app settings. Msg frequency varies. Msg & data rates may apply. "
    "Reply STOP to unsubscribe, HELP for help."
)

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "")
EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", "smtp").strip().lower()
GMAIL_CLIENT_ID = os.environ.get("GMAIL_CLIENT_ID", "")
GMAIL_CLIENT_SECRET = os.environ.get("GMAIL_CLIENT_SECRET", "")
GMAIL_REFRESH_TOKEN = os.environ.get("GMAIL_REFRESH_TOKEN", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", SMTP_USER)


def send_text(body: str) -> None:
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER and TWILIO_TO_NUMBER):
        raise RuntimeError("Twilio env vars not set (see .env.example)")

    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    # Twilio POSTs create messages, so retrying after an ambiguous failure
    # could deliver a duplicate alert.
    with http.session(retries=0) as session:
        resp = session.post(
            url,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            data={"From": TWILIO_FROM_NUMBER, "To": TWILIO_TO_NUMBER, "Body": body},
        )
        resp.raise_for_status()


def send_email(subject: str, body: str) -> None:
    if EMAIL_PROVIDER == "gmail_api":
        return _send_gmail_api(subject, body)
    if EMAIL_PROVIDER != "smtp":
        raise RuntimeError("EMAIL_PROVIDER must be smtp or gmail_api")
    if not (SMTP_USER and SMTP_PASSWORD and EMAIL_TO):
        raise RuntimeError("SMTP env vars not set (see .env.example)")

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO
    recipients = [address for _, address in getaddresses([EMAIL_TO])]

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg, to_addrs=recipients)


def _send_gmail_api(subject: str, body: str) -> None:
    """Send over HTTPS using an offline OAuth grant with gmail.send scope."""
    if not all((GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN,
                EMAIL_FROM, EMAIL_TO)):
        raise RuntimeError("Gmail API env vars not set (see .env.example)")
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    # A send may succeed before the connection fails: never retry it blindly.
    with http.session(retries=0) as session:
        response = session.post("https://oauth2.googleapis.com/token", data={
            "client_id": GMAIL_CLIENT_ID,
            "client_secret": GMAIL_CLIENT_SECRET,
            "refresh_token": GMAIL_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        })
        response.raise_for_status()
        token = response.json()["access_token"]
        response = session.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {token}"},
            json={"raw": raw},
        )
        response.raise_for_status()


def ensure_opted_in() -> None:
    """Send the one-time SMS opt-in confirmation the first time alerts are enabled."""
    if not SMS_ALERTS_ENABLED or OPT_IN_SENT_MARKER.exists():
        return
    send_text(OPT_IN_MESSAGE)
    OPT_IN_SENT_MARKER.write_text("sent\n")


def notify_new_job(company: str, job: dict) -> None:
    subject = f"New {company} posting: {job['title']}"
    body = f"{job['title']}\n{', '.join(job['locations'])}\n{job.get('url', '')}"
    if SMS_ALERTS_ENABLED:
        send_text(f"{subject}\n{', '.join(job['locations'])}")
    send_email(subject, body)
