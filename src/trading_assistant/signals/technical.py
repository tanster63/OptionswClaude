"""Technical signal generator: SMA cross, RSI, breakout."""

from __future__ import annotations

import datetime as dt
import hashlib
from statistics import fmean

from trading_assistant.ingest.bars import Bar, BarSource
from trading_assistant.signals.model import Signal, SignalKind

_LOOKBACK_DAYS = 60  # enough for 50-day SMA + 14-day RSI + breakout buffer

# Minimum fractional move beyond the 20-day extreme to count as a breakout.
# Filters out noise like a 0.07% drift on otherwise-flat data.
_BREAKOUT_MARGIN = 0.005  # 0.5%


class TechnicalSignalGen:
    name = "technical"

    def __init__(self, bar_source: BarSource, universe: list[str]) -> None:
        self._bars = bar_source
        self._universe = [u.upper() for u in universe]

    def generate(self, now: dt.datetime) -> list[Signal]:
        out: list[Signal] = []
        start = (now - dt.timedelta(days=_LOOKBACK_DAYS * 2)).date()
        end = now.date()
        for symbol in self._universe:
            bars = self._bars.daily_bars(symbol, start, end)
            if len(bars) < 21:
                continue
            closes = [b.close for b in bars]
            out.extend(self._breakout(symbol, closes, now))
            out.extend(self._sma_cross(symbol, closes, now))
            out.extend(self._rsi(symbol, closes, now))
        return out

    def _breakout(self, symbol: str, closes: list[float], now: dt.datetime) -> list[Signal]:
        window = closes[-21:-1]  # last 20 closes excluding today
        today_close = closes[-1]
        hi = max(window)
        lo = min(window)
        if today_close > hi * (1.0 + _BREAKOUT_MARGIN):
            return [self._sig(symbol, SignalKind.TECHNICAL_BREAKOUT, 0.7, now,
                               {"direction": "up", "close": today_close, "20d_high": hi})]
        if today_close < lo * (1.0 - _BREAKOUT_MARGIN):
            return [self._sig(symbol, SignalKind.TECHNICAL_BREAKOUT, 0.7, now,
                               {"direction": "down", "close": today_close, "20d_low": lo})]
        return []

    def _sma_cross(self, symbol: str, closes: list[float], now: dt.datetime) -> list[Signal]:
        if len(closes) < 51:
            return []
        sma20_today = fmean(closes[-20:])
        sma50_today = fmean(closes[-50:])
        sma20_yest = fmean(closes[-21:-1])
        sma50_yest = fmean(closes[-51:-1])
        crossed_up = sma20_yest <= sma50_yest and sma20_today > sma50_today
        crossed_dn = sma20_yest >= sma50_yest and sma20_today < sma50_today
        if crossed_up:
            return [self._sig(symbol, SignalKind.TECHNICAL_BREAKOUT, 0.6, now,
                               {"direction": "up", "indicator": "sma20_over_sma50"})]
        if crossed_dn:
            return [self._sig(symbol, SignalKind.TECHNICAL_BREAKOUT, 0.6, now,
                               {"direction": "down", "indicator": "sma20_under_sma50"})]
        return []

    def _rsi(self, symbol: str, closes: list[float], now: dt.datetime) -> list[Signal]:
        if len(closes) < 15:
            return []
        deltas = [closes[i] - closes[i - 1] for i in range(-14, 0)]
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]
        # Require both gains and losses in the window for a meaningful RSI;
        # degenerate cases (e.g., flat data with a single tick) shouldn't emit.
        if not gains or not losses:
            return []
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        if rsi > 70:
            return [self._sig(symbol, SignalKind.TECHNICAL_BREAKOUT, 0.4, now,
                               {"direction": "down", "indicator": "rsi_overbought", "rsi": rsi})]
        if rsi < 30:
            return [self._sig(symbol, SignalKind.TECHNICAL_BREAKOUT, 0.4, now,
                               {"direction": "up", "indicator": "rsi_oversold", "rsi": rsi})]
        return []

    @staticmethod
    def _sig(symbol: str, kind: SignalKind, strength: float, now: dt.datetime,
             evidence: dict) -> Signal:
        key = f"tech:{symbol}:{kind.value}:{evidence.get('indicator', evidence.get('direction', ''))}:{now.date().isoformat()}"
        sid = "tech_" + hashlib.sha256(key.encode()).hexdigest()[:16]
        return Signal(
            id=sid,
            kind=kind,
            symbol=symbol,
            created_at=now,
            strength=strength,
            evidence=evidence,
        )
