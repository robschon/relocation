"""Backfill Beach accessibility research for locations missing that category.

Usage:
    uv run python scripts/backfill_beach_accessibility_research_openai.py
    uv run python scripts/backfill_beach_accessibility_research_openai.py --dry-run
    uv run python scripts/backfill_beach_accessibility_research_openai.py --location "Valencia"
"""

from __future__ import annotations

import argparse

from openai import OpenAI

from research_location_openai import (
    api_get,
    api_post,
    get_location_research,
    get_profile_answers,
    get_profile_context,
    infer_profile_flags,
    research_category,
    resolve_location,
)


def _normalize_name(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalpha())


def _resolve_target_category(categories: list[dict], requested_name: str) -> dict:
    requested = _normalize_name(requested_name)
    for category in categories:
        if _normalize_name(str(category.get("name") or "")) == requested:
            return category

    # Typo-tolerant fallback for this category.
    if requested in {"beachaccessibility", "beachaccesibility"}:
        for category in categories:
            normalized = _normalize_name(str(category.get("name") or ""))
            if normalized in {"beachaccessibility", "beachaccesibility"}:
                return category

    raise ValueError(f"No category matching '{requested_name}'")


def _has_category_research(location_id: int, category_id: int) -> bool:
    entries = get_location_research(location_id)
    return any(entry.get("category_id") == category_id for entry in entries)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill Beach accessibility research for locations missing this category."
    )
    parser.add_argument(
        "--category",
        default="Beach accessibility",
        help="Category name to backfill (default: Beach accessibility).",
    )
    parser.add_argument(
        "--location",
        action="append",
        help="Location name to process (substring match). Repeatable.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional max number of locations to process after filtering.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Research even when this category already has a research entry for a location.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be researched without writing records.",
    )
    args = parser.parse_args()

    categories = api_get("/categories")
    if not isinstance(categories, list):
        raise ValueError("Categories response was not a list")
    target_category = _resolve_target_category(categories, args.category)
    target_category_id = target_category["id"]

    if args.location:
        locations = [resolve_location(name) for name in args.location]
    else:
        locations = api_get("/locations")
        if not isinstance(locations, list):
            raise ValueError("Locations response was not a list")

    locations = sorted(locations, key=lambda item: (item.get("name") or "").lower())
    if args.limit is not None:
        locations = locations[: args.limit]

    if not locations:
        print("No locations to process.")
        return 0

    profile_context = get_profile_context()
    profile_answers = get_profile_answers()
    profile_flags = infer_profile_flags(profile_answers)
    if profile_context:
        print("[context] Profile context loaded and will be used in prompts.")
    else:
        print("[context] No profile context found; using location/category-only prompts.")
    if profile_flags.get("is_us_citizen"):
        print("[context] Profile indicates U.S. citizenship.")

    client = OpenAI() if not args.dry_run else None

    researched = 0
    skipped = 0
    failures = 0

    for location in locations:
        location_name = location["name"]
        location_country = location["country"]
        has_existing = _has_category_research(location["id"], target_category_id)
        if has_existing and not args.force:
            print(f"[skip] {location_name} ({location_country}) already has {target_category['name']} research")
            skipped += 1
            continue

        if args.dry_run:
            mode = "would refresh" if has_existing else "would research"
            print(f"[dry-run] {location_name} ({location_country}) {mode}")
            continue

        print(f"[run] {location_name} ({location_country})")
        try:
            result = research_category(
                client=client,
                location=location,
                category=target_category,
                profile_context=profile_context,
                profile_flags=profile_flags,
            )
            api_post(
                "/research",
                {
                    "location_id": location["id"],
                    "category_id": target_category_id,
                    "content": result["content"],
                    "source": result.get("source"),
                    "source_published_at": result.get("source_published_at"),
                    "source_urls": result.get("source_urls"),
                    "source_checked_at": result.get("source_checked_at"),
                    "verification_status": result.get("verification_status"),
                    "confidence": result.get("confidence"),
                },
            )
            print(f"[done] {location_name}")
            researched += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[error] {location_name}: {exc}")
            failures += 1

    print(
        f"[summary] researched={researched} skipped={skipped} failures={failures} total={len(locations)}"
    )
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
