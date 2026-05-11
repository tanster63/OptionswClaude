from pathlib import Path

import pytest

from trading_assistant.secrets import Secrets, SecretsError, load_secrets


def write_env(tmp_path: Path, body: str) -> Path:
    p = tmp_path / ".env"
    p.write_text(body)
    return p


def test_load_secrets_returns_all_required_keys(tmp_path: Path):
    env = write_env(
        tmp_path,
        "ALPACA_API_KEY=ak\nALPACA_SECRET_KEY=sk\nFRED_API_KEY=fk\n"
        "FINNHUB_API_KEY=fnk\nANTHROPIC_API_KEY=anth\nPUSHOVER_USER_KEY=puk\n"
        "PUSHOVER_APP_TOKEN=pat\n",
    )
    s = load_secrets(env)
    assert isinstance(s, Secrets)
    assert s.alpaca_api_key == "ak"
    assert s.alpaca_secret_key == "sk"
    assert s.fred_api_key == "fk"
    assert s.finnhub_api_key == "fnk"
    assert s.anthropic_api_key == "anth"
    assert s.pushover_user_key == "puk"
    assert s.pushover_app_token == "pat"


def test_load_secrets_rejects_missing_file(tmp_path: Path):
    with pytest.raises(SecretsError, match="secrets file not found"):
        load_secrets(tmp_path / "missing.env")


def test_load_secrets_rejects_missing_keys(tmp_path: Path):
    env = write_env(tmp_path, "ALPACA_API_KEY=ak\n")
    with pytest.raises(SecretsError, match="missing required keys"):
        load_secrets(env)


def test_load_secrets_repr_redacts_values(tmp_path: Path):
    env = write_env(
        tmp_path,
        "ALPACA_API_KEY=ak\nALPACA_SECRET_KEY=sk\nFRED_API_KEY=fk\n"
        "FINNHUB_API_KEY=fnk\nANTHROPIC_API_KEY=anth\nPUSHOVER_USER_KEY=puk\n"
        "PUSHOVER_APP_TOKEN=pat\n",
    )
    s = load_secrets(env)
    text = repr(s)
    for value in ("ak", "sk", "fk", "fnk", "anth", "puk", "pat"):
        assert value not in text
    assert "REDACTED" in text
