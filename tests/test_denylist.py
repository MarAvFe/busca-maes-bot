"""Denylist + denied_users table. Uses temp DB."""

import pytest

from buscamaes.storage import audit


@pytest.fixture
async def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "audit.db"
    monkeypatch.setenv("BOT_TOKEN", "test_token")
    monkeypatch.setenv("AUDIT_DB_PATH", str(db_path))

    from buscamaes.settings import get_settings

    get_settings.cache_clear()

    await audit.init_db()
    yield db_path
    await audit.close_db()


async def test_deny_user_inserts_row(temp_db):
    await audit.deny_user(user_id=123, reason="daily_threshold (21 > 20)")
    assert await audit.is_denied(123) is True


async def test_is_denied_false_for_unlisted_user(temp_db):
    await audit.deny_user(user_id=100, reason="spam")
    assert await audit.is_denied(100) is True
    assert await audit.is_denied(200) is False


async def test_deny_user_idempotent(temp_db):
    await audit.deny_user(user_id=42, reason="v1")
    await audit.deny_user(user_id=42, reason="v2")
    # Should not raise; second insert ignored
    listed = await audit._list_denied()
    assert listed == [42]
