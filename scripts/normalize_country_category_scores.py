#!/usr/bin/env python3
"""Normalize category scores so locations in the same country share one baseline."""

from __future__ import annotations

import argparse
import math
import sqlite3
from collections import defaultdict
from pathlib import Path
from statistics import median

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "relocation.db"

COUNTRY_ALIASES = {
    "US": "United States",
    "USA": "United States",
    "United States": "United States",
    "United States of America": "United States",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize scores for a category so each country has one shared score."
    )
    parser.add_argument(
        "--category",
        required=True,
        help='Exact category name, e.g. "Visa / residency feasibility".',
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help=f"SQLite database path (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Persist the normalized scores. Default is dry-run.",
    )
    return parser.parse_args()


def canonical_country(country: str) -> str:
    text = country.strip()
    return COUNTRY_ALIASES.get(text, text)


def round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def main() -> int:
    args = parse_args()
    conn = sqlite3.connect(args.db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            s.id AS score_id,
            s.score AS score,
            l.id AS location_id,
            l.name AS location_name,
            l.country AS country
        FROM scores s
        JOIN locations l ON l.id = s.location_id
        JOIN categories c ON c.id = s.category_id
        WHERE c.name = ?
        ORDER BY l.country, l.name
        """,
        (args.category,),
    ).fetchall()

    if not rows:
        print(f'No scores found for category "{args.category}".')
        return 1

    grouped_scores: dict[str, list[int]] = defaultdict(list)
    grouped_rows: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        country_key = canonical_country(str(row["country"]))
        grouped_scores[country_key].append(int(row["score"]))
        grouped_rows[country_key].append(row)

    targets = {
        country: round_half_up(float(median(scores)))
        for country, scores in grouped_scores.items()
    }

    updates: list[tuple[int, int, str, str, int]] = []
    for country, country_rows in grouped_rows.items():
        target = targets[country]
        for row in country_rows:
            old_score = int(row["score"])
            if old_score == target:
                continue
            updates.append(
                (
                    row["score_id"],
                    target,
                    str(row["location_name"]),
                    country,
                    old_score,
                )
            )

    print(f'Category: "{args.category}"')
    print(f"Countries touched: {len(grouped_rows)}")
    print(f"Planned score updates: {len(updates)}")
    print()

    for country in sorted(grouped_rows):
        before_scores = sorted(grouped_scores[country])
        target = targets[country]
        changed = sum(1 for row in grouped_rows[country] if int(row["score"]) != target)
        if changed == 0:
            continue
        print(
            f"{country}: {before_scores} -> {target} "
            f"(updates={changed}/{len(grouped_rows[country])})"
        )
        for row in grouped_rows[country]:
            old_score = int(row["score"])
            if old_score == target:
                continue
            print(f"  - {row['location_name']}: {old_score} -> {target}")

    if not args.write:
        print()
        print("Dry run only. Re-run with --write to persist changes.")
        return 0

    with conn:
        conn.executemany(
            "UPDATE scores SET score = ? WHERE id = ?",
            [(target, score_id) for score_id, target, *_ in updates],
        )

    print()
    print(f"Updated {len(updates)} scores.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
