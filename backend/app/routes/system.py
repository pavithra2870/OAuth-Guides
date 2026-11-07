"""Operational endpoints: liveness, dependency status and a streaming self-test."""
from __future__ import annotations

import asyncio
import time
from typing import AsyncIterator

from fastapi import APIRouter

from ..checks import run_all
from ..config import get_settings
from ..streaming import sse, sse_response

router = APIRouter(tags=["system"])

_status_cache: tuple[float, dict] | None = None
_status_lock = asyncio.Lock()


@router.get("/health")
async def health() -> dict:
    """Liveness only: cheap, no dependencies. Used to wake the server up."""
    return {"ok": True}


@router.get("/status")
async def status(refresh: bool = False) -> dict:
    """Checks every external dependency. Cached briefly; free (spends no credits)."""
    global _status_cache
    settings = get_settings()
    async with _status_lock:
        now = time.monotonic()
        if not refresh and _status_cache and now - _status_cache[0] < settings.status_cache_ttl:
            return _status_cache[1]
        results = await run_all(settings, spend=False)
        by_service: dict[str, list[dict]] = {}
        for r in results:
            by_service.setdefault(r.service, []).append(
                {k: v for k, v in r.to_dict().items() if k != "extra"}
            )
        payload = {
            "ok": all(
                any(c["ok"] for c in checks) for checks in by_service.values()
            ),  # a service is healthy if at least one key works
            "services": by_service,
            "config": settings.public_summary(),
        }
        _status_cache = (now, payload)
        return payload


@router.get("/stream-test")
async def stream_test(steps: int = 5, delay: float = 0.6):
    """Emits a few progress events. Lets the frontend verify streaming end to end."""
    steps = max(1, min(steps, 20))
    delay = max(0.0, min(delay, 5.0))
    settings = get_settings()

    async def source() -> AsyncIterator[str]:
        for i in range(1, steps + 1):
            await asyncio.sleep(delay)
            yield sse("progress", {"step": i, "of": steps, "message": f"Step {i} of {steps}"})
        yield sse("done", {"ok": True})

    return sse_response(source(), heartbeat=settings.sse_heartbeat, deadline=settings.generation_deadline)
