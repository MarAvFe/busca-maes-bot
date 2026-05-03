"""Allowlist behavior. Tests use monkeypatch on get_settings()."""

import os

from buscamaes.security.allowlist import is_allowed
from buscamaes.settings import Settings


def _make_settings(allowlist_csv: str) -> Settings:
    os.environ["BOT_TOKEN"] = "test_token"  # noqa: S105
    os.environ["ALLOWLIST_USER_IDS"] = allowlist_csv
    return Settings()


def test_empty_allowlist_denies_everyone(monkeypatch):
    s = _make_settings("")
    monkeypatch.setattr("buscamaes.security.allowlist.get_settings", lambda: s)
    assert is_allowed(123) is False
    assert is_allowed(0) is False


def test_allowlist_admits_listed_users(monkeypatch):
    s = _make_settings("100,200,300")
    monkeypatch.setattr("buscamaes.security.allowlist.get_settings", lambda: s)
    assert is_allowed(100) is True
    assert is_allowed(200) is True
    assert is_allowed(300) is True
    assert is_allowed(400) is False


def test_allowlist_strips_whitespace(monkeypatch):
    s = _make_settings(" 100 , 200 ")
    monkeypatch.setattr("buscamaes.security.allowlist.get_settings", lambda: s)
    assert is_allowed(100) is True
    assert is_allowed(200) is True
