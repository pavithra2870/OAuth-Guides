"""Server-Sent Events helpers: formatting, heartbeats and a hard deadline.

Wrap any async generator of SSE strings with `guarded_stream` so that:
  * a comment heartbeat is sent while the source is quiet (keeps proxies from
    closing the connection),
  * the whole stream stops with a `timeout` error event after `deadline` seconds,
  * an exception in the source becomes a clean `error` event,
  * the source is cancelled if the client disconnects.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import AsyncIterator

from fastapi.responses import StreamingResponse

log = logging.getLogger("stream")

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # disable proxy buffering (nginx-style proxies)
}


def sse(event: str, data: dict | str) -> str:
    """Format one SSE message."""
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


_DONE = object()


async def guarded_stream(
    source: AsyncIterator[str], *, heartbeat: float, deadline: float
) -> AsyncIterator[str]:
    queue: asyncio.Queue = asyncio.Queue()

    async def pump() -> None:
        try:
            async for chunk in source:
                await queue.put(chunk)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("stream source failed")
            await queue.put(sse("error", {"code": "internal", "message": "Something went wrong."}))
        finally:
            await queue.put(_DONE)

    task = asyncio.create_task(pump())
    loop = asyncio.get_running_loop()
    end = loop.time() + deadline
    try:
        while True:
            remaining = end - loop.time()
            if remaining <= 0:
                yield sse("error", {"code": "timeout", "message": f"Stopped after {deadline:g}s."})
                break
            try:
                item = await asyncio.wait_for(queue.get(), timeout=min(heartbeat, remaining))
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
                continue
            if item is _DONE:
                break
            yield item
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task


def sse_response(source: AsyncIterator[str], *, heartbeat: float, deadline: float) -> StreamingResponse:
    return StreamingResponse(
        guarded_stream(source, heartbeat=heartbeat, deadline=deadline),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
