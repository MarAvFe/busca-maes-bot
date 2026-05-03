from dataclasses import dataclass


@dataclass
class SearchResult:
    index: int  # 0-based position → used as chk1$N
    cedula: str
    nombre: str
    fallecido: bool = False


@dataclass
class SearchSession:
    muestra_url: str
    viewstate: dict
    cookies: dict[str, str]
    results: list[SearchResult]  # alive results only (fallecidos filtered)
    total_raw: int  # total count before filter


@dataclass
class PersonResult:
    cedula: str = ""
    nombre: str = ""
    conocido_como: str = ""
    fecha_nacimiento: str = ""
    edad: str = ""
    nacionalidad: str = ""
    padre: str = ""
    madre: str = ""
