"""Database access. Postgres (Supabase) when DATABASE_URL is set, otherwise a local SQLite file.

Sync drivers; callers run them in a thread.
"""
from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import get_settings

log = logging.getLogger("db")

_pool: ConnectionPool | None = None
_sqlite_ready = False

_BACKEND = Path(__file__).resolve().parents[1]


def use_sqlite() -> bool:
    """Local mode: no DATABASE_URL means a SQLite file, no external setup."""
    return not get_settings().database_url


def sqlite_path() -> Path:
    return Path(os.getenv("SQLITE_PATH") or _BACKEND / "data" / "local.db")


@contextmanager
def sqlite_conn():
    conn = sqlite3.connect(sqlite_path(), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _init_sqlite() -> None:
    global _sqlite_ready
    path = sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite_conn() as conn:
        conn.executescript((_BACKEND / "db" / "schema_sqlite.sql").read_text(encoding="utf-8"))
    _sqlite_ready = True
    log.info("using local SQLite database at %s", path)


def open_pool() -> bool:
    """Open the Postgres pool, or prepare the local SQLite file. Returns whether storage is available."""
    global _pool
    url = get_settings().database_url
    if not url:
        if not _sqlite_ready:
            _init_sqlite()
        return True
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=url,
            min_size=1,
            max_size=4,
            max_idle=240,
            timeout=10,
            kwargs={"row_factory": dict_row, "connect_timeout": 10},
            check=ConnectionPool.check_connection,
            open=False,
        )
        _pool.open(wait=False)
    return True


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def pool() -> ConnectionPool:
    if _pool is None:
        raise RuntimeError("database is not configured")
    return _pool


def available() -> bool:
    return _sqlite_ready if use_sqlite() else _pool is not None
