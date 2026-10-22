"""Write computed scores for derived categories (swimming viability, beach access).

A derived score is one row per location/category with provider "computed" and
method "derived". It serves every provider's rankings. A manual override (method
"manual") is never replaced; leftover LLM scores for the category are removed.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from relocation.models import Score

COMPUTED_PROVIDER = "computed"


def write_derived_score(
    session: Session,
    *,
    location_id: int,
    category_id: int,
    score: int,
    notes: str,
    run_id: int | None = None,
) -> str:
    """Upsert the computed score. Returns "created", "updated" or "kept_manual"."""
    rows = session.query(Score).filter(Score.location_id == location_id, Score.category_id == category_id).all()
    if any(row.method == "manual" for row in rows):
        return "kept_manual"

    target = next((row for row in rows if row.provider == COMPUTED_PROVIDER), None) or (rows[0] if rows else None)
    created = target is None
    if created:
        target = Score(location_id=location_id, category_id=category_id, provider=COMPUTED_PROVIDER, score=score)
        session.add(target)
    for row in rows:
        if row is not target:
            session.delete(row)
    target.provider = COMPUTED_PROVIDER
    target.score = score
    target.notes = notes
    target.method = "derived"
    target.research_id = None
    target.run_id = run_id
    return "created" if created else "updated"
