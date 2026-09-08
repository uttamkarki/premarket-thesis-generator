"""Thin wrapper around Charles Schwab's Market Data API.

Auth notes (important, unlike Gmail's OAuth):
    - Access tokens last 30 minutes; refreshed automatically here.
    - Refresh tokens have a HARD 7-day expiration with no way to extend --
      you must re-run scripts/schwab_oauth_setup.py roughly weekly.
    - If the refresh token itself has expired, refreshing the access token
      will fail with a 400 invalid_grant error; the fix is re-running the
      OAuth setup script, not a code change.

Movers endpoint: GET /movers/{symbol_id}, symbol_id is an INDEX (e.g.
$SPX, $COMPX, $DJI, $NDX, $RUT), not "the whole market" -- gainers/losers
are scoped to that index's constituents. `sort` is "PERCENT_CHANGE_UP" or
"PERCENT_CHANGE_DOWN"; exact valid values and response field names are
NOT yet verified against a live account -- see NewsClient-shaped caution:
run scripts/schwab_oauth_setup.py, then curl the movers endpoint directly
and share the real response before trusting this parsing.

Docs: https://developer.schwab.com/products/trader-api--individual
"""
from __future__ import annotations

import base64
import time
from typing import Any

import requests

from src.gap_scout.config import (
    SCHWAB_APP_KEY,
    SCHWAB_APP_SECRET,
    SCHWAB_REDIRECT_URI,
    SCHWAB_TOKEN_JSON_B64,
)

TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
MARKET_DATA_BASE_URL = "https://api.schwabapi.com/marketdata/v1"


class SchwabClient:
    def __init__(self) -> None:
        if not (SCHWAB_APP_KEY and SCHWAB_APP_SECRET and SCHWAB_TOKEN_JSON_B64):
            raise RuntimeError(
                "SCHWAB_APP_KEY, SCHWAB_APP_SECRET, and SCHWAB_TOKEN_JSON_B64 "
                "must all be set -- run scripts/schwab_oauth_setup.py first."
            )
        import base64 as _b64
        import json as _json

        self._tokens = _json.loads(_b64.b64decode(SCHWAB_TOKEN_JSON_B64))
        self._access_token: str = self._tokens["access_token"]
        self._refresh_token: str = self._tokens["refresh_token"]
        # We don't persist obtained_at across runs, so conservatively assume
        # the access token might already be stale and refresh proactively.
        self._access_token_fetched_at: float = 0.0
        self.session = requests.Session()

    def _refresh_access_token(self) -> None:
        basic_auth = base64.b64encode(f"{SCHWAB_APP_KEY}:{SCHWAB_APP_SECRET}".encode()).decode()
        resp = requests.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {basic_auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "refresh_token", "refresh_token": self._refresh_token},
            timeout=20,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Schwab access-token refresh failed ({resp.status_code}): {resp.text}\n"
                "If this says invalid_grant, your 7-day refresh token has expired -- "
                "re-run scripts/schwab_oauth_setup.py."
            )
        data = resp.json()
        self._access_token = data["access_token"]
        self._access_token_fetched_at = time.time()

    def _ensure_fresh_token(self) -> None:
        # Refresh proactively: at process start, or after ~25 minutes.
        if self._access_token_fetched_at == 0.0 or (
            time.time() - self._access_token_fetched_at > 25 * 60
        ):
            self._refresh_access_token()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self._ensure_fresh_token()
        resp = self.session.get(
            f"{MARKET_DATA_BASE_URL}{path}",
            headers={"Authorization": f"Bearer {self._access_token}"},
            params=params or {},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()

    def movers(self, index_symbol: str, sort: str = "PERCENT_CHANGE_UP") -> list[dict[str, Any]]:
        """`index_symbol` e.g. "$COMPX" or "$SPX". `sort` per Schwab docs is one of
        VOLUME, TRADES, PERCENT_CHANGE_UP, PERCENT_CHANGE_DOWN.
        NOT YET VERIFIED against a live response -- test with curl first.
        """
        data = self._get(f"/movers/{index_symbol}", params={"sort": sort, "frequency": 0})
        # Field name for the list itself is unconfirmed -- adjust once we see
        # a real response (commonly "screeners" in this API family).
        return data.get("screeners", []) if isinstance(data, dict) else []
