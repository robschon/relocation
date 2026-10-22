"""Full research for one location with pipeline v2 (thin wrapper around relocation.pipeline.runner).

    uv run python scripts/full_research_location_openai.py "Khao Lak"
    uv run python scripts/full_research_location_openai.py --location-id 42
    uv run python scripts/full_research_location_openai.py --location-id 42 --force-research

Equivalent: uv run relocation pipeline run 42 [--force]
"""

from __future__ import annotations

import argparse

from relocation.cli.helpers import resolve_location
from relocation.database import SessionLocal, init_db
from relocation.pipeline.runner import run_location


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full research pipeline for one location")
    parser.add_argument("location", nargs="?", help="Location name (or unique part of it)")
    parser.add_argument("--location-id", type=int, help="Exact location ID")
    parser.add_argument("--force-research", action="store_true", help="Redo every researched category and visa info")
    parser.add_argument("--skip-visa", action="store_true", help="Skip visa info")
    parser.add_argument("--force-description", action="store_true", help="Overwrite the existing description")
    parser.add_argument("--run-id", type=int, help="Existing research_runs id to report into")
    args = parser.parse_args()
    init_db()

    if args.location_id is None and not args.location:
        parser.error("Provide either LOCATION or --location-id.")
    location_id = args.location_id
    if location_id is None:
        with SessionLocal() as session:
            location_id = resolve_location(session, args.location).id

    summary = run_location(
        location_id,
        force=args.force_research,
        skip_visa=args.skip_visa,
        force_description=args.force_description,
        run_id=args.run_id,
        kind="full",
    )
    return 0 if not summary.failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
