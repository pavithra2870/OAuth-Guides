"""Guide endpoints: library, single guide, and the live generate stream."""
from __future__ import annotations

import hashlib
import re
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from .. import db, jobs, store
from ..catalog import resolve
from ..config import get_settings
from ..streaming import sse, sse_response

router = APIRouter(prefix="/api", tags=["guides"])

_ALLOWED = re.compile(r"[^\w .&+'/:@-]")


def _require_db() -> None:
    if not db.available():
        raise HTTPException(503, "Guide storage is not configured.")


def _clean(query: str) -> str:
    return re.sub(r"\s+", " ", _ALLOWED.sub("", query)).strip()


def _summary(row: dict) -> dict:
    guide = row["content"]
    return {
        "slug": row["slug"],
        "app_name": row["app_name"],
        "domain": guide.get("domain"),
        "origin": row["source"],
        "difficulty": guide["difficulty"]["level"],
        "headline": guide["difficulty"].get("headline", ""),
        "segments": guide["timeline"]["segments"],
        "hands_on": guide["timeline"]["hands_on"],
        "waiting": guide["timeline"]["waiting"],
        "agent_share": guide["timeline"]["agent_share"],
        "composio": guide["composio"]["status"],
        "confidence": guide["stats"]["confidence"],
        "researched_at": guide["meta"]["researched_at"],
    }


def _ip_hash(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    ip = forwarded or (request.client.host if request.client else "unknown")
    return hashlib.sha256(f"oauth-guides:{ip}".encode()).hexdigest()[:16]


class GenerateRequest(BaseModel):
    query: str = Field(min_length=2, max_length=120)

    @field_validator("query")
    @classmethod
    def _sanitize(cls, value: str) -> str:
        cleaned = _clean(value)
        if len(cleaned) < 2:
            raise ValueError("Enter an app name or website.")
        return cleaned


@router.get("/guides")
async def list_guides() -> dict:
    _require_db()
    return {"guides": [_summary(r) for r in await store.list_guides()]}


@router.get("/guides/{slug}")
async def get_guide(slug: str) -> dict:
    _require_db()
    row = await store.get_guide(slug.lower())
    if not row or row["content"] is None:
        raise HTTPException(404, "No guide for this app yet.")
    return {"guide": row["content"], "origin": row["source"], "status": row["status"]}


@router.get("/resolve")
async def resolve_app(q: str) -> dict:
    """What would we do for this input? Used by the search box before generating."""
    _require_db()
    target = resolve(_clean(q))
    row = await store.get_guide(target["slug"])
    return {
        "slug": target["slug"],
        "name": target["name"],
        "composio": target["catalog"]["status"],
        "has_guide": bool(row and row["content"] is not None),
    }


@router.post("/generate")
async def generate(body: GenerateRequest, request: Request):
    """Stream a guide: instantly if cached, otherwise researched live."""
    _require_db()
    settings = get_settings()
    target = resolve(body.query)
    slug, name = target["slug"], target["name"]
    ip_hash = _ip_hash(request)

    async def source() -> AsyncIterator[str]:
        yield sse("resolved", {"slug": slug, "name": name, "composio": target["catalog"]["status"]})

        # Daily caps protect the free-tier keys. They apply only to brand-new research,
        # never to guides we already have or runs that are already in progress.
        existing = await store.get_guide(slug)
        has_guide = bool(existing and existing["content"] is not None)
        if not has_guide and jobs.get(slug) is None:
            mine, total = await store.usage_today(ip_hash)
            if mine >= settings.daily_cap_per_ip or total >= settings.daily_cap_global:
                yield sse("error", {"code": "rate_limited",
                                    "message": "Daily limit for live research reached. Browse the library, or try again tomorrow."})
                return

        outcome, row = await store.claim(slug, name, target["website"], settings.guide_fresh_days)

        if outcome == "cached":
            yield sse("guide", row["content"])
            yield sse("done", {"cached": True})
            return

        if outcome == "claimed":
            await store.record_event(ip_hash, slug)
            job = jobs.start(slug, body.query)
        else:  # in_progress: join the run that is already going
            job = jobs.get(slug)
            if job is None:
                yield sse("error", {"code": "busy", "message": "This app is being researched. Try again in a moment."})
                return

        async for event, data in job.subscribe():
            yield sse(event, data)
        yield sse("done", {"cached": False})

    return sse_response(source(), heartbeat=settings.sse_heartbeat, deadline=settings.generation_deadline)
