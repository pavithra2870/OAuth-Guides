"""Lookup against the snapshot of Composio's managed-OAuth directory."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "composio_catalog.json"


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def query_tokens(query: str) -> list[str]:
    """Candidate names from user input: a plain name, or the brand part of a website."""
    query = query.strip()
    if re.match(r"^(https?://)?[\w.-]+\.[a-z]{2,}(/|$)", query, re.I):
        host = urlparse(query if "//" in query else f"//{query}").hostname or ""
        parts = [p for p in host.split(".") if p not in ("www", "com", "org", "net", "io", "co", "app", "dev", "so", "ai")]
        return [normalize(p) for p in reversed(parts)] or [normalize(host)]
    return [normalize(query)]


def resolve(query: str) -> dict:
    """Turn user input (a name or a website) into {slug, name, website, catalog}."""
    query = query.strip()
    catalog = lookup(query)
    is_url = bool(re.match(r"^(https?://)?[\w.-]+\.[a-z]{2,}(/|$)", query, re.I))
    website = None
    if is_url:
        website = (urlparse(query if "//" in query else f"//{query}").hostname or "").removeprefix("www.") or None
    if catalog["name"]:
        name = catalog["name"]
    elif is_url:
        name = (query_tokens(query)[0] or query).capitalize()
    else:
        name = query
    return {"slug": slugify(name), "name": name, "website": website, "catalog": catalog}


@lru_cache
def _load() -> dict:
    if not CATALOG_PATH.exists():
        return {"managed": [], "byo": [], "fetched_at": None}
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def lookup(query: str) -> dict:
    """Return {status: managed|byo|not_listed, name, slug, related, snapshot_date}."""
    data = _load()
    entries = [(e, "managed") for e in data["managed"]] + [(e, "byo") for e in data["byo"]]
    tokens = [t for t in query_tokens(query) if t]
    result = {"status": "not_listed", "name": None, "slug": None, "related": [], "snapshot_date": data.get("fetched_at")}

    for token in tokens:
        exact = [(e, s) for e, s in entries if token in (normalize(e["name"]), normalize(e["slug"]))]
        if exact:
            # prefer the managed entry when the same name appears in both lists
            entry, status = sorted(exact, key=lambda x: x[1] != "managed")[0]
            result.update(status=status, name=entry["name"], slug=entry["slug"])
            result["related"] = [
                {"name": e["name"], "slug": e["slug"], "status": s}
                for e, s in entries
                if normalize(e["name"]).startswith(token) and e["slug"] != entry["slug"]
            ][:5]
            return result
    return result
