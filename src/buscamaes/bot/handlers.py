import logging
import time
from dataclasses import dataclass, field

from telegram import Update
from telegram.ext import ContextTypes

from .. import __version__
from ..logging_utils import query_hash
from ..observability import new_correlation_id
from ..security.decorators import rate_limited
from ..settings import get_settings
from ..sources.rnp import RNPUnavailable, get_rnp_pool
from ..sources.tse import SearchSession, search_session, select_from_session
from ..storage.audit import get_stats, record_audit
from ..validation import detect_plate, sanitize_user_error, validate_name_query
from .formatting import (
    _build_choices_keyboard,
    _choices_header,
    _format_person,
    _format_stats,
    _format_vehicle,
    _parse_name_input_with_fallbacks,
    _person_detail_keyboard,
    _truncate_for_telegram,
)

logger = logging.getLogger(__name__)

SESSION_TTL = 300  # seconds before a pending search expires


@dataclass
class PendingSearch:
    session: SearchSession
    query: tuple[str, str, str] = field(default_factory=lambda: ("", "", ""))
    page: int = 0
    created_at: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        return time.time() - self.created_at > SESSION_TTL


_pending: dict[int, PendingSearch] = {}  # keyed by user_id


def _store_session(user_id: int, session: SearchSession, query: tuple[str, str, str]) -> None:
    _pending[user_id] = PendingSearch(session=session, query=query)


def _peek_session(user_id: int) -> PendingSearch | None:
    """Return pending search without removing it. Returns None if missing or expired."""
    pending = _pending.get(user_id)
    if pending is None or pending.is_expired():
        _pending.pop(user_id, None)
        return None
    return pending


def _pop_session(user_id: int) -> SearchSession | None:
    pending = _pending.pop(user_id, None)
    if pending is None or pending.is_expired():
        return None
    return pending.session


def _plate_allowed(user_id: int) -> bool:
    """Return True only if user_id is in the plate allowlist. Empty list = nobody."""
    return user_id in get_settings().plate_allowed_user_ids


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
        "También podés usar /buscar seguido del nombre.",
        parse_mode="Markdown",
    )


@rate_limited
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    assert update.effective_user is not None
    user_id = update.effective_user.id

    help_text = f"*BuscaMaes* v{__version__}\n\n"
    help_text += "*Búsqueda de personas (TSE):*\n"
    help_text += "Escribí un nombre o usa /buscar \\<nombre\\>\n"
    help_text += "*Formato:* `nombre apellido1 apellido2`\n\n"

    # Conditionally show vehicle search based on allowlist
    if _plate_allowed(user_id):
        help_text += "*Búsqueda de vehículos (RNP):*\n"
        help_text += "Escribí la placa del vehículo o usa /placa \\<placa\\>\n"
        help_text += "*Formatos válidos:*\n"
        help_text += "  - Auto: `621335` o `BJV123`\n"
        help_text += "  - Moto: `621335` o `MOT621335` o `M621ABC`\n"
        help_text += "  - Carga: `CL123456`\n\n"

    help_text += "*Comandos:*\n"
    help_text += "/buscar \\<nombre\\> — buscar persona\n"
    if _plate_allowed(user_id):
        help_text += "/placa \\<placa\\> — buscar vehículo\n"
    help_text += "/start — bienvenida\n"
    help_text += "/help — esta ayuda"

    await update.message.reply_text(help_text, parse_mode="Markdown")


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
    _store_session(user_id, session, (nombre, apellido1, apellido2))
    await record_audit(
        user_id=user_id,
        action="search",
        query_hash=query_hash(nombre, apellido1, apellido2),
        result="ok_multi",
    )
    header = _choices_header(session, nombre, apellido1, apellido2, page=0)
    keyboard = _build_choices_keyboard(session, page=0)
    await msg.edit_text(header, parse_mode="Markdown", reply_markup=keyboard)


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

    if query.data.startswith("page:"):
        pending = _peek_session(user_id)
        if pending is None:
            await query.edit_message_text(
                "⏱ Esta selección expiró. Realizá la búsqueda nuevamente."
            )
            return
        pending.page = int(query.data.split(":")[1])
        header = _choices_header(pending.session, *pending.query, page=pending.page)
        keyboard = _build_choices_keyboard(pending.session, page=pending.page)
        await query.edit_message_text(header, parse_mode="Markdown", reply_markup=keyboard)
        return

    if query.data == "back":
        pending = _peek_session(user_id)
        if pending is None:
            await query.edit_message_text(
                "⏱ Esta selección expiró. Realizá la búsqueda nuevamente."
            )
            return
        header = _choices_header(pending.session, *pending.query, page=pending.page)
        keyboard = _build_choices_keyboard(pending.session, page=pending.page)
        await query.edit_message_text(header, parse_mode="Markdown", reply_markup=keyboard)
        return

    if query.data.startswith("sel:"):
        pending = _peek_session(user_id)
        if pending is None:
            await query.edit_message_text(
                "⏱ Esta selección expiró. Realizá la búsqueda nuevamente."
            )
            return

        index = int(query.data.split(":")[1])
        await query.edit_message_text("🔍 Obteniendo detalle…")

        try:
            person = await select_from_session(pending.session, index)
        except Exception as e:
            logger.exception("select_from_session failed")
            await query.edit_message_text(f"❌ {sanitize_user_error(e)}")
            return

        if not person:
            await query.edit_message_text("No se pudo obtener el detalle de la persona.")
            return

        await query.edit_message_text(
            _format_person(person),
            parse_mode="Markdown",
            reply_markup=_person_detail_keyboard(),
        )


@rate_limited
async def cmd_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_correlation_id()
    assert update.message is not None
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Uso: /buscar <nombre> [apellido1] [apellido2]")
        return
    await _do_search(update, query)


async def _do_plate_search(update: Update, plate_query) -> None:
    assert update.effective_user is not None
    assert update.message is not None
    user_id = update.effective_user.id

    msg = await update.message.reply_text("🔍 Buscando…")

    try:
        pool = get_rnp_pool()
        vehicle = await pool.query_plate(plate_query.class_code, plate_query.car_number)

        if not vehicle.marca:
            await msg.edit_text("No se encontró el vehículo.")
            await record_audit(
                user_id=user_id,
                action="plate_search",
                query_hash=query_hash(plate_query.raw),
                result="no_results",
            )
            return

        await msg.edit_text(_truncate_for_telegram(_format_vehicle(vehicle)), parse_mode="Markdown")
        await record_audit(
            user_id=user_id,
            action="plate_search",
            query_hash=query_hash(plate_query.raw),
            result="ok",
        )
    except RNPUnavailable as e:
        logger.debug("RNP unavailable: %s", e)
        await msg.edit_text(f"❌ {sanitize_user_error(e)}")
        await record_audit(
            user_id=user_id,
            action="plate_search",
            query_hash=query_hash(plate_query.raw),
            result="unavailable",
        )
    except Exception as e:
        logger.exception("Plate search failed")
        await msg.edit_text(f"❌ {sanitize_user_error(e)}")
        await record_audit(
            user_id=user_id,
            action="plate_search",
            query_hash=query_hash(plate_query.raw),
            result="error",
        )


@rate_limited
async def cmd_placa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_correlation_id()
    assert update.message is not None
    assert update.effective_user is not None
    user_id = update.effective_user.id

    # Check allowlist first; don't hint at command existence if not allowed
    if not _plate_allowed(user_id):
        await update.message.reply_text(
            "Formato no reconocido. Ejemplos: 621335, BJV123, MOT621335, M621ABC, CL123456."
        )
        return

    plate_input = " ".join(context.args) if context.args else ""
    if not plate_input:
        await update.message.reply_text("Uso: /placa <placa>")
        return
    plate_query = detect_plate(plate_input)
    if not plate_query:
        await update.message.reply_text(
            "Formato no reconocido. Ejemplos: 621335, BJV123, MOT621335, M621ABC, CL123456."
        )
        return
    await _do_plate_search(update, plate_query)


@rate_limited
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_correlation_id()
    assert update.message is not None
    assert update.message.text is not None
    assert update.effective_user is not None
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Por favor ingrese al menos un nombre.")
        return

    # Single word: try plate first (only for allowed users), reject if no match
    if " " not in text:
        plate_query = detect_plate(text)
        if plate_query and _plate_allowed(update.effective_user.id):
            await _do_plate_search(update, plate_query)
            return
        # If user not allowed, don't mention plate search exists
        if _plate_allowed(update.effective_user.id):
            error_msg = (
                "Formato no reconocido. Escribí un nombre"
                " (2+ palabras) o una placa válida. Vea /help"
            )
        else:
            error_msg = "Escribí un nombre con al menos 2 palabras. Vea /help"
        await update.message.reply_text(error_msg)
        return

    # Multi-word: name search
    await _do_search(update, text)


@rate_limited
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    assert update.effective_user is not None
    user_id = update.effective_user.id

    # Gate: admins only
    if user_id not in get_settings().admin_user_ids:
        await update.message.reply_text("Comando no reconocido.")
        return

    stats = await get_stats(days=7)
    await update.message.reply_text(_format_stats(stats), parse_mode="Markdown")
