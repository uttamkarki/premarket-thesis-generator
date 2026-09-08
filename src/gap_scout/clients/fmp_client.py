"""Thin REST wrapper around Financial Modeling Prep's free-tier /stable API.

Used ONLY for gapper discovery (biggest-gainers/losers). Confirmed to
return real, populated data on every test during this project -- unlike
Schwab's /movers, which only reflects regular-session activity and is
empty pre-market. Schwab is still used elsewhere (kept for future
per-symbol premarket quote enrichment, since /quotes DOES carry live
pre-market prices in its "extended" field).

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

    def gainers(self, limit: int = 20) -> list[dict[str, Any]]:
        data = self._get("/biggest-gainers")
        return data[:limit] if isinstance(data, list) else []

    def losers(self, limit: int = 20) -> list[dict[str, Any]]:
        data = self._get("/biggest-losers")
        return data[:limit] if isinstance(data, list) else []
