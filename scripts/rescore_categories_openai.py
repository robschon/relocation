"""Rescore selected categories for locations using existing research evidence.

Usage:
    uv run python scripts/rescore_categories_openai.py
    uv run python scripts/rescore_categories_openai.py --stale-only
    uv run python scripts/rescore_categories_openai.py --location "Valencia"
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable

from openai import OpenAI

from full_research_location_openai import score_category
from research_location_openai import (
    api_get,
    api_post,
    get_location_research,
    resolve_location,
)

DEFAULT_CATEGORY_NAMES = {"Visa / residency feasibility", "Tax implications"}


def latest_research_by_category(entries: list[dict]) -> dict[int, dict]:
    latest: dict[int, dict] = {}
    for entry in entries:
        category_id = entry.get("category_id")
        if category_id is None:
            continue
        prev = latest.get(category_id)
        if prev is None or entry.get("id", 0) > prev.get("id", 0):
            latest[category_id] = entry
    return latest


def stale_location_names() -> list[str]:
    """Return locations where visa/tax score is missing or older than latest research."""
    categories = api_get("/categories")
    category_map = {c["name"]: c["id"] for c in categories}
    target_ids = {category_map[name] for name in DEFAULT_CATEGORY_NAMES if name in category_map}
    if not target_ids:
        return []

    locations = api_get("/locations")
    out: list[str] = []
    for loc in locations:
        loc_id = loc["id"]
        entries = get_location_research(loc_id)
        latest = latest_research_by_category(entries)
        scores = api_get(f"/locations/{loc_id}/scores")
        score_by_cat = {s["category_id"]: s for s in scores if s.get("category_id") is not None}

        needs_rescore = False
        for cat_id in target_ids:
            research = latest.get(cat_id)
            score = score_by_cat.get(cat_id)
            if not research or not score:
                needs_rescore = True
                break
            if (score.get("updated_at") or "") < (research.get("created_at") or ""):
                needs_rescore = True
                break
        if needs_rescore:
            out.append(loc["name"])
    return out


def resolve_locations(location_names: Iterable[str]) -> list[dict]:
    resolved: list[dict] = []
    for name in location_names:
        resolved.append(resolve_location(name))
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description="Rescore selected categories for locations")
    parser.add_argument(
        "--location",
        action="append",
        help="Location name to process (substring match). Repeatable.",
    )
    parser.add_argument(
        "--stale-only",
        action="store_true",
        help="Only process locations where visa/tax score is stale vs latest research.",
    )
    parser.add_argument(
        "--category",
        action="append",
        help="Category name to rescore (repeatable). Defaults to visa + tax.",
    )
    args = parser.parse_args()

    categories = api_get("/categories")
    category_by_name = {c["name"]: c for c in categories}

    requested = set(args.category or DEFAULT_CATEGORY_NAMES)
    target_categories = [category_by_name[name] for name in requested if name in category_by_name]
    if not target_categories:
        raise ValueError("No valid categories selected for rescoring")

    if args.location:
        names = args.location
    elif args.stale_only:
        names = stale_location_names()
    else:
        names = [loc["name"] for loc in api_get("/locations")]

    if not names:
        print("No locations to process.")
        return 0

    locations = resolve_locations(names)
    client = OpenAI()

    total_updated = 0
    total_skipped = 0
    for location in locations:
        print(f"=== {location['name']} ({location['country']}) ===")
        entries = get_location_research(location["id"])
        latest = latest_research_by_category(entries)

        for category in target_categories:
            research = latest.get(category["id"])
            if not research:
                print(f"  [skip] {category['name']} (no research)")
                total_skipped += 1
                continue

            result = score_category(
                client=client,
                location=location,
                category=category,
                research_content=research["content"],
            )
            api_post(
                "/scores",
                {
                    "location_id": location["id"],
                    "category_id": category["id"],
                    "score": result["score"],
                    "notes": result["notes"],
                },
            )
            print(f"  [done] {category['name']}: {result['score']}/10")
            total_updated += 1

    print(f"Updated scores: {total_updated}")
    print(f"Skipped: {total_skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
