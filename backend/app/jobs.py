"""In-flight generation jobs.

A generation runs as a background task, independent of any browser connection:
if the visitor closes the tab the guide still finishes and is saved. Anyone who
asks for the same app meanwhile joins the same job and sees the same events.
"""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from . import llm, pipeline, store
from .config import get_settings

log = logging.getLogger("jobs")

Event = tuple[str, dict]


class Job:
    def __init__(self, slug: str) -> None:
        self.slug = slug
        self.events: list[Event] = []
        self._subscribers: set[asyncio.Queue] = set()
        self.done = False

    def publish(self, event: str, data: dict) -> None:
        self.events.append((event, data))
        for queue in self._subscribers:
            queue.put_nowait((event, data))

    def finish(self) -> None:
        self.done = True
        for queue in self._subscribers:
            queue.put_nowait(None)

    async def subscribe(self) -> AsyncIterator[Event]:
        """Replay everything so far, then follow live until the job ends."""
        queue: asyncio.Queue = asyncio.Queue()
        for item in self.events:  # no await between replay and registering: nothing can be missed
            queue.put_nowait(item)
        if self.done:
            queue.put_nowait(None)
        else:
            self._subscribers.add(queue)
        try:
            while (item := await queue.get()) is not None:
                yield item
        finally:
            self._subscribers.discard(queue)


_jobs: dict[str, Job] = {}


def get(slug: str) -> Job | None:
    return _jobs.get(slug)


def start(slug: str, query: str) -> Job:
    job = Job(slug)
    _jobs[slug] = job
    task = asyncio.create_task(_run(job, query))
    task.add_done_callback(lambda _t: _jobs.pop(slug, None))
    return job


async def _run(job: Job, query: str) -> None:
    settings = get_settings()

    async def body() -> None:
        guide = None
        async for event, data in pipeline.run(query):
            if event == "guide":
                guide = data
            else:
                job.publish(event, data)
        await store.save_ready(job.slug, guide)
        job.publish("guide", guide)

    try:
        await asyncio.wait_for(body(), timeout=settings.generation_deadline + 30)
    except pipeline.PipelineError as exc:
        await _fail(job, "failed", str(exc))
    except llm.LLMError:
        await _fail(job, "busy", "The AI service is busy right now. Please try again in a minute.")
    except asyncio.TimeoutError:
        await _fail(job, "timeout", "This is taking longer than expected. Please try again.")
    except Exception:  # noqa: BLE001
        log.exception("generation crashed for %s", job.slug)
        await _fail(job, "internal", "Something went wrong while researching this app.")
    finally:
        job.finish()


async def _fail(job: Job, code: str, message: str) -> None:
    try:
        await store.save_failed(job.slug, message)
    except Exception:  # noqa: BLE001
        log.exception("could not record failure for %s", job.slug)
    job.publish("error", {"code": code, "message": message})
