"""Binary sequence heuristic.

Track a sliding window of the last N messages. If only 2 unique nicks appear
in the window, add a medium-weight edge between them and clear the window.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from .base import InferenceHeuristic

if TYPE_CHECKING:
    from weft.graph.social_graph import SocialGraph
    from weft.parser.znc import ChatMessage


class BinarySequenceHeuristic(InferenceHeuristic):
    """Medium signal: two nicks dominating a short window are likely in dialogue."""

    weight: float = 0.8

    def __init__(self, weight: float = 0.8, window: int = 5) -> None:
        self.weight = weight
        self.window = window
        self._buffer: deque[str] = deque(maxlen=window)

    def process(self, event: "ChatMessage", graph: "SocialGraph") -> None:
        self._buffer.append(event.nick)

        if len(self._buffer) == self.window:
            unique = {n.lower() for n in self._buffer}
            if len(unique) == 2:
                # nicks = list({n for n in self._buffer})  # preserve case
                # Use the first occurrence case for each unique nick
                seen: dict[str, str] = {}
                for n in self._buffer:
                    key = n.lower()
                    if key not in seen:
                        seen[key] = n
                nick_a, nick_b = list(seen.values())
                graph.add_edge(nick_a, nick_b, self.weight)
                self._buffer.clear()
