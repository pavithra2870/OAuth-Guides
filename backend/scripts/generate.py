"""Run the research agent from the command line (no database needed).

    python backend/scripts/generate.py "Spotify"
    python backend/scripts/generate.py xero.com --out backend/data/drafts/xero.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import pipeline  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="app name or website")
    parser.add_argument("--out", help="write the guide JSON here")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="  ! %(name)s: %(message)s")
    logging.getLogger("verify").setLevel(logging.INFO)

    started = time.perf_counter()
    guide = None
    try:
        async for event, data in pipeline.run(args.query):
            at = f"{time.perf_counter() - started:5.1f}s"
            if event == "progress":
                print(f"[{at}] {data['stage']:<8} {data['status']:<8} {data['message']}")
            elif event == "source":
                print(f"[{at}]   source {data['id']} ({data['kind']}) {data['url']}")
            elif event == "guide":
                guide = data
    except pipeline.PipelineError as exc:
        print(f"\nFAILED: {exc}")
        return 1

    out = Path(args.out) if args.out else Path(__file__).resolve().parents[1] / "data" / "drafts" / f"{guide['slug']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(guide, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
