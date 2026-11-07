"""Snapshot Composio's managed-OAuth directory into backend/data/composio_catalog.json.

    python backend/scripts/build_catalog.py

Source: https://docs.composio.dev/toolkits/managed-auth (public, no API key needed).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

URL = "https://docs.composio.dev/toolkits/managed-auth.md"
OUT = Path(__file__).resolve().parents[1] / "data" / "composio_catalog.json"
ROW = re.compile(r"^\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|\s*`([^`]+)`\s*\|")


def parse(markdown: str) -> dict[str, list[dict]]:
    sections: dict[str, list[dict]] = {"managed": [], "byo": []}
    current = None
    for line in markdown.splitlines():
        if line.startswith("## "):
            title = line.lower()
            current = "managed" if "managed oauth available" in title else "byo" if "bring your own" in title else None
        elif current and (m := ROW.match(line)):
            sections[current].append({"name": m.group(1), "slug": m.group(3), "page": m.group(2)})
    return sections


def main() -> None:
    response = httpx.get(URL, timeout=30, follow_redirects=True)
    response.raise_for_status()
    sections = parse(response.text)
    if not sections["managed"] or not sections["byo"]:
        raise SystemExit("Parsed an empty section; the page format may have changed.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {"source": URL, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **sections},
            indent=1,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"managed: {len(sections['managed'])}, bring-your-own: {len(sections['byo'])} -> {OUT}")


if __name__ == "__main__":
    main()
