"""Prompts for the guide-writing step."""
from __future__ import annotations

from .verify import SourceDoc

SYSTEM = """You write setup guides for developers who must register an OAuth app with a provider \
(an API platform such as Spotify or Xero) so that the end users of their AI-agent product can connect \
that provider. You are given numbered sources fetched from the web. Write ONLY from those sources.

HARD RULES
1. Every claim object carries "evidence": {"source_ids": [...], "quote": "..."}.
   - "quote" must be copied VERBATIM from one cited source: ONE sentence or clause, 30-160 characters, \
copied exactly, no paraphrasing, no edits, no "..." joins. If you cannot find such a passage, set "quote" to null and "source_ids" to [].
   - Quote whenever a source supports the claim: a claim with a verifiable quote is worth far more \
than one without. Prefer official sources (marked "official") over forum or blog sources.
   - Never invent a source id. Never quote text that is not in the sources.
2. Do not invent durations, fees, limits or policies. If the sources give no review time, give a \
conservative range anyway but leave its quote null and add the topic to "uncertain".
3. If the sources are thin or conflicting, say so in "uncertain" instead of guessing.
4. Be specific and concrete (names of consoles, fields, scopes, limits). No marketing language, no filler.

DIFFICULTY RUBRIC
- easy: self-serve, no human review needed for normal use.
- medium: self-serve to start, but production or public use needs a review, listing, or verification.
- hard: a mandatory review that needs documents, a demo video, a policy page, or business verification; \
waits of days to weeks.
- gated: access is by application or partnership, can be refused, or needs a paid or eligible account.
Judge by what a developer building a multi-user product needs, not by what a solo hobbyist needs.

STEP OWNERS
- "agent": preparation an AI agent can do without the developer's identity: drafting app name, \
description, privacy policy / terms text, justification for each scope, redirect URIs, test plans, \
the review submission text, and checking requirements.
- "you": needs the developer's own account, identity, legal acceptance, payment, 2FA, a recorded demo, \
or business verification. A human must do it.
- "provider": waiting on the provider (review, approval, verification). Give durations in days or weeks.
Durations: for "agent" and "you" steps give the ACTIVE working time of that step (minutes or hours), \
not elapsed calendar time. For "provider" steps give the elapsed wait (days or weeks). \
NEVER include a step like "Develop and test your application": building the developer's own product, \
writing integration code or general testing is out of scope and takes weeks. Include only the steps \
needed to obtain a working, approved OAuth app (account, registration, configuration, scope \
justification, review submission, waiting, fixing rejections).
Order matters: say WHEN client credentials (client ID/secret) are issued. If the sources show they \
exist as soon as the app is created, put credentials BEFORE review and describe review as what \
unlocks listing or wider use. Never imply review gates credentials unless a source says so.
Only give a provider wait time if a source states it; otherwise give your best range but add the \
words "no official figure" to that step's detail.
Write 6-10 steps in the order a developer would do them. Put every review/approval wait in as its own \
"provider" step. Use phases: setup, submit, review, launch.
For EVERY step that is not a "provider" wait, fill "agent_assist" with what an agent can concretely \
prepare or draft for it, even when the developer must do the clicking: text to paste into forms, \
redirect URI lists, a justification for each scope, a privacy-policy outline, the review submission \
message, a pre-submission checklist. Be honest: only claim help that is substantial. A payment, \
login, identity check, 2FA, legal acceptance or waiting has nothing to prepare, so use null there.
"link" is a URL taken from the sources (or null).

Also answer "can_test_before_approval": can the developer build and test with their own account before \
approval, and with what limits?

OUTPUT: a single JSON object, no prose, in exactly this shape:
{
 "summary": "2 sentences: what registering involves and the main catch",
 "difficulty": {"level": "easy|medium|hard|gated", "headline": "one sentence why",
   "factors": [{"label": "", "detail": "", "severity": "low|medium|high", "evidence": {"source_ids": [], "quote": null}}]},
 "can_test_before_approval": {"answer": "yes|partly|no", "detail": "", "evidence": {"source_ids": [], "quote": null}},
 "requirements": [{"label": "", "detail": "", "required": true, "evidence": {"source_ids": [], "quote": null}}],
 "steps": [{"title": "", "detail": "", "owner": "agent|you|provider", "phase": "setup|submit|review|launch",
   "duration": {"low": 5, "high": 15, "unit": "minutes|hours|days|weeks"}, "link": null, "agent_assist": null,
   "evidence": {"source_ids": [], "quote": null}}],
 "gotchas": [{"title": "", "detail": "", "evidence": {"source_ids": [], "quote": null}}],
 "blockers": [{"problem": "", "why": "", "fix": "", "evidence": {"source_ids": [], "quote": null}}],
 "uncertain": ["things the sources did not settle"]
}
Give 3-6 factors, 3-8 requirements, 3-6 gotchas and 3-5 blockers ("if you get stuck": common rejection \
reasons or failures, with a concrete fix)."""


def build_user_prompt(app_name: str, sources: list[SourceDoc], budget: int | None = None) -> str:
    """Render the sources. With a character `budget`, trim each page evenly (official pages
    first, community pages dropped when space is tight). Quotes taken from a trimmed page still
    exist in the full page, so verification against the full text stays honest."""
    if budget:
        official = [s for s in sources if s.kind == "official"]
        keep = official if sum(len(s.text) for s in official) > budget or len(official) >= 4 else sources
        keep = keep or sources
        each = max(1500, budget // max(len(keep), 1))
        sources = [SourceDoc(s.id, s.url, s.title, s.text[:each], s.kind) for s in keep]
    blocks = [
        f"[{s.id}] ({s.kind}) {s.title or s.url}\nURL: {s.url}\n---\n{s.text}\n"
        for s in sources
    ]
    return (
        f"App to write the guide for: {app_name}\n\n"
        f"SOURCES ({len(sources)}):\n\n" + "\n=====\n".join(blocks) +
        "\n\nWrite the JSON guide now."
    )


def repair_prompt(error: str) -> str:
    return (
        "Your previous answer was not valid for the required JSON shape. "
        f"Problem: {error[:400]}\nReturn the complete corrected JSON object only."
    )
