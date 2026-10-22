"""Scores as each location sees them.

- Location-scope categories: the location's own score for the provider.
- Country-scope categories (visa/residency): the location's country's score.
- Derived categories (swimming, beach access): one score serves every provider,
  because it is computed from data. If several rows exist, a manual override wins,
  then the computed score, then any legacy LLM score.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from relocation.models import Category, CountryScore, Location, Score


@dataclass
class EffectiveScore:
    id: int
    location_id: int
    category_id: int
    provider: str
    score: int
    notes: str | None
    method: str
    research_id: int | None
    run_id: int | None
    scope: str
    country_code: str | None
    created_at: datetime
    updated_at: datetime


_METHOD_PRIORITY = {"manual": 3, "derived": 2, "llm": 1}


def country_category_ids(session: Session) -> set[int]:
    return {cid for (cid,) in session.query(Category.id).filter(Category.scope == "country").all()}


def derived_category_ids(session: Session) -> set[int]:
    return {cid for (cid,) in session.query(Category.id).filter(Category.kind == "derived").all()}


def _pick_derived(rows: list[Score]) -> list[Score]:
    best: dict[tuple[int, int], Score] = {}
    for s in rows:
        key = (s.location_id, s.category_id)
        rank = (_METHOD_PRIORITY.get(s.method, 0), s.updated_at)
        if key not in best or rank > (_METHOD_PRIORITY.get(best[key].method, 0), best[key].updated_at):
            best[key] = s
    return list(best.values())


def effective_scores(
    session: Session,
    *,
    provider: str | None = None,
    location_id: int | None = None,
    category_id: int | None = None,
) -> list[EffectiveScore]:
    country_ids = country_category_ids(session)
    derived_ids = derived_category_ids(session)

    query = session.query(Score)
    if country_ids:
        query = query.filter(Score.category_id.notin_(country_ids))
    if location_id:
        query = query.filter(Score.location_id == location_id)
    if category_id:
        query = query.filter(Score.category_id == category_id)
    location_rows = query.all()
    derived_rows = _pick_derived([s for s in location_rows if s.category_id in derived_ids])
    provider_rows = [
        s for s in location_rows if s.category_id not in derived_ids and (not provider or s.provider == provider)
    ]
    rows = [
        EffectiveScore(
            id=s.id, location_id=s.location_id, category_id=s.category_id, provider=s.provider,
            score=s.score, notes=s.notes, method=s.method, research_id=s.research_id, run_id=s.run_id,
            scope="location", country_code=None, created_at=s.created_at, updated_at=s.updated_at,
        )
        for s in provider_rows + derived_rows
    ]

    if country_ids and (category_id is None or category_id in country_ids):
        cquery = (
            session.query(CountryScore, Location.id)
            .join(Location, Location.country_code == CountryScore.country_code)
            .filter(CountryScore.category_id.in_(country_ids))
        )
        if provider:
            cquery = cquery.filter(CountryScore.provider == provider)
        if location_id:
            cquery = cquery.filter(Location.id == location_id)
        if category_id:
            cquery = cquery.filter(CountryScore.category_id == category_id)
        rows.extend(
            EffectiveScore(
                id=cs.id, location_id=loc_id, category_id=cs.category_id, provider=cs.provider,
                score=cs.score, notes=cs.notes, method=cs.method, research_id=cs.research_id, run_id=cs.run_id,
                scope="country", country_code=cs.country_code, created_at=cs.created_at, updated_at=cs.updated_at,
            )
            for cs, loc_id in cquery.all()
        )
    return rows
