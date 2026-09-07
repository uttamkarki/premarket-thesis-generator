"""Node 3: is the gap already 'used up' relative to the stock's typical range?"""
from __future__ import annotations

from src.gap_scout.clients.fmp_client import FMPClient
from src.gap_scout.state import GraphState, TickerAssessment


def _atr_pct(client: FMPClient, ticker: str, prior_close: float, days: int = 14) -> float | None:
    """Average true range over `days` trading sessions, as a % of prior close."""
    bars = client.historical_daily(ticker, days=days + 1)  # +1 for the prev-close anchor
    if not bars or not prior_close:
        return None

    true_ranges: list[float] = []
    prev_close = bars[0].get("close")
    for bar in bars[1:]:
        high, low, close = bar.get("high"), bar.get("low"), bar.get("close")
        if high is None or low is None or prev_close is None:
            continue
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)
        prev_close = close

    if not true_ranges:
        return None
    atr = sum(true_ranges) / len(true_ranges)
    return round((atr / prior_close) * 100, 2)


def check_gap_room(state: GraphState) -> dict:
    fmp = FMPClient()
    roomed: list[TickerAssessment] = []

    for item in state["researched"]:
        try:
            atr_pct = _atr_pct(fmp, item["ticker"], item["prior_close"])
        except Exception:
            atr_pct = None
        move_pct = abs(item["gap_pct"])

        range_used_pct = None
        gap_room: str = "unclear"
        if atr_pct:
            range_used_pct = round((move_pct / atr_pct) * 100, 0)
            if range_used_pct >= 150:
                gap_room = "used_up"
            elif range_used_pct <= 80:
                gap_room = "room_to_extend"
            else:
                gap_room = "unclear"

        roomed.append(
            {
                **item,
                "atr_pct": atr_pct if atr_pct is not None else 0.0,
                "range_used_pct": range_used_pct if range_used_pct is not None else 0.0,
                "gap_room": gap_room,  # type: ignore[typeddict-item]
                "conviction": 0,
                "keep": False,
            }
        )

    return {"assessed": roomed}