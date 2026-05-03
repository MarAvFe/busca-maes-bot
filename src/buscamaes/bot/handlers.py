import logging
import time
from dataclasses import dataclass, field

from telegram import Update
from telegram.ext import ContextTypes

from .. import __version__
from ..logging_utils import query_hash
from ..observability import new_correlation_id
from ..security.decorators import rate_limited, requires_auth
from ..sources.tse import SearchSession, search_session, select_from_session
from ..storage.audit import record_audit
from ..validation import sanitize_user_error, validate_name_query
from .formatting import (
    _build_choices_keyboard,
    _choices_header,
    _format_person,
    _parse_name_input_with_fallbacks,
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


@requires_auth
@rate_limited
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    await update.message.reply_text(
        f"*BuscaMaes* v{__version__}\n\n"
        "Envíame un nombre para buscarlo en el TSE.\n\n"
        "Ejemplos:\n"
        "  `juan mora fernandez`\n"
        "  `maria jose mora`\n"
        "  `mora fernandez`\n\n"
        "También podés usar /buscar seguido del nombre.\n\n"
        "_Esta herramienta consulta registros públicos. El uso indebido"
        " es responsabilidad del usuario._",
        parse_mode="Markdown",
    )


@requires_auth
@rate_limited
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    await update.message.reply_text(
        f"*BuscaMaes* v{__version__}\n\n"
        "_Esta herramienta consulta registros públicos. El uso indebido"
        " es responsabilidad del usuario._\n\n"
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


async def _do_search(update: Update, query: str) -> None:
    assert update.effective_user is not None
    assert update.message is not None
    user_id = update.effective_user.id
    msg = await update.message.reply_text("🔍 Buscando…")

    try:
        query = validate_name_query(query)
    except ValueError as e:
        await msg.edit_text(f"❌ {e}")
        return

    # Try multiple decompositions
    decompositions = _parse_name_input_with_fallbacks(query)
    session = None
    used_decomposition = None

    for i, (nombre, apellido1, apellido2) in enumerate(decompositions):
        logger.debug(
            "User=%s attempt=%d query=%s",
            user_id,
            i + 1,
            query_hash(nombre, apellido1, apellido2),
        )
        try:
            session = await search_session(nombre, apellido1, apellido2)
            if session and session.results:
                used_decomposition = (nombre, apellido1, apellido2)
                logger.info(
                    "User=%s got results attempt=%d query=%s",
                    user_id,
                    i + 1,
                    query_hash(nombre, apellido1, apellido2),
                )
                break
        except Exception:
            logger.exception("Search attempt %d failed", i + 1)
            # Continue to next decomposition

    if not session or not session.results:
        logger.info("No results attempts=%d user=%s", len(decompositions), user_id)
        # Hash first decomposition for consistency with success paths
        nombre, apellido1, apellido2 = decompositions[0]
        await record_audit(
            user_id=user_id,
            action="search",
            query_hash=query_hash(nombre, apellido1, apellido2),
            result="no_results",
        )
        await msg.edit_text("No se encontraron resultados para esa búsqueda.")
        return

    # Unpack the successful decomposition
    if used_decomposition is None:
        logger.error("Internal: used_decomposition is None despite session having results")
        await msg.edit_text("❌ Error interno al procesar la búsqueda.")
        return
    nombre, apellido1, apellido2 = used_decomposition

    # Single result → show detail directly
    if len(session.results) == 1 and session.total_raw == 1:
        try:
            person = await select_from_session(session, session.results[0].index)
        except Exception as e:
            logger.exception("Select failed")
            await msg.edit_text(f"❌ {sanitize_user_error(e)}")
            return

        if not person:
            await msg.edit_text("No se pudo obtener el detalle de la persona.")
            return

        await msg.edit_text(_format_person(person), parse_mode="Markdown")
        await record_audit(
            user_id=user_id,
            action="search",
            query_hash=query_hash(nombre, apellido1, apellido2),
            result="ok_single",
        )
        return

    # Multiple results → show choice keyboard
    _store_session(user_id, session)
    await record_audit(
        user_id=user_id,
        action="search",
        query_hash=query_hash(nombre, apellido1, apellido2),
        result="ok_multi",
    )
    header = _choices_header(session, nombre, apellido1, apellido2)
    keyboard = _build_choices_keyboard(session)
    await msg.edit_text(header, parse_mode="Markdown", reply_markup=keyboard)


@requires_auth
@rate_limited
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_correlation_id()
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
            await query.edit_message_text(f"❌ {sanitize_user_error(e)}")
            return

        if not person:
            await query.edit_message_text("No se pudo obtener el detalle de la persona.")
            return

        await query.edit_message_text(_format_person(person), parse_mode="Markdown")


@requires_auth
@rate_limited
async def cmd_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_correlation_id()
    assert update.message is not None
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Uso: /buscar <nombre> [apellido1] [apellido2]")
        return
    await _do_search(update, query)


@requires_auth
@rate_limited
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_correlation_id()
    assert update.message is not None
    assert update.message.text is not None
    if not update.message.text.strip():
        await update.message.reply_text("Por favor ingrese al menos un nombre.")
        return
    await _do_search(update, update.message.text)
