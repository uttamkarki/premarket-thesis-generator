"""Thin REST wrapper around Financial Modeling Prep's free-tier /stable API.

Verified directly against a live free-tier key (Sept 2026):
- /biggest-gainers, /biggest-losers -> free, fields: symbol, price, name,
  change, changesPercentage (note the "s"), exchange. No volume field.
- /quote?symbol=X -> free, fields include previousClose, volume, changePercentage
  (no "s" here -- FMP is inconsistent between endpoints).
- /historical-price-eod/full?symbol=X -> free, newest-first list of
  {date, open, high, low, close, volume, change, changePercent, vwap}.
- /news/stock?symbols=X -> CONFIRMED RESTRICTED on free tier (402-style
  "Restricted Endpoint" message). Do not use -- see clients/news_client.py
  for the free replacement (Google News RSS).

Docs: https://site.financialmodelingprep.com/developer/docs
"""
from __future__ import annotations

from typing import Any

import requests

from src.gap_scout.config import FMP_API_KEY, FMP_BASE_URL


class FMPClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or FMP_API_KEY
        if not self.api_key:
            raise RuntimeError("FMP_API_KEY is not set")
        self.base_url = (base_url or FMP_BASE_URL).rstrip("/")
        self.session = requests.Session()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        query = dict(params or {})
        query["apikey"] = self.api_key
        resp = self.session.get(f"{self.base_url}{path}", params=query, timeout=20)
        resp.raise_for_status()
        return resp.json()

    # ---- movers (used by fetch_gappers) ----
    def gainers(self, limit: int = 5) -> list[dict[str, Any]]:
        data = self._get("/biggest-gainers")
        return data[:limit] if isinstance(data, list) else []

    def losers(self, limit: int = 5) -> list[dict[str, Any]]:
        data = self._get("/biggest-losers")
        return data[:limit] if isinstance(data, list) else []

    # ---- single-ticker quote: previousClose, volume, etc (used by fetch_gappers) ----
    def quote(self, ticker: str) -> dict[str, Any] | None:
        data = self._get("/quote", params={"symbol": ticker})
        if isinstance(data, list) and data:
            return data[0]
        return None

    # ---- daily OHLCV history (used by check_gap_room + market_regime) ----
    def historical_daily(self, ticker: str, days: int = 20) -> list[dict[str, Any]]:
        """Returns up to `days` most-recent daily bars, oldest first."""
        data = self._get("/historical-price-eod/full", params={"symbol": ticker})
        bars = data if isinstance(data, list) else []
        bars = bars[:days]  # API returns newest-first; take the most recent `days`
        return list(reversed(bars))  # flip to chronological ascending