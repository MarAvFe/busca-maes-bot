import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from tse_scraper import (
    TSE_SEARCH_URL,
    PersonResult,
    SearchSession,
    search_session,
    select_from_session,
)

load_dotenv()

VERSION = Path(__file__).parent.joinpath("VERSION").read_text().strip()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

MAX_CHOICES = 5
SESSION_TTL = 300  # seconds before a pending search expires


# ---------------------------------------------------------------------------
# In-memory pending search store
# ---------------------------------------------------------------------------


@dataclass
class PendingSearch:
    session: SearchSession
    created_at: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        return time.time() - self.created_at > SESSION_TTL


_pending: dict[int, PendingSearch] = {}  # keyed by user_id


def _store_session(user_id: int, session: SearchSession) -> None:
    _pending[user_id] = PendingSearch(session=session)


def _pop_session(user_id: int) -> SearchSession | None:
    pending = _pending.pop(user_id, None)
    if pending is None or pending.is_expired():
        return None
    return pending.session


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _parse_name_input(text: str) -> tuple[str, str, str]:
    parts = text.strip().split()
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return " ".join(parts[:-2]), parts[-2], parts[-1]


def _format_person(r: PersonResult) -> str:
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
        lines.append(f"*Progenitor/a:* {r.padre}")
    if r.madre:
        lines.append(f"*Progenitor/a:* {r.madre}")
    return "\n".join(lines) if lines else "Sin datos."


def _build_choices_keyboard(session: SearchSession) -> InlineKeyboardMarkup:
    rows = []
    for r in session.results[:MAX_CHOICES]:
        label = f"{r.cedula} — {r.nombre}"
        rows.append([InlineKeyboardButton(label, callback_data=f"sel:{r.index}")])

    footer = [
        InlineKeyboardButton("🌐 Abrir en TSE", url=TSE_SEARCH_URL),
        InlineKeyboardButton("❌ Cancelar", callback_data="cancel"),
    ]
    rows.append(footer)
    return InlineKeyboardMarkup(rows)


def _choices_header(session: SearchSession, nombre: str, apellido1: str, apellido2: str) -> str:
    query = " ".join(filter(None, [nombre, apellido1, apellido2]))
    alive = len(session.results)
    total = session.total_raw
    filtered = total - alive

    lines = [f"*{total} resultado(s)* para *{query}*"]
    if filtered:
        lines.append(f"_{filtered} fallecido(s) ocultado(s)_")
    shown = min(alive, MAX_CHOICES)
    lines.append(f"\nMostrando los primeros {shown}. Seleccioná uno o refiná la búsqueda:")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"*BuscaMaes* v{VERSION}\n\n"
        "Envíame un nombre para buscarlo en el TSE.\n\n"
        "Ejemplos:\n"
        "  `juan mora fernandez`\n"
        "  `maria jose mora`\n"
        "  `mora fernandez`\n\n"
        "También podés usar /buscar seguido del nombre.",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"*BuscaMaes* v{VERSION}\n\n"
        "*Uso:*\n"
        "Escribí un nombre (o parte del nombre) y el bot buscará"
        " en el padrón electoral del TSE.\n\n"
        "*Formato:* `nombre apellido1 apellido2`\n"
        "  - El último token es el segundo apellido\n"
        "  - El penúltimo es el primer apellido\n"
        "  - El resto es el nombre\n\n"
        "*Cuando hay múltiples resultados:*\n"
        "El bot muestra hasta 5 opciones. Tocá uno para ver el detalle, "
        "o abrí el link del TSE para buscar con más filtros.\n\n"
        "*Comandos:*\n"
        "/buscar \\<nombre\\> — buscar persona\n"
        "/start — mensaje de bienvenida\n"
        "/help — esta ayuda",
        parse_mode="Markdown",
    )


async def _do_search(update: Update, nombre: str, apellido1: str, apellido2: str) -> None:
    user_id = update.effective_user.id
    msg = await update.message.reply_text("🔍 Buscando…")

    try:
        session = await search_session(nombre, apellido1, apellido2)
    except Exception as e:
        logger.exception("Search failed")
        await msg.edit_text(f"❌ Error al buscar: {e}")
        return

    if not session or not session.results:
        await msg.edit_text("No se encontraron resultados para esa búsqueda.")
        return

    # Single result → show detail directly
    if len(session.results) == 1 and session.total_raw == 1:
        try:
            person = await select_from_session(session, session.results[0].index)
        except Exception as e:
            logger.exception("Select failed")
            await msg.edit_text(f"❌ Error al obtener el detalle: {e}")
            return

        if not person:
            await msg.edit_text("No se pudo obtener el detalle de la persona.")
            return

        await msg.edit_text(_format_person(person), parse_mode="Markdown")
        return

    # Multiple results → show choice keyboard
    _store_session(user_id, session)
    header = _choices_header(session, nombre, apellido1, apellido2)
    keyboard = _build_choices_keyboard(session)
    await msg.edit_text(header, parse_mode="Markdown", reply_markup=keyboard)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if query.data == "cancel":
        _pending.pop(user_id, None)
        await query.edit_message_text("Búsqueda cancelada.")
        return

    if query.data.startswith("sel:"):
        session = _pop_session(user_id)
        if session is None:
            await query.edit_message_text(
                "⏱ Esta selección expiró. Realizá la búsqueda nuevamente."
            )
            return

        index = int(query.data.split(":")[1])
        await query.edit_message_text("🔍 Obteniendo detalle…")

        try:
            person = await select_from_session(session, index)
        except Exception as e:
            logger.exception("select_from_session failed")
            await query.edit_message_text(f"❌ Error al obtener el detalle: {e}")
            return

        if not person:
            await query.edit_message_text("No se pudo obtener el detalle de la persona.")
            return

        await query.edit_message_text(_format_person(person), parse_mode="Markdown")


async def cmd_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Uso: /buscar <nombre> [apellido1] [apellido2]")
        return
    nombre, apellido1, apellido2 = _parse_name_input(query)
    await _do_search(update, nombre, apellido1, apellido2)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    nombre, apellido1, apellido2 = _parse_name_input(update.message.text)
    if not nombre:
        await update.message.reply_text("Por favor ingrese al menos un nombre.")
        return
    await _do_search(update, nombre, apellido1, apellido2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN not set. Create a .env file with BOT_TOKEN=...")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("buscar", cmd_buscar))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
