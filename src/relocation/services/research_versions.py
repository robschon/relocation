"""Which locations have all their researched categories on the current prompt version."""

from __future__ import annotations

from sqlalchemy.orm import Session

from relocation.models import DEFAULT_PROVIDER, Category, Location, Research, ResearchRun


def current_research_location_ids(
    session: Session, *, version: str | None = None, provider: str = DEFAULT_PROVIDER
) -> set[int]:
    """Locations whose every researched category (country rows for country-scope ones) comes
    from a run with ``version`` (default: the pipeline's current prompt version). One pass, no N+1."""
    if version is None:
        from relocation.settings import get_settings

        version = get_settings().prompt_version
    researched = {cid for (cid,) in session.query(Category.id).filter(Category.kind == "researched")}
    rows = (
        session.query(Research.location_id, Research.country_code, Research.category_id, ResearchRun.prompt_version)
        .outerjoin(ResearchRun, ResearchRun.id == Research.run_id)
        .filter(Research.is_current.is_(True), Research.provider == provider, Research.category_id.in_(researched))
        .all()
    )
    by_location: dict[int, set[int]] = {}
    by_country: dict[str, set[int]] = {}
    for location_id, country_code, category_id, prompt_version in rows:
        if prompt_version != version:
            continue
        if location_id is not None:
            by_location.setdefault(location_id, set()).add(category_id)
        else:
            by_country.setdefault(country_code, set()).add(category_id)
    return {
        loc_id
        for loc_id, country_code in session.query(Location.id, Location.country_code)
        if researched <= (by_location.get(loc_id, set()) | by_country.get(country_code, set()))
    }
