"""
Gmail provider using the Gmail API and OAuth 2.0.

No password is ever stored. Authentication uses:
    * `credentials.json`  — OAuth client secret, downloaded from Google
                             Cloud Console (Desktop app credentials).
    * `token.json`        — cached user access/refresh token, created on
                             first run after the user authorizes in a
                             browser. Refreshed automatically afterwards.

Both files are expected to live outside version control (see
.gitignore) and their paths are configurable via settings.
"""

from __future__ import annotations

import base64
import mimetypes
import os
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from providers.base import EmailProvider

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


class GmailProvider(EmailProvider):
    def __init__(self, credentials_path: str, token_path: str):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self._service = None  # lazily built on first send

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------
    def _get_service(self):
        if self._service is not None:
            return self._service

        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:  # pragma: no cover - import guard
            raise RuntimeError(
                "Gmail dependencies are not installed. Run: "
                "pip install -r requirements.txt"
            ) from exc

        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Gmail OAuth client secret not found at: {self.credentials_path}. "
                        "Download it from Google Cloud Console (OAuth client, Desktop app "
                        "type) and place it there, or set GMAIL_CREDENTIALS_PATH."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)

            Path(self.token_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, "w", encoding="utf-8") as token_file:
                token_file.write(creds.to_json())

        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    def _build_message(
        self,
        recipient: str,
        subject: str,
        body: str,
        attachment: Optional[str],
    ) -> dict:
        message = MIMEMultipart()
        message["to"] = recipient
        message["subject"] = subject
        message.attach(MIMEText(body, "plain"))

        if attachment:
            attach_path = Path(attachment)
            if not attach_path.exists():
                raise FileNotFoundError(f"Attachment not found: {attachment}")
            mime_type, _ = mimetypes.guess_type(str(attach_path))
            mime_type = mime_type or "application/octet-stream"
            main_type, sub_type = mime_type.split("/", 1)
            with open(attach_path, "rb") as f:
                part = MIMEApplication(f.read(), _subtype=sub_type)
            part.add_header(
                "Content-Disposition", "attachment", filename=attach_path.name
            )
            message.attach(part)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        return {"raw": raw}

    def send_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        attachment: Optional[str] = None,
    ) -> None:
        service = self._get_service()
        message = self._build_message(recipient, subject, body, attachment)
        service.users().messages().send(userId="me", body=message).execute()
