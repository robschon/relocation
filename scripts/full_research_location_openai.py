"""Run the full OpenAI research routine for one location.

Pipeline:
1. Research all categories + visa + bespoke description
2. Generate and upsert category scores
3. Replace pros/cons with 8 pros + 8 cons
4. Export research markdown doc

Usage:
    uv run python scripts/full_research_location_openai.py "Khao Lak"
    uv run python scripts/full_research_location_openai.py --location-id 42
    uv run python scripts/full_research_location_openai.py "Khao Lak" --force-research
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

from research_location_openai import (
    api_delete,
    api_get,
    api_post,
    api_put,
    category_requires_freshness,
    get_profile_answers,
    get_profile_context,
    generate_bespoke_description,
    generate_json,
    get_existing_research,
    get_existing_visa,
    get_location_research,
    get_location_scores,
    infer_profile_flags,
    research_category,
    research_visa,
    resolve_location,
)

def get_location(location_id: int) -> dict:
    return api_get(f"/locations/{location_id}")


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


def score_category(
    client: OpenAI,
    location: dict,
    category: dict,
    research_content: str,
) -> dict:
    prompt = f"""You are scoring one relocation category for {location['name']}, {location['country']}.

Category: {category['name']}
Category description: {category.get('description') or 'N/A'}

Research evidence:
{research_content}

Return JSON only:
{{
  "score": <integer 1-10>,
  "notes": "<one concise sentence explaining the score>"
}}

Scoring guidance:
- 10 world-class
- 8-9 excellent
- 6-7 good with tradeoffs
- 4-5 notable weaknesses
- 1-3 serious concerns
"""
    result = generate_json(client, prompt, max_output_tokens=260)
    if not isinstance(result, dict):
        raise ValueError(f"Expected object JSON for score result, got {type(result).__name__}")
    score = int(result["score"])
    score = max(1, min(10, score))
    notes = str(result.get("notes", "")).strip()
    if not notes:
        notes = "Balanced assessment from current research evidence."
    return {"score": score, "notes": notes}


def generate_pros_cons(
    client: OpenAI,
    location: dict,
    categories: list[dict],
    scores: list[dict],
    research_entries: list[dict],
) -> dict:
    categories_by_id = {c["id"]: c for c in categories}
    score_by_category = {s["category_id"]: s for s in scores}
    latest_research = latest_research_by_category(research_entries)

    context_rows: list[str] = []
    for category in categories:
        cid = category["id"]
        score_entry = score_by_category.get(cid)
        if not score_entry:
            continue
        research = latest_research.get(cid)
        excerpt = (research.get("content", "") if research else "").replace("\n", " ").strip()
        excerpt = excerpt[:180] + ("..." if len(excerpt) > 180 else "")
        context_rows.append(
            f"- id={cid} | {category['name']} | score={score_entry['score']} | notes={score_entry.get('notes') or ''} | research={excerpt}"
        )

    prompt = f"""Generate relocation pros/cons for {location['name']}, {location['country']}.

Use only the evidence below:
{chr(10).join(context_rows)}

Return JSON only:
{{
  "pros": [
    {{"category_id": <int>, "content": "<single sentence>"}}
  ],
  "cons": [
    {{"category_id": <int>, "content": "<single sentence>"}}
  ]
}}

Rules:
- Exactly 8 pros and 8 cons.
- Each item must map to a valid category_id from the list.
- Content should be specific and concise (about 12-24 words).
- Pros should highlight strongest strengths.
- Cons should be honest tradeoffs or risks.
"""
    result = generate_json(client, prompt, max_output_tokens=2200)
    if not isinstance(result, dict):
        raise ValueError(f"Expected object JSON for pros/cons result, got {type(result).__name__}")

    pros = result.get("pros")
    cons = result.get("cons")
    if not isinstance(pros, list) or not isinstance(cons, list):
        raise ValueError("Pros/cons response missing list fields")

    normalized_pros: list[dict] = []
    normalized_cons: list[dict] = []

    def normalize(items: list, out: list[dict], type_name: str) -> None:
        for item in items:
            if not isinstance(item, dict):
                continue
            cid = item.get("category_id")
            content = str(item.get("content", "")).strip()
            if not isinstance(cid, int) or cid not in categories_by_id:
                continue
            if not content:
                continue
            out.append({"category_id": cid, "content": content, "type": type_name})

    normalize(pros, normalized_pros, "pro")
    normalize(cons, normalized_cons, "con")

    if len(normalized_pros) < 8 or len(normalized_cons) < 8:
        raise ValueError(
            f"Insufficient pros/cons generated (pros={len(normalized_pros)}, cons={len(normalized_cons)})"
        )

    return {
        "pros": normalized_pros[:8],
        "cons": normalized_cons[:8],
    }


def export_research_markdown(location_name: str) -> None:
    project_root = Path(__file__).resolve().parent.parent
    script = project_root / "scripts" / "export_research_markdown.py"
    subprocess.run(
        [sys.executable, str(script), location_name],
        cwd=str(project_root),
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full OpenAI research routine for one location")
    parser.add_argument("location", nargs="?", help="Location name to process")
    parser.add_argument("--location-id", type=int, help="Exact location ID to process")
    parser.add_argument("--force-research", action="store_true", help="Re-run category research even if already present")
    parser.add_argument("--skip-visa", action="store_true", help="Skip visa generation")
    parser.add_argument("--force-description", action="store_true", help="Overwrite existing location description")
    args = parser.parse_args()

    if args.location_id is not None:
        location = get_location(args.location_id)
    elif args.location:
        location = resolve_location(args.location)
    else:
        parser.error("Provide either LOCATION or --location-id.")

    location_name = location["name"]
    print(f"[start] Full routine: {location_name} ({location['country']})")

    client = OpenAI()
    profile_context = get_profile_context()
    profile_answers = get_profile_answers()
    profile_flags = infer_profile_flags(profile_answers)
    if profile_context:
        print("[context] Profile context loaded and will be used in prompts")
    else:
        print("[context] No profile context found; using location/category-only prompts")
    if profile_flags.get("is_us_citizen"):
        print("[context] Profile indicates U.S. citizenship")

    categories = api_get("/categories")
    if not isinstance(categories, list):
        raise ValueError("Categories response was not a list")

    # 1) Research categories
    existing = get_existing_research(location["id"]) if not args.force_research else set()
    print("[step] Research categories")
    research_failures: list[str] = []
    for category in categories:
        should_refresh = category_requires_freshness(category)
        if category["id"] in existing and not should_refresh:
            print(f"  [skip] {category['name']} (already researched)")
            continue
        if category["id"] in existing and should_refresh:
            print(f"  [refresh] {category['name']} (freshness policy)")
        try:
            result = research_category(
                client=client,
                location=location,
                category=category,
                profile_context=profile_context,
                profile_flags=profile_flags,
            )
            api_post(
                "/research",
                {
                    "location_id": location["id"],
                    "category_id": category["id"],
                    "content": result["content"],
                    "source": result.get("source"),
                    "source_published_at": result.get("source_published_at"),
                    "source_urls": result.get("source_urls"),
                    "source_checked_at": result.get("source_checked_at"),
                    "verification_status": result.get("verification_status"),
                    "confidence": result.get("confidence"),
                },
            )
            print(f"  [done] {category['name']}")
        except Exception as exc:
            print(f"  [error] {category['name']}: {exc}")
            research_failures.append(category["name"])

    # 2) Visa
    if not args.skip_visa:
        print("[step] Visa research")
        try:
            existing_visa = get_existing_visa(location["country"])
            if existing_visa:
                print(
                    f"  [refresh] Visa info for {location['country']} "
                    f"(replacing {len(existing_visa)} existing type(s))"
                )
                for old in existing_visa:
                    api_delete(f"/visa/{old['id']}")
            visa_types = research_visa(
                client=client,
                location=location,
                profile_context=profile_context,
                profile_flags=profile_flags,
            )
            for visa in visa_types:
                api_post(
                    "/visa",
                    {
                        "country": location["country"],
                        "visa_type": visa["visa_type"],
                        "description": visa.get("description"),
                        "residency_pathway": visa.get("residency_pathway"),
                        "requirements": visa.get("requirements"),
                        "timeline": visa.get("timeline"),
                        "cost": visa.get("cost"),
                        "notes": visa.get("notes"),
                        "source_urls": visa.get("source_urls"),
                        "source_published_at": visa.get("source_published_at"),
                        "source_checked_at": visa.get("source_checked_at"),
                        "verification_status": visa.get("verification_status"),
                        "confidence": visa.get("confidence"),
                    },
                )
            print(f"  [done] {len(visa_types)} visa type(s) for {location['country']}")
        except Exception as exc:
            print(f"  [error] Visa research: {exc}")

    # Fetch refreshed data
    research_entries = get_location_research(location["id"])
    if not isinstance(research_entries, list):
        raise ValueError("Research response was not a list")
    if not research_entries:
        raise ValueError("No research entries were created; cannot continue full routine")

    if research_failures:
        print(f"[warn] Categories with research errors: {', '.join(research_failures)}")

    latest_research = latest_research_by_category(research_entries)

    # 3) Scores
    print("[step] Generate scores")
    for category in categories:
        research = latest_research.get(category["id"])
        if not research:
            print(f"  [warn] {category['name']} has no research; skipping score")
            continue
        score_result = score_category(
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
                "score": score_result["score"],
                "notes": score_result["notes"],
            },
        )
        print(f"  [done] {category['name']}: {score_result['score']}/10")

    # 4) Pros/cons (replace existing)
    print("[step] Generate pros/cons")
    existing_pros_cons = api_get("/pros-cons", {"location_id": location["id"]})
    if not isinstance(existing_pros_cons, list):
        raise ValueError("Pros/cons response was not a list")
    for item in existing_pros_cons:
        api_delete(f"/pros-cons/{item['id']}")
    scores = get_location_scores(location["id"])
    if not isinstance(scores, list):
        raise ValueError("Scores response was not a list")
    pc = generate_pros_cons(
        client=client,
        location=location,
        categories=categories,
        scores=scores,
        research_entries=research_entries,
    )
    for pro in pc["pros"]:
        api_post(
            "/pros-cons",
            {
                "location_id": location["id"],
                "category_id": pro["category_id"],
                "type": "pro",
                "content": pro["content"],
            },
        )
    for con in pc["cons"]:
        api_post(
            "/pros-cons",
            {
                "location_id": location["id"],
                "category_id": con["category_id"],
                "type": "con",
                "content": con["content"],
            },
        )
    print(f"  [done] Pros/cons set (pros={len(pc['pros'])}, cons={len(pc['cons'])})")

    # 5) Bespoke description
    print("[step] Bespoke description")
    latest_location = get_location(location["id"])
    existing_description = (latest_location.get("description") or "").strip()
    if existing_description and not args.force_description:
        print("  [skip] Description already set (use --force-description to overwrite)")
    else:
        description, score_coverage, research_coverage = generate_bespoke_description(
            client=client,
            location=latest_location,
            categories=categories,
            scores=scores,
            research_entries=research_entries,
            profile_context=profile_context,
        )
        api_put(f"/locations/{location['id']}", {"description": description})
        print(
            f"  [done] Description set (scores: {score_coverage}/{len(categories)}, "
            f"research: {research_coverage}/{len(categories)})"
        )

    # 6) Export markdown doc
    print("[step] Export markdown")
    export_research_markdown(location_name)
    print("  [done] Research markdown exported")

    api_put(
        f"/locations/{location['id']}",
        {"full_research_ran_at": datetime.now(timezone.utc).isoformat()},
    )
    print("  [done] Full research timestamp updated")

    print(f"[done] Full routine complete for {location_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
