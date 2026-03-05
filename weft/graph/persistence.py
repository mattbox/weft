"""Graph state persistence — save/load as JSON."""

from __future__ import annotations

import json
from pathlib import Path

from .social_graph import SocialGraph


def save_graph(graph: SocialGraph, path: str | Path) -> None:
    """Serialise graph state to JSON."""
    path = Path(path)
    data = graph.to_dict()
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_graph(path: str | Path) -> SocialGraph:
    """Load graph state from JSON."""
    path = Path(path)
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return SocialGraph.from_dict(data)
