"""Run this standalone to test the scraper without the bot."""
import asyncio
import logging

logging.basicConfig(level=logging.WARNING)  # suppress httpx noise

import httpx
from bs4 import BeautifulSoup
from urllib.parse import unquote
from tse_scraper import search_person, BASE, HEADERS, _extract_viewstate, _parse_delta


async def dump_resultado_html():
    """Fetch resultado_persona.aspx and print the raw HTML for parser debugging."""
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=30) as client:
        resp = await client.get(f"{BASE}/consulta_nombres.aspx")
        soup = BeautifulSoup(resp.text, "lxml")
        vs = _extract_viewstate(soup)

        resp = await client.post(
            f"{BASE}/consulta_nombres.aspx",
            data={
                "ScriptManager1": "UpdatePanel1|btnConsultarNombre",
                **vs,
                "txtnombre": "ignacio",
                "txtapellido1": "avila",
                "txtapellido2": "feoli",
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
        muestra_url = f"https://servicioselectorales.tse.go.cr{redirect_path}"

        resp = await client.get(muestra_url)
        soup = BeautifulSoup(resp.text, "lxml")
        vs = _extract_viewstate(soup)

        resp = await client.post(
            muestra_url,
            data={**vs, "chk1$0": "on", "Button1": "Realizar consulta"},
        )
        # Print the resultado_persona.aspx HTML
        soup = BeautifulSoup(resp.text, "lxml")
        # Only print table rows so it's readable
        for tr in soup.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if any(cells):
                print(cells)


async def main():
    print("=== Parsed result ===")
    result = await search_person("ignacio", "avila", "feoli")
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
    await dump_resultado_html()


asyncio.run(main())
