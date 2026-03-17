"""Populate research data for a location using Claude API.

Usage:
    uv run python scripts/research_location.py Fremantle
    uv run python scripts/research_location.py Fremantle --force
    uv run python scripts/research_location.py Fremantle --category "Cost"
    uv run python scripts/research_location.py Fremantle --force-description
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime

import anthropic
import httpx

API_BASE = "http://localhost:8000/api/v1"
MODEL = "claude-sonnet-4-6"
MAX_RETRIES = 2
RETRY_DELAY = 2
STRICT_FRESHNESS_CATEGORY_NAMES = {"Visa / residency feasibility", "Tax implications"}


def api_get(path: str, params: dict | None = None) -> list | dict:
    r = httpx.get(f"{API_BASE}{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def api_post(path: str, data: dict) -> dict:
    r = httpx.post(f"{API_BASE}{path}", json=data, timeout=30)
    r.raise_for_status()
    return r.json()


def api_put(path: str, data: dict) -> dict:
    r = httpx.put(f"{API_BASE}{path}", json=data, timeout=30)
    r.raise_for_status()
    return r.json()


def api_delete(path: str) -> None:
    r = httpx.delete(f"{API_BASE}{path}", timeout=30)
    r.raise_for_status()


def resolve_location(name: str) -> dict:
    locations = api_get("/locations")
    name_lower = name.lower()
    for loc in locations:
        if name_lower in loc["name"].lower():
            return loc
    print(f"Error: No location matching '{name}' found.")
    print(f"Available: {', '.join(loc['name'] for loc in locations)}")
    sys.exit(1)


def get_existing_research(location_id: int) -> set[int]:
    entries = api_get("/research", {"location_id": location_id})
    return {e["category_id"] for e in entries if e["category_id"] is not None}


def get_existing_visa(country: str) -> list:
    return api_get("/visa", {"country": country})


def get_location_scores(location_id: int) -> list[dict]:
    return api_get(f"/locations/{location_id}/scores")


def get_location_research(location_id: int) -> list[dict]:
    return api_get("/research", {"location_id": location_id})


def get_location(location_id: int) -> dict:
    return api_get(f"/locations/{location_id}")


def parse_json_response(text: str) -> dict | list:
    """Parse JSON from Claude's response, stripping markdown fences if present."""
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    return json.loads(cleaned)


def _normalize_urls(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = re.split(r"[\s,]+", value.strip())
    elif isinstance(value, list):
        candidates = [str(v).strip() for v in value]
    else:
        return []

    urls: list[str] = []
    for candidate in candidates:
        if candidate.startswith(("http://", "https://")):
            urls.append(candidate)
    return urls


def _parse_confidence(value: object) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, parsed))


def category_requires_freshness(category: dict) -> bool:
    return (category.get("name") or "").strip() in STRICT_FRESHNESS_CATEGORY_NAMES


def format_location_context(location: dict) -> str:
    """Render an exact-location block that reduces same-name place ambiguity."""
    lines = [
        "Target location (use this exact place; do not substitute another same-name place):",
        f"- Name: {location['name']}",
        f"- Country: {location['country']}",
    ]

    region = str(location.get("region") or "").strip()
    if region:
        lines.append(f"- Region: {region}")

    latitude = location.get("latitude")
    longitude = location.get("longitude")
    if latitude is not None and longitude is not None:
        lines.append(f"- Coordinates: {float(latitude):.5f}, {float(longitude):.5f}")

    lines.append("- If a source is about a different same-name place, ignore it or explicitly note the mismatch.")
    return "\n".join(lines)


def _normalize_iso_date(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "unknown", "n/a", "na"}:
        return None

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            datetime.strptime(text, "%Y-%m-%d")
            return text
        except ValueError:
            return None

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.date().isoformat()
    except ValueError:
        return None


def generate_json(
    client: anthropic.Anthropic,
    prompt: str,
    max_tokens: int,
) -> dict | list:
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            return parse_json_response(text)
        except json.JSONDecodeError:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
                continue
            raise
        except anthropic.RateLimitError:
            wait = RETRY_DELAY * (2**attempt)
            print(f"    [rate limited] Waiting {wait}s...")
            time.sleep(wait)
            if attempt == MAX_RETRIES:
                raise


def research_category(
    client: anthropic.Anthropic,
    location: dict,
    category: dict,
) -> dict:
    """Ask Claude to research a single category for a location."""
    strict_mode = category_requires_freshness(category)
    strict_instruction = ""
    if strict_mode:
        strict_instruction = """This is a high-volatility category (visa/tax). You must use live web research and provide dated citations.
- Do not use "general knowledge" as a source basis.
- Include at least one official source URL and one corroborating secondary URL.
- If evidence conflicts, state uncertainty in source text and lower confidence."""

    prompt = f"""Research this exact location for the category: {category['name']}.

{format_location_context(location)}

{f"Category description: {category['description']}" if category.get('description') else ""}
{strict_instruction}

Provide detailed, factual research notes that would help someone evaluating this location for retirement/relocation. Include specific data points, numbers, and comparisons where possible.
- Do not switch to another city/town/municipality that shares part or all of the same name.

Respond with JSON only (no markdown fences):
{{
  "content": "Your detailed research notes (multiple paragraphs, use \\n for line breaks)",
  "source": "Brief description of evidence basis and when checked (e.g. 'Web research checked March 2026')",
  "source_urls": ["https://example.gov/...", "https://example.com/..."],
  "source_published_at": "YYYY-MM-DD or null if unknown (do not use ranges like '2023-2026')",
  "source_checked_at": "YYYY-MM-DD",
  "verification_status": "verified or needs_review",
  "confidence": 0.0
}}"""
    result = generate_json(client, prompt, max_tokens=2048)
    if not isinstance(result, dict):
        raise ValueError(f"Expected object JSON for category result, got {type(result).__name__}")

    source_urls = _normalize_urls(result.get("source_urls"))
    source_published_at = _normalize_iso_date(result.get("source_published_at"))
    source_checked_at = str(result.get("source_checked_at") or date.today().isoformat())
    source = str(result.get("source") or "").strip()
    confidence = _parse_confidence(result.get("confidence"))

    if strict_mode:
        if not source or "general knowledge" in source.lower():
            raise ValueError(f"{category['name']} requires dated citation evidence, not general knowledge")
        if not source_urls:
            raise ValueError(f"{category['name']} requires source URLs")
        if confidence is None:
            confidence = 0.65

    result["source_urls"] = source_urls or None
    result["source_published_at"] = source_published_at
    result["source_checked_at"] = source_checked_at
    result["source"] = source or None
    result["verification_status"] = str(result.get("verification_status") or "needs_review")
    result["confidence"] = confidence
    return result


def research_visa(
    client: anthropic.Anthropic,
    location: dict,
) -> list[dict]:
    """Ask Claude to research visa/residency options for the country."""
    prompt = f"""Research visa and residency options for {location['country']} that would be relevant to retirees or people relocating from the US/UK/EU.

Provide the most relevant visa types (typically 2-5).
Use live web sources from official government immigration pages when available.
Do not rely on general knowledge.

Respond with JSON only (no markdown fences):
[
  {{
    "visa_type": "Name of the visa",
    "description": "Brief description of the visa",
    "residency_pathway": "Whether/how this leads to permanent residency",
    "requirements": "Key requirements (age, income, investment, etc.)",
    "timeline": "Typical processing time",
    "cost": "Application fees and costs",
    "notes": "Any additional relevant notes",
    "source_urls": ["https://example.gov/...", "https://example.com/..."],
    "source_published_at": "YYYY-MM-DD or null if unknown (do not use ranges like '2023-2026')",
    "source_checked_at": "YYYY-MM-DD",
    "verification_status": "verified or needs_review",
    "confidence": 0.0
  }}
]"""
    result = generate_json(client, prompt, max_tokens=4096)
    if not isinstance(result, list):
        raise ValueError(f"Expected array JSON for visa result, got {type(result).__name__}")
    today = date.today().isoformat()
    normalized: list[dict] = []
    for visa in result:
        if not isinstance(visa, dict):
            continue
        urls = _normalize_urls(visa.get("source_urls"))
        if not urls:
            continue
        confidence = _parse_confidence(visa.get("confidence"))
        if confidence is None:
            confidence = 0.65
        normalized.append(
            {
                **visa,
                "source_urls": urls,
                "source_published_at": _normalize_iso_date(visa.get("source_published_at")),
                "source_checked_at": str(visa.get("source_checked_at") or today),
                "verification_status": str(visa.get("verification_status") or "verified"),
                "confidence": confidence,
            }
        )
    if not normalized:
        raise ValueError("No visa entries with usable citations were generated")
    return normalized


def build_description_context(
    categories: list[dict],
    scores: list[dict],
    research_entries: list[dict],
) -> tuple[str, int, int]:
    score_map = {s["category_id"]: s for s in scores if s.get("category_id") is not None}

    latest_research: dict[int, dict] = {}
    for entry in research_entries:
        cat_id = entry.get("category_id")
        if cat_id is None:
            continue
        prev = latest_research.get(cat_id)
        if prev is None or entry.get("id", 0) > prev.get("id", 0):
            latest_research[cat_id] = entry

    coverage_scores = len(score_map)
    coverage_research = len(latest_research)

    scored_rows: list[dict] = []
    for cat in categories:
        cat_id = cat["id"]
        score_entry = score_map.get(cat_id)
        if not score_entry:
            continue
        research = latest_research.get(cat_id)
        content = (research.get("content", "") if research else "").replace("\n", " ").strip()
        excerpt = content[:220] + ("..." if len(content) > 220 else "") if content else "No research excerpt."
        scored_rows.append(
            {
                "name": cat["name"],
                "score": int(score_entry["score"]),
                "notes": (score_entry.get("notes") or "").strip(),
                "research_excerpt": excerpt,
            }
        )

    scored_rows.sort(key=lambda r: r["score"], reverse=True)
    top_rows = scored_rows[:4]
    low_row = sorted(scored_rows, key=lambda r: r["score"])[0] if scored_rows else None

    lines = ["Top strengths (from current scoring + research):"]
    for row in top_rows:
        note = f" | score note: {row['notes']}" if row["notes"] else ""
        lines.append(f"- {row['name']} | score={row['score']}{note} | research: {row['research_excerpt']}")
    if low_row:
        low_note = f" | score note: {low_row['notes']}" if low_row["notes"] else ""
        lines.append(
            f"Weakest area to respect: {low_row['name']} | score={low_row['score']}"
            f"{low_note} | research: {low_row['research_excerpt']}"
        )

    return "\n".join(lines), coverage_scores, coverage_research


def generate_bespoke_description(
    client: anthropic.Anthropic,
    location: dict,
    categories: list[dict],
    scores: list[dict],
    research_entries: list[dict],
) -> tuple[str, int, int]:
    context, score_coverage, research_coverage = build_description_context(
        categories=categories,
        scores=scores,
        research_entries=research_entries,
    )

    prompt = f"""Write one bespoke location description for a relocation shortlist card.

Location:
- Name: {location['name']}
- Country: {location['country']}
- Region: {location.get('region') or 'N/A'}

Style:
- Glossy travel-magazine voice, but still credible and specific.
- 28-42 words, one sentence.
- Do NOT include numeric scores, ratings, or slash notation (e.g., 8/10).
- Avoid generic filler and avoid repeating exact phrase patterns.

Use this evidence context:
{context}

Respond with JSON only:
{{
  "description": "One-sentence bespoke description"
}}
"""

    result = generate_json(client, prompt, max_tokens=320)
    if not isinstance(result, dict) or "description" not in result:
        raise ValueError("Expected JSON object with a 'description' field")
    description = str(result["description"]).strip()
    if not description:
        raise ValueError("Generated description is empty")
    return description, score_coverage, research_coverage


def main():
    parser = argparse.ArgumentParser(description="Research a location using Claude API")
    parser.add_argument("location", help="Location name to research (e.g. Fremantle)")
    parser.add_argument(
        "--force", action="store_true", help="Re-research all categories"
    )
    parser.add_argument(
        "--category",
        help="Research only a specific category (substring match)",
    )
    parser.add_argument(
        "--skip-visa", action="store_true", help="Skip visa research"
    )
    parser.add_argument(
        "--skip-description",
        action="store_true",
        help="Skip bespoke location description generation",
    )
    parser.add_argument(
        "--force-description",
        action="store_true",
        help="Overwrite existing location description",
    )
    args = parser.parse_args()

    # Resolve location
    location = resolve_location(args.location)
    print(f"Researching {location['name']} ({location['country']})...")

    # Fetch categories
    categories = api_get("/categories")

    # Filter to specific category if requested
    if args.category:
        cat_lower = args.category.lower()
        categories = [c for c in categories if cat_lower in c["name"].lower()]
        if not categories:
            print(f"Error: No category matching '{args.category}'")
            sys.exit(1)

    # Check existing research
    existing = get_existing_research(location["id"]) if not args.force else set()

    # Init Claude client
    client = anthropic.Anthropic()

    # Research each category
    for cat in categories:
        should_refresh = category_requires_freshness(cat)
        if cat["id"] in existing and not should_refresh:
            print(f"  [skip] {cat['name']} (already researched)")
            continue
        if cat["id"] in existing and should_refresh:
            print(f"  [refresh] {cat['name']} (freshness policy)")

        try:
            result = research_category(client, location, cat)
            api_post(
                "/research",
                {
                    "location_id": location["id"],
                    "category_id": cat["id"],
                    "content": result["content"],
                    "source": result.get("source"),
                    "source_published_at": result.get("source_published_at"),
                    "source_urls": result.get("source_urls"),
                    "source_checked_at": result.get("source_checked_at"),
                    "verification_status": result.get("verification_status"),
                    "confidence": result.get("confidence"),
                },
            )
            print(f"  [done] {cat['name']}")
        except Exception as e:
            print(f"  [error] {cat['name']}: {e}")

    # Visa research
    if not args.skip_visa:
        existing_visa = get_existing_visa(location["country"])
        try:
            if existing_visa:
                print(
                    f"  [refresh] Visa info for {location['country']} "
                    f"(replacing {len(existing_visa)} existing type(s))"
                )
                for old in existing_visa:
                    api_delete(f"/visa/{old['id']}")
            visa_types = research_visa(client, location)
            for v in visa_types:
                api_post(
                    "/visa",
                    {
                        "country": location["country"],
                        "visa_type": v["visa_type"],
                        "description": v.get("description"),
                        "residency_pathway": v.get("residency_pathway"),
                        "requirements": v.get("requirements"),
                        "timeline": v.get("timeline"),
                        "cost": v.get("cost"),
                        "notes": v.get("notes"),
                        "source_urls": v.get("source_urls"),
                        "source_published_at": v.get("source_published_at"),
                        "source_checked_at": v.get("source_checked_at"),
                        "verification_status": v.get("verification_status"),
                        "confidence": v.get("confidence"),
                    },
                )
            print(f"  [done] {len(visa_types)} visa type(s) for {location['country']}")
        except Exception as e:
            print(f"  [error] Visa research: {e}")

    # Bespoke location description
    if not args.skip_description:
        latest_location = get_location(location["id"])
        existing_description = (latest_location.get("description") or "").strip()

        if existing_description and not args.force_description:
            print("  [skip] Bespoke description (already set; use --force-description to overwrite)")
        else:
            try:
                all_categories = api_get("/categories")
                all_scores = get_location_scores(location["id"])
                all_research = get_location_research(location["id"])
                description, score_coverage, research_coverage = generate_bespoke_description(
                    client=client,
                    location=latest_location,
                    categories=all_categories,
                    scores=all_scores,
                    research_entries=all_research,
                )
                api_put(f"/locations/{location['id']}", {"description": description})
                print(
                    "  [done] Bespoke description "
                    f"(scores: {score_coverage}/{len(all_categories)}, "
                    f"research: {research_coverage}/{len(all_categories)})"
                )
            except Exception as e:
                print(f"  [error] Description generation: {e}")

    print("Done.")


if __name__ == "__main__":
    main()
