"""Structured logging + correlation IDs + Sentry init.

correlation_id is a contextvars.ContextVar so each async telegram update
has its own ID without explicit thread-local plumbing. The logging filter
injects it onto every LogRecord; the JSON formatter emits it as a field.
"""

import logging
import os
import uuid
from contextvars import ContextVar

from pythonjsonlogger import jsonlogger

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


def new_correlation_id() -> str:
    cid = uuid.uuid4().hex[:12]
    correlation_id.set(cid)
    return cid


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id.get()
        return True


def configure_logging(level: str) -> None:
    """Replace root handlers with a single JSON stream handler.

    Format: {"timestamp": ..., "level": ..., "logger": ..., "message": ...,
             "correlation_id": ...}
    """
    handler = logging.StreamHandler()
    handler.addFilter(CorrelationIdFilter())
    handler.setFormatter(
        jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(correlation_id)s",
            rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def configure_sentry() -> bool:
    """Init Sentry if SENTRY_DSN is set. Return True if initialized."""
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=0.0,
        send_default_pii=False,
        release=_release_tag(),
    )
    return True


def _release_tag() -> str:
    from . import __version__

    return f"buscamaes@{__version__}"
