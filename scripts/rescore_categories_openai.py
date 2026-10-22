"""Re-score categories from stored evidence (no web search) with pipeline v2.

    uv run python scripts/rescore_categories_openai.py                 # visa + tax, all locations
    uv run python scripts/rescore_categories_openai.py --stale-only    # only scores older than their evidence
    uv run python scripts/rescore_categories_openai.py --location "Valencia" --category food

Equivalent: uv run relocation pipeline rescore [--category KEY] [--location NAME] [--stale-only]
"""

from __future__ import annotations

import argparse

from relocation.cli.helpers import resolve_location
from relocation.database import SessionLocal, init_db
from relocation.pipeline.runner import run_rescore


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-score categories from stored evidence")
    parser.add_argument("--location", action="append", help="Location name or ID (repeatable); default all")
    parser.add_argument("--category", action="append", help="Category key or name (repeatable); default visa + tax")
    parser.add_argument("--stale-only", action="store_true", help="Only where the score predates the current evidence")
    args = parser.parse_args()
    init_db()

    location_ids = None
    if args.location:
        with SessionLocal() as session:
            location_ids = [resolve_location(session, name).id for name in args.location]
    summary = run_rescore(
        category_keys=args.category or ["visa", "tax"],
        location_ids=location_ids,
        stale_only=args.stale_only,
    )
    print(f"Rescored: {len(summary.rescored)}  Failed: {len(summary.failures)}")
    return 0 if not summary.failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
