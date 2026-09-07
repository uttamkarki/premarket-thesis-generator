"""Node 2 (fanned out via Send, one call per ticker): catalyst research."""
from __future__ import annotations

from typing import Literal

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

from src.gap_scout.clients.news_client import NewsClient
from src.gap_scout.config import ANTHROPIC_MODEL
from src.gap_scout.state import Gapper, TickerResearch


class CatalystClassification(BaseModel):
    catalyst_type: Literal[
        "earnings_beat_or_miss",
        "guidance_change",
        "fda_or_trial_news",
        "mna",
        "macro_or_sector",
        "analyst_action",
        "regulatory_or_legal",
        "no_clear_reason",
        "other",
    ] = Field(description="Best-fit category for the news catalyst behind today's gap.")
    summary: str = Field(description="Exactly two plain-English sentences summarizing what happened.")
    magnitude: Literal["small", "medium", "large"] = Field(
        description="How big a deal this looks like as a driver of a real multi-day move."
    )


_SYSTEM_PROMPT = """You are a pre-market gap-trading research assistant for a swing trader who \
follows Breakouts, Episodic Pivots, Parabolic shorts/longs). \
Given a ticker, its gap %, and a batch of recent headlines, identify the most likely catalyst, \
summarize it in exactly two plain-English sentences, and rate how large the catalyst looks \
(small/medium/large) as a driver of a real multi-day move rather than noise. If headlines are \
thin, stale, or unrelated to today's move, classify as no_clear_reason with small magnitude and \
say so plainly rather than guessing."""


def research_ticker(payload: dict) -> dict:
    """`payload` is `{"gapper": Gapper}`, dispatched per-ticker via LangGraph `Send`."""
    gapper: Gapper = payload["gapper"]
    news = NewsClient()

    try:
        articles = news.get_headlines(f"{gapper['ticker']} stock", limit=8)
    except Exception:
        articles = []

    headlines = [
        f"- {a.get('title', '').strip()} ({a.get('publishedDate', '')}): "
        f"{(a.get('text') or '')[:280].strip()}"
        for a in articles[:8]
        if a.get("title")
    ]
    headline_block = "\n".join(headlines) if headlines else "(no recent headlines found)"

    llm = ChatAnthropic(model=ANTHROPIC_MODEL, temperature=0).with_structured_output(
        CatalystClassification
    )
    user_prompt = (
        f"Ticker: {gapper['ticker']}\n"
        f"Direction: gap {gapper['direction']}\n"
        f"Gap %: {gapper['gap_pct']}\n\n"
        f"Recent headlines:\n{headline_block}"
    )
    result: CatalystClassification = llm.invoke(
        [("system", _SYSTEM_PROMPT), ("human", user_prompt)]
    )

    research: TickerResearch = {
        **gapper,
        "catalyst_type": result.catalyst_type,
        "catalyst_magnitude": result.magnitude,
        "summary": result.summary,
        "headlines_used": [a.get("title", "") for a in articles[:8] if a.get("title")],
    }
    return {"researched": [research]}