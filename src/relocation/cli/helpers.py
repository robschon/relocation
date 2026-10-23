from sqlalchemy.orm import Session

from relocation.models import Category, Location


def resolve_location(session: Session, query: str) -> Location:
    """Resolve a location by ID, slug ("rincon-puerto-rico") or case-insensitive name substring."""
    if query.isdigit():
        loc = session.get(Location, int(query))
        if loc:
            return loc
    by_slug = session.query(Location).filter(Location.slug == query.strip().lower()).one_or_none()
    if by_slug:
        return by_slug

    matches = (
        session.query(Location)
        .filter(Location.name.ilike(f"%{query}%"))
        .all()
    )
    exact = [m for m in matches if m.name.lower() == query.strip().lower()]
    if len(exact) == 1:
        return exact[0]  # "Lima" means Lima, not Limassol
    if len(matches) == 1:
        return matches[0]
    if len(matches) == 0:
        raise SystemExit(f"No location matching '{query}'")
    names = ", ".join(f"'{m.name}' (id={m.id})" for m in matches)
    raise SystemExit(f"Ambiguous: '{query}' matches multiple locations: {names}")


def resolve_category(session: Session, query: str) -> Category:
    """Resolve a category by ID or case-insensitive name substring."""
    if query.isdigit():
        cat = session.get(Category, int(query))
        if cat:
            return cat

    matches = (
        session.query(Category)
        .filter(Category.name.ilike(f"%{query}%"))
        .all()
    )
    if len(matches) == 1:
        return matches[0]
    if len(matches) == 0:
        raise SystemExit(f"No category matching '{query}'")
    names = ", ".join(f"'{m.name}' (id={m.id})" for m in matches)
    raise SystemExit(f"Ambiguous: '{query}' matches multiple categories: {names}")
