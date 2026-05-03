import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from .bot.handlers import cmd_buscar, cmd_help, cmd_start, handle_callback, handle_text
from .settings import get_settings


def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=settings.log_level,
    )
    logger = logging.getLogger(__name__)

    app = Application.builder().token(settings.bot_token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("buscar", cmd_buscar))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
