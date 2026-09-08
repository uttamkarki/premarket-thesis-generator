"""Node 1: pull today's top gap-up and gap-down tickers.

Discovery uses FMP's /biggest-gainers and /biggest-losers -- confirmed to
return real, populated data reliably (unlike Schwab's /movers, which only
reflects regular-session activity and returns empty results pre-market;
see clients/schwab_client.py for that finding). prior_close is derived
algebraically from price + %change, so no extra per-ticker API call is
needed. Schwab remains available in this project for future per-symbol
premarket quote enrichment (its /quotes endpoint DOES carry a live
pre-market price in its "extended" field), just not for discovery.

Applies quality filters (min price, allowed exchanges, SPAC unit/warrant/
rights ticker-suffix pattern) so the scan reflects real, tradeable gappers.
"""
from __future__ import annotations

import re
from datetime import datetime

from src.gap_scout.clients.fmp_client import FMPClient
from src.gap_scout.config import ALLOWED_EXCHANGES, MIN_PRICE, NUM_GAPPERS_PER_DIRECTION
from src.gap_scout.state import Gapper, GraphState

# SPAC units/warrants/rights are typically 4+ letter tickers ending in
# U, W, or R (e.g. FSHPR, RIBBR, IPEXU) -- ordinary common stock tickers on
# NASDAQ/NYSE are almost always 1-4 letters.
_SPAC_SUFFIX_RE = re.compile(r"^[A-Z]{4,}[UWR]$")


def _passes_quality_filters(ticker: str, price: float | None, exchange: str | None) -> bool:
    if price is None or price < MIN_PRICE:
        return False
    if exchange and exchange.strip().upper() not in ALLOWED_EXCHANGES:
        return False
    if _SPAC_SUFFIX_RE.match(ticker):
        return False
    return True


def fetch_gappers(state: GraphState) -> dict:
    fmp = FMPClient()
    gappers: list[Gapper] = []

    raw_limit = max(NUM_GAPPERS_PER_DIRECTION * 6, 30)
    movers_by_direction = (
        (fmp.gainers(limit=raw_limit), "up"),
        (fmp.losers(limit=raw_limit), "down"),
    )

    for movers, label in movers_by_direction:
        kept_for_direction = 0
        for m in movers:
            if kept_for_direction >= NUM_GAPPERS_PER_DIRECTION:
                break

            ticker = m.get("symbol")
            price = m.get("price")
            gap_pct = m.get("changesPercentage")
            exchange = m.get("exchange")

            if not ticker or price is None or gap_pct is None:
                continue
            if not _passes_quality_filters(ticker, price, exchange):
                continue

            try:
                prior_close = float(price) / (1 + float(gap_pct) / 100)
            except ZeroDivisionError:
                continue

            gappers.append(
                Gapper(
                    ticker=ticker,
                    direction=label,
                    gap_pct=round(float(gap_pct), 2),
                    prior_close=round(prior_close, 4),
                    last_price=float(price),
                    premarket_volume=0,  # not available without a per-ticker call; not filtered on for now
                )
            )
            kept_for_direction += 1

    run_date = datetime.now().astimezone().strftime("%Y-%m-%d")
    return {"gappers": gappers, "run_date": run_date}