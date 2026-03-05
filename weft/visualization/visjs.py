"""Generate a CSP-compliant vis.js HTML graph from a SocialGraph."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from weft.graph.social_graph import SocialGraph

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_VENDOR_DIR = Path(__file__).parent / "vendor"


def render_html(graph: SocialGraph, output_path: str | Path) -> None:
    """Render graph to a directory of HTML, CSS, and JS files.

    Given an output_path like 'out/weft-output.html', writes:
      out/weft-output.html
      out/graph.css
      out/graph.js
      out/graph-data.js
      out/vis-network.min.js
    """
    output_path = Path(output_path)
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

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

    # Render HTML
    html_template = env.get_template("graph.html.j2")
    html = html_template.render(
        nodes_json=json.dumps(visible_nodes),
        edges_json=json.dumps(edges),
        node_count=len(visible_nodes),
        edge_count=len(edges),
        max_weight=max_weight,
        most_active=most_active,
    )
    output_path.write_text(html, encoding="utf-8")

    # Render graph-data.js (contains the graph data)
    data_template = env.get_template("graph-data.js.j2")
    data_js = data_template.render(
        nodes_json=json.dumps(visible_nodes),
        edges_json=json.dumps(edges),
    )
    (output_dir / "graph-data.js").write_text(data_js, encoding="utf-8")

    # Copy static assets
    shutil.copy2(_TEMPLATES_DIR / "graph.css", output_dir / "graph.css")
    shutil.copy2(_TEMPLATES_DIR / "graph.js", output_dir / "graph.js")
    shutil.copy2(_VENDOR_DIR / "vis-network.min.js", output_dir / "vis-network.min.js")
