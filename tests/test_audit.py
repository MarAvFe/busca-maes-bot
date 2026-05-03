"""Audit DB write + cleanup. Uses temp DB path."""


import pytest

from buscamaes.storage import audit


@pytest.fixture
async def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "audit.db"
    monkeypatch.setenv("BOT_TOKEN", "test_token")
    monkeypatch.setenv("AUDIT_DB_PATH", str(db_path))
    monkeypatch.setenv("AUDIT_RETENTION_DAYS", "30")

    # Force settings reload (lru_cache + module-level _conn)
    from buscamaes.settings import get_settings

    get_settings.cache_clear()

    await audit.init_db()
    yield db_path
    await audit.close_db()


async def test_record_audit_inserts_row(temp_db):
    await audit.record_audit(user_id=42, action="search", query_hash="abc123", result="ok_single")
    assert await audit._count_rows() == 1


async def test_record_audit_no_op_when_db_uninitialized():
    # Force conn to None
    audit._conn = None
    # Should not raise
    await audit.record_audit(user_id=1, action="search", query_hash="x", result="ok_single")


async def test_cleanup_deletes_old_rows(temp_db):
    # Insert a row with backdated ts
    assert audit._conn is not None
    await audit._conn.execute(
        "INSERT INTO audit (ts, user_id, action, query_hash, correlation_id, result)"
        " VALUES (datetime('now', '-100 days'), 1, 'search', 'x', '-', 'ok')"
    )
    await audit._conn.commit()
    # And a fresh row
    await audit.record_audit(user_id=2, action="search", query_hash="y", result="ok")
    assert await audit._count_rows() == 2

    deleted = await audit.cleanup_old(retention_days=30)
    assert deleted == 1
    assert await audit._count_rows() == 1
