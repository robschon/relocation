from sqlalchemy.orm import Session

from relocation.countries import normalize_country_fields
from relocation.models import Category, Location, User, Weight

SEED_USERS = [("partner_a", "Partner A"), ("partner_b", "Partner B")]  # (name, display_name)

SEED_CATEGORIES = [
    {
        "name": "Cost of living / housing",
        "sort_order": 1,
        "description": "Overall affordability including rent/purchase, groceries, utilities, dining",
    },
    {
        "name": "Climate / weather",
        "sort_order": 2,
        "description": "Temperature ranges, seasons, humidity, natural disaster risk",
    },
    {
        "name": "Healthcare quality & access",
        "sort_order": 3,
        "description": "Hospital quality, specialist availability, health insurance options, costs",
    },
    {
        "name": "Visa / residency feasibility",
        "sort_order": 4,
        "description": "Ease of obtaining legal residency, visa types available, requirements",
    },
    {
        "name": "Tax implications",
        "sort_order": 5,
        "description": "Income tax, property tax, estate tax, US tax obligations, tax treaties",
    },
    {
        "name": "Safety / stability / values",
        "sort_order": 6,
        "description": "Crime rates, political stability, natural disaster preparedness, LGBTQ+ rights, progressiveness, diversity and pluralism",
    },
    {
        "name": "Language & community",
        "sort_order": 7,
        "description": "Language accessibility, cultural openness to foreigners, expat community size, English prevalence, social integration ease",
    },
    {
        "name": "Walkability / public transit",
        "sort_order": 8,
        "description": "Ability to live car-free or car-light, transit quality, bike infrastructure",
    },
    {
        "name": "Cultural amenities / lifestyle",
        "sort_order": 9,
        "description": "Museums, theaters, music, nightlife, community activities",
    },
    {
        "name": "Travel connectivity & proximity to family/friends",
        "sort_order": 10,
        "description": "Airport access, flight connections to US/family, travel time and cost",
    },
    {
        "name": "Food scene",
        "sort_order": 11,
        "description": "Restaurant quality/variety, markets, local cuisine, dietary accommodation",
    },
    {
        "name": "Natural beauty / outdoor recreation",
        "sort_order": 12,
        "description": "Scenery, parks, beaches, hiking, nature access",
    },
    {
        "name": "Environmental quality & climate risk",
        "sort_order": 13,
        "description": "Air quality, clean drinking water availability, pollution levels, climate change vulnerability (sea level rise, extreme weather trends, drought risk). Distinct from Climate/weather which covers day-to-day temperatures and seasons.",
    },
    {
        "name": "Year-round swimming viability",
        "sort_order": 14,
        "description": "Derived from monthly ocean temperature: higher scores indicate more months comfortable for swimming.",
    },
    {
        "name": "Beach accessibility",
        "sort_order": 15,
        "description": "Derived from nearest public beach distance and local beach density around each location.",
    },
]

# Behaviour flags per category (see Category in models.py).
# name -> (key, scope, kind, needs_web, requires_citation, refresh_after_days)
CATEGORY_FLAGS = {
    "Cost of living / housing": ("cost_of_living", "location", "researched", True, False, 365),
    "Climate / weather": ("climate", "location", "researched", False, False, None),
    "Healthcare quality & access": ("healthcare", "location", "researched", True, False, 365),
    "Visa / residency feasibility": ("visa", "country", "researched", True, True, 90),
    "Tax implications": ("tax", "location", "researched", True, True, 90),
    "Safety / stability / values": ("safety_values", "location", "researched", False, False, 365),
    "Language & community": ("language_community", "location", "researched", False, False, None),
    "Walkability / public transit": ("walkability", "location", "researched", False, False, None),
    "Cultural amenities / lifestyle": ("culture", "location", "researched", False, False, None),
    "Travel connectivity & proximity to family/friends": ("travel_connectivity", "location", "researched", True, False, 365),
    "Food scene": ("food", "location", "researched", False, False, None),
    "Natural beauty / outdoor recreation": ("nature", "location", "researched", False, False, None),
    "Environmental quality & climate risk": ("environment_climate_risk", "location", "researched", False, False, None),
    "Year-round swimming viability": ("swimming", "location", "derived", False, False, None),
    "Beach accessibility": ("beach_access", "location", "derived", False, False, None),
}
for _category in SEED_CATEGORIES:
    _key, _scope, _kind, _web, _cite, _refresh = CATEGORY_FLAGS[_category["name"]]
    _category.update(
        key=_key,
        scope=_scope,
        kind=_kind,
        needs_web=_web,
        requires_citation=_cite,
        refresh_after_days=_refresh,
    )

SEED_LOCATIONS = [
    {
        "name": "Osa Peninsula",
        "country": "Costa Rica",
        "region": "Central America",
        "description": "Remote, biodiverse Pacific coast region known for Corcovado National Park",
    },
    {
        "name": "Fremantle",
        "country": "Australia",
        "region": "Western Australia",
        "population": 30000,
        "description": "Historic port city near Perth with strong arts scene and maritime character",
    },
    {
        "name": "Baja Peninsula",
        "country": "Mexico",
        "region": "North America",
        "description": "Desert peninsula with Pacific and Sea of Cortez coastlines, popular with US expats",
    },
    {
        "name": "Lima",
        "country": "Peru",
        "region": "South America",
        "population": 10000000,
        "description": "Capital city, world-renowned food scene, mild desert climate on the Pacific coast",
    },
]

DEFAULT_WEIGHT = 5.0


def seed_database(session: Session) -> dict[str, int]:
    """Seed the database with initial data. Returns counts of created items."""
    counts = {"users": 0, "categories": 0, "locations": 0, "weights": 0}

    # Users
    for name, display_name in SEED_USERS:
        if not session.query(User).filter_by(name=name).first():
            session.add(User(name=name, display_name=display_name))
            counts["users"] += 1

    session.flush()

    # Categories
    for cat_data in SEED_CATEGORIES:
        if not session.query(Category).filter_by(name=cat_data["name"]).first():
            session.add(Category(**cat_data))
            counts["categories"] += 1

    session.flush()

    # Locations
    for loc_data in SEED_LOCATIONS:
        normalized_country, normalized_country_code = normalize_country_fields(
            country=loc_data["country"]
        )
        if not session.query(Location).filter_by(
            name=loc_data["name"], country=normalized_country
        ).first():
            normalized_location = {
                **loc_data,
                "country": normalized_country,
                "country_code": normalized_country_code,
            }
            session.add(
                Location(**normalized_location)
            )
            counts["locations"] += 1

    session.flush()

    # Default weights (5 for all categories for both users)
    users = session.query(User).all()
    categories = session.query(Category).all()
    for user in users:
        for category in categories:
            if not session.query(Weight).filter_by(
                user_id=user.id, category_id=category.id
            ).first():
                session.add(
                    Weight(user_id=user.id, category_id=category.id, weight=DEFAULT_WEIGHT)
                )
                counts["weights"] += 1

    session.commit()
    return counts
