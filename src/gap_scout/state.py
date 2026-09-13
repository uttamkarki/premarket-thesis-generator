"""Shared graph state for the gap-scout LangGraph pipeline."""
from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict


class Gapper(TypedDict):
    """A single ticker pulled from the pre-market gap scan."""

    ticker: str
    company_name: str
    category: Literal["Gainers", "Losers", "Most Active"]
    direction: Literal["Bullish", "Bearish"]
    gap_pct: float
    prior_close: float
    last_price: float
    premarket_volume: int
    avg_volume_10d: int


class TickerResearch(Gapper):
    """Gapper plus the news-derived catalyst read from `research_ticker`."""

    catalyst_type: str
    category_label: str
    catalyst_magnitude: Literal["small", "medium", "large"]
    summary: str
    thesis: str
    plan_bias: Literal["Long", "Short"]
    plan_action: str
    headlines_used: list[str]


class TickerAssessment(TickerResearch):
    """TickerResearch plus gap-room + scoring data."""

    atr_pct: float
    range_used_pct: float
    gap_room: Literal["used_up", "room_to_extend", "unclear"]
    conviction: int  # 1-5
    keep: bool


class GraphState(TypedDict):
    """The full shared state passed between LangGraph nodes."""

    run_date: str
    gappers: list[Gapper]
    stocks_in_play_path: str

    # Populated by parallel `Send`-fanned `research_ticker` calls, one list
    # entry appended per ticker -> needs an additive reducer.
    researched: Annotated[list[TickerResearch], operator.add]

    # Populated wholesale (overwritten) by `check_gap_room` and then again by
    # `score_ticker` -- deliberately NOT an additive reducer.
    assessed: list[TickerAssessment]

    market_regime: str
    email_body: str
    email_sent: bool