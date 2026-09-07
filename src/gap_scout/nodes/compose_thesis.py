"""Node 6: draft the final HTML brief from the surviving tickers + regime."""
from __future__ import annotations

from langchain_anthropic import ChatAnthropic

from src.gap_scout.config import ANTHROPIC_MODEL
from src.gap_scout.state import GraphState

_SYSTEM_PROMPT = """You write a concise, no-fluff pre-market gap-trading brief for a swing \
trader who follows Breakouts, Episodic Pivots, Parabolic \
shorts/longs). Output clean HTML fragment only (no markdown, no <html>/<body>/<head> wrapper) \
using <h2>, <h3>, <p>, <ul>/<li> tags. Structure:

1. <h2>Market Regime</h2> — one short paragraph using the regime line given.
2. <h2>Today's Gappers</h2> — tickers ranked by conviction, highest first. For each ticker: \
   <h3>TICKER — gap %</h3> then a short paragraph combining the catalyst summary, the gap-room \
   read, and a one-line suggested bias (long / short / pass) tied to whichever setup \
   fits best (Breakout, Episodic Pivot, or Parabolic short/long) if one clearly applies.
3. If no tickers survived, say so plainly and suggest sitting on hands today.

Do not invent facts beyond what's given. Keep it skimmable — readable in under two minutes."""


def compose_thesis(state: GraphState) -> dict:
    kept = [t for t in state["assessed"] if t.get("keep")]
    kept.sort(key=lambda t: t["conviction"], reverse=True)

    lines = [f"Market regime: {state['market_regime']}", ""]
    if not kept:
        lines.append("No gappers cleared the catalyst/gap-room bar today.")
    for t in kept:
        lines.append(
            f"{t['ticker']} | gap {t['direction']} {t['gap_pct']}% | conviction {t['conviction']}/5\n"
            f"  catalyst: {t['catalyst_type']} ({t['catalyst_magnitude']}) - {t['summary']}\n"
            f"  gap room: {t['gap_room']} (used ~{t['range_used_pct']}% of {t['atr_pct']}% ADR)"
        )
    facts_block = "\n".join(lines)

    llm = ChatAnthropic(model=ANTHROPIC_MODEL, temperature=0.2)
    response = llm.invoke(
        [
            ("system", _SYSTEM_PROMPT),
            ("human", f"Facts for today ({state['run_date']}):\n\n{facts_block}"),
        ]
    )
    return {"email_body": response.content}
