from .client import search_person, search_session, select_from_session
from .models import PersonResult, SearchResult, SearchSession

TSE_SEARCH_URL = "https://servicioselectorales.tse.go.cr/chc/consulta_nombres.aspx"

__all__ = [
    "TSE_SEARCH_URL",
    "PersonResult",
    "SearchResult",
    "SearchSession",
    "search_person",
    "search_session",
    "select_from_session",
]
