"""Base class for all inference heuristics."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from weft.graph.social_graph import SocialGraph
    from weft.parser.znc import ChatMessage


class InferenceHeuristic(ABC):
    """Abstract base for relationship-inference heuristics."""

    weight: float = 1.0

    @abstractmethod
    def process(self, event: "ChatMessage", graph: "SocialGraph") -> None:
        """Inspect a chat message and update the graph accordingly."""
        ...
