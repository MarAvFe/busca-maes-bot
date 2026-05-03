"""Telegram user ID allowlist. Empty allowlist = deny all (fail closed)."""

from ..settings import get_settings


def is_allowed(user_id: int) -> bool:
    return user_id in get_settings().allowlist
