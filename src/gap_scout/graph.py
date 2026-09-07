"""LangGraph assembly for the gap-scout pipeline.

Flow:
    START --> fetch_gappers --> (Send fan-out) --> research_ticker  --\
    START --> market_regime -----------------------------------------> compose_thesis --> send_email --> END
                                  research_ticker --> check_gap_room --> score_ticker --/
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


def _route_to_research(state: GraphState) -> list[Send]:
    """Fan out one `research_ticker` call per gapper, run in parallel."""
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

    # Two independent branches from START, run concurrently.
    graph.add_edge(START, "fetch_gappers")
    graph.add_edge(START, "market_regime")

    # Ticker branch: fan out for research, then fan back in sequentially.
    graph.add_conditional_edges("fetch_gappers", _route_to_research, ["research_ticker"])
    graph.add_edge("research_ticker", "check_gap_room")
    graph.add_edge("check_gap_room", "score_ticker")

    # Both branches join at compose_thesis.
    graph.add_edge("score_ticker", "compose_thesis")
    graph.add_edge("market_regime", "compose_thesis")

    graph.add_edge("compose_thesis", "send_email")
    graph.add_edge("send_email", END)

    return graph.compile()
