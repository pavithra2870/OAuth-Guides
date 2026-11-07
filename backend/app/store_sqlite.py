"""SQLite twin of the Postgres storage in store.py, for easy local setup (no Supabase needed).

Same functions, same return shapes. Used automatically when DATABASE_URL is empty.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from . import db

STALE_RUN = timedelta(minutes=5)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ago(iso: str | None) -> timedelta | None:
    return None if not iso else datetime.now(timezone.utc) - datetime.fromisoformat(iso)


def _row(raw) -> dict | None:
    if raw is None:
        return None
    row = dict(raw)
    row["content"] = json.loads(row["content"]) if row.get("content") else None
    return row


def _get(slug: str) -> dict | None:
    with db.sqlite_conn() as conn:
        return _row(conn.execute("select * from guides where slug = ?", (slug,)).fetchone())


def _list() -> list[dict]:
    with db.sqlite_conn() as conn:
        rows = conn.execute(
            "select slug, app_name, source, content, updated_at from guides "
            "where status = 'ready' and content is not null order by app_name collate nocase"
        ).fetchall()
    return [_row(r) for r in rows]


def _claim(slug: str, app_name: str, website: str | None, fresh_days: float):
    with db.sqlite_conn() as conn:
        conn.execute("begin immediate")  # one writer at a time: the claim is atomic
        try:
            row = _row(conn.execute("select * from guides where slug = ?", (slug,)).fetchone())
            if row is None:
                now = _now()
                conn.execute(
                    "insert into guides (slug, app_name, website, source, status, claimed_at, created_at, updated_at) "
                    "values (?, ?, ?, 'generated', 'generating', ?, ?, ?)",
                    (slug, app_name, website, now, now, now),
                )
                outcome, result = "claimed", None
            else:
                age, run_age = _ago(row["updated_at"]), _ago(row["claimed_at"])
                fresh = row["status"] != "generating" and age is not None and age < timedelta(days=fresh_days)
                if row["content"] is not None and (row["source"] == "curated" or fresh):
                    outcome, result = "cached", row
                elif row["status"] == "generating" and run_age is not None and run_age < STALE_RUN:
                    outcome, result = "in_progress", row
                else:
                    conn.execute(
                        "update guides set status = 'generating', claimed_at = ?, error = null where slug = ?",
                        (_now(), slug),
                    )
                    outcome, result = "claimed", row
            conn.execute("commit")
            return outcome, result
        except Exception:
            conn.execute("rollback")
            raise


def _save_ready(slug: str, guide: dict) -> None:
    with db.sqlite_conn() as conn:
        conn.execute(
            "update guides set content = ?, status = 'ready', error = null, app_name = ?, "
            "website = coalesce(?, website), updated_at = ? where slug = ?",
            (json.dumps(guide), guide["app_name"], guide.get("domain"), _now(), slug),
        )


def _save_failed(slug: str, error: str) -> None:
    with db.sqlite_conn() as conn:
        conn.execute(
            "update guides set status = case when content is null then 'failed' else 'ready' end, error = ? "
            "where slug = ?",
            (error[:300], slug),
        )


def _record_event(ip_hash: str, slug: str) -> None:
    with db.sqlite_conn() as conn:
        conn.execute("insert into generation_events (ip_hash, slug, created_at) values (?, ?, ?)", (ip_hash, slug, _now()))


def _counts(ip_hash: str) -> tuple[int, int]:
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    with db.sqlite_conn() as conn:
        row = conn.execute(
            "select coalesce(sum(ip_hash = ?), 0), count(*) from generation_events where created_at > ?",
            (ip_hash, since),
        ).fetchone()
    return int(row[0]), int(row[1])


def _upsert(guide: dict, origin: str) -> None:
    now = _now()
    with db.sqlite_conn() as conn:
        conn.execute(
            "insert into guides (slug, app_name, website, source, status, content, created_at, updated_at) "
            "values (?, ?, ?, ?, 'ready', ?, ?, ?) "
            "on conflict (slug) do update set app_name = excluded.app_name, website = excluded.website, "
            "source = excluded.source, status = 'ready', content = excluded.content, error = null, updated_at = excluded.updated_at",
            (guide["slug"], guide["app_name"], guide.get("domain"), origin, json.dumps(guide), now, now),
        )


def _delete(slug: str) -> int:
    with db.sqlite_conn() as conn:
        return conn.execute("delete from guides where slug = ?", (slug,)).rowcount


def _count() -> int:
    with db.sqlite_conn() as conn:
        return conn.execute("select count(*) from guides").fetchone()[0]
