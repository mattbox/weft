"""Tests for CLI orchestration."""

from __future__ import annotations

from click.testing import CliRunner

from weft.cli import cli


def test_join_events_do_not_increment_message_count(tmp_path):
    log_file = tmp_path / "2025-01-01.log"
    log_file.write_text(
        "[00:00:01] *** Joins: alice (alice@irc.example)\n"
        "[00:00:02] <alice> hello\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "out"
    result = CliRunner().invoke(cli, [str(log_file), "-o", str(output_dir)])

    assert result.exit_code == 0

    graph_data = (output_dir / "graph-data.js").read_text(encoding="utf-8")
    assert '"id": "alice", "message_count": 1' in graph_data


def test_cli_uses_config_defaults_from_working_directory(tmp_path, monkeypatch):
    log_file = tmp_path / "2025-01-01.log"
    log_file.write_text("[00:00:02] <alice> hello\n", encoding="utf-8")
    (tmp_path / "config.toml").write_text(
        """
[output]
default_path = "custom-output/"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, [str(log_file)])

    assert result.exit_code == 0
    assert (tmp_path / "custom-output" / "graph.html").exists()
    assert not (tmp_path / "build" / "graph.html").exists()
