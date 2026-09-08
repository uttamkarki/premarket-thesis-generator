# Changelog

## 0.2.0
- Removed FMP and Massive (both hit free-tier paid-endpoint walls).
- Migrated market data to Charles Schwab (movers endpoint, $COMPX + $SPX).
- Stubbed check_gap_room and market_regime pending Schwab field verification.

## 0.1.0
- Initial LangGraph pipeline: fetch_gappers, research_ticker, check_gap_room,
  score_ticker, market_regime, compose_thesis, send_email.
- FMP (free tier) for market data + Google News RSS for catalysts.
