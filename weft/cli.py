"""Command-line interface for weft."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import click

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


@click.group()
def cli() -> None:
    """weft — IRC social network visualizer."""


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    default="weft-output.html",
    show_default=True,
    help="Output HTML file.",
)
@click.option(
    "--from", "from_date", default=None, help="Start date filter (YYYY-MM-DD)."
)
@click.option("--to", "to_date", default=None, help="End date filter (YYYY-MM-DD).")
@click.option(
    "--ignore",
    "ignore_nicks",
    multiple=True,
    help="Ignore a nick (repeatable, case-insensitive).",
)
@click.option(
    "--ai", "ai_enabled", is_flag=True, default=False, help="Enable AI heuristic."
)
@click.option(
    "--ai-model",
    default="ollama/llama3.2",
    show_default=True,
    help="litellm model string.",
)
@click.option(
    "--save-state",
    "save_state",
    default=None,
    type=click.Path(),
    help="Save graph state to JSON.",
)
@click.option(
    "--load-state",
    "load_state",
    default=None,
    type=click.Path(exists=True),
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
def process(
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
    """Process a ZNC log file or directory and output an HTML graph.

    PATH may be a single .log file or a directory containing YYYY-MM-DD.log files.
    """
    p = Path(path)

    # Parse date filters
    fd: date | None = None
    td: date | None = None
    if from_date:
        try:
            fd = date.fromisoformat(from_date)
        except ValueError:
            click.echo(
                f"Error: invalid --from date '{from_date}'. Use YYYY-MM-DD.", err=True
            )
            sys.exit(1)
    if to_date:
        try:
            td = date.fromisoformat(to_date)
        except ValueError:
            click.echo(
                f"Error: invalid --to date '{to_date}'. Use YYYY-MM-DD.", err=True
            )
            sys.exit(1)

    # Normalise ignore set
    ignored: set[str] = {n.lower() for n in ignore_nicks}
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
    direct_h = DirectAddressingHeuristic(weight=1.0)
    indirect_h = IndirectAddressingHeuristic(weight=0.5, direct_heuristic=direct_h)
    heuristics = [
        direct_h,
        indirect_h,
        AdjacencyHeuristic(weight=0.2),
        BinarySequenceHeuristic(weight=0.8, window=5),
    ]
    if ai_enabled:
        heuristics.append(AIHeuristic(weight=0.7, model=ai_model))
        click.echo(f"[weft] AI heuristic enabled (model: {ai_model})")

    # Process events
    decay_counter = 0
    decay_every = 50  # apply decay every N chat messages
    total = len(events)

    with click.progressbar(events, label="[weft] Processing", length=total) as bar:
        for event in bar:
            if isinstance(event, JoinEvent):
                if event.nick.lower() not in ignored:
                    graph.add_node(event.nick)

            elif isinstance(event, NickChangeEvent):
                if (
                    event.old_nick.lower() not in ignored
                    and event.new_nick.lower() not in ignored
                ):
                    graph.merge_nick(event.old_nick, event.new_nick)

            elif isinstance(event, (QuitEvent,)):
                pass  # No special handling needed for quits

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

    # Render HTML
    render_html(graph, output)
    click.echo(f"[weft] Output written to: {output}")
