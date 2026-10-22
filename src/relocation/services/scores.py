"""Score writes shared by the API, CLI and pipeline."""

from __future__ import annotations

from sqlalchemy.orm import Session

from relocation.models import DEFAULT_PROVIDER, CountryScore, Score
from relocation.services.effective_scores import EffectiveScore
from relocation.services.errors import ValidationFailed
from relocation.services.subjects import resolve_subject


def _effective(row, *, location_id, scope, country_code) -> EffectiveScore:
    return EffectiveScore(
        id=row.id, location_id=location_id, category_id=row.category_id, provider=row.provider,
        score=row.score, notes=row.notes, method=row.method, research_id=row.research_id, run_id=row.run_id,
        scope=scope, country_code=country_code, created_at=row.created_at, updated_at=row.updated_at,
    )


def upsert_score(
    db: Session,
    *,
    category_id: int,
    score: int,
    location_id: int | None = None,
    country_code: str | None = None,
    provider: str = DEFAULT_PROVIDER,
    notes: str | None = None,
    method: str = "manual",
    research_id: int | None = None,
    run_id: int | None = None,
) -> EffectiveScore:
    """Create or update a score (one per subject + category + provider).

    Country-scope categories are stored on the country. method / research_id / run_id
    always describe the latest write, so a manual edit of an LLM score becomes manual.
    """
    subject = resolve_subject(db, category_id=category_id, location_id=location_id, country_code=country_code)
    if subject.category is not None and subject.category.kind == "derived" and method == "llm":
        raise ValidationFailed(f"{subject.category.name} is computed from data; LLM scores are not accepted.")

    if subject.country_code:
        row = db.query(CountryScore).filter_by(
            country_code=subject.country_code, category_id=category_id, provider=provider
        ).first()
        if row is None:
            row = CountryScore(country_code=subject.country_code, category_id=category_id, provider=provider)
            db.add(row)
    else:
        row = db.query(Score).filter_by(location_id=subject.location_id, category_id=category_id, provider=provider).first()
        if row is None:
            row = Score(location_id=subject.location_id, category_id=category_id, provider=provider)
            db.add(row)

    row.score = score
    if notes is not None:
        row.notes = notes
    row.method = method
    row.research_id = research_id
    row.run_id = run_id
    db.commit()
    db.refresh(row)
    if subject.country_code:
        return _effective(row, location_id=subject.requested_location_id, scope="country", country_code=row.country_code)
    return _effective(row, location_id=row.location_id, scope="location", country_code=None)
