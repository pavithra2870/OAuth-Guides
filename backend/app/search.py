"""Tavily client (search + page extraction) with key rotation."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from .config import get_settings
from .keys import KeyPool

log = logging.getLogger("search")

TAVILY_BASE = "https://api.tavily.com"
_KEY_PROBLEM = {401, 403, 429, 432, 433}  # bad key, rate limit, plan limit

_pool: KeyPool | None = None


class SearchError(Exception):
    """Tavily could not serve the request with any key."""


@dataclass
class SearchHit:
    url: str
    title: str
    snippet: str
    score: float


@dataclass
class Page:
    url: str
    text: str


def _keys() -> KeyPool:
    global _pool
    if _pool is None:
        _pool = KeyPool("tavily", get_settings().tavily_keys)
    return _pool


async def _post(path: str, body: dict, timeout: float) -> dict:
    settings = get_settings()
    pool = _keys()
    if not len(pool):
        raise SearchError("no Tavily keys configured")
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=settings.http_connect_timeout)) as client:
        for label, key in pool.candidates():
            try:
                r = await client.post(f"{TAVILY_BASE}{path}", json=body, headers={"Authorization": f"Bearer {key}"})
            except httpx.HTTPError as exc:
                errors.append(f"{label}: {type(exc).__name__}")
                pool.penalize(label, 20)
                continue
            if r.status_code == 200:
                return r.json()
            if r.status_code in _KEY_PROBLEM:
                pool.penalize(label, 600 if r.status_code != 429 else 60)
                errors.append(f"{label}: HTTP {r.status_code}")
                continue
            raise SearchError(settings.redact(f"HTTP {r.status_code}: {r.text[:140]}"))
    raise SearchError(settings.redact("; ".join(errors)))


async def search(query: str, *, max_results: int = 5, include_domains: list[str] | None = None) -> list[SearchHit]:
    body: dict = {"query": query, "max_results": max_results, "search_depth": "basic"}
    if include_domains:
        body["include_domains"] = include_domains
    data = await _post("/search", body, timeout=25)
    return [
        SearchHit(r["url"], r.get("title", ""), r.get("content", ""), float(r.get("score", 0)))
        for r in data.get("results", [])
    ]


async def extract(urls: list[str]) -> list[Page]:
    """Fetch the readable text of pages. Pages that fail to load are skipped."""
    if not urls:
        return []
    data = await _post("/extract", {"urls": urls, "extract_depth": "basic"}, timeout=40)
    return [Page(r["url"], r.get("raw_content", "")) for r in data.get("results", []) if r.get("raw_content")]
