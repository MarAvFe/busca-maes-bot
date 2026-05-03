import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from ..sources.tse import SearchSession, search_session, select_from_session
from .formatting import (
    _build_choices_keyboard,
    _choices_header,
    _format_person,
    _parse_name_input,
)

logger = logging.getLogger(__name__)

SESSION_TTL = 300  # seconds before a pending search expires


@dataclass
class PendingSearch:
    session: SearchSession
    created_at: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        return time.time() - self.created_at > SESSION_TTL


_pending: dict[int, PendingSearch] = {}  # keyed by user_id


def _store_session(user_id: int, session) -> None:
    _pending[user_id] = PendingSearch(session=session)


def _pop_session(user_id: int):
    pending = _pending.pop(user_id, None)
    if pending is None or pending.is_expired():
        return None
    return pending.session


def _get_version() -> str:
    version_file = Path(__file__).parent.parent.parent.parent / "VERSION"
    return version_file.read_text().strip()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    version = _get_version()
    await update.message.reply_text(
        f"*BuscaMaes* v{version}\n\n"
        "Envíame un nombre para buscarlo en el TSE.\n\n"
        "Ejemplos:\n"
        "  `juan mora fernandez`\n"
        "  `maria jose mora`\n"
        "  `mora fernandez`\n\n"
        "También podés usar /buscar seguido del nombre.",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    version = _get_version()
    await update.message.reply_text(
        f"*BuscaMaes* v{version}\n\n"
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
    assert update.effective_user is not None
    assert update.message is not None
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
    assert query is not None
    assert query.data is not None
    assert update.effective_user is not None
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
    assert update.message is not None
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Uso: /buscar <nombre> [apellido1] [apellido2]")
        return
    nombre, apellido1, apellido2 = _parse_name_input(query)
    await _do_search(update, nombre, apellido1, apellido2)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    assert update.message.text is not None
    nombre, apellido1, apellido2 = _parse_name_input(update.message.text)
    if not nombre:
        await update.message.reply_text("Por favor ingrese al menos un nombre.")
        return
    await _do_search(update, nombre, apellido1, apellido2)
