"""Weighted rankings for any set of users.

Each user's score for a location is the weight-averaged score over the categories
that location has scores for. The combined score blends the users' scores (mean).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from relocation.models import DEFAULT_PROVIDER, Category, Location, User, Weight
from relocation.services.effective_scores import effective_scores
from relocation.services.scoring import get_fully_scored_location_ids

DEFAULT_WEIGHT = 5.0
COMBINED = "combined"


@dataclass
class CategoryDetail:
    category_id: int
    category_name: str
    score: int
    weights: dict[int, float]  # user_id -> weight
    weighted: dict[int, float]  # user_id -> score * weight


@dataclass
class LocationRanking:
    location_id: int
    location_name: str
    country: str
    overall_score: float
    user_scores: dict[int, float]  # user_id -> weighted score
    details: list[CategoryDetail] = field(default_factory=list)
    scored_categories: int = 0
    total_categories: int = 0

    @property
    def coverage(self) -> float:
        return self.scored_categories / self.total_categories if self.total_categories else 0.0


def resolve_users(session: Session, user_ids: list[int] | None = None) -> list[User]:
    query = session.query(User).order_by(User.id)
    if user_ids:
        query = query.filter(User.id.in_(user_ids))
    return query.all()


def find_user(session: Session, user: str | int) -> User | None:
    """Look a user up by id or by name (case-insensitive)."""
    if isinstance(user, int) or str(user).isdigit():
        return session.get(User, int(user))
    return session.query(User).filter(User.name.ilike(str(user))).first()


def compute_rankings(
    session: Session,
    user: str | int | None = None,
    fully_scored_only: bool = False,
    provider: str = DEFAULT_PROVIDER,
    user_ids: list[int] | None = None,
) -> list[LocationRanking]:
    """Rank all locations, best first.

    user: a user id or name to rank by that person's score, or None / "combined"
    for the mean of all selected users (``user_ids``, default everyone).
    provider: rank using this provider's scores.
    """
    users = resolve_users(session, user_ids)
    focus: User | None = None
    if user not in (None, COMBINED):
        focus = find_user(session, user)
        if focus is None:
            raise ValueError(f"Unknown user: {user}")
        if focus not in users:
            users.append(focus)

    locations = session.query(Location).all()
    categories = session.query(Category).order_by(Category.sort_order).all()
    fully_scored = get_fully_scored_location_ids(session, provider=provider) if fully_scored_only else None

    weight_map = {(w.user_id, w.category_id): w.weight for w in session.query(Weight).all()}
    score_map = {(s.location_id, s.category_id): s.score for s in effective_scores(session, provider=provider)}

    rankings: list[LocationRanking] = []
    for loc in locations:
        if fully_scored is not None and loc.id not in fully_scored:
            continue

        sums = {u.id: 0.0 for u in users}
        weight_totals = {u.id: 0.0 for u in users}
        details: list[CategoryDetail] = []
        for cat in categories:
            score = score_map.get((loc.id, cat.id))
            if score is None:
                continue
            weights = {u.id: weight_map.get((u.id, cat.id), DEFAULT_WEIGHT) for u in users}
            weighted = {uid: score * w for uid, w in weights.items()}
            for uid in sums:
                sums[uid] += weighted[uid]
                weight_totals[uid] += weights[uid]
            details.append(CategoryDetail(cat.id, cat.name, score, weights, weighted))

        user_scores = {uid: (sums[uid] / weight_totals[uid] if weight_totals[uid] > 0 else 0.0) for uid in sums}
        if focus is not None:
            overall = user_scores[focus.id]
        else:
            overall = sum(user_scores.values()) / len(user_scores) if user_scores else 0.0

        rankings.append(
            LocationRanking(
                location_id=loc.id,
                location_name=loc.name,
                country=loc.country,
                overall_score=overall,
                user_scores=user_scores,
                details=details,
                scored_categories=len(details),
                total_categories=len(categories),
            )
        )

    rankings.sort(key=lambda r: r.overall_score, reverse=True)
    return rankings
