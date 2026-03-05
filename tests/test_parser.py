"""Tests for the ZNC log parser."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from weft.parser.znc import (
    ActionMessage,
    ChatMessage,
    JoinEvent,
    NickChangeEvent,
    PartEvent,
    QuitEvent,
    parse_file,
)

FIXTURE = Path(__file__).parent / "fixtures" / "2025-10-05.log"


@pytest.fixture(scope="module")
def events():
    return parse_file(FIXTURE)


# ---------------------------------------------------------------------------
# Basic parsing
# ---------------------------------------------------------------------------


def test_parse_returns_events(events):
    assert len(events) > 0


def test_chat_messages_parsed(events):
    chats = [e for e in events if isinstance(e, ChatMessage)]
    assert len(chats) > 0


def test_chat_message_fields(events):
    chats = [e for e in events if isinstance(e, ChatMessage)]
    first = chats[0]
    # From the log: [00:00:02] <glitch> neonwave: no it wasn't
    assert first.nick == "glitch"
    assert "neonwave" in first.message
    assert isinstance(first.timestamp, datetime)
    assert first.timestamp.year == 2025
    assert first.timestamp.month == 10
    assert first.timestamp.day == 5
    assert first.timestamp.hour == 0
    assert first.timestamp.minute == 0
    assert first.timestamp.second == 2


def test_chat_message_date_from_filename(events):
    """All events should carry the date from the filename (2025-10-05)."""
    for e in events:
        assert e.timestamp.year == 2025
        assert e.timestamp.month == 10
        assert e.timestamp.day == 5


def test_join_event_parsed(events):
    joins = [e for e in events if isinstance(e, JoinEvent)]
    assert len(joins) > 0
    join = joins[0]
    assert join.nick == "ember"
    assert join.ident == "ember_x"
    assert "example.net" in join.host
    assert isinstance(join.timestamp, datetime)


def test_part_event_parsed(events):
    parts = [e for e in events if isinstance(e, PartEvent)]
    assert len(parts) > 0
    part = parts[0]
    assert part.nick == "ember"
    assert part.reason == "Leaving"


def test_nick_change_parsed(events):
    nicks = [e for e in events if isinstance(e, NickChangeEvent)]
    assert len(nicks) > 0
    change = nicks[0]
    assert change.old_nick == "drift3"
    assert change.new_nick == "drift"


def test_quit_event_parsed(events):
    quits = [e for e in events if isinstance(e, QuitEvent)]
    assert len(quits) > 0
    quit_ev = quits[0]
    assert quit_ev.nick == "ratchet"


def test_action_message_parsed(events):
    actions = [e for e in events if isinstance(e, ActionMessage)]
    assert len(actions) > 0
    action = actions[0]
    assert action.nick == "starfall"
    assert "changelog" in action.action


def test_multiple_nicks_in_log(events):
    chats = [e for e in events if isinstance(e, ChatMessage)]
    nicks = {e.nick for e in chats}
    assert "glitch" in nicks
    assert "neonwave" in nicks
    assert "hexdump" in nicks
    assert "starfall" in nicks
    assert "cipher" in nicks
    assert "vortex" in nicks


def test_unparseable_lines_skipped(tmp_path):
    """Lines that don't match any pattern should be silently skipped."""
    log = tmp_path / "2025-01-01.log"
    log.write_text(
        "[00:01:00] <alice> hello bob\n"
        "this line is garbage\n"
        "[00:02:00] <bob> hey alice\n",
        encoding="utf-8",
    )
    events = parse_file(log)
    assert len(events) == 2
    assert all(isinstance(e, ChatMessage) for e in events)


def test_parse_directory(tmp_path):
    """parse_directory should walk files in chronological order."""
    (tmp_path / "2025-01-01.log").write_text(
        "[00:00:01] <alice> first\n", encoding="utf-8"
    )
    (tmp_path / "2025-01-02.log").write_text(
        "[00:00:01] <bob> second\n", encoding="utf-8"
    )
    (tmp_path / "2025-01-03.log").write_text(
        "[00:00:01] <charlie> third\n", encoding="utf-8"
    )

    from weft.parser.znc import parse_directory

    events = parse_directory(tmp_path)
    assert len(events) == 3
    nicks = [e.nick for e in events]
    assert nicks == ["alice", "bob", "charlie"]


def test_parse_directory_date_filter(tmp_path):
    from datetime import date
    from weft.parser.znc import parse_directory

    (tmp_path / "2025-01-01.log").write_text(
        "[00:00:01] <alice> jan1\n", encoding="utf-8"
    )
    (tmp_path / "2025-01-02.log").write_text(
        "[00:00:01] <bob> jan2\n", encoding="utf-8"
    )
    (tmp_path / "2025-01-03.log").write_text(
        "[00:00:01] <charlie> jan3\n", encoding="utf-8"
    )

    events = parse_directory(
        tmp_path, from_date=date(2025, 1, 2), to_date=date(2025, 1, 2)
    )
    assert len(events) == 1
    assert events[0].nick == "bob"
