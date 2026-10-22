"""Research (and score) a location with pipeline v2 (thin wrapper around relocation.pipeline.runner).

    uv run python scripts/research_location_openai.py Fremantle
    uv run python scripts/research_location_openai.py Fremantle --force
    uv run python scripts/research_location_openai.py Fremantle --category "Cost"
    uv run python scripts/research_location_openai.py Fremantle --skip-description

Equivalent: uv run relocation pipeline run Fremantle [--force] [--category cost_of_living]
"""

from __future__ import annotations

import argparse

from relocation.cli.helpers import resolve_location
from relocation.database import SessionLocal, init_db
from relocation.pipeline.runner import run_location


def main() -> int:
    parser = argparse.ArgumentParser(description="Research and score a location")
    parser.add_argument("location", help="Location name (or unique part of it) or ID")
    parser.add_argument("--force", action="store_true", help="Re-research even if current")
    parser.add_argument("--category", help="Only this category (key, or part of its name)")
    parser.add_argument("--skip-visa", action="store_true", help="Skip visa info")
    parser.add_argument("--skip-description", action="store_true", help="Skip pros/cons and description")
    parser.add_argument("--force-description", action="store_true", help="Overwrite the existing description")
    parser.add_argument("--run-id", type=int, help="Existing research_runs id to report into")
    args = parser.parse_args()
    init_db()

    with SessionLocal() as session:
        location_id = resolve_location(session, args.location).id
    summary = run_location(
        location_id,
        force=args.force,
        category_keys=[args.category] if args.category else None,
        skip_visa=args.skip_visa,
        skip_synthesis=args.skip_description,
        force_description=args.force_description,
        run_id=args.run_id,
        kind="category" if args.category else "full",
    )
    return 0 if not summary.failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
