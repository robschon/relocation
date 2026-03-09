"""Normalize location descriptions using existing scorecard toplines.

For each location, generate a concise one-line summary with personality:
- strongest two categories
- primary watchout category
No numeric score text is included in the final description.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re

from relocation.database import SessionLocal
from relocation.models import Location

CATEGORY_LABELS = {
    "Cost of living / housing": "affordability",
    "Climate / weather": "climate",
    "Healthcare quality & access": "healthcare access",
    "Visa / residency feasibility": "residency pathways",
    "Tax implications": "tax profile",
    "Safety / stability / values": "safety/stability",
    "Language & community": "community fit",
    "Walkability / public transit": "walkability/transit",
    "Cultural amenities / lifestyle": "culture/lifestyle",
    "Travel connectivity & proximity to family/friends": "travel connectivity",
    "Food scene": "food scene",
    "Natural beauty / outdoor recreation": "outdoor access",
    "Environmental quality & climate risk": "environmental resilience",
}

STRENGTH_COPY = {
    "affordability": "wallet-friendly living",
    "climate": "sun-friendly weather",
    "healthcare access": "reliable healthcare access",
    "residency pathways": "clear residency pathways",
    "tax profile": "a workable tax setup",
    "safety/stability": "a steady day-to-day feel",
    "community fit": "an easy community landing",
    "walkability/transit": "car-light convenience",
    "culture/lifestyle": "culture and lifestyle depth",
    "travel connectivity": "easy travel links",
    "food scene": "a food scene worth planning your week around",
    "outdoor access": "serious outdoor access",
    "environmental resilience": "a sturdier environmental profile",
}

WATCHOUT_COPY = {
    "affordability": "housing costs can spike in the most desirable pockets",
    "climate": "weather patterns may not match everyone's comfort zone",
    "healthcare access": "specialist depth can require extra planning",
    "residency pathways": "visa paperwork can test your patience",
    "tax profile": "tax planning deserves a spreadsheet and a strong coffee",
    "safety/stability": "neighborhood selection and street-smarts still matter",
    "community fit": "finding your people can take a little time",
    "walkability/transit": "car-free daily life may need deliberate neighborhood choice",
    "culture/lifestyle": "the cultural pace can feel quieter than expected",
    "travel connectivity": "long-haul trips can mean extra hops and layovers",
    "food scene": "the dining mix may feel narrower long-term",
    "outdoor access": "great nature does not always mean easy daily access",
    "environmental resilience": "climate and infrastructure risk should stay on the checklist",
}

VOICE_CONFIG = {
    "mediterranean": {
        "templates": [
            "{name} has that Mediterranean cadence: {s1}, {s2}, and a lifestyle built around being outside. {caveat}",
            "Long lunches, sea air, and a practical core of {s1} plus {s2} make {name} easy to like. {caveat}",
            "{name} works best for people chasing {s1} and {s2} with a slower, social daily rhythm. {caveat}",
            "{name} balances old-world charm with day-to-day practicality, especially on {s1} and {s2}. {caveat}",
            "If your ideal routine is walk, coffee, sea, repeat, {name} backs it up with {s1} and {s2}. {caveat}",
        ],
        "caveat_prefixes": ["Tradeoff", "Fine print", "Worth planning for"],
        "softeners": [
            "Great fit if you like your weeks more promenade than grind.",
            "The charm is real, but planning details still matter.",
        ],
    },
    "island": {
        "templates": [
            "{name} is salt-air living with substance: {s1} up front, {s2} close behind. {caveat}",
            "In {name}, the headline is island energy, backed by {s1} and {s2}. {caveat}",
            "{name} suits people who want their daily routine anchored by {s1} and {s2}, not city noise. {caveat}",
            "{name} leans into laid-back island pace without giving up the practical upside of {s1} and {s2}. {caveat}",
            "For an island base that still feels livable long-term, {name} stands on {s1} and {s2}. {caveat}",
        ],
        "caveat_prefixes": ["Reality check", "Practical catch", "Watch the details on"],
        "softeners": [
            "If remoteness feels like freedom to you, this can work beautifully.",
            "The upside is lifestyle quality; the cost is usually convenience.",
        ],
    },
    "urban_coast": {
        "templates": [
            "{name} delivers an urban-coastal mix where {s1} and {s2} do the heavy lifting. {caveat}",
            "For city people who still want the coast nearby, {name} leans into {s1} and {s2}. {caveat}",
            "{name} has big-city momentum with coastal breathing room, led by {s1} and {s2}. {caveat}",
            "{name} feels dynamic without being all concrete, and {s1} with {s2} are big reasons why. {caveat}",
            "{name} is a practical city pick with coastal perks, especially around {s1} and {s2}. {caveat}",
        ],
        "caveat_prefixes": ["Friction point", "Tradeoff", "Keep an eye on"],
        "softeners": [
            "It rewards people who like options and can tolerate some complexity.",
            "Strong upside, as long as your logistics tolerance is decent.",
        ],
    },
    "nature_forward": {
        "templates": [
            "{name} is nature-first living, and {s1} with {s2} are central to the appeal. {caveat}",
            "If your ideal week includes more horizon than traffic, {name} makes a strong case through {s1} and {s2}. {caveat}",
            "{name} puts outdoor rhythm ahead of urban buzz, with {s1} and {s2} setting the tone. {caveat}",
            "{name} is less about city polish and more about everyday access to {s1} and {s2}. {caveat}",
            "People who recharge outdoors tend to click with {name}, mostly because of {s1} and {s2}. {caveat}",
        ],
        "caveat_prefixes": ["Practical catch", "Planning note", "Watchout"],
        "softeners": [
            "Great for self-directed people who can plan around constraints.",
            "The payback is quality of life if you accept a little friction.",
        ],
    },
    "general_coast": {
        "templates": [
            "{name} stands out on {s1} and {s2}, with a coastal pace that many people find sustainable. {caveat}",
            "{name} is a balanced contender built on {s1} plus {s2}. {caveat}",
            "For a broad relocation shortlist, {name} earns attention through {s1} and {s2}. {caveat}",
            "{name} has a well-rounded profile where {s1} and {s2} are the biggest draws. {caveat}",
            "{name} combines everyday livability with coastal upside, anchored by {s1} and {s2}. {caveat}",
        ],
        "caveat_prefixes": ["Watchout", "Tradeoff", "Keep in mind"],
        "softeners": [
            "Worth a close look if your priorities align.",
            "Not one-size-fits-all, but compelling in the right profile.",
        ],
    },
}

GENUINELY_LOCATION = "San Sebastian"
LOCATION_VOICE_OVERRIDES = {
    "Todos Santos / Cerritos": "nature_forward",
    "Golfito": "nature_forward",
    "Osa Peninsula": "nature_forward",
    "Kaikoura": "nature_forward",
    "Brooklyn": "urban_coast",
    "East Bay (Oakland/Berkeley)": "urban_coast",
}


def _label(category_name: str) -> str:
    return CATEGORY_LABELS.get(category_name, category_name.lower())


def _top_strengths(scored_categories: list[tuple[str, int]]) -> tuple[str, str]:
    # Prefer truly standout scores first; if fewer than 2, fill from best remaining.
    standout = [name for name, score in scored_categories if score >= 8]
    if len(standout) >= 2:
        return _label(standout[0]), _label(standout[1])

    best = [name for name, _ in scored_categories]
    merged: list[str] = []
    for cat in standout + best:
        if cat not in merged:
            merged.append(cat)
        if len(merged) == 2:
            break
    if len(merged) == 1:
        return _label(merged[0]), "overall livability"
    return _label(merged[0]), _label(merged[1])


def _watchout(scored_categories: list[tuple[str, int]]) -> tuple[str, int]:
    low_name, low_score = sorted(scored_categories, key=lambda x: (x[1], x[0]))[0]
    return _label(low_name), low_score


def _pick(options: list[str], key: str) -> str:
    h = int(hashlib.sha1(key.encode("utf-8")).hexdigest(), 16)
    return options[h % len(options)]


def _voice_for_location(name: str, country: str, region: str | None) -> str:
    if name in LOCATION_VOICE_OVERRIDES:
        return LOCATION_VOICE_OVERRIDES[name]

    text = f"{name} {country} {region or ''}".lower()

    if country in {"Spain", "Portugal", "Italy", "Croatia", "Malta"}:
        return "mediterranean"

    if any(
        token in text
        for token in [
            "island",
            "isla ",
            "ilha ",
            "bay islands",
            "bocas del toro",
            "hawaii",
            "roatan",
            "kona",
        ]
    ):
        return "island"

    if any(token in text for token in ["peninsula", "kaikoura", "golfito", "dauin"]):
        return "nature_forward"

    if any(token in text for token in ["brooklyn", "oakland", "berkeley", "lima", "cape town", "valparaiso"]):
        return "urban_coast"

    if country in {"United States", "Colombia", "Mexico", "Vietnam", "Uruguay", "Australia", "Chile", "Peru"}:
        return "urban_coast"

    return "general_coast"


def _caveat_line(location_name: str, voice: str, watchout_label: str, watchout_score: int) -> str:
    base = WATCHOUT_COPY.get(watchout_label, f"{watchout_label} needs attention")
    prefix_key = f"{location_name.lower()}::{watchout_label}::{watchout_score}"
    voice_cfg = VOICE_CONFIG[voice]
    prefix = _pick(voice_cfg["caveat_prefixes"], prefix_key)
    if watchout_score <= 5:
        return f"{prefix}: {base}."
    if watchout_score <= 6:
        return f"{prefix}: {base}."
    softener = _pick(voice_cfg["softeners"], prefix_key + "::soft")
    return f"{prefix}: {base}. {softener}"


def _inject_single_genuinely(location_name: str, description: str, strength1: str, strength2: str) -> str:
    # Hard guard: only one location gets "genuinely", and only once.
    if location_name != GENUINELY_LOCATION:
        return re.sub(r"\bgenuinely\b", "", description, flags=re.IGNORECASE).replace("  ", " ").strip()

    if "food scene" in strength1 or "food scene" in strength2:
        return description.replace(
            "a food scene worth planning your week around",
            "a genuinely brilliant food scene",
            1,
        )

    return description + " And yes, one genuinely standout quality still shows up in the lived experience."


def build_description(location_name: str, country: str, region: str | None, scored_categories: list[tuple[str, int]]) -> str:
    if not scored_categories:
        return "Still gathering the full picture here, but early signals suggest this one is worth a closer look."

    voice = _voice_for_location(location_name, country, region)
    strength1, strength2 = _top_strengths(scored_categories)
    watchout_label, watchout_score = _watchout(scored_categories)
    s1_copy = STRENGTH_COPY.get(strength1, strength1)
    s2_copy = STRENGTH_COPY.get(strength2, strength2)
    caveat = _caveat_line(location_name, voice, watchout_label, watchout_score)
    template = _pick(VOICE_CONFIG[voice]["templates"], location_name.lower())

    description = template.format(
        name=location_name,
        s1=s1_copy,
        s2=s2_copy,
        caveat=caveat,
    )
    return _inject_single_genuinely(location_name, description, strength1, strength2)


def main() -> int:
    with SessionLocal() as session:
        locations = session.query(Location).order_by(Location.name).all()
        now = datetime.now(timezone.utc)

        for loc in locations:
            scored = sorted(
                ((s.category.name, s.score) for s in loc.scores),
                key=lambda x: (-x[1], x[0]),
            )
            loc.description = build_description(loc.name, loc.country, loc.region, scored)
            loc.updated_at = now
            print(f"[updated] {loc.name}: {loc.description}")

        session.commit()

    print(f"Done. Updated descriptions for {len(locations)} locations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
