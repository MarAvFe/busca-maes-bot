"""SQLite audit log. Stores query hashes only — never raw text.

Schema:
    audit(id, ts, user_id, action, query_hash, correlation_id, result)

Connection model: one shared aiosqlite connection opened at startup,
closed at shutdown. SQLite WAL mode handles concurrent writes from
asyncio tasks at this scale (~100 users).
"""

import asyncio
import logging
import os
from typing import Any

import aiosqlite

from ..observability import correlation_id
from ..settings import get_settings

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    query_hash TEXT,
    correlation_id TEXT,
    result TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit(ts);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit(user_id);
"""

_conn: aiosqlite.Connection | None = None


async def init_db() -> None:
    """Open connection, ensure schema. Called once at startup."""
    global _conn
    s = get_settings()
    os.makedirs(os.path.dirname(s.audit_db_path) or ".", exist_ok=True)
    _conn = await aiosqlite.connect(s.audit_db_path)
    await _conn.execute("PRAGMA journal_mode=WAL")
    await _conn.executescript(_SCHEMA)
    await _conn.commit()
    logger.info("Audit DB ready path=%s", s.audit_db_path)


async def close_db() -> None:
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None


async def record_audit(
    *,
    user_id: int,
    action: str,
    query_hash: str | None,
    result: str,
) -> None:
    """Insert one audit row. Silently no-ops if DB not initialized (test mode)."""
    if _conn is None:
        return
    cid = correlation_id.get()
    try:
        await _conn.execute(
            "INSERT INTO audit (user_id, action, query_hash, correlation_id, result)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, action, query_hash, cid, result),
        )
        await _conn.commit()
    except Exception:
        # Never let audit failure break a user-facing request.
        logger.exception("Audit write failed action=%s", action)


async def cleanup_old(retention_days: int) -> int:
    """Delete rows older than retention_days. Return number of rows deleted."""
    if _conn is None:
        return 0
    cur = await _conn.execute(
        "DELETE FROM audit WHERE ts < datetime('now', ?)",
        (f"-{retention_days} days",),
    )
    await _conn.commit()
    deleted = cur.rowcount or 0
    await cur.close()
    if deleted:
        logger.info("Audit cleanup deleted=%d", deleted)
    return deleted


async def cleanup_loop() -> None:
    """Background task: run cleanup once a day."""
    s = get_settings()
    while True:
        try:
            await cleanup_old(s.audit_retention_days)
        except Exception:
            logger.exception("Cleanup loop iteration failed")
        await asyncio.sleep(24 * 60 * 60)


# Test helper: expose row count
async def _count_rows() -> int:
    if _conn is None:
        return 0
    cur = await _conn.execute("SELECT COUNT(*) FROM audit")
    row: Any = await cur.fetchone()
    await cur.close()
    return int(row[0])
