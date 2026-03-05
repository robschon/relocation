"""Populate research data for a location using OpenAI API.

Usage:
    uv run python scripts/research_location_openai.py Fremantle
    uv run python scripts/research_location_openai.py Fremantle --force
    uv run python scripts/research_location_openai.py Fremantle --category "Cost"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

import httpx
from openai import OpenAI, RateLimitError

API_BASE = "http://localhost:8000/api/v1"
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
MAX_RETRIES = 2
RETRY_DELAY = 2


def api_get(path: str, params: dict | None = None) -> list | dict:
    r = httpx.get(f"{API_BASE}{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def api_post(path: str, data: dict) -> dict:
    r = httpx.post(f"{API_BASE}{path}", json=data, timeout=30)
    r.raise_for_status()
    return r.json()


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


def parse_json_response(text: str) -> dict | list:
    """Parse JSON from model output, stripping markdown fences if present."""
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    return json.loads(cleaned)


def generate_json(client: OpenAI, prompt: str, max_output_tokens: int = 2048) -> dict | list:
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.responses.create(
                model=MODEL,
                input=prompt,
                max_output_tokens=max_output_tokens,
            )
            text = response.output_text
            return parse_json_response(text)
        except json.JSONDecodeError:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
                continue
            raise
        except RateLimitError:
            wait = RETRY_DELAY * (2**attempt)
            print(f"    [rate limited] Waiting {wait}s...")
            time.sleep(wait)
            if attempt == MAX_RETRIES:
                raise


def research_category(client: OpenAI, location: dict, category: dict) -> dict:
    """Ask OpenAI to research a single category for a location."""
    prompt = f"""Research {location['name']}, {location['country']} for the category: {category['name']}.

{f"Category description: {category['description']}" if category.get('description') else ""}

Provide detailed, factual research notes that would help someone evaluating this location for retirement/relocation. Include specific data points, numbers, and comparisons where possible.

Respond with JSON only (no markdown fences):
{{
  "content": "Your detailed research notes (multiple paragraphs, use \\n for line breaks)",
  "source": "Brief description of knowledge basis, e.g. 'General knowledge as of 2025'"
}}"""

    result = generate_json(client, prompt, max_output_tokens=2048)
    if not isinstance(result, dict):
        raise ValueError(f"Expected object JSON for category result, got {type(result).__name__}")
    return result


def research_visa(client: OpenAI, location: dict) -> list[dict]:
    """Ask OpenAI to research visa/residency options for the country."""
    prompt = f"""Research visa and residency options for {location['country']} that would be relevant to retirees or people relocating from the US/UK/EU.

Provide the most relevant visa types (typically 2-5).

Respond with JSON only (no markdown fences):
[
  {{
    "visa_type": "Name of the visa",
    "description": "Brief description of the visa",
    "residency_pathway": "Whether/how this leads to permanent residency",
    "requirements": "Key requirements (age, income, investment, etc.)",
    "timeline": "Typical processing time",
    "cost": "Application fees and costs",
    "notes": "Any additional relevant notes"
  }}
]"""

    result = generate_json(client, prompt, max_output_tokens=4096)
    if not isinstance(result, list):
        raise ValueError(f"Expected array JSON for visa result, got {type(result).__name__}")
    return result


def main():
    parser = argparse.ArgumentParser(description="Research a location using OpenAI API")
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

    # Init OpenAI client
    client = OpenAI()

    # Research each category
    for cat in categories:
        if cat["id"] in existing:
            print(f"  [skip] {cat['name']} (already researched)")
            continue

        try:
            result = research_category(client, location, cat)
            api_post(
                "/research",
                {
                    "location_id": location["id"],
                    "category_id": cat["id"],
                    "content": result["content"],
                    "source": result.get("source"),
                },
            )
            print(f"  [done] {cat['name']}")
        except Exception as e:
            print(f"  [error] {cat['name']}: {e}")

    # Visa research
    if not args.skip_visa:
        existing_visa = get_existing_visa(location["country"])
        if existing_visa and not args.force:
            print(
                f"  [skip] Visa info for {location['country']} "
                f"({len(existing_visa)} type(s) already exist)"
            )
        else:
            try:
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
                        },
                    )
                print(f"  [done] {len(visa_types)} visa type(s) for {location['country']}")
            except Exception as e:
                print(f"  [error] Visa research: {e}")

    print("Done.")


if __name__ == "__main__":
    main()
