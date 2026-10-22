"""Prompt building blocks for v2 research.

Prompts are ordered for prompt caching: instructions (identical for every call in a
run: role, rules, rubric, profile brief) -> location block (identical for every
category of a location) -> category-specific text last.

The profile brief sends only what research needs. Finance details go only to cost and
tax (and visa, where income thresholds matter); health details only to healthcare.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from relocation.models import Category, Country, Location, ProfileResponse
from relocation.profile_builder.questions import QUESTIONS

BASE_PROFILE_KEYS = (
    "must_haves",
    "deal_breakers",
    "climate_preference",
    "languages",
    "cultural_preferences",
    "interests_hobbies",
    "exercise_activity",
    "food_preferences",
    "family_locations",
    "visit_frequency",
    "additional_notes",
)
CATEGORY_PROFILE_EXTRAS = {
    "cost_of_living": ("budget_monthly", "budget_housing"),
    "tax": ("income_sources", "tax_situation"),
    "visa": ("ages", "income_sources"),
    "healthcare": ("health_status", "healthcare_needs", "ages"),
    "travel_connectivity": ("friend_locations",),
}

RUBRIC = (
    "10 world-class; 8-9 excellent; 6-7 good with tradeoffs; 4-5 notable weaknesses; "
    "1-3 serious concerns; 0 disqualifying for these people."
)


@dataclass
class Profile:
    answers: dict[str, str]
    questions: dict[str, str]

    @classmethod
    def load(cls, session: Session) -> "Profile":
        answers = {r.question_key: r.answer.strip() for r in session.query(ProfileResponse).all() if r.answer and r.answer.strip()}
        return cls(answers=answers, questions={q.key: q.question for q in QUESTIONS})

    def lines(self, keys) -> str:
        out = []
        for key in keys:
            if key in self.answers:
                out.append(f"- {self.questions.get(key, key)} {self.answers[key]}")
        return "\n".join(out)

    def base_brief(self) -> str:
        return self.lines(BASE_PROFILE_KEYS) or "- (no profile answers yet)"

    def extras_for(self, category_key: str) -> str:
        return self.lines(CATEGORY_PROFILE_EXTRAS.get(category_key, ()))


def research_instructions(profile: Profile, *, summary_words: int, today: date) -> str:
    return f"""You research one category of one place for a couple choosing where to retire, and score it.

Who it is for:
{profile.base_brief()}

Return:
- summary: at most {summary_words} words, specific to this exact place, with numbers where they help.
- key_facts: 5-10 short facts. Give a value when there is a number, price, date or name; give source_url when the fact came from a web page.
- score: an integer 0-10 for these people. Rubric: {RUBRIC}
- score_rationale: one or two sentences naming the main reasons for the score.
- confidence: 0-1, lower when sources disagree, are old, or are about a different place.
- source_note: what the evidence rests on (see the category instructions).

Rules:
- Research the exact place given. Ignore or flag sources about a different place with the same name.
- Prefer official and primary sources; say when evidence conflicts.
- Do not invent URLs. Only give source_url for pages you actually used.

Today is {today.isoformat()}."""


def location_block(location: Location, country: Country | None) -> str:
    lines = [
        "Place (use this exact one; do not substitute another place with the same name):",
        f"- Name: {location.name}",
        f"- Country: {location.country}" + (f" ({country.code})" if country else ""),
    ]
    if country and country.parent_code:
        lines.append(f"- Jurisdiction: part of {country.parent_code}")
    if location.region:
        lines.append(f"- Region: {location.region}")
    if location.latitude is not None and location.longitude is not None:
        lines.append(f"- Coordinates: {location.latitude:.5f}, {location.longitude:.5f}")
    return "\n".join(lines)


def country_block(country: Country) -> str:
    parent = f" (part of {country.parent_code})" if country.parent_code else ""
    return f"Country: {country.name} ({country.code}){parent}\nThis category is assessed for the country as a whole."


def category_input(
    *,
    subject_block: str,
    category: Category,
    profile: Profile,
    web_search: bool,
    us_citizens_at_home: bool = False,
) -> str:
    parts = [subject_block, "", f"Category: {category.name}"]
    if category.description:
        parts.append(f"What it covers: {category.description}")
    extras = profile.extras_for(category.key)
    if extras:
        parts += ["", "Relevant profile details:", extras]
    if us_citizens_at_home:
        parts += ["", "They appear to be U.S. citizens and this is U.S. territory: treat visa/residency as no barrier "
                      "and focus on practical registration and tax-residency implications."]
    if category.requires_citation:
        parts += ["", "This changes often (visa/tax): base it on current official sources found by web search, "
                      "include at least one official URL, and say how current the information is."]
    if web_search:
        parts += ["", "Use web search for current facts and give the source_url of each fact you took from a page. "
                      "source_note: name the main sources and the date checked."]
    else:
        parts += ["", "No web search for this category: use what you know, and leave source_url empty unless you are "
                      "sure of a stable official page. source_note: \"Model knowledge (not web-verified)\"."]
    return "\n".join(parts)
