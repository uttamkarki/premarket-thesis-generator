"""Node 1: pull today's top gap-up and gap-down tickers via Schwab movers.

STATUS: field-name parsing below is a best guess, NOT yet verified against
a populated response -- confirmed only that the endpoint returns
{"screeners": [...]} with an empty list (tested on a market holiday, so
no data to inspect). Finalize the inner-object field names once we test
this during real market hours.

Applies quality filters so the scan reflects real, tradeable gappers
rather than every sub-$1 SPAC unit/warrant/rights ticker: minimum price,
allowed exchanges, and a ticker-suffix pattern for SPAC units/warrants/rights.
"""
from __future__ import annotations

import re
from datetime import datetime

from src.gap_scout.clients.schwab_client import SchwabClient
from src.gap_scout.config import (
    ALLOWED_EXCHANGES,
    MIN_PRICE,
    NUM_GAPPERS_PER_DIRECTION,
    SCHWAB_MOVER_INDICES,
)
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
    schwab = SchwabClient()
    gappers: list[Gapper] = []
    seen_tickers: set[str] = set()

    for label, sort in (("up", "PERCENT_CHANGE_UP"), ("down", "PERCENT_CHANGE_DOWN")):
        kept_for_direction = 0
        for index_symbol in SCHWAB_MOVER_INDICES:
            if kept_for_direction >= NUM_GAPPERS_PER_DIRECTION:
                break
            entries = schwab.movers(index_symbol, sort=sort)
            for e in entries:
                if kept_for_direction >= NUM_GAPPERS_PER_DIRECTION:
                    break

                # TODO: confirm these field names against a real populated
                # response -- best guesses based on this API family for now.
                ticker = e.get("symbol")
                last_price = e.get("lastPrice")
                gap_pct = e.get("netPercentChange")
                volume = e.get("totalVolume") or e.get("volume") or 0
                exchange = e.get("exchangeName") or e.get("exchange")

                if not ticker or ticker in seen_tickers:
                    continue
                if last_price is None or gap_pct is None:
                    continue
                if not _passes_quality_filters(ticker, float(last_price), exchange):
                    continue

                try:
                    prior_close = float(last_price) / (1 + float(gap_pct) / 100)
                except ZeroDivisionError:
                    continue

                gappers.append(
                    Gapper(
                        ticker=ticker,
                        direction=label,
                        gap_pct=round(float(gap_pct), 2),
                        prior_close=round(prior_close, 4),
                        last_price=float(last_price),
                        premarket_volume=int(volume or 0),
                    )
                )
                seen_tickers.add(ticker)
                kept_for_direction += 1

    run_date = datetime.now().astimezone().strftime("%Y-%m-%d")
    return {"gappers": gappers, "run_date": run_date}