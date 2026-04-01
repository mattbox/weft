# weft

**weft** is an IRC social network visualizer based on [Piespy](https://github.com/mchelen/piespy) model of using heuristic analysis to infer relationships between pairs of users.

It reads ZNC log files and generates an interactive HTML graph showing the relationships between IRC users — built on [vis.js](https://visjs.org/).

## Example

See a [live example](https://mattbox.github.io/weft/).

## Features

- Parses ZNC `.log` files (`YYYY-MM-DD.log` format)
- Multiple relationship-inference heuristics (direct addressing, indirect mention, adjacency, binary sequence conversations)
- Optional AI heuristic powered by [litellm](https://docs.litellm.ai/)
- Interactive vis.js graph: node size by message count, edge weight by relationship strength
- Edge weight threshold slider and physics controls
- Graph state persistence (save/load JSON)
- Temporal decay: relationships fade over time unless reinforced

## Installation

Requires [uv](https://docs.astral.sh/uv/) and Python >= 3.11.

```bash
uv sync
# or, with AI heuristic support:
uv sync --extra ai
```

## Quick Start

```bash
# Process a single log file
uv run weft 2025-10-05.log

# Process a directory of logs, output to custom file
uv run weft /var/log/znc/channel/ -o graph.html

# Filter by date range
uv run weft /var/log/znc/channel/ --from 2025-09-01 --to 2025-10-01

# Ignore bots and service nicks
uv run weft 2025-10-05.log --ignore NickServ --ignore helpfulbot

# Enable AI-assisted heuristic
uv run weft 2025-10-05.log --ai --ai-model ollama/llama3.2

# Save and reload graph state across runs
uv run weft day1.log --save-state state.json
uv run weft day2.log --load-state state.json --save-state state.json
```

## Configuration

Runtime defaults are loaded from `config.toml` in the current working directory.
CLI flags override config values when passed explicitly.

## CLI Reference

```
weft <path> [OPTIONS]

Arguments:
  PATH    ZNC log file or directory of YYYY-MM-DD.log files

Options:
  -o, --output PATH          Output HTML file or directory [default: build/]
  --from DATE                Start date filter (YYYY-MM-DD)
  --to DATE                  End date filter (YYYY-MM-DD)
  --ignore NICK              Ignore a nick (repeatable, case-insensitive)
  --ai                       Enable AI heuristic
  --ai-model MODEL           litellm model string [default: ollama/llama3.2]
  --save-state FILE          Save graph state to JSON after processing
  --load-state FILE          Load existing graph state before processing
  --decay-amount FLOAT       Temporal decay per batch [default: 0.02]
  --no-decay                 Disable temporal decay entirely
```

## Inference Heuristics

| Heuristic | Weight | Description |
|-----------|--------|-------------|
| Direct addressing | 1.0 | Message starts with `nick:` or `nick,` |
| Indirect addressing | 0.5 | Nick mentioned anywhere in the message |
| Adjacency | 0.2 | Consecutive speakers (A then B) |
| Binary sequence | 0.8 | Only 2 unique speakers in a 5-message window |
| AI (optional) | 0.7 | LLM determines who the speaker is addressing |

## Log Format

ZNC logs must follow this format (filename = `YYYY-MM-DD.log`):

```
[HH:MM:SS] <nick> message text here
[HH:MM:SS] *** Joins: nick (ident@host)
[HH:MM:SS] *** Parts: nick (ident@host) (reason)
[HH:MM:SS] *** Quits: nick (ident@host) (reason)
[HH:MM:SS] *** nick is now known as newnick
[HH:MM:SS] *** ChanServ sets mode: +qo nick nick
[HH:MM:SS] * nick does an action
```

## Running Tests

```bash
uv run pytest
```

## Project Structure

```
weft/
├── weft/
│   ├── cli.py               # Click CLI entry point
│   ├── parser/znc.py        # ZNC log parser
│   ├── inference/           # Relationship heuristics
│   ├── graph/               # NetworkX-backed social graph + persistence
│   └── visualization/       # vis.js HTML renderer
└── tests/
```
