"""Fill locations.admin1 (state/province) from the geocoder, for locations that lack it.

For each location the geocoder candidates are compared with the stored coordinates and the
nearest one within --max-km is used. Needs network access to Open-Meteo geocoding (and
Nominatim as a fallback), so run it on your own machine.

    uv run python scripts/backfill_admin1.py --dry-run
    uv run python scripts/backfill_admin1.py
"""

from __future__ import annotations

import argparse
import math
import time

from relocation.database import SessionLocal, init_db
from relocation.models import Location
from relocation.services.location_candidates import search_location_candidates


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="Show what would be set without saving")
    parser.add_argument("--max-km", type=float, default=30.0, help="Ignore candidates farther than this from the stored coordinates")
    parser.add_argument("--all", action="store_true", help="Also re-check locations that already have admin1")
    parser.add_argument("--interval", type=float, default=1.1, help="Seconds between lookups (Nominatim asks for <=1/s)")
    args = parser.parse_args()

    init_db()
    with SessionLocal() as session:
        query = session.query(Location).filter(Location.latitude.isnot(None)).order_by(Location.id)
        if not args.all:
            query = query.filter(Location.admin1.is_(None))
        locations = query.all()
        updated, unmatched = 0, []
        for loc in locations:
            try:
                result = search_location_candidates(name=loc.name, country=loc.country, region=loc.region)
            except Exception as exc:  # noqa: BLE001
                unmatched.append(f"{loc.name}: lookup failed ({exc})")
                continue
            best = None
            for cand in result.get("candidates", []):
                if not cand.get("admin1"):
                    continue
                distance = _km(loc.latitude, loc.longitude, cand["latitude"], cand["longitude"])
                if distance <= args.max_km and (best is None or distance < best[0]):
                    best = (distance, cand["admin1"])
            if best is None:
                unmatched.append(f"{loc.name}: no candidate with admin1 within {args.max_km:g} km")
            else:
                print(f"[{'dry' if args.dry_run else 'set'}] {loc.id} {loc.name}: {best[1]} ({best[0]:.1f} km)")
                if not args.dry_run:
                    loc.admin1 = best[1]
                    session.commit()
                updated += 1
            time.sleep(args.interval)
    print(f"[done] matched={updated} unmatched={len(unmatched)}")
    for line in unmatched:
        print(f"  - {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
