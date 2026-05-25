"""check-holding CLI command smoke test."""

from typer.testing import CliRunner
from trading_assistant.cli import app


def test_cli_help_lists_check_holding_command():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    # Typer normalizes underscores to dashes in command names
    assert "check-holding" in result.stdout or "check_holding" in result.stdout
    # Existing commands must still be there
    assert "snapshot" in result.stdout
    assert "synthesize" in result.stdout
