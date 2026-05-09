# ============================================================
# backend/utils/gmail_client.py
# NeuroAgent - Gmail API Integration (OAuth2)
# ============================================================
# Handles OAuth2 token management and provides helper
# functions to read, send, and search Gmail messages.
# ============================================================

import os
import base64
import json
from email.mime.text import MIMEText
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from backend.config import GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH, GMAIL_SCOPES


# ── Token Management ──────────────────────────────────────────

def _get_credentials() -> Optional[Credentials]:
    """
    Load or refresh Gmail OAuth2 credentials.
    If no valid token exists, starts the OAuth2 flow (browser-based).
    Returns None if credentials.json is not found.
    """
    if not os.path.exists(GMAIL_CREDENTIALS_PATH):
        print("[Gmail] credentials.json not found — Gmail disabled.")
        return None

    creds = None

    # Load existing token if available
    if os.path.exists(GMAIL_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_PATH, GMAIL_SCOPES)

    # Refresh or re-authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"[Gmail] Token refresh failed: {e}")
                creds = None

        if not creds:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    GMAIL_CREDENTIALS_PATH, GMAIL_SCOPES
                )
                creds = flow.run_local_server(port=0)
            except Exception as e:
                print(f"[Gmail] OAuth2 flow failed: {e}")
                return None

        # Save refreshed token for next run
        with open(GMAIL_TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())

    return creds


def _build_service():
    """Build and return an authorised Gmail API service object."""
    creds = _get_credentials()
    if creds is None:
        return None
    return build("gmail", "v1", credentials=creds)


def is_gmail_available() -> bool:
    """Check if Gmail integration is usable."""
    return os.path.exists(GMAIL_CREDENTIALS_PATH)


# ── Read Emails ───────────────────────────────────────────────

def get_recent_emails(max_results: int = 5, query: str = "") -> list[dict]:
    """
    Fetch recent emails from Gmail inbox.
    `query` accepts Gmail search syntax (e.g. 'from:boss@example.com').
    Returns list of {id, from, subject, snippet, date}.
    """
    service = _build_service()
    if service is None:
        return [{"error": "Gmail not configured. Add credentials.json."}]

    try:
        # List message IDs
        q = query if query else "in:inbox"
        response = service.users().messages().list(
            userId="me", q=q, maxResults=max_results
        ).execute()

        messages = response.get("messages", [])
        results = []

        for msg_ref in messages:
            msg = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()

            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            results.append({
                "id": msg_ref["id"],
                "from": headers.get("From", "Unknown"),
                "subject": headers.get("Subject", "(No Subject)"),
                "snippet": msg.get("snippet", ""),
                "date": headers.get("Date", ""),
            })

        return results

    except HttpError as e:
        return [{"error": str(e)}]


def get_email_body(message_id: str) -> str:
    """Fetch and decode the full body of a specific email."""
    service = _build_service()
    if service is None:
        return "Gmail not configured."

    try:
        msg = service.users().messages().get(
            userId="me", id=message_id, format="full"
        ).execute()

        # Recursively extract text parts
        def extract_parts(payload):
            if payload.get("mimeType") == "text/plain":
                data = payload.get("body", {}).get("data", "")
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            for part in payload.get("parts", []):
                result = extract_parts(part)
                if result:
                    return result
            return ""

        return extract_parts(msg["payload"]) or "Could not extract body."

    except HttpError as e:
        return f"Error reading email: {e}"


# ── Send Email ────────────────────────────────────────────────

def send_email(to: str, subject: str, body: str) -> dict:
    """
    Send an email from the authenticated Gmail account.
    Returns {'success': True} or {'error': '...'}.
    """
    service = _build_service()
    if service is None:
        return {"error": "Gmail not configured. Add credentials.json."}

    try:
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject

        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()
        send_response = service.users().messages().send(
            userId="me", body={"raw": encoded}
        ).execute()

        return {"success": True, "message_id": send_response.get("id")}

    except HttpError as e:
        return {"error": str(e)}


# ── Search Emails ─────────────────────────────────────────────

def search_emails(query: str, max_results: int = 5) -> list[dict]:
    """Alias for get_recent_emails with a search query."""
    return get_recent_emails(max_results=max_results, query=query)
