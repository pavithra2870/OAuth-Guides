"""Load guide JSON files into the database (upsert).

    python backend/scripts/seed.py                       # every file in backend/data/drafts as 'generated'
    python backend/scripts/seed.py --origin curated backend/data/guides/*.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db, store  # noqa: E402
from app.schemas import Guide  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data"


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--origin", choices=["generated", "curated"], default="generated")
    args = parser.parse_args()

    files = args.files or sorted((DATA / "drafts").glob("*.json"))
    if not files:
        print("No files to seed.")
        return 1

    db.open_pool()
    try:
        for path in files:
            guide = Guide.model_validate(json.loads(path.read_text(encoding="utf-8")))  # reject malformed files
            await store.upsert_guide(json.loads(guide.model_dump_json()), args.origin)
            print(f"seeded {guide.slug} ({args.origin})")
    finally:
        db.close_pool()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
