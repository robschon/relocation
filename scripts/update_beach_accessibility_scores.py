"""Compute deterministic beach accessibility scores from nearby mapped beaches.

Usage:
    UV_CACHE_DIR=.uv-cache uv run python scripts/update_beach_accessibility_scores.py
    UV_CACHE_DIR=.uv-cache uv run python scripts/update_beach_accessibility_scores.py --location-id 104
"""

from __future__ import annotations

import argparse
import math
import time

import httpx
from sqlalchemy import func, or_

from relocation.database import SessionLocal, init_db
from relocation.models import Category, Location, OceanTemperatureMonthly, Score, User, Weight
from relocation.services.beach_accessibility import (
    compute_beach_accessibility_score,
    fallback_score_from_ocean_distance_km,
)

CATEGORY_NAME = "Beach accessibility"
CATEGORY_DESCRIPTION = (
    "Deterministic score from distance to nearby mapped public beaches and local beach density. "
    "Higher scores indicate beaches are practical for frequent daily use."
)
DEFAULT_WEIGHT = 5.0
OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update beach accessibility category scores.")
    parser.add_argument(
        "--location-id",
        action="append",
        type=int,
        help="Exact location id to process. Repeat for multiple ids.",
    )
    parser.add_argument(
        "--location",
        action="append",
        help="Exact location name to process. Repeat for multiple names.",
    )
    parser.add_argument(
        "--radius-km",
        type=float,
        default=50.0,
        help="Radius for beach search around each location coordinate.",
    )
    parser.add_argument(
        "--request-interval-seconds",
        type=float,
        default=1.0,
        help="Sleep interval between locations to reduce upstream rate-limit errors.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=45.0,
        help="HTTP timeout for Overpass requests.",
    )
    return parser.parse_args()


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


def _overpass_query(latitude: float, longitude: float, radius_km: float) -> str:
    radius_m = int(round(max(1.0, radius_km) * 1000))
    return (
        "[out:json][timeout:40];"
        f"(node(around:{radius_m},{latitude:.6f},{longitude:.6f})['natural'='beach'];"
        f"way(around:{radius_m},{latitude:.6f},{longitude:.6f})['natural'='beach'];"
        f"relation(around:{radius_m},{latitude:.6f},{longitude:.6f})['natural'='beach'];);"
        "out center tags;"
    )


def _fetch_beach_elements(
    client: httpx.Client,
    *,
    latitude: float,
    longitude: float,
    radius_km: float,
) -> list[dict]:
    query = _overpass_query(latitude, longitude, radius_km)
    last_error: Exception | None = None
    for attempt in range(1, 5):
        try:
            response = client.post(OVERPASS_API_URL, data={"data": query})
            if response.status_code == 429:
                time.sleep(min(20.0, 2**attempt))
                continue
            if 500 <= response.status_code < 600:
                time.sleep(min(20.0, 2**attempt))
                continue
            response.raise_for_status()
            payload = response.json()
            elements = payload.get("elements") or []
            if not isinstance(elements, list):
                raise RuntimeError("Overpass response did not include a valid elements list.")
            return [element for element in elements if isinstance(element, dict)]
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(min(20.0, 2**attempt))
    raise RuntimeError(f"Overpass request failed after retries: {last_error}")


def _element_coordinates(element: dict) -> tuple[float, float] | None:
    if element.get("type") == "node":
        lat = element.get("lat")
        lon = element.get("lon")
        if lat is not None and lon is not None:
            return float(lat), float(lon)
    center = element.get("center")
    if isinstance(center, dict) and center.get("lat") is not None and center.get("lon") is not None:
        return float(center["lat"]), float(center["lon"])
    return None


def _is_public_beach(element: dict) -> bool:
    tags = element.get("tags")
    if not isinstance(tags, dict):
        return True
    access = str(tags.get("access") or "").strip().lower()
    return access not in {"private", "no"}


def _latest_ocean_grid_distance_km(location_id: int) -> float | None:
    with SessionLocal() as session:
        latest = (
            session.query(
                OceanTemperatureMonthly.baseline_end_year,
                OceanTemperatureMonthly.baseline_start_year,
            )
            .filter(
                OceanTemperatureMonthly.location_id == location_id,
                OceanTemperatureMonthly.grid_distance_km.is_not(None),
            )
            .order_by(
                OceanTemperatureMonthly.baseline_end_year.desc(),
                OceanTemperatureMonthly.baseline_start_year.desc(),
            )
            .first()
        )
        if not latest:
            return None

        baseline_end_year, baseline_start_year = latest
        min_distance = (
            session.query(func.min(OceanTemperatureMonthly.grid_distance_km))
            .filter(
                OceanTemperatureMonthly.location_id == location_id,
                OceanTemperatureMonthly.baseline_start_year == baseline_start_year,
                OceanTemperatureMonthly.baseline_end_year == baseline_end_year,
            )
            .scalar()
        )
        return float(min_distance) if min_distance is not None else None


def main() -> int:
    args = parse_args()
    init_db()

    with SessionLocal() as session:
        category = session.query(Category).filter(Category.name == CATEGORY_NAME).first()
        if not category:
            max_sort_order = session.query(Category.sort_order).order_by(Category.sort_order.desc()).first()
            next_sort = (max_sort_order[0] if max_sort_order else 0) + 1
            category = Category(
                name=CATEGORY_NAME,
                sort_order=next_sort,
                description=CATEGORY_DESCRIPTION,
            )
            session.add(category)
            session.flush()
            print(f"[info] created category '{CATEGORY_NAME}'")

        users = session.query(User).all()
        for user in users:
            existing_weight = (
                session.query(Weight)
                .filter(
                    Weight.user_id == user.id,
                    Weight.category_id == category.id,
                )
                .first()
            )
            if not existing_weight:
                session.add(Weight(user_id=user.id, category_id=category.id, weight=DEFAULT_WEIGHT))

        query = session.query(Location).order_by(Location.name.asc())
        if args.location_id:
            query = query.filter(Location.id.in_(args.location_id))
        if args.location:
            predicates = [Location.name.ilike(name.strip()) for name in args.location]
            query = query.filter(or_(*predicates))
        locations = query.all()

        if not locations:
            print("[warn] no locations matched filters")
            return 1

        created = 0
        updated = 0
        skipped = 0
        fallback_used = 0
        failures = 0

        with httpx.Client(timeout=args.timeout_seconds) as client:
            for idx, location in enumerate(locations, start=1):
                print(f"[{idx}/{len(locations)}] {location.name} ({location.country})")
                if location.latitude is None or location.longitude is None:
                    print("  [skip] no coordinates on location row")
                    skipped += 1
                    continue

                score_value: int | None = None
                notes: str | None = None

                try:
                    elements = _fetch_beach_elements(
                        client,
                        latitude=float(location.latitude),
                        longitude=float(location.longitude),
                        radius_km=float(args.radius_km),
                    )

                    public_distances: list[float] = []
                    private_count = 0
                    for element in elements:
                        coords = _element_coordinates(element)
                        if not coords:
                            continue
                        beach_lat, beach_lon = coords
                        distance_km = _haversine_km(
                            float(location.latitude),
                            float(location.longitude),
                            beach_lat,
                            beach_lon,
                        )
                        if _is_public_beach(element):
                            public_distances.append(distance_km)
                        else:
                            private_count += 1

                    nearest_public = min(public_distances) if public_distances else None
                    public_within_10 = sum(1 for d in public_distances if d <= 10.0)
                    public_within_20 = sum(1 for d in public_distances if d <= 20.0)
                    score_value = compute_beach_accessibility_score(
                        nearest_public_km=nearest_public,
                        public_within_10_km=public_within_10,
                        public_within_20_km=public_within_20,
                        has_private_only=bool(private_count and not public_distances),
                    )
                    nearest_text = f"{nearest_public:.2f} km" if nearest_public is not None else "none mapped"
                    notes = (
                        f"Nearest mapped public beach: {nearest_text}; "
                        f"public beaches within 10 km: {public_within_10}; "
                        f"within 20 km: {public_within_20}; "
                        f"private-only mapped beaches: {private_count}; "
                        f"search radius: {float(args.radius_km):.0f} km."
                    )
                except Exception as exc:  # noqa: BLE001
                    fallback_distance = _latest_ocean_grid_distance_km(location.id)
                    if fallback_distance is None:
                        print(f"  [error] beach lookup failed and no ocean fallback: {exc}")
                        failures += 1
                        continue
                    score_value = fallback_score_from_ocean_distance_km(fallback_distance)
                    notes = (
                        "Beach mapping lookup failed; used nearest ocean-grid distance fallback "
                        f"({fallback_distance:.2f} km) from ocean temperature source."
                    )
                    fallback_used += 1
                    print(f"  [warn] used fallback scoring: {exc}")

                existing_score = (
                    session.query(Score)
                    .filter(
                        Score.location_id == location.id,
                        Score.category_id == category.id,
                    )
                    .first()
                )
                if existing_score:
                    existing_score.score = score_value
                    existing_score.notes = notes
                    updated += 1
                else:
                    session.add(
                        Score(
                            location_id=location.id,
                            category_id=category.id,
                            score=score_value,
                            notes=notes,
                        )
                    )
                    created += 1
                print(f"  [ok] score={score_value}/10")

                if args.request_interval_seconds > 0:
                    time.sleep(args.request_interval_seconds)

        session.commit()

    print(
        f"[done] created={created} updated={updated} skipped={skipped} "
        f"fallback_used={fallback_used} failed={failures}"
    )
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
