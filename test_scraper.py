"""Run this standalone to test the scraper without the bot.

Usage:
    python test_scraper.py [nombre] [apellido1] [apellido2]

Example:
    python test_scraper.py juan mora fernandez
"""
import asyncio
import logging
import sys

logging.basicConfig(level=logging.WARNING)  # suppress httpx noise

from urllib.parse import unquote

import httpx
from bs4 import BeautifulSoup

from tse_scraper import BASE, HEADERS, _extract_viewstate, _parse_delta, search_person


def _args() -> tuple[str, str, str]:
    parts = sys.argv[1:]
    if len(parts) == 0:
        print("Usage: python test_scraper.py <nombre> [apellido1] [apellido2]")
        sys.exit(1)
    nombre = parts[0]
    apellido1 = parts[1] if len(parts) > 1 else ""
    apellido2 = parts[2] if len(parts) > 2 else ""
    return nombre, apellido1, apellido2


async def dump_resultado_html(nombre: str, apellido1: str, apellido2: str) -> None:
    """Fetch resultado_persona.aspx and print raw table rows for parser debugging."""
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=30) as client:
        resp = await client.get(f"{BASE}/consulta_nombres.aspx")
        soup = BeautifulSoup(resp.text, "lxml")
        vs = _extract_viewstate(soup)

        resp = await client.post(
            f"{BASE}/consulta_nombres.aspx",
            data={
                "ScriptManager1": "UpdatePanel1|btnConsultarNombre",
                **vs,
                "txtnombre": nombre,
                "txtapellido1": apellido1,
                "txtapellido2": apellido2,
                "referencia": "",
                "observacion": "",
                "__ASYNCPOST": "true",
                "btnConsultarNombre": "Consultar",
            },
            headers={
                **HEADERS,
                "X-MicrosoftAjax": "Delta=true",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
        )
        delta = _parse_delta(resp.text)
        redirect_path = unquote(delta.get("pageRedirect:", ""))
        if not redirect_path:
            print("No results found.")
            return

        muestra_url = f"https://servicioselectorales.tse.go.cr{redirect_path}"
        resp = await client.get(muestra_url)
        soup = BeautifulSoup(resp.text, "lxml")
        vs = _extract_viewstate(soup)

        resp = await client.post(
            muestra_url,
            data={**vs, "chk1$0": "on", "Button1": "Realizar consulta"},
        )
        soup = BeautifulSoup(resp.text, "lxml")
        for tr in soup.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if any(cells):
                print(cells)


async def main() -> None:
    nombre, apellido1, apellido2 = _args()

    print(f"=== Parsed result for: {nombre} {apellido1} {apellido2} ===")
    result = await search_person(nombre, apellido1, apellido2)
    if result:
        print(f"Cedula:            {result.cedula}")
        print(f"Nombre:            {result.nombre}")
        print(f"Conocido/a como:   {result.conocido_como}")
        print(f"Fecha nacimiento:  {result.fecha_nacimiento}")
        print(f"Edad:              {result.edad}")
        print(f"Nacionalidad:      {result.nacionalidad}")
        print(f"Padre:             {result.padre}")
        print(f"Madre:             {result.madre}")
    else:
        print("No result found.")

    print("\n=== Raw table rows from resultado_persona.aspx ===")
    await dump_resultado_html(nombre, apellido1, apellido2)


asyncio.run(main())
