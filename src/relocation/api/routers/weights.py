from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from relocation.database import get_db
from relocation.models import User, Weight
from relocation.schemas import WeightCreate, WeightOut

router = APIRouter(tags=["weights"])


@router.get("/weights", response_model=list[WeightOut])
def list_weights(user_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(Weight)
    if user_id:
        query = query.filter(Weight.user_id == user_id)
    return query.all()


@router.get("/users/{user_name}/weights", response_model=list[WeightOut])
def get_user_weights(user_name: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.name.ilike(user_name)).first()
    if not user:
        raise HTTPException(404, f"User '{user_name}' not found")
    return db.query(Weight).filter(Weight.user_id == user.id).all()


@router.post("/weights", response_model=WeightOut, status_code=201)
def upsert_weight(data: WeightCreate, db: Session = Depends(get_db)):
    """Create or update a weight (upsert on user_id + category_id)."""
    existing = (
        db.query(Weight)
        .filter_by(user_id=data.user_id, category_id=data.category_id)
        .first()
    )
    if existing:
        existing.weight = data.weight
        db.commit()
        db.refresh(existing)
        return existing
    else:
        weight = Weight(**data.model_dump())
        db.add(weight)
        db.commit()
        db.refresh(weight)
        return weight
