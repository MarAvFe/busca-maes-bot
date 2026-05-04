import asyncio
import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from .bot.handlers import cmd_buscar, cmd_help, cmd_placa, cmd_start, handle_callback, handle_text
from .observability import configure_logging, configure_sentry
from .settings import get_settings
from .storage.audit import cleanup_loop, close_db, init_db


async def _post_init(_: Application) -> None:
    await init_db()
    asyncio.create_task(cleanup_loop())  # noqa: RUF006


async def _post_shutdown(_: Application) -> None:
    await close_db()


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    sentry_on = configure_sentry()
    logger = logging.getLogger(__name__)

    assert settings.bot_token is not None
    app = (
        Application.builder()
        .token(settings.bot_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))  # type: ignore[arg-type]
    app.add_handler(CommandHandler("help", cmd_help))  # type: ignore[arg-type]
    app.add_handler(CommandHandler("buscar", cmd_buscar))  # type: ignore[arg-type]
    app.add_handler(CommandHandler("placa", cmd_placa))  # type: ignore[arg-type]
    app.add_handler(CallbackQueryHandler(handle_callback))  # type: ignore[arg-type]
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))  # type: ignore[arg-type]

    logger.info("Bot started", extra={"sentry_enabled": sentry_on})
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
