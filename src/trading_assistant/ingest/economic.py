"""Economic data client using FRED for CPI / NFP / Fed funds rate."""

from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass
from typing import Protocol

import structlog

log = structlog.get_logger(__name__)

DEFAULT_SERIES: tuple[str, ...] = ("CPIAUCSL", "PAYEMS", "DFF")


@dataclass(frozen=True)
class EconObservation:
    series_id: str
    observation_date: dt.date
    value: float


class _FredGateway(Protocol):
    def latest(self, series_id: str) -> EconObservation: ...


class EconomicDataClient:
    def __init__(
        self,
        *,
        gateway: _FredGateway,
        conn: sqlite3.Connection,
        series: tuple[str, ...] = DEFAULT_SERIES,
    ) -> None:
        self._gw = gateway
        self._conn = conn
        self._series = series

    def refresh(self) -> None:
        now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
        for sid in self._series:
            try:
                obs = self._gw.latest(sid)
            except Exception as exc:  # noqa: BLE001
                log.warning("fred_fetch_failed", series=sid, error=str(exc))
                continue
            self._conn.execute(
                "INSERT INTO econ_observations(series_id, observation_date, value, fetched_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(series_id, observation_date) DO UPDATE SET "
                "value=excluded.value, fetched_at=excluded.fetched_at",
                (obs.series_id, obs.observation_date.isoformat(), obs.value, now_iso),
            )
