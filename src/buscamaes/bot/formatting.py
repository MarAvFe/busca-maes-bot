from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..sources.tse import TSE_SEARCH_URL, PersonResult, SearchSession

MAX_CHOICES = 5


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
