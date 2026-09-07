"""Node 5: one-line risk-on / risk-off / neutral read from SPY + VIX (free-tier FMP)."""
from __future__ import annotations

from src.gap_scout.clients.fmp_client import FMPClient
from src.gap_scout.state import GraphState


def _pct_change(bars: list[dict]) -> float | None:
    if len(bars) < 2:
        return None
    first, last = bars[0].get("close"), bars[-1].get("close")
    if not first:
        return None
    return round(((last - first) / first) * 100, 2)


def market_regime(state: GraphState) -> dict:
    fmp = FMPClient()

    try:
        spy_bars = fmp.historical_daily("SPY", days=15)
    except Exception:
        spy_bars = []
    try:
        vix_bars = fmp.historical_daily("%5EVIX", days=15)
    except Exception:
        vix_bars = []

    spy_trend = _pct_change(spy_bars[-10:]) if spy_bars else None
    vix_level = vix_bars[-1]["close"] if vix_bars else None
    vix_trend = _pct_change(vix_bars[-5:]) if vix_bars else None

    if spy_trend is None or vix_level is None:
        regime = "Neutral (market data unavailable this run — trade smaller and confirm manually)."
    elif spy_trend > 1 and vix_level < 20 and (vix_trend or 0) <= 0:
        regime = f"Risk-on: SPY +{spy_trend}% over the last 10 sessions, VIX {vix_level:.1f} and calm."
    elif spy_trend < -1 or vix_level > 25:
        regime = (
            f"Risk-off: SPY {spy_trend}% over the last 10 sessions, VIX {vix_level:.1f} elevated. "
            "Trade smaller, favor shorts or pass."
        )
    else:
        regime = f"Neutral/chop: SPY {spy_trend}% over the last 10 sessions, VIX {vix_level:.1f}. Be selective."

    return {"market_regime": regime}