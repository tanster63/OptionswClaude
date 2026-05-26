from trading_assistant.adapters.yahoo import _safe_int


def test_safe_int_handles_nan_and_none():
    assert _safe_int(None) == 0
    assert _safe_int(float("nan")) == 0
    assert _safe_int(1500) == 1500
    assert _safe_int(1500.7) == 1500
    assert _safe_int("not a number") == 0
