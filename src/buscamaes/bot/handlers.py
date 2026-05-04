import logging
import time
from dataclasses import dataclass, field

from telegram import Update
from telegram.ext import ContextTypes

from .. import __version__
from ..logging_utils import query_hash
from ..observability import new_correlation_id
from ..security.decorators import rate_limited
from ..sources.rnp import get_rnp_client
from ..sources.tse import SearchSession, search_session, select_from_session
from ..storage.audit import record_audit
from ..validation import detect_plate, sanitize_user_error, validate_name_query
from .formatting import (
    _build_choices_keyboard,
    _choices_header,
    _format_person,
    _format_vehicle,
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
    await update.message.reply_text(
        f"*BuscaMaes* v{__version__}\n\n"
        "*Búsqueda de personas (TSE):*\n"
        "Escribí un nombre o usa /buscar \\<nombre\\>\n"
        "*Formato:* `nombre apellido1 apellido2`\n\n"
        "*Búsqueda de vehículos (RNP):*\n"
        "Escribí la placa del vehículo o usa /placa \\<placa\\>\n"
        "*Formatos válidos:*\n"
        "  - Auto: `621335` o `BJV123`\n"
        "  - Moto: `621335` o `MOT621335` o `M621ABC`\n"
        "  - Carga: `CL123456`\n\n"
        "*Comandos:*\n"
        "/buscar \\<nombre\\> — buscar persona\n"
        "/placa \\<placa\\> — buscar vehículo\n"
        "/start — bienvenida\n"
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
        from ..settings import get_settings

        settings = get_settings()
        if not settings.rnp_email or not settings.rnp_password:
            await msg.edit_text("❌ Búsqueda de vehículos no disponible.")
            return

        client = get_rnp_client()
        vehicle = await client.query_plate(plate_query.class_code, plate_query.car_number)

        if not vehicle.marca:
            await msg.edit_text("No se encontró el vehículo.")
            await record_audit(
                user_id=user_id,
                action="plate_search",
                query_hash=query_hash(plate_query.raw),
                result="no_results",
            )
            return

        await msg.edit_text(_format_vehicle(vehicle), parse_mode="Markdown")
        await record_audit(
            user_id=user_id,
            action="plate_search",
            query_hash=query_hash(plate_query.raw),
            result="ok",
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
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Por favor ingrese al menos un nombre.")
        return

    # Single word: try plate first, reject if no match
    if " " not in text:
        plate_query = detect_plate(text)
        if plate_query:
            await _do_plate_search(update, plate_query)
            return
        await update.message.reply_text(
            "Formato no reconocido. Escribí un nombre (2+ palabras) o una placa válida. Vea /help"
        )
        return

    # Multi-word: name search
    await _do_search(update, text)
