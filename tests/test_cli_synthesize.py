"""CLI synthesize command smoke test (with all externals mocked)."""

from __future__ import annotations

from typer.testing import CliRunner

from trading_assistant.cli import app


def test_cli_help_lists_synthesize_command():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "synthesize" in result.stdout
    assert "snapshot" in result.stdout
