from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from relocation.database import get_db
from relocation.models import Category, Research
from relocation.schemas import ResearchCreate, ResearchOut

router = APIRouter(tags=["research"])
STRICT_FRESHNESS_CATEGORIES = {"Visa / residency feasibility", "Tax implications"}


def _validate_strict_research_entry(data: ResearchCreate) -> None:
    source = (data.source or "").strip().lower()
    if not source:
        raise HTTPException(
            status_code=422,
            detail="Visa/tax research requires a source summary with dated citations.",
        )
    if "general knowledge" in source:
        raise HTTPException(
            status_code=422,
            detail="Visa/tax research cannot use 'general knowledge' as source basis.",
        )
    if not data.source_urls:
        raise HTTPException(
            status_code=422,
            detail="Visa/tax research requires at least one source URL.",
        )
    if not data.source_checked_at:
        raise HTTPException(
            status_code=422,
            detail="Visa/tax research requires source_checked_at.",
        )
    if data.confidence is None:
        raise HTTPException(
            status_code=422,
            detail="Visa/tax research requires a confidence score between 0 and 1.",
        )
    if data.verification_status == "stale":
        raise HTTPException(
            status_code=422,
            detail="New visa/tax research cannot be created with stale verification status.",
        )


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
    if data.category_id:
        category = db.get(Category, data.category_id)
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
        if category.name in STRICT_FRESHNESS_CATEGORIES:
            _validate_strict_research_entry(data)

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
