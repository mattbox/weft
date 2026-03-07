"""Tests for SocialGraph operations."""

from __future__ import annotations

import json
import pytest

from weft.graph.persistence import load_graph, save_graph
from weft.graph.social_graph import SocialGraph


# ---------------------------------------------------------------------------
# add_node / add_edge basics
# ---------------------------------------------------------------------------


class TestAddNode:
    def test_add_node_creates_node(self):
        g = SocialGraph()
        g.add_node("alice")
        assert g.contains("alice")

    def test_add_node_increments_count(self):
        g = SocialGraph()
        g.add_node("alice")
        g.add_node("alice")
        assert g.get_message_count("alice") == 2

    def test_message_count_zero_by_default(self):
        g = SocialGraph()
        assert g.get_message_count("nobody") == 0


class TestAddEdge:
    def test_edge_created(self):
        g = SocialGraph()
        g.add_edge("alice", "bob", 1.0)
        assert g.get_edge_weight("alice", "bob") > 0

    def test_edge_is_bidirectional(self):
        g = SocialGraph()
        g.add_edge("alice", "bob", 1.0)
        assert g.get_edge_weight("bob", "alice") > 0

    def test_edge_weight_accumulates(self):
        g = SocialGraph()
        g.add_edge("alice", "bob", 1.0)
        g.add_edge("alice", "bob", 0.5)
        assert g.get_edge_weight("alice", "bob") == pytest.approx(1.5)

    def test_edge_creates_nodes_if_absent(self):
        g = SocialGraph()
        g.add_edge("alice", "charlie", 1.0)
        assert g.contains("alice")
        assert g.contains("charlie")

    def test_missing_edge_returns_zero(self):
        g = SocialGraph()
        g.add_node("alice")
        assert g.get_edge_weight("alice", "nobody") == 0.0


# ---------------------------------------------------------------------------
# Decay
# ---------------------------------------------------------------------------


class TestDecay:
    def test_decay_reduces_weight(self):
        g = SocialGraph()
        g.add_edge("alice", "bob", 1.0)
        before = g.get_edge_weight("alice", "bob")
        g.decay(0.1)
        after = g.get_edge_weight("alice", "bob")
        assert after < before

    def test_decay_removes_zero_edges(self):
        g = SocialGraph()
        g.add_edge("alice", "bob", 0.05)
        g.decay(0.1)  # Should drop edge weight to <= 0
        assert g.get_edge_weight("alice", "bob") == 0.0

    def test_decay_keeps_strong_edges(self):
        g = SocialGraph()
        g.add_edge("alice", "bob", 100.0)
        g.decay(0.1)
        assert g.get_edge_weight("alice", "bob") > 0


# ---------------------------------------------------------------------------
# merge_nick
# ---------------------------------------------------------------------------


class TestMergeNick:
    def test_merge_transfers_edges(self):
        g = SocialGraph()
        g.add_edge("oldnick", "charlie", 2.0)
        g.merge_nick("oldnick", "newnick")
        assert g.contains("newnick")
        assert not g.contains("oldnick")
        assert g.get_edge_weight("newnick", "charlie") > 0

    def test_merge_accumulates_message_count(self):
        g = SocialGraph()
        g.add_node("oldnick")
        g.add_node("oldnick")  # count = 2
        g.add_node("newnick")  # count = 1
        g.merge_nick("oldnick", "newnick")
        assert g.get_message_count("newnick") == 3

    def test_merge_nonexistent_old_nick(self):
        """merge_nick should not raise when old_nick doesn't exist."""
        g = SocialGraph()
        g.add_node("newnick")
        g.merge_nick("ghost", "newnick")  # Should not raise
        assert g.contains("newnick")

    def test_merge_creates_new_nick_if_absent(self):
        g = SocialGraph()
        g.add_node("oldnick")
        g.merge_nick("oldnick", "newnick")
        assert g.contains("newnick")
        assert not g.contains("oldnick")

    def test_merge_tracks_aliases(self):
        g = SocialGraph()
        g.add_node("alice")
        g.add_node("alice_away")
        g.merge_nick("alice_away", "alice")
        aliases = g.get_aliases("alice")
        assert "alice" in aliases
        assert "alice_away" in aliases

    def test_merge_primary_nick_is_most_active(self):
        g = SocialGraph()
        for _ in range(5):
            g.add_node("alice")
        g.add_node("alice_away")
        g.merge_nick("alice_away", "alice")
        assert g.get_primary_nick("alice") == "alice"

    def test_merge_chain_preserves_all_aliases(self):
        g = SocialGraph()
        g.add_node("alice")
        g.add_node("alice_away")
        g.add_node("alice_mobile")
        g.merge_nick("alice", "alice_away")
        g.merge_nick("alice_away", "alice_mobile")
        aliases = g.get_aliases("alice_mobile")
        assert "alice" in aliases
        assert "alice_away" in aliases
        assert "alice_mobile" in aliases


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_save_load_roundtrip(self, tmp_path):
        g = SocialGraph()
        g.add_node("alice")
        g.add_node("alice")  # msg count = 2
        g.add_edge("alice", "bob", 1.5)

        p = tmp_path / "graph.json"
        save_graph(g, p)
        g2 = load_graph(p)

        assert g2.contains("alice")
        assert g2.contains("bob")
        assert g2.get_message_count("alice") == 2
        assert g2.get_edge_weight("alice", "bob") > 0

    def test_save_produces_valid_json(self, tmp_path):
        g = SocialGraph()
        g.add_edge("alice", "bob", 1.0)
        p = tmp_path / "graph.json"
        save_graph(g, p)
        data = json.loads(p.read_text())
        assert "nodes" in data
        assert "edges" in data

    def test_to_dict_deduplicates_edges(self):
        g = SocialGraph()
        g.add_edge("alice", "bob", 1.0)
        d = g.to_dict()
        edge_keys = [(e["source"], e["target"]) for e in d["edges"]]
        # Both directions should not both appear
        assert len(edge_keys) == 1

    def test_aliases_persist_roundtrip(self, tmp_path):
        g = SocialGraph()
        for _ in range(3):
            g.add_node("alice")
        g.add_node("alice_away")
        g.merge_nick("alice_away", "alice")

        p = tmp_path / "graph.json"
        save_graph(g, p)
        g2 = load_graph(p)

        aliases = g2.get_aliases("alice")
        assert "alice" in aliases
        assert "alice_away" in aliases
        assert aliases["alice"] == 3

    def test_load_legacy_json_without_aliases(self, tmp_path):
        """Old JSON without aliases should get backward-compat default."""
        legacy = {
            "nodes": [{"id": "alice", "message_count": 5}],
            "edges": [],
        }
        p = tmp_path / "legacy.json"
        p.write_text(json.dumps(legacy))
        g = load_graph(p)
        aliases = g.get_aliases("alice")
        assert aliases == {"alice": 5}
