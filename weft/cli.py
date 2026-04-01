"""Command-line interface for weft."""

from __future__ import annotations

import sys
import tomllib
from datetime import date
from pathlib import Path

import click
from click.core import ParameterSource

from weft.graph.persistence import load_graph, save_graph
from weft.graph.social_graph import SocialGraph
from weft.inference import (
    AdjacencyHeuristic,
    AIHeuristic,
    BinarySequenceHeuristic,
    DirectAddressingHeuristic,
    IndirectAddressingHeuristic,
)
from weft.parser.znc import (
    ActionMessage,
    ChatMessage,
    JoinEvent,
    NickChangeEvent,
    QuitEvent,
    parse_directory,
    parse_file,
)
from weft.visualization.visjs import render_html

DEFAULT_CONFIG = {
    "inference": {
        "direct_addressing_weight": 1.0,
        "indirect_addressing_weight": 0.5,
        "adjacency_weight": 0.2,
        "binary_sequence_weight": 0.8,
        "binary_sequence_window": 5,
        "ai_weight": 0.7,
        "ai_enabled": False,
        "ai_model": "ollama/llama3.2",
    },
    "decay": {
        "enabled": True,
        "amount": 0.02,
    },
    "graph": {
        "ignore_nicks": ["chanserv", "nickserv"],
    },
    "output": {
        "default_path": "build/",
    },
}


def _load_project_config(path: str | Path = "config.toml") -> dict:
    """Load config.toml from the current working directory if it exists."""
    config = {
        section: values.copy()
        for section, values in DEFAULT_CONFIG.items()
    }
    config_path = Path(path)
    if not config_path.exists():
        return config

    with config_path.open("rb") as f:
        loaded = tomllib.load(f)

    for section, defaults in config.items():
        section_values = loaded.get(section, {})
        if isinstance(section_values, dict):
            defaults.update(section_values)
    return config


@click.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    default="build/",
    show_default=True,
    metavar="PATH",
    help="Output HTML file or directory.",
)
@click.option(
    "--from",
    "from_date",
    default=None,
    metavar="DATE",
    help="Start date filter (YYYY-MM-DD).",
)
@click.option(
    "--to",
    "to_date",
    default=None,
    metavar="DATE",
    help="End date filter (YYYY-MM-DD).",
)
@click.option(
    "--ignore",
    "ignore_nicks",
    multiple=True,
    metavar="NICK",
    help="Ignore a nick (repeatable, case-insensitive).",
)
@click.option(
    "--ai", "ai_enabled", is_flag=True, default=False, help="Enable AI heuristic."
)
@click.option(
    "--ai-model",
    default="ollama/llama3.2",
    show_default=True,
    metavar="MODEL",
    help="litellm model string.",
)
@click.option(
    "--save-state",
    "save_state",
    default=None,
    type=click.Path(),
    metavar="FILE",
    help="Save graph state to JSON.",
)
@click.option(
    "--load-state",
    "load_state",
    default=None,
    type=click.Path(exists=True),
    metavar="FILE",
    help="Load existing graph state.",
)
@click.option(
    "--decay-amount",
    default=0.02,
    show_default=True,
    type=float,
    help="Temporal decay per message batch.",
)
@click.option(
    "--no-decay", is_flag=True, default=False, help="Disable temporal decay entirely."
)
@click.pass_context
def cli(
    ctx: click.Context,
    path: str,
    output: str,
    from_date: str | None,
    to_date: str | None,
    ignore_nicks: tuple[str, ...],
    ai_enabled: bool,
    ai_model: str,
    save_state: str | None,
    load_state: str | None,
    decay_amount: float,
    no_decay: bool,
) -> None:
    """
    PATH    may be a single .log file or a directory containing YYYY-MM-DD.log files.
    """
    p = Path(path)
    config = _load_project_config()

    def _parse_date(value: str | None, flag: str) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            click.echo(
                f"Error: invalid {flag} date '{value}'. Use YYYY-MM-DD.", err=True
            )
            sys.exit(1)

    fd = _parse_date(from_date, "--from")
    td = _parse_date(to_date, "--to")

    if ctx.get_parameter_source("output") is ParameterSource.DEFAULT:
        output = config["output"]["default_path"]
    if ctx.get_parameter_source("ai_enabled") is ParameterSource.DEFAULT:
        ai_enabled = config["inference"]["ai_enabled"]
    if ctx.get_parameter_source("ai_model") is ParameterSource.DEFAULT:
        ai_model = config["inference"]["ai_model"]
    if ctx.get_parameter_source("decay_amount") is ParameterSource.DEFAULT:
        decay_amount = config["decay"]["amount"]
    if ctx.get_parameter_source("no_decay") is ParameterSource.DEFAULT:
        no_decay = not config["decay"]["enabled"]

    # Normalise ignore set
    ignored: set[str] = {n.lower() for n in config["graph"]["ignore_nicks"]}
    ignored.update(n.lower() for n in ignore_nicks)
    # Always ignore these service bots
    ignored.update({"chanserv", "nickserv"})

    click.echo(f"[weft] Reading logs from: {p}")

    # Load events
    if p.is_dir():
        events = parse_directory(p, from_date=fd, to_date=td)
    else:
        events = parse_file(p)

    click.echo(f"[weft] Parsed {len(events)} events.")

    # Set up graph
    if load_state:
        click.echo(f"[weft] Loading existing graph state from {load_state}")
        graph = load_graph(load_state)
    else:
        graph = SocialGraph()

    # Set up heuristics — wire direct into indirect so it can skip already-matched nicks
    direct_h = DirectAddressingHeuristic(
        weight=config["inference"]["direct_addressing_weight"]
    )
    indirect_h = IndirectAddressingHeuristic(
        weight=config["inference"]["indirect_addressing_weight"],
        direct_heuristic=direct_h,
    )
    heuristics = [
        direct_h,
        indirect_h,
        AdjacencyHeuristic(weight=config["inference"]["adjacency_weight"]),
        BinarySequenceHeuristic(
            weight=config["inference"]["binary_sequence_weight"],
            window=config["inference"]["binary_sequence_window"],
        ),
    ]
    if ai_enabled:
        heuristics.append(
            AIHeuristic(
                weight=config["inference"]["ai_weight"],
                model=ai_model,
            )
        )
        click.echo(f"[weft] AI heuristic enabled (model: {ai_model})")

    # Process events
    decay_counter = 0
    decay_every = 50  # apply decay every N chat messages
    total = len(events)

    with click.progressbar(events, label="[weft] Processing", length=total) as bar:
        for event in bar:
            if isinstance(event, JoinEvent):
                if event.nick.lower() not in ignored:
                    graph.ensure_node(event.nick)

            elif isinstance(event, NickChangeEvent):
                if (
                    event.old_nick.lower() not in ignored
                    and event.new_nick.lower() not in ignored
                ):
                    graph.merge_nick(event.old_nick, event.new_nick)

            elif isinstance(event, QuitEvent):
                pass

            elif isinstance(event, (ChatMessage, ActionMessage)):
                if event.nick.lower() in ignored:
                    continue

                graph.add_node(event.nick)

                # Convert ActionMessage to a ChatMessage-compatible object for heuristics
                if isinstance(event, ActionMessage):
                    chat_event = ChatMessage(
                        timestamp=event.timestamp,
                        nick=event.nick,
                        message=event.action,
                    )
                else:
                    chat_event = event

                for h in heuristics:
                    h.process(chat_event, graph)

                if not no_decay:
                    decay_counter += 1
                    if decay_counter >= decay_every:
                        graph.decay(decay_amount)
                        decay_counter = 0

    node_count = len(graph.nodes())
    edge_count = len(graph.edges())
    click.echo(f"[weft] Graph built: {node_count} nodes, {edge_count} edges.")

    # Save state if requested
    if save_state:
        save_graph(graph, save_state)
        click.echo(f"[weft] Graph state saved to {save_state}")

    # Render HTML — if output is a directory, place graph.html inside it
    out = Path(output)
    if out.is_dir() or output.endswith("/") or not out.suffix:
        out = out / "graph.html"
    render_html(graph, out)
    click.echo(f"[weft] Output written to: {out}")
