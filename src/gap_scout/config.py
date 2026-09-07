"""Centralized environment/config loading for gap-scout."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

MASSIVE_API_KEY = os.environ.get("MASSIVE_API_KEY", "")
MASSIVE_BASE_URL = os.environ.get("MASSIVE_BASE_URL", "https://api.massive.com")

FMP_API_KEY = os.environ.get("FMP_API_KEY", "")
FMP_BASE_URL = os.environ.get("FMP_BASE_URL", "https://financialmodelingprep.com/stable")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

GMAIL_TOKEN_JSON_B64 = os.environ.get("GMAIL_TOKEN_JSON_B64", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "")

NUM_GAPPERS_PER_DIRECTION = int(os.environ.get("NUM_GAPPERS_PER_DIRECTION", "5"))

# Quality filters for fetch_gappers -- keeps the scan to real, tradeable
# gappers instead of every sub-$1 SPAC unit/warrant/rights ticker FMP's
# raw movers list includes.
MIN_PRICE = float(os.environ.get("MIN_PRICE", "5"))
MIN_VOLUME = int(os.environ.get("MIN_VOLUME", "500000"))
ALLOWED_EXCHANGES = {
    e.strip().upper()
    for e in os.environ.get("ALLOWED_EXCHANGES", "NASDAQ,NYSE,AMEX").split(",")
    if e.strip()
}