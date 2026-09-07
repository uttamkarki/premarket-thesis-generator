"""Node 1: pull today's top gap-up and gap-down tickers (free-tier FMP).

Applies quality filters so the scan reflects real, tradeable gappers --
similar in spirit to what a curated feed like Briefing.com's movers list
would show -- rather than every sub-$1 SPAC unit/warrant/rights ticker
that a raw movers list includes.

IMPORTANT: this deliberately never calls FMP's /quote endpoint. Confirmed
against a live free-tier key that /stable/quote only works for AAPL (likely
a whitelisted demo symbol) and returns 402 Payment Required for every other
ticker, even large, liquid ones (GWRE, EGAN, etc). Everything below is
derived instead from:
  - /biggest-gainers, /biggest-losers -- free, gives price + % change, from
    which previousClose is derived algebraically (no extra request needed).
  - /historical-price-eod/full -- free, used only for its most recent day's
    volume, as a liquidity proxy (this is prior-day volume, not true live
    premarket volume, which the free tier has no way to provide).
"""
from __future__ import annotations

import re
import time
from datetime import datetime

from src.gap_scout.clients.fmp_client import FMPClient
from src.gap_scout.config import (
    ALLOWED_EXCHANGES,
    MIN_PRICE,
    MIN_VOLUME,
    NUM_GAPPERS_PER_DIRECTION,
)
from src.gap_scout.state import Gapper, GraphState

# SPAC units/warrants/rights are typically 4+ letter tickers ending in
# U, W, or R (e.g. FSHPR, RIBBR, IPEXU) -- ordinary common stock tickers on
# NASDAQ/NYSE are almost always 1-4 letters.
_SPAC_SUFFIX_RE = re.compile(r"^[A-Z]{4,}[UWR]$")

# Delay between per-ticker historical_daily() calls, to avoid tripping any
# burst rate limit on the free plan.
_REQUEST_DELAY_SECONDS = 0.35


def _passes_cheap_filters(ticker: str, price: float | None, exchange: str | None) -> bool:
    """Filters using only data already on the gainers/losers list -- no extra request."""
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

    raw_limit = max(NUM_GAPPERS_PER_DIRECTION * 4, 20)
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
            if not _passes_cheap_filters(ticker, price, exchange):
                continue

            # previousClose = price / (1 + pct_change/100) -- no extra request.
            try:
                prior_close = float(price) / (1 + float(gap_pct) / 100)
            except ZeroDivisionError:
                continue

            # Liquidity check via yesterday's volume (free, no /quote needed).
            time.sleep(_REQUEST_DELAY_SECONDS)
            try:
                bars = fmp.historical_daily(ticker, days=2)
            except Exception as exc:
                print(f"  skipping {ticker}: historical lookup failed ({exc})")
                continue
            if not bars:
                continue
            volume = bars[-1].get("volume", 0) or 0
            if volume < MIN_VOLUME:
                continue

            gappers.append(
                Gapper(
                    ticker=ticker,
                    direction=label,
                    gap_pct=round(float(gap_pct), 2),
                    prior_close=round(prior_close, 4),
                    last_price=float(price),
                    premarket_volume=int(volume),
                )
            )
            kept_for_direction += 1

    run_date = datetime.now().astimezone().strftime("%Y-%m-%d")
    return {"gappers": gappers, "run_date": run_date}