"""Compute deterministic swimming-viability scores from ocean temperatures.

Usage:
    UV_CACHE_DIR=.uv-cache uv run python scripts/update_swimming_scores.py
    UV_CACHE_DIR=.uv-cache uv run python scripts/update_swimming_scores.py --threshold-c 19
"""

from __future__ import annotations

import argparse
import math

from relocation.database import SessionLocal, init_db
from relocation.models import Category, OceanTemperatureMonthly, Score, User, Weight

CATEGORY_NAME = "Year-round swimming viability"
CATEGORY_DESCRIPTION = (
    "Deterministic score from monthly sea-surface temperature. "
    "10 means all months are at or above threshold; 0 means no months meet threshold."
)
DEFAULT_WEIGHT = 5.0
SOURCE_DATASET = "open-meteo-marine-era5-ocean"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update the year-round swimming viability category scores."
    )
    parser.add_argument(
        "--threshold-c",
        type=float,
        default=19.0,
        help="Comfort threshold in degrees Celsius for a month to count as swimmable.",
    )
    parser.add_argument(
        "--source-dataset",
        default=SOURCE_DATASET,
        help="Ocean temperature source dataset key to use when selecting monthly rows.",
    )
    parser.add_argument(
        "--location-id",
        action="append",
        type=int,
        help="Exact location id to process. Repeat for multiple ids.",
    )
    return parser.parse_args()


def _score_from_warm_months(warm_months: int) -> int:
    if warm_months <= 0:
        return 0
    if warm_months >= 12:
        return 10
    return int(math.floor((warm_months * 10 / 12) + 0.5))


def main() -> int:
    args = parse_args()
    threshold_c = float(args.threshold_c)

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

        # Determine latest baseline window present in the ocean temp table for this dataset.
        latest = (
            session.query(
                OceanTemperatureMonthly.baseline_end_year,
                OceanTemperatureMonthly.baseline_start_year,
            )
            .filter(OceanTemperatureMonthly.source_dataset == args.source_dataset)
            .order_by(
                OceanTemperatureMonthly.baseline_end_year.desc(),
                OceanTemperatureMonthly.baseline_start_year.desc(),
            )
            .first()
        )
        if not latest:
            print("[error] no ocean temperature data found")
            return 1
        baseline_end_year, baseline_start_year = latest
        print(f"[info] baseline={baseline_start_year}-{baseline_end_year} threshold={threshold_c:.1f}C")

        location_ids = [
            row[0]
            for row in (
                session.query(OceanTemperatureMonthly.location_id)
                .filter(
                    OceanTemperatureMonthly.source_dataset == args.source_dataset,
                    OceanTemperatureMonthly.baseline_start_year == baseline_start_year,
                    OceanTemperatureMonthly.baseline_end_year == baseline_end_year,
                )
                .distinct()
                .all()
            )
        ]
        if args.location_id:
            requested_ids = set(args.location_id)
            location_ids = [location_id for location_id in location_ids if location_id in requested_ids]
            if not location_ids:
                print("[error] no matching ocean temperature baseline rows for requested location id(s)")
                return 1

        updated = 0
        created = 0
        skipped = 0
        for location_id in location_ids:
            monthly_rows = (
                session.query(OceanTemperatureMonthly)
                .filter(
                    OceanTemperatureMonthly.location_id == location_id,
                    OceanTemperatureMonthly.source_dataset == args.source_dataset,
                    OceanTemperatureMonthly.baseline_start_year == baseline_start_year,
                    OceanTemperatureMonthly.baseline_end_year == baseline_end_year,
                )
                .order_by(OceanTemperatureMonthly.month.asc())
                .all()
            )
            if len(monthly_rows) < 12:
                skipped += 1
                continue

            warm_months = sum(1 for row in monthly_rows if row.avg_temp_c >= threshold_c)
            score_value = _score_from_warm_months(warm_months)
            quality_flags = sorted({row.quality_flag for row in monthly_rows if row.quality_flag and row.quality_flag != "ok"})
            notes = (
                f"{warm_months}/12 months have average sea temperature >= {threshold_c:.1f}C "
                f"(baseline {baseline_start_year}-{baseline_end_year})."
            )
            if quality_flags:
                notes += f" Quality flags: {', '.join(quality_flags)}."

            existing_score = (
                session.query(Score)
                .filter(
                    Score.location_id == location_id,
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
                        location_id=location_id,
                        category_id=category.id,
                        score=score_value,
                        notes=notes,
                    )
                )
                created += 1

        session.commit()

    print(f"[done] created={created} updated={updated} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
