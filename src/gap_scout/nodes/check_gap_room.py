"""Node 3: is the gap already 'used up' relative to the stock's typical range?

STUBBED as a no-op while FMP is being removed from the project. This used
to compute ATR% from FMP's historical-price-eod endpoint; that's gone now.
TODO next session: rewire this using SchwabClient's price-history endpoint
once its response shape is verified against a live market-hours test.
"""
from __future__ import annotations

from src.gap_scout.state import GraphState, TickerAssessment


def check_gap_room(state: GraphState) -> dict:
    assessed: list[TickerAssessment] = [
        {
            **item,
            "atr_pct": 0.0,
            "range_used_pct": 0.0,
            "gap_room": "unclear",  # type: ignore[typeddict-item]
            "conviction": 0,
            "keep": False,
        }
        for item in state["researched"]
    ]
    return {"assessed": assessed}