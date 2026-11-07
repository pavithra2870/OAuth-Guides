"""Create the tables (safe to run repeatedly). Postgres if DATABASE_URL is set, otherwise local SQLite.

    python backend/scripts/migrate.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db  # noqa: E402
from app.config import get_settings  # noqa: E402

SCHEMA = Path(__file__).resolve().parents[1] / "db" / "schema.sql"


def main() -> int:
    if db.use_sqlite():
        db.open_pool()
        print(f"Local SQLite ready at {db.sqlite_path()}")
        return 0

    import psycopg

    with psycopg.connect(get_settings().database_url, connect_timeout=15) as conn:
        conn.execute(SCHEMA.read_text(encoding="utf-8"))
        tables = conn.execute(
            "select table_name from information_schema.tables "
            "where table_schema = 'public' and table_name in ('guides', 'generation_events') order by 1"
        ).fetchall()
    print("Tables ready:", ", ".join(t[0] for t in tables))
    return 0


if __name__ == "__main__":
    sys.exit(main())
