import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from tse_scraper import PersonResult, search_person

load_dotenv()

VERSION = Path(__file__).parent.joinpath("VERSION").read_text().strip()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")


def _parse_name_input(text: str) -> tuple[str, str, str]:
    """Split input into (nombre, apellido1, apellido2).

    Rules:
      - 1 word  → nombre only
      - 2 words → nombre apellido1
      - 3+ words → everything except last two = nombre, last two = apellidos
    """
    parts = text.strip().split()
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return " ".join(parts[:-2]), parts[-2], parts[-1]


def _format_result(r: PersonResult) -> str:
    lines = []
    if r.cedula:
        lines.append(f"*Cédula:* `{r.cedula}`")
    if r.nombre:
        lines.append(f"*Nombre:* {r.nombre}")
    if r.conocido_como:
        lines.append(f"*Conocido/a como:* {r.conocido_como}")
    if r.fecha_nacimiento:
        lines.append(f"*Fecha de nacimiento:* {r.fecha_nacimiento}")
    if r.edad:
        lines.append(f"*Edad:* {r.edad}")
    if r.nacionalidad:
        lines.append(f"*Nacionalidad:* {r.nacionalidad}")
    if r.padre:
        lines.append(f"*Padre/Madre:* {r.padre}")
    if r.madre:
        lines.append(f"*Padre/Madre:* {r.madre}")
    return "\n".join(lines) if lines else "Sin datos."


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"*DiayQuién* v{VERSION}\n\n"
        "Envíame un nombre para buscarlo en el TSE.\n\n"
        "Ejemplos:\n"
        "  `ignacio avila feoli`\n"
        "  `maria jose avila`\n"
        "  `avila feoli`\n\n"
        "También puedes usar /buscar seguido del nombre.",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"*DiayQuién* v{VERSION}\n\n"
        "*Uso:*\n"
        "Escribe un nombre (o parte del nombre) y el bot buscará en el padrón electoral del TSE.\n\n"
        "*Formato:* `nombre apellido1 apellido2`\n"
        "  - El último token es el segundo apellido\n"
        "  - El penúltimo es el primer apellido\n"
        "  - El resto es el nombre\n\n"
        "*Comandos:*\n"
        "/buscar \\<nombre\\> — buscar persona\n"
        "/start — mensaje de bienvenida\n"
        "/help — esta ayuda",
        parse_mode="Markdown",
    )


async def _do_search(update: Update, text: str) -> None:
    nombre, apellido1, apellido2 = _parse_name_input(text)
    if not nombre:
        await update.message.reply_text("Por favor ingrese al menos un nombre.")
        return

    msg = await update.message.reply_text("🔍 Buscando…")

    try:
        result = await search_person(nombre, apellido1, apellido2)
    except Exception as e:
        logger.exception("Search failed")
        await msg.edit_text(f"❌ Error al buscar: {e}")
        return

    if not result:
        await msg.edit_text("No se encontraron resultados para esa búsqueda.")
        return

    await msg.edit_text(_format_result(result), parse_mode="Markdown")


async def cmd_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Uso: /buscar <nombre> [apellido1] [apellido2]")
        return
    await _do_search(update, query)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _do_search(update, update.message.text)


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN not set. Create a .env file with BOT_TOKEN=...")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("buscar", cmd_buscar))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
