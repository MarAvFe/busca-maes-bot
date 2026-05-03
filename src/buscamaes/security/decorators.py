"""Handler decorators for allowlist + rate limiting.

Apply to PTB handlers in this order (outermost first):
    @requires_auth          # allowlist check
    @rate_limited           # token bucket check
    async def handler(...): ...

Order matters: deny-listed users must not consume bucket capacity, so
allowlist runs first.
"""

import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from ..settings import get_settings
from ..storage.audit import record_audit
from .allowlist import is_allowed
from .rate_limit import check_and_consume

logger = logging.getLogger(__name__)

Handler = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]


def _user_id(update: Update) -> int | None:
    if update.effective_user is None:
        return None
    return update.effective_user.id


async def _reply(update: Update, text: str) -> None:
    """Best-effort reply to either a message or a callback query."""
    if update.message is not None:
        await update.message.reply_text(text)
    elif update.callback_query is not None:
        await update.callback_query.answer(text=text, show_alert=True)


def requires_auth(handler: Handler) -> Handler:
    @wraps(handler)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        uid = _user_id(update)
        if uid is None or not is_allowed(uid):
            logger.warning("Allowlist denied user_id=%s", uid)
            await _reply(update, "No tenés acceso a este bot.")
            await record_audit(
                user_id=uid or 0,
                action="auth_denied",
                query_hash=None,
                result="denied",
            )
            return None
        return await handler(update, context)

    return wrapped


def rate_limited(handler: Handler) -> Handler:
    @wraps(handler)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        uid = _user_id(update)
        if uid is None:
            return await handler(update, context)
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
        return await handler(update, context)

    return wrapped
