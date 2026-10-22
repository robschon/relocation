from collections import Counter

from sqlalchemy import func
from sqlalchemy.orm import Session

from relocation.models import DEFAULT_PROVIDER, Category, Location
from relocation.services.effective_scores import effective_scores


def get_fully_scored_location_ids(session: Session, provider: str = DEFAULT_PROVIDER) -> set[int]:
    """Locations with a score in every category (country-scope categories count via the country)."""
    category_count = session.query(func.count(Category.id)).scalar() or 0
    if category_count == 0:
        return {location_id for (location_id,) in session.query(Location.id).all()}

    per_location = Counter(s.location_id for s in effective_scores(session, provider=provider))
    return {location_id for location_id, count in per_location.items() if count == category_count}
