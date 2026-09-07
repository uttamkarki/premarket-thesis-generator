"""One-time LOCAL script to generate a Gmail OAuth refresh token for gap-scout.

Steps:
    1. In Google Cloud Console: create/select a project, enable the Gmail API,
       then create an OAuth Client ID of type "Desktop app".
    2. Download the client secret JSON and save it as
       scripts/client_secret.json (this filename is git-ignored — never commit it).
    3. Run:  python scripts/gmail_oauth_setup.py
    4. A browser window opens — sign in with the Gmail account gap-scout should
       send from, and grant the "send email on your behalf" permission.
    5. Copy the printed base64 string into:
         - your local .env, as GMAIL_TOKEN_JSON_B64=...
         - your GitHub repo's Actions secrets, as GMAIL_TOKEN_JSON_B64
"""
from __future__ import annotations

import base64
import pathlib

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
CLIENT_SECRET_FILE = pathlib.Path(__file__).parent / "client_secret.json"


def main() -> None:
    if not CLIENT_SECRET_FILE.exists():
        raise SystemExit(
            f"Missing {CLIENT_SECRET_FILE}.\n"
            "Download an OAuth Client ID (Desktop app type) JSON from Google Cloud "
            "Console and save it at that path, then re-run this script."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
    creds = flow.run_local_server(port=0)

    token_b64 = base64.b64encode(creds.to_json().encode()).decode()
    print("\nSuccess. Add this value as GMAIL_TOKEN_JSON_B64:\n")
    print(token_b64)
    print(
        "\n- Locally: paste into .env as GMAIL_TOKEN_JSON_B64=<value above>\n"
        "- CI: add as a GitHub Actions repo secret named GMAIL_TOKEN_JSON_B64\n"
    )


if __name__ == "__main__":
    main()
