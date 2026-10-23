"""Export location research from the DB into markdown files in ./research (named by location slug).

Examples:
    uv run python scripts/export_research_markdown.py "Rincón" 54
    uv run python scripts/export_research_markdown.py --all --prune
"""

from __future__ import annotations

import argparse

from relocation.cli.helpers import resolve_location
from relocation.database import SessionLocal, init_db
from relocation.export_markdown import OUT_DIR, export_locations, stale_files
from relocation.models import Location


def main() -> int:
    parser = argparse.ArgumentParser(description="Export markdown research docs for locations.")
    parser.add_argument("locations", nargs="*", help='Location ids or names, e.g. 54 or "Valletta / Sliema"')
    parser.add_argument("--all", action="store_true", help="Export every location")
    parser.add_argument("--prune", action="store_true", help="Delete research/*.md files that match no location slug")
    parser.add_argument("--dry-run", action="store_true", help="With --prune: list stale files without deleting")
    args = parser.parse_args()
    if not args.locations and not args.all and not args.prune:
        parser.error("give location ids/names, --all, or --prune")

    init_db()
    with SessionLocal() as session:
        if args.all:
            locations = session.query(Location).order_by(Location.id).all()
        else:
            locations = [resolve_location(session, value) for value in args.locations]
        for path in export_locations(session, locations):
            print(f"[ok] wrote {path.relative_to(OUT_DIR.parent)}")
        if args.prune:
            for path in stale_files(session):
                if args.dry_run:
                    print(f"[stale] {path.relative_to(OUT_DIR.parent)}")
                else:
                    path.unlink()
                    print(f"[removed] {path.relative_to(OUT_DIR.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
