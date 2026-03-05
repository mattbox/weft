"""ZNC log file parser."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Union


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


@dataclass
class ChatMessage:
    timestamp: datetime
    nick: str
    message: str


@dataclass
class ActionMessage:
    timestamp: datetime
    nick: str
    action: str


@dataclass
class JoinEvent:
    timestamp: datetime
    nick: str
    ident: str
    host: str


@dataclass
class PartEvent:
    timestamp: datetime
    nick: str
    ident: str
    host: str
    reason: str


@dataclass
class QuitEvent:
    timestamp: datetime
    nick: str
    ident: str
    host: str
    reason: str


@dataclass
class NickChangeEvent:
    timestamp: datetime
    old_nick: str
    new_nick: str


@dataclass
class ModeEvent:
    timestamp: datetime
    setter: str
    mode: str
    targets: list[str]


Event = Union[
    ChatMessage,
    ActionMessage,
    JoinEvent,
    PartEvent,
    QuitEvent,
    NickChangeEvent,
    ModeEvent,
]


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_TIME_PREFIX = r"\[(\d{2}:\d{2}:\d{2})\]"

_RE_CHAT = re.compile(rf"^{_TIME_PREFIX} <(.+?)> (.*)$")
_RE_ACTION = re.compile(rf"^{_TIME_PREFIX} \* (\S+) (.*)$")
_RE_JOIN = re.compile(rf"^{_TIME_PREFIX} \*\*\* Joins: (\S+) \((\S+?)@(\S+?)\)$")
_RE_PART = re.compile(
    rf"^{_TIME_PREFIX} \*\*\* Parts: (\S+) \((\S+?)@(\S+?)\)(?: \((.*)\))?$"
)
_RE_QUIT = re.compile(
    rf"^{_TIME_PREFIX} \*\*\* Quits: (\S+) \((\S+?)@(\S+?)\)(?: \((.*)\))?$"
)
_RE_NICK = re.compile(rf"^{_TIME_PREFIX} \*\*\* (\S+) is now known as (\S+)$")
_RE_MODE = re.compile(rf"^{_TIME_PREFIX} \*\*\* (\S+) sets mode: ([+\-]\S*)(?: (.*))?$")


def _make_dt(log_date: date, time_str: str) -> datetime:
    h, m, s = (int(x) for x in time_str.split(":"))
    return datetime(log_date.year, log_date.month, log_date.day, h, m, s)


def _parse_line(line: str, log_date: date) -> Event | None:
    line = line.rstrip("\n")

    m = _RE_CHAT.match(line)
    if m:
        return ChatMessage(
            timestamp=_make_dt(log_date, m.group(1)),
            nick=m.group(2),
            message=m.group(3),
        )

    m = _RE_ACTION.match(line)
    if m:
        return ActionMessage(
            timestamp=_make_dt(log_date, m.group(1)),
            nick=m.group(2),
            action=m.group(3),
        )

    m = _RE_JOIN.match(line)
    if m:
        return JoinEvent(
            timestamp=_make_dt(log_date, m.group(1)),
            nick=m.group(2),
            ident=m.group(3),
            host=m.group(4),
        )

    m = _RE_PART.match(line)
    if m:
        return PartEvent(
            timestamp=_make_dt(log_date, m.group(1)),
            nick=m.group(2),
            ident=m.group(3),
            host=m.group(4),
            reason=m.group(5) or "",
        )

    m = _RE_QUIT.match(line)
    if m:
        return QuitEvent(
            timestamp=_make_dt(log_date, m.group(1)),
            nick=m.group(2),
            ident=m.group(3),
            host=m.group(4),
            reason=m.group(5) or "",
        )

    m = _RE_NICK.match(line)
    if m:
        return NickChangeEvent(
            timestamp=_make_dt(log_date, m.group(1)),
            old_nick=m.group(2),
            new_nick=m.group(3),
        )

    m = _RE_MODE.match(line)
    if m:
        targets_str = m.group(4) or ""
        targets = targets_str.split() if targets_str else []
        return ModeEvent(
            timestamp=_make_dt(log_date, m.group(1)),
            setter=m.group(2),
            mode=m.group(3),
            targets=targets,
        )

    return None


def _date_from_filename(path: Path) -> date | None:
    """Extract date from a YYYY-MM-DD.log filename."""
    stem = path.stem
    try:
        return date.fromisoformat(stem)
    except ValueError:
        return None


def parse_file(path: str | Path) -> list[Event]:
    """Parse a single ZNC log file. Date is derived from the filename."""
    path = Path(path)
    log_date = _date_from_filename(path)
    if log_date is None:
        # Fall back to today if filename doesn't match
        log_date = date.today()

    events: list[Event] = []
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            event = _parse_line(line, log_date)
            if event is not None:
                events.append(event)
    return events


def parse_directory(
    path: str | Path,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[Event]:
    """Walk a directory of YYYY-MM-DD.log files in chronological order."""
    path = Path(path)
    log_files: list[tuple[date, Path]] = []

    for f in path.iterdir():
        if f.suffix != ".log":
            continue
        d = _date_from_filename(f)
        if d is None:
            continue
        if from_date is not None and d < from_date:
            continue
        if to_date is not None and d > to_date:
            continue
        log_files.append((d, f))

    log_files.sort(key=lambda t: t[0])

    events: list[Event] = []
    for _, f in log_files:
        events.extend(parse_file(f))
    return events
