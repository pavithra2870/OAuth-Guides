"""Connectivity checks for every external dependency.

Shared by the `/status` endpoint and `scripts/check_connections.py`.
Checks are free (they list models or query the database) unless
`spend=True`, which also runs one tiny Tavily search per key.
Keys are identified only by label (e.g. "gemini#2"), never by value.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass, field
from typing import Awaitable, Callable

import httpx
import psycopg

from .config import Settings

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
GROQ_BASE = "https://api.groq.com/openai/v1"
TAVILY_BASE = "https://api.tavily.com"


@dataclass
class CheckResult:
    service: str
    label: str
    ok: bool
    detail: str
    latency_ms: int = 0
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _snippet(response: httpx.Response) -> str:
    try:
        message = response.json().get("error", {})
        message = message.get("message") if isinstance(message, dict) else message
    except ValueError:
        message = None
    return (message or response.text or "")[:140].replace("\n", " ")


def _http_failure(response: httpx.Response) -> str:
    return f"HTTP {response.status_code}: {_snippet(response)}"


# --- individual checks ------------------------------------------------------

async def check_gemini(client: httpx.AsyncClient, key: str) -> tuple[bool, str, dict]:
    r = await client.get(f"{GEMINI_BASE}/models", params={"pageSize": 200}, headers={"x-goog-api-key": key})
    if r.status_code != 200:
        return False, _http_failure(r), {}
    models = [
        m["name"].removeprefix("models/")
        for m in r.json().get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]
    return True, f"{len(models)} models can generate content", {"models": models}


async def check_groq(client: httpx.AsyncClient, key: str) -> tuple[bool, str, dict]:
    r = await client.get(f"{GROQ_BASE}/models", headers={"Authorization": f"Bearer {key}"})
    if r.status_code != 200:
        return False, _http_failure(r), {}
    models = sorted(m["id"] for m in r.json().get("data", []))
    return True, f"{len(models)} models available", {"models": models}


async def check_tavily(client: httpx.AsyncClient, key: str, spend: bool) -> tuple[bool, str, dict]:
    headers = {"Authorization": f"Bearer {key}"}
    if spend:
        body = {"query": "OAuth app registration", "max_results": 1, "search_depth": "basic"}
        r = await client.post(f"{TAVILY_BASE}/search", json=body, headers=headers)
        if r.status_code != 200:
            return False, _http_failure(r), {}
        return True, "search works (spent 1 credit)", {}
    r = await client.get(f"{TAVILY_BASE}/usage", headers=headers)
    if r.status_code == 200:
        return True, "key accepted", {}
    if r.status_code in (401, 403):
        return False, _http_failure(r), {}
    return True, "not probed (no free endpoint); run with --spend to verify", {"probed": False}


def _check_database_sync(url: str, timeout: float) -> tuple[bool, str, dict]:
    with psycopg.connect(url, connect_timeout=int(timeout)) as conn:
        version = conn.execute("select version()").fetchone()[0]
    return True, version.split(" on ")[0], {}


def _check_sqlite_sync() -> tuple[bool, str, dict]:
    from . import db

    db.open_pool()
    with db.sqlite_conn() as conn:
        version = conn.execute("select sqlite_version()").fetchone()[0]
    return True, f"local SQLite {version} (DATABASE_URL not set)", {}


# --- runner -----------------------------------------------------------------

async def _run(
    settings: Settings,
    service: str,
    label: str,
    fn: Callable[[], Awaitable[tuple[bool, str, dict]]],
) -> CheckResult:
    started = time.perf_counter()
    try:
        ok, detail, extra = await asyncio.wait_for(fn(), timeout=settings.check_timeout)
    except asyncio.TimeoutError:
        ok, detail, extra = False, f"timed out after {settings.check_timeout:g}s", {}
    except httpx.HTTPError as exc:
        ok, detail, extra = False, f"network error: {type(exc).__name__}", {}
    except Exception as exc:  # noqa: BLE001 - report any failure, never crash the run
        ok, detail, extra = False, f"{type(exc).__name__}: {str(exc)[:140]}", {}
    return CheckResult(
        service=service,
        label=label,
        ok=ok,
        detail=settings.redact(detail),
        latency_ms=int((time.perf_counter() - started) * 1000),
        extra=extra,
    )


async def run_all(settings: Settings, spend: bool = False) -> list[CheckResult]:
    timeout = httpx.Timeout(settings.http_read_timeout, connect=settings.http_connect_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        jobs = []
        for i, key in enumerate(settings.gemini_keys, 1):
            jobs.append(_run(settings, "gemini", f"gemini#{i}", lambda k=key: check_gemini(client, k)))
        for i, key in enumerate(settings.groq_keys, 1):
            jobs.append(_run(settings, "groq", f"groq#{i}", lambda k=key: check_groq(client, k)))
        for i, key in enumerate(settings.tavily_keys, 1):
            jobs.append(_run(settings, "tavily", f"tavily#{i}", lambda k=key: check_tavily(client, k, spend)))
        if settings.database_url:
            jobs.append(
                _run(
                    settings,
                    "database",
                    "postgres",
                    lambda: asyncio.to_thread(
                        _check_database_sync, settings.database_url, settings.http_connect_timeout * 2
                    ),
                )
            )
        else:
            jobs.append(_run(settings, "database", "sqlite", lambda: asyncio.to_thread(_check_sqlite_sync)))
        return list(await asyncio.gather(*jobs))


def _missing(message: str) -> Callable[[], Awaitable[tuple[bool, str, dict]]]:
    async def fail() -> tuple[bool, str, dict]:
        return False, message, {}

    return fail
