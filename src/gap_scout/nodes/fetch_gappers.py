"""Node 1: pull today's "Stocks In Play" -- gainers, losers, AND most-active.

Rationale (per user): a stock that gapped but isn't trading actively is not
useful for intraday setups. The flow is gap -> becomes active -> gets
public attention -> tradeable. So discovery pulls all three FMP lists in
full (no cap here -- filtering happens once, in one place, below) and
merges them into a single flat table, tagged with which list(s) it came
from, then sorted by % change.

All three endpoints share the same response shape (symbol, price, name,
change, changesPercentage, exchange). Direction (up/down) is derived from the sign of changesPercentage
rather than trusted from which endpoint it came from, since most-actives
isn't itself directional.

Quality filter applied once, after merging: price >= MIN_PRICE, allowed
exchanges only, no SPAC unit/warrant/rights tickers.

Also writes the full resulting table to output/stocks_in_play_{date}.txt
as a plain-text artifact, so the raw discovery output can be eyeballed
directly rather than only seen after it's been through news research.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from src.gap_scout.clients.fmp_client import FMPClient
from src.gap_scout.clients.schwab_client import SchwabClient
from src.gap_scout.config import ALLOWED_EXCHANGES, MIN_PRICE
from src.gap_scout.state import Gapper, GraphState

# SPAC units/warrants/rights are typically 4+ letter tickers ending in
# U, W, or R (e.g. FSHPR, RIBBR, IPEXU) -- ordinary common stock tickers on
# NASDAQ/NYSE are almost always 1-4 letters.
_SPAC_SUFFIX_RE = re.compile(r"^[A-Z]{4,}[UWR]$")

_CATEGORY_BY_SOURCE = {
    "gainers": "Gainers",
    "losers": "Losers",
    "most_actives": "Most Active",
}


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

    # No limit here -- pull everything each endpoint returns. Filtering
    # happens once, in one place, after everything is merged and tagged.
    merged: dict[str, dict[str, Any]] = {}
    for source_name in ("gainers", "losers", "most_actives"):
        source_call = getattr(fmp, source_name)
        try:
            entries = source_call()
        except Exception as exc:
            print(f"  [warn] {source_name} failed: {exc}")
            continue
        category = _CATEGORY_BY_SOURCE[source_name]
        for e in entries:
            ticker = e.get("symbol")
            if ticker and ticker not in merged:
                merged[ticker] = {**e, "category": category}

    gappers: list[Gapper] = []
    for ticker, e in merged.items():
        price = e.get("price")
        gap_pct = e.get("changesPercentage")
        exchange = e.get("exchange")

        if price is None or gap_pct is None:
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
                company_name="",
                category=e["category"],
                direction="Bullish" if float(gap_pct) >= 0 else "Bearish",
                gap_pct=round(float(gap_pct), 2),
                prior_close=round(prior_close, 4),
                last_price=float(price),
                premarket_volume=0,
                avg_volume_10d=0,
            )
        )

    # One sort, whole table: gainers at top, decliners at bottom.
    gappers.sort(key=lambda g: g["gap_pct"], reverse=True)

    _enrich_with_schwab(gappers)

    run_date = datetime.now().astimezone().strftime("%Y-%m-%d")
    stocks_in_play_path = _write_stocks_in_play_file(gappers, run_date)

    return {"gappers": gappers, "run_date": run_date, "stocks_in_play_path": stocks_in_play_path}


def _enrich_with_schwab(gappers: list[Gapper]) -> None:
    """Backfill company name, premarket volume, and 10-day avg volume from
    Schwab's batch /quotes endpoint. One call for the whole list. Fully
    resilient: if Schwab creds are missing/expired or the call fails
    entirely, gappers just keep their zero/blank defaults rather than
    crashing the run. A single bad ticker inside the batch doesn't affect
    the others (Schwab returns per-symbol errors, not a batch failure).
    """
    if not gappers:
        return
    try:
        schwab = SchwabClient()
        quotes = schwab.quotes([g["ticker"] for g in gappers])
    except Exception as exc:
        print(f"  [warn] Schwab enrichment skipped entirely: {exc}")
        return

    for g in gappers:
        entry = quotes.get(g["ticker"])
        if not entry or not isinstance(entry, dict):
            continue
        extended = entry.get("extended", {}) or {}
        fundamental = entry.get("fundamental", {}) or {}
        reference = entry.get("reference", {}) or {}

        if extended.get("totalVolume") is not None:
            g["premarket_volume"] = int(extended["totalVolume"])
        if fundamental.get("avg10DaysVolume") is not None:
            g["avg_volume_10d"] = int(fundamental["avg10DaysVolume"])
        if reference.get("description"):
            g["company_name"] = reference["description"]


def _write_stocks_in_play_file(gappers: list[Gapper], run_date: str) -> str:
    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"stocks_in_play_{run_date}.txt"

    header = (
        f"{'Ticker':<8}{'Company':<28}{'Category':<14}{'Price':>10}{'Gap %':>10}"
        f"{'PM Vol':>12}{'10d Avg Vol':>14}"
    )
    lines = [header, "-" * len(header)]
    for g in gappers:
        lines.append(
            f"{g['ticker']:<8}{g['company_name'][:26]:<28}{g['category']:<14}"
            f"{g['last_price']:>10.2f}{g['gap_pct']:>+10.2f}"
            f"{g['premarket_volume']:>12,}{g['avg_volume_10d']:>14,}"
        )

    path.write_text("\n".join(lines))
    print(f"  [info] Stocks In Play: {len(gappers)} rows written to {path}")
    return str(path)