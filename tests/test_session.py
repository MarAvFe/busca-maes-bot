import os
import time

os.environ.setdefault("BOT_TOKEN", "test_token")

from bot import SESSION_TTL, PendingSearch
from tse_scraper import SearchSession


def _make_session() -> SearchSession:
    return SearchSession(muestra_url="", viewstate={}, cookies={}, results=[], total_raw=0)


def test_fresh_session_is_not_expired():
    ps = PendingSearch(session=_make_session())
    assert not ps.is_expired()


def test_old_session_is_expired():
    ps = PendingSearch(session=_make_session())
    ps.created_at = time.time() - SESSION_TTL - 1
    assert ps.is_expired()


def test_session_at_exact_ttl_boundary_is_expired():
    ps = PendingSearch(session=_make_session())
    ps.created_at = time.time() - SESSION_TTL
    assert ps.is_expired()
