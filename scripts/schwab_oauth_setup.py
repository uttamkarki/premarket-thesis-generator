"""One-time LOCAL script to generate a Schwab OAuth refresh token.

Schwab uses 3-legged OAuth, and (unlike Google) the refresh token it issues
has a HARD 7-day expiration -- there is no way to get a permanent token.
You will need to re-run this script roughly once a week to keep the
scheduled pipeline working.

Prereqs (one-time, in the Schwab Developer Portal at developer.schwab.com):
    1. Create an app under the "Market Data Production" product (movers,
       quotes, price history -- no trading needed for this project).
    2. Set a Callback URL, e.g. https://127.0.0.1:8182 (must be HTTPS,
       Schwab accepts localhost with https for this).
    3. Wait for the app status to become "Ready For Use" (can take a
       few days for Schwab's approval).
    4. Copy the App Key (Client ID) and Secret from the app's page.

Usage:
    Put SCHWAB_APP_KEY, SCHWAB_APP_SECRET, and SCHWAB_REDIRECT_URI in your
    .env file (same as every other credential in this project), then:
        python scripts/schwab_oauth_setup.py
    This script loads .env itself -- no need to `export` anything by hand.

Steps this script walks you through:
    1. Prints an authorization URL -- open it in a browser, log in with your
       Schwab brokerage credentials, and approve access.
    2. Schwab redirects you to your Callback URL with a `code=` parameter
       in the address bar. The page itself will likely show an error (since
       nothing is actually listening on that URL) -- that's expected. Copy
       the FULL resulting URL from the browser's address bar.
    3. Paste that full URL back into this script when prompted.
    4. The script exchanges the code for tokens and prints a base64 blob to
       store as SCHWAB_TOKEN_JSON_B64.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import load_dotenv

load_dotenv()  # reads .env in the project root, same as config.py does

AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"
TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"


def main() -> None:
    app_key = os.environ.get("SCHWAB_APP_KEY")
    app_secret = os.environ.get("SCHWAB_APP_SECRET")
    redirect_uri = os.environ.get("SCHWAB_REDIRECT_URI")

    if not app_key or not app_secret or not redirect_uri:
        raise SystemExit(
            "Missing SCHWAB_APP_KEY, SCHWAB_APP_SECRET, or SCHWAB_REDIRECT_URI "
            "in your .env file. Add all three, then re-run this script."
        )

    auth_url = f"{AUTH_URL}?client_id={app_key}&redirect_uri={redirect_uri}"
    print("\n1. Open this URL in a browser and log in / approve access:\n")
    print(f"   {auth_url}\n")
    print("2. After approving, your browser will redirect to your Callback URL")
    print("   with a 'code=' parameter in the address bar (the page itself may")
    print("   show a connection error -- that's fine, we just need the URL).\n")

    redirected_url = input("3. Paste the FULL redirected URL here: ").strip()

    parsed = urlparse(redirected_url)
    query = parse_qs(parsed.query)
    code = query.get("code", [None])[0]
    if not code:
        raise SystemExit("Could not find a 'code=' parameter in that URL. Try again.")

    basic_auth = base64.b64encode(f"{app_key}:{app_secret}".encode()).decode()
    resp = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {basic_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
        timeout=20,
    )

    if resp.status_code != 200:
        print(f"\nToken exchange failed ({resp.status_code}):\n{resp.text}")
        sys.exit(1)

    tokens = resp.json()  # {access_token, refresh_token, expires_in, token_type, scope}
    token_b64 = base64.b64encode(json.dumps(tokens).encode()).decode()

    print("\nSuccess. Add this value as SCHWAB_TOKEN_JSON_B64:\n")
    print(token_b64)
    print(
        "\nAlso keep SCHWAB_APP_KEY, SCHWAB_APP_SECRET, and SCHWAB_REDIRECT_URI "
        "set in .env / GitHub secrets -- the client needs them to refresh the "
        "access token automatically.\n"
        "\nReminder: the refresh token in this blob expires in 7 days. You'll "
        "need to re-run this script weekly to keep the scheduled pipeline alive.\n"
    )


if __name__ == "__main__":
    main()