"""Direct addressing heuristic.

Detects messages that start with a known nick followed by ':', ',', or whitespace.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .base import InferenceHeuristic

if TYPE_CHECKING:
    from weft.graph.social_graph import SocialGraph
    from weft.parser.znc import ChatMessage

# Match a leading word (the potential nick) followed by a separator
_RE_LEADING_NICK = re.compile(r"^(\S+?)(?:[:,]\s?|\s)")


class DirectAddressingHeuristic(InferenceHeuristic):
    """Strongest signal: sender explicitly addresses a nick at the start of the message."""

    weight: float = 1.0

    def __init__(self, weight: float = 1.0) -> None:
        self.weight = weight
        # Track which nick was matched so IndirectAddressing can skip it
        self.last_matched_nick: str | None = None

    def process(self, event: "ChatMessage", graph: "SocialGraph") -> None:
        self.last_matched_nick = None
        msg = event.message.strip()

        m = _RE_LEADING_NICK.match(msg)
        if not m:
            return

        candidate = m.group(1).lower()

        # Check if the candidate matches any known nick in the graph
        for nick in graph.nodes():
            if nick.lower() == candidate and nick.lower() != event.nick.lower():
                graph.add_edge(event.nick, nick, self.weight)
                self.last_matched_nick = nick.lower()
                return
