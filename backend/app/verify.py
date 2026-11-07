"""Deterministic evidence checking and derived fields.

The model never decides how trustworthy a claim is. We do:
  documented = its quote appears verbatim in an *official* source we fetched
  reported   = the quote appears, but only in a non-official source
  inferred   = anything else (no quote, quote not found, no valid source)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterator
from urllib.parse import urlparse

from .schemas import Evidence, GuideDraft, Segment, Span, Stats, Timeline

log = logging.getLogger("verify")


@dataclass
class SourceDoc:
    id: str
    url: str
    title: str
    text: str
    kind: str  # official | community

    @property
    def search_text(self) -> str:
        return _flatten(self.text)


def _flatten(text: str) -> str:
    text = text.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def quote_in(quote: str, source: SourceDoc) -> bool:
    """True if every sentence of `quote` appears verbatim in the source.

    Models often join two nearby sentences, or add "..." between them. We split the
    quote into sentences/lines and require each one to be found as-is, so the quote
    can be stitched from real passages but never contain invented text.
    """
    fragments = [f for f in re.split(r"\.\.\.|…|\n|(?<=[.!?])\s+", quote) if len(_flatten(f)) >= 12]
    if not fragments:
        return False
    haystack = source.search_text
    return all(_flatten(f) in haystack for f in fragments)


_USER_CONTENT_HOST = re.compile(r"^(community|forums?|discuss|discussions?|answers|ideas|groups)\.")
_USER_CONTENT_PATH = re.compile(r"/(forum|forums|discussion|discussions|t5|questions|community|pulse|posts|in|feed|groups|company)/", re.I)


def is_official(url: str, brand_tokens: set[str], base_domain: str | None) -> bool:
    """Official = the provider's own docs. User-written forums on its domain don't count."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if _USER_CONTENT_HOST.match(host) or _USER_CONTENT_PATH.search(parsed.path or ""):
        return False
    flat = re.sub(r"[^a-z0-9]", "", host)
    if base_domain and (host == base_domain or host.endswith("." + base_domain)):
        return True
    return any(len(t) >= 4 and t in flat for t in brand_tokens)


def iter_evidence(draft: GuideDraft) -> Iterator[tuple[str, Evidence]]:
    yield "Testing before approval", draft.can_test_before_approval.evidence
    for f in draft.difficulty.factors:
        yield f.label, f.evidence
    for r in draft.requirements:
        yield r.label, r.evidence
    for s in draft.steps:
        yield s.title, s.evidence
    for g in draft.gotchas:
        yield g.title, g.evidence
    for b in draft.blockers:
        yield b.problem, b.evidence


def verify(draft: GuideDraft, sources: dict[str, SourceDoc]) -> Stats:
    """Set each claim's evidence level and return summary statistics."""
    counts = {"tested": 0, "documented": 0, "reported": 0, "inferred": 0}
    unverified: list[str] = []

    for label, ev in iter_evidence(draft):
        ev.source_ids = [i for i in dict.fromkeys(ev.source_ids) if i in sources]
        level = "inferred"
        if ev.quote and ev.source_ids:
            hits = [sources[i] for i in ev.source_ids if quote_in(ev.quote, sources[i])]
            if any(s.kind == "official" for s in hits):
                level = "documented"
            elif hits:
                level = "reported"
        if level == "inferred":
            if ev.quote:
                log.info("quote not found for %r: %r (cited %s)", label, ev.quote[:160], ev.source_ids)
            ev.quote = None  # an unverifiable quote must not be displayed as one
            if label not in unverified:
                unverified.append(label)
        ev.level = level
        counts[level] += 1

    total = sum(counts.values()) or 1
    strong = (counts["documented"] + counts["tested"]) / total
    solid = (counts["documented"] + counts["tested"] + counts["reported"]) / total
    confidence = "high" if strong >= 0.7 else "medium" if solid >= 0.5 else "low"
    return Stats(counts=counts, confidence=confidence, unverified=unverified[:10])


def build_timeline(draft: GuideDraft) -> Timeline:
    segments: list[Segment] = []
    hands = [0, 0]
    wait = [0, 0]
    agent_minutes = [0, 0]
    for step in draft.steps:
        low, high = step.duration.minutes()
        segments.append(
            Segment(step_id=step.id, label=step.title, owner=step.owner, phase=step.phase,
                    min_minutes=low, max_minutes=high)
        )
        bucket = wait if step.owner == "provider" else hands
        bucket[0] += low
        bucket[1] += high
        if step.owner == "agent":
            agent_minutes[0] += low
            agent_minutes[1] += high
    share = (agent_minutes[1] / hands[1]) if hands[1] else 0.0
    return Timeline(
        segments=segments,
        hands_on=Span(min_minutes=hands[0], max_minutes=hands[1]),
        waiting=Span(min_minutes=wait[0], max_minutes=wait[1]),
        agent_share=round(share, 2),
    )
