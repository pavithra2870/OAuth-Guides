"""Check every API key and the database connection.

    python backend/scripts/check_connections.py            # free checks only
    python backend/scripts/check_connections.py --models   # also list usable models
    python backend/scripts/check_connections.py --spend    # also run 1 Tavily search per key

Never prints key values.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.checks import run_all  # noqa: E402
from app.config import get_settings  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--models", action="store_true", help="list models each LLM key can use")
    parser.add_argument("--spend", action="store_true", help="run a real Tavily search per key (uses credits)")
    args = parser.parse_args()

    settings = get_settings()
    print("Configuration:", settings.public_summary(), "\n")

    results = await run_all(settings, spend=args.spend)
    for r in results:
        flag = "OK  " if r.ok else "FAIL"
        print(f"[{flag}] {r.label:<10} {r.latency_ms:>5} ms  {r.detail}")

    if args.models:
        for service in ("gemini", "groq"):
            sets = [set(r.extra.get("models", [])) for r in results if r.service == service and r.ok]
            if sets:
                print(f"\n{service} models (available to at least one key):")
                for name in sorted(set.union(*sets)):
                    print(f"  {name}")

    failed = [r for r in results if not r.ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
