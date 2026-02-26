from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from relocation.database import get_db
from relocation.models import Research
from relocation.schemas import ResearchCreate, ResearchOut

router = APIRouter(tags=["research"])


@router.get("/research", response_model=list[ResearchOut])
def list_research(
    location_id: Optional[int] = None,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Research)
    if location_id:
        query = query.filter(Research.location_id == location_id)
    if category_id:
        query = query.filter(Research.category_id == category_id)
    return query.order_by(Research.created_at.desc()).all()


@router.get("/research/{research_id}", response_model=ResearchOut)
def get_research(research_id: int, db: Session = Depends(get_db)):
    entry = db.get(Research, research_id)
    if not entry:
        raise HTTPException(404, "Research entry not found")
    return entry


@router.post("/research", response_model=ResearchOut, status_code=201)
def create_research(data: ResearchCreate, db: Session = Depends(get_db)):
    entry = Research(**data.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/research/{research_id}", status_code=204)
def delete_research(research_id: int, db: Session = Depends(get_db)):
    entry = db.get(Research, research_id)
    if not entry:
        raise HTTPException(404, "Research entry not found")
    db.delete(entry)
    db.commit()
