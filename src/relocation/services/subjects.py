"""Route research and scores to the right subject: a location, or its country for
country-scope categories."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from relocation.models import Category, Location
from relocation.services.errors import NotFound, ValidationFailed


@dataclass
class Subject:
    category: Category | None
    location_id: int | None
    country_code: str | None
    # The location the caller asked about, if any (for building responses).
    requested_location_id: int | None


def resolve_subject(
    db: Session,
    *,
    category_id: int | None,
    location_id: int | None,
    country_code: str | None,
) -> Subject:
    category = db.get(Category, category_id) if category_id is not None else None
    if category_id is not None and category is None:
        raise NotFound("Category not found")

    location = db.get(Location, location_id) if location_id is not None else None
    if location_id is not None and location is None:
        raise NotFound("Location not found")

    if category is not None and category.scope == "country":
        code = (country_code or (location.country_code if location else None) or "").upper() or None
        if not code:
            raise ValidationFailed(f"{category.name} is per country: give location_id or country_code.")
        if location is not None and location.country_code != code:
            raise ValidationFailed("country_code does not match the location's country.")
        return Subject(category, None, code, location_id)

    if location is None:
        raise ValidationFailed("location_id is required for location-level categories.")
    return Subject(category, location.id, None, location.id)
