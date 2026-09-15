"""Node 1: pull today's "Stocks In Play" -- gainers, losers, AND most-active.

Rationale (per user): a stock that gapped but isn't trading actively is not
useful for intraday setups. The flow is gap -> becomes active -> gets
public attention -> tradeable. So discovery pulls all three FMP lists in
full (no cap here -- filtering happens once, in one place, below) and
merges them into a single flat table, tagged with which list(s) it came
from, then sorted by % change.

All three endpoints share the same response shape (symbol, price, name,
change, changesPercentage, exchange) -- confirmed against a live
key. Direction (up/down) is derived from the sign of changesPercentage
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
from src.gap_scout.config import ALLOWED_EXCHANGES, MAX_GAP_PCT, MIN_PRICE, MIN_VOLUME
from src.gap_scout.state import Gapper, GraphState

# SPAC units/warrants/rights are typically 4+ letter tickers ending in
# U, W, or R (e.g. FSHPR, RIBBR, IPEXU) -- ordinary common stock tickers on
# NASDAQ/NYSE are almost always 1-4 letters.
_SPAC_SUFFIX_RE = re.compile(r"^[A-Z]{4,}[UWR]$")

# Mutual funds use a 5-letter ticker ending in X as a hard naming
# convention (e.g. FCIGX, FIDGX, FBCVX). These only price once per day at
# NAV -- they don't gap, don't trade intraday, and have no place in a
# pre-market scan. A "-19% change" on one of these is a distribution event
# or stale data, never a real move.
_MUTUAL_FUND_RE = re.compile(r"^[A-Z]{4}X$")

_CATEGORY_BY_SOURCE = {
    "gainers": "Gainers",
    "losers": "Losers",
    "most_actives": "Most Active",
}


def _passes_quality_filters(
    ticker: str, price: float | None, exchange: str | None, gap_pct: float | None
) -> bool:
    if price is None or price < MIN_PRICE:
        return False
    # NOTE: this used to be `if exchange and exchange.strip().upper() not in
    # ALLOWED_EXCHANGES`, which silently let through any ticker with a
    # missing/None exchange value (the `exchange and ...` short-circuited
    # to False, skipping the check instead of enforcing it -- exactly how
    # some mutual funds with blank exchange data got through). Now a
    # missing exchange is treated as a reject, not a free pass.
    if not exchange or exchange.strip().upper() not in ALLOWED_EXCHANGES:
        return False
    if _SPAC_SUFFIX_RE.match(ticker):
        return False
    if _MUTUAL_FUND_RE.match(ticker):
        return False
    if gap_pct is not None and abs(gap_pct) > MAX_GAP_PCT:
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
        if not _passes_quality_filters(ticker, price, exchange, gap_pct):
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

    schwab_enriched = _enrich_with_schwab(gappers)

    # Volume filter only enforced when Schwab enrichment actually succeeded
    # -- if it's down/expired, every ticker's volume defaults to 0, and
    # filtering on that would wrongly reject the entire list instead of
    # just degrading gracefully like the rest of this pipeline does.
    if schwab_enriched:
        gappers = [g for g in gappers if g["premarket_volume"] >= MIN_VOLUME]

    # Sort AFTER enrichment, not before -- Schwab may have just corrected
    # gap_pct for some tickers, and the table needs to reflect the final,
    # corrected values, not FMP's original (possibly stale) ordering.
    gappers.sort(key=lambda g: g["premarket_volume"], reverse=True)

    run_date = datetime.now().astimezone().strftime("%Y-%m-%d")
    stocks_in_play_path = _write_stocks_in_play_file(gappers, run_date)

    return {"gappers": gappers, "run_date": run_date, "stocks_in_play_path": stocks_in_play_path}


def _enrich_with_schwab(gappers: list[Gapper]) -> bool:
    """Backfill company name, current volume, and 10-day avg volume from
    Schwab's batch /quotes endpoint -- AND recompute price/gap_pct/prior_close
    from Schwab's own numbers when available, overriding FMP's. Also
    corrects `category` when it does: a ticker tagged "Losers" at FMP's
    discovery-time snapshot can have since recovered into positive
    territory by the time Schwab's fresher quote lands (or vice versa) --
    confirmed in practice (FTFT tagged "Gainers" while showing -23%).
    "Most Active" is left alone since it isn't direction-based.

    Field source: `quote`, not `extended`. Confirmed against a real response
    dump (INTC) that `extended`'s fields are frequently just empty
    placeholders (totalVolume=0, quoteTime=0, bidPrice=0.0) even when real
    trading is happening -- while `quote.totalVolume`, `quote.lastPrice`,
    and `quote.closePrice` are populated with real, current numbers in the
    same response. `extended` is kept only as a fallback if `quote`'s
    corresponding field is ever missing.

    Why override FMP's price/gap_pct at all: FMP's `changesPercentage` is
    FMP's own precomputed value, not something we calculate -- and it can
    reference a stale previousClose very early in pre-market (confirmed in
    practice: FMP showed a gap still matching the PRIOR day's move when
    queried early the following morning, instead of the new day's actual
    move vs the new prior close).

    Returns True if the Schwab call itself succeeded (even if individual
    tickers inside it came back with gaps) -- callers use this to decide
    whether it's safe to filter on premarket_volume, since that field is
    meaningless (stuck at 0) when this returns False.

    One call for the whole list. Fully resilient: if Schwab creds are
    missing/expired or the call fails entirely, gappers just keep their
    FMP-derived values (and zero/blank volume/name) rather than crashing
    the run. A single bad ticker inside the batch doesn't affect the
    others (Schwab returns per-symbol errors, not a batch failure).
    """
    if not gappers:
        return False
    try:
        schwab = SchwabClient()
        quotes = schwab.quotes([g["ticker"] for g in gappers])
    except Exception as exc:
        print(f"  [warn] Schwab enrichment skipped entirely: {exc}")
        return False

    for g in gappers:
        entry = quotes.get(g["ticker"])
        if not entry or not isinstance(entry, dict):
            continue
        extended = entry.get("extended", {}) or {}
        fundamental = entry.get("fundamental", {}) or {}
        reference = entry.get("reference", {}) or {}
        quote = entry.get("quote", {}) or {}

        volume = quote.get("totalVolume")
        if not volume:
            volume = extended.get("totalVolume")  # fallback only
        if volume is not None:
            g["premarket_volume"] = int(volume)

        if fundamental.get("avg10DaysVolume") is not None:
            g["avg_volume_10d"] = int(fundamental["avg10DaysVolume"])
        if reference.get("description"):
            g["company_name"] = reference["description"]

        # Recompute price/gap_pct/prior_close from Schwab's fresher numbers
        # when both a current price and a real previous close are available.
        fresh_price = quote.get("lastPrice") or extended.get("lastPrice")
        fresh_prior_close = quote.get("closePrice")
        if fresh_price and fresh_prior_close:
            try:
                new_gap_pct = (float(fresh_price) - float(fresh_prior_close)) / float(fresh_prior_close) * 100
            except ZeroDivisionError:
                continue
            g["last_price"] = round(float(fresh_price), 4)
            g["prior_close"] = round(float(fresh_prior_close), 4)
            g["gap_pct"] = round(new_gap_pct, 2)
            g["direction"] = "Bullish" if new_gap_pct >= 0 else "Bearish"
            if g["category"] in ("Gainers", "Losers"):
                g["category"] = "Gainers" if new_gap_pct >= 0 else "Losers"

    return True


def _write_stocks_in_play_file(gappers: list[Gapper], run_date: str) -> str:
    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"stocks_in_play_{run_date}.txt"

    header = (
        f"{'Ticker':<8}{'Company':<26}{'Category':<14}{'Price':>10}{'Gap %':>10}"
        f"{'PM Vol':>12}{'10d Avg Vol':>14}"
    )
    lines = [header, "-" * len(header)]
    for g in gappers:
        lines.append(
            f"{g['ticker']:<8}{g['company_name'][:24]:<26}{g['category']:<14}"
            f"{g['last_price']:>10.2f}{g['gap_pct']:>+10.2f}"
            f"{g['premarket_volume']:>12,}{g['avg_volume_10d']:>14,}"
        )

    path.write_text("\n".join(lines))
    print(f"  [info] Stocks In Play: {len(gappers)} rows written to {path}")
    return str(path)