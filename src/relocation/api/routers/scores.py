from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from relocation.database import get_db
from relocation.models import Score
from relocation.schemas import ScoreCreate, ScoreOut

router = APIRouter(tags=["scores"])


@router.get("/scores", response_model=list[ScoreOut])
def list_scores(
    location_id: Optional[int] = None,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Score)
    if location_id:
        query = query.filter(Score.location_id == location_id)
    if category_id:
        query = query.filter(Score.category_id == category_id)
    return query.all()


@router.get("/locations/{location_id}/scores", response_model=list[ScoreOut])
def get_location_scores(location_id: int, db: Session = Depends(get_db)):
    return db.query(Score).filter(Score.location_id == location_id).all()


@router.post("/scores", response_model=ScoreOut, status_code=201)
def upsert_score(data: ScoreCreate, db: Session = Depends(get_db)):
    """Create or update a score (upsert on location_id + category_id)."""
    existing = (
        db.query(Score)
        .filter_by(location_id=data.location_id, category_id=data.category_id)
        .first()
    )
    if existing:
        existing.score = data.score
        if data.notes is not None:
            existing.notes = data.notes
        db.commit()
        db.refresh(existing)
        return existing
    else:
        score = Score(**data.model_dump())
        db.add(score)
        db.commit()
        db.refresh(score)
        return score
