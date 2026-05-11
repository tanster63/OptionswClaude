from typer.testing import CliRunner

from trading_assistant.cli import app


def test_help_lists_snapshot_command():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "snapshot" in result.stdout


def test_snapshot_requires_config_path():
    runner = CliRunner()
    result = runner.invoke(app, ["snapshot"])
    assert result.exit_code != 0
