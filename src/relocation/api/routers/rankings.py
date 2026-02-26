from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from relocation.database import get_db
from relocation.schemas import RankingOut
from relocation.services.ranking import compute_rankings

router = APIRouter(tags=["rankings"])


@router.get("/rankings", response_model=list[RankingOut])
def get_rankings(user: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Get weighted rankings for all locations.

    Query params:
      - user: "husband", "wife", or "combined" (default)
    """
    if user == "combined":
        user = None
    rankings = compute_rankings(db, user=user)
    return [
        RankingOut(
            location_name=r.location_name,
            country=r.country,
            overall_score=r.overall_score,
            husband_score=r.husband_score,
            wife_score=r.wife_score,
            details=[
                {
                    "category_name": d.category_name,
                    "score": d.score,
                    "husband_weight": d.husband_weight,
                    "wife_weight": d.wife_weight,
                    "husband_weighted": d.husband_weighted,
                    "wife_weighted": d.wife_weighted,
                }
                for d in r.details
            ],
        )
        for r in rankings
    ]
