import datetime as dt

import pytest

from trading_assistant.db.schema import create_schema
from trading_assistant.ingest.economic import (
    DEFAULT_SERIES,
    EconomicDataClient,
    EconObservation,
)


class FakeFredGateway:
    def __init__(self, latest: dict[str, EconObservation]):
        self._latest = latest

    def latest(self, series_id: str) -> EconObservation:
        if series_id not in self._latest:
            raise KeyError(series_id)
        return self._latest[series_id]


@pytest.fixture
def conn(db_conn):
    create_schema(db_conn)
    return db_conn


def test_refresh_persists_observations(conn):
    gw = FakeFredGateway({
        "CPIAUCSL": EconObservation("CPIAUCSL", dt.date(2026, 4, 10), 320.5),
        "PAYEMS":   EconObservation("PAYEMS",   dt.date(2026, 4, 5),  158_000.0),
        "DFF":      EconObservation("DFF",      dt.date(2026, 4, 25), 4.25),
    })
    client = EconomicDataClient(gateway=gw, conn=conn)
    client.refresh()
    rows = list(conn.execute("SELECT series_id, value FROM econ_observations ORDER BY series_id"))
    assert {r["series_id"] for r in rows} == set(DEFAULT_SERIES)


def test_refresh_skips_failed_series(conn):
    gw = FakeFredGateway({
        "CPIAUCSL": EconObservation("CPIAUCSL", dt.date(2026, 4, 10), 320.5),
        "DFF":      EconObservation("DFF",      dt.date(2026, 4, 25), 4.25),
    })
    client = EconomicDataClient(gateway=gw, conn=conn)
    client.refresh()
    rows = list(conn.execute("SELECT series_id FROM econ_observations"))
    fetched = {r["series_id"] for r in rows}
    assert "PAYEMS" not in fetched
    assert "CPIAUCSL" in fetched
    assert "DFF" in fetched


def test_refresh_is_idempotent(conn):
    gw = FakeFredGateway({
        "CPIAUCSL": EconObservation("CPIAUCSL", dt.date(2026, 4, 10), 320.5),
        "PAYEMS":   EconObservation("PAYEMS",   dt.date(2026, 4, 5),  158_000.0),
        "DFF":      EconObservation("DFF",      dt.date(2026, 4, 25), 4.25),
    })
    client = EconomicDataClient(gateway=gw, conn=conn)
    client.refresh()
    client.refresh()
    rows = list(conn.execute("SELECT COUNT(*) AS n FROM econ_observations"))
    assert rows[0]["n"] == 3
