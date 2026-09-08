"""Centralized environment/config loading for gap-scout."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

GMAIL_TOKEN_JSON_B64 = os.environ.get("GMAIL_TOKEN_JSON_B64", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "")

NUM_GAPPERS_PER_DIRECTION = int(os.environ.get("NUM_GAPPERS_PER_DIRECTION", "5"))

# Quality filters for fetch_gappers -- keeps the scan to real, tradeable
# gappers instead of every sub-$1 SPAC unit/warrant/rights ticker.
MIN_PRICE = float(os.environ.get("MIN_PRICE", "5"))
MIN_VOLUME = int(os.environ.get("MIN_VOLUME", "500000"))
ALLOWED_EXCHANGES = {
    e.strip().upper()
    for e in os.environ.get("ALLOWED_EXCHANGES", "NASDAQ,NYSE,AMEX").split(",")
    if e.strip()
}

# ---- Charles Schwab (market data: movers, quotes, price history) ----
# OAuth refresh token expires every 7 days -- rerun scripts/schwab_oauth_setup.py
# weekly. See clients/schwab_client.py for details.
SCHWAB_APP_KEY = os.environ.get("SCHWAB_APP_KEY", "")
SCHWAB_APP_SECRET = os.environ.get("SCHWAB_APP_SECRET", "")
SCHWAB_REDIRECT_URI = os.environ.get("SCHWAB_REDIRECT_URI", "")
SCHWAB_TOKEN_JSON_B64 = os.environ.get("SCHWAB_TOKEN_JSON_B64", "")

# Which indices to scan for movers, combined.
SCHWAB_MOVER_INDICES = [
    s.strip() for s in os.environ.get("SCHWAB_MOVER_INDICES", "$COMPX,$SPX").split(",") if s.strip()
]