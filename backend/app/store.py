"""Guide storage: the library, the cache, and generation claims.

`claim()` decides, atomically, whether a request is served from the cache,
joins a run already in progress, or starts a new run. Only one run per app
can be active at a time (a unique slug plus a row lock enforce this).
"""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Literal

from psycopg.types.json import Jsonb

from . import db, store_sqlite

STALE_RUN = timedelta(minutes=5)

Outcome = Literal["cached", "in_progress", "claimed"]


def _get(slug: str) -> dict | None:
    with db.pool().connection() as conn:
        return conn.execute("select * from guides where slug = %s", (slug,)).fetchone()


def _list() -> list[dict]:
    with db.pool().connection() as conn:
        return conn.execute(
            "select slug, app_name, source, content, updated_at from guides "
            "where status = 'ready' and content is not null order by app_name"
        ).fetchall()


def _claim(slug: str, app_name: str, website: str | None, fresh_days: float) -> tuple[Outcome, dict | None]:
    select = (
        "select *, now() - updated_at as age, now() - claimed_at as run_age "
        "from guides where slug = %s for update"
    )
    with db.pool().connection() as conn:
        row = conn.execute(select, (slug,)).fetchone()
        if row is None:
            inserted = conn.execute(
                "insert into guides (slug, app_name, website, source, status, claimed_at) "
                "values (%s, %s, %s, 'generated', 'generating', now()) on conflict (slug) do nothing returning slug",
                (slug, app_name, website),
            ).fetchone()
            if inserted:
                return "claimed", None
            row = conn.execute(select, (slug,)).fetchone()  # lost a race: someone else just claimed it

        has_content = row["content"] is not None
        if has_content and (row["source"] == "curated" or (row["status"] != "generating" and row["age"] < timedelta(days=fresh_days))):
            return "cached", row
        if row["status"] == "generating" and row["run_age"] is not None and row["run_age"] < STALE_RUN:
            return "in_progress", row
        conn.execute("update guides set status = 'generating', claimed_at = now(), error = null where slug = %s", (slug,))
        return "claimed", row


def _save_ready(slug: str, guide: dict) -> None:
    with db.pool().connection() as conn:
        conn.execute(
            "update guides set content = %s, status = 'ready', error = null, app_name = %s, "
            "website = coalesce(%s, website), updated_at = now() where slug = %s",
            (Jsonb(guide), guide["app_name"], guide.get("domain"), slug),
        )


def _save_failed(slug: str, error: str) -> None:
    # Keep any older content usable: only mark 'failed' if there is nothing to show.
    with db.pool().connection() as conn:
        conn.execute(
            "update guides set status = case when content is null then 'failed' else 'ready' end, error = %s "
            "where slug = %s",
            (error[:300], slug),
        )


def _record_event(ip_hash: str, slug: str) -> None:
    with db.pool().connection() as conn:
        conn.execute("insert into generation_events (ip_hash, slug) values (%s, %s)", (ip_hash, slug))


def _counts(ip_hash: str) -> tuple[int, int]:
    with db.pool().connection() as conn:
        row = conn.execute(
            "select count(*) filter (where ip_hash = %s) as mine, count(*) as total "
            "from generation_events where created_at > now() - interval '24 hours'",
            (ip_hash,),
        ).fetchone()
    return row["mine"], row["total"]


def _upsert(guide: dict, origin: str) -> None:
    with db.pool().connection() as conn:
        conn.execute(
            "insert into guides (slug, app_name, website, source, status, content, updated_at) "
            "values (%s, %s, %s, %s, 'ready', %s, now()) "
            "on conflict (slug) do update set app_name = excluded.app_name, website = excluded.website, "
            "source = excluded.source, status = 'ready', content = excluded.content, error = null, updated_at = now()",
            (guide["slug"], guide["app_name"], guide.get("domain"), origin, Jsonb(guide)),
        )


def _delete(slug: str) -> int:
    with db.pool().connection() as conn:
        return conn.execute("delete from guides where slug = %s", (slug,)).rowcount


def _impl(name: str):
    """The Postgres function, or its SQLite twin when running locally without DATABASE_URL."""
    return getattr(store_sqlite, name) if db.use_sqlite() else globals()[name]


# Async wrappers: the drivers are synchronous, so run them off the event loop.
async def get_guide(slug: str) -> dict | None:
    return await asyncio.to_thread(_impl("_get"), slug)


async def list_guides() -> list[dict]:
    return await asyncio.to_thread(_impl("_list"))


async def claim(slug: str, app_name: str, website: str | None, fresh_days: float) -> tuple[Outcome, dict | None]:
    return await asyncio.to_thread(_impl("_claim"), slug, app_name, website, fresh_days)


async def save_ready(slug: str, guide: dict) -> None:
    await asyncio.to_thread(_impl("_save_ready"), slug, guide)


async def save_failed(slug: str, error: str) -> None:
    await asyncio.to_thread(_impl("_save_failed"), slug, error)


async def record_event(ip_hash: str, slug: str) -> None:
    await asyncio.to_thread(_impl("_record_event"), ip_hash, slug)


async def usage_today(ip_hash: str) -> tuple[int, int]:
    """(runs by this visitor, runs by everyone) in the last 24 hours."""
    return await asyncio.to_thread(_impl("_counts"), ip_hash)


async def upsert_guide(guide: dict, origin: str) -> None:
    await asyncio.to_thread(_impl("_upsert"), guide, origin)


async def delete_guide(slug: str) -> int:
    return await asyncio.to_thread(_impl("_delete"), slug)


async def seed_if_empty(drafts_dir) -> int:
    """Local SQLite mode only: load the bundled library the first time, so setup needs no extra step."""
    import json

    if not db.use_sqlite() or store_sqlite._count() > 0:
        return 0
    files = sorted(drafts_dir.glob("*.json"))
    for path in files:
        await upsert_guide(json.loads(path.read_text(encoding="utf-8")), "generated")
    return len(files)
