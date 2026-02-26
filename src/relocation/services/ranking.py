from dataclasses import dataclass

from sqlalchemy.orm import Session

from relocation.models import Category, Location, Score, User, Weight

DEFAULT_WEIGHT = 5.0


@dataclass
class CategoryDetail:
    category_name: str
    score: int
    husband_weight: float
    wife_weight: float
    husband_weighted: float
    wife_weighted: float


@dataclass
class LocationRanking:
    location_name: str
    country: str
    overall_score: float
    husband_score: float
    wife_score: float
    details: list[CategoryDetail]


def compute_rankings(session: Session, user: str | None = None) -> list[LocationRanking]:
    """
    Compute weighted rankings for all locations.

    user: "husband", "wife", or None for combined (averaged weights).
    Returns sorted list (highest score first).
    """
    locations = session.query(Location).all()
    categories = session.query(Category).order_by(Category.sort_order).all()
    users = {u.name: u for u in session.query(User).all()}

    # Build weight lookup: {(user_id, category_id): weight}
    weight_map: dict[tuple[int, int], float] = {}
    for w in session.query(Weight).all():
        weight_map[(w.user_id, w.category_id)] = w.weight

    # Build score lookup: {(location_id, category_id): score}
    score_map: dict[tuple[int, int], int] = {}
    for s in session.query(Score).all():
        score_map[(s.location_id, s.category_id)] = s.score

    husband = users.get("husband")
    wife = users.get("wife")

    rankings = []
    for loc in locations:
        details = []
        h_weighted_sum = 0.0
        h_weight_sum = 0.0
        w_weighted_sum = 0.0
        w_weight_sum = 0.0

        for cat in categories:
            score_val = score_map.get((loc.id, cat.id))
            if score_val is None:
                continue

            h_wt = weight_map.get((husband.id, cat.id), DEFAULT_WEIGHT) if husband else DEFAULT_WEIGHT
            w_wt = weight_map.get((wife.id, cat.id), DEFAULT_WEIGHT) if wife else DEFAULT_WEIGHT

            h_wtd = score_val * h_wt
            w_wtd = score_val * w_wt

            h_weighted_sum += h_wtd
            h_weight_sum += h_wt
            w_weighted_sum += w_wtd
            w_weight_sum += w_wt

            details.append(CategoryDetail(
                category_name=cat.name,
                score=score_val,
                husband_weight=h_wt,
                wife_weight=w_wt,
                husband_weighted=h_wtd,
                wife_weighted=w_wtd,
            ))

        h_score = h_weighted_sum / h_weight_sum if h_weight_sum > 0 else 0.0
        w_score = w_weighted_sum / w_weight_sum if w_weight_sum > 0 else 0.0

        if user == "husband":
            overall = h_score
        elif user == "wife":
            overall = w_score
        else:
            # Combined: average of the two weighted scores
            overall = (h_score + w_score) / 2 if (h_weight_sum > 0 or w_weight_sum > 0) else 0.0

        rankings.append(LocationRanking(
            location_name=loc.name,
            country=loc.country,
            overall_score=overall,
            husband_score=h_score,
            wife_score=w_score,
            details=details,
        ))

    rankings.sort(key=lambda r: r.overall_score, reverse=True)
    return rankings
