"""AI heuristic (optional).

Uses litellm to determine which nick the current speaker is most likely addressing.
Disabled by default. Degrades gracefully if litellm is not installed.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from .base import InferenceHeuristic

if TYPE_CHECKING:
    from weft.graph.social_graph import SocialGraph
    from weft.parser.znc import ChatMessage

_LITELLM_AVAILABLE = False
try:
    import litellm  # noqa: F401

    _LITELLM_AVAILABLE = True
except ImportError:
    pass


_PROMPT_TEMPLATE = """\
You are analyzing IRC chat logs. Given the following recent messages, determine which IRC nick the LAST speaker is most likely addressing. If they are not clearly addressing anyone, reply with "none". Reply with ONLY the nick name or "none" — no explanation.

Recent messages:
{context}

Who is the last speaker addressing?"""


class AIHeuristic(InferenceHeuristic):
    """Optional AI-powered heuristic using litellm."""

    weight: float = 0.7

    def __init__(
        self, weight: float = 0.7, model: str = "ollama/llama3.2", context_size: int = 5
    ) -> None:
        self.weight = weight
        self.model = model
        self.context_size = context_size
        self._context: deque[str] = deque(maxlen=context_size)
        self._enabled = _LITELLM_AVAILABLE

    def process(self, event: "ChatMessage", graph: "SocialGraph") -> None:
        if not self._enabled:
            return

        self._context.append(f"<{event.nick}> {event.message}")

        if len(self._context) < 2:
            return

        context_text = "\n".join(self._context)
        prompt = _PROMPT_TEMPLATE.format(context=context_text)

        try:
            import litellm

            response = litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=20,
                temperature=0.0,
            )
            reply = response.choices[0].message.content.strip()

            if reply.lower() == "none" or not reply:
                return

            # Find a matching nick in the graph (case-insensitive)
            for nick in graph.nodes():
                if nick.lower() == reply.lower() and nick.lower() != event.nick.lower():
                    graph.add_edge(event.nick, nick, self.weight)
                    break
        except Exception:
            # Degrade gracefully on any error (network, model not available, etc.)
            pass
