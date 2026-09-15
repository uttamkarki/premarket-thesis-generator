# Changelog

## 0.4.0
- Removed FMP client's hidden 20-item cap on gainers/losers/most-actives --
  fetch_gappers.py's own docstring said "no limit" but the client silently
  truncated anyway.
- Fixed Schwab enrichment reading from the wrong response block (`extended`
  instead of `quote`) -- confirmed via a real INTC dump that `extended` is
  frequently just empty placeholders even during real trading.
- Added price/gap_pct/prior_close recomputation from Schwab's quote data,
  overriding FMP's changesPercentage -- confirmed root cause: FMP's own
  precomputed gap can reference a stale previousClose very early pre-market.
- Fixed category label going stale after the above correction (a ticker
  tagged "Losers" could flip positive by the time Schwab's fresher quote
  lands; confirmed on FTFT).
- Fixed sort happening before enrichment instead of after.
- Wired up MIN_VOLUME, previously dead config with nothing enforcing it --
  only applied when Schwab enrichment succeeds, so a down/expired Schwab
  connection degrades gracefully instead of rejecting every ticker.

## 0.3.0
- Reverted discovery from Schwab back to FMP: Schwab's `/movers` only
  reflects regular-session activity and is empty pre-market, which defeats
  the point of a 7am scan. FMP's `/biggest-gainers`/`/biggest-losers` proven
  reliable at all hours.
- Added FMP `/most-actives` as a third discovery source, merged with
  gainers/losers into one "Stocks In Play" table (a gap with no follow-on
  volume isn't useful; this catches names becoming active even without a
  top % move).
- Added Schwab as a per-ticker **enrichment** step instead: one batch
  `/quotes` call backfills company name, live pre-market volume, and 10-day
  average volume for the discovered list. Fully resilient -- missing/expired
  Schwab creds degrade gracefully rather than breaking the run.
- `fetch_gappers` now writes a plain-text `Stocks In Play` table to
  `output/stocks_in_play_{date}.txt`, attached to the email via real MIME
  multipart (`gmail_client.py`).
- `research_ticker`'s prompt and schema reworked around a "Stocks In Play"
  quant-research framing (magnitude tiering, no-clear-reason rule, today's
  date injected for staleness checks) with 4 new structured fields:
  `category_label`, `thesis`, `plan_bias`, `plan_action`.
- `compose_thesis` rewritten from an LLM-drafted prose brief to
  **deterministic HTML templating** -- no LLM call, renders identically
  every run. High-Conviction tickers (conviction >= 4) get a full
  Catalyst/Thesis/Plan card; everything else lands in a Low-Conviction/Pass
  table instead of being silently dropped.
- Fixed a critical bug: `market_regime` and `score_ticker` both fed
  `compose_thesis` as parallel branches, which LangGraph treats as OR, not
  AND -- `compose_thesis`/`send_email` fired twice per run (once early with
  an empty gappers section, once later with real data). Graph is now fully
  sequential.
- Fixed a second bug found while fixing the first: a zero-gapper day
  stalled the pipeline entirely (research_ticker's fan-out never triggers
  check_gap_room downstream), so no email sent at all. Added a bypass route
  straight to compose_thesis when the gapper list is empty.
- `market_regime` remains a static placeholder pending real Schwab
  price-history computation -- now feeds `compose_thesis` as a genuine
  sequential predecessor either way, ready for that later.
- `Gapper.direction` changed from `"up"/"down"` to `"Bullish"/"Bearish"`.

## 0.2.0
- Migrated market data to Charles Schwab (movers endpoint, $COMPX + $SPX).
- Stubbed check_gap_room and market_regime pending Schwab field verification.

## 0.1.0
- Initial LangGraph pipeline: fetch_gappers, research_ticker, check_gap_room,
  score_ticker, market_regime, compose_thesis, send_email.
- FMP for market data + Google News RSS for catalysts.