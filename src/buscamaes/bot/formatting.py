from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..sources.rnp import VehicleResult
from ..sources.tse import TSE_SEARCH_URL, PersonResult, SearchSession

MAX_CHOICES = 5


def _escape_markdown(text: str) -> str:
    """Escape Telegram Markdown v1 special characters."""
    for char in r"*_`[]()+=-{}":
        text = text.replace(char, f"\\{char}")
    return text


def _parse_name_input(text: str) -> tuple[str, str, str]:
    parts = text.strip().split()
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return " ".join(parts[:-2]), parts[-2], parts[-1]


def _parse_name_input_with_fallbacks(text: str) -> list[tuple[str, str, str]]:
    """Generate decompositions of a name query in order of likelihood.

    For "Maria Jose Mora Fernandez" (4 words):
      Primary:  nombre="Maria Jose Mora", apellido1="Fernandez", apellido2=""
      Fallback: nombre="Maria Jose", apellido1="Mora", apellido2="Fernandez"
      Fallback: nombre="Maria", apellido1="Jose Mora", apellido2="Fernandez"

    For "Maria Jose Mora" (3 words):
      Primary:  nombre="Maria Jose", apellido1="Mora", apellido2=""
      Fallback: nombre="Maria", apellido1="Jose", apellido2="Mora"

    For "Maria Mora" (2 words):
      Only:     nombre="Maria", apellido1="Mora", apellido2=""
    """
    parts = text.strip().split()
    if len(parts) <= 2:
        # 1-2 word queries: only one decomposition
        return [_parse_name_input(text)]

    decompositions: list[tuple[str, str, str]] = []

    # Primary: traditional decomposition (rest, penultimate, last)
    primary = _parse_name_input(text)
    decompositions.append(primary)

    # Fallback: all except last word → nome, last word → apel1
    # Avoids duplicating the primary when len==3
    fallback = (" ".join(parts[:-1]), parts[-1], "")
    if fallback != primary:
        decompositions.append(fallback)

    return decompositions


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


def _format_vehicle(v: VehicleResult) -> str:
    """Format vehicle result as single-line summary with escaped Markdown."""
    parts = []
    if v.placa:
        parts.append(f"*{v.placa}*")
    if v.categoria and v.marca and v.estilo:
        categoria = _escape_markdown(v.categoria)
        marca = _escape_markdown(v.marca)
        estilo = _escape_markdown(v.estilo)
        parts.append(f"{categoria} {marca} {estilo}")
    if v.año_fabricacion:
        parts.append(f"({_escape_markdown(v.año_fabricacion)})")
    if v.cilindrada_cc:
        parts.append(f"{_escape_markdown(v.cilindrada_cc)} cc")
    if v.valor_contrato:
        parts.append(f"₡ {_escape_markdown(v.valor_contrato)}")
    if v.propietario_id and v.propietario_nombre:
        pid = _escape_markdown(v.propietario_id)
        pnombre = _escape_markdown(v.propietario_nombre)
        parts.append(f"({pid}) {pnombre}")
    elif v.propietario_id:
        parts.append(f"({_escape_markdown(v.propietario_id)})")

    return " · ".join(parts) if parts else "Sin datos."
