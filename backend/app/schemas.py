"""The guide data model.

`GuideDraft` is what the LLM writes. `Guide` is the full, server-completed
document stored in the database and shown to the developer. The LLM only
supplies *pointers* to evidence (source ids + a verbatim quote); the evidence
*level* is computed by `verify.py`, never trusted from the model.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Owner = Literal["agent", "you", "provider"]
Phase = Literal["setup", "submit", "review", "launch"]
Difficulty = Literal["easy", "medium", "hard", "gated"]
Severity = Literal["low", "medium", "high"]
# tested     : a person or agent actually did it (curated guides only)
# documented : a verbatim quote was found in an official source
# reported   : a verbatim quote was found, but only in a non-official source
# inferred   : no verifiable quote; reasoning or best estimate
EvidenceLevel = Literal["tested", "documented", "reported", "inferred"]

_UNIT_MINUTES = {"minutes": 1, "hours": 60, "days": 1440, "weeks": 10080}


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Evidence(_Model):
    source_ids: list[str] = Field(default_factory=list)
    quote: str | None = None
    level: EvidenceLevel = "inferred"  # computed by verify.py

    @field_validator("source_ids", mode="before")
    @classmethod
    def _normalize_ids(cls, value):
        """Models sometimes write 1, "1" or "s1" for "S1"."""
        if not isinstance(value, list):
            return []
        ids = []
        for item in value:
            digits = "".join(ch for ch in str(item) if ch.isdigit())
            if digits:
                ids.append(f"S{int(digits)}")
        return ids

    @field_validator("quote", mode="before")
    @classmethod
    def _blank_quote(cls, value):
        return value.strip() or None if isinstance(value, str) else None


class Duration(_Model):
    low: float = 0
    high: float = 0
    unit: Literal["minutes", "hours", "days", "weeks"] = "minutes"

    def minutes(self) -> tuple[int, int]:
        factor = _UNIT_MINUTES[self.unit]
        low, high = sorted((max(self.low, 0), max(self.high, self.low, 0)))
        return int(low * factor), int(high * factor)


class Factor(_Model):
    label: str
    detail: str = ""
    severity: Severity = "medium"
    evidence: Evidence = Field(default_factory=Evidence)


class DifficultyAssessment(_Model):
    level: Difficulty
    headline: str = ""
    factors: list[Factor] = Field(default_factory=list)


class BeforeApproval(_Model):
    answer: Literal["yes", "partly", "no"] = "partly"
    detail: str = ""
    evidence: Evidence = Field(default_factory=Evidence)


class Requirement(_Model):
    label: str
    detail: str = ""
    required: bool = True
    evidence: Evidence = Field(default_factory=Evidence)


class Step(_Model):
    id: str = ""
    title: str
    detail: str = ""
    owner: Owner = "you"
    phase: Phase = "setup"
    duration: Duration = Field(default_factory=Duration)
    link: str | None = None
    agent_assist: str | None = None
    evidence: Evidence = Field(default_factory=Evidence)


class Gotcha(_Model):
    title: str
    detail: str = ""
    evidence: Evidence = Field(default_factory=Evidence)


class Blocker(_Model):
    problem: str
    why: str = ""
    fix: str = ""
    evidence: Evidence = Field(default_factory=Evidence)


class GuideDraft(_Model):
    """Exactly what the LLM is asked to produce."""

    summary: str
    difficulty: DifficultyAssessment
    can_test_before_approval: BeforeApproval = Field(default_factory=BeforeApproval)
    requirements: list[Requirement] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)
    gotchas: list[Gotcha] = Field(default_factory=list)
    blockers: list[Blocker] = Field(default_factory=list)
    uncertain: list[str] = Field(default_factory=list)


# --- server-completed parts ---------------------------------------------------

class Source(_Model):
    id: str
    url: str
    title: str = ""
    kind: Literal["official", "community"] = "community"


class Segment(_Model):
    step_id: str
    label: str
    owner: Owner
    phase: Phase
    min_minutes: int
    max_minutes: int


class Span(_Model):
    min_minutes: int = 0
    max_minutes: int = 0


class Timeline(_Model):
    segments: list[Segment] = Field(default_factory=list)
    hands_on: Span = Field(default_factory=Span)   # agent + you
    waiting: Span = Field(default_factory=Span)    # provider
    agent_share: float = 0.0                       # share of hands-on time an agent can take


class Stats(_Model):
    counts: dict[str, int] = Field(default_factory=dict)
    confidence: Literal["high", "medium", "low"] = "low"
    unverified: list[str] = Field(default_factory=list)  # claims we could not verify


class ComposioStatus(_Model):
    status: Literal["managed", "byo", "not_listed"] = "not_listed"
    name: str | None = None
    slug: str | None = None
    related: list[dict] = Field(default_factory=list)
    snapshot_date: str | None = None


class Meta(_Model):
    researched_at: str
    provider: str = ""
    model: str = ""
    queries: list[str] = Field(default_factory=list)
    pages_read: int = 0
    origin: Literal["generated", "curated"] = "generated"


class Guide(GuideDraft):
    slug: str
    app_name: str
    domain: str | None = None
    composio: ComposioStatus = Field(default_factory=ComposioStatus)
    sources: list[Source] = Field(default_factory=list)
    timeline: Timeline = Field(default_factory=Timeline)
    stats: Stats = Field(default_factory=Stats)
    meta: Meta
