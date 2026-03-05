"""Adjacency heuristic.

If person A speaks immediately after person B (consecutive messages, different nicks),
add a very weak edge between them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import InferenceHeuristic

if TYPE_CHECKING:
    from weft.graph.social_graph import SocialGraph
    from weft.parser.znc import ChatMessage


class AdjacencyHeuristic(InferenceHeuristic):
    """Very weak signal: consecutive speakers may be in conversation."""

    weight: float = 0.2

    def __init__(self, weight: float = 0.2) -> None:
        self.weight = weight
        self._last_nick: str | None = None

    def process(self, event: "ChatMessage", graph: "SocialGraph") -> None:
        current = event.nick
        if self._last_nick is not None and self._last_nick.lower() != current.lower():
            graph.add_edge(current, self._last_nick, self.weight)
        self._last_nick = current
