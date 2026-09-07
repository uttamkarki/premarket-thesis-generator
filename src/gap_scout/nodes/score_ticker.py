"""Node 4: combine catalyst magnitude + gap room into a keep/drop + conviction score."""
from __future__ import annotations

from src.gap_scout.state import GraphState, TickerAssessment

_MAGNITUDE_POINTS = {"large": 3, "medium": 2, "small": 1}
_ROOM_POINTS = {"room_to_extend": 2, "unclear": 1, "used_up": 0}


def score_ticker(state: GraphState) -> dict:
    scored: list[TickerAssessment] = []

    for item in state["assessed"]:
        magnitude_points = _MAGNITUDE_POINTS.get(item["catalyst_magnitude"], 1)
        room_points = _ROOM_POINTS.get(item["gap_room"], 1)
        conviction = max(1, min(5, magnitude_points + room_points))

        keep = item["catalyst_magnitude"] != "small" and item["gap_room"] != "used_up"

        scored.append({**item, "conviction": conviction, "keep": keep})

    scored.sort(key=lambda t: t["conviction"], reverse=True)
    return {"assessed": scored}
