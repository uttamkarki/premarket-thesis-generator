"""Node 2 (fanned out via Send, one call per ticker): catalyst research."""
from __future__ import annotations

from datetime import datetime
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
    ] = Field(
        description=(
            "The underlying fundamental catalyst driving today's pre-market volume. "
            "Per the NO CLEAR REASON RULE: use 'no_clear_reason' if headlines are "
            "thin, stale (older than 48 hours), or unrelated to the gap direction -- "
            "do not fabricate a narrative to fit a more specific category."
        )
    )
    summary: str = Field(
        description=(
            "Exactly two plain-English sentences detailing the operational reality "
            "of the news -- what actually happened, not vague stock-market jargon."
        )
    )
    magnitude: Literal["small", "medium", "large"] = Field(
        description=(
            "LARGE: a structural, multi-day systemic move -- massive earnings beat "
            "plus guidance raise, major FDA clearance, an M&A buyout offer. "
            "MEDIUM: a decent immediate trading catalyst that's prone to intraday "
            "mean-reversion -- a secondary contract award, an analyst upgrade. "
            "SMALL: low-volume noise or macro/sector correlation with no company-"
            "specific catalyst -- also the correct tier whenever catalyst_type is "
            "'no_clear_reason'."
        )
    )
    category_label: str = Field(
        description=(
            "A short, human-readable tag for the brief's UI -- 2 to 4 words, title "
            "case, e.g. 'Earnings Blowout', 'Secondary Offering', 'M&A Buyout', "
            "'Debt Retirement', 'Index Rebalance', 'Theme Extension'. This is shown "
            "to the trader directly, so it must read naturally -- do not just "
            "restate catalyst_type's enum value."
        )
    )
    thesis: str = Field(
        description=(
            "1-2 sentences on why this setup matters and how it's likely to play "
            "out -- the trading interpretation, not a restatement of the news "
            "itself. E.g. 'Purely technical selling pressure. Setups like this can "
            "flush hard at the open, then stabilize once the block clears.'"
        )
    )
    plan_bias: Literal["Long", "Short"] = Field(
        description="Directional bias for this setup given the catalyst and gap direction."
    )
    plan_action: str = Field(
        description=(
            "1-2 sentences: the concrete entry trigger or what to wait for, in the "
            "voice of a professional trader giving a colleague a game plan. E.g. "
            "'Watch for orderly price action after the open; a clean base near "
            "High of Day (HOD) is the entry trigger. Wait for confirmation.'"
        )
    )


_SYSTEM_PROMPT = """

You are an expert quantitative research assistant for a professional trader specializing in high-velocity "Stocks In Play". \
The trader executes strategies strictly anchored on Breakouts, Episodic Pivots (EP), Earnings Plays, and major macro/micro catalysts.

CRITICAL GOAL
Analyze a given stock ticker's immediate market profile, gap magnitude, and a raw batch of news headlines. Your task is to extract the \
underlying fundamental catalyst driving the pre-market volume, summarize the core thesis, and assess its technical magnitude.

CRITICAL INSTRUCTIONS & GUARDRAILS:
1. MAGNITUDE TIERING:
   - LARGE: Generates structural, multi-day systemic moves (e.g., massive earnings beats + guidance raise, major FDA clearance, M&A buyout offers).
   - MEDIUM: Decent immediate trading catalyst but prone to intraday mean-reversion (e.g., secondary contract awards, analyst upgrades).
   - SMALL: Low-volume noise or macro sector correlation.
2. NO CLEAR REASON RULE: If the headlines are thin, stale (older than 48 hours), or unrelated to the gap direction, you MUST explicitly \
    classify the catalyst as "no_clear_reason" with a "small" magnitude. Say so plainly rather than guessing or fabricating a narrative.
3. SUMMARY CONSTRAINT: Your summary must be exactly two plain-English sentences detailing the operational reality of the news. Avoid vague \
    stock-market jargon.
4. THESIS AND PLAN: In addition to the catalyst summary, provide a "thesis" (why this setup matters and how it's likely to play out) and a \
    "plan_action" (the concrete entry trigger or what to wait for, written like a professional trader briefing a colleague). Pick a "plan_bias" \
    of Long or Short based on the catalyst and gap direction. These apply even to no_clear_reason/small-magnitude tickers -- the thesis in \
    that case should explain why the setup is skippable, and the plan should say to pass or wait for confirmation rather than chase.
5. CATEGORY LABEL: Provide a short, natural-language "category_label" (2-4 words) for the catalyst, distinct from the fixed catalyst_type \
    enum -- e.g. "Earnings Blowout" or "Secondary Offering" rather than the raw enum value.

STRICT OUTPUT FORMAT:
You must return your analysis formatted EXACTLY like the markdown layout below, with no conversational preamble, intros, or meta-commentary:

- **Catalyst Category:** [Insert Class, e.g., Earnings, FDA Approval, M&A, or no_clear_reason]
- **Magnitude:** [SMALL / MEDIUM / LARGE]
- **Summary:** [Insert exactly two plain-English sentences.]
- **Thesis:** [1-2 sentences on why this matters and how it's likely to play out.]
- **Plan:** [BIAS: LONG or SHORT. 1-2 sentences on the entry trigger or what to wait for.]

"""


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
        f"Today's date: {datetime.now().astimezone().strftime('%Y-%m-%d')}\n"
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
        "category_label": result.category_label,
        "catalyst_magnitude": result.magnitude,
        "summary": result.summary,
        "thesis": result.thesis,
        "plan_bias": result.plan_bias,
        "plan_action": result.plan_action,
        "headlines_used": [a.get("title", "") for a in articles[:8] if a.get("title")],
    }
    return {"researched": [research]}