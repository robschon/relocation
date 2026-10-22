from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from relocation.database import get_db
from relocation.models import DEFAULT_PROVIDER
from relocation.schemas import RankingOut
from relocation.services.ranking import compute_rankings

router = APIRouter(tags=["rankings"])


@router.get("/rankings", response_model=list[RankingOut])
def get_rankings(
    user: Optional[str] = None,
    fully_scored_only: bool = False,
    provider: str = DEFAULT_PROVIDER,
    user_ids: Optional[list[int]] = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Weighted rankings for all locations, best first.

    Query params:
      - user: a user id or name to rank by that person's score, or "combined" (default)
        for the mean of all users
      - user_ids: limit which users are included (repeatable); default everyone
      - provider: whose scores to rank by (default "openai")
    """
    try:
        rankings = compute_rankings(
            db, user=user, fully_scored_only=fully_scored_only, provider=provider, user_ids=user_ids
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [
        RankingOut(
            location_id=r.location_id,
            location_name=r.location_name,
            country=r.country,
            overall_score=r.overall_score,
            user_scores=r.user_scores,
            scored_categories=r.scored_categories,
            total_categories=r.total_categories,
            coverage=r.coverage,
            details=[
                {
                    "category_id": d.category_id,
                    "category_name": d.category_name,
                    "score": d.score,
                    "weights": d.weights,
                    "weighted": d.weighted,
                }
                for d in r.details
            ],
        )
        for r in rankings
    ]
