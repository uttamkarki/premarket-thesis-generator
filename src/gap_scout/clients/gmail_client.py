"""Send email via the Gmail API using a pre-generated OAuth refresh token.

The refresh token is produced once, locally, via scripts/gmail_oauth_setup.py
and stored as a base64-encoded JSON blob in the GMAIL_TOKEN_JSON_B64 env var
(both locally in .env and as a GitHub Actions secret).
"""
from __future__ import annotations

import base64
import json
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.gap_scout.config import GMAIL_TOKEN_JSON_B64

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def _load_credentials() -> Credentials:
    if not GMAIL_TOKEN_JSON_B64:
        raise RuntimeError("GMAIL_TOKEN_JSON_B64 is not set")
    token_info = json.loads(base64.b64decode(GMAIL_TOKEN_JSON_B64))
    creds = Credentials.from_authorized_user_info(token_info, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


def send_email(to_addr: str, subject: str, html_body: str) -> str:
    if not to_addr:
        raise RuntimeError("EMAIL_TO is not set")
    creds = _load_credentials()
    service = build("gmail", "v1", credentials=creds)

    message = MIMEText(html_body, "html")
    message["to"] = to_addr
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return sent.get("id", "")
