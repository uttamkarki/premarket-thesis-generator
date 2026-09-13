"""Node 5: one-line risk-on / risk-off / neutral read from SPY + VIX.

STILL A STATIC PLACEHOLDER -- this does not compute anything from live
data. It used to pull SPY/VIX history from FMP (cut when that provider's
historical endpoint got dropped); real computation is still pending a
Schwab price-history integration. This string is just a canned stand-in
so the "Market Regime" section of the email isn't empty in the meantime --
update it by hand, or replace this whole function, whenever real signal
is wired in.
"""
from __future__ import annotations

from src.gap_scout.state import GraphState

_PLACEHOLDER_REGIME = (
    "Situational Awareness: Breakout setups are likely to work, but play with "
    "caution as we are in an extended bull market session. Wait for a clean "
    "directional read on the broader market before sizing up."
)


def market_regime(state: GraphState) -> dict:
    return {"market_regime": _PLACEHOLDER_REGIME}