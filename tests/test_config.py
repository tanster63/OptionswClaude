from pathlib import Path

import pytest

from trading_assistant.config import AppConfig, ConfigError, load_config


def write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return p


def test_load_config_returns_defaults_when_file_minimal(tmp_path: Path):
    cfg_path = write_yaml(tmp_path, "mode: paper\n")
    cfg = load_config(cfg_path)
    assert isinstance(cfg, AppConfig)
    assert cfg.mode == "paper"
    assert cfg.daily_idea_cap == 2
    assert cfg.daily_loss_cap_usd == 500.0
    assert cfg.universe == ["SPY", "QQQ", "IWM", "DIA"]
    assert cfg.max_spread_pct_of_mid == 0.05


def test_load_config_overrides_defaults(tmp_path: Path):
    cfg_path = write_yaml(
        tmp_path,
        "mode: paper\ndaily_idea_cap: 5\ndaily_loss_cap_usd: 1000\nmax_spread_pct_of_mid: 0.1\n",
    )
    cfg = load_config(cfg_path)
    assert cfg.daily_idea_cap == 5
    assert cfg.daily_loss_cap_usd == 1000.0
    assert cfg.max_spread_pct_of_mid == 0.1


def test_load_config_rejects_live_mode_in_phase_1(tmp_path: Path):
    cfg_path = write_yaml(tmp_path, "mode: live\n")
    with pytest.raises(ConfigError, match="live mode is not yet supported"):
        load_config(cfg_path)


def test_load_config_missing_file_raises(tmp_path: Path):
    with pytest.raises(ConfigError, match="config file not found"):
        load_config(tmp_path / "missing.yaml")
