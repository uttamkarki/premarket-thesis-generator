"""LangGraph assembly for the gap-scout pipeline.

Flow (fully sequential -- see note below on why):
    START --> fetch_gappers --> market_regime --> [gappers empty?]
                                                       |-- yes --> compose_thesis --> send_email --> END
                                                       |-- no  --> (Send fan-out) --> research_ticker
                                                                   --> check_gap_room --> score_ticker
                                                                   --> compose_thesis --> send_email --> END

NOTE on why market_regime isn't a parallel branch off START:
LangGraph treats two separate `add_edge(X, "compose_thesis")` calls as an
OR, not an AND -- the node fires once per predecessor that completes, not
once after both complete. With market_regime and score_ticker both feeding
compose_thesis as parallel branches, compose_thesis (and everything after
it, including send_email) ran TWICE per pipeline execution: once early
when the near-instant market_regime placeholder finished, producing an
email with an empty gappers section, and again later when the slower
research/scoring branch finished, producing the real email. Two emails,
every run. Keeping this fully sequential avoids the double-fire entirely.
market_regime still runs before compose_thesis either way, so its output
is always available to the thesis draft -- this is about edge wiring, not
about whether market_regime's data reaches compose_thesis (it always does,
via shared state). If market_regime ever becomes real, non-trivial work
(e.g. a live Schwab call), reintroduce it as a true parallel branch using
a node-level `defer=True` barrier on compose_thesis instead of plain
add_edge.

NOTE on the empty-gappers bypass:
If fetch_gappers returns zero tickers, there's nothing for research_ticker
to fan out over -- Send dispatches zero calls, so research_ticker never
fires, and everything downstream of it (check_gap_room, score_ticker) never
fires either, which previously meant compose_thesis/send_email never ran
and NO email went out at all on a zero-gapper day. The conditional edge
below detects this and routes straight to compose_thesis, skipping the
research/scoring nodes entirely (cheapest option -- no news lookups or
Claude calls for tickers that don't exist). compose_thesis already handles
an empty `assessed` list correctly (prints "no gappers cleared" and tells
the trader to sit on hands), so no changes were needed there.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from src.gap_scout.nodes.check_gap_room import check_gap_room
from src.gap_scout.nodes.compose_thesis import compose_thesis
from src.gap_scout.nodes.fetch_gappers import fetch_gappers
from src.gap_scout.nodes.market_regime import market_regime
from src.gap_scout.nodes.research_ticker import research_ticker
from src.gap_scout.nodes.score_ticker import score_ticker
from src.gap_scout.nodes.send_email import send_email
from src.gap_scout.state import GraphState


def _route_to_research(state: GraphState) -> str | list[Send]:
    """Fan out one `research_ticker` call per gapper, run in parallel --
    unless there are zero gappers, in which case skip straight to
    compose_thesis (nothing to research, nothing to score)."""
    if not state["gappers"]:
        return "compose_thesis"
    return [Send("research_ticker", {"gapper": g}) for g in state["gappers"]]


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("fetch_gappers", fetch_gappers)
    graph.add_node("research_ticker", research_ticker)
    graph.add_node("check_gap_room", check_gap_room)
    graph.add_node("score_ticker", score_ticker)
    graph.add_node("market_regime", market_regime)
    graph.add_node("compose_thesis", compose_thesis)
    graph.add_node("send_email", send_email)

    # Fully sequential -- see module docstring for why market_regime is not
    # a parallel branch off START.
    graph.add_edge(START, "fetch_gappers")
    graph.add_edge("fetch_gappers", "market_regime")

    graph.add_conditional_edges(
        "market_regime", _route_to_research, ["research_ticker", "compose_thesis"]
    )
    graph.add_edge("research_ticker", "check_gap_room")
    graph.add_edge("check_gap_room", "score_ticker")

    graph.add_edge("score_ticker", "compose_thesis")
    graph.add_edge("compose_thesis", "send_email")
    graph.add_edge("send_email", END)

    return graph.compile()