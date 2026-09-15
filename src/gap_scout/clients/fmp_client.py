"""Thin REST wrapper around Financial Modeling Prep's /stable API.

Used ONLY for gapper discovery (biggest-gainers/losers/most-actives).
Confirmed to return real, populated data on every test during this
project -- unlike Schwab's /movers, which only reflects regular-session
activity and is empty pre-market. Schwab is used elsewhere for per-symbol
premarket quote enrichment (its /quotes endpoint carries live pre-market
prices in its "extended" field).

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

    def gainers(self) -> list[dict[str, Any]]:
        # No truncation here on purpose -- fetch_gappers.py filters in one
        # place, after merging all three lists. A `limit` param here used
        # to silently cap this at 20 regardless of what fetch_gappers.py's
        # own docstring claimed ("no limit, filter later") -- that
        # contradiction is why this method no longer slices at all.
        data = self._get("/biggest-gainers")
        return data if isinstance(data, list) else []

    def losers(self) -> list[dict[str, Any]]:
        data = self._get("/biggest-losers")
        return data if isinstance(data, list) else []

    def most_actives(self) -> list[dict[str, Any]]:
        """Highest trading-volume stocks today -- same shape as gainers/losers
        (symbol, price, name, change, changesPercentage, exchange), just
        sorted by volume instead of % move."""
        data = self._get("/most-actives")
        return data if isinstance(data, list) else []