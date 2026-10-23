from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from relocation.database import get_db
from relocation.schemas import ScoreCreate, ScoreOut
from relocation.services.effective_scores import effective_scores
from relocation.services.research_versions import current_research_location_ids
from relocation.services.scores import upsert_score

router = APIRouter(tags=["scores"])


@router.get("/scores", response_model=list[ScoreOut])
def list_scores(
    location_id: Optional[int] = None,
    category_id: Optional[int] = None,
    provider: Optional[str] = None,
    current_research_only: bool = False,
    db: Session = Depends(get_db),
):
    """Scores per location, with country-scope categories (visa) taken from the location's country."""
    rows = effective_scores(db, provider=provider, location_id=location_id, category_id=category_id)
    if current_research_only:
        current = current_research_location_ids(db)
        rows = [r for r in rows if r.location_id in current]
    return rows


@router.get("/locations/{location_id}/scores", response_model=list[ScoreOut])
def get_location_scores(location_id: int, provider: Optional[str] = None, db: Session = Depends(get_db)):
    return effective_scores(db, provider=provider, location_id=location_id)


@router.post("/scores", response_model=ScoreOut, status_code=201)
def create_or_update_score(data: ScoreCreate, db: Session = Depends(get_db)):
    """Create or update a score (upsert per subject + category + provider).

    For a country-scope category the score is stored on the country, so it applies to
    every location there. A score without ``method`` is a manual score.
    """
    return upsert_score(db, **data.model_dump())
