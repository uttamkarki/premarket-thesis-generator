"""Node 5: one-line risk-on / risk-off / neutral read from SPY + VIX.

STUBBED as a no-op while FMP is being removed from the project. This used
to pull SPY/VIX history from FMP; that's gone now.
TODO next session: rewire this using SchwabClient's price-history endpoint
for SPX and VIX once its response shape is verified against a live
market-hours test.
"""
from __future__ import annotations

from src.gap_scout.state import GraphState


def market_regime(state: GraphState) -> dict:
    return {"market_regime": "Market regime check not yet wired up to Schwab -- pending next session."}