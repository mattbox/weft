"""Social graph wrapping NetworkX Graph (undirected)."""

from __future__ import annotations

import networkx as nx


class SocialGraph:
    """Undirected weighted graph tracking IRC user relationships."""

    def __init__(self) -> None:
        self._g: nx.Graph = nx.Graph()

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    def add_node(self, nick: str) -> None:
        """Add a node (or increment its message count if already present)."""
        if self._g.has_node(nick):
            self._g.nodes[nick]["message_count"] = (
                self._g.nodes[nick].get("message_count", 0) + 1
            )
        else:
            self._g.add_node(nick, message_count=1)

    def contains(self, nick: str) -> bool:
        return self._g.has_node(nick)

    def nodes(self) -> list[str]:
        return list(self._g.nodes())

    def get_message_count(self, nick: str) -> int:
        if not self._g.has_node(nick):
            return 0
        return self._g.nodes[nick].get("message_count", 0)

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    def add_edge(self, source: str, target: str, weight: float) -> None:
        """Add weight to an edge (creates nodes and edge if needed).

        Since the graph is undirected, add_edge("a", "b", w) and
        add_edge("b", "a", w) affect the same edge.
        """
        if not self._g.has_node(source):
            self._g.add_node(source, message_count=0)
        if not self._g.has_node(target):
            self._g.add_node(target, message_count=0)

        if self._g.has_edge(source, target):
            self._g[source][target]["weight"] += weight
        else:
            self._g.add_edge(source, target, weight=weight)

    def get_edge_weight(self, source: str, target: str) -> float:
        if self._g.has_edge(source, target):
            return self._g[source][target]["weight"]
        return 0.0

    def edges(self) -> list[tuple[str, str, float]]:
        """Return list of (source, target, weight) for all edges."""
        return [(u, v, d["weight"]) for u, v, d in self._g.edges(data=True)]

    # ------------------------------------------------------------------
    # Decay
    # ------------------------------------------------------------------

    def decay(self, amount: float) -> None:
        """Subtract amount from all edge weights; remove edges at or below 0."""
        to_remove = []
        for u, v, data in self._g.edges(data=True):
            data["weight"] -= amount
            if data["weight"] <= 0:
                to_remove.append((u, v))
        self._g.remove_edges_from(to_remove)

    # ------------------------------------------------------------------
    # Nick merging
    # ------------------------------------------------------------------

    def merge_nick(self, old_nick: str, new_nick: str) -> None:
        """Handle a nick change by merging old_nick into new_nick."""
        if not self._g.has_node(old_nick):
            return

        old_data = self._g.nodes[old_nick]
        old_msg_count = old_data.get("message_count", 0)

        if not self._g.has_node(new_nick):
            self._g.add_node(new_nick, message_count=0)

        # Accumulate message count
        self._g.nodes[new_nick]["message_count"] = (
            self._g.nodes[new_nick].get("message_count", 0) + old_msg_count
        )

        # Redirect all edges from old_nick to new_nick
        for neighbor in list(self._g.neighbors(old_nick)):
            if neighbor == old_nick or neighbor == new_nick:
                continue
            w = self._g[old_nick][neighbor]["weight"]
            # add_edge handles accumulation if new_nick already has an edge to neighbor
            self.add_edge(new_nick, neighbor, w)

        self._g.remove_node(old_nick)

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        nodes = [
            {"id": n, "message_count": self._g.nodes[n].get("message_count", 0)}
            for n in self._g.nodes()
        ]
        edges = [
            {"source": u, "target": v, "weight": d["weight"]}
            for u, v, d in self._g.edges(data=True)
        ]
        return {"nodes": nodes, "edges": edges}

    @classmethod
    def from_dict(cls, data: dict) -> "SocialGraph":
        g = cls()
        for node in data.get("nodes", []):
            g._g.add_node(node["id"], message_count=node.get("message_count", 0))
        for edge in data.get("edges", []):
            src, tgt, w = edge["source"], edge["target"], edge["weight"]
            g._g.add_edge(src, tgt, weight=w)
        return g
