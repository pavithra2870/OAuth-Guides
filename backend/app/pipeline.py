"""The research agent: find sources, read them, write the guide, verify it.

`run(query)` is an async generator of `(event, data)` pairs that the API streams
to the browser:

    progress  {stage, status: running|done|failed, message}
    source    {id, url, title, kind}        one per page the agent will read
    guide     {...full Guide...}            the finished, verified guide
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import AsyncIterator
from urllib.parse import urlparse

from pydantic import ValidationError

from . import llm, search
from .catalog import normalize, resolve
from .config import get_settings
from .prompts import SYSTEM, build_user_prompt, repair_prompt
from .schemas import ComposioStatus, Guide, GuideDraft, Meta, Source, Step
from .verify import SourceDoc, build_timeline, is_official, verify

log = logging.getLogger("pipeline")

QUERIES = [
    "{app} API OAuth 2.0 register developer app credentials",
    "{app} OAuth app review approval requirements production access",
    "{app} developer app approval how long review rejected",
    "{app} API scopes verification requirements developer policy",
]

DEEP_QUERIES = [
    "{app} app review process how long it takes extended quota production access",
    "{app} app registration requirements policy approval",
]

Event = tuple[str, dict]


class PipelineError(Exception):
    """A failure whose message is safe to show to the user."""


def _progress(stage: str, status: str, message: str) -> Event:
    return "progress", {"stage": stage, "status": status, "message": message}


def _base_domain(host: str) -> str:
    parts = host.lower().removeprefix("www.").split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _brand_tokens(name: str, website: str | None) -> set[str]:
    tokens = {normalize(name), normalize(name.split()[0])}
    if website:
        tokens.add(normalize(website.split(".")[0]))
    return {t for t in tokens if t}


def _mentions_app(hit: search.SearchHit, tokens: set[str]) -> bool:
    haystack = normalize(f"{hit.title} {hit.url} {hit.snippet}")
    return any(len(t) >= 4 and t in haystack for t in tokens)


def _choose(hits: list[search.SearchHit], tokens: set[str], base_domain: str | None, limit: int) -> list[tuple[search.SearchHit, str]]:
    """Rank hits: official sources first, plus a couple of community ones that are actually about the app."""
    seen: set[str] = set()
    official: list[search.SearchHit] = []
    community: list[search.SearchHit] = []
    for hit in sorted(hits, key=lambda h: -h.score):
        key = hit.url.split("#")[0].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        if is_official(hit.url, tokens, base_domain):
            official.append(hit)
        elif _mentions_app(hit, tokens):
            community.append(hit)
    chosen = [(h, "official") for h in official[: limit - min(2, len(community))]]
    chosen += [(h, "community") for h in community[: max(2, limit - len(chosen))]]
    return chosen[:limit]


_BUILD_STEP = re.compile(r"^(develop|build|implement|code|create your (app|product|integration))\b|integration code", re.I)


def _drop_build_steps(steps: list[Step]) -> list[Step]:
    """Models like to add 'Develop and test your app (1-2 weeks)'. That's the developer's own
    product work, not part of getting an OAuth app approved, and it wrecks the time estimate."""
    kept = []
    for step in steps:
        _, high = step.duration.minutes()
        if step.owner != "provider" and high >= 480 and _BUILD_STEP.search(step.title):
            log.info("dropped build step: %r", step.title)
            continue
        kept.append(step)
    return kept


def _parse_draft(text: str) -> GuideDraft:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object found")
    return GuideDraft.model_validate_json(text[start : end + 1])


async def _write_draft(app_name: str, docs: list[SourceDoc]) -> tuple[GuideDraft, llm.LLMResult]:
    last_error = ""
    for attempt in range(2):
        def prompt(budget: int | None, note: str = last_error) -> str:
            text = build_user_prompt(app_name, docs, budget)
            return f"{text}\n\n{repair_prompt(note)}" if note else text

        result = await llm.generate_json(SYSTEM, prompt)
        try:
            return _parse_draft(result.text), result
        except (ValueError, ValidationError) as exc:
            last_error = str(exc)
            log.warning("draft attempt %d invalid: %s", attempt + 1, last_error[:200])
    raise PipelineError("The model returned a guide we couldn't read. Please try again.")


async def run(query: str) -> AsyncIterator[Event]:
    settings = get_settings()
    target = resolve(query)
    name, website = target["name"], target["website"]
    catalog = target["catalog"]

    yield _progress("resolve", "done", f"Looking into {name}")

    # 1. search ---------------------------------------------------------------
    yield _progress("search", "running", "Searching official docs and developer forums")
    queries = [q.format(app=name) for q in QUERIES]
    base_domain = _base_domain(website) if website else None
    results = await asyncio.gather(
        *(search.search(q, max_results=settings.search_results_per_query) for q in queries),
        return_exceptions=True,
    )
    hits: list[search.SearchHit] = []
    for r in results:
        if isinstance(r, Exception):
            log.warning("search query failed: %s", settings.redact(str(r)))
        else:
            hits.extend(r)
    if not hits:
        raise PipelineError("Search is unavailable right now. Please try again in a minute.")

    tokens = _brand_tokens(name, website)

    # Second hop: now that we know the provider's own domain, search only there
    # for the pages that usually hold the review/approval rules.
    official_hosts = [_base_domain(urlparse(h.url).hostname or "") for h in hits if is_official(h.url, tokens, base_domain)]
    domains = list(dict.fromkeys([d for d in ([base_domain] if base_domain else []) + official_hosts if d]))[:2]
    if domains:
        yield _progress("search", "running", f"Digging into {', '.join(domains)} for review and approval rules")
        deep_queries = [q.format(app=name) for q in DEEP_QUERIES]
        deep = await asyncio.gather(
            *(search.search(q, max_results=settings.search_results_per_query, include_domains=domains) for q in deep_queries),
            return_exceptions=True,
        )
        for r in deep:
            if not isinstance(r, Exception):
                hits.extend(r)
        queries += deep_queries

    chosen = _choose(hits, tokens, base_domain, settings.max_sources)
    yield _progress("search", "done", f"Found {len(hits)} results, reading the {len(chosen)} best")

    # 2. read -----------------------------------------------------------------
    yield _progress("read", "running", "Reading the pages")
    docs: list[SourceDoc] = []
    for i, (hit, kind) in enumerate(chosen, 1):
        yield "source", {"id": f"S{i}", "url": hit.url, "title": hit.title, "kind": kind}
    try:
        pages = {p.url: p.text for p in await search.extract([h.url for h, _ in chosen])}
    except search.SearchError as exc:
        log.warning("extract failed: %s", exc)
        pages = {}
    for i, (hit, kind) in enumerate(chosen, 1):
        text = (pages.get(hit.url) or hit.snippet or "").strip()
        if len(text) < 200 and hit.snippet:
            text = hit.snippet
        if len(text) >= 120:
            docs.append(SourceDoc(f"S{i}", hit.url, hit.title, text[: settings.source_char_limit], kind))
    if not any(d.kind == "official" for d in docs):
        raise PipelineError(f"We couldn't find official developer documentation for {name}. Try its website address instead.")
    yield _progress("read", "done", f"Read {len(docs)} pages")

    # 3. write ----------------------------------------------------------------
    yield _progress("write", "running", "Working out the path, timing and blockers")
    draft, result = await _write_draft(name, docs)
    yield _progress("write", "done", "Draft written")

    # 4. verify ---------------------------------------------------------------
    yield _progress("verify", "running", "Checking every claim against its source")
    draft.steps = _drop_build_steps(draft.steps)
    for i, step in enumerate(draft.steps, 1):
        step.id = f"s{i}"
    stats = verify(draft, {d.id: d for d in docs})
    timeline = build_timeline(draft)

    official_host = next((urlparse(d.url).hostname for d in docs if d.kind == "official"), None)
    domain = base_domain or (_base_domain(official_host) if official_host else None)
    guide = Guide(
        **draft.model_dump(),
        slug=target["slug"],
        app_name=name,
        domain=domain,
        composio=ComposioStatus(**catalog),
        sources=[Source(id=d.id, url=d.url, title=d.title, kind=d.kind) for d in docs],
        timeline=timeline,
        stats=stats,
        meta=Meta(
            researched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            provider=result.provider,
            model=result.model,
            queries=queries,
            pages_read=len(docs),
        ),
    )
    c = stats.counts
    yield _progress("verify", "done", f"{c['documented']} claims confirmed in official docs, {c['inferred']} unconfirmed")
    yield "guide", json.loads(guide.model_dump_json())
