"""Generate a self-contained vis.js HTML graph from a SocialGraph."""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from weft.graph.social_graph import SocialGraph

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def render_html(graph: SocialGraph, output_path: str | Path) -> None:
    """Render graph to a self-contained HTML file."""
    output_path = Path(output_path)

    graph_dict = graph.to_dict()
    nodes = graph_dict["nodes"]
    edges = graph_dict["edges"]

    # Filter out isolated nodes only when there ARE edges
    connected_nicks: set[str] = set()
    for e in edges:
        connected_nicks.add(e["source"])
        connected_nicks.add(e["target"])

    # If there are no edges at all, show all nodes
    if not edges:
        connected_nicks = {n["id"] for n in nodes}

    visible_nodes = [n for n in nodes if n["id"] in connected_nicks]

    max_weight = max((e["weight"] for e in edges), default=1.0)
    most_active = (
        max(nodes, key=lambda n: n["message_count"], default={"id": "—"})["id"]
        if nodes
        else "—"
    )

    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=False)
    template = env.get_template("graph.html.j2")

    html = template.render(
        nodes_json=json.dumps(visible_nodes),
        edges_json=json.dumps(edges),
        node_count=len(visible_nodes),
        edge_count=len(edges),
        max_weight=max_weight,
        most_active=most_active,
    )

    output_path.write_text(html, encoding="utf-8")
