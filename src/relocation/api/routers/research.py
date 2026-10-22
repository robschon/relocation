from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from relocation.database import get_db
from sqlalchemy import and_, or_

from relocation.models import Location, Research
from relocation.schemas import ResearchCreate, ResearchOut
from relocation.services.effective_scores import country_category_ids
from relocation.services.research_records import create_research as create_research_record
from relocation.services.research_records import delete_research as delete_research_entry

router = APIRouter(tags=["research"])


@router.get("/research", response_model=list[ResearchOut])
def list_research(
    location_id: Optional[int] = None,
    category_id: Optional[int] = None,
    provider: Optional[str] = None,
    current_only: bool = False,
    country_code: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List research, newest first. ``current_only`` drops superseded history rows.

    With ``location_id``, country-level research for that location's country
    (visa/residency) is included too.
    """
    query = db.query(Research)
    if location_id:
        location = db.get(Location, location_id)
        condition = Research.location_id == location_id
        country_ids = country_category_ids(db)
        if location is not None and country_ids:
            condition = or_(
                condition,
                and_(
                    Research.location_id.is_(None),
                    Research.country_code == location.country_code,
                    Research.category_id.in_(country_ids),
                ),
            )
        query = query.filter(condition)
    if country_code:
        query = query.filter(Research.country_code == country_code.upper())
    if category_id:
        query = query.filter(Research.category_id == category_id)
    if provider:
        query = query.filter(Research.provider == provider)
    if current_only:
        query = query.filter(Research.is_current.is_(True))
    return query.order_by(Research.created_at.desc()).all()


@router.get("/research/{research_id}", response_model=ResearchOut)
def get_research(research_id: int, db: Session = Depends(get_db)):
    entry = db.get(Research, research_id)
    if not entry:
        raise HTTPException(404, "Research entry not found")
    return entry


@router.post("/research", response_model=ResearchOut, status_code=201)
def create_research(data: ResearchCreate, db: Session = Depends(get_db)):
    """Add research; for a country-scope category it is stored on the location's country."""
    return create_research_record(db, data.model_dump())


@router.delete("/research/{research_id}", status_code=204)
def delete_research(research_id: int, db: Session = Depends(get_db)):
    entry = db.get(Research, research_id)
    if not entry:
        raise HTTPException(404, "Research entry not found")
    delete_research_entry(db, entry)
