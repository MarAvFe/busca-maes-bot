# Backward compatibility shim - import from new location
from src.buscamaes.sources.tse import (
    TSE_SEARCH_URL,
    PersonResult,
    SearchResult,
    SearchSession,
    search_person,
    search_session,
    select_from_session,
)

__all__ = [
    "TSE_SEARCH_URL",
    "PersonResult",
    "SearchResult",
    "SearchSession",
    "search_person",
    "search_session",
    "select_from_session",
]
