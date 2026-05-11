import json
import logging

import structlog

from trading_assistant.logging_setup import configure_logging


def test_configure_logging_emits_json_with_required_fields(capsys):
    configure_logging(level="INFO", json_output=True)
    log = structlog.get_logger("test")
    log.info("hello", count=3)
    captured = capsys.readouterr()
    record = json.loads(captured.out.strip().splitlines()[-1])
    assert record["event"] == "hello"
    assert record["count"] == 3
    assert record["level"] == "info"
    assert "timestamp" in record


def test_configure_logging_respects_level(capsys):
    configure_logging(level="WARNING", json_output=True)
    log = structlog.get_logger("test")
    log.info("debug-level should be hidden")
    log.warning("warn-level should appear")
    captured = capsys.readouterr()
    assert "debug-level" not in captured.out
    assert "warn-level" in captured.out
