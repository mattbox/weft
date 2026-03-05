"""Tests for inference heuristics."""

from __future__ import annotations

from datetime import datetime

import pytest

from weft.graph.social_graph import SocialGraph
from weft.inference import (
    AdjacencyHeuristic,
    BinarySequenceHeuristic,
    DirectAddressingHeuristic,
    IndirectAddressingHeuristic,
)
from weft.parser.znc import ChatMessage


def _msg(nick: str, message: str) -> ChatMessage:
    return ChatMessage(
        timestamp=datetime(2025, 1, 1, 12, 0, 0), nick=nick, message=message
    )


def _graph_with(*nicks: str) -> SocialGraph:
    g = SocialGraph()
    for n in nicks:
        g.add_node(n)
    return g


# ---------------------------------------------------------------------------
# DirectAddressingHeuristic
# ---------------------------------------------------------------------------


class TestDirectAddressing:
    def test_colon_address(self):
        g = _graph_with("alice", "bob")
        h = DirectAddressingHeuristic()
        h.process(_msg("alice", "bob: hey there"), g)
        assert g.get_edge_weight("alice", "bob") > 0

    def test_comma_address(self):
        g = _graph_with("alice", "bob")
        h = DirectAddressingHeuristic()
        h.process(_msg("alice", "bob, what do you think?"), g)
        assert g.get_edge_weight("alice", "bob") > 0

    def test_no_address_when_not_at_start(self):
        g = _graph_with("alice", "bob")
        h = DirectAddressingHeuristic()
        h.process(_msg("alice", "I told bob something"), g)
        assert g.get_edge_weight("alice", "bob") == 0

    def test_no_self_address(self):
        g = _graph_with("alice")
        h = DirectAddressingHeuristic()
        h.process(_msg("alice", "alice: talking to myself"), g)
        assert g.get_edge_weight("alice", "alice") == 0

    def test_case_insensitive(self):
        g = _graph_with("alice", "Bob")
        h = DirectAddressingHeuristic()
        h.process(_msg("alice", "bob: hi"), g)
        assert g.get_edge_weight("alice", "Bob") > 0

    def test_weight_applied(self):
        g = _graph_with("alice", "bob")
        h = DirectAddressingHeuristic(weight=2.0)
        h.process(_msg("alice", "bob: hi"), g)
        assert g.get_edge_weight("alice", "bob") == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# IndirectAddressingHeuristic
# ---------------------------------------------------------------------------


class TestIndirectAddressing:
    def test_nick_in_body(self):
        g = _graph_with("alice", "bob")
        h = IndirectAddressingHeuristic()
        h.process(_msg("alice", "I think bob was right"), g)
        assert g.get_edge_weight("alice", "bob") > 0

    def test_whole_word_only(self):
        g = _graph_with("alice", "al")
        h = IndirectAddressingHeuristic()
        h.process(_msg("alice", "I like algorithms"), g)
        # "al" should NOT match inside "algorithms"
        assert g.get_edge_weight("alice", "al") == 0

    def test_case_insensitive(self):
        g = _graph_with("alice", "Bob")
        h = IndirectAddressingHeuristic()
        h.process(_msg("alice", "BOB was there"), g)
        assert g.get_edge_weight("alice", "Bob") > 0

    def test_no_self_reference(self):
        g = _graph_with("alice")
        h = IndirectAddressingHeuristic()
        h.process(_msg("alice", "alice is here"), g)
        assert g.get_edge_weight("alice", "alice") == 0

    def test_skips_direct_addressed_nick(self):
        """IndirectAddressing should not fire for a nick already caught by DirectAddressing."""
        g = _graph_with("alice", "bob")
        direct = DirectAddressingHeuristic(weight=1.0)
        indirect = IndirectAddressingHeuristic(weight=0.5, direct_heuristic=direct)
        # Direct fires first
        direct.process(_msg("alice", "bob: hey there"), g)
        indirect.process(_msg("alice", "bob: hey there"), g)
        # Should only have direct weight (1.0), not direct + indirect (1.5)
        assert g.get_edge_weight("alice", "bob") == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# AdjacencyHeuristic
# ---------------------------------------------------------------------------


class TestAdjacency:
    def test_consecutive_different_nicks(self):
        g = _graph_with("alice", "bob")
        h = AdjacencyHeuristic()
        h.process(_msg("alice", "hey"), g)
        h.process(_msg("bob", "hi"), g)
        assert g.get_edge_weight("bob", "alice") > 0

    def test_same_nick_no_edge(self):
        g = _graph_with("alice")
        h = AdjacencyHeuristic()
        h.process(_msg("alice", "a"), g)
        h.process(_msg("alice", "b"), g)
        assert g.get_edge_weight("alice", "alice") == 0

    def test_weight_accumulates(self):
        g = _graph_with("alice", "bob")
        h = AdjacencyHeuristic(weight=0.2)
        for _ in range(3):
            h.process(_msg("alice", "x"), g)
            h.process(_msg("bob", "y"), g)
        # Edge weight should be > 0.2 after multiple pairs
        assert g.get_edge_weight("alice", "bob") > 0.2


# ---------------------------------------------------------------------------
# BinarySequenceHeuristic
# ---------------------------------------------------------------------------


class TestBinarySequence:
    def test_triggers_on_two_nicks_in_window(self):
        g = _graph_with("alice", "bob")
        h = BinarySequenceHeuristic(window=5)
        for _ in range(5):
            h.process(_msg("alice" if _ % 2 == 0 else "bob", "hi"), g)
        assert g.get_edge_weight("alice", "bob") > 0

    def test_does_not_trigger_with_three_nicks(self):
        g = _graph_with("alice", "bob", "charlie")
        h = BinarySequenceHeuristic(window=5)
        msgs = ["alice", "bob", "charlie", "alice", "bob"]
        for nick in msgs:
            h.process(_msg(nick, "x"), g)
        # Three unique nicks in window — should not trigger
        assert g.get_edge_weight("alice", "bob") == 0

    def test_clears_after_trigger(self):
        g = _graph_with("alice", "bob")
        h = BinarySequenceHeuristic(window=3)
        for _ in range(3):
            h.process(_msg("alice" if _ % 2 == 0 else "bob", "x"), g)
        w1 = g.get_edge_weight("alice", "bob")
        assert w1 > 0
        # Buffer should be cleared; need 3 more messages to trigger again
        assert len(h._buffer) == 0
