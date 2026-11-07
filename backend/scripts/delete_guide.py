"""Delete a guide row so it is regenerated on next request.

    python backend/scripts/delete_guide.py spotify
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db, store  # noqa: E402


async def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    db.open_pool()
    try:
        count = await store.delete_guide(sys.argv[1].lower())
    finally:
        db.close_pool()
    print(f"deleted {count} row(s)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
