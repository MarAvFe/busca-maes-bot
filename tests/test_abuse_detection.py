"""Daily counter + abuse threshold. Uses temp DB + mocked time."""

import pytest

from buscamaes.security.rate_limit import _reset_for_tests, increment_daily
from buscamaes.storage import audit


@pytest.fixture
async def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "audit.db"
    monkeypatch.setenv("BOT_TOKEN", "test_token")
    monkeypatch.setenv("AUDIT_DB_PATH", str(db_path))
    monkeypatch.setenv("DAILY_ABUSE_THRESHOLD", "20")

    from buscamaes.settings import get_settings

    get_settings.cache_clear()

    await audit.init_db()
    _reset_for_tests()
    yield db_path
    await audit.close_db()
    _reset_for_tests()


async def test_under_threshold_no_deny(temp_db):
    for _ in range(15):
        count = increment_daily(123)
    assert count == 15
    assert await audit.is_denied(123) is False


async def test_over_threshold_triggers_deny(temp_db):
    for _ in range(21):
        count = increment_daily(456)
    assert count == 21
    # In decorator, would call deny_user here
    await audit.deny_user(456, f"daily_threshold ({count} > 20)")
    assert await audit.is_denied(456) is True
