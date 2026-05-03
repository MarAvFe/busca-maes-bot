"""Rate limiting + abuse detection decorator.

Denylist model: everyone access default. Auto-deny on abuse (>N req/day).

Denial persistent (DB). Token bucket in-memory (restart resets, not denial).
"""

import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from ..settings import get_settings
from ..storage.audit import deny_user, is_denied, record_audit
from .rate_limit import check_and_consume, increment_daily

logger = logging.getLogger(__name__)

Handler = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]


def _user_id(update: Update) -> int | None:
    if update.effective_user is None:
        return None
    return update.effective_user.id


async def _reply(update: Update, text: str) -> None:
    """Best-effort reply to either a message or callback query."""
    if update.message is not None:
        await update.message.reply_text(text)
    elif update.callback_query is not None:
        await update.callback_query.answer(text=text, show_alert=True)


def rate_limited(handler: Handler) -> Handler:
    @wraps(handler)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        uid = _user_id(update)
        if uid is None:
            return await handler(update, context)

        # Check if user denied (persistent)
        if await is_denied(uid):
            logger.warning("Denied user_id=%s", uid)
            await _reply(update, "Tu acceso está restringido.")
            await record_audit(
                user_id=uid,
                action="auth_denied",
                query_hash=None,
                result="denied",
            )
            return None

        # Token bucket check
        s = get_settings()
        if not check_and_consume(uid, s.rate_limit_max, s.rate_limit_window):
            logger.warning("Rate limited user_id=%s", uid)
            await _reply(
                update,
                f"Esperá un momento. Máximo {s.rate_limit_max} consultas cada"
                f" {s.rate_limit_window}s.",
            )
            await record_audit(
                user_id=uid,
                action="rate_limited",
                query_hash=None,
                result="rate_limited",
            )
            return None

        # Abuse detection: increment daily counter
        count = increment_daily(uid)
        if count > s.daily_abuse_threshold:
            logger.warning("Abuse threshold exceeded user_id=%s count=%d", uid, count)
            await deny_user(uid, f"daily_threshold ({count} > {s.daily_abuse_threshold})")
            await _reply(update, "Excediste el límite diario. Tu acceso ha sido restringido.")
            await record_audit(
                user_id=uid,
                action="auth_denied",
                query_hash=None,
                result="abuse_threshold",
            )
            return None

        return await handler(update, context)

    return wrapped
