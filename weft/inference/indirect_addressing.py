"""Indirect addressing heuristic.

Detects any known nick mentioned anywhere in the message body (whole-word, case-insensitive).
Skips nicks already matched by direct addressing to avoid double-counting.

Optimised for large log volumes: uses a pre-built set of lowercased nicks and
splits the message into words for O(words) lookup instead of regex scanning.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import InferenceHeuristic

if TYPE_CHECKING:
    from weft.graph.social_graph import SocialGraph
    from weft.parser.znc import ChatMessage

# Characters commonly found adjacent to nicks that we strip for matching
_STRIP_CHARS = ",:;.!?()[]{}\"'`~<>@#$%^&*+=/\\|"


class IndirectAddressingHeuristic(InferenceHeuristic):
    """Weaker signal: a nick appears anywhere in the message."""

    weight: float = 0.5

    def __init__(self, weight: float = 0.5, direct_heuristic=None) -> None:
        self.weight = weight
        self.direct_heuristic = direct_heuristic
        # Cache: lowercase nick set + case map, rebuilt when graph changes
        self._cached_node_count: int = -1
        self._nick_lower_set: set[str] = set()
        self._nick_lower_map: dict[str, str] = {}  # lowercase -> original case

    def _refresh_cache(self, graph: "SocialGraph") -> None:
        """Rebuild nick lookup cache if the node count changed."""
        count = len(graph.nodes())
        if count == self._cached_node_count:
            return
        self._cached_node_count = count
        self._nick_lower_set.clear()
        self._nick_lower_map.clear()
        for nick in graph.nodes():
            low = nick.lower()
            self._nick_lower_set.add(low)
            self._nick_lower_map[low] = nick

    def process(self, event: "ChatMessage", graph: "SocialGraph") -> None:
        self._refresh_cache(graph)

        if not self._nick_lower_set:
            return

        sender_lower = event.nick.lower()

        # Determine which nick was already matched by direct addressing
        skip_nick: str | None = None
        if self.direct_heuristic is not None:
            skip_nick = self.direct_heuristic.last_matched_nick

        # Split message into words and strip punctuation for matching
        seen: set[str] = set()
        for word in event.message.split():
            candidate = word.strip(_STRIP_CHARS).lower()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            if candidate == sender_lower:
                continue
            if skip_nick is not None and candidate == skip_nick:
                continue
            if candidate in self._nick_lower_set:
                original = self._nick_lower_map[candidate]
                graph.add_edge(event.nick, original, self.weight)
