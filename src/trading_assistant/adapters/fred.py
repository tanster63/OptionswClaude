"""FRED adapter."""

from __future__ import annotations

import datetime as dt

from fredapi import Fred

from trading_assistant.ingest.economic import EconObservation


class FredAdapter:
    def __init__(self, *, api_key: str) -> None:
        self._client = Fred(api_key=api_key)

    def latest(self, series_id: str) -> EconObservation:
        series = self._client.get_series_latest_release(series_id)
        last_index = series.index[-1]
        last_value = series.iloc[-1]
        return EconObservation(
            series_id=series_id,
            observation_date=last_index.date() if hasattr(last_index, "date") else dt.date.today(),
            value=float(last_value),
        )
