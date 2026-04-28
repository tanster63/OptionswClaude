import json

import pytest

from trading_assistant.db.repositories import (
    AppStateRepo,
    AuditLogRepo,
    JobLockHeld,
    JobLockRepo,
    NewsRepo,
)
from trading_assistant.db.schema import create_schema


@pytest.fixture
def conn(db_conn):
    create_schema(db_conn)
    return db_conn


def test_app_state_get_and_set(conn):
    repo = AppStateRepo(conn)
    assert repo.get("kill_switch") == "off"
    repo.set("kill_switch", "on")
    assert repo.get("kill_switch") == "on"
    assert repo.get("missing") is None


def test_audit_log_writes_payload(conn):
    repo = AuditLogRepo(conn)
    repo.write("llm_call", {"prompt_tokens": 1234, "model": "claude"})
    rows = list(conn.execute("SELECT kind, payload_json FROM audit_log"))
    assert len(rows) == 1
    assert rows[0]["kind"] == "llm_call"
    assert json.loads(rows[0]["payload_json"]) == {"prompt_tokens": 1234, "model": "claude"}


def test_job_lock_acquire_and_release(conn):
    repo = JobLockRepo(conn)
    with repo.acquire("scan", now="t1"):
        rows = list(conn.execute("SELECT name FROM job_locks"))
        assert {r["name"] for r in rows} == {"scan"}
    rows = list(conn.execute("SELECT name FROM job_locks"))
    assert rows == []


def test_job_lock_double_acquire_raises(conn):
    repo = JobLockRepo(conn)
    with repo.acquire("scan", now="t1"):
        with pytest.raises(JobLockHeld):
            with repo.acquire("scan", now="t2"):
                pass


def test_news_upsert_dedupes(conn):
    repo = NewsRepo(conn)
    repo.upsert(
        url_hash="h1", source="rss", title="t", snippet="s",
        published_at="2026-04-26T13:00:00Z", arrived_at="2026-04-26T13:01:00Z",
    )
    repo.upsert(
        url_hash="h1", source="rss", title="t-different", snippet="s",
        published_at="2026-04-26T13:00:00Z", arrived_at="2026-04-26T14:00:00Z",
    )
    rows = list(conn.execute("SELECT title FROM news_items"))
    assert len(rows) == 1
    assert rows[0]["title"] == "t"


def test_news_fresh_since_filters(conn):
    repo = NewsRepo(conn)
    repo.upsert(url_hash="a", source="rss", title="old", snippet=None,
                published_at=None, arrived_at="2026-04-26T10:00:00Z")
    repo.upsert(url_hash="b", source="rss", title="new", snippet=None,
                published_at=None, arrived_at="2026-04-26T15:00:00Z")
    fresh = list(repo.fresh_since("2026-04-26T12:00:00Z"))
    titles = {n["title"] for n in fresh}
    assert titles == {"new"}
